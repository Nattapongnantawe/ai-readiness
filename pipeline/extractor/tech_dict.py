# -*- coding: utf-8 -*-
"""Dictionary matching: หาชื่อเทคโนโลยีด้วย Regex เสริมผล LLM ไม่ให้หลุด"""
import re

# ชื่อมาตรฐาน -> group   (เพิ่มได้เรื่อย ๆ)
TECH = {
    "Python": "programming_language", "Java": "programming_language", "C#": "programming_language",
    "C++": "programming_language", "JavaScript": "programming_language", "TypeScript": "programming_language",
    "PHP": "programming_language", "Go": None, "Kotlin": "programming_language", "Swift": "programming_language",
    "VBA": "programming_language", "R": None,
    ".NET": "framework", "ASP.NET": "framework", "React": "framework", "React Native": "framework",
    "Angular": "framework", "Vue.js": "framework", "Node.js": "framework", "Laravel": "framework",
    "Django": "framework", "Flask": "framework", "Spring Boot": "framework", "Flutter": "framework",
    "SQL": "database", "MySQL": "database", "PostgreSQL": "database", "Microsoft SQL Server": "database",
    "Oracle": "database", "MongoDB": "database", "Redis": "database",
    "AWS": "cloud_devops", "Microsoft Azure": "cloud_devops", "Google Cloud": "cloud_devops",
    "Docker": "cloud_devops", "Kubernetes": "cloud_devops", "Git": "cloud_devops", "Linux": "os_network",
    "Windows Server": "os_network", "Windows": "os_network", "Active Directory": "os_network",
    "LAN": "os_network", "Wi-Fi": "os_network", "Firewall": "os_network", "VPN": "os_network",
    "Computer Networking": "os_network", "CCNA": "os_network", "VMware": "os_network",
    "Microsoft Office": "software_tool", "Microsoft Excel": "software_tool", "Power BI": "ai_data",
    "Tableau": "ai_data", "HTML": "framework", "CSS": "framework", "AutoCAD": "software_tool", "SolidWorks": "software_tool", "SAP": "software_tool",
    "ERP": "software_tool", "Figma": "software_tool", "Jira": "software_tool",
    "PLC": "automation_plc", "SCADA": "automation_plc", "HMI": "automation_plc",
    "Ladder Logic": "automation_plc", "Structured Text": "automation_plc", "ROS": "automation_plc",
    # --- ไฟฟ้า / อิเล็กทรอนิกส์ / embedded ---
    "Arduino": "electrical_electronics", "Raspberry Pi": "electrical_electronics",
    "ESP32": "electrical_electronics", "STM32": "electrical_electronics",
    "Microcontroller": "electrical_electronics", "Embedded C": "electrical_electronics",
    "FPGA": "electrical_electronics", "Verilog": "electrical_electronics", "VHDL": "electrical_electronics",
    "PCB Design": "electrical_electronics", "Altium Designer": "electrical_electronics",
    "KiCad": "electrical_electronics", "Eagle": "electrical_electronics", "Proteus": "electrical_electronics",
    "MATLAB": "electrical_electronics", "Simulink": "electrical_electronics", "LabVIEW": "electrical_electronics",
    "AutoCAD Electrical": "electrical_electronics", "ETAP": "electrical_electronics",
    "Oscilloscope": "electrical_electronics", "Multimeter": "electrical_electronics",
    "VFD": "electrical_electronics", "Servo Motor": "electrical_electronics",
    "Modbus": "automation_plc", "RS485": "electrical_electronics", "CAN Bus": "electrical_electronics",
    "Siemens TIA Portal": "automation_plc", "Mitsubishi PLC": "automation_plc", "Omron PLC": "automation_plc",
    "Solar PV": "electrical_electronics", "UPS": "electrical_electronics", "CCTV": "os_network",
    "Preventive Maintenance": "engineering", "Corrective Maintenance": "engineering",
    "Electric Motors": "electrical_electronics", "Control Panel": "electrical_electronics",
    "Low Voltage Systems": "electrical_electronics", "High Voltage Systems": "electrical_electronics",
    "Reading Electrical Drawings": "electrical_electronics", "Electrical Troubleshooting": "electrical_electronics",
    "Software Testing": "engineering", "Web Security": "cloud_devops", "Webhook": "framework",
    "Network Router": "os_network", "Network Switch": "os_network",
    "Machine Learning": "ai_data", "Artificial Intelligence": "ai_data", "Deep Learning": "ai_data",
}
# รูปแบบที่ต้องจับเพิ่ม (ชื่อที่เขียนไม่ตรง) -> ชื่อมาตรฐาน
EXTRA = {r"\bMS\s*Office\b": "Microsoft Office", r"\bExcel\b": "Microsoft Excel",
         r"\bSQL\s*Server\b|\bMSSQL\b": "Microsoft SQL Server", r"\bReact\s*JS\b|\bReact\.js\b": "React",
         r"\bNode\s*JS\b": "Node.js", r"\bPostgres\b": "PostgreSQL", r"\bNetwork\s*Infrastructure\b|\bNetworking\b": "Computer Networking",
         r"\bK8s\b": "Kubernetes", r"\bWifi\b": "Wi-Fi",
         r"\bAI\s*Tools?\b|\bGenerative\s*AI\b": "Artificial Intelligence",
         r"\bHTML5?\b": "HTML", r"\bCSS3?\b": "CSS",
         r"\bAltium\b": "Altium Designer", r"\bTIA\s*Portal\b": "Siemens TIA Portal",
         r"ออกแบบ\s*(แผ่น)?\s*PCB|\bPCB\s*(design|layout)\b": "PCB Design",
         r"ไมโครคอนโทรลเลอร์|\bMCU\b": "Microcontroller",
         r"อินเวอร์เตอร์|\bInverter\b": "VFD", r"เซอร์โว\s*มอเตอร์": "Servo Motor",
         r"ออสซิลโลสโคป": "Oscilloscope", r"มัลติมิเตอร์": "Multimeter",
         r"โซล่า\s*เซลล์|โซลาร์\s*เซลล์|\bsolar\s*(cell|pv)\b": "Solar PV",
         r"กล้อง\s*วงจรปิด": "CCTV",
         r"ซ่อมบำรุง\s*เชิง\s*ป้องกัน|\bpreventive\s*maintenance\b": "Preventive Maintenance",
         r"ซ่อมบำรุง\s*เชิง\s*แก้ไข|\bcorrective\s*maintenance\b": "Corrective Maintenance",
         r"มอเตอร์\s*ไฟฟ้า|\belectric(al)?\s*motors?\b": "Electric Motors",
         r"ตู้\s*ควบคุม|แผง\s*ควบคุม(ไฟฟ้า)?|ตู้\s*MDB|\bcontrol\s*panels?\b": "Control Panel",
         r"ไฟฟ้า\s*แรง\s*ต่ำ|\blow\s*voltage\b": "Low Voltage Systems",
         r"ไฟฟ้า\s*แรง\s*สูง|\bhigh\s*voltage\b": "High Voltage Systems",
         r"อ่าน\s*(แบบ|วงจร)\s*(ไฟฟ้า)?|\b(read(ing)?)\s*(electrical\s*)?(drawings?|schematics?)\b": "Reading Electrical Drawings",
         r"\b(software|qa)\s*testing\b|\btest\s*plans?\b|\bunit\s*tests?\b|ทดสอบ\s*(โปรแกรม|ซอฟต์แวร์|ระบบงาน)": "Software Testing",
         r"\bweb\s*security\b|\bOWASP\b|ความปลอดภัย\s*(ของ)?\s*เว็บ": "Web Security",
         r"\bwebhooks?\b": "Webhook",
         r"\brouters?\b|เราเตอร์": "Network Router"}
# คำสั้น/กำกวม ไม่จับด้วย dictionary (ปล่อยให้ LLM)
SKIP = {"Go", "R", "Oracle", "Windows", "SQL"}
NICE = re.compile(r"พิจารณาเป็นพิเศษ|หากมี|จะได้รับการพิจารณา|preferred|is a plus|nice to have|advantage", re.I)

_PATTERNS = []
for name, grp in TECH.items():
    if name in SKIP or grp is None:
        continue
    esc = re.escape(name)
    tail = r"(?!\s*Native)" if name == "React" else ""          # React Native != React
    _PATTERNS.append((re.compile(rf"(?<![A-Za-z0-9.#+]){esc}(?![A-Za-z0-9#+]){tail}", re.I), name))
for pat, name in EXTRA.items():
    _PATTERNS.append((re.compile(pat, re.I), name))
# Windows / SQL: จับเฉพาะตัวพิมพ์ตรง และไม่ใช่ส่วนหนึ่งของคำอื่น
_PATTERNS.append((re.compile(r"(?<![A-Za-z])Windows(?!\s*(Server|-based|application))"), "Windows"))
_PATTERNS.append((re.compile(r"(?<![A-Za-z])SQL(?![A-Za-z]|\s*Server)"), "SQL"))   # ไม่นับ SQLite


def match_items(items: list) -> list:
    """items: [{id, content}] -> [{name, group, item_id, is_required}]"""
    found = {}
    for it in items:
        text = it["content"]
        for pat, name in _PATTERNS:
            if name not in found and pat.search(text):
                found[name] = {"name": name, "group": TECH.get(name, "other"),
                               "item_id": it["id"], "is_required": not NICE.search(text)}
    return list(found.values())