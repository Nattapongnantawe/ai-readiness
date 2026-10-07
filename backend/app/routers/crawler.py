"""Crawler control (FR-CR): schedules per source, run now, process pending jobs, cancel, logs."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import pipeline
from app import scheduler as sch
from app.auth import require_admin
from app.config import settings
from app.changes import TRACKED
from app.db import get_db, rows
from app.models import CrawlRun, CrawlSchedule
from app.schemas import CrawlerStatus, RunCreated, RunOut, ScheduleIn, SourceOut

router = APIRouter(prefix="/crawler", tags=["crawler"])


def _source_out(db: Session, sched: CrawlSchedule) -> SourceOut:
    last = db.scalar(select(CrawlRun).where(CrawlRun.source == sched.source).order_by(CrawlRun.started_at.desc()).limit(1))
    return SourceOut(source=sched.source, label=pipeline.SOURCE_LABELS.get(sched.source, sched.source),
                     mode=sched.mode, every_hours=sched.every_hours, daily_at=sched.daily_at,
                     enabled=sched.enabled, next_run_at=sch.next_run_at(sched.source),
                     last_run=RunOut.model_validate(last) if last else None,
                     categories=[u or "ค่า LISTING_URL ใน config.py" for u in pipeline.listing_urls(sched.source)],
                     problems=pipeline.preflight(sched.source))


def _get_schedule(db: Session, source: str) -> CrawlSchedule:
    sched = db.get(CrawlSchedule, source)
    if not sched:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "UNKNOWN_SOURCE", "message": f"No source named {source}"})
    return sched


def _start(source: str) -> RunCreated:
    try:
        return RunCreated(run_id=sch.start_run(source, "manual"))
    except sch.RunInProgress:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail={"code": "RUN_IN_PROGRESS", "message": "มีรอบอื่นกำลังรันอยู่ รอให้จบก่อน หรือกดหยุด"})
    except sch.NotReady as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "NOT_READY", "message": str(e)})


@router.get("/status", response_model=CrawlerStatus)
def crawler_status():
    return CrawlerStatus(active_run_id=sch.active_run_id(), process_problems=pipeline.preflight("process"),
                         extract_limit_per_run=settings.extract_limit_per_run,
                         auto_delay=f"{settings.crawl_delay.replace('-', '–')} วินาที/request · ช้าลงเองถ้าเว็บตอบ 429/5xx · เคารพ Crawl-delay ของ robots.txt")


@router.get("/sources", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db)):
    scheds = db.scalars(select(CrawlSchedule).where(CrawlSchedule.source.in_(settings.sources)).order_by(CrawlSchedule.source))
    return [_source_out(db, s) for s in scheds]


@router.put("/sources/{source}/schedule", response_model=SourceOut, dependencies=[Depends(require_admin)])
def update_schedule(source: str, body: ScheduleIn, db: Session = Depends(get_db)):
    sched = _get_schedule(db, source)
    sched.mode, sched.enabled = body.mode, body.enabled
    sched.every_hours = body.every_hours if body.mode == "interval" else sched.every_hours
    sched.daily_at = body.daily_at if body.mode == "daily" else sched.daily_at
    db.commit()
    sch.apply_schedule(sched)  # takes effect immediately, no restart (FR-CR-03)
    return _source_out(db, sched)


@router.post("/sources/{source}/runs", response_model=RunCreated, status_code=status.HTTP_202_ACCEPTED,
             dependencies=[Depends(require_admin)])
def run_now(source: str, db: Session = Depends(get_db)):
    _get_schedule(db, source)
    return _start(source)


@router.post("/process", response_model=RunCreated, status_code=status.HTTP_202_ACCEPTED,
             dependencies=[Depends(require_admin)])
def process_pending():
    """Steps 2–6 (no crawling): import what the scrapers saved (both sites), then extract / embed / map what is pending."""
    return _start("process")


@router.post("/runs/{run_id}/cancel", dependencies=[Depends(require_admin)])
def cancel(run_id: int):
    if not sch.cancel_run(run_id):
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "NOT_RUNNING", "message": "รอบนี้ไม่ได้กำลังรัน"})
    return {"ok": True}


@router.get("/runs", response_model=list[RunOut])
def list_runs(source: str | None = None, limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    stmt = select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(limit)
    if source:
        stmt = stmt.where(CrawlRun.source == source)
    return list(db.scalars(stmt))


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(CrawlRun, run_id)
    if not run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "RUN_NOT_FOUND", "message": "No such run"})
    return run


def _short(v, n: int = 400):
    if v is None:
        return None
    v = str(v)
    return v if len(v) <= n else v[:n] + "…"


@router.get("/runs/{run_id}/feed")
def run_feed(run_id: int, db: Session = Depends(get_db)):
    """Jobs scraped in this run (newest first), each linked to the job in our database
    and, for updated postings, the fields that changed (old -> new) — for checking against the real site."""
    run = get_run(run_id, db)
    feed = next((st.get("feed") or [] for st in (run.steps or []) if st.get("key") == "crawl"), [])
    hashes = list({pipeline.url_hash(it.get("url", "")) for it in feed})
    jobs = {r["url_hash"]: r["id"] for r in rows(db, "SELECT id, url_hash FROM jobs WHERE url_hash = ANY(:h)", h=hashes)} if hashes else {}
    changes: dict[int, dict] = {}
    ids = list(jobs.values())
    if ids:
        try:
            for r in rows(db, """SELECT DISTINCT ON (job_id) job_id, fields, old_values, new_values, reextract
                                 FROM m4_job_changes WHERE job_id = ANY(:ids) AND changed_at >= :t
                                 ORDER BY job_id, changed_at DESC""", ids=ids, t=run.started_at):
                changes[r["job_id"]] = {
                    "reextract": r["reextract"],
                    "fields": [{"field": f, "label": TRACKED.get(f, f),
                                "old": None if f == "company_id" else _short(r["old_values"].get(f)),
                                "new": None if f == "company_id" else _short(r["new_values"].get(f))}
                               for f in r["fields"]],
                }
        except Exception:  # noqa: BLE001 - change log not installed
            db.rollback()
    out = []
    for it in reversed(feed):
        jid = jobs.get(pipeline.url_hash(it.get("url", "")))
        out.append({**it, "job_id": jid, "db_changes": changes.get(jid) if jid else None})
    return out


@router.get("/runs/{run_id}/log", response_class=PlainTextResponse, dependencies=[Depends(require_admin)])
def run_log(run_id: int, db: Session = Depends(get_db)):
    """Full log of a run (the run itself keeps only the last lines)."""
    path = Path(settings.pipeline_log_dir) / f"run_{run_id}.log"
    if path.exists():
        return PlainTextResponse(path.read_text(encoding="utf-8", errors="replace"),
                                 headers={"Content-Disposition": f'attachment; filename="run_{run_id}.log"'})
    run = get_run(run_id, db)
    return PlainTextResponse("\n".join(run.log or []))
