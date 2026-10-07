# Data Pipeline v2

แปลงไฟล์ JSON จาก scraper → PostgreSQL (schema v2)

```
jobs_data.json (JobThai v3) ┐
                            ├→ adapters → parsers → raw_jobs
jobbkk_all.json             ┘                        ↓
                                    companies + jobs + job_requirement_items
```

## เปลี่ยนอะไรจาก v1
| | v1 | v2 |
|---|---|---|
| JobThai | อ่านฟิลด์เก่า (`url`, `company`) | อ่านฟิลด์ v3 (`source_url`, `company_name`) |
| โลโก้/คำแนะนำบริษัท | ไม่มี | เก็บใน **ตาราง companies** (เป็นของบริษัท ไม่ใช่ของงาน) |
| วิธีการเดินทาง | ไม่มี | `jobs.travel` |
| bullet แต่ละข้อ | ไม่มี | **ตาราง `job_requirement_items`** ← ฐานของขั้นจำแนกทักษะ |
| ไฟล์ .jsonl | ไม่รองรับ | รองรับ |

## ติดตั้ง
```powershell
pip install -r requirements.txt
psql -U postgres -d jobmarket -f ..\db_v2\schema.sql
$env:DATABASE_URL="postgresql://postgres:รหัส@localhost:5432/jobmarket"
```
> ⚠️ `schema.sql` มี `DROP TABLE` — ข้อมูลเดิมจะหายหมด (ตั้งใจ เพราะต้องโหลดใหม่ทั้งคู่)

## ขั้นตอนตามโจทย์
```
raw json          →  สกัด info        →  structured info as json  →  DB
jobs_data.json       adapters.py           structured.json            PostgreSQL
                     parsers.py            (--export)
```

## ใช้งาน
```powershell
# 1) แปลง + บันทึกเป็น structured json + ดูรายงานคุณภาพ (ยังไม่แตะ DB)
python load.py --file "...\jobs_data.json" --site jobthai --export output\structured_jobthai.json --dry-run

# 2) เข้า DB จริง
python load.py --file "...\jobs_data.json" --site jobthai

# JobBKK
python load.py --file "...\jobbkk_all.json" --site jobbkk
```

### ตัวเลือก
| ตัวเลือก | ทำอะไร |
|---|---|
| `--dry-run` | แปลงอย่างเดียว ไม่เขียน DB |
| `--export FILE` | บันทึก structured info เป็น JSON (ตรวจก่อน / ใช้ประกอบรายงาน) |
| `--site` | ระบุแหล่ง (ไม่ใส่ = เดาจากข้อมูล) |

ทุกครั้งที่รันจะมี **รายงานความครบถ้วน** แสดงเป็นแถบ % ว่าแต่ละฟิลด์มีข้อมูลกี่ %

## Deduplication 3 ชั้น
1. ในไฟล์เดียวกัน — dedup ด้วย `url_hash`
2. `raw_jobs.url_hash UNIQUE`
3. `jobs.url_hash UNIQUE` + `ON CONFLICT DO UPDATE` → รันซ้ำได้ไม่พัง

## การแปลงข้อมูล
| ดิบ | ผลลัพธ์ |
|---|---|
| `"18,000 - 20,000 บาท"` | range, 18000, 20000 |
| `"ตามประสบการณ์"` | negotiable, NULL, NULL |
| `"18 ก.ย. 69"` (พ.ศ.) | 2026-09-18 |
| `"เขตสวนหลวง กรุงเทพมหานคร"` | กรุงเทพมหานคร / สวนหลวง |
| `"BTS ราชเทวี, สยาม"` | หาจังหวัดจากที่อยู่ในช่อง contact แทน |
| `"บริษัท ABC จำกัด"` | `abc` (ใช้จับบริษัทซ้ำ) |

## ตาราง job_requirement_items
เก็บ bullet แต่ละข้อแยกบรรทัด พร้อมคอลัมน์ `category` ที่ยังว่าง
ขั้นตอนถัดไป (จำแนก skill / experience / certificate) จะมาเติมคอลัมน์นี้

```sql
SELECT * FROM v_requirement_breakdown;   -- ดูความคืบหน้าการจำแนก
```
