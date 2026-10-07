# -*- coding: utf-8 -*-
"""config.py — ตั้งค่า JobBKK scraper (แก้ที่นี่ที่เดียว)"""

# ========================= ปรับได้บ่อย =========================
# หน้ารายการ: เลข /lists/1/ คือหน้าที่ — โค้ดจะเปลี่ยนให้เอง
# ช่องที่ 2 ของ path คือ "คำค้นหา" ใส่ ทั้งหมด = ไม่กรองด้วยคำค้น
# ช่องที่ 2 ของ path คือ "คำค้นหา" (ก็อป URL จากหน้าค้นหาของ JobBKK มาวางได้เลย)
# ช่องที่ 2 ของ path คือ "คำค้นหา" (ก็อป URL จากหน้าค้นหาของ JobBKK มาวางได้เลย)
# ปัจจุบัน: ไอที ทั้งหมด + วิศวกรรม/วิศวกรคอมพิวเตอร์  (occupation=25,21-176)
LISTING_URL = ("https://www.jobbkk.com/jobs/lists/1/"
               "หางาน,ทั้งหมด,ทุกจังหวัด,ทั้งหมด.html"
               "?lang_id=1&occupation=25,21-176,21-167,32-268")

MAX_JOBS = 0          # 0 = ไม่จำกัด  (ตอนนี้ตั้ง 3 ไว้ทดสอบ)
HEADLESS = True       # True = ไม่เปิดหน้าต่างเบราว์เซอร์ (False ไว้ debug)
SAVE_EVERY = 10

INCREMENTAL = False   # True = เจองานเดิมติดกันครบแล้วหยุด
STOP_AFTER_KNOWN = 40
MAX_EMPTY_PAGES = 2

# ---------- ตัวหยุดเมื่อเลยหน้าสุดท้าย ----------
# JobBKK พอขอหน้าที่เกินจำนวนจริง ไม่ตอบหน้าว่าง แต่ส่ง "งานแนะนำชุดเดิม" กลับมา
# ถ้าไม่มีตัวหยุดพวกนี้ scraper จะวนไม่รู้จบ (เคยวนถึงหน้า 1,059 ทั้งที่มีจริง ~47 หน้า)
STOP_AFTER_DUP_PAGES = 3     # เจอหน้าที่ "ไม่มีงานใหม่เลย" ติดกันกี่หน้า = หยุด
STOP_WHEN_NO_RESULTS = True  # หาคำว่า "ผลการค้นหาพบ" ไม่เจอ = เลยผลค้นหาแล้ว หยุด
PAGE_LIMIT_MARGIN = 2        # อนุญาตเกินหน้าที่คำนวณได้กี่หน้า (เผื่องานใหม่เข้าระหว่างรัน)

# ---------- ขอบเขตสายงาน (ด่านสุดท้ายก่อนบันทึก) ----------
# ตรวจ "สาขาอาชีพ" ของแต่ละงานจากหน้ารายละเอียด ถ้าไม่ตรงขอบเขต → ไม่บันทึก
# กันงานแนะนำ/งานนอกสายหลุดเข้ามา (เคยหลุดมา ~1,200 งานตอนที่ pagination วน)
#   key   = สาขาอาชีพหลัก
#   value = None       → รับทุกสาขารอง
#           [...]      → รับเฉพาะสาขารองที่ระบุ
# ตั้ง SCOPE = {} ถ้าไม่ต้องการกรอง
SCOPE = {
    "ไอที": None,
    "วิศวกรรม": ["วิศวกรคอมพิวเตอร์", "วิศวกรไฟฟ้า/วิศวกรอิเล็กทรอนิกส์"],
    "ช่าง/ช่างเทคนิค/อิเลคโทรนิค": ["ช่างไฟฟ้า/อิเลคโทรนิค/คอมพิวเตอร์/สื่อสาร"],
}
KEEP_UNKNOWN_SCOPE = False   # งานที่อ่านสาขาไม่ได้ (?) — False = ไม่บันทึก แต่จดไว้ให้ตรวจ

FETCH_COMPANY_PROFILE = True   # ดึง "ข้อมูลบริษัท" จากหน้าโปรไฟล์ (cache ต่อบริษัท)
# ==============================================================

DATA_DIR = "output"
JSONL_PATH = "output/jobs.jsonl"
JSON_PATH = "output/jobs_data.json"
FAILED_PATH = "output/failed.jsonl"
OUT_OF_SCOPE_PATH = "output/out_of_scope.jsonl"   # งานนอกสายที่ถูกตัดทิ้ง (ไว้ตรวจ)
COMPANY_CACHE = "output/company_cache.json"

BASE = "https://www.jobbkk.com"
PAGE_TIMEOUT = 30000      # Playwright (ms)
WAIT_TIMEOUT = 15000
HTTP_TIMEOUT = 25         # requests (วินาที)

# ---------- Ethical scraping ----------
MIN_DELAY = 3.0
MAX_DELAY = 7.0
MAX_RETRIES = 3
COOLDOWN_429 = 60
BACKOFF_BASE = 10

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Upgrade-Insecure-Requests": "1",
}

# ---------- Selector หน้ารายการ ----------
# ผลค้นหาของ JobBKK เรนเดอร์ด้วย JS จึงต้องใช้ Playwright เปิดหน้ารายการ
JOB_LINK = 'a[href*="/jobs/detail"]'   # ลิงก์งาน: /jobs/detail[urgent]/{companyId}/{jobId}

# ---------- ขอบเขต "ผลการค้นหา" ----------
# หน้ารายการมีเมนู/บล็อกงานแนะนำ/footer ปนอยู่ จึงเก็บเฉพาะลิงก์ที่อยู่
# ระหว่าง RESULT_START กับ RESULT_END
#
# ⚠️ สำคัญ: ต้องนับเฉพาะ element ที่ "มองเห็นได้จริง" เท่านั้น
#    เพราะ JobBKK มีคำว่า "ตำแหน่งงานแนะนำ" ซ่อนอยู่ใน DOM ก่อนการ์ดงาน
#    ถ้าไม่กรองความมองเห็น จะตัดงานทิ้งหมด (โค้ดใน scraper.py ทำให้แล้ว)
RESULT_START = ["ผลการค้นหาพบ", "ผลการค้นหางานด่วนทั้งหมด"]
RESULT_END = [
    "ตำแหน่งงานแนะนำ", "ตำแหน่งงานอื่นๆ", "ตำแหน่งงานอื่น ๆ",
    "Job Recommend", "งานที่คุณอาจสนใจ",
    "หางานตามสาขาอาชีพ", "หางานตามพื้นที่", "สำหรับผู้หางาน", "เกี่ยวกับเรา",
]

# ลิงก์โฆษณา/แบนเนอร์ที่ไม่ใช่การ์ดงาน — ตัดออก
# (เทียบกับ href ที่ตัด query แล้ว เพื่อไม่ให้ไปตัดงานจริงที่มี ?utm_source=...)
AD_URL_PARTS = ["/ads/", "/banner", "/promotion", "/campaign", "adsense"]

# ---------- หน้าข้อมูลบริษัท ----------
# หน้ารายละเอียดงานไม่มี "ข้อมูลบริษัท" ต้องดึงจากหน้าโปรไฟล์แยก
# โครงสร้าง:  ข้อมูลบริษัท / (Company Information) / <ย่อหน้า> / สินค้าและบริการ ...
COMPANY_PROFILE_URL = "{base}/company/corporate/{cid}?tab=info"
COMPANY_DESC_START = ["ข้อมูลบริษัท", "Company Information"]
COMPANY_DESC_END = [
    "สินค้าและบริการ", "Product and Service", "สวัสดิการ", "Benefits",
    "ติดต่อเรา", "การเดินทาง", "แผนที่ออนไลน์", "พร้อมร่วมงานกับเราหรือยัง",
    "สถิติการ View Jobs", "ดูตำแหน่งงานเลย",
]