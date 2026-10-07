# -*- coding: utf-8 -*-
"""scope.py — ตรวจว่างานอยู่ในขอบเขตสายงานที่ต้องการไหม (ใช้ทั้งตอน scrape และตอนทำความสะอาด)"""
from typing import Tuple

import config


def job_category(d: dict) -> Tuple[str, str]:
    """คืน (สาขาอาชีพหลัก, สาขาอาชีพรอง) จากข้อมูลงาน"""
    a = d.get("attributes") or {}
    return (a.get("สาขาอาชีพหลัก") or "").strip(), (a.get("สาขาอาชีพรอง") or "").strip()


def in_scope(d: dict) -> Tuple[bool, str]:
    """
    คืน (อยู่ในขอบเขตไหม, เหตุผล)
    ถ้า config.SCOPE ว่าง = ไม่กรอง รับทุกงาน
    """
    if not config.SCOPE:
        return True, "ไม่ได้ตั้งขอบเขต"

    main, sub = job_category(d)
    if not main:
        return config.KEEP_UNKNOWN_SCOPE, "อ่านสาขาอาชีพไม่ได้"

    if main not in config.SCOPE:
        return False, f"นอกสาย: {main}"

    allowed = config.SCOPE[main]
    if allowed is None:
        return True, "ในขอบเขต"
    if sub in allowed:
        return True, "ในขอบเขต"
    return False, f"นอกสาย: {main} / {sub or '?'}"
