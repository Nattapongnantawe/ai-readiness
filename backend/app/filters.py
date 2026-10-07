"""Shared query filters for analytics endpoints (FR-DB-05). All SQL runs against the m4_jobs view."""
from dataclasses import dataclass

from fastapi import Query

from app.config import settings

ALL_DAYS = 3650  # "all data"


@dataclass
class JobFilters:
    days: int
    source: str | None
    province: str | None
    work_mode: str | None
    level: str | None

    @property
    def windowed(self) -> bool:
        return self.days < ALL_DAYS

    def where(self, alias: str = "j", previous: bool = False, use_window: bool = True) -> tuple[str, dict]:
        """SQL condition (always valid, starts with TRUE) and its bind parameters."""
        parts, params = ["TRUE"], {}
        if use_window and self.windowed:
            if previous:
                parts.append(f"{alias}.posted_at >= now() - make_interval(days => :days * 2) "
                             f"AND {alias}.posted_at < now() - make_interval(days => :days)")
            else:
                parts.append(f"{alias}.posted_at >= now() - make_interval(days => :days)")
            params["days"] = self.days
        for key in ("source", "province", "work_mode", "level"):
            value = getattr(self, key)
            if value:
                parts.append(f"{alias}.{key} = :f_{key}")
                params[f"f_{key}"] = value
        return " AND ".join(parts), params


def job_filters(
    days: int = Query(settings.default_days, ge=1, le=ALL_DAYS, description="Window in days (7, 30, 90, 365, 3650 = all)"),
    source: str | None = None,
    province: str | None = None,
    work_mode: str | None = None,
    level: str | None = None,
) -> JobFilters:
    return JobFilters(days=days, source=source, province=province, work_mode=work_mode, level=level)
