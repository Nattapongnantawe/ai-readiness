# -*- coding: utf-8 -*-
"""
freshness.py — ตรวจ "งานที่ถูกอัปเดต" + ส่งรายการสดให้หน้าเว็บ (ใช้ไฟล์เดียวกันทั้ง JobThai และ JobBKK)

ปัญหาเดิม: โหมด --new ข้ามงานที่เคยเก็บโดยไม่เปิดดู ถ้าบริษัทแก้เงินเดือน/คุณสมบัติ เราจะไม่รู้
วิธีใหม่:   อ่าน "วันที่" บนการ์ดในหน้ารายการ (ไม่ต้องเปิดหน้าเพิ่ม) แล้วเทียบกับวันที่ที่เคยเก็บ
            การ์ดใหม่กว่า -> เปิดหน้ารายละเอียดใหม่ -> เทียบเนื้อหา
              เนื้อหาเปลี่ยน  = "อัปเดต"   (บอกด้วยว่าช่องไหนเปลี่ยน)
              เนื้อหาเดิม    = "ดันประกาศ" (บริษัทกดเลื่อนประกาศขึ้นเฉยๆ)
            วันที่ที่เห็นบนการ์ดถูกจำไว้ใน output/listing_dates.json จึงไม่เปิดงานเดิมซ้ำทุกรอบ

ตัวเลือก (ผ่าน polite.apply_cli):
  --max-updates N   เปิดงานที่ถูกอัปเดตได้สูงสุด N งานต่อรอบ (ค่าเริ่มต้น 50) ที่เหลือทำรอบถัดไป
  --cards           ตรวจอย่างเดียว: แสดงวันที่บนการ์ดหน้าแรกเทียบกับที่เก็บไว้ แล้วจบ (ไม่ดึงอะไร)

บรรทัด "@@FEED {...}" ที่พิมพ์ออกไปคือรายการสดสำหรับหน้า Crawler ของระบบ (Module 4)
"""
import json
import os
import re
from datetime import date, datetime, timedelta
from typing import Optional

import config

MAX_UPDATES_DEFAULT = 50
DATES_FILE = "listing_dates.json"

_TH_MONTHS = {
    "ม.ค.": 1, "มกราคม": 1, "ก.พ.": 2, "กุมภาพันธ์": 2, "มี.ค.": 3, "มีนาคม": 3,
    "เม.ย.": 4, "เมษายน": 4, "พ.ค.": 5, "พฤษภาคม": 5, "มิ.ย.": 6, "มิถุนายน": 6,
    "ก.ค.": 7, "กรกฎาคม": 7, "ส.ค.": 8, "สิงหาคม": 8, "ก.ย.": 9, "กันยายน": 9,
    "ต.ค.": 10, "ตุลาคม": 10, "พ.ย.": 11, "พฤศจิกายน": 11, "ธ.ค.": 12, "ธันวาคม": 12,
}
_EN_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MONTH_RE = "|".join(sorted((re.escape(k) for k in _TH_MONTHS), key=len, reverse=True))

_PATTERNS = [
    ("thai", re.compile(rf"(\d{{1,2}})\s*({_MONTH_RE})\s*(\d{{2,4}})")),
    ("iso", re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")),
    ("dmy", re.compile(r"(?<!\d)(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})(?!\d)")),
    ("en", re.compile(r"(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{2,4})", re.I)),
    ("rel", re.compile(r"(วันนี้|เมื่อวาน|today|yesterday|(\d+)\s*(นาที|ชั่วโมง|ชม\.|วัน)\s*(?:ที่แล้ว|ก่อน))", re.I)),
]


def _year(y: int) -> int:
    if y < 100:                  # 69 -> 2569 (พ.ศ.) ; 26 -> 2026
        y = y + 2500 if y >= 40 else y + 2000
    return y - 543 if y > 2400 else y


def parse_date(text) -> Optional[date]:
    """อ่านวันที่แรกที่เจอในข้อความ รองรับ '18 ก.ย. 69', '2026-09-18', '18/09/2569', 'วันนี้', '3 วันที่แล้ว'"""
    if not text:
        return None
    s = str(text)
    today = date.today()
    for kind, rx in _PATTERNS:
        m = rx.search(s)
        if not m:
            continue
        try:
            if kind == "thai":
                return date(_year(int(m.group(3))), _TH_MONTHS[m.group(2)], int(m.group(1)))
            if kind == "iso":
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if kind == "dmy":
                return date(_year(int(m.group(3))), int(m.group(2)), int(m.group(1)))
            if kind == "en":
                return date(_year(int(m.group(3))), _EN_MONTHS[m.group(2).lower()[:3]], int(m.group(1)))
            w = m.group(1).lower()
            if w in ("วันนี้", "today"):
                return today
            if w in ("เมื่อวาน", "yesterday"):
                return today - timedelta(days=1)
            n, unit = int(m.group(2)), m.group(3)
            return today - timedelta(days=n) if unit == "วัน" else today
        except (ValueError, KeyError):
            continue
    return None


# ---------------------------------------------------------------- จำวันที่บนการ์ด
def _dates_path() -> str:
    return os.path.join(getattr(config, "DATA_DIR", "output"), DATES_FILE)


def load_dates() -> dict:
    try:
        with open(_dates_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_dates(d: dict) -> None:
    os.makedirs(os.path.dirname(_dates_path()) or ".", exist_ok=True)
    tmp = _dates_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, _dates_path())


def remember(d: dict, h: str, card_date) -> None:
    """จำวันที่บนการ์ดของงานนี้ แล้วเขียนไฟล์ทันที (รอบถูกหยุดกลางทางก็ไม่ต้องเปิดงานนี้ซ้ำ)"""
    d[h] = str(card_date)
    try:
        save_dates(d)
    except OSError:
        pass          # เขียนไม่ได้ชั่วคราว: จะเขียนอีกครั้งตอนจบรอบ


def _get(job, key: str, default=""):
    return job.get(key, default) if isinstance(job, dict) else getattr(job, key, default)


def is_updated(card_date: Optional[date], stored_job, remembered: Optional[str]) -> bool:
    """การ์ดใหม่กว่าวันที่ที่เคยเก็บ (ทั้งวันที่ในประกาศ และวันที่บนการ์ดที่เคยเห็น) หรือไม่"""
    if not card_date:
        return False
    known = [d for d in (parse_date(_get(stored_job, "post_date")), parse_date(remembered)) if d]
    return bool(known) and card_date > max(known)


# ---------------------------------------------------------------- เทียบเนื้อหา
FIELDS = [
    ("job_title", "ชื่อตำแหน่ง"), ("company_name", "บริษัท"), ("salary", "เงินเดือน"),
    ("num_positions", "จำนวนที่รับ"), ("location", "สถานที่"),
    ("job_description", "รายละเอียดงาน"), ("qualification", "คุณสมบัติ"), ("welfare", "สวัสดิการ"),
]


def _norm(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def changed_fields(old, new) -> list:
    """ชื่อช่องที่เนื้อหาเปลี่ยน (ไม่นับช่องว่าง/ขึ้นบรรทัด)"""
    return [label for key, label in FIELDS if _norm(_get(old, key)) != _norm(_get(new, key))]


# ---------------------------------------------------------------- รายการสดให้หน้าเว็บ
def feed(kind: str, job=None, url: str = "", **extra) -> None:
    """kind: new / updated / bumped / partial / failed"""
    rec = {"kind": kind, "url": url or _get(job, "source_url"),
           "title": _get(job, "job_title")[:120] if job is not None else "",
           "company": _get(job, "company_name")[:120] if job is not None else "",
           "salary": _get(job, "salary")[:60] if job is not None else "",
           "location": _get(job, "location")[:80] if job is not None else "",
           "post_date": _get(job, "post_date")[:40] if job is not None else "",
           "at": datetime.now().strftime("%H:%M:%S"), **extra}
    print("@@FEED " + json.dumps(rec, ensure_ascii=False), flush=True)


def max_updates() -> int:
    return int(getattr(config, "MAX_UPDATES", MAX_UPDATES_DEFAULT))


def show_cards(cards: list, done: dict, url_hash) -> None:
    """--cards: ตรวจว่าการ์ดหน้าแรกมีวันที่ไหม และระบบจะถือว่างานไหนอัปเดต"""
    remembered = load_dates()
    print(f"\nการ์ดหน้าแรก {len(cards)} ใบ\n")
    found = 0
    for i, c in enumerate(cards, 1):
        h = url_hash(c["url"])
        cd = parse_date(c.get("text"))
        found += bool(cd)
        old = done.get(h)
        if old is None:
            state = "ใหม่ (ยังไม่เคยเก็บ)"
        elif is_updated(cd, old, remembered.get(h)):
            state = f"อัปเดต (เคยเก็บวันที่ {_get(old, 'post_date') or '-'})"
        else:
            state = f"เดิม (เคยเก็บวันที่ {_get(old, 'post_date') or '-'})"
        snippet = re.sub(r"\s+", " ", c.get("text") or "")[:70]
        print(f"[{i:2}] วันที่บนการ์ด: {cd or '✗ ไม่พบ'} | {state}")
        print(f"     {snippet}")
    print(f"\nการ์ดที่อ่านวันที่ได้ {found}/{len(cards)}")
    if not found:
        print("⚠️ การ์ดไม่มีวันที่ — ระบบจะตรวจงานที่ถูกอัปเดตไม่ได้ (ส่งผลนี้ให้ผู้พัฒนาดู)")