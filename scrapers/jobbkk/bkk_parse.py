# -*- coding: utf-8 -*-
"""
bkk_parse.py — แกะข้อมูลจาก "ข้อความ" ของหน้า JobBKK
ทำงานกับ text ไม่ใช่ CSS class จึงไม่พังเวลาเว็บเปลี่ยนโครงสร้าง
(แนวคิดเดียวกับ JobThai v3)
"""
import re
from typing import Dict, List, Optional

# ---------- หัวข้อที่ต้องการ (ตรงกับที่เว็บใช้จริง) ----------
SECTIONS = {
    "job_description": ["หน้าที่และความรับผิดชอบ"],
    "qualification":   ["คุณสมบัติด้านความรู้และความสามารถ"],
    "welfare":         ["สวัสดิการ"],
    "contact":         ["สนใจสมัครงานตำแหน่งงานนี้กรุณาติดต่อ", "ติดต่อ"],
    "travel":          ["การเดินทาง"],
    "_qual_attrs":     ["คุณสมบัติ"],          # เพศ/อายุ/การศึกษา/ประสบการณ์
}

# ห้ามเก็บ (ตามโจทย์)
EXCLUDE = [
    "เลือกวิธีการสมัครงาน", "วิธีการสมัคร", "สมัครงานด่วน", "แนบไฟล์สมัครงาน",
    "ตำแหน่งงานอื่นๆ ของบริษัทนี้", "ตำแหน่งงานอื่น ๆ ของบริษัทนี้",
    "Tags :", "Tags", "ดูตำแหน่งงานทั้งหมดของบริษัทนี้",
]

# ป้ายข้อมูลแบบ "ชื่อ : ค่า"
LABELS = [
    "สถานที่", "เงินเดือน (บาท)", "สาขาอาชีพหลัก", "สาขาอาชีพรอง", "รูปแบบงาน",
    "จำนวนที่รับ", "วันทำงาน", "วันหยุด", "เวลาทำงาน", "ระดับตำแหน่งงาน",
    "เพศ", "อายุ(ปี)", "ระดับการศึกษา", "ประสบการณ์(ปี)",
    "ชื่อ", "เบอร์โทรศัพท์", "ที่อยู่", "อีเมล",
    "ประเภทธุรกิจ", "วันที่อัปเดต", "จำนวนผู้เข้าชม", "สมัครงานตำแหน่งนี้",
    "การเดินทางเพิ่มเติม",
]
# ป้ายที่ไม่ใช่ข้อมูลงาน (ไม่เก็บลง attributes)
SKIP_LABELS = {"จำนวนผู้เข้าชม", "สมัครงานตำแหน่งนี้"}

_ALL_HEADINGS = [h for v in SECTIONS.values() for h in v] + EXCLUDE


def clean(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\u00a0", " ").replace("\u200b", "")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in s.splitlines()]
    return "\n".join(ln for ln in lines if ln)


_TH_MONTHS = ("ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
              "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.")
_DATE_LABELS = {"วันที่อัปเดต"}


def looks_like_date(s: str) -> bool:
    """เช็กว่าข้อความเป็นวันที่จริง (ไทยย่อ หรือ ISO) — กันเอาชื่อตำแหน่งมาเป็นวันที่"""
    s = (s or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return True
    return bool(re.search(r"\d{1,2}\s*(" + "|".join(re.escape(m) for m in _TH_MONTHS)
                          + r")\s*\d{2,4}", s))


def merge_colon_lines(text: str) -> str:
    """
    HTML จริงของ JobBKK แยก ":" ออกมาเป็นบรรทัดของตัวเอง
        ชื่อ
        :
        คุณพีรณัฐ
    ฟังก์ชันนี้รวมให้เป็น "ชื่อ :" เพื่อให้ parse ต่อได้
    """
    lines = clean(text).splitlines()
    out: List[str] = []
    for ln in lines:
        s_ = ln.strip()
        if s_ in (":", "：") and out:
            out[-1] = out[-1].rstrip() + " :"
        elif s_.startswith((":", "：")) and out and len(s_) > 1:
            out[-1] = out[-1].rstrip() + " :"
            out.append(s_.lstrip(":：").strip())
        else:
            out.append(ln)
    return "\n".join(out)


def parse_labels(text: str) -> Dict[str, str]:
    """
    อ่านค่าแบบ "ป้าย :" ซึ่งบนหน้าเว็บค่าจะอยู่บรรทัดถัดไป
        สถานที่ :
        กรุงเทพมหานคร (เขตห้วยขวาง)
    """
    lines = merge_colon_lines(text).splitlines()
    out: Dict[str, str] = {}
    for i, ln in enumerate(lines):
        m = re.match(r"^(.+?)\s*:\s*(.*)$", ln)
        if not m:
            continue
        label, inline = m.group(1).strip(), m.group(2).strip()
        if label not in LABELS:
            continue
        if inline:                                  # ค่าอยู่บรรทัดเดียวกัน
            value = inline
        elif i + 1 < len(lines):                    # ค่าอยู่บรรทัดถัดไป
            nxt = lines[i + 1].strip()
            if not nxt or nxt.endswith(":") or nxt in _ALL_HEADINGS:
                continue
            value = nxt
        else:
            continue
        # ★ ป้ายวันที่: ถ้าค่าไม่ใช่วันที่ (เช่นได้ชื่อตำแหน่งมาแทน) → ไม่รับ
        if label in _DATE_LABELS and not looks_like_date(value):
            continue
        out.setdefault(label, value)
    return out


def parse_sections(text: str) -> Dict[str, str]:
    """
    ตัดข้อความเป็นก้อนตามหัวข้อ แล้วคืนเฉพาะหัวข้อที่ต้องการ
    หัวข้อต้องห้าม (วิธีการสมัคร / Tags / งานอื่นๆ) จะถูกตัดทิ้งทั้งก้อน
    """
    lines = merge_colon_lines(text).splitlines()
    blocks: Dict[str, List[str]] = {}
    cur: Optional[str] = None

    for ln in lines:
        s = ln.strip().rstrip(":：").strip()
        if s in _ALL_HEADINGS:
            cur = s
            blocks.setdefault(cur, [])
            continue
        if cur:
            blocks[cur].append(ln)

    out: Dict[str, str] = {}
    for field, names in SECTIONS.items():
        for n in names:
            if n in blocks:
                body = "\n".join(blocks[n]).strip()
                body = _strip_labels_tail(body) if field != "_qual_attrs" else body
                if body:
                    out[field] = body
                break
    return out


def _strip_labels_tail(body: str) -> str:
    """ตัดบรรทัดที่เป็นป้ายข้อมูลออกจากเนื้อหา (เช่น 'ชื่อ :' ใน contact เก็บแยกแล้ว)"""
    keep = []
    for ln in body.splitlines():
        s = ln.strip().rstrip(":：").strip()
        if s in EXCLUDE:
            break
        keep.append(ln)
    return "\n".join(keep).strip()


def to_bullets(text: str) -> List[str]:
    """แตกเป็นรายการ bullet (ตัดสัญลักษณ์/เลขหัวข้อนำหน้า)"""
    pat = re.compile(r"^\s*(?:[-•·*▪◦–—]+|\d+(?:\.\d+)+|\d+[.)]|\(\d+\))\s*")
    out = []
    for ln in clean(text).splitlines():
        t = pat.sub("", ln).strip()
        if t and t not in ("-", "ไม่มี", "ไม่ระบุ"):
            out.append(t)
    return out


def format_pairs(text: str) -> str:
    """
    รวม "ป้าย :" กับค่าที่อยู่บรรทัดถัดไป ให้เป็นบรรทัดเดียว
        ชื่อ :            ->   ชื่อ: คุณพีรณัฐ
        คุณพีรณัฐ
    """
    lines = merge_colon_lines(text).splitlines()
    out, i = [], 0
    while i < len(lines):
        ln = lines[i].strip()
        if ln.endswith(":") and i + 1 < len(lines):
            val = lines[i + 1].strip()
            if val and not val.endswith(":"):
                out.append(f"{ln[:-1].strip()}: {val}")
                i += 2
                continue
        if ln and ln not in (":", "："):
            out.append(ln)
        i += 1
    return "\n".join(out).strip()


def clean_travel(text: str) -> str:
    """ตัดบรรทัด 'ไม่มี' / '-' ที่เว็บใส่ไว้เป็น placeholder ของรถไฟฟ้าแต่ละสาย"""
    keep = []
    for ln in format_pairs(text).splitlines():
        s_ = ln.strip()
        if s_ in ("-", ":", "ไม่มี", "ไม่ระบุ"):
            continue
        # "การเดินทางเพิ่มเติม: ไม่ระบุ" = ไม่มีข้อมูล
        if s_.startswith("การเดินทางเพิ่มเติม"):
            val = s_.split(":", 1)[-1].strip()
            if val in ("", "-", "ไม่ระบุ", "ไม่มี"):
                continue
        keep.append(s_)
    return "\n".join(keep).strip()