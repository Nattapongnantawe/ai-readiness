# -*- coding: utf-8 -*-
"""รวมผล LLM + กฎ (dictionary / seniority) ใช้ทั้งโหมด JSON และ DB"""
from .preprocess import seniority_rule, years_from_items
from .schemas import ExtractedSkill, Seniority, SkillGroup, SkillType
from .tech_dict import match_items


def enrich(result, job: dict, items: list, normalizer):
    """แก้ result ในที่ (in-place) คืน experience_years ที่ใช้"""
    years = job.get("experience_years")
    if years is None:
        years = years_from_items(items)
    rule = seniority_rule(years)
    if rule:
        result.seniority = Seniority(rule)

    have = {normalizer.canonical(s.name)[1] for s in result.skills}
    for m in match_items(items):
        key = normalizer.canonical(m["name"])[1]
        if key in have:
            continue
        result.skills.append(ExtractedSkill(
            name=m["name"], skill_type=SkillType.hard, group=SkillGroup(m["group"]),
            is_required=m["is_required"], item_id=m["item_id"]))
        have.add(key)
    return years
