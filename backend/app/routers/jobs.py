from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db, one, rows
from app.privacy import clean_title, mask_text
from app.routers.search import logo_url
from app.schemas import JobDetail, SkillOut

router = APIRouter(prefix="/jobs", tags=["jobs"])

STD_SHORT = {"ONET": "O*NET", "SKILLSFUTURE": "SkillsFuture", "ESCO": "ESCO", "DSD": "DSD", "TPQI": "TPQI"}


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: int, db: Session = Depends(get_db)):
    j = one(db, """
        SELECT v.id, v.title, v.company, v.company_logo, v.province, v.salary_min, v.salary_max, v.level, v.work_mode,
               v.source, v.url, v.is_ai_related, v.posted_at, v.updated_at,
               r.description::text AS description, r.qualification::text AS qualification,
               r.welfare::text AS welfare, r.experience_years,
               r.education_level::text AS education_level, r.employment_type::text AS employment_type,
               r.seniority::text AS seniority_raw
        FROM m4_jobs v JOIN jobs r ON r.id = v.id
        WHERE v.id = :id""", id=job_id)
    if not j:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "JOB_NOT_FOUND", "message": "No such job"})
    skills = rows(db, """
        SELECT s.id, s.name, lower(s.skill_type::text) AS type, (a.skill_id IS NOT NULL) AS is_ai,
               coalesce(js.is_required, true) AS is_required,
               coalesce(array_agg(m.standard || '|' || m.std_label ORDER BY m.standard)
                        FILTER (WHERE m.standard IS NOT NULL), '{}') AS stds
        FROM job_skills js
        JOIN skills s ON s.id = js.skill_id
        LEFT JOIN m4_ai_skills a ON a.skill_id = s.id
        LEFT JOIN skill_standard_map m ON m.skill_id = s.id
        WHERE js.job_id = :id
        GROUP BY s.id, s.name, s.skill_type, a.skill_id, js.is_required
        ORDER BY js.is_required DESC NULLS LAST, s.name""", id=job_id)

    def std_label(x: str) -> str:
        code, _, label = x.partition("|")
        return f"{STD_SHORT.get(code, code)}: {label}"

    # Contact details (jobs.contact) are never returned, and phone / e-mail / LINE inside the
    # title or text are removed (FR-SS-05 / PDPA, app/privacy.py).
    return JobDetail(
        id=j["id"], title=clean_title(j["title"]), company=j["company"],
        company_logo=logo_url(j["company_logo"], j["source"]), province=j["province"],
        salary_min=j["salary_min"], salary_max=j["salary_max"], level=j["level"], work_mode=j["work_mode"],
        source=j["source"], source_url=j["url"] or "", description=mask_text(j["description"]),
        qualification=mask_text(j["qualification"]), welfare=mask_text(j["welfare"]), experience_years=float(j["experience_years"]) if j["experience_years"] is not None else None,
        education_level=j["education_level"], employment_type=j["employment_type"], seniority_raw=j["seniority_raw"],
        is_ai_related=j["is_ai_related"], posted_at=j["posted_at"], last_updated_at=j["updated_at"],
        skills=[SkillOut(id=s["id"], name=s["name"], type=s["type"] or "hard", is_ai_skill=s["is_ai"],
                         is_required=s["is_required"], standards=[std_label(x) for x in s["stds"]]) for s in skills])