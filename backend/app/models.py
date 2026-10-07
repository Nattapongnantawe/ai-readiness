"""Module 4 own tables (prefixed m4_ so they never clash with Module 1 tables such as crawl_runs). Everything else (jobs, skills, curriculum ...) is read from the
jobmarket database through raw SQL and the views in app/sql/views.sql."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CrawlSchedule(Base):
    __tablename__ = "m4_crawl_schedules"

    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    mode: Mapped[str] = mapped_column(String(16), default="interval")  # interval / daily
    every_hours: Mapped[int | None] = mapped_column(Integer, default=6)
    daily_at: Mapped[str | None] = mapped_column(String(5))  # "HH:MM"
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CrawlRun(Base):
    __tablename__ = "m4_crawl_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)       # jobthai / jobbkk / process
    trigger: Mapped[str] = mapped_column(String(16))  # manual / scheduled
    # queued / running / success / warning / failed / cancelled
    status: Mapped[str] = mapped_column(String(16), default="queued")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    found: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    duplicated: Mapped[int] = mapped_column(Integer, default=0)
    pages_done: Mapped[int] = mapped_column(Integer, default=0)
    pages_total: Mapped[int | None] = mapped_column(Integer)
    log: Mapped[list] = mapped_column(JSON, default=list)
    steps: Mapped[list] = mapped_column(JSON, default=list)   # pipeline steps (app/pipeline.py)
    error_message: Mapped[str | None] = mapped_column(Text)