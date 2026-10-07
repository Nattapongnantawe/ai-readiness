# -*- coding: utf-8 -*-
"""
load.py — โหลดไฟล์ JSON จาก scraper เข้า PostgreSQL

ไฟล์ JSON -> raw_jobs (ดิบ) -> normalize -> companies + jobs
                                          + job_requirement_items (bullet แยกบรรทัด)

รัน:
  python load.py --file ..\\jobthai_v3\\output\\jobs_data.json --site jobthai
  python load.py --file ..\\jobbkk\\data\\jobbkk_all.json --site jobbkk
  python load.py --file a.json --file b.json            # หลายไฟล์
  python load.py --file a.json --dry-run                # แปลงอย่างเดียว ไม่เขียน DB
  python load.py --file a.jsonl                         # รองรับ .jsonl ด้วย

  # ★ บันทึก "structured info" เป็นไฟล์ JSON ก่อนเข้า DB (ตรวจสอบได้)
  python load.py --file a.json --export structured.json --dry-run
"""
import argparse
import json
import os
import sys
from typing import Dict, List

from adapters import adapt

try:                                    # อ่าน DATABASE_URL จาก .env เดียวกับ extractor
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DSN = os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/jobmarket")
BATCH = 500

SQL_RAW = """
INSERT INTO raw_jobs (url_hash, source_site, source_url, payload, scraped_at)
VALUES (%(url_hash)s, %(source_site)s, %(source_url)s, %(payload)s, %(scraped_at)s)
ON CONFLICT (url_hash) DO UPDATE
    SET payload = EXCLUDED.payload, loaded_at = now()
"""

SQL_COMPANY = """
INSERT INTO companies (name, name_normalized, logo_url, description)
VALUES (%(name)s, %(norm)s, %(logo)s, %(desc)s)
ON CONFLICT (name_normalized) DO UPDATE SET
    name        = EXCLUDED.name,
    logo_url    = COALESCE(EXCLUDED.logo_url, companies.logo_url),
    description = COALESCE(EXCLUDED.description, companies.description),
    updated_at  = now()
RETURNING id
"""

SQL_JOB = """
INSERT INTO jobs (
    url_hash, source_site, source_url, detail_url, scraped_at,
    title, company_id,
    salary_raw, salary_type, salary_min, salary_max, salary_period,
    location_raw, province, district, travel,
    num_positions, posted_date, valid_through,
    employment_type, job_category, experience_years, education_level,
    description, qualification, welfare, contact, work_location,
    sections, attributes
) VALUES (
    %(url_hash)s, %(source_site)s, %(source_url)s, %(detail_url)s, %(scraped_at)s,
    %(title)s, %(company_id)s,
    %(salary_raw)s, %(salary_type)s, %(salary_min)s, %(salary_max)s, %(salary_period)s,
    %(location_raw)s, %(province)s, %(district)s, %(travel)s,
    %(num_positions)s, %(posted_date)s, %(valid_through)s,
    %(employment_type)s, %(job_category)s, %(experience_years)s, %(education_level)s,
    %(description)s, %(qualification)s, %(welfare)s, %(contact)s, %(work_location)s,
    %(sections)s, %(attributes)s
)
ON CONFLICT (url_hash) DO UPDATE SET
    detail_url = EXCLUDED.detail_url,
    scraped_at = EXCLUDED.scraped_at,
    title = EXCLUDED.title,
    company_id = EXCLUDED.company_id,
    salary_raw = EXCLUDED.salary_raw,
    salary_type = EXCLUDED.salary_type,
    salary_min = EXCLUDED.salary_min,
    salary_max = EXCLUDED.salary_max,
    salary_period = EXCLUDED.salary_period,
    location_raw = EXCLUDED.location_raw,
    province = EXCLUDED.province,
    district = EXCLUDED.district,
    travel = EXCLUDED.travel,
    num_positions = EXCLUDED.num_positions,
    posted_date = COALESCE(EXCLUDED.posted_date, jobs.posted_date),
    valid_through = EXCLUDED.valid_through,
    employment_type = EXCLUDED.employment_type,
    job_category = EXCLUDED.job_category,
    experience_years = EXCLUDED.experience_years,
    education_level = EXCLUDED.education_level,
    description = EXCLUDED.description,
    qualification = EXCLUDED.qualification,
    welfare = EXCLUDED.welfare,
    contact = EXCLUDED.contact,
    work_location = EXCLUDED.work_location,
    sections = EXCLUDED.sections,
    attributes = EXCLUDED.attributes,
    updated_at = now()
RETURNING id, (xmax = 0) AS inserted
"""

# ลบ bullet เดิมของงานนี้ก่อน แล้วใส่ใหม่ (กันข้อมูลค้างเวลาเนื้อหาเปลี่ยน)
SQL_DEL_ITEMS = "DELETE FROM job_requirement_items WHERE job_id = %s"
SQL_ITEM = """
INSERT INTO job_requirement_items (job_id, source, seq, content)
VALUES (%(job_id)s, %(source)s, %(seq)s, %(content)s)
ON CONFLICT (job_id, source, seq) DO UPDATE SET content = EXCLUDED.content
"""

SQL_TAG = ("INSERT INTO tags (name) VALUES (%s) "
           "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id")
SQL_JOB_TAG = "INSERT INTO job_tags (job_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING"


# ---------------- helpers ----------------
def read_json(path: str) -> List[dict]:
    """รองรับทั้ง .json (array) และ .jsonl (บรรทัดละ record)"""
    if path.endswith(".jsonl"):
        rows = []
        with open(path, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    try:
                        rows.append(json.loads(ln))
                    except json.JSONDecodeError:
                        pass
        return rows
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return list(data.values()) if isinstance(data, dict) else data


def to_records(rows: List[dict], site: str = None) -> List[dict]:
    out, bad = [], 0
    for r in rows:
        try:
            rec = adapt(r, site)
            if rec["url_hash"] and rec["title"]:
                rec["_raw"] = r
                out.append(rec)
            else:
                bad += 1
        except Exception as e:
            bad += 1
            print(f"  ⚠️ ข้าม 1 แถว: {e}")
    if bad:
        print(f"  ⚠️ ข้ามทั้งหมด {bad} แถว (ข้อมูลไม่ครบ)")
    return out


def export_structured(records: List[dict], path: str) -> None:
    """
    บันทึก record กลาง (structured info) เป็นไฟล์ JSON
    ขั้นตอนตามโจทย์:  raw json -> สกัด info -> [structured info as json] -> DB
    ไฟล์นี้ใช้ตรวจสอบก่อนเข้าฐานข้อมูล และใช้เป็นตัวอย่างประกอบรายงานได้
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    out = []
    for r in records:
        d = {k: v for k, v in r.items() if k != "_raw"}   # ไม่เอา JSON ดิบมาปน
        d["posted_date"] = str(d["posted_date"]) if d["posted_date"] else None
        d["valid_through"] = str(d["valid_through"]) if d["valid_through"] else None
        out.append(d)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"  💾 structured info -> {path}  ({len(out)} งาน)")


def quality_report(records: List[dict]) -> None:
    """สรุปความครบถ้วนของข้อมูลหลังแปลง — ใช้ตรวจก่อนเข้า DB"""
    n = len(records)
    if not n:
        return
    checks = [
        ("มีชื่อตำแหน่ง",     lambda r: bool(r["title"])),
        ("มีชื่อบริษัท",      lambda r: bool(r["company_name"])),
        ("มีโลโก้บริษัท",     lambda r: bool(r["company_logo_url"])),
        ("มีคำแนะนำบริษัท",   lambda r: bool(r["company_description"])),
        ("มีรายละเอียดงาน",   lambda r: bool(r["description"])),
        ("มีคุณสมบัติ",       lambda r: bool(r["qualification"])),
        ("มีจังหวัด",         lambda r: bool(r["province"])),
        ("เงินเดือนเป็นตัวเลข", lambda r: r["salary_min"] is not None),
        ("มีวันที่ประกาศ",     lambda r: bool(r["posted_date"])),
        ("มีวิธีการเดินทาง",   lambda r: bool(r["travel"])),
        ("แตก bullet ได้",    lambda r: bool(r["requirement_items"])),
    ]
    print(f"\n  ความครบถ้วนของข้อมูล ({n} งาน)")
    print("  " + "-" * 44)
    for label, fn in checks:
        c = sum(1 for r in records if fn(r))
        pct = c * 100 // n
        bar = "█" * (pct // 5) + "·" * (20 - pct // 5)
        print(f"  {label:20} {bar} {pct:3d}%  ({c})")


def dedup(records: List[dict]) -> List[dict]:
    seen: Dict[str, dict] = {}
    for r in records:
        seen[r["url_hash"]] = r          # เอาอันหลังสุด
    dropped = len(records) - len(seen)
    if dropped:
        print(f"  ♻️ ตัดซ้ำในไฟล์ {dropped} รายการ")
    return list(seen.values())


# ---------------- load ----------------
def load(records: List[dict], dsn: str = DSN) -> dict:
    import psycopg2
    from psycopg2.extras import Json, execute_batch

    st = {"raw": 0, "inserted": 0, "updated": 0, "companies": 0,
          "items": 0, "tags": 0}
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            # 1) raw_jobs
            execute_batch(cur, SQL_RAW, [{
                "url_hash": r["url_hash"], "source_site": r["source_site"],
                "source_url": r["source_url"], "payload": Json(r["_raw"]),
                "scraped_at": r["scraped_at"],
            } for r in records], page_size=BATCH)
            st["raw"] = len(records)

            # 2) companies (ครั้งเดียวต่อบริษัท)
            comp: Dict[str, int] = {}
            for r in records:
                n = r["company_norm"]
                if not n:
                    continue
                if n not in comp:
                    cur.execute(SQL_COMPANY, {
                        "name": r["company_name"], "norm": n,
                        "logo": r["company_logo_url"], "desc": r["company_description"]})
                    comp[n] = cur.fetchone()[0]
                elif r["company_logo_url"] or r["company_description"]:
                    # เจอบริษัทเดิมแต่รอบนี้มีโลโก้/คำอธิบาย -> เติมให้
                    cur.execute(SQL_COMPANY, {
                        "name": r["company_name"], "norm": n,
                        "logo": r["company_logo_url"], "desc": r["company_description"]})
            st["companies"] = len(comp)

            # 3) jobs + 4) requirement items + 5) tags
            tag_ids: Dict[str, int] = {}
            for r in records:
                r["company_id"] = comp.get(r["company_norm"])
                r.setdefault("salary_period", "month")
                cur.execute(SQL_JOB, {**r,
                                      "sections": Json(r["sections"]),
                                      "attributes": Json(r["attributes"])})
                job_id, inserted = cur.fetchone()
                st["inserted" if inserted else "updated"] += 1

                items = r["requirement_items"]
                cur.execute(SQL_DEL_ITEMS, (job_id,))
                if items:
                    execute_batch(cur, SQL_ITEM,
                                  [{"job_id": job_id, **it} for it in items],
                                  page_size=BATCH)
                    st["items"] += len(items)

                for t in r["tags"]:
                    if t not in tag_ids:
                        cur.execute(SQL_TAG, (t,))
                        tag_ids[t] = cur.fetchone()[0]
                    cur.execute(SQL_JOB_TAG, (job_id, tag_ids[t]))
            st["tags"] = len(tag_ids)

            cur.execute("UPDATE raw_jobs SET processed_at = now() "
                        "WHERE url_hash = ANY(%s)",
                        ([r["url_hash"] for r in records],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="append", required=True, help="ไฟล์ .json หรือ .jsonl")
    ap.add_argument("--site", choices=["jobthai", "jobbkk"], help="ระบุแหล่ง (ไม่ใส่ = เดาเอง)")
    ap.add_argument("--dsn", default=DSN)
    ap.add_argument("--dry-run", action="store_true", help="ไม่เขียน DB")
    ap.add_argument("--export", metavar="FILE",
                    help="บันทึก structured info เป็นไฟล์ JSON (ตรวจก่อนเข้า DB)")
    a = ap.parse_args()

    all_recs: List[dict] = []
    for path in a.file:
        if not os.path.exists(path):
            print(f"✗ ไม่พบไฟล์: {path}")
            sys.exit(1)
        rows = read_json(path)
        print(f"\n📄 {path}: {len(rows)} แถว")
        recs = to_records(rows, a.site)
        print(f"  ✓ แปลงสำเร็จ {len(recs)} รายการ")
        all_recs.extend(recs)

    all_recs = dedup(all_recs)
    items = sum(len(r["requirement_items"]) for r in all_recs)
    print(f"\nรวม {len(all_recs)} งาน | bullet ทั้งหมด {items} รายการ")

    quality_report(all_recs)

    if a.export:
        export_structured(all_recs, a.export)

    if a.dry_run:
        print("\n--dry-run: ไม่เขียน DB")
        if not a.export:
            print("ตัวอย่างรายการแรก:")
            s = {k: v for k, v in all_recs[0].items() if k != "_raw"}
            print(json.dumps(s, ensure_ascii=False, indent=2, default=str)[:900])
        return

    db = a.dsn.rsplit("/", 1)[-1]
    print(f"\n🗄️  เขียนลงฐานข้อมูล: {db}")
    st = load(all_recs, a.dsn)
    print(f"\n{'=' * 46}")
    print(f"✅ raw_jobs        : {st['raw']}")
    print(f"   งานเพิ่มใหม่    : {st['inserted']}")
    print(f"   งานอัปเดต      : {st['updated']}")
    print(f"   บริษัท          : {st['companies']}")
    print(f"   bullet (items) : {st['items']}")
    if st["tags"]:
        print(f"   ป้ายกำกับ       : {st['tags']}")


if __name__ == "__main__":
    main()