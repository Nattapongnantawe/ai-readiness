# -*- coding: utf-8 -*-
"""models.py — โครงสร้าง JSON ให้ "เหมือน JobThai v3" เพื่อให้ pipeline ใช้ตัวเดียวกันได้"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict


@dataclass
class Job:
    url_hash: str = ""
    source_site: str = "jobbkk"
    source_url: str = ""
    detail_url: str = ""
    scraped_at: str = ""

    company_id: str = ""
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
    travel: str = ""

    job_description: str = ""
    qualification: str = ""
    job_description_items: List[str] = field(default_factory=list)
    qualification_items: List[str] = field(default_factory=list)

    # ข้อมูลเพิ่มที่ JobBKK มีแต่ JobThai ไม่มี
    attributes: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Job":
        allowed = Job.__dataclass_fields__.keys()
        return Job(**{k: v for k, v in d.items() if k in allowed})

    def is_usable(self) -> bool:
        return bool(self.job_title and self.source_url)

    def is_complete(self) -> bool:
        return bool(self.job_title and (self.job_description or self.qualification))

    def missing_fields(self) -> list:
        return [f for f in ("job_title", "job_description", "qualification", "company_name")
                if not getattr(self, f)]
