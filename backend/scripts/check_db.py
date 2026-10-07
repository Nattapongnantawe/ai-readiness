"""Check that DATABASE_URL points at the jobmarket database and has everything Module 4 reads.

    python -m scripts.check_db

Prints missing tables/columns and the raw values the views normalise (seniority, work_mode,
source_site, skill_type, category) so app/sql/views.sql can be adjusted if needed.
"""
import sys

from sqlalchemy import create_engine, text

from app.config import settings

NEED = {
    "jobs": ["id", "title", "company_id", "province", "source_site", "source_url", "detail_url", "seniority",
             "work_mode", "salary_min", "salary_max", "posted_date", "scraped_at", "updated_at", "description",
             "qualification", "welfare", "experience_years", "education_level", "employment_type",
             "llm_extracted_at", "embedding"],
    "companies": ["id", "name"],
    "skills": ["id", "name", "skill_type", "category", "embedding"],
    "job_skills": ["job_id", "skill_id", "is_required"],
    "skill_standard_map": ["skill_id", "standard", "std_label", "method"],
    "curriculum_courses": ["course_code", "program", "name_th", "name_en", "credits", "hours_theory", "hours_practice",
                           "hours_self", "category", "course_group", "prerequisite", "description_th", "description_en",
                           "embedding", "embedded_at"],
    "course_skill_map": ["course_code", "skill_id", "similarity", "method", "matched_topic"],
}
VIEWS = ["v_std_coverage_by_standard"]
DISTINCT = [("jobs", "seniority"), ("jobs", "work_mode"), ("jobs", "source_site"), ("skills", "skill_type"),
            ("skills", "category"), ("course_skill_map", "method"), ("skill_standard_map", "standard")]


def main() -> int:
    eng = create_engine(settings.database_url)
    ok = True
    with eng.connect() as c:
        print(f"DB: {c.execute(text('SELECT current_database()')).scalar()}")
        cols = {}
        for t, col in c.execute(text("SELECT table_name, column_name FROM information_schema.columns "
                                     "WHERE table_schema = current_schema()")):
            cols.setdefault(t, set()).add(col)
        for t, need in NEED.items():
            if t not in cols:
                print(f"  ✗ ไม่มีตาราง {t}")
                ok = False
                continue
            miss = [x for x in need if x not in cols[t]]
            print(f"  {'✓' if not miss else '✗'} {t}" + (f"  ขาดคอลัมน์: {', '.join(miss)}" if miss else ""))
            ok &= not miss
        for v in VIEWS:
            exists = c.execute(text("SELECT to_regclass(:v)"), {"v": v}).scalar()
            print(f"  {'✓' if exists else '✗'} view {v}")
            ok &= bool(exists)
        ext = c.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")).scalar()
        print(f"  {'✓' if ext else '✗'} pgvector {ext or '(ไม่ได้ติดตั้ง)'}")
        ok &= bool(ext)
        print("\nค่าที่ views.sql ต้องแปลง:")
        for t, col in DISTINCT:
            if col in cols.get(t, set()):
                vals = c.execute(text(f"SELECT {col}::text AS v, count(*) AS n FROM {t} GROUP BY 1 ORDER BY 2 DESC LIMIT 12")).all()
                print(f"  {t}.{col}: " + ", ".join(f"{v}({n})" for v, n in vals))
    print("\n✅ พร้อมใช้" if ok else "\n❌ แก้ตามรายการด้านบนก่อน (หรือแก้ชื่อคอลัมน์ใน app/sql/views.sql)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
