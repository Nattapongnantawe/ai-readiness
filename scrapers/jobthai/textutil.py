# -*- coding: utf-8 -*-
"""
textutil.py — จัดการข้อความ: ทำความสะอาด + ตัดข้อมูลซ้ำ
แยกออกมาเป็นไฟล์ต่างหากเพื่อให้ทดสอบได้โดยไม่ต้องเปิดเบราว์เซอร์
"""
import re
import unicodedata
from typing import List, Set

# ตัด bullet / เลขข้อ หน้าบรรทัด
#   "- ข้อความ" / "1. ข้อความ" / "(1) ข้อความ" / "2.1 ข้อความ" (เลขข้อย่อย)
# ระวัง: ต้องไม่ไปตัดตัวเลขที่เป็นเนื้อหา เช่น "25,000 - 35,000 บาท" หรือ "10-15 ปี"
BULLET_PREFIX = re.compile(
    r"^\s*(?:[-•·*▪◦–—]"          # bullet สัญลักษณ์
    r"|\d+(?:\.\d+)+[.)]?\s"      # เลขข้อย่อย 2.1 / 3.2.1 (ต้องมีช่องว่างตาม)
    r"|\d+[.)]"                   # เลขข้อ 1. หรือ 1)
    r"|\(\d+\))\s*")

# ข้อความไทยจากบางประกาศมีช่องว่างแทรกก่อนสระ/วรรณยุกต์
# เช่น "ผู ้ให้บริการ" / "ที ่เกี ่ยวข้อง"  ->  ต้องลบช่องว่างนั้นออก
THAI_COMBINING = "\u0E31\u0E34-\u0E3A\u0E47-\u0E4E"
BROKEN_THAI = re.compile(f"([\u0E00-\u0E7F])[ \t]+([{THAI_COMBINING}])")


def clean_text(s: str) -> str:
    """ตัดช่องว่างเกิน / บรรทัดว่างซ้อน ให้เหลือรูปแบบเดียว"""
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    s = s.replace("\u00a0", " ").replace("\u200b", "")
    # ซ่อมช่องว่างที่แทรกกลางคำไทย (วนซ้ำเผื่อมีหลายชั้น)
    for _ in range(3):
        s2 = BROKEN_THAI.sub(r"\1\2", s)
        if s2 == s:
            break
        s = s2
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in s.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def _norm_line(ln: str) -> str:
    """ทำบรรทัดให้เทียบกันได้ (ตัด bullet / ช่องว่าง / ตัวพิมพ์)"""
    ln = BULLET_PREFIX.sub("", ln)
    ln = re.sub(r"\s+", "", ln)
    return ln.lower()


def line_keys(text: str) -> Set[str]:
    """แปลงข้อความเป็นชุด key ของแต่ละบรรทัด (ใช้เทียบหาบรรทัดซ้ำ)"""
    out = set()
    for ln in clean_text(text).splitlines():
        k = _norm_line(ln)
        if len(k) >= 8:          # บรรทัดสั้นมากไม่นับ (เช่น "-", "ฯลฯ")
            out.add(k)
    return out


def remove_duplicate_lines(text: str, seen: Set[str]) -> str:
    """
    ตัดบรรทัดใน text ที่ซ้ำกับ seen ออก (ตามเงื่อนไขข้อ 1 ของโจทย์)
    บรรทัดสั้น ๆ ไม่ตัด เพราะอาจเป็นหัวข้อย่อยที่ซ้ำโดยธรรมชาติ
    """
    if not text:
        return ""
    kept = []
    for ln in clean_text(text).splitlines():
        k = _norm_line(ln)
        if len(k) >= 8 and k in seen:
            continue
        kept.append(ln)
    return "\n".join(kept).strip()


def dedupe_within(text: str) -> str:
    """ตัดบรรทัดที่ซ้ำกันเองภายในข้อความเดียวกัน (คงลำดับเดิม)"""
    seen, out = set(), []
    for ln in clean_text(text).splitlines():
        k = _norm_line(ln)
        if len(k) >= 8:
            if k in seen:
                continue
            seen.add(k)
        out.append(ln)
    return "\n".join(out).strip()


def to_bullets(text: str) -> List[str]:
    """แตกข้อความเป็นรายการ bullet (ไว้ใช้ตอนสกัดทักษะภายหลัง)"""
    return [BULLET_PREFIX.sub("", ln).strip()
            for ln in clean_text(text).splitlines() if ln.strip()]