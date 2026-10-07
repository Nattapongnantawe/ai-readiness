# -*- coding: utf-8 -*-
r"""
ย้ายผลจาก jobmarket_test -> jobmarket ด้วยการ "เปลี่ยนชื่อฐานข้อมูล" (ไม่คัดลอก ไม่ลบข้อมูล)

  jobmarket       -> jobmarket_old_YYYYMMDD   (เก็บไว้เป็นสำรอง)
  jobmarket_test  -> jobmarket

  python -m extractor.db_promote            # ดูจำนวนแถวเทียบ 2 ฐาน (ยังไม่เปลี่ยนอะไร)
  python -m extractor.db_promote --yes      # เปลี่ยนชื่อจริง

หลังเสร็จ: แก้ .env ให้ DATABASE_URL ชี้ไปที่ /jobmarket
ปิด pgAdmin / VS Code ที่เปิดฐานข้อมูลทั้งสองก่อน (สคริปต์จะตัดการเชื่อมต่อที่ค้างให้)
"""
import argparse
import datetime
import os
import sys

import psycopg2
from psycopg2.extensions import make_dsn, parse_dsn

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SRC, DST = "jobmarket_test", "jobmarket"
TABLES = ["jobs", "companies", "skills", "job_skills", "skill_standard_map", "std_skills",
          "curriculum_courses", "course_skill_map"]


def base_dsn():
    url = os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/jobmarket_test")
    return parse_dsn(url)


def dsn_for(db):
    d = base_dsn(); d["dbname"] = db
    return make_dsn(**d)


def exists(cur, db):
    cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (db,))
    return cur.fetchone() is not None


def counts(db):
    out = {}
    try:
        conn = psycopg2.connect(dsn_for(db))
    except psycopg2.OperationalError:
        return None
    with conn.cursor() as cur:
        for t in TABLES:
            cur.execute("SELECT to_regclass(%s)", (t,))
            if cur.fetchone()[0] is None:
                out[t] = "-"
            else:
                cur.execute(f"SELECT count(*) FROM {t}")
                out[t] = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM information_schema.columns "
                    "WHERE table_name='jobs' AND column_name='embedding'")
        out["jobs.embedding"] = "มี" if cur.fetchone()[0] else "-"
    conn.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="เปลี่ยนชื่อจริง")
    a = ap.parse_args()

    admin = psycopg2.connect(dsn_for("postgres"))
    admin.autocommit = True
    cur = admin.cursor()
    if not exists(cur, SRC):
        sys.exit(f"❌ ไม่พบฐาน {SRC}")

    cs, cd = counts(SRC), counts(DST) if exists(cur, DST) else None
    print(f"\n{'ตาราง':22}{SRC:>16}{DST:>16}")
    for k in TABLES + ["jobs.embedding"]:
        print(f"{k:22}{str(cs[k]):>16}{str(cd[k]) if cd else '(ไม่มีฐาน)':>16}")

    if cs["jobs"] in ("-", 0) or cs["curriculum_courses"] == "-":
        sys.exit("\n❌ jobmarket_test ดูไม่ครบ — ยกเลิก")

    backup = f"{DST}_old_{datetime.date.today():%Y%m%d}"
    print(f"\nแผน: {DST} -> {backup}   และ   {SRC} -> {DST}")
    if not a.yes:
        print("ยังไม่ได้เปลี่ยนอะไร — ตรวจตัวเลขแล้วรันใหม่ด้วย --yes")
        return

    if exists(cur, backup):
        sys.exit(f"❌ มีฐาน {backup} อยู่แล้ว — ลบหรือเปลี่ยนชื่อก่อน")
    for db in (SRC, DST):
        cur.execute("""SELECT pg_terminate_backend(pid) FROM pg_stat_activity
                       WHERE datname=%s AND pid <> pg_backend_pid()""", (db,))
    if cd is not None:
        cur.execute(f'ALTER DATABASE "{DST}" RENAME TO "{backup}"')
        print(f"✔ {DST} -> {backup}")
    cur.execute(f'ALTER DATABASE "{SRC}" RENAME TO "{DST}"')
    print(f"✔ {SRC} -> {DST}")
    admin.close()

    print(f"\n✅ เสร็จ — แก้ .env:  DATABASE_URL=.../{DST}")
    print(f"   ถ้าต้องการย้อนกลับ: เปลี่ยนชื่อ {DST} -> {SRC} และ {backup} -> {DST}")


if __name__ == "__main__":
    main()
