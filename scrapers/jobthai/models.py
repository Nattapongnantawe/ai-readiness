# -*- coding: utf-8 -*-
"""models.py — โครงสร้าง JSON ของงาน 1 รายการ (Structured Data)"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class Job:
    # --- ตัวระบุ ---
    url_hash: str = ""                 # SHA-256 ของ URL (กันงานซ้ำ)
    source_site: str = "jobthai"
    source_url: str = ""               # หน้าที่คลิกเข้าไปครั้งแรก
    detail_url: str = ""               # หน้ารายละเอียดเต็ม
    scraped_at: str = ""

    # --- Step 2: ข้อมูลบริษัท + ภาพรวมงาน ---
    company_name: str = ""
    company_logo_url: Optional[str] = None
    company_description: str = ""
    job_title: str = ""
    location: str = ""
    salary: str = ""
    num_positions: str = ""
    post_date: str = ""
    welfare: str = ""
    contact: str = ""
    work_location: str = ""
    travel: str = ""                   # วิธีการเดินทาง (บางงานไม่มี)

    # --- Step 3: รายละเอียดเต็ม (ตัดส่วนซ้ำกับ Step 2 แล้ว) ---
    job_description: str = ""
    qualification: str = ""

    # --- ข้อความดิบก่อนตัดซ้ำ (เก็บไว้กู้คืนได้ ไม่ต้องกลับไปดึงเว็บใหม่) ---
    job_description_raw: str = ""
    qualification_raw: str = ""

    # --- เตรียมไว้ให้ขั้นสกัดทักษะ (Sprint ถัดไป) ---
    job_description_items: List[str] = field(default_factory=list)
    qualification_items: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Job":
        allowed = Job.__dataclass_fields__.keys()
        return Job(**{k: v for k, v in d.items() if k in allowed})

    def is_usable(self) -> bool:
        """มีข้อมูลขั้นต่ำพอที่จะเก็บไว้ (อย่างน้อยต้องรู้ว่าเป็นงานอะไร)"""
        return bool(self.job_title and self.source_url)

    def is_complete(self) -> bool:
        """ได้เนื้อหาหลักครบถ้วน — ถ้าไม่ครบจะถูกจดไว้ใน failed.jsonl เพื่อตามเก็บ"""
        return bool(self.job_title and (self.job_description or self.qualification))

    def missing_fields(self) -> list:
        """บอกว่าขาดอะไรบ้าง (ใช้เขียน log)"""
        out = []
        for f in ("job_title", "job_description", "qualification", "company_name"):
            if not getattr(self, f):
                out.append(f)
        return out