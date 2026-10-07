"""APScheduler wiring for the automatic pipeline (FR-CR-01..08).

* Schedules (per source: every N hours or daily at HH:MM) are stored in PostgreSQL, so they survive
  restarts (NFR-04). Missed runs while the computer was off run once when the API starts again.
* Only ONE pipeline run at a time for the whole system (scrapers, Gemini and the GPU are shared):
  a thread lock inside this process plus a PostgreSQL advisory lock across processes.
  A scheduled run that finds another run busy waits (QUEUE_WAIT_MIN) instead of being dropped.
* The work itself is app/pipeline.py.
"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, text

from app import pipeline
from app.config import settings
from app.db import SessionLocal, engine
from app.models import CrawlRun, CrawlSchedule

log = logging.getLogger("scheduler")

scheduler = BackgroundScheduler(
    timezone=settings.timezone,
    jobstores={"default": SQLAlchemyJobStore(engine=engine, tablename="m4_apscheduler_jobs")},
    # misfire: if the PC was off at 02:00, run once when the API comes back (within 12 h)
    job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 12 * 3600},
)
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pipeline")
_lock = threading.Lock()
ADVISORY_KEY = 7342001          # pg_advisory_lock key for "a pipeline run is active"
RUN_SOURCES = ("jobthai", "jobbkk", "process")


class RunInProgress(Exception):
    pass


class UnknownSource(Exception):
    pass


class NotReady(Exception):
    """Paths in .env are wrong: nothing would run."""


def _job_id(source: str) -> str:
    return f"crawl:{source}"


def scheduled_crawl(source: str) -> None:
    """Entry point APScheduler calls. Waits for a busy run instead of skipping the schedule."""
    deadline = time.monotonic() + settings.queue_wait_min * 60
    while True:
        try:
            start_run(source, "scheduled")
            return
        except RunInProgress:
            if time.monotonic() > deadline:
                log.warning("scheduled %s skipped: another run was busy for %s min", source, settings.queue_wait_min)
                return
            time.sleep(60)
        except NotReady as e:
            _record_failed(source, "scheduled", str(e))
            return


def apply_schedule(sched: CrawlSchedule) -> None:
    job_id = _job_id(sched.source)
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    if not sched.enabled:
        return
    if sched.mode == "interval":
        trigger = IntervalTrigger(hours=sched.every_hours or 6, timezone=settings.timezone)
    else:
        hh, mm = (sched.daily_at or "02:00").split(":")
        trigger = CronTrigger(hour=int(hh), minute=int(mm), timezone=settings.timezone)
    scheduler.add_job("app.scheduler:scheduled_crawl", trigger, args=[sched.source], id=job_id, replace_existing=True)


def next_run_at(source: str) -> datetime | None:
    job = scheduler.get_job(_job_id(source))
    return job.next_run_time if job else None


def active_run_id() -> int | None:
    with SessionLocal() as db:
        return db.scalar(select(CrawlRun.id).where(CrawlRun.status.in_(["queued", "running"])).limit(1))


def _record_failed(source: str, trigger: str, message: str) -> int:
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        run = CrawlRun(source=source, trigger=trigger, status="failed", log=[message], steps=[],
                       error_message=message[:500], finished_at=now)
        db.add(run)
        db.commit()
        return run.id


def start_run(source: str, trigger: str) -> int:
    if source not in RUN_SOURCES:
        raise UnknownSource(source)
    problems = pipeline.preflight(source)
    if problems:
        raise NotReady(" · ".join(problems))
    if not _lock.acquire(blocking=False):
        raise RunInProgress(source)
    try:
        if active_run_id():
            raise RunInProgress(source)
        with SessionLocal() as db:
            steps = [pipeline.Step(k, pipeline.STEP_LABELS[k]).as_dict() for k in pipeline.PLANS[source]]
            run = CrawlRun(source=source, trigger=trigger, status="queued", log=[], steps=steps)
            db.add(run)
            db.commit()
            run_id = run.id
    except Exception:
        _lock.release()
        raise
    _pool.submit(_execute, run_id, source)
    return run_id


def cancel_run(run_id: int) -> bool:
    with SessionLocal() as db:
        run = db.get(CrawlRun, run_id)
        if not run or run.status not in ("queued", "running"):
            return False
    return pipeline.request_cancel(run_id)


def _execute(run_id: int, source: str) -> None:
    conn = None
    try:
        conn = engine.connect()
        got = conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": ADVISORY_KEY}).scalar()
        if not got:
            pipeline.Store().save(run_id, status="failed", finished_at=datetime.now(timezone.utc),
                                  error_message="มีรอบอื่นกำลังรันอยู่ใน process อื่น (เช่น uvicorn เปิดซ้ำ 2 หน้าต่าง)")
            return
        pipeline.Runner(run_id, source).execute()
    except Exception as exc:  # noqa: BLE001 - a failed run must never stop the scheduler (NFR-05)
        log.exception("pipeline %s failed", source)
        pipeline.Store().save(run_id, status="failed", error_message=str(exc)[:500], finished_at=datetime.now(timezone.utc))
    finally:
        if conn is not None:
            try:
                conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": ADVISORY_KEY})
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        _lock.release()


def bootstrap() -> None:
    """Create default schedules, mark runs orphaned by a restart as failed, start the scheduler."""
    with SessionLocal() as db:
        for source in settings.sources:
            if not db.get(CrawlSchedule, source):
                # suggested times: JobThai 02:00, JobBKK 03:30 (never at the same time)
                db.add(CrawlSchedule(source=source, mode="daily", every_hours=24,
                                     daily_at="02:00" if source == "jobthai" else "03:30", enabled=False))
        for run in db.scalars(select(CrawlRun).where(CrawlRun.status.in_(["queued", "running"]))):
            run.status = "failed"
            run.error_message = "API ถูกปิด/รีสตาร์ตระหว่างรัน — ข้อมูลที่บันทึกแล้วไม่หาย รอบหน้าจะทำต่อ"
            run.finished_at = datetime.now(timezone.utc)
        db.commit()
        schedules = list(db.scalars(select(CrawlSchedule)))
    scheduler.start()
    for sched in schedules:
        apply_schedule(sched)


def shutdown() -> None:
    active = active_run_id()
    if active:
        pipeline.request_cancel(active)
    scheduler.shutdown(wait=False)
    _pool.shutdown(wait=False, cancel_futures=True)