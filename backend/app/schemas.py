from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import settings

Level = Literal["Entry", "Mid", "Senior"]
WorkMode = Literal["Onsite", "Hybrid", "Remote"]


# ---------- auth ----------
class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    expires_at: datetime


# ---------- crawler ----------
class ScheduleIn(BaseModel):
    mode: Literal["interval", "daily"]
    every_hours: int | None = Field(default=None, ge=1, le=168)
    daily_at: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    enabled: bool = True

    @model_validator(mode="after")
    def check_mode(self):
        if self.mode == "interval":
            if self.every_hours is None:
                raise ValueError("every_hours is required when mode is interval")
            if self.every_hours < settings.min_interval_hours:
                raise ValueError(f"every_hours must be at least {settings.min_interval_hours}")
        if self.mode == "daily" and not self.daily_at:
            raise ValueError("daily_at (HH:MM) is required when mode is daily")
        return self


class RunOut(BaseModel):
    id: int
    source: str
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    found: int
    inserted: int
    duplicated: int
    pages_done: int
    pages_total: int | None
    log: list[str] = []
    steps: list[dict] = []
    error_message: str | None

    model_config = {"from_attributes": True}

    @field_validator("log", "steps", mode="before")
    @classmethod
    def none_to_list(cls, v):
        return v or []

    @field_validator("steps", mode="after")
    @classmethod
    def drop_feed(cls, v):
        # the live job list is served by /crawler/runs/{id}/feed; keep run polling small
        return [{**{k: x for k, x in st.items() if k != "feed"}, "feed_count": len(st["feed"]) if "feed" in st else None}
                for st in v]


class SourceOut(BaseModel):
    source: str
    label: str = ""
    mode: str
    every_hours: int | None
    daily_at: str | None
    enabled: bool
    next_run_at: datetime | None
    last_run: RunOut | None
    categories: list[str] = []      # listing URLs a run visits
    problems: list[str] = []        # why a run cannot start (paths in .env)


class CrawlerStatus(BaseModel):
    active_run_id: int | None
    process_problems: list[str]
    extract_limit_per_run: int
    auto_delay: str
    robots_txt: bool = True


class RunCreated(BaseModel):
    run_id: int


# ---------- search / jobs ----------
class SearchFilters(BaseModel):
    min_salary: int | None = None
    level: list[Level] | None = None
    work_mode: list[WorkMode] | None = None
    province: list[str] | None = None
    source: list[str] | None = None


class SearchIn(BaseModel):
    query: str = Field(default="", max_length=500)   # empty = browse all jobs, newest first
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)
    group_duplicates: bool = True   # same company + same title (branch postings) → one card
    filters: SearchFilters = SearchFilters()

    @field_validator("query")
    @classmethod
    def strip_query(cls, v: str) -> str:
        v = v.strip()
        return v if len(v) >= 2 else ""


class SkillOut(BaseModel):
    id: int
    name: str
    type: str
    is_ai_skill: bool
    is_required: bool = True
    standards: list[str] = []          # e.g. ["ESCO: computer networks", "O*NET: Cisco IOS"]


class JobCard(BaseModel):
    job_id: int
    title: str
    company: str | None
    province: str | None
    salary_min: int | None
    salary_max: int | None
    level: str | None
    work_mode: str | None
    source: str
    source_url: str
    top_skills: list[str]
    similarity: float | None        # None in browse mode (no query)
    posted_at: datetime | None = None
    company_logo: str | None = None
    similar_postings: int = 0       # other postings of the same company + title folded into this card


class SearchOut(BaseModel):
    mode: str = "semantic"          # semantic (query) / browse (no query → all jobs, newest first)
    took_ms: dict[str, float]
    results: list[JobCard]
    page: int = 1
    page_size: int = 20
    total: int = 0                  # cards available (after grouping), capped at max_results
    max_results: int = 200
    capped: bool = False            # True = more jobs exist beyond the closest max_results


class JobDetail(BaseModel):
    id: int
    title: str
    company: str | None
    company_logo: str | None = None
    province: str | None
    salary_min: int | None
    salary_max: int | None
    level: str | None
    work_mode: str | None
    source: str
    source_url: str
    description: str | None
    qualification: str | None = None
    welfare: str | None = None
    experience_years: float | None = None
    education_level: str | None = None
    employment_type: str | None = None
    seniority_raw: str | None = None
    is_ai_related: bool
    posted_at: datetime | None
    last_updated_at: datetime | None
    skills: list[SkillOut]


# ---------- curriculum ----------
class CourseIn(BaseModel):
    code: str = Field(min_length=1, max_length=16)
    name_th: str = Field(min_length=1)
    name_en: str | None = None
    description: str = ""                      # Thai description (curriculum_courses.description_th)
    description_en: str | None = None
    year: int | None = Field(default=None, ge=1, le=8)   # not stored in มคอ.2 data; accepted for compatibility
    credits: str | None = None                 # "3(2-2-5)" or "3"
    category: str | None = None
    course_group: str | None = None


class CourseUpdate(BaseModel):
    name_th: str | None = None
    name_en: str | None = None
    description: str | None = None
    description_en: str | None = None
    year: int | None = Field(default=None, ge=1, le=8)
    credits: str | None = None
    category: str | None = None
    course_group: str | None = None


class CourseSkillsIn(BaseModel):
    skills: list[str]


class CourseSkill(BaseModel):
    name: str
    method: str                                # exact / semantic / manual
    similarity: float | None
    jobs: int                                  # jobs that ask for this skill


class CourseOut(BaseModel):
    code: str
    name_th: str
    name_en: str | None
    description: str
    description_en: str | None = None
    year: int | None
    credits: str | None
    category: str | None = None
    course_group: str | None = None
    prerequisite: list[str] = []
    skills: list[str]
    skill_links: list[CourseSkill] = []
