# -*- coding: utf-8 -*-
"""Pydantic schema — ใช้ทั้งเป็น response_schema ของ Gemini และ validate ผลลัพธ์"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, field_validator


class ItemCategory(str, Enum):
    skill = "skill"
    experience = "experience"
    education = "education"
    certificate = "certificate"
    language = "language"
    responsibility = "responsibility"
    other = "other"


class Seniority(str, Enum):
    entry = "entry"
    mid = "mid"
    senior = "senior"
    unknown = "unknown"


class WorkMode(str, Enum):
    onsite = "onsite"
    remote = "remote"
    hybrid = "hybrid"
    unknown = "unknown"


class SkillType(str, Enum):
    hard = "hard"
    soft = "soft"


class SkillGroup(str, Enum):
    programming_language = "programming_language"
    framework = "framework"
    database = "database"
    cloud_devops = "cloud_devops"
    os_network = "os_network"
    automation_plc = "automation_plc"
    electrical_electronics = "electrical_electronics"      # วงจร, PCB, embedded, ระบบไฟฟ้ากำลัง
    ai_data = "ai_data"
    software_tool = "software_tool"
    engineering = "engineering"
    business = "business"
    soft = "soft"
    other = "other"


class ItemLabel(BaseModel):
    item_id: int
    category: ItemCategory
    confidence: float

    @field_validator("confidence")
    @classmethod
    def _clamp(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


class ExtractedSkill(BaseModel):
    name: str                      # ชื่อมาตรฐานภาษาอังกฤษ เช่น "Python", "Teamwork"
    skill_type: SkillType
    group: SkillGroup
    is_required: bool              # False = "จะพิจารณาเป็นพิเศษ" / nice-to-have
    item_id: Optional[int]

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return " ".join(v.split()).strip(" ,;:-").rstrip(".")


class JobExtraction(BaseModel):
    job_id: int
    seniority: Seniority
    work_mode: WorkMode
    items: List[ItemLabel]
    skills: List[ExtractedSkill]


class BatchExtraction(BaseModel):
    jobs: List[JobExtraction]


# ---------- Output models (C4: บังคับ category ให้อยู่ใน enum ก่อนเขียนไฟล์/DB) ----------
from typing import Literal  # noqa: E402


class BulletOut(BaseModel):
    source: Literal["description", "qualification"]
    category: ItemCategory                     # ค่านอก enum (เช่น "header") -> ValidationError
    confidence: Optional[float] = None
    text: str
    cleaned: Optional[str] = None


class SkillOut(BaseModel):
    name: str
    name_norm: str                             # C2: canonical key มีเสมอ แม้ ESCO ไม่เจอ
    type: SkillType
    group: SkillGroup
    required: bool
    from_text: Optional[str] = None
    raw_name: Optional[str] = None
    esco_label: Optional[str] = None
    esco_uri: Optional[str] = None
    esco_score: Optional[float] = None
    esco_description: Optional[str] = None
