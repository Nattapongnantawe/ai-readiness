"""Curriculum courses (FR-GA-01, 02, 06) on the jobmarket tables curriculum_courses / course_skill_map.

The 79 courses and their skill links come from Module 3 (extractor/curriculum.py). Admin edits here keep
those links: text changes only redo the 'exact' links; PUT /skills sets the full list (new ones = 'manual').
"""
import re

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import gap
from app.auth import require_admin
from app.config import settings
from app.db import get_db, one, rows
from app.embedding import embed_texts, to_pgvector
from app.schemas import CourseIn, CourseOut, CourseSkill, CourseSkillsIn, CourseUpdate
from app.skill_extract import extract_skill_ids

router = APIRouter(prefix="/curriculum", tags=["curriculum"])

COURSE_SQL = """
SELECT c.course_code, c.name_th, c.name_en, c.description_th, c.description_en, c.credits,
       c.hours_theory, c.hours_practice, c.hours_self, c.category, c.course_group,
       coalesce(c.prerequisite, '{}') AS prerequisite
FROM curriculum_courses c"""

LINKS_SQL = """
SELECT m.course_code, s.name, m.method, m.similarity,
       (SELECT count(DISTINCT js.job_id) FROM job_skills js WHERE js.skill_id = s.id) AS jobs
FROM course_skill_map m JOIN skills s ON s.id = m.skill_id
WHERE m.course_code = ANY(:codes)
ORDER BY jobs DESC, s.name"""


def _credits_str(c: dict) -> str | None:
    if c["credits"] is None:
        return None
    if c["hours_theory"] is None:
        return str(c["credits"])
    return f"{c['credits']}({c['hours_theory']}-{c['hours_practice']}-{c['hours_self']})"


def _parse_credits(s: str | None) -> dict:
    if not s:
        return {"credits": None, "ht": None, "hp": None, "hs": None}
    m = re.match(r"\s*(\d+)\s*(?:\(\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*\))?", s)
    if not m:
        raise HTTPException(422, detail={"code": "INVALID_INPUT", "message": "หน่วยกิตต้องเป็นรูปแบบ 3 หรือ 3(2-2-5)"})
    g = [int(x) if x is not None else None for x in m.groups()]
    return {"credits": g[0], "ht": g[1], "hp": g[2], "hs": g[3]}


def _load(db: Session, codes: list[str] | None = None) -> list[CourseOut]:
    where = " WHERE c.course_code = ANY(:codes)" if codes else ""
    courses = rows(db, COURSE_SQL + where + " ORDER BY c.course_code", **({"codes": codes} if codes else {}))
    links = rows(db, LINKS_SQL, codes=[c["course_code"] for c in courses]) if courses else []
    by_course: dict[str, list[dict]] = {}
    for ln in links:
        by_course.setdefault(ln["course_code"], []).append(ln)
    out = []
    for c in courses:
        lk = by_course.get(c["course_code"], [])
        out.append(CourseOut(
            code=c["course_code"], name_th=c["name_th"], name_en=c["name_en"], description=c["description_th"] or "",
            description_en=c["description_en"], year=None, credits=_credits_str(c), category=c["category"],
            course_group=c["course_group"], prerequisite=list(c["prerequisite"] or []),
            skills=[x["name"] for x in lk],
            skill_links=[CourseSkill(name=x["name"], method=x["method"] or "exact",
                                     similarity=float(x["similarity"]) if x["similarity"] is not None else None,
                                     jobs=x["jobs"]) for x in lk]))
    return out


def _get(db: Session, code: str) -> CourseOut:
    found = _load(db, [code])
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "COURSE_NOT_FOUND", "message": f"No course {code}"})
    return found[0]


def _refresh(db: Session, code: str) -> None:
    """Re-embed the course (same text as Module 3) and redo its exact skill links."""
    c = one(db, "SELECT name_th, name_en, description_th, description_en FROM curriculum_courses WHERE course_code = :c", c=code)
    full = f"{c['name_en'] or ''} / {c['name_th']}. {c['description_en'] or ''} {c['description_th'] or ''}"
    db.execute(text("UPDATE curriculum_courses SET embedding = CAST(:e AS vector), embedded_at = now() WHERE course_code = :c"),
               {"e": to_pgvector(embed_texts([full])[0]), "c": code})
    db.execute(text("DELETE FROM course_skill_map WHERE course_code = :c AND method = 'exact'"), {"c": code})
    haystack = f"{c['name_en'] or ''} ; {c['description_en'] or ''} ; {c['description_th'] or ''} ; {c['name_th']}"
    for sid in extract_skill_ids(db, haystack):
        db.execute(text("""INSERT INTO course_skill_map (course_code, skill_id, similarity, method, matched_topic)
                           VALUES (:c, :s, 1.0, 'exact', 'admin edit') ON CONFLICT (course_code, skill_id) DO NOTHING"""),
                   {"c": code, "s": sid})


@router.get("/courses", response_model=list[CourseOut])
def list_courses(db: Session = Depends(get_db)):
    return _load(db)


@router.get("/courses/{code}", response_model=CourseOut)
def get_course(code: str, db: Session = Depends(get_db)):
    return _get(db, code)


@router.post("/courses", response_model=CourseOut, status_code=201, dependencies=[Depends(require_admin)])
def create_course(body: CourseIn, db: Session = Depends(get_db)):
    if one(db, "SELECT 1 AS x FROM curriculum_courses WHERE course_code = :c", c=body.code):
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "COURSE_EXISTS", "message": f"{body.code} already exists"})
    cr = _parse_credits(body.credits)
    db.execute(text("""
        INSERT INTO curriculum_courses (course_code, program, name_th, name_en, credits, hours_theory, hours_practice,
                                        hours_self, category, course_group, description_th, description_en)
        VALUES (:code, :program, :name_th, :name_en, :credits, :ht, :hp, :hs, :category, :course_group, :d_th, :d_en)"""),
        {"code": body.code, "program": settings.program_name, "name_th": body.name_th, "name_en": body.name_en,
         **cr, "category": body.category, "course_group": body.course_group, "d_th": body.description,
         "d_en": body.description_en})
    _refresh(db, body.code)
    db.commit()
    gap.clear_cache()
    return _get(db, body.code)


@router.put("/courses/{code}", response_model=CourseOut, dependencies=[Depends(require_admin)])
def update_course(code: str, body: CourseUpdate, db: Session = Depends(get_db)):
    _get(db, code)
    data = body.model_dump(exclude_unset=True)
    cols = {"name_th": "name_th", "name_en": "name_en", "description": "description_th",
            "description_en": "description_en", "category": "category", "course_group": "course_group"}
    sets, params = [], {"code": code}
    for k, colname in cols.items():
        if k in data:
            sets.append(f"{colname} = :{k}")
            params[k] = data[k]
    if "credits" in data:
        cr = _parse_credits(data["credits"])
        sets += ["credits = :credits", "hours_theory = :ht", "hours_practice = :hp", "hours_self = :hs"]
        params.update(cr)
    if sets:
        db.execute(text(f"UPDATE curriculum_courses SET {', '.join(sets)} WHERE course_code = :code"), params)
    if any(k in data for k in ("name_th", "name_en", "description", "description_en")):
        _refresh(db, code)
    db.commit()
    gap.clear_cache()
    return _get(db, code)


@router.delete("/courses/{code}", status_code=204, dependencies=[Depends(require_admin)])
def delete_course(code: str, db: Session = Depends(get_db)):
    _get(db, code)
    db.execute(text("DELETE FROM course_skill_map WHERE course_code = :c"), {"c": code})
    db.execute(text("DELETE FROM curriculum_courses WHERE course_code = :c"), {"c": code})  # course_topics cascade
    db.commit()
    gap.clear_cache()
    return Response(status_code=204)


@router.post("/courses/{code}/extract", response_model=CourseOut, dependencies=[Depends(require_admin)])
def re_extract(code: str, db: Session = Depends(get_db)):
    _get(db, code)
    _refresh(db, code)
    db.commit()
    gap.clear_cache()
    return _get(db, code)


@router.put("/courses/{code}/skills", response_model=CourseOut, dependencies=[Depends(require_admin)])
def set_skills(code: str, body: CourseSkillsIn, db: Session = Depends(get_db)):
    """Set the course's full skill list: kept links keep their method, removed ones are deleted, new ones are 'manual'."""
    _get(db, code)
    wanted = rows(db, "SELECT id FROM skills WHERE name = ANY(:names)", names=body.skills)
    ids = [r["id"] for r in wanted]
    if ids:
        db.execute(text("DELETE FROM course_skill_map WHERE course_code = :c AND NOT (skill_id = ANY(:ids))"),
                   {"c": code, "ids": ids})
    else:
        db.execute(text("DELETE FROM course_skill_map WHERE course_code = :c"), {"c": code})
    for sid in ids:
        db.execute(text("""INSERT INTO course_skill_map (course_code, skill_id, similarity, method, matched_topic)
                           VALUES (:c, :s, NULL, 'manual', 'researcher-reviewed') ON CONFLICT (course_code, skill_id) DO NOTHING"""),
                   {"c": code, "s": sid})
    db.commit()
    gap.clear_cache()
    return _get(db, code)


@router.get("/skills", response_model=list[str])
def skill_names(q: str = "", limit: int = 20, db: Session = Depends(get_db)):
    """Skill names for the admin autocomplete (skills that appear in jobs, most demanded first)."""
    data = rows(db, """
        SELECT s.name FROM skills s JOIN job_skills js ON js.skill_id = s.id
        WHERE s.name ILIKE :q GROUP BY s.name ORDER BY count(*) DESC LIMIT :k""", q=f"%{q}%", k=max(1, min(limit, 50)))
    return [r["name"] for r in data]
