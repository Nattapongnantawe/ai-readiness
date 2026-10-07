"""Automatic data pipeline (Module 1 → 2 → 3) run by the scheduler or the "รันตอนนี้" button.

A run is a list of steps. Every step calls the scripts you already use by hand, as a subprocess,
in their own folder and virtualenv, so nothing is re-implemented here:

  crawl       <scraper>\\venv\\Scripts\\python main.py --new --auto --stop-after N --max-updates M [--url U]
              (lines "@@FEED {json}" = live list of new / updated jobs shown on the Crawler page)
  load        <pipeline> python load.py --file <scraper>\\output\\jobs.jsonl --site <source>
  extract     <pipeline> python -m extractor.run --limit N                      (Gemini, only jobs not extracted)
  embed_jobs  <pipeline> python -m extractor.embed jobs                         (only jobs without embedding)
  skills      <pipeline> python -m extractor.embed skills  (+ embed map when new skills appeared)
  curriculum  in-process: exact course links for the new skills (insert only) + clear the gap cache

Every step only touches rows that are not done yet, so a failed or cancelled run is simply
continued by the next one. Only one run at a time (thread lock + PostgreSQL advisory lock).
Output of each step is streamed into the run's log (DB, last lines) and a full log file.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

log = logging.getLogger("pipeline")

STEP_LABELS = {
    "crawl": "ดึงประกาศ (Module 1)",
    "load": "นำเข้าฐานข้อมูล",
    "extract": "สกัดทักษะด้วย Gemini (Module 2)",
    "embed_jobs": "Embedding ประกาศ (Module 3)",
    "skills": "ทักษะใหม่ + จับคู่มาตรฐาน",
    "curriculum": "จับคู่หลักสูตร + อัปเดตหน้าเว็บ",
}
FULL = ["crawl", "load", "extract", "embed_jobs", "skills", "curriculum"]
# "process" = no crawling: import what the scrapers already saved (e.g. a run stopped mid-crawl) + steps 3-6
PLANS = {"jobthai": FULL, "jobbkk": FULL, "process": FULL[1:]}
SOURCE_LABELS = {"jobthai": "JobThai", "jobbkk": "JobBKK", "process": "ประมวลผลงานที่ค้าง"}

EXIT_ROBOTS = 3          # scrapers/polite.py: robots.txt disallows or cannot be read
LOG_TAIL = 400           # lines kept in the DB (full log is in the log file)
FEED_MAX = 500           # live feed items kept per run
FEED_PREFIX = "@@FEED "
FEED_TEXT = {"new": "✓ ใหม่", "updated": "↻ อัปเดต", "bumped": "↑ ดันประกาศ (เนื้อหาเดิม)",
             "partial": "⚠ ได้ไม่ครบ", "failed": "✗ ดึงไม่ได้"}
FLUSH_EVERY = 2.0        # seconds between DB writes while a step prints


class Cancelled(Exception):
    pass


class StepFailed(Exception):
    pass


class StepTimeout(StepFailed):
    """A step ran past its time limit. For the crawl this is a planned cut-off, not a failure."""


# ----------------------------------------------------------------------------- output parsing
def _num(pattern: str, text: str) -> int | None:
    m = re.findall(pattern, text)
    return int(m[-1]) if m else None


def parse_scraper(text: str) -> dict:
    return {k: v for k, v in {
        "seen": _num(r"เจอในหน้ารายการ\s*:\s*(\d+)", text),
        "new": (_num(r"เก็บใหม่สำเร็จ\s*:\s*(\d+)", text) or 0) + (_num(r"เก็บแต่ไม่ครบ\s*:\s*(\d+)", text) or 0),
        "skipped": _num(r"ข้าม \(เคยเก็บ\)\s*:\s*(\d+)", text),
        "failed": _num(r"ดึงไม่ได้เลย\s*:\s*(\d+)", text),
        "out_of_scope": _num(r"นอกสายงาน\s*:\s*(\d+)", text),
        "updated": _num(r"อัปเดต \(เนื้อหาเปลี่ยน\)\s*:\s*(\d+)", text),
        "bumped": _num(r"ดันประกาศ \(เนื้อหาเดิม\)\s*:\s*(\d+)", text),
    }.items() if v is not None}


def url_hash(url: str) -> str:
    """Same key the scrapers and load.py use (jobs.url_hash)."""
    return hashlib.sha256((url or "").split("?")[0].rstrip("/").encode("utf-8")).hexdigest()


def latest_lines(jsonl: Path, out: Path) -> tuple[int, int]:
    """jobs.jsonl gets a new line when a posting is re-scraped; keep only the newest line per job
    so load.py never writes the old version back over the new one."""
    keep: dict[str, str] = {}
    total = 0
    with open(jsonl, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            total += 1
            try:
                d = json.loads(ln)
            except json.JSONDecodeError:
                continue
            h = d.get("url_hash") or url_hash(d.get("source_url", ""))
            keep.pop(h, None)          # re-insert so the order follows the newest line
            keep[h] = ln
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.writelines(v + "\n" for v in keep.values())
    return total, len(keep)


def parse_load(text: str) -> dict:
    return {k: v for k, v in {"inserted": _num(r"งานเพิ่มใหม่\s*:\s*(\d+)", text),
                              "updated": _num(r"งานอัปเดต\s*:\s*(\d+)", text)}.items() if v is not None}


def parse_extract(text: str) -> dict:
    out = {"pending": _num(r"งานที่ต้องประมวลผล:\s*(\d+)", text), "quota": "quota เต็ม" in text}
    m = re.findall(r"สำเร็จ (\d+) \| ล้มเหลว (\d+) \| skills ที่ผูกกับงาน (\d+)", text)
    if m:
        out.update(done=int(m[-1][0]), failed=int(m[-1][1]), skills=int(m[-1][2]))
    return {k: v for k, v in out.items() if v is not None}


# ----------------------------------------------------------------------------- run state
@dataclass
class Step:
    key: str
    label: str
    status: str = "pending"            # pending / running / success / warning / failed / skipped / cancelled
    started_at: str | None = None
    finished_at: str | None = None
    summary: str = ""
    counts: dict = field(default_factory=dict)
    feed: list = field(default_factory=list)   # crawl only: jobs as they are scraped (newest last)

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    """Where a run is saved. The default writes m4_crawl_runs; tests pass a fake."""

    def save(self, run_id: int, **fields) -> None:  # pragma: no cover - DB glue
        from app.db import SessionLocal
        from app.models import CrawlRun
        with SessionLocal() as db:
            r = db.get(CrawlRun, run_id)
            if r is None:
                return
            for k, v in fields.items():
                setattr(r, k, v)
            db.commit()


_cancel: set[int] = set()
_procs: dict[int, subprocess.Popen] = {}
_lock = threading.Lock()


def request_cancel(run_id: int) -> bool:
    """Ask a running run to stop: the current subprocess (and its browser) is killed."""
    _cancel.add(run_id)
    proc = _procs.get(run_id)
    if proc and proc.poll() is None:
        _kill_tree(proc)
    return True


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False)
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:  # noqa: BLE001
        proc.kill()


# ----------------------------------------------------------------------------- paths / commands
def _venv_python(folder: str, override: str) -> str:
    if override:
        return override
    win = Path(folder) / "venv" / "Scripts" / "python.exe"
    posix = Path(folder) / "venv" / "bin" / "python"
    return str(win if win.exists() or os.name == "nt" else posix)


def scraper_dir(source: str) -> str:
    return settings.jobthai_dir if source == "jobthai" else settings.jobbkk_dir


def scraper_python(source: str) -> str:
    return _venv_python(scraper_dir(source), settings.jobthai_python if source == "jobthai" else settings.jobbkk_python)


def pipeline_python() -> str:
    return settings.pipeline_python or sys.executable


def listing_urls(source: str) -> list[str | None]:
    raw = settings.jobthai_urls if source == "jobthai" else settings.jobbkk_urls
    urls = [u.strip() for u in re.split(r"[|\n]", raw or "") if u.strip()]
    return urls or [None]          # None = use LISTING_URL in the scraper's config.py


def preflight(source: str) -> list[str]:
    """Problems that would make the run fail immediately (shown to the admin, nothing is run)."""
    problems = []
    if not settings.pipeline_dir or not Path(settings.pipeline_dir, "load.py").exists():
        problems.append(f"ไม่พบ load.py ใน PIPELINE_DIR ({settings.pipeline_dir or 'ยังไม่ตั้งค่า'})")
    if settings.pipeline_python and not Path(settings.pipeline_python).exists():
        problems.append(f"ไม่พบ PIPELINE_PYTHON: {settings.pipeline_python}")
    if source in ("jobthai", "jobbkk"):
        d = scraper_dir(source)
        if not d or not Path(d, "main.py").exists():
            problems.append(f"ไม่พบ main.py ของ {SOURCE_LABELS[source]} ({d or 'ยังไม่ตั้งค่า ' + source.upper() + '_DIR'})")
        elif not Path(scraper_python(source)).exists():
            problems.append(f"ไม่พบ python ของ {SOURCE_LABELS[source]}: {scraper_python(source)}")
        elif not Path(d, "polite.py").exists():
            problems.append(f"{SOURCE_LABELS[source]} ยังไม่มี polite.py (robots.txt / โหมด --auto) — วางไฟล์ที่ส่งให้ก่อน")
    return problems


def child_env() -> dict:
    env = os.environ.copy()
    env.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONUNBUFFERED="1")
    if settings.pipeline_pass_database_url:
        # load.py / extractor read DATABASE_URL; they use psycopg directly, so drop the "+psycopg" driver part
        env["DATABASE_URL"] = re.sub(r"^postgresql\+\w+://", "postgresql://", settings.database_url)
    return env


# ----------------------------------------------------------------------------- runner
class Runner:
    def __init__(self, run_id: int, source: str, store: Store | None = None,
                 in_process: Callable[[str, "Runner"], dict] | None = None):
        self.run_id, self.source = run_id, source
        self.store = store or Store()
        self.steps = [Step(k, STEP_LABELS[k]) for k in PLANS[source]]
        self.lines: list[str] = []
        self.totals = {"found": 0, "inserted": 0, "duplicated": 0, "pages_done": 0}
        self._last_flush = 0.0
        self._in_process = in_process or default_in_process
        self._takes_since = in_process is None      # test fakes take (what, runner) only
        self._found_before = self._skipped_before = 0
        self._step: Step | None = None
        logdir = Path(settings.pipeline_log_dir)
        logdir.mkdir(parents=True, exist_ok=True)
        self.logfile = logdir / f"run_{run_id}.log"

    # -- logging
    def say(self, line: str, flush: bool = False) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"{stamp}  {line.rstrip()}"
        self.lines.append(line)
        with open(self.logfile, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        if flush or time.monotonic() - self._last_flush > FLUSH_EVERY:
            self.flush()

    def flush(self, **extra) -> None:
        self._last_flush = time.monotonic()
        self.store.save(self.run_id, log=self.lines[-LOG_TAIL:], steps=[s.as_dict() for s in self.steps],
                        **self.totals, **extra)

    # -- subprocess
    def run_cmd(self, args: list[str], cwd: str, timeout_min: int) -> tuple[int, str]:
        if self.run_id in _cancel:
            raise Cancelled()
        self.say("$ " + " ".join(a if " " not in a else f'"{a}"' for a in args), flush=True)
        kw: dict = {}
        if os.name == "nt":
            kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        else:
            kw["start_new_session"] = True
        proc = subprocess.Popen(args, cwd=cwd, env=child_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", bufsize=1, **kw)
        _procs[self.run_id] = proc
        timed_out = threading.Event()

        def watchdog():
            deadline = time.monotonic() + timeout_min * 60
            while proc.poll() is None:
                if self.run_id in _cancel:
                    _kill_tree(proc)
                    return
                if time.monotonic() > deadline:
                    timed_out.set()
                    _kill_tree(proc)
                    return
                time.sleep(1)

        threading.Thread(target=watchdog, daemon=True).start()
        out = []
        assert proc.stdout is not None
        for raw in proc.stdout:
            if raw.startswith(FEED_PREFIX):
                self.on_feed(raw[len(FEED_PREFIX):])
                continue
            out.append(raw)
            if raw.strip():
                self.say("  " + raw.rstrip("\n"))
                self.on_line(raw)
        rc = proc.wait()
        _procs.pop(self.run_id, None)
        if self.run_id in _cancel:
            raise Cancelled()
        if timed_out.is_set():
            raise StepTimeout(f"เกินเวลา {timeout_min} นาที — หยุดขั้นนี้ (ข้อมูลที่ได้แล้วไม่หาย)")
        return rc, "".join(out)

    def on_line(self, raw: str) -> None:
        if self._current != "crawl":
            return
        m = re.search(r"\[หน้า (\d+)\]", raw)
        if m:
            self._page_in_url = max(self._page_in_url, int(m.group(1)))
        if "⏭" in raw:
            self._live_count("skipped")

    def _live_count(self, key: str) -> None:
        st = self._step
        if st is None:
            return
        live = st.counts.setdefault("live", {})
        live[key] = live.get(key, 0) + 1
        # run totals while crawling (a run stopped mid-crawl still shows what it did)
        self.totals["found"] = self._found_before + sum(live.values())
        self.totals["duplicated"] = self._skipped_before + live.get("skipped", 0)
        parts = [("new", "ใหม่"), ("updated", "อัปเดต"), ("bumped", "ดันประกาศ"), ("skipped", "ข้ามงานเดิม"),
                 ("failed", "ดึงไม่ได้")]
        st.summary = "กำลังดึง… " + " · ".join(f"{label} {live[k]}" for k, label in parts if live.get(k))

    def on_feed(self, payload: str) -> None:
        """One job just scraped: keep it for the live list and write a readable log line."""
        try:
            item = json.loads(payload)
        except json.JSONDecodeError:
            return
        kind = item.get("kind", "new")
        if self._step is not None:
            self._step.feed.append(item)
            del self._step.feed[:-FEED_MAX]
            self._live_count("new" if kind == "partial" else kind)
        extra = f" [{', '.join(item['changed'])}]" if item.get("changed") else ""
        who = " — ".join(x for x in (item.get("title"), item.get("company")) if x) or item.get("url", "")
        self.say(f"  {FEED_TEXT.get(kind, kind)}{extra}: {who}", flush=True)

    # -- steps
    def step_crawl(self, st: Step) -> None:
        py, cwd = scraper_python(self.source), scraper_dir(self.source)
        agg: dict = {}
        urls = listing_urls(self.source)
        for n, url in enumerate(urls, 1):
            args = ([py, "main.py", "--new", "--auto", "--delay", settings.crawl_delay,
                     "--stop-after", str(settings.stop_after_known),
                     "--max-updates", str(settings.max_updates_per_run)]
                    + (["--url", url] if url else []))
            if len(urls) > 1:
                self.say(f"หมวด {n}/{len(urls)}: {url}", flush=True)
            self._page_in_url = 0
            self._found_before, self._skipped_before = agg.get("seen", 0), agg.get("skipped", 0)
            st.counts.pop("live", None)
            rc, text = self.run_cmd(args, cwd, settings.timeout_crawl_min)
            self.totals["pages_done"] += self._page_in_url
            for k, v in parse_scraper(text).items():
                agg[k] = agg.get(k, 0) + v
            st.counts = agg
            self.totals["found"] = agg.get("seen", 0)
            self.totals["duplicated"] = agg.get("skipped", 0)
            if rc == EXIT_ROBOTS:
                raise StepFailed("หยุดตาม robots.txt (ไม่อนุญาต หรืออ่านไม่ได้) — ไม่ดึงข้อมูลรอบนี้")
            if rc != 0:
                raise StepFailed(f"scraper จบด้วยรหัส {rc} — งานที่ดึงได้ก่อนหน้านี้ยังถูกนำเข้าต่อ")
        st.counts.pop("live", None)
        if not agg.get("seen"):
            st.status = "warning"
            st.summary = ("หน้ารายการไม่พบงานเลย — เว็บอาจเปลี่ยนหน้าตาหรือจำกัดการเข้าถึงชั่วคราว "
                          "(ลอง python main.py --cards ในโฟลเดอร์ scraper)")
            return
        st.summary = (f"เจอ {agg.get('seen', 0)} · ใหม่ {agg.get('new', 0)}"
                      + (f" · อัปเดต {agg['updated']}" if agg.get("updated") else "")
                      + (f" · ดันประกาศ {agg['bumped']}" if agg.get("bumped") else "")
                      + f" · ข้าม {agg.get('skipped', 0)}"
                      + (f" · ดึงไม่ได้ {agg['failed']}" if agg.get("failed") else ""))

    def step_load(self, st: Step) -> None:
        sources = [self.source] if self.source in ("jobthai", "jobbkk") else ["jobthai", "jobbkk"]
        files = [(src, Path(scraper_dir(src), "output", "jobs.jsonl")) for src in sources if scraper_dir(src)]
        files = [(src, f) for src, f in files if f.exists()]
        if not files:
            st.status, st.summary = "skipped", "ยังไม่มีไฟล์ output/jobs.jsonl"
            return
        total: dict = {}
        for src, jsonl in files:
            one = Step(st.key, st.label)
            self._load_one(one, src, jsonl)
            for k, v in one.counts.items():
                total[k] = total.get(k, 0) + v
        st.counts = total
        self.totals["inserted"] = total.get("inserted", 0)
        st.summary = (f"งานใหม่ {total.get('inserted', 0)}"
                      + (f" · เนื้อหาเปลี่ยน {total['changed']} งาน" if total.get("changed") else "")
                      + (f" (สกัดทักษะใหม่ {total['reextract']})" if total.get("reextract") else ""))

    def _load_one(self, st: Step, source: str, jsonl: Path) -> None:
        latest = Path(settings.pipeline_log_dir).resolve() / f"load_{source}.jsonl"
        lines, jobs = latest_lines(jsonl, latest)
        if lines != jobs:
            self.say(f"jobs.jsonl {lines} บรรทัด = {jobs} งาน (ใช้บรรทัดล่าสุดของงานที่ถูกดึงซ้ำ)")
        started = datetime.now(timezone.utc)
        rc, text = self.run_cmd([pipeline_python(), "load.py", "--file", str(latest), "--site", source],
                                settings.pipeline_dir, settings.timeout_load_min)
        if rc != 0:
            raise StepFailed(f"load.py จบด้วยรหัส {rc}")
        st.counts = parse_load(text)
        ch = self._in_process("changes_since", self, since=started) if self._takes_since else {}
        st.counts.update({k: v for k, v in ch.items() if isinstance(v, int)})

    def step_extract(self, st: Step) -> None:
        rc, text = self.run_cmd([pipeline_python(), "-m", "extractor.run", "--limit", str(settings.extract_limit_per_run)],
                                settings.pipeline_dir, settings.timeout_extract_min)
        if rc != 0:
            raise StepFailed(f"extractor.run จบด้วยรหัส {rc}")
        st.counts = parse_extract(text)
        st.summary = (f"สกัดแล้ว {st.counts.get('done', 0)} งาน · ทักษะ {st.counts.get('skills', 0)}"
                      + (f" · ล้มเหลว {st.counts['failed']}" if st.counts.get("failed") else ""))
        if st.counts.get("quota"):
            st.status = "warning"
            st.summary += " · โควตา Gemini หมด งานที่เหลือจะทำรอบหน้า"

    def step_embed_jobs(self, st: Step) -> None:
        rc, text = self.run_cmd([pipeline_python(), "-m", "extractor.embed", "jobs"],
                                settings.pipeline_dir, settings.timeout_embed_min)
        if rc != 0:
            raise StepFailed(f"embed jobs จบด้วยรหัส {rc}")
        n = _num(r"ประกาศที่ต้อง embed:\s*(\d+)", text) or 0
        st.counts, st.summary = {"embedded": n}, f"embed {n} ประกาศ"

    def step_skills(self, st: Step) -> None:
        rc, text = self.run_cmd([pipeline_python(), "-m", "extractor.embed", "skills"],
                                settings.pipeline_dir, settings.timeout_embed_min)
        if rc != 0:
            raise StepFailed(f"embed skills จบด้วยรหัส {rc}")
        n = _num(r"ทักษะที่ต้อง embed:\s*(\d+)", text) or 0
        st.counts = {"new_skills": n}
        if n == 0:
            st.summary = "ไม่มีทักษะใหม่ — ข้ามการจับคู่มาตรฐาน"
            return
        rc, text = self.run_cmd([pipeline_python(), "-m", "extractor.embed", "map"],
                                settings.pipeline_dir, settings.timeout_embed_min)
        if rc != 0:
            raise StepFailed(f"embed map จบด้วยรหัส {rc}")
        st.counts["std_links"] = _num(r"เติมคู่ใหม่\s*(\d+)", text) or 0
        st.summary = f"ทักษะใหม่ {n} · คู่มาตรฐาน {st.counts['std_links']}"

    def step_curriculum(self, st: Step) -> None:
        st.counts = self._in_process("curriculum", self)
        st.summary = f"คู่วิชา–ทักษะใหม่ {st.counts.get('links', 0)} · ล้าง cache หน้า Gap แล้ว"

    # -- main
    def execute(self) -> str:
        self._current, self._page_in_url, self._step = "", 0, None
        self.skill_id_before = self._in_process("max_skill_id", self).get("max_skill_id", 0)
        status, error = "success", None
        self.store.save(self.run_id, status="running")
        self.say(f"เริ่มรอบ {SOURCE_LABELS[self.source]} (run #{self.run_id})", flush=True)
        try:
            for st in self.steps:
                self._current, self._step = st.key, st
                st.status, st.started_at = "running", _now()
                self.flush()
                try:
                    getattr(self, f"step_{st.key}")(st)
                    if st.status == "running":
                        st.status = "success"
                except StepTimeout as e:
                    if st.key != "crawl":
                        st.status, st.summary = "failed", str(e)
                        status, error = "failed", f"{st.label}: {e}"
                        self.say(f"✗ {st.label}: {e}", flush=True)
                        break
                    # crawl reached its time limit: what was scraped is imported and processed as usual,
                    # the rest is picked up by the next run -> warning, not failure
                    live = st.counts.pop("live", {})
                    done = " · ".join(f"{label} {live[k]}" for k, label in
                                      (("new", "ใหม่"), ("updated", "อัปเดต"), ("bumped", "ดันประกาศ"), ("skipped", "ข้าม"))
                                      if live.get(k))
                    st.status = "warning"
                    st.summary = (f"ครบเวลา {settings.timeout_crawl_min} นาที — หยุดดึง ส่วนที่เหลือดึงต่อรอบหน้า"
                                  + (f" · {done}" if done else ""))
                    self.say(f"⏱ {st.label}: {st.summary}", flush=True)
                except StepFailed as e:
                    st.status, st.summary = "failed", str(e)
                    status, error = "failed", f"{st.label}: {e}"
                    self.say(f"✗ {st.label}: {e}", flush=True)
                    # robots.txt / missing files: stop. A crashed crawl still loads what it saved.
                    if st.key != "crawl" or "robots" in str(e):
                        break
                finally:
                    st.finished_at = _now()
                    if st.status != "running":
                        self.say(f"• {st.label}: {st.summary or st.status}", flush=True)
        except Cancelled:
            status, error = "cancelled", "หยุดโดยผู้ดูแล — ข้อมูลที่บันทึกแล้วไม่หาย รอบหน้าจะทำต่อ"
            for st in self.steps:
                if st.status == "running":
                    st.status, st.finished_at = "cancelled", _now()
                    if st.summary.startswith("กำลังดึง… "):
                        st.summary = "หยุดก่อนจบ: " + st.summary[len("กำลังดึง… "):]
            self.say("⏹ " + error, flush=True)
        except Exception as e:  # noqa: BLE001 - never let a run take the scheduler down
            log.exception("pipeline run %s crashed", self.run_id)
            status, error = "failed", f"ข้อผิดพลาดภายใน: {str(e)[:300]}"
            self.say("✗ " + error, flush=True)
        finally:
            for st in self.steps:
                if st.status == "pending":
                    st.status = "skipped"
            _cancel.discard(self.run_id)
            _procs.pop(self.run_id, None)
        if status == "success" and any(s.status == "warning" for s in self.steps):
            status = "warning"
        self.say(f"จบรอบ: {status}", flush=True)
        self.flush(status=status, error_message=error, finished_at=datetime.now(timezone.utc))
        return status


# ----------------------------------------------------------------------------- in-process steps (DB)
def default_in_process(what: str, runner: Runner, since=None) -> dict:  # pragma: no cover - DB glue
    from app.db import SessionLocal, one
    if what == "changes_since":
        try:
            with SessionLocal() as db:
                r = one(db, """SELECT count(DISTINCT job_id) AS changed,
                                      count(DISTINCT job_id) FILTER (WHERE reextract) AS reextract
                               FROM m4_job_changes WHERE changed_at >= :t""", t=since)
            return {k: int(v or 0) for k, v in (r or {}).items()}
        except Exception:  # noqa: BLE001 - table missing: no change log
            return {}
    if what == "max_skill_id":
        with SessionLocal() as db:
            return {"max_skill_id": (one(db, "SELECT coalesce(max(id), 0) AS m FROM skills") or {"m": 0})["m"]}
    if what == "curriculum":
        return link_new_skills(runner.skill_id_before)
    return {}


def link_new_skills(since_skill_id: int) -> dict:  # pragma: no cover - DB glue
    """Exact course links for skills created during this run. Insert only: existing links —
    including the ones the researcher added on the web (method manual) — are never touched."""
    from sqlalchemy import text as sql

    from app import gap
    from app.db import SessionLocal, rows
    from app.skill_extract import exact_ok, name_in_text

    links = 0
    with SessionLocal() as db:
        new = [r for r in rows(db, """SELECT s.id, s.name FROM skills s WHERE s.id > :m
                                      AND EXISTS (SELECT 1 FROM job_skills js WHERE js.skill_id = s.id)""", m=since_skill_id)
               if exact_ok(r["name"])]
        if new:
            for c in rows(db, "SELECT course_code, name_th, name_en, description_th, description_en FROM curriculum_courses"):
                hay = f"{c['name_en'] or ''} ; {c['description_en'] or ''} ; {c['description_th'] or ''} ; {c['name_th']}"
                for s in new:
                    if name_in_text(s["name"], hay):
                        res = db.execute(sql("""INSERT INTO course_skill_map (course_code, skill_id, similarity, method, matched_topic)
                                                VALUES (:c, :s, 1.0, 'exact', 'auto pipeline')
                                                ON CONFLICT (course_code, skill_id) DO NOTHING"""),
                                         {"c": c["course_code"], "s": s["id"]})
                        links += res.rowcount or 0
            db.commit()
    gap.clear_cache()
    return {"new_skills": len(new), "links": links}
