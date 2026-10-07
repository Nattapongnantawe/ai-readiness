"""Dashboard data (FR-DB-01..05) from the jobmarket database via the m4_jobs / m4_ai_skills views."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db, one, rows
from app.filters import JobFilters, job_filters
from app.gap import compute as gap_compute

router = APIRouter(prefix="/analytics", tags=["analytics"])

SALARY_OK = "j.salary_mid BETWEEN :s_lo AND :s_hi"
SAL = {"s_lo": settings.salary_floor, "s_hi": settings.salary_ceiling}

STANDARD_LABELS = {
    "ESCO": "ESCO (สหภาพยุโรป)",
    "ONET": "O*NET (สหรัฐฯ)",
    "SKILLSFUTURE": "SkillsFuture (สิงคโปร์)",
    "DSD": "กรมพัฒนาฝีมือแรงงาน",
    "TPQI": "TPQI คุณวุฒิวิชาชีพ",
}


def _counts(db: Session, f: JobFilters, previous: bool) -> dict:
    where, p = f.where(previous=previous)
    r = one(db, f"""
        SELECT count(*) AS total,
               count(*) FILTER (WHERE j.is_ai_related) AS ai,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY j.salary_mid) FILTER (WHERE {SALARY_OK}) AS median,
               count(*) FILTER (WHERE {SALARY_OK}) AS disclosed
        FROM m4_jobs j WHERE {where}""", **p, **SAL)
    return {"total": r["total"], "ai": r["ai"], "median": float(r["median"]) if r["median"] is not None else None,
            "disclosed": r["disclosed"]}


@router.get("/summary")
def summary(f: JobFilters = Depends(job_filters), db: Session = Depends(get_db)):
    cur = _counts(db, f, False)
    prev = _counts(db, f, True) if f.windowed else None
    where, p = f.where(use_window=False)
    week = one(db, f"""
        SELECT count(*) FILTER (WHERE j.scraped_at >= now() - interval '7 days') AS new_7d,
               count(*) FILTER (WHERE j.scraped_at >= now() - interval '14 days'
                                  AND j.scraped_at <  now() - interval '7 days') AS new_prev
        FROM m4_jobs j WHERE {where}""", **p)
    inv = one(db, """
        SELECT (SELECT count(*) FROM companies)                         AS companies,
               (SELECT count(DISTINCT skill_id) FROM job_skills)        AS skills,
               (SELECT count(*) FROM job_skills)                        AS job_skill_pairs,
               (SELECT count(*) FROM curriculum_courses)                AS courses,
               (SELECT max(scraped_at) FROM jobs)                       AS last_scraped_at""")
    std = one(db, """SELECT weighted_pct, skills FROM v_std_coverage_by_standard
                     WHERE standard LIKE 'ANY%' LIMIT 1""")
    gap = gap_compute(db)
    share = lambda c: (c["ai"] / c["total"]) if c and c["total"] else 0.0  # noqa: E731
    return {
        "total_jobs": cur["total"], "total_jobs_prev": prev["total"] if prev else None,
        "new_7d": week["new_7d"], "new_7d_prev": week["new_prev"],
        "ai_jobs": cur["ai"], "ai_share": share(cur), "ai_share_prev": share(prev) if prev else None,
        "median_salary": cur["median"], "median_salary_prev": prev["median"] if prev else None,
        "salary_disclosed_share": (cur["disclosed"] / cur["total"]) if cur["total"] else 0.0,
        "curriculum_match": gap["overall_match_score"] if gap["skills_analyzed"] else None,
        "window_days": f.days,
        "companies": inv["companies"], "unique_skills": inv["skills"], "job_skill_pairs": inv["job_skill_pairs"],
        "courses": inv["courses"], "last_scraped_at": inv["last_scraped_at"],
        "std_coverage": float(std["weighted_pct"]) / 100 if std else None,
        "std_skills": std["skills"] if std else None,
    }


def _skill_counts(db: Session, f: JobFilters, previous: bool, skill_type: str | None, limit: int | None,
                  ids: list[int] | None = None) -> tuple[list[dict], int]:
    where, p = f.where(previous=previous)
    total = one(db, f"SELECT count(*) AS n FROM m4_jobs j WHERE {where}", **p)["n"]
    cond = "TRUE"
    if skill_type:
        cond = "lower(s.skill_type::text) = :stype"
        p["stype"] = skill_type
    if ids is not None:
        cond += " AND s.id = ANY(:ids)"
        p["ids"] = ids
    lim = f"LIMIT {int(limit)}" if limit else ""
    data = rows(db, f"""
        SELECT s.id, s.name, lower(s.skill_type::text) AS type, count(DISTINCT j.id) AS n,
               (a.skill_id IS NOT NULL) AS is_ai
        FROM job_skills js
        JOIN m4_jobs j ON j.id = js.job_id
        JOIN skills s  ON s.id = js.skill_id
        LEFT JOIN m4_ai_skills a ON a.skill_id = s.id
        WHERE {where} AND {cond}
        GROUP BY s.id, s.name, s.skill_type, a.skill_id
        ORDER BY n DESC, s.name {lim}""", **p)
    return data, total


@router.get("/top-skills")
def top_skills(type: str = Query("hard", pattern="^(hard|soft|all)$"), limit: int = Query(10, ge=1, le=50),
               f: JobFilters = Depends(job_filters), db: Session = Depends(get_db)):
    stype = None if type == "all" else type
    cur, total = _skill_counts(db, f, False, stype, limit)
    prev_map, prev_total = {}, 0
    if f.windowed and cur:
        prev, prev_total = _skill_counts(db, f, True, stype, None, ids=[r["id"] for r in cur])
        prev_map = {r["id"]: r["n"] / prev_total for r in prev} if prev_total else {}
    return [{"skill": r["name"], "type": r["type"], "jobs": r["n"], "pct": round(r["n"] / total, 4) if total else 0.0,
             "delta_pct": round(r["n"] / total - prev_map.get(r["id"], 0.0), 4) if prev_total else None,
             "is_ai_skill": r["is_ai"]} for r in cur]


@router.get("/salary-distribution")
def salary_distribution(f: JobFilters = Depends(job_filters), db: Session = Depends(get_db)):
    where, p = f.where()
    data = rows(db, f"""
        SELECT j.level, count(*) AS n,
               percentile_cont(0.0)  WITHIN GROUP (ORDER BY j.salary_mid) AS min,
               percentile_cont(0.25) WITHIN GROUP (ORDER BY j.salary_mid) AS p25,
               percentile_cont(0.5)  WITHIN GROUP (ORDER BY j.salary_mid) AS median,
               percentile_cont(0.75) WITHIN GROUP (ORDER BY j.salary_mid) AS p75,
               percentile_cont(1.0)  WITHIN GROUP (ORDER BY j.salary_mid) AS max
        FROM m4_jobs j
        WHERE {where} AND {SALARY_OK} AND j.level IS NOT NULL
        GROUP BY j.level""", **p, **SAL)
    order = {"Entry": 0, "Mid": 1, "Senior": 2}
    for r in data:
        for k in ("min", "p25", "median", "p75", "max"):
            r[k] = float(r[k])
    return sorted(data, key=lambda r: order.get(r["level"], 9))


@router.get("/salary-histogram")
def salary_histogram(f: JobFilters = Depends(job_filters), db: Session = Depends(get_db)):
    """Counts per monthly-salary band (baht), for the Salary Distribution chart."""
    where, p = f.where()
    edges = [0, 15_000, 20_000, 25_000, 30_000, 40_000, 50_000, 70_000, 100_000]
    case = " ".join(f"WHEN j.salary_mid < {hi} THEN {i}" for i, hi in enumerate(edges[1:]))
    data = rows(db, f"""
        SELECT CASE {case} ELSE {len(edges) - 1} END AS b, count(*) AS n
        FROM m4_jobs j WHERE {where} AND {SALARY_OK} GROUP BY 1 ORDER BY 1""", **p, **SAL)
    counts = {r["b"]: r["n"] for r in data}
    labels = ["<15k", "15–20k", "20–25k", "25–30k", "30–40k", "40–50k", "50–70k", "70–100k", "100k+"]
    return [{"band": labels[i], "min": edges[i], "max": edges[i + 1] if i + 1 < len(edges) else None, "n": counts.get(i, 0)}
            for i in range(len(labels))]


@router.get("/ai-trend")
def ai_trend(weeks: int = Query(8, ge=2, le=52), bucket: str = Query("auto", pattern="^(auto|week|day)$"),
             min_jobs_per_day: int = Query(20, ge=1), f: JobFilters = Depends(job_filters), db: Session = Depends(get_db)):
    """AI share over time. bucket=auto: weekly, but daily when fewer than 4 weeks have data (a fresh
    snapshot); days with fewer than min_jobs_per_day postings are dropped because their share is noise."""
    where, p = f.where(use_window=False)

    def series_by(unit: str) -> list[dict]:
        return rows(db, f"""
            SELECT date_trunc('{unit}', j.posted_at) AS week_start, count(*) AS total,
                   count(*) FILTER (WHERE j.is_ai_related) AS ai
            FROM m4_jobs j
            WHERE {where} AND j.posted_at >= date_trunc('week', now()) - make_interval(weeks => :weeks - 1)
            GROUP BY 1 ORDER BY 1""", **p, weeks=weeks)

    used = "week" if bucket != "day" else "day"
    series = series_by("week") if used == "week" else []
    if bucket == "day" or (bucket == "auto" and len(series) < 4):
        used = "day"
        series = [s for s in series_by("day") if s["total"] >= min_jobs_per_day]
    for s in series:
        s["share"] = (s["ai"] / s["total"]) if s["total"] else 0.0

    def groups(previous: bool) -> dict[str, float]:
        w, q = f.where(previous=previous)
        base = one(db, f"SELECT count(*) AS n FROM m4_jobs j WHERE {w}", **q)["n"]
        if not base:
            return {}
        data = rows(db, f"""
            SELECT a.ai_group AS g, count(DISTINCT j.id) AS n
            FROM m4_jobs j JOIN job_skills js ON js.job_id = j.id JOIN m4_ai_skills a ON a.skill_id = js.skill_id
            WHERE {w} GROUP BY a.ai_group""", **q)
        return {r["g"]: r["n"] / base for r in data}

    cur = groups(False)
    prev = groups(True) if f.windowed else {}
    group_rows = sorted(({"group": g, "pct": round(v, 4), "delta_pct": round(v - prev.get(g, 0.0), 4) if prev else None}
                         for g, v in cur.items()), key=lambda r: r["pct"], reverse=True)
    top_ai = rows(db, f"""
        SELECT a.name AS skill, a.ai_group AS "group", count(DISTINCT j.id) AS jobs
        FROM m4_jobs j JOIN job_skills js ON js.job_id = j.id JOIN m4_ai_skills a ON a.skill_id = js.skill_id
        WHERE {f.where()[0]} GROUP BY a.name, a.ai_group ORDER BY jobs DESC LIMIT 8""", **f.where()[1])
    return {"weeks": series, "bucket": used, "min_jobs_per_day": min_jobs_per_day,
            "groups": group_rows, "top_ai_skills": top_ai}


@router.get("/standards")
def standards(db: Session = Depends(get_db)):
    """Share of skill demand each skill standard covers (Module 2-3: v_std_coverage_by_standard)."""
    data = rows(db, "SELECT standard, skills, unique_pct, weighted_pct FROM v_std_coverage_by_standard")
    out = [{"standard": r["standard"], "label": STANDARD_LABELS.get(r["standard"], "รวมทุกมาตรฐาน" if r["standard"].startswith("ANY") else r["standard"]),
            "is_total": r["standard"].startswith("ANY"), "skills": r["skills"],
            "unique_pct": float(r["unique_pct"]) / 100, "weighted_pct": float(r["weighted_pct"]) / 100} for r in data]
    return sorted(out, key=lambda r: (not r["is_total"], -r["weighted_pct"]))


@router.get("/filters")
def filter_options(db: Session = Depends(get_db)):
    def facet(col: str, limit: int | None = None) -> list[dict]:
        lim = f"LIMIT {int(limit)}" if limit else ""
        return rows(db, f"""SELECT {col} AS value, count(*) AS count FROM m4_jobs
                            WHERE {col} IS NOT NULL AND {col} <> '' GROUP BY {col} ORDER BY count DESC {lim}""")

    return {"sources": facet("source"), "provinces": facet("province", 77),
            "levels": facet("level"), "work_modes": facet("work_mode")}


@router.get("/pipeline")
def pipeline_status(db: Session = Depends(get_db)):
    """How far each Module 1-3 step has got, straight from the jobmarket tables."""
    r = one(db, """
        SELECT (SELECT count(*) FROM jobs)                                         AS jobs,
               (SELECT count(*) FROM jobs WHERE llm_extracted_at IS NOT NULL)      AS extracted,
               (SELECT count(*) FROM jobs WHERE embedding IS NOT NULL)             AS jobs_embedded,
               (SELECT count(*) FROM skills)                                       AS skills,
               (SELECT count(*) FROM skills WHERE embedding IS NOT NULL)           AS skills_embedded,
               (SELECT count(DISTINCT skill_id) FROM skill_standard_map)           AS skills_std_mapped,
               (SELECT count(*) FROM curriculum_courses)                           AS courses,
               (SELECT count(*) FROM course_skill_map)                             AS course_links,
               (SELECT min(scraped_at) FROM jobs)                                  AS first_scraped_at,
               (SELECT max(scraped_at) FROM jobs)                                  AS last_scraped_at,
               (SELECT max(llm_extracted_at) FROM jobs)                            AS last_extracted_at""")
    by_source = rows(db, "SELECT source, count(*) AS jobs FROM m4_jobs GROUP BY source ORDER BY jobs DESC")
    return {**r, "by_source": by_source}