# -*- coding: utf-8 -*-
"""
adapters.py — แปลง JSON ของแต่ละเว็บให้เป็น record กลางรูปแบบเดียวกัน
เพิ่มเว็บใหม่ = เขียนฟังก์ชันใหม่ 1 ตัว ไม่ต้องแตะ schema หรือ loader
"""
import hashlib
from typing import Dict, List, Optional

from parsers import (parse_salary, parse_salary_period, parse_date, parse_positions,
                     parse_experience, parse_location, normalize_company)
from extractor.bullets import merge_bullets, years_from_lines

# หัวข้อใน sections ของ JobBKK ที่แมปเข้าคอลัมน์หลัก
BKK_SECTION_MAP = {
    "description":   ["หน้าที่และความรับผิดชอบ", "รายละเอียดงาน", "ลักษณะงาน"],
    "qualification": ["คุณสมบัติด้านความรู้และความสามารถ", "คุณสมบัติผู้สมัคร", "คุณสมบัติ"],
    "welfare":       ["สวัสดิการ"],
}


def _hash(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    return hashlib.sha256(url.split("?")[0].rstrip("/").encode("utf-8")).hexdigest()


def _clean(v) -> str:
    return (v or "").strip() if isinstance(v, str) else ""


def _lines(text: str) -> List[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def _sections_to_text(sections: dict, keys: List[str]) -> str:
    for k in keys:
        if k in sections:
            v = sections[k]
            if isinstance(v, list):
                return "\n".join(str(x).strip() for x in v if str(x).strip())
            return str(v).strip()
    return ""


def _sections_to_items(sections: dict, keys: List[str]) -> List[str]:
    for k in keys:
        if k in sections:
            v = sections[k]
            if isinstance(v, list):
                return [str(x).strip() for x in v if str(x).strip()]
            return _lines(str(v))
    return []


def _province_fallback(*texts) -> tuple:
    """
    หาจังหวัดจากข้อความสำรอง (เช่น ที่อยู่ในช่องติดต่อ)
    ใช้เมื่อสถานที่ปฏิบัติงานเป็นสถานีรถไฟฟ้า เช่น "BTS ราชเทวี"
    ซึ่ง parse_location คืน None โดยตั้งใจ
    """
    from parsers import PROVINCES, PROVINCE_ALIAS
    for t in texts:
        if not t:
            continue
        for alias, official in PROVINCE_ALIAS.items():
            if alias in t:
                return official, None
        for p in sorted(PROVINCES, key=len, reverse=True):
            if p in t:
                # หาอำเภอ/เขตที่อยู่ใกล้ ๆ ด้วย
                import re
                m = re.search(r"(?:เขต|อำเภอ|อ\.)\s*([^\s,]+)", t)
                return p, (m.group(1) if m else None)
    return None, None


def _requirement_items(desc_items: List[str], qual_items: List[str], title: str = "") -> List[dict]:
    """
    รวม bullet ทั้งหมดพร้อมลำดับ — ฐานของขั้น 'จำแนก skill / experience / certificate'
    merge_bullets: ตัดหัวข้อ/noise + รวมบรรทัดต่อเนื่อง (แก้ header ใน DB และ JobThai แตก bullet เกิน)
    """
    out = []
    for source, lines in (("description", desc_items), ("qualification", qual_items)):
        for seq, c in enumerate(merge_bullets(lines, title), 1):
            out.append({"source": source, "seq": seq, "content": c})
    return out


def _base() -> dict:
    """ฟิลด์ทั้งหมดของ record กลาง (ทุก adapter ต้องคืนครบชุดนี้)"""
    return {
        "url_hash": None, "source_site": None, "source_url": None,
        "detail_url": None, "scraped_at": None,
        "company_name": None, "company_norm": None,
        "company_logo_url": None, "company_description": None,
        "title": "", "salary_raw": None, "salary_type": "unspecified", "salary_period": "month",
        "salary_min": None, "salary_max": None,
        "location_raw": None, "province": None, "district": None, "travel": None,
        "num_positions": None, "posted_date": None, "valid_through": None,
        "employment_type": None, "job_category": None,
        "experience_years": None, "education_level": None,
        "description": None, "qualification": None, "welfare": None,
        "contact": None, "work_location": None,
        "sections": {}, "attributes": {},
        "tags": [], "requirement_items": [],
    }


# ---------------------------------------------------------------- JobThai v3
def from_jobthai(r: dict) -> dict:
    """JobThai (scraper v3 — single-pass) -> record กลาง"""
    stype, smin, smax = parse_salary(r.get("salary"))

    work_loc = _clean(r.get("work_location")) or _clean(r.get("location"))
    province, district = parse_location(work_loc)
    if not province:
        # สถานที่เป็นสถานีรถไฟฟ้า -> หาจังหวัดจากที่อยู่ในช่องติดต่อแทน
        province, d2 = _province_fallback(r.get("contact"), r.get("travel"))
        district = district or d2
    company = _clean(r.get("company_name"))

    desc = _clean(r.get("job_description"))
    qual = _clean(r.get("qualification"))
    d_items = r.get("job_description_items") or _lines(desc)
    q_items = r.get("qualification_items") or _lines(qual)

    rec = _base()
    rec.update({
        "url_hash":        r.get("url_hash") or _hash(r.get("source_url")),
        "source_site":     "jobthai",
        "source_url":      _clean(r.get("source_url")),
        "detail_url":      _clean(r.get("detail_url")) or None,
        "scraped_at":      _clean(r.get("scraped_at")) or None,
        "company_name":    company or None,
        "company_norm":    normalize_company(company),
        "company_logo_url": _clean(r.get("company_logo_url")) or None,
        "company_description": _clean(r.get("company_description")) or None,
        "title":           _clean(r.get("job_title")),
        "salary_raw":      _clean(r.get("salary")) or None,
        "salary_period":   parse_salary_period(r.get("salary")),
        "salary_type":     stype,
        "salary_min":      smin,
        "salary_max":      smax,
        "location_raw":    work_loc or None,
        "province":        province,
        "district":        district,
        "travel":          _clean(r.get("travel")) or None,
        "num_positions":   parse_positions(r.get("num_positions")),
        "posted_date":     parse_date(r.get("post_date")),
        "description":     desc or None,
        "qualification":   qual or None,
        "welfare":         _clean(r.get("welfare")) or None,
        "contact":         _clean(r.get("contact")) or None,
        "work_location":   work_loc or None,
        "tags":            [t for t in (r.get("tags") or []) if t],
        "requirement_items": _requirement_items(d_items, q_items, _clean(r.get("job_title"))),
        "experience_years": years_from_lines(q_items + d_items),
    })
    return rec


# ---------------------------------------------------------------- JobBKK
def from_jobbkk(r: dict) -> dict:
    """
    JobBKK -> record กลาง  (เลือกตามรูปแบบข้อมูลอัตโนมัติ)
      v2  = scraper ใหม่ (single-pass) มี job_description / attributes
      old = crawler เดิม มี sections / fields / datePosted
    """
    if "job_description" in r or "attributes" in r:
        return _from_jobbkk_v2(r)
    return _from_jobbkk_legacy(r)


def _from_jobbkk_v2(r: dict) -> dict:
    """JobBKK scraper v2 -> record กลาง (โครงสร้างเดียวกับ JobThai v3 + attributes)"""
    attrs = r.get("attributes") or {}
    stype, smin, smax = parse_salary(r.get("salary"))

    loc = _clean(r.get("location")) or _clean(r.get("work_location"))
    province, district = parse_location(loc)
    if district and district.startswith(("ทุกเขต", "ทุกอำเภอ")):
        district = None                      # "นนทบุรี (ทุกเขต/อำเภอ)" = ไม่ระบุเขต
    if not province:
        province, d2 = _province_fallback(attrs.get("ที่อยู่"), r.get("contact"))
        district = district or d2

    company = _clean(r.get("company_name"))
    desc = _clean(r.get("job_description"))
    qual = _clean(r.get("qualification"))
    d_items = r.get("job_description_items") or _lines(desc)
    q_items = r.get("qualification_items") or _lines(qual)

    main_cat = _clean(attrs.get("สาขาอาชีพหลัก"))
    sub_cat = _clean(attrs.get("สาขาอาชีพรอง"))
    category = " / ".join(x for x in (main_cat, sub_cat) if x) or None

    rec = _base()
    rec.update({
        "url_hash":        r.get("url_hash") or _hash(r.get("source_url")),
        "source_site":     "jobbkk",
        "source_url":      _clean(r.get("source_url")),
        "detail_url":      _clean(r.get("detail_url")) or None,
        "scraped_at":      _clean(r.get("scraped_at")) or None,
        "company_name":    company or None,
        "company_norm":    normalize_company(company),
        "company_logo_url": _clean(r.get("company_logo_url")) or None,
        "company_description": _clean(r.get("company_description")) or None,
        "title":           _clean(r.get("job_title")),
        "salary_raw":      _clean(r.get("salary")) or None,
        "salary_period":   parse_salary_period(r.get("salary")),
        "salary_type":     stype,
        "salary_min":      smin,
        "salary_max":      smax,
        "location_raw":    loc or None,
        "province":        province,
        "district":        district,
        "travel":          _clean(r.get("travel")) or None,
        "num_positions":   parse_positions(r.get("num_positions")),
        "posted_date":     parse_date(r.get("post_date")),
        "employment_type": _clean(attrs.get("รูปแบบงาน")) or None,
        "job_category":    category,
        "experience_years": (parse_experience(attrs.get("ประสบการณ์(ปี)"))
                             if attrs.get("ประสบการณ์(ปี)") else years_from_lines(q_items + d_items)),
        "education_level": _clean(attrs.get("ระดับการศึกษา")) or None,
        "description":     desc or None,
        "qualification":   qual or None,
        "welfare":         _clean(r.get("welfare")) or None,
        "contact":         _clean(r.get("contact")) or None,
        "work_location":   _clean(r.get("work_location")) or None,
        "attributes":      attrs,
        "requirement_items": _requirement_items(d_items, q_items, _clean(r.get("job_title"))),
    })
    return rec


def _from_jobbkk_legacy(r: dict) -> dict:
    """JobBKK crawler เดิม (sections / fields) -> record กลาง"""
    fields = r.get("fields") or {}
    sections = r.get("sections") or {}
    stype, smin, smax = parse_salary(r.get("salary"))

    # JobBKK แยกจังหวัด/เขตมาให้แล้ว ใช้ของเว็บก่อน
    province = _clean(r.get("address_region")) or None
    district = _clean(r.get("address_locality")) or None
    if district:
        district = district.replace("เขต", "", 1).strip() or None
    if not province:
        province, district = parse_location(r.get("location"))
    if not province:
        province, d2 = _province_fallback(fields.get("ที่อยู่"), r.get("location"))
        district = district or d2

    company = _clean(r.get("company_name"))
    desc = _sections_to_text(sections, BKK_SECTION_MAP["description"])
    qual = _sections_to_text(sections, BKK_SECTION_MAP["qualification"])

    rec = _base()
    rec.update({
        "url_hash":        r.get("url_hash") or _hash(r.get("source_url")),
        "source_site":     "jobbkk",
        "source_url":      _clean(r.get("source_url")),
        "detail_url":      _clean(r.get("detail_url")) or None,
        "scraped_at":      _clean(r.get("scraped_at")) or None,
        "company_name":    company or None,
        "company_norm":    normalize_company(company),
        "company_logo_url": _clean(r.get("company_logo_url")) or None,
        "company_description": _clean(r.get("company_description")) or None,
        "title":           _clean(r.get("job_title")) or _clean(r.get("title")),
        "salary_raw":      _clean(r.get("salary")) or None,
        "salary_period":   parse_salary_period(r.get("salary")),
        "salary_type":     stype,
        "salary_min":      smin,
        "salary_max":      smax,
        "location_raw":    _clean(r.get("location")) or None,
        "province":        province,
        "district":        district,
        "travel":          _clean(r.get("travel")) or None,
        "num_positions":   parse_positions(fields.get("จำนวนที่รับ")),
        "posted_date":     parse_date(r.get("datePosted")),
        "valid_through":   parse_date(r.get("validThrough")),
        "employment_type": _clean(r.get("employmentType")) or None,
        "job_category":    _clean(r.get("occupationalCategory")) or None,
        "experience_years": parse_experience(fields.get("ประสบการณ์(ปี)")),
        "education_level": _clean(fields.get("ระดับการศึกษา")) or None,
        "description":     desc or None,
        "qualification":   qual or None,
        "welfare":         _sections_to_text(sections, BKK_SECTION_MAP["welfare"]) or None,
        "work_location":   _clean(fields.get("ที่อยู่")) or None,
        "sections":        sections,
        "attributes":      fields,
        "requirement_items": _requirement_items(
            _sections_to_items(sections, BKK_SECTION_MAP["description"]),
            _sections_to_items(sections, BKK_SECTION_MAP["qualification"]),
            _clean(r.get("job_title")) or _clean(r.get("title")),
        ),
    })
    return rec


ADAPTERS = {"jobthai": from_jobthai, "jobbkk": from_jobbkk}


def adapt(record: dict, site: Optional[str] = None) -> dict:
    """เลือก adapter อัตโนมัติจาก source_site (หรือเดาจากรูปร่างข้อมูล)"""
    site = site or record.get("source_site")
    if not site:
        site = "jobbkk" if "occupationalCategory" in record or "fields" in record else "jobthai"
    fn = ADAPTERS.get(site)
    if not fn:
        raise ValueError(f"ไม่รู้จักแหล่งข้อมูล: {site}")
    return fn(record)