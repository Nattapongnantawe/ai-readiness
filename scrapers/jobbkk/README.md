# JobBKK Scraper v2 — Single-Pass Extraction

ดึงข้อมูลงานจาก JobBKK แบบเดียวกับ JobThai v3 — **จบครบใน 1 รอบต่อ 1 งาน**
ผลลัพธ์เป็น JSON โครงสร้างเดียวกับ JobThai จึงใช้ `pipeline` ตัวเดียวกันได้เลย

## Flow
```
หน้ารายการ (Playwright)  →  หน้ารายละเอียด (requests)  →  ตัดซ้ำ + ตัดหัวข้อต้องห้าม
   ผลค้นหาเรนเดอร์ด้วย JS      หน้านี้ server-rendered         →  บันทึก JSON → งานถัดไป
```

**ทำไมใช้ 2 เทคโนโลยี** — หน้ารายการของ JobBKK โหลดผลค้นหาด้วย JavaScript จึงต้องใช้เบราว์เซอร์
แต่หน้ารายละเอียดเป็น server-rendered ใช้ `requests` ได้ ซึ่งเร็วกว่าและกินแรมน้อยกว่ามาก
(สำคัญเมื่อต้องดึงหลักหมื่นงาน)

## ติดตั้ง
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

## ใช้งาน
```powershell
python main.py                # ดึงงาน (รันซ้ำได้ ไม่ดึงงานเดิม)
python main.py --new          # ดึงเฉพาะงานใหม่
python main.py --check URL    # ตรวจหน้าเดียว (ไม่ต้องเปิดเบราว์เซอร์)
python main.py --retry        # ดึงซ้ำเฉพาะงานที่เคยพลาด
```

## ไฟล์ผลลัพธ์
| ไฟล์ | คืออะไร |
|---|---|
| `output/jobs.jsonl` | 1 งานต่อบรรทัด เขียนทันที — แครชแล้วไม่หาย |
| `output/jobs_data.json` | JSON array สำหรับ pipeline |
| `output/failed.jsonl` | งานที่ดึงไม่สำเร็จ/ไม่ครบ |
| `output/company_cache.json` | คำแนะนำบริษัท (ยิง request แค่ครั้งเดียวต่อบริษัท) |

## ข้อมูลที่เก็บ (เหมือน JobThai v3)
`company_name` `company_logo_url` `company_description` `job_title` `location`
`salary` `num_positions` `post_date` `welfare` `contact` `travel`
`job_description` `qualification` + `*_items` (bullet แยกบรรทัด)

**เพิ่มจาก JobThai:** `attributes` เก็บ ประเภทธุรกิจ / สาขาอาชีพ / รูปแบบงาน /
เพศ / อายุ / ระดับการศึกษา / ประสบการณ์ / วันทำงาน / เวลาทำงาน

## เงื่อนไขตามโจทย์
| เงื่อนไข | ทำที่ไหน |
|---|---|
| ตัดข้อมูลซ้ำระหว่างส่วน | `scraper._drop_dup()` |
| ห้ามดึง "วิธีการสมัคร" / "Tags" / "งานอื่นๆ" | `bkk_parse.EXCLUDE` |
| กันประกาศซ้ำ | `url_hash` (SHA-256) |
| งานใหม่โผล่หน้าแรก | `python main.py --new` |
| บันทึกทันทีทุกงาน | `append_jsonl()` |
| ไม่มีงานหายเงียบ | `failed.jsonl` + สรุปตัวเลขท้ายรอบ |

## จุดที่ต่างจาก JobThai
- **โลโก้**: อ่านจาก `<meta property="og:image">` ตรง ๆ แม่นกว่าการเดาจาก `<img>`
- **คำแนะนำบริษัท**: ไม่มีในหน้ารายละเอียด ต้องดึงจาก `/jobs/profile/{id}`
  → cache ไว้ ยิง request ครั้งเดียวต่อบริษัท (ปิดได้ที่ `FETCH_COMPANY_PROFILE`)

## เปลี่ยนสายงานที่ดึง
แก้ `LISTING_URL` ใน `config.py` — ก็อป URL จากหน้าค้นหาของ JobBKK มาวางได้เลย
เลข `/lists/1/` คือหน้าที่ โค้ดจะเปลี่ยนให้เอง
