"""Application settings, read from environment variables or `.env`."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # The jobmarket database built by Modules 1-3 (same DB the pipeline writes to).
    database_url: str = "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/jobmarket"  # set in .env
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    timezone: str = "Asia/Bangkok"
    # Built web app (npm run build -> frontend/dist). When it exists, the API also serves the website on
    # the same port, so one process = whole system (http://localhost:8000). Empty = <project>/frontend/dist
    frontend_dist: str = ""

    # Embeddings: must be the same model Module 3 used for jobs.embedding (bge-m3, 1024 dims, normalised).
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    embedding_device: str | None = None      # None = auto (cuda if available)
    use_fake_embeddings: bool = False
    hnsw_ef_search: int = 100
    search_max_results: int = 200         # semantic search pages through the closest N jobs
    gap_suggest_min: float = 0.55         # below this, a missing skill has no close course topic

    # Admin auth (FR-AU-01). AUTH_ENABLED=false turns every admin check off.
    auth_enabled: bool = True
    admin_username: str = "admin"
    admin_password: str = "change-me"
    jwt_secret: str = "change-me-please-use-a-long-random-string"
    jwt_expire_hours: int = 8

    # Automatic pipeline (app/pipeline.py). Schedules start disabled; turn them on in the Crawler page.
    crawler_sources: str = "jobthai,jobbkk"
    min_interval_hours: int = 1
    pipeline_dir: str = r"C:\projeb\pipeline"          # load.py + extractor/
    pipeline_python: str = ""                           # empty = the python running this API (pipeline venv)
    pipeline_pass_database_url: bool = True             # give load.py / extractor the same DATABASE_URL
    pipeline_log_dir: str = "logs"                      # full log of every run: logs/run_<id>.log
    jobthai_dir: str = r"C:\projeb\jobthai_v3"
    jobthai_python: str = ""                            # empty = <jobthai_dir>\venv\Scripts\python.exe
    # JobThai categories, one run visits each ( | separated ). jobtype=7 = คอมพิวเตอร์/ไอที,
    # subjobtype=116 = วิศวกรไฟฟ้า/อิเล็กทรอนิกส์ — the two lists the current dataset came from.
    jobthai_urls: str = "https://www.jobthai.com/th/jobs?jobtype=7|https://www.jobthai.com/th/jobs?subjobtype=116"
    jobbkk_dir: str = r"C:\projeb\jobbkk_v341"
    jobbkk_python: str = ""
    jobbkk_urls: str = ""                               # empty = LISTING_URL in jobbkk config.py
    extract_limit_per_run: int = 500                    # jobs sent to Gemini per run (quota)
    stop_after_known: int = 200                         # --new stops after N already-saved jobs in a row
    crawl_delay: str = "4-7"                            # seconds between requests (random in range); auto slows down on 429/5xx
    max_updates_per_run: int = 50                       # known jobs re-opened because the listing shows a newer date
    timeout_crawl_min: int = 240
    timeout_load_min: int = 30
    timeout_extract_min: int = 180
    timeout_embed_min: int = 60
    queue_wait_min: int = 240                           # a scheduled run waits this long if another run is busy

    # Dashboard
    default_days: int = 3650               # 3650 = all data (the dataset is a snapshot)
    salary_floor: int = 5_000              # ignore salaries outside this monthly range (parse errors)
    salary_ceiling: int = 500_000

    # Curriculum
    program_name: str = "วศ.บ. วิศวกรรมคอมพิวเตอร์ (ปรับปรุง พ.ศ. 2566) มหาวิทยาลัยกาฬสินธุ์"
    max_selected_courses: int = 15

    # Gap analysis (SRS section 10) — see app/gap.py
    gap_top_n: int = 0                     # 0 = every skill found in jobs (matches the Module 3 report: 29.4%)
    gap_min_jobs: int = 1
    gap_relevance_top: int = 100           # Relevance_j is measured against the Top-100 skills
    gap_matrix_skills: int = 30
    gap_matrix_demand_threshold: float = 0.05
    gap_cov_threshold: float = 0.5
    gap_missing_limit: int = 50
    gap_missing_min_jobs: int = 10        # 'ยังขาด (≥10 งาน)' on the Gap page
    gap_heatmap_skills: int = 10
    gap_heatmap_courses: int = 12

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sources(self) -> list[str]:
        return [s.strip() for s in self.crawler_sources.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
