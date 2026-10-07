"""Job search (FR-SS-01..03).

* With a query  → semantic search: the query is embedded with bge-m3 and compared (cosine) with
  jobs.embedding, which Module 3 built from "title + description + qualification" of each posting.
  The closest `search_max_results` jobs (after filters) come from the HNSW index.
* Without query → browse: every job that passes the filters, newest first.
In both modes postings of the same company with the same title (branch postings) are folded into one
card, and the result is paged.
"""
import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db, rows
from app.embedding import embed_query, to_pgvector
from app.privacy import clean_title
from app.schemas import JobCard, SearchIn, SearchOut

router = APIRouter(tags=["search"])

SITE = {"jobthai": "https://www.jobthai.com", "jobbkk": "https://www.jobbkk.com"}

# Title key used to fold branch postings: drop "(...)", "สาขา..." and spaces.
TITLE_KEY = r"""lower(regexp_replace(regexp_replace(title, '\([^)]*\)|\[[^]]*\]|สาขา.*$', '', 'g'), '\s+', '', 'g'))"""


def logo_url(raw: str | None, source: str | None) -> str | None:
    """companies.logo_url may be absolute, protocol-relative or site-relative."""
    if not raw or not raw.strip():
        return None
    u = raw.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        base = SITE.get((source or "").lower())
        return base + u if base else None
    return u if u.startswith(("http://", "https://")) else None


def top_skills_for(db: Session, job_ids: list[int], n: int = 5) -> dict[int, list[str]]:
    """Hard skills first, AI skills first, required first."""
    if not job_ids:
        return {}
    data = rows(db, """
        SELECT js.job_id, s.name
        FROM job_skills js JOIN skills s ON s.id = js.skill_id
        LEFT JOIN m4_ai_skills a ON a.skill_id = s.id
        WHERE js.job_id = ANY(:ids)
        ORDER BY js.job_id, (lower(s.skill_type::text) = 'hard') DESC, (a.skill_id IS NOT NULL) DESC,
                 js.is_required DESC NULLS LAST, s.name""", ids=job_ids)
    out: dict[int, list[str]] = {}
    for r in data:
        lst = out.setdefault(r["job_id"], [])
        if len(lst) < n:
            lst.append(r["name"])
    return out


def _filters(body: SearchIn) -> tuple[list[str], dict]:
    cond, p = [], {}
    f = body.filters
    if f.min_salary:
        cond.append("coalesce(j.salary_max, j.salary_min) >= :min_salary")
        p["min_salary"] = f.min_salary
    for key in ("level", "work_mode", "province", "source"):
        values = getattr(f, key)
        if values:
            cond.append(f"j.{key} = ANY(:{key})")
            p[key] = list(values)
    return cond, p


@router.post("/search", response_model=SearchOut)
def search(body: SearchIn, db: Session = Depends(get_db)):
    t0 = time.perf_counter()
    cond, p = _filters(body)
    p.update(off=(body.page - 1) * body.page_size, ps=body.page_size)
    group_key = f"coalesce(company, id::text), {TITLE_KEY}" if body.group_duplicates else "id"
    semantic = bool(body.query)
    cap = int(settings.search_max_results)

    if semantic:
        p.update(q=to_pgvector(embed_query(body.query)), cap=cap)
        cond.insert(0, "j.embedding IS NOT NULL")
        # pgvector >= 0.8: keep scanning the HNSW index until enough rows pass the filters.
        db.execute(text(f"SET LOCAL hnsw.ef_search = {max(int(settings.hnsw_ef_search), cap)}"))
        try:
            with db.begin_nested():
                db.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
        except Exception:  # noqa: BLE001 - older pgvector: plain HNSW is fine
            pass
        rank, order, limit = "j.embedding <=> CAST(:q AS vector)", "rank, id", "LIMIT :cap"
    else:
        # browse: newest first; rank is only used for ordering
        rank, order, limit = "-extract(epoch FROM coalesce(j.posted_at, j.scraped_at))", "rank NULLS LAST, id DESC", ""
    t1 = time.perf_counter()

    where = " AND ".join(cond) or "TRUE"
    data = rows(db, f"""
        WITH cand AS MATERIALIZED (
            SELECT j.id, j.title, j.company, j.company_logo, j.province, j.salary_min, j.salary_max, j.level,
                   j.work_mode, j.source, j.url, j.posted_at, {rank} AS rank
            FROM m4_jobs j
            WHERE {where}
            ORDER BY {rank}
            {limit}),
        g AS (
            SELECT cand.*,
                   row_number() OVER (PARTITION BY {group_key} ORDER BY {order}) AS rn,
                   count(*)     OVER (PARTITION BY {group_key})              AS dup
            FROM cand)
        SELECT g.*, count(*) OVER () AS total, (SELECT count(*) FROM cand) AS n_cand
        FROM g WHERE rn = 1
        ORDER BY {order}
        OFFSET :off LIMIT :ps""", **p)
    if data:
        total = int(data[0]["total"])
        capped = semantic and int(data[0]["n_cand"]) >= cap
    else:  # no rows on this page: still report the total
        total = int(rows(db, f"""
            WITH cand AS MATERIALIZED (
                SELECT j.id, j.title, j.company FROM m4_jobs j WHERE {where} ORDER BY {rank} {limit})
            SELECT count(DISTINCT ({group_key})) AS n FROM cand""", **p)[0]["n"])
        capped = False
    skills = top_skills_for(db, [r["id"] for r in data])
    t2 = time.perf_counter()

    results = [JobCard(job_id=r["id"], title=clean_title(r["title"]), company=r["company"], province=r["province"],
                       salary_min=r["salary_min"], salary_max=r["salary_max"], level=r["level"], work_mode=r["work_mode"],
                       source=r["source"], source_url=r["url"] or "", top_skills=skills.get(r["id"], []),
                       similarity=round(max(0.0, 1 - float(r["rank"])), 4) if semantic else None,
                       posted_at=r["posted_at"], company_logo=logo_url(r["company_logo"], r["source"]),
                       similar_postings=int(r["dup"]) - 1) for r in data]
    return SearchOut(mode="semantic" if semantic else "browse",
                     took_ms={"embed": round((t1 - t0) * 1000, 1), "db": round((t2 - t1) * 1000, 1)},
                     results=results, page=body.page, page_size=body.page_size, total=total,
                     max_results=cap if semantic else total, capped=capped)


@router.get("/search/suggest")
def suggest(q: str = "", limit: int = Query(6, ge=1, le=15), db: Session = Depends(get_db)):
    """Type-ahead for the search box: skills and job titles that contain what was typed, most common first.
    Empty q → the most demanded skills and the most common titles (shown when the box gets focus)."""
    q = q.strip()
    like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    skill_rows = rows(db, f"""
        SELECT s.name, count(DISTINCT js.job_id) AS n
        FROM skills s JOIN job_skills js ON js.skill_id = s.id
        {"WHERE s.name ILIKE :like" if q else ""}
        GROUP BY s.id, s.name
        ORDER BY {"(lower(s.name) LIKE lower(:prefix)) DESC," if q else ""} n DESC, s.name
        LIMIT :lim""", like=like, prefix=q.replace("%", "") + "%", lim=limit)
    title_rows = rows(db, f"""
        SELECT min(t.base) AS title, count(*) AS n
        FROM (SELECT trim(regexp_replace(j.title, '\\s*[(\\[][^)\\]]*[)\\]]|\\s*สาขา.*$', '', 'g')) AS base
              FROM m4_jobs j {"WHERE j.title ILIKE :like" if q else ""}) t
        WHERE t.base <> ''
        GROUP BY lower(regexp_replace(t.base, '\\s+', ' ', 'g'))
        ORDER BY n DESC, min(t.base)
        LIMIT :lim""", like=like, lim=limit * 2)
    titles, seen = [], set()
    for r in title_rows:  # remove contact info, then de-duplicate what is left
        t = clean_title(r["title"])
        if t and t.lower() not in seen:
            seen.add(t.lower())
            titles.append({"text": t, "jobs": int(r["n"])})
    return {"skills": [{"text": r["name"], "jobs": int(r["n"])} for r in skill_rows], "titles": titles[:limit]}


@router.get("/search/related-skills")
def related_skills(q: str, k: int = 10, db: Session = Depends(get_db)):
    """Skills closest in meaning to the query (skills.embedding)."""
    vec = to_pgvector(embed_query(q))
    data = rows(db, """
        SELECT s.name, 1 - (s.embedding <=> CAST(:q AS vector)) AS similarity
        FROM skills s WHERE s.embedding IS NOT NULL
        ORDER BY s.embedding <=> CAST(:q AS vector) LIMIT :k""", q=vec, k=max(1, min(k, 30)))
    return [{"skill": r["name"], "similarity": round(float(r["similarity"]), 3)} for r in data]