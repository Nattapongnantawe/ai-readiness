# ชุดข้อมูล (SQL Dump) — `jobmarket.sql.gz`

ไฟล์ dump อยู่ใน **GitHub Releases** ของ repo นี้ (ใหญ่เกินกว่าจะเก็บใน git) ดาวน์โหลดแล้ววางไว้ในโฟลเดอร์นี้

| | |
| --- | --- |
| รูปแบบ | PostgreSQL plain SQL บีบอัด gzip (`pg_dump -Fp -Z 9 --no-owner`) จาก PostgreSQL 18 + pgvector |
| ประกาศงาน | ≥ 3,000 รายการ (JobThai + JobBKK สายคอมพิวเตอร์/ไอที และวิศวกรรมไฟฟ้า/อิเล็กทรอนิกส์) |
| เวกเตอร์ | `jobs.embedding`, `skills.embedding`, `std_skills.embedding`, `course_topics.embedding` — `vector(1024)` จาก BAAI/bge-m3 + ดัชนี HNSW |
| ตารางหลัก | `jobs`, `companies`, `job_requirement_items`, `skills`, `job_skills`, `std_skills`, `skill_standard_map`, `curriculum_courses`, `course_topics`, `course_skill_map` |
| ไม่มีข้อมูล | ข้อมูลติดต่อ (PDPA): `jobs.contact` ว่าง, เบอร์โทร/อีเมล/LINE ในชื่องานและเนื้อหาถูกแทนด้วย `[ซ่อนข้อมูลติดต่อ]` (`backend/scripts/pdpa_clean.py`) · ไม่มีข้อมูลใน `raw_jobs` (JSON ดิบ) และ log การรันของระบบ |

## ติดตั้ง
**Docker:** วางไฟล์ไว้ที่นี่แล้ว `docker compose up -d` — คอนเทนเนอร์ `db` จะ restore ให้เองในการเปิดครั้งแรก

**Windows (PostgreSQL 18 + pgvector ติดตั้งในเครื่อง):** ดับเบิลคลิก `restore-db.bat` ในโฟลเดอร์นี้

**คำสั่งเอง (Linux/macOS):**
```bash
createdb jobmarket
psql -d jobmarket -c "CREATE EXTENSION IF NOT EXISTS vector"
gunzip -c jobmarket.sql.gz | psql -d jobmarket
```

## ตรวจว่าครบ
```sql
SELECT count(*) AS jobs, count(embedding) AS with_vector FROM jobs;
SELECT source_site, count(*) FROM jobs GROUP BY 1;
```
