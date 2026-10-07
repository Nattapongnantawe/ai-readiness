import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app import gap as engine
from app.auth import require_admin
from app.config import settings
from app.db import get_db

router = APIRouter(prefix="/gap-analysis", tags=["gap-analysis"])


def _codes(courses: str | None) -> list[str] | None:
    if not courses:
        return None
    codes = [c.strip() for c in courses.split(",") if c.strip()]
    if len(codes) > settings.max_selected_courses:
        raise HTTPException(422, detail={"code": "TOO_MANY_COURSES",
                                         "message": f"เลือกได้ไม่เกิน {settings.max_selected_courses} รายวิชา"})
    return codes or None


def _payload(db: Session, courses: str | None, exclude_manual: bool, fresh: bool = False) -> dict:
    p = engine.compute(db, _codes(courses), exclude_manual=exclude_manual, use_cache=not fresh)
    return {**p, "computed_at": datetime.now(timezone.utc).isoformat()}


@router.get("")
def get_gap(courses: str | None = Query(None, description="Comma-separated course codes (≤ 15). Empty = whole curriculum."),
            exclude_manual: bool = False, db: Session = Depends(get_db)):
    return _payload(db, courses, exclude_manual)


@router.post("/recalculate", dependencies=[Depends(require_admin)])
def recalculate(courses: str | None = None, exclude_manual: bool = False, db: Session = Depends(get_db)):
    engine.clear_cache()
    return _payload(db, courses, exclude_manual, fresh=True)


@router.get("/export.csv")
def export_csv(courses: str | None = None, exclude_manual: bool = False, db: Session = Depends(get_db)):
    p = _payload(db, courses, exclude_manual)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Match Score", p["overall_match_score"], "Match Score (no manual links)", p["overall_match_score_no_manual"],
                "Computed at", p["computed_at"]])
    w.writerow(["Courses analysed", len(p["courses"]), "Skills analysed", p["skills_analyzed"], "Jobs", p["total_jobs"]])
    w.writerow([])
    w.writerow(["Skill", "Jobs", "Demand (% of jobs)", "Coverage", "Gap priority", "Suggested course code", "Suggested course", "Closest topic", "Topic similarity"])
    for m in p["missing_skills"]:
        w.writerow([m["skill"], m["jobs"], round(m["demand_pct"] * 100, 2), m["coverage"], m["priority"],
                    m["suggested_course_code"], m["suggested_course"], m.get("suggested_topic", ""),
                    m.get("suggested_similarity") or ""])
    w.writerow([])
    w.writerow(["Course code", "Course", "Contribution", "Relevance", "Linked skills"])
    for c in p["courses"]:
        w.writerow([c["code"], c["name"], c["contribution"], c["relevance"], c["skill_count"]])
    # UTF-8 with BOM so Thai text opens correctly in Excel (FR-GA-07)
    return Response(content="﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="gap-analysis.csv"'})