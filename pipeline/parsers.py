# -*- coding: utf-8 -*-
"""
parsers.py — แปลงข้อความดิบเป็นค่าที่ใช้วิเคราะห์ได้
ทุกฟังก์ชันต้องทนข้อมูลสกปรก: คืน None แทนที่จะ raise
"""
import re
from datetime import date, datetime
from typing import Optional, Tuple

# ---------- เงินเดือน ----------
SALARY_NEGOTIABLE = ("ตามตกลง", "ตามประสบการณ์", "ตามโครงสร้าง", "ตามความสามารถ",
                     "ตามข้อตกลง", "พิจารณาตามความสามารถ", "negotiable")
SALARY_UNSPEC = ("ไม่ระบุ", "-", "")

# หน่วยเวลาของค่าจ้าง -> ตัวคูณเป็น "ต่อเดือน"
#   รายวัน 26 วันทำงาน/เดือน, รายชั่วโมง 8 ชม. x 26 วัน (ตามแนวปฏิบัติค่าจ้างแรงงานไทย)
DAYS_PER_MONTH = 26
HOURS_PER_MONTH = 8 * DAYS_PER_MONTH
_PERIOD = [
    ("hour", re.compile(r"ชั่วโมงละ|ต่อ\s*ชั่วโมง|/\s*ชม|/\s*ชั่วโมง|รายชั่วโมง|per\s*hour|/\s*hr|hourly", re.I)),
    ("day",  re.compile(r"วันละ|ต่อ\s*วัน|/\s*วัน|รายวัน|แรงละ|per\s*day|/\s*day|daily", re.I)),
    ("year", re.compile(r"ต่อ\s*ปี|/\s*ปี|ปีละ|per\s*(year|annum)|/\s*year|annual", re.I)),
]
_FACTOR = {"hour": HOURS_PER_MONTH, "day": DAYS_PER_MONTH, "year": 1 / 12, "month": 1}
# ช่วงค่าที่สมเหตุสมผลของแต่ละหน่วย (กันตัวเลขที่ไม่ใช่ค่าจ้าง เช่น "ปี 2", "อายุ 25")
_RANGE = {"hour": (30, 2000), "day": (150, 5000), "month": (1000, 2_000_000),
          "year": (50_000, 20_000_000)}


def parse_salary_period(raw: Optional[str]) -> str:
    """ "วันละ 400 บาท" -> 'day' | "60 บาท/ชม." -> 'hour' | อื่น ๆ -> 'month' """
    s = raw or ""
    for name, pat in _PERIOD:
        if pat.search(s):
            return name
    return "month"


def parse_salary(raw: Optional[str]) -> Tuple[str, Optional[float], Optional[float]]:
    """
    คืนค่าเป็น "บาทต่อเดือน" เสมอ เพื่อให้เทียบกันได้ทุกประกาศ (หน่วยเดิมดูได้จาก parse_salary_period)
    "17,000 - 25,000 บาท" -> ('range', 17000, 25000)
    "4,000 บาท"           -> ('fixed', 4000, 4000)
    "วันละ 400 บาท"        -> ('fixed', 10400, 10400)       400 x 26 วัน
    "ค่าแรง 400-500/วัน"   -> ('range', 10400, 13000)
    "60 บาท/ชม."           -> ('fixed', 12480, 12480)       60 x 8 x 26
    "ตามประสบการณ์"        -> ('negotiable', None, None)
    "ไม่ระบุ" / ""         -> ('unspecified', None, None)
    """
    if not raw:
        return ("unspecified", None, None)
    s = raw.strip()
    if s in SALARY_UNSPEC:
        return ("unspecified", None, None)
    if any(k in s for k in SALARY_NEGOTIABLE):
        return ("negotiable", None, None)

    period = parse_salary_period(s)
    lo_ok, hi_ok = _RANGE[period]
    nums = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", s)]
    # "15k" / "15K" -> 15000
    if re.search(r"\d\s*[kK]\b", s):
        nums = [n * 1000 if n < 1000 else n for n in nums]
    nums = [n for n in nums if lo_ok <= n <= hi_ok]
    if not nums:
        return ("negotiable" if s else "unspecified", None, None)
    f = _FACTOR[period]
    if len(nums) == 1:
        v = round(nums[0] * f, 2)
        return ("fixed", v, v)
    lo, hi = min(nums[:2]), max(nums[:2])
    return ("range", round(lo * f, 2), round(hi * f, 2))


# ---------- วันที่ ----------
TH_MONTHS = {"ม.ค.": 1, "ก.พ.": 2, "มี.ค.": 3, "เม.ย.": 4, "พ.ค.": 5, "มิ.ย.": 6,
             "ก.ค.": 7, "ส.ค.": 8, "ก.ย.": 9, "ต.ค.": 10, "พ.ย.": 11, "ธ.ค.": 12}


def parse_date(raw: Optional[str]) -> Optional[date]:
    """
    JobThai: "13 ก.ย. 69"  (พ.ศ. 2 หลัก) -> date(2026, 9, 13)
    JobBKK : "2026-09-09T17:35:34+07:00" -> date(2026, 9, 9)
    """
    if not raw:
        return None
    s = raw.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        except ValueError:
            return None
    months = "|".join(re.escape(m) for m in sorted(TH_MONTHS, key=len, reverse=True))
    m = re.search(rf"(\d{{1,2}})\s*({months})\s*(\d{{2,4}})", s)
    if not m:
        return None
    day, mon_th, year = int(m.group(1)), m.group(2), int(m.group(3))
    month = TH_MONTHS[mon_th]
    if year < 100:
        year += 2500
    if year > 2400:
        year -= 543
    try:
        return date(year, month, day)
    except ValueError:
        return None


# ---------- จำนวนอัตรา ----------
def parse_positions(raw: Optional[str]) -> Optional[int]:
    """ "3 อัตรา" / "4 ตำแหน่ง" -> 3 / 4  |  "ไม่ระบุ" -> None """
    if not raw:
        return None
    m = re.search(r"\d+", str(raw).replace(",", ""))
    if not m:
        return None
    n = int(m.group())
    return n if 0 < n < 10000 else None


# ---------- ประสบการณ์ ----------
def parse_experience(raw: Optional[str]) -> Optional[int]:
    """ "0 ปีขึั้นไป" -> 0 | "1 ปีขึ้นไป" -> 1 | "ไม่มีประสบการณ์" -> 0 """
    if not raw:
        return None
    s = str(raw)
    if "ไม่มีประสบการณ์" in s or "ไม่ระบุ" in s:
        return 0 if "ไม่มี" in s else None
    m = re.search(r"\d+", s)
    return int(m.group()) if m else None


# ---------- สถานที่ ----------
PROVINCES = [
    "กรุงเทพมหานคร", "กระบี่", "กาญจนบุรี", "กาฬสินธุ์", "กำแพงเพชร", "ขอนแก่น",
    "จันทบุรี", "ฉะเชิงเทรา", "ชลบุรี", "ชัยนาท", "ชัยภูมิ", "ชุมพร", "เชียงราย",
    "เชียงใหม่", "ตรัง", "ตราด", "ตาก", "นครนายก", "นครปฐม", "นครพนม",
    "นครราชสีมา", "นครศรีธรรมราช", "นครสวรรค์", "นนทบุรี", "นราธิวาส", "น่าน",
    "บึงกาฬ", "บุรีรัมย์", "ปทุมธานี", "ประจวบคีรีขันธ์", "ปราจีนบุรี", "ปัตตานี",
    "พระนครศรีอยุธยา", "พังงา", "พัทลุง", "พิจิตร", "พิษณุโลก", "เพชรบุรี",
    "เพชรบูรณ์", "แพร่", "พะเยา", "ภูเก็ต", "มหาสารคาม", "มุกดาหาร", "แม่ฮ่องสอน",
    "ยโสธร", "ยะลา", "ร้อยเอ็ด", "ระนอง", "ระยอง", "ราชบุรี", "ลพบุรี", "ลำปาง",
    "ลำพูน", "เลย", "ศรีสะเกษ", "สกลนคร", "สงขลา", "สตูล", "สมุทรปราการ",
    "สมุทรสงคราม", "สมุทรสาคร", "สระแก้ว", "สระบุรี", "สิงห์บุรี", "สุโขทัย",
    "สุพรรณบุรี", "สุราษฎร์ธานี", "สุรินทร์", "หนองคาย", "หนองบัวลำภู",
    "อ่างทอง", "อำนาจเจริญ", "อุดรธานี", "อุตรดิตถ์", "อุทัยธานี", "อุบลราชธานี",
]
PROVINCE_ALIAS = {
    "กรุงเทพฯ": "กรุงเทพมหานคร", "กทม.": "กรุงเทพมหานคร", "กทม": "กรุงเทพมหานคร",
    "กรุงเทพ": "กรุงเทพมหานคร", "อยุธยา": "พระนครศรีอยุธยา",
    "ศรีษะเกษ": "ศรีสะเกษ", "บุรีรัมย": "บุรีรัมย์",
}
_PROV_SORTED = sorted(PROVINCES, key=len, reverse=True)


def parse_location(raw: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not raw:
        return (None, None)
    s = raw.strip()
    if re.match(r"^(MRT|BTS|BRT|SRT|ARL)\b", s, re.I):
        return (None, None)
    province = None
    for alias, official in PROVINCE_ALIAS.items():
        if alias in s:
            province = official
            break
    if not province:
        for p in _PROV_SORTED:
            if p in s:
                province = p
                break
    district = None
    m = re.search(r"(?:^|\s)(?:อ\.|อำเภอ|เขต)\s*([^\s()]+)", s)
    if m:
        district = m.group(1)
    else:
        m = re.search(r"\(\s*(?:เขต|อำเภอ|อ\.)?\s*([^)]+?)\s*\)", s)
        if m:
            district = m.group(1).strip()
    if district:
        district = re.sub(r"^(เขต|อำเภอ|อ\.)\s*", "", district).strip(" .,-") or None
    if not province:
        m = re.search(r"จ\.\s*(\S+)", s)
        if m:
            province = m.group(1).strip(" .,-") or None
    return (province, district)


# ---------- ชื่อบริษัท ----------
COMPANY_NOISE = [r"^บริษัท\s*", r"^บจก\.?\s*", r"^หจก\.?\s*", r"^ห้างหุ้นส่วน\S*\s*",
                 r"\s*จำกัด\s*", r"\s*\(มหาชน\)\s*", r"\s*co\.?,?\s*ltd\.?\s*$",
                 r"\s*company\s*limited\s*$", r"\s*ltd\.?\s*$", r"\s*inc\.?\s*$"]


def normalize_company(name: Optional[str]) -> Optional[str]:
    if not name or not name.strip():
        return None
    s = name.strip().lower()
    for pat in COMPANY_NOISE:
        s = re.sub(pat, " ", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" -–—.,")
    return s or None
