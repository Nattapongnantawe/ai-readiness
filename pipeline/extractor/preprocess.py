# -*- coding: utf-8 -*-
"""ทำความสะอาดข้อความไทย/อังกฤษ ก่อนส่ง LLM (PyThaiNLP + Regex)"""
import html
import re
import unicodedata

try:
    from pythainlp.util import normalize as th_normalize
except ImportError:
    th_normalize = None

from .bullets import is_header, seniority_rule, years_from_lines  # noqa: F401  (re-export)
from .config import MAX_ITEM_CHARS

_BULLET = re.compile(r"^\s*(?:\d{1,2}\s*[.)]|[-•*●▪➢>✓]|\(\d{1,2}\))\s*")
_SPACES = re.compile(r"\s+")


# ---------- ซ่อมข้อความไทยที่สระ/วรรณยุกต์สลับตำแหน่ง (มักเกิดจาก copy จาก PDF) ----------
_LEAD = "เแโใไ"                       # สระหน้า
_ABOVE = "\u0e31\u0e34-\u0e37\u0e47-\u0e4e"   # สระบน/ล่าง/วรรณยุกต์ (ั ิ ี ึ ื ็ ่ ้ ๊ ๋ ์ ํ ๎)
_TONE = "\u0e48-\u0e4b"
_CONS = "\u0e01-\u0e2e"
_FIX = [
    # "ใหเ้" -> "ให้เ" : วรรณยุกต์หลุดไปติดหลังสระหน้า ย้ายกลับไปที่พยัญชนะก่อนหน้า
    (re.compile(rf"([{_CONS}])([{_LEAD}])([{_TONE}])"), r"\1\3\2"),
    # หมายเหตุ: ไม่แก้ "จกัร" -> "จักร" เพราะแยกไม่ออกจากคำที่ถูกอยู่แล้ว (รักษา, ครับ) — ปล่อยให้ LLM อ่านเอง
    # วรรณยุกต์/สระบนลอยหลังช่องว่างหรือต้นคำ -> ทิ้ง
    (re.compile(rf"(^|\s)[{_ABOVE}]+"), r"\1"),
]


def fix_thai(s: str) -> str:
    for pat, rep in _FIX:
        s = pat.sub(rep, s)
    return s


def clean_text(s: str) -> str:
    s = html.unescape(s or "")
    s = unicodedata.normalize("NFC", s)
    s = s.replace("ึั้", "ึ้").replace("\u200b", "")      # "ขึั้นไป" -> "ขึ้นไป"
    s = fix_thai(s)
    if th_normalize:
        s = th_normalize(s)
    s = _BULLET.sub("", s)
    s = _SPACES.sub(" ", s).strip()
    return s[:MAX_ITEM_CHARS]


def years_from_items(items: list):
    return years_from_lines([it["content"] for it in items])


def build_job_payload(job: dict, items: list) -> tuple:
    """คืน (payload ส่ง LLM, item_id ที่เป็นหัวข้อ — ตาข่ายสำรอง ปกติ loader ตัดไปแล้ว)"""
    title = clean_text(job["title"])
    attrs = job.get("attributes") or {}
    hints = {k: attrs[k] for k in ("ระดับตำแหน่งงาน", "รูปแบบงาน", "ประสบการณ์(ปี)") if attrs.get(k)}
    if job.get("experience_years") is not None:
        hints["experience_years"] = job["experience_years"]

    header_ids, sent = [], []
    for it in items:
        text = clean_text(it["content"])
        if is_header(text, title):
            header_ids.append(it["id"])
        else:
            sent.append({"item_id": it["id"], "source": it["source"], "text": text})
    return {"job_id": job["id"], "title": title, "hints": hints, "items": sent}, header_ids