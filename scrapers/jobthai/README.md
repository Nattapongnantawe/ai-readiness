# JobThai Scraper v3 — Single-Pass Extraction

ดึงข้อมูลงานสายไอทีจาก JobThai แบบ **จบครบใน 1 รอบต่อ 1 งาน**
(ไม่แยกเป็น 2 ขั้นตอนเหมือนเวอร์ชันก่อน)

## Flow ต่อ 1 งาน
```
หน้ารายการ → คลิกงาน → ดึงข้อมูลบริษัท+ภาพรวม → เปิดหน้ารายละเอียดเต็ม
→ ดึง job description + คุณสมบัติ → ตัดข้อมูลซ้ำ → บันทึก JSON → งานถัดไป
```

## ติดตั้ง
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

## ใช้งาน
```powershell
python main.py              # ดึงงาน (รันซ้ำได้ ไม่ดึงงานเดิม)
python main.py --new        # ดึงเฉพาะงานใหม่ (เจองานเดิมติดกันแล้วหยุด)
python main.py --check URL  # ตรวจว่าหน้านั้นดึงอะไรได้บ้าง
```

## ไฟล์ผลลัพธ์
| ไฟล์ | คืออะไร |
|---|---|
| `output/jobs.jsonl` | 1 งานต่อ 1 บรรทัด เขียนทันทีทุกงาน — แครชแล้วไม่หาย |
| `output/jobs_data.json` | JSON array สำหรับส่งงาน / เข้า pipeline |
| `output/sample_job.json` | ตัวอย่างงานเดียว (จาก `--check`) |

## ข้อมูลที่เก็บได้ต่อ 1 งาน
```jsonc
{
  "url_hash": "...",              // กันงานซ้ำ
  "source_url": "...",            // หน้าที่คลิกเข้าไปครั้งแรก
  "detail_url": "...",            // หน้ารายละเอียดเต็ม
  "scraped_at": "2026-09-15T...",

  // Step 2 — ข้อมูลบริษัท + ภาพรวมงาน
  "company_name": "...",
  "company_logo_url": "https://...",   // ลิงก์รูป ไม่ได้ดาวน์โหลดไฟล์
  "company_description": "...",
  "job_title": "...",
  "location": "...",
  "salary": "...",
  "num_positions": "...",
  "post_date": "...",
  "welfare": "...",
  "contact": "...",
  "work_location": "...",
  "travel": "...",                     // บางงานไม่มี → ว่าง

  // Step 3 — ตัดส่วนที่ซ้ำกับ Step 2 ออกแล้ว
  "job_description": "...",
  "qualification": "...",

  // เตรียมไว้ให้ขั้นสกัดทักษะ
  "job_description_items": ["...", "..."],
  "qualification_items": ["...", "..."]
}
```

## เงื่อนไขตามโจทย์ (ทดสอบแล้ว)
| เงื่อนไข | ทำที่ไหน |
|---|---|
| ตัดข้อมูลที่ซ้ำระหว่าง Step 3 กับ Step 2 | `textutil.remove_duplicate_lines()` |
| ห้ามดึง "วิธีการสมัครงาน" และ "Tags" | `extract._strip_excluded()` + `config.EXCLUDE_SECTIONS` |
| กันประกาศซ้ำ | `url_hash` (SHA-256 ตัด query) |
| งานใหม่โผล่หน้าแรก → ดึงต่อได้ | `python main.py --new` |
| บันทึกทันทีทุกงาน | `append_jsonl()` |

## ปรับค่าที่ config.py
| ค่า | ความหมาย |
|---|---|
| `LISTING_URL` | เปลี่ยน `jobtype`/`subjobtype` เพื่อดึงสายอื่น |
| `MAX_JOBS` | 0 = ไม่จำกัด |
| `HEADLESS` | False = เห็นเบราว์เซอร์ทำงาน (ใช้ตอนสาธิต) |
| `INCREMENTAL` | True = ดึงเฉพาะงานใหม่ |
| `SECTIONS` | เพิ่ม/แก้ชื่อหัวข้อที่ต้องการดึง |
| `EXCLUDE_SECTIONS` | หัวข้อที่ห้ามดึง |

## ทำไมดึงตาม "ชื่อหัวข้อ" ไม่ใช่ CSS class
JobThai ใช้ class สุ่ม (`sc-1k7b98y-12`) ที่เปลี่ยนทุกครั้งที่เว็บอัปเดต
โค้ดนี้ค้นหาจากข้อความหัวข้อ เช่น "สวัสดิการ" แล้วดึงเนื้อหาที่อยู่ในกล่องเดียวกัน
→ เว็บเปลี่ยน class ก็ยังทำงานได้ และเพิ่มหัวข้อใหม่แค่เติมชื่อใน `config.SECTIONS`
