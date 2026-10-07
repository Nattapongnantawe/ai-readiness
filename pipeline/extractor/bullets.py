# -*- coding: utf-8 -*-
"""
จัดการ bullet ก่อนเข้า DB/LLM (ใช้ได้ทั้ง Module 1 loader และ Module 2) — ไม่พึ่ง config/LLM
  - ตัดบรรทัดหัวข้อ + noise (C3)
  - รวมบรรทัดต่อเนื่อง / รายการย่อยใต้ ":" (C5)
  - อ่านจำนวนปีประสบการณ์จากประโยคไทย/อังกฤษ (C7)
"""
import re

HEADER = re.compile(
    r"^(หน้าที่(ความรับผิดชอบ)?|ความรับผิดชอบ|รายละเอียด(งาน)?|ลักษณะ(งาน|การทำงาน)|คุณสมบัติ(ผู้สมัคร)?"
    r"|สวัสดิการ|job\s*descriptions?|responsibilit(y|ies)|qualifications?|requirements?"
    r"|duties|key\s*responsibilities|job\s*summary)(?![ก-๙a-z0-9])[^ก-๙a-z0-9]*(\(.*\))?\s*:?$",
    re.I,
)
NOISE = re.compile(
    r"สนใจ(สมัคร|ติดต่อ)?|ส่ง\s*(resume|ประวัติ|ใบสมัคร)|ติดต่อ(สอบถาม|ได้ที่)|โทร\.?\s*[:0-9]"
    r"|e-?mail\s*:|อีเมล|line\s*id|https?://|www\.", re.I)
EMPTY = re.compile(r"^(ไม่ระบุ|ไม่มี|ตามที่ตกลง|-+|n/?a|none|\.+)\s*$", re.I)
MARKER = re.compile(r"^\s*(?:\d{1,2}\s*[.)]|\(\d{1,2}\)|[-•*●▪➢>✓])\s*")
NUMBERED = re.compile(r"^\s*(?:\d{1,2}\s*[.)]|\(\d{1,2}\))")
CONT_START = re.compile(r"^(และ|หรือ|โดย|เช่น|รวมถึง|ซึ่ง|ได้แก่|ตลอดจน|\(|[a-z])")
OPEN_END = re.compile(r"(,|/|และ|หรือ|เช่น|ได้แก่|\()\s*$")
MAX_LEN = 300


def is_header(text: str, title: str = "") -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if t.endswith(":") and len(t) < 40 and not re.search(r"\d", t):
        return HEADER.match(t) is not None or len(t) < 25
    if HEADER.match(t):
        return True
    words = set(t.lower().split())
    return bool(title) and len(t) <= 30 and words <= set(title.lower().split())


def merge_bullets(lines, title: str = "") -> list:
    """แปลงบรรทัดดิบ -> bullet ที่มีความหมายครบ 1 ข้อ"""
    out, under_colon = [], False
    for raw in lines or []:
        t = " ".join(str(raw).split())
        if not t:
            continue
        body = MARKER.sub("", t).strip()
        if not body:
            continue
        if is_header(body, title) and not body.endswith(":") or HEADER.match(body):
            under_colon = False
            continue
        if NOISE.search(body) and len(body) < 150:
            continue
        if EMPTY.match(body):                    # "ไม่ระบุ", "-", "N/A" ไม่ใช่เนื้อหา
            continue
        has_marker = bool(MARKER.match(t))
        prev = out[-1] if out else ""
        short_list = (not has_marker and 0 < len(prev) <= 20 and len(body) <= 20
                      and not re.search(r"\d", body + prev))
        cont = bool(prev) and (
            (under_colon and not NUMBERED.match(t))
            or (not has_marker and (CONT_START.match(body) or OPEN_END.search(prev)))
            or short_list
        )
        if cont and len(prev) + len(body) < MAX_LEN:
            if prev.endswith(":"):
                out[-1] = f"{prev} {body}"
            elif (under_colon or short_list) and not prev.endswith(","):
                out[-1] = f"{prev}, {body}"
            else:
                out[-1] = f"{prev} {body}"
        else:
            out.append(body)
            under_colon = False
        if out[-1].endswith(":"):
            under_colon = True
    return [b.rstrip(":").strip() for b in out if len(b.strip()) > 1]


# ---------- ประสบการณ์ ----------
NO_EXP = re.compile(
    r"ไม่จำกัดประสบการณ์|ไม่(ต้อง)?มีประสบการณ์(ก็)?(ได้|สามารถ|ยินดี)|ไม่ต้องมีประสบการณ์"
    r"|(นักศึกษา|นศ\.?)?จบใหม่|fresh\s*grad|new\s*grad|no\s+experience\s+(is\s+)?required", re.I)
EXP_CTX = re.compile(r"ประสบการณ์|experience|\bexp\b", re.I)
EXP_NUM = re.compile(r"(\d{1,2})\s*(?:(?:-|–|ถึง)\s*\d{1,2}\s*)?\+?\s*(?:ปี|years?|yrs?)", re.I)


def years_from_lines(lines):
    """
    "มีประสบการณ์อย่างน้อย 2 ปี" -> 2 | "ประสบการณ์ 3-5 ปี" -> 3 | "3+ years experience" -> 3
    "ไม่จำกัดประสบการณ์" / "รับนักศึกษาจบใหม่" -> 0 | "อายุ 23-35 ปี" -> ไม่นับ (ไม่มีคำว่าประสบการณ์)
    """
    for t in lines or []:
        t = str(t)
        if not EXP_CTX.search(t) and not NO_EXP.search(t):
            continue
        m = EXP_NUM.search(t)
        if m and EXP_CTX.search(t):
            return int(m.group(1))
        if NO_EXP.search(t):
            return 0
    return None


def seniority_rule(years):
    if years is None:
        return None
    return "entry" if years <= 1 else "mid" if years <= 4 else "senior"