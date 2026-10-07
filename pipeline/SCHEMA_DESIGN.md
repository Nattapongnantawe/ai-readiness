# Database Schema Design
**Sprint 1 — Job Market Data Warehouse (PostgreSQL)**

## 1. ภาพรวม

เก็บประกาศงานจาก 2 แหล่ง (JobThai, JobBKK) ที่มีโครงสร้างต่างกัน ให้อยู่ใน schema เดียวกัน
พร้อมระบบ deduplication และเก็บข้อมูลดิบไว้ re-process ได้

```
Scraper → raw_jobs (JSON ดิบ) → [Pipeline: normalize] → jobs + companies + tags → Analysis
```

## 2. ตารางทั้งหมด

| ตาราง | หน้าที่ |
|---|---|
| `raw_jobs` | เก็บ JSON ดิบตามที่ scraper ดึงมา ไม่แตะต้อง |
| `companies` | บริษัท (แยกออกมาเพราะ 1 บริษัทลงหลายงาน) |
| `jobs` | ตารางหลัก ข้อมูลที่ normalize แล้ว |
| `tags` / `job_tags` | ป้ายกำกับ เช่น "รับสมัครด่วน" (many-to-many) |
| `skills` / `job_skills` | ทักษะที่สกัดจากประกาศ (ใช้ตอนวิเคราะห์) |
| `crawl_runs` | log การรัน scraper แต่ละครั้ง |

## 3. เหตุผลการออกแบบ (ข้อสำคัญ)

### 3.1 ทำไมต้องมี `raw_jobs` แยกจาก `jobs`
การดึงข้อมูลเป็นขั้นตอนที่แพงที่สุด (ช้า + รบกวนเซิร์ฟเวอร์เว็บเป้าหมาย)
ถ้าเก็บแต่ข้อมูลที่ normalize แล้ว พอต้องแก้ parser หรือเพิ่มฟิลด์ใหม่ จะต้องกลับไปยิงเว็บใหม่ทั้งหมด
การเก็บ JSON ดิบไว้ทำให้ re-process ได้จาก DB ตรง ๆ

`processed_at IS NULL` = แถวที่ยังรอ normalize (pipeline หยิบไปทำต่อได้)

### 3.2 เงินเดือนต้องเก็บทั้งข้อความและตัวเลข
จากข้อมูลจริง เงินเดือนส่วนใหญ่**ไม่ใช่ตัวเลข**:

| ค่าที่เจอจริง | salary_type | salary_min | salary_max |
|---|---|---|---|
| `17,000 - 25,000 บาท` | `range` | 17000 | 25000 |
| `20,000 บาท` | `fixed` | 20000 | 20000 |
| `ตามประสบการณ์` | `negotiable` | NULL | NULL |
| `ตามโครงสร้างบริษัทฯ` | `negotiable` | NULL | NULL |
| `ไม่ระบุ` / ว่าง | `unspecified` | NULL | NULL |

ถ้าออกแบบเป็น `INTEGER NOT NULL` จะเก็บข้อมูลส่วนใหญ่ไม่ได้เลย
จึงเก็บ `salary_raw` (ข้อความเดิม) + `salary_type` (ประเภท) + `salary_min/max` ที่เป็น NULL ได้

### 3.3 ทำไมใช้ JSONB สำหรับ `sections`
JobBKK ใช้หัวข้อไม่คงที่ในแต่ละประกาศ เช่น
`"หน้าที่และความรับผิดชอบ"`, `"คุณสมบัติด้านความรู้และความสามารถ"`, `"สวัสดิการ"`
ซึ่งแต่ละประกาศมีหัวข้อไม่เหมือนกัน — สร้างคอลัมน์ตายตัวไม่ได้

วิธีแก้: ฟิลด์ที่ทั้ง 2 เว็บมีเหมือนกัน → คอลัมน์ปกติ (query เร็ว, มี index)
ส่วนหัวข้อที่ไม่คงที่ → `sections JSONB` + GIN index (ยังค้นได้)

### 3.4 Deduplication 2 ชั้น
- `raw_jobs.url_hash UNIQUE` — กันเก็บ JSON ดิบซ้ำ
- `jobs.url_hash UNIQUE` — กัน normalize ซ้ำ

`url_hash` = SHA-256 ของ URL ที่ตัด query string ออกแล้ว (มาจาก scraper)
ทำให้ `/th/job/123?utm_source=google` กับ `/th/job/123` ถือเป็นงานเดียวกัน

Pipeline ใช้ `INSERT ... ON CONFLICT (url_hash) DO UPDATE` = รันซ้ำกี่ครั้งก็ปลอดภัย (idempotent)

## 4. การแมปฟิลด์จาก 2 เว็บ

| คอลัมน์ใน `jobs` | JobThai | JobBKK |
|---|---|---|
| `url_hash` | `url_hash` | `url_hash` |
| `source_url` | `url` | `source_url` |
| `title` | `title` | `job_title` |
| `company_id` | `company` → lookup | `company_name` → lookup |
| `salary_raw` | `salary` | `salary` |
| `location_raw` | `location` | `location` |
| `province` | แยกจาก `location` | `address_region` (ตรง ๆ) |
| `district` | แยกจาก `location` | `address_locality` |
| `employment_type` | — | `employmentType` |
| `job_category` | — | `occupationalCategory` |
| `experience_years` | — | `fields['ประสบการณ์(ปี)']` |
| `education_level` | — | `fields['ระดับการศึกษา']` |
| `attributes` | — | `fields` ทั้งก้อน |
| `num_positions` | `num_positions` | `fields['จำนวนที่รับ']` |
| `posted_date` | `post_date` (พ.ศ.) | `datePosted` (ISO) |
| `description` | `description` | `sections['หน้าที่และความรับผิดชอบ']` |
| `qualification` | `qualification` | `sections['คุณสมบัติ...']` |
| `welfare` | — | `sections['สวัสดิการ']` |
| `how_to_apply` | `how_to_apply` | — |
| `contact` | `contact` | — |
| `sections` | — | `sections` ทั้งก้อน |

> หมายเหตุ: JobBKK มีฟิลด์ที่ JobThai ไม่มี — `employmentType`, `occupationalCategory`,
> `datePosted` (ISO 8601), `address_region`/`address_locality` (แยกจังหวัด/เขตมาให้แล้ว)
> และ `fields` ที่เก็บ เพศ/อายุ/วันทำงาน/เวลาทำงาน/ระดับการศึกษา → เก็บลง `attributes JSONB`

## 5. การแปลงข้อมูลที่ pipeline ต้องทำ

| จาก | เป็น | ตัวอย่าง |
|---|---|---|
| `"17,000 - 25,000 บาท"` | salary_min/max | 17000, 25000 |
| `"13 ก.ย. 69"` (พ.ศ.) | DATE | 2026-09-13 |
| `"3 อัตรา"` | INTEGER | 3 |
| `"อ.โชคชัย จ.นครราชสีมา"` | province/district | นครราชสีมา / โชคชัย |
| `"บริษัท ABC จำกัด (มหาชน)"` | name_normalized | abc |

## 6. Index ที่ใส่ไว้และเหตุผล

| Index | ใช้ตอน |
|---|---|
| `uq_jobs_hash` | dedup (บังคับใช้โดย constraint) |
| `ix_jobs_province` | นับงานรายจังหวัด |
| `ix_jobs_salary` (partial) | กรองช่วงเงินเดือน — partial เพราะส่วนใหญ่เป็น NULL |
| `ix_jobs_title_trgm` | ค้นหาชื่อตำแหน่งแบบ LIKE/fuzzy |
| `ix_jobs_sections` (GIN) | ค้นในหัวข้อที่ไม่คงที่ |
| `ix_jobs_search` (GIN) | full-text search |
| `ix_raw_jobs_unprocessed` (partial) | pipeline หาแถวที่ยังไม่ normalize |

## 7. View สำหรับวิเคราะห์

- `v_jobs_full` — jobs + ชื่อบริษัท + เงินเดือนกลาง
- `v_salary_by_province` — เงินเดือนเฉลี่ยรายจังหวัด
- `v_source_summary` — สรุปจำนวนงาน/ความครบถ้วนต่อแหล่ง

## 8. วิธีติดตั้ง

```bash
createdb jobmarket
psql -d jobmarket -f schema.sql
```
