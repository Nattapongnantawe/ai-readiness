from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

VIEWS_SQL = Path(__file__).with_name("sql") / "views.sql"

# Tables Modules 1-3 must already have created in the jobmarket database.
REQUIRED_TABLES = ["jobs", "companies", "skills", "job_skills", "skill_standard_map",
                   "curriculum_courses", "course_skill_map"]


class Base(DeclarativeBase):
    """Only Module 4's own tables (crawl_schedules, crawl_runs) are ORM models."""


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def rows(db: Session, sql: str, **params) -> list[dict]:
    """Run a SELECT and return plain dicts."""
    return [dict(r._mapping) for r in db.execute(text(sql), params)]


def one(db: Session, sql: str, **params) -> dict | None:
    r = db.execute(text(sql), params).first()
    return dict(r._mapping) if r else None


def split_sql(script: str) -> list[str]:
    """Split a .sql file into statements (statements end with ';' at the end of a line)."""
    body = "\n".join(line for line in script.splitlines() if not line.strip().startswith("--"))
    return [s.strip() for s in body.split(";\n") if s.strip().rstrip(";").strip()]


def init_db() -> None:
    from app import models  # noqa: F401  (register Module 4 tables)

    with engine.begin() as conn:
        present = {r[0] for r in conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"))}
        missing = [t for t in REQUIRED_TABLES if t not in present]
        if missing:
            raise RuntimeError(
                f"ฐานข้อมูลนี้ไม่มีตาราง {', '.join(missing)} — ตรวจ DATABASE_URL ว่าชี้ไปที่ jobmarket "
                f"และรัน migration ของ Module 1-3 ครบแล้ว (python -m scripts.check_db)")
        script = VIEWS_SQL.read_text(encoding="utf-8")
        has_logo = conn.execute(text(
            "SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema() "
            "AND table_name = 'companies' AND column_name = 'logo_url'")).first()
        if not has_logo:
            script = script.replace("c.logo_url ", "NULL::text ")
        for stmt in split_sql(script):
            conn.exec_driver_sql(stmt)
    # Creates m4_crawl_schedules / m4_crawl_runs only; shared tables are never created or altered here.
    Base.metadata.create_all(engine)
    with engine.begin() as conn:  # columns added after the first release of Module 4
        conn.exec_driver_sql("ALTER TABLE m4_crawl_runs ADD COLUMN IF NOT EXISTS steps JSON")
    try:  # content-change log + re-extract on change (app/changes.py)
        from app import changes
        with engine.begin() as conn:
            changes.install(conn)
    except Exception as e:  # noqa: BLE001 - the website still works without it
        import logging
        logging.getLogger("db").warning("job change tracking not installed: %s", e)
