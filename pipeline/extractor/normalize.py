# -*- coding: utf-8 -*-
"""Skill Normalization: รวมคำพ้อง (synonyms) ให้เป็น skill เดียว"""
import re
import unicodedata

# alias (ตัวพิมพ์เล็ก) -> ชื่อมาตรฐาน   | เพิ่มได้เรื่อย ๆ หรือเพิ่มในตาราง skill_aliases
SEED_ALIASES = {
    # programming / framework
    "js": "JavaScript", "javascript": "JavaScript", "ts": "TypeScript", "typescript": "TypeScript",
    "reactjs": "React", "react.js": "React", "react js": "React",
    "react native": "React Native", "nodejs": "Node.js", "node": "Node.js", "node js": "Node.js",
    "vuejs": "Vue.js", "vue": "Vue.js", "nextjs": "Next.js", "next": "Next.js",
    "c sharp": "C#", "csharp": "C#", "dotnet": ".NET", ".net framework": ".NET",
    "asp.net": "ASP.NET", "golang": "Go", "python3": "Python",
    # database
    "sql database": "SQL", "sql server": "Microsoft SQL Server", "mssql": "Microsoft SQL Server",
    "ms sql": "Microsoft SQL Server", "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
    "mongo": "MongoDB", "mongodb": "MongoDB",
    # devops / cloud / os / network
    "k8s": "Kubernetes", "aws": "AWS", "amazon web services": "AWS",
    "gcp": "Google Cloud", "google cloud platform": "Google Cloud", "azure": "Microsoft Azure",
    "ad": "Active Directory", "microsoft active directory": "Active Directory",
    "windows server": "Windows Server", "lan": "LAN", "wifi": "Wi-Fi", "wi fi": "Wi-Fi",
    "network infrastructure": "Computer Networking", "networking": "Computer Networking",
    "wi fi": "Wi-Fi", "wireless network": "Wi-Fi", "ui/ux design": "UI/UX Design",
    "working under pressure": "Work Under Pressure", "work under stress": "Work Under Pressure",
    "ability to work under pressure": "Work Under Pressure",
    "router": "Network Router", "routers": "Network Router", "switch": "Network Switch",
    "network switch": "Network Switch", "network router": "Network Router",
    "system design": "System Design", "solution design": "Solution Design",
    "java spring boot": "Spring Boot", "spring": "Spring Boot",
    "preventive maintenance": "Preventive Maintenance", "pm": "Preventive Maintenance",
    "corrective maintenance": "Corrective Maintenance",
    "dot net": ".NET", "vb.net": "VB.NET", "asp net": "ASP.NET", "network": "Computer Networking", "ระบบเครือข่าย": "Computer Networking",
    # office / tools
    "ms office": "Microsoft Office", "microsoft office": "Microsoft Office", "office": "Microsoft Office",
    "excel": "Microsoft Excel", "ms excel": "Microsoft Excel", "autocad": "AutoCAD",
    "erp system": "ERP", "erp": "ERP", "sap erp": "SAP", "ai tools": "Artificial Intelligence", "ai tool": "Artificial Intelligence",
    "ai": "Artificial Intelligence", "artificial intelligence": "Artificial Intelligence",
    "generative ai": "Artificial Intelligence", "genai": "Artificial Intelligence",
    "html5": "HTML", "css3": "CSS", "vue": "Vue.js", "angularjs": "Angular",
    "microsoft windows": "Windows", "windows os": "Windows", "ms windows": "Windows",
    # automation
    "programmable logic controller": "PLC", "plc programming": "PLC", "ladder": "Ladder Logic",
    "scada systems": "SCADA", "ml": "Machine Learning",
    # soft skills
    "team work": "Teamwork", "teamwork": "Teamwork", "การทำงานเป็นทีม": "Teamwork",
    "ทำงานเป็นทีม": "Teamwork", "problem-solving": "Problem Solving",
    "การแก้ปัญหา": "Problem Solving", "แก้ไขปัญหา": "Problem Solving",
    "communication skills": "Communication", "การสื่อสาร": "Communication",
    "มนุษยสัมพันธ์": "Interpersonal Skills", "มนุษยสัมพันธ์ดี": "Interpersonal Skills",
    "interpersonal": "Interpersonal Skills", "ภาวะผู้นำ": "Leadership",
    "ความรับผิดชอบ": "Responsibility", "analytical skills": "Analytical Thinking",
    "analytical thinking": "Analytical Thinking", "การวิเคราะห์": "Analytical Thinking",
}

_KEEP = re.compile(r"[^0-9a-z\u0e00-\u0e7f#+. ]")


def norm_key(name: str) -> str:
    s = unicodedata.normalize("NFC", name or "").lower().strip()
    s = s.replace("_", " ").replace("-", " ")
    s = _KEEP.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip().rstrip(".").strip()
    return s


# คำกว้างเกินไป ไม่นับเป็นทักษะ (ตัดทิ้งตั้งแต่ก่อนบันทึก)
GENERIC_SKILLS = {
    "software", "hardware", "system", "systems", "server", "servers", "application",
    "applications", "program", "programs", "computer", "computers", "it", "tool", "tools",
    "technology", "technologies", "data", "web", "cloud", "network", "database", "api",
    "design", "development", "programming", "coding",
    "software development", "application development", "web application", "word", "office",
    "framework", "platform", "script", "scripting",
}


class SkillNormalizer:
    def __init__(self, db_aliases: dict = None):
        """db_aliases: {alias_norm: canonical_name} จากตาราง skill_aliases"""
        self.map = {norm_key(k): v for k, v in SEED_ALIASES.items()}
        self.map.update(db_aliases or {})

    def is_generic(self, name: str) -> bool:
        return norm_key(self.canonical(name)[0]) in GENERIC_SKILLS

    def canonical(self, name: str) -> tuple:
        """คืน (ชื่อมาตรฐาน, key มาตรฐาน, key ของ alias เดิม)"""
        alias_key = norm_key(name)
        canon = self.map.get(alias_key, name.strip())
        canon_key = norm_key(canon)
        return canon, canon_key, alias_key