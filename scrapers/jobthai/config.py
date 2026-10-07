# -*- coding: utf-8 -*-
"""config.py — ตั้งค่าทั้งหมดของ JobThai scraper (แก้ที่นี่ที่เดียว)"""

# ========================= ปรับได้บ่อย =========================
# หน้ารายการงาน (สายไอที) — เปลี่ยน jobtype/subjobtype เพื่อดึงสายอื่น
#LISTING_URL = "https://www.jobthai.com/th/jobs?jobtype=7&subjobtype=110"
LISTING_URL = "https://www.jobthai.com/th/jobs?jobtype=7&subjobtype=116%2C110&orderBy=UPDATED_AT_DESC"
MAX_JOBS = 0          # ดึงกี่งานแล้วหยุด (0 = ไม่จำกัด)
HEADLESS = True       # False = เห็นเบราว์เซอร์ทำงาน (ใช้ตอนสาธิต/debug)
SAVE_EVERY = 10       # เขียนไฟล์ .json ทุกกี่งาน (.jsonl เขียนทุกงานอยู่แล้ว)

# --- โหมดดึงเฉพาะงานใหม่ ---
INCREMENTAL = False   # True = เจองานเดิมติดกันครบ STOP_AFTER_KNOWN แล้วหยุด
STOP_AFTER_KNOWN = 40

MAX_EMPTY_PAGES = 2   # เจอหน้าที่ไม่มีงานติดกันกี่หน้า = ถือว่าหมด
RETRY_FAILED = True   # จบรอบแล้ววนกลับไปลองงานที่ดึงไม่สำเร็จอีกครั้ง
# ==============================================================

# ---------- ไฟล์ผลลัพธ์ ----------
DATA_DIR = "output"
JSONL_PATH = "output/jobs.jsonl"       # เขียนต่อท้ายทีละงาน (กันข้อมูลหายถ้าแครช)
JSON_PATH = "output/jobs_data.json"    # ไฟล์ JSON array สำหรับส่งงาน/เข้า pipeline
FAILED_PATH = "output/failed.jsonl"    # งานที่ดึงไม่สำเร็จ/ได้ไม่ครบ (ไว้ตามเก็บทีหลัง)
SEEN_PATH = "output/seen_urls.json"    # ทะเบียนลิงก์ที่ "เคยเห็น" ทุกตัว + สถานะ
                                        # ใช้พิสูจน์ว่าไม่มีงานหายระหว่างทาง

# ---------- ค่าคงที่ ----------
BASE_DOMAIN = "https://www.jobthai.com"
PAGE_TIMEOUT = 30000
WAIT_TIMEOUT = 10000

# ---------- Ethical scraping ----------
MIN_DELAY = 3.0
MAX_DELAY = 7.0
MAX_RETRIES = 3
COOLDOWN_429 = 60
BACKOFF_BASE = 10

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
DEFAULT_HEADERS = {
    "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,image/apng,*/*;q=0.8"),
    "Upgrade-Insecure-Requests": "1",
}

# ---------- Selector ที่ยืนยันจาก HTML จริง ----------
SEL = {
    "job_card": 'a[ga-name="job_list_job"]',   # การ์ดงานในหน้ารายการ
    "detail_button": 'a[id^="job-detail-"]',   # ปุ่มส้ม "ดูรายละเอียดงาน" (เป็น <a href>)
    "job_title": 'h1, [id^="job-card-item-"], [id^="job-title"]',
    "positions": "#job-number-of-position",
    "post_date": "#job-update-at",
    "salary": "#salary-text",
    "work_location_id": '[id^="work-location-"]',   # สถานที่ปฏิบัติงาน (id นิ่ง)
}

# ---------- โลโก้บริษัท ----------
# หน้าเว็บมีทั้งรูปโลโก้ (_logo_) และรูปปก/แบนเนอร์ (_pic_) ที่ URL คล้ายกันมาก
# จึงให้คะแนนเลือกรูป แทนการเดา selector
LOGO_PREFER = ["_logo_", "logo-pic-map"]   # ยิ่งตรงยิ่งได้คะแนนสูง
LOGO_REJECT = ["_pic_", "banner", "cover", "_map_", "/static/", ".svg"]

# ---------- หัวข้อที่ต้องการ (ค้นจากข้อความ ไม่ใช่ class) ----------
SECTIONS = {
    "company_description": ["รายละเอียดบริษัท", "ข้อมูลบริษัท", "เกี่ยวกับบริษัท", "แนะนำบริษัท"],
    "job_description":     ["รายละเอียดงาน", "ลักษณะงาน", "หน้าที่และความรับผิดชอบ"],
    "qualification":       ["คุณสมบัติผู้สมัคร", "คุณสมบัติ"],
    "welfare":             ["สวัสดิการ"],
    "contact":             ["ติดต่อ", "ข้อมูลติดต่อ"],
    "work_location":       ["สถานที่ปฏิบัติงาน", "สถานที่ทำงาน"],
    "travel":              ["วิธีการเดินทาง", "การเดินทาง"],
}

# ---------- ป้ายที่ใช้เป็น "จุดตัด" ท้ายหัวข้อ ----------
# หน้าเว็บวางข้อมูลเป็นรายการติดกัน เช่น
#   สถานที่ปฏิบัติงาน / MRT พระราม 9 / เงินเดือน / 28,000-30,000 / อัตรา / 1
# ถ้าไม่ตัด เนื้อหาหัวข้อหนึ่งจะลากไปถึงหัวข้อถัดไป
STOP_LABELS = [
    "เงินเดือน", "อัตรา", "สถานที่ปฏิบัติงาน", "สถานที่ทำงาน", "วันที่ประกาศ",
    "ประเภทงาน", "รูปแบบงาน", "ระดับการศึกษา", "ประสบการณ์", "เพศ", "อายุ",
    "สวัสดิการ", "ติดต่อ", "วิธีการเดินทาง", "คุณสมบัติผู้สมัคร", "รายละเอียดงาน",
    "แผนที่ออนไลน์", "แผนที่ภาพ", "ใช้งานแผนที่",
    "ดูรายละเอียดบริษัท", "ดูรายละเอียดงาน", "ดูข้อมูลสวัสดิการทั้งหมด",
    "สนใจ", "พิมพ์", "แชร์", "สมัครงาน", "สมัครด่วน", "ส่งไฟล์ประวัติ",
]

# ---------- ห้ามดึงเด็ดขาด (ตามโจทย์) ----------
EXCLUDE_SECTIONS = [
    "วิธีการสมัคร", "วิธีการสมัครงาน", "เลือกวิธีการสมัครงาน",
    "Tags", "แท็ก", "งานอื่น ๆ ของบริษัทนี้", "งานอื่นๆ ของบริษัทนี้",
]