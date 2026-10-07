# -*- coding: utf-8 -*-
r"""
Export ผลจากฐานข้อมูลเป็น structured JSON (รูปแบบเดียวกับ run_json) — ใช้ส่งอาจารย์/แนบรายงาน

  python -m extractor.export_db --output output\structured_all.json
  python -m extractor.export_db --limit 20 --output output\sample20.json
  python -m extractor.export_db --site jobbkk --output output\jobbkk.json
"""
import argparse
import json
import os

import psycopg2
from psycopg2.extras import RealDictCursor

from . import config
from .run_json import dump_compact

SQL_JOBS = """
SELECT j.id, j.source_site::text AS site, j.source_url, j.title, c.name AS company,
       j.province, j.district, j.salary_type::text AS salary_type, j.salary_min, j.salary_max,
       j.salary_period, j.posted_date, j.experience_years, j.education_level,
       j.seniority, j.work_mode, j.llm_model
FROM jobs j LEFT JOIN companies c ON c.id = j.company_id
WHERE j.llm_extracted_at IS NOT NULL
  AND (%(site)s::text IS NULL OR j.source_site::text = %(site)s)
ORDER BY j.id LIMIT %(limit)s
"""
SQL_ITEMS = """
SELECT job_id, source::text AS source, category::text AS category, confidence, content
FROM job_requirement_items WHERE job_id = ANY(%s) ORDER BY job_id, source, seq
"""
SQL_SKILLS = """
SELECT js.job_id, s.name, s.name_norm, s.skill_type, s.category AS grp, js.is_required,
       ri.content AS from_text, s.esco_label, s.esco_uri, s.onet_label, s.onet_group, s.onet_hot
FROM job_skills js JOIN skills s ON s.id = js.skill_id
LEFT JOIN job_requirement_items ri ON ri.id = js.item_id
WHERE js.job_id = ANY(%s) ORDER BY js.job_id, s.name
"""


def clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v not in (None, "")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=os.path.join("output", "structured_all.json"))
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--site", choices=["jobthai", "jobbkk"])
    a = ap.parse_args()

    conn = psycopg2.connect(config.DATABASE_URL)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(SQL_JOBS, {"site": a.site, "limit": a.limit})
        jobs = cur.fetchall()
        ids = [j["id"] for j in jobs]
        cur.execute(SQL_ITEMS, (ids,))
        items = cur.fetchall()
        cur.execute(SQL_SKILLS, (ids,))
        skills = cur.fetchall()
    conn.close()

    by_items, by_skills = {}, {}
    for it in items:
        by_items.setdefault(it["job_id"], []).append(clean({
            "source": it["source"], "category": it["category"],
            "confidence": round(it["confidence"], 2) if it["confidence"] is not None else None,
            "text": it["content"]}))
    for s in skills:
        by_skills.setdefault(s["job_id"], []).append(s)

    out = []
    for j in jobs:
        hard, soft = [], []
        for s in by_skills.get(j["id"], []):
            d = clean({"name": s["name"], "name_norm": s["name_norm"], "group": s["grp"],
                       "required": s["is_required"], "from_text": s["from_text"],
                       "esco_label": s["esco_label"], "esco_uri": s["esco_uri"],
                       "onet_label": s["onet_label"], "onet_group": s["onet_group"],
                       "onet_hot": s["onet_hot"] or None})
            (soft if s["skill_type"] == "soft" else hard).append(d)
        out.append({
            "job_id": j["id"], "source_site": j["site"], "source_url": j["source_url"],
            "job_info": clean({
                "title": j["title"], "company": j["company"], "province": j["province"],
                "district": j["district"], "salary_type": j["salary_type"],
                "salary_min": float(j["salary_min"]) if j["salary_min"] is not None else None,
                "salary_max": float(j["salary_max"]) if j["salary_max"] is not None else None,
                "salary_period": j["salary_period"],
                "posted_date": str(j["posted_date"]) if j["posted_date"] else None,
                "experience_years": j["experience_years"], "education_level": j["education_level"],
                "seniority": j["seniority"], "work_mode": j["work_mode"], "llm_model": j["llm_model"]}),
            "classified_bullets": by_items.get(j["id"], []),
            "hard_skills": hard, "soft_skills": soft})

    os.makedirs(os.path.dirname(a.output) or ".", exist_ok=True)
    with open(a.output, "w", encoding="utf-8") as f:
        f.write(dump_compact(out))
    n_sk = sum(len(o["hard_skills"]) + len(o["soft_skills"]) for o in out)
    print(f"💾 {a.output}  ({len(out)} งาน · {n_sk} ทักษะ)")


if __name__ == "__main__":
    main()
