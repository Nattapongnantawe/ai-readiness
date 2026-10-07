"""Exact skill matching for course descriptions (FR-GA-02), the same rule Module 3 used
(extractor/curriculum.py): a skill links to a course when its name appears in the course text as a
whole word — multi-word names, acronyms/CamelCase (PLC, NoSQL, JavaScript) and a short allow-list of
single words. Single common words (Design, Communication) are left to the semantic step of Module 3.
"""
import re

from sqlalchemy.orm import Session

from app.db import rows

EXACT_SINGLE_OK = {"unix", "linux", "python", "java", "arduino", "android", "matlab", "php", "javascript", "html",
                   "css", "sql", "nosql", "plc", "iot", "hdl", "vhdl", "verilog", "gis", "tcp/ip", "fpga", "scada",
                   "cad", "uml", "excel", "agile", "scrum", "git", "docker", "kubernetes", "mysql", "oracle",
                   "postgresql", "mongodb", "vpn", "firewall", "raspberry pi"}


def exact_ok(name: str) -> bool:
    n = name.strip()
    if n.lower() in EXACT_SINGLE_OK:
        return True
    if len(n) < 3:
        return False
    if " " in n:
        return True
    return bool(re.search(r"[A-Z].*[A-Z]|[0-9+#/.]", n[1:]))


def name_in_text(name: str, text: str) -> bool:
    """Whole-word, case-insensitive occurrence of a skill name (C++, C#, .NET safe)."""
    return bool(re.search(r"(?<![\w+#.])" + re.escape(name) + r"(?![\w+#])", text, re.I))


def extract_skill_ids(db: Session, text: str) -> list[int]:
    """Skill ids (only skills that appear in job postings) whose name occurs in `text`."""
    found = []
    for r in rows(db, "SELECT s.id, s.name FROM skills s WHERE EXISTS (SELECT 1 FROM job_skills js WHERE js.skill_id = s.id)"):
        name = r["name"]
        if not exact_ok(name):
            continue
        if name_in_text(name, text):
            found.append(r["id"])
    return found