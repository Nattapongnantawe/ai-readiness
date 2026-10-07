"""Curriculum Gap Analysis (SRS section 10) on the jobmarket database.

Coverage comes from course_skill_map, the course↔skill links Module 3 built and the researcher
reviewed (method exact / semantic / manual). A skill is covered by a course when that link exists.

d(s)   = share of jobs that require skill s                (job_skills, distinct jobs)
c_j(s) = 1 if (course j, skill s) is in course_skill_map, else 0
c(s)   = max over the selected courses of c_j(s)
MatchScore     = Σ d·c / Σ d        over the analysed skills (all skills by default → 29.4 % in the report)
Contribution_j = Σ d·c_j / Σ d
Relevance_j    = |S_j ∩ Top-K| / |S_j|                      (K = GAP_RELEVANCE_TOP)
GapPriority(s) = d · (1 − c)                                 for uncovered skills
Suggested course for a missing skill = the selected course with the closest topic (course_topics).
"""
from __future__ import annotations

import time

import numpy as np
from sqlalchemy.orm import Session

from app.config import settings
from app.db import rows

_CACHE: dict[tuple, tuple[float, dict]] = {}
_TTL = 300  # seconds; data changes only when the pipeline runs


def parse_vec(s: str | None) -> np.ndarray | None:
    if not s:
        return None
    return np.asarray(s.strip("[]").split(","), dtype=np.float32)


def _params() -> dict:
    return {"top_n": settings.gap_top_n, "tau": 1.0, "cov_threshold": settings.gap_cov_threshold,
            "matrix_demand_threshold": settings.gap_matrix_demand_threshold,
            "relevance_top": settings.gap_relevance_top}


def compute(db: Session, courses: list[str] | None = None, exclude_manual: bool = False, use_cache: bool = True) -> dict:
    key = (tuple(sorted(courses or [])), exclude_manual)
    hit = _CACHE.get(key)
    if use_cache and hit and time.time() - hit[0] < _TTL:
        return hit[1]
    payload = _compute(db, courses, exclude_manual)
    _CACHE[key] = (time.time(), payload)
    return payload


def clear_cache() -> None:
    _CACHE.clear()


def _compute(db: Session, selected: list[str] | None, exclude_manual: bool) -> dict:
    total = rows(db, "SELECT count(*) AS n FROM jobs")[0]["n"]
    all_courses = rows(db, "SELECT course_code AS code, name_th, name_en, category FROM curriculum_courses ORDER BY course_code")
    by_code = {c["code"]: c for c in all_courses}
    chosen = [c for c in (selected or []) if c in by_code] or list(by_code)
    empty = {"overall_match_score": 0.0, "overall_match_score_no_manual": 0.0, "skills_analyzed": 0, "covered": 0,
             "missing": 0, "missing_min_jobs": 0, "missing_min_jobs_threshold": settings.gap_missing_min_jobs, "courses": [], "missing_skills": [], "matrix": [],
             "heatmap": {"courses": [], "skills": [], "values": []}, "params": _params(), "total_jobs": total,
             "selected_courses": chosen if selected else [], "total_courses": len(all_courses),
             "methods": {}}
    if total == 0 or not chosen:
        return empty

    demand = rows(db, """
        SELECT s.id, s.name, count(DISTINCT js.job_id) AS n, (a.skill_id IS NOT NULL) AS is_ai
        FROM job_skills js
        JOIN skills s ON s.id = js.skill_id
        LEFT JOIN m4_ai_skills a ON a.skill_id = s.id
        GROUP BY s.id, s.name, a.skill_id
        HAVING count(DISTINCT js.job_id) >= :min_jobs
        ORDER BY n DESC, s.name""", min_jobs=settings.gap_min_jobs)
    if settings.gap_top_n > 0:
        demand = demand[: settings.gap_top_n]
    if not demand:
        return empty

    idx = {d["id"]: i for i, d in enumerate(demand)}
    col = {code: j for j, code in enumerate(chosen)}
    d = np.array([r["n"] / total for r in demand], dtype=np.float64)

    links = rows(db, """
        SELECT m.course_code, m.skill_id, m.method, coalesce(m.similarity, 1.0) AS sim
        FROM course_skill_map m WHERE m.course_code = ANY(:codes)""", codes=chosen)
    cov_j = np.zeros((len(demand), len(chosen)))
    cov_j_auto = np.zeros_like(cov_j)          # without researcher-reviewed (manual) links
    strength = np.zeros_like(cov_j)            # link similarity, for the matrix / heatmap shading
    methods: dict[str, int] = {}
    own: dict[str, set[int]] = {c: set() for c in chosen}
    for ln in links:
        i, j = idx.get(ln["skill_id"]), col[ln["course_code"]]
        own[ln["course_code"]].add(ln["skill_id"])
        methods[ln["method"]] = methods.get(ln["method"], 0) + 1
        if i is None:
            continue
        cov_j[i, j] = 1.0
        strength[i, j] = max(strength[i, j], float(ln["sim"]) if ln["method"] == "semantic" else 1.0)
        if ln["method"] != "manual":
            cov_j_auto[i, j] = 1.0
    if exclude_manual:
        cov_j = cov_j_auto

    cov = cov_j.max(axis=1)
    d_sum = d.sum()
    overall = float((d * cov).sum() / d_sum)
    overall_auto = float((d * cov_j_auto.max(axis=1)).sum() / d_sum)

    top_rel = {demand[i]["id"] for i in range(min(settings.gap_relevance_top, len(demand)))}
    course_rows = []
    for code in chosen:
        j = col[code]
        mine = own[code]
        covered_idx = [i for i in np.flatnonzero(cov_j[:, j])]
        course_rows.append({
            "code": code,
            "name": by_code[code]["name_th"],
            "name_en": by_code[code]["name_en"],
            "category": by_code[code]["category"],
            "contribution": round(float((d * cov_j[:, j]).sum() / d_sum), 4),
            "relevance": round(len(mine & top_rel) / len(mine), 4) if mine else 0.0,
            "skill_count": len(mine),
            "covered_skills": [demand[i]["name"] for i in covered_idx[:12]],
        })
    course_rows.sort(key=lambda c: c["contribution"], reverse=True)

    # Missing skills, ranked by priority = d (they are uncovered, so 1 - c = 1)
    missing_i = [i for i in range(len(demand)) if cov[i] < settings.gap_cov_threshold][: settings.gap_missing_limit]
    suggestions = _suggest(db, [demand[i]["id"] for i in missing_i], chosen)
    missing = []
    for i in missing_i:
        sid = demand[i]["id"]
        code, topic, tsim = suggestions.get(sid, (None, "", None))
        missing.append({
            "skill": demand[i]["name"], "demand_pct": round(float(d[i]), 4), "jobs": demand[i]["n"],
            "coverage": round(float(cov[i]), 4), "priority": round(float(d[i] * (1 - cov[i])), 4),
            "suggested_course": by_code[code]["name_th"] if code else "",
            "suggested_course_code": code or "",
            "suggested_topic": topic,
            "suggested_similarity": tsim,
            "is_ai_skill": demand[i]["is_ai"],
        })

    k = min(settings.gap_matrix_skills, len(demand))
    matrix = []
    for i in range(k):
        teaching = [chosen[j] for j in np.flatnonzero(cov_j[i])]
        matrix.append({"skill": demand[i]["name"], "demand_pct": round(float(d[i]), 4), "jobs": demand[i]["n"],
                       "coverage": round(float(strength[i].max()), 4), "is_ai_skill": demand[i]["is_ai"],
                       "courses": len(teaching),
                       "course_names": [f"{c} {by_code[c]['name_th']}" for c in teaching[:5]]})

    hk = min(settings.gap_heatmap_skills, len(demand))
    heat_courses = chosen if selected else [c["code"] for c in course_rows[: settings.gap_heatmap_courses]]
    heatmap = {
        "courses": [by_code[c]["name_th"] for c in heat_courses],
        "course_codes": heat_courses,
        "skills": [demand[i]["name"] for i in range(hk)],
        "values": [[round(float(strength[i, col[c]]), 2) for i in range(hk)] for c in heat_courses],
    }

    covered = int((cov >= settings.gap_cov_threshold).sum())
    return {
        "overall_match_score": round(overall, 4),
        "overall_match_score_no_manual": round(overall_auto, 4),
        "skills_analyzed": len(demand),
        "covered": covered,
        "missing": len(demand) - covered,
        "missing_min_jobs": int(sum(1 for i in range(len(demand)) if cov[i] < settings.gap_cov_threshold
                                    and demand[i]["n"] >= settings.gap_missing_min_jobs)),
        "missing_min_jobs_threshold": settings.gap_missing_min_jobs,
        "courses": course_rows,
        "missing_skills": missing,
        "matrix": matrix,
        "heatmap": heatmap,
        "params": _params(),
        "total_jobs": total,
        "selected_courses": chosen if selected else [],
        "total_courses": len(all_courses),
        "methods": methods,
    }


def _suggest(db: Session, skill_ids: list[int], codes: list[str]) -> dict[int, tuple[str, str, float]]:
    """Closest selected course for each missing skill, judged by the course's topics (course_topics,
    one embedding per topic from มคอ.2) instead of the whole-course embedding, which was too coarse
    (Python → Discrete Math). Returns skill_id → (course_code, topic, similarity); skills whose best
    topic is below GAP_SUGGEST_MIN get no suggestion (= needs new content, not an existing course)."""
    if not skill_ids or not codes:
        return {}
    sk = rows(db, "SELECT id, embedding::text AS e FROM skills WHERE id = ANY(:ids) AND embedding IS NOT NULL", ids=skill_ids)
    tp = rows(db, "SELECT course_code AS code, topic, embedding::text AS e FROM course_topics "
                  "WHERE course_code = ANY(:codes) AND embedding IS NOT NULL", codes=codes)
    if not tp:  # no topic embeddings yet: fall back to whole-course embeddings
        tp = rows(db, "SELECT course_code AS code, name_th AS topic, embedding::text AS e FROM curriculum_courses "
                      "WHERE course_code = ANY(:codes) AND embedding IS NOT NULL", codes=codes)
    if not sk or not tp:
        return {}
    S = np.stack([parse_vec(r["e"]) for r in sk])
    T = np.stack([parse_vec(r["e"]) for r in tp])
    S /= np.linalg.norm(S, axis=1, keepdims=True) + 1e-9
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
    sim = S @ T.T
    best = sim.argmax(axis=1)
    out = {}
    for r, b, row in zip(sk, best, sim):
        v = float(row[b])
        if v >= settings.gap_suggest_min:
            out[r["id"]] = (tp[b]["code"], tp[b]["topic"], round(v, 3))
    return out