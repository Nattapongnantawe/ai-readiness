# -*- coding: utf-8 -*-
r"""
จับคู่ทักษะกับ O*NET Technology Skills (ชื่อผลิตภัณฑ์/เทคโนโลยี) — เสริมส่วนที่ ESCO ไม่มี
ทำงานออฟไลน์ทั้งหมด ผลคงที่ ทำซ้ำได้ (ระบุเวอร์ชันไฟล์ได้)

เตรียมข้อมูลครั้งเดียว
  1) เปิด https://www.onetcenter.org/database.html#individual-files
  2) เลือกรูปแบบ CSV แล้วดาวน์โหลด "Software Skills" (เดิมชื่อ Technology Skills)
  3) วางไฟล์เป็น  data\onet_technology_skills.csv

รัน
  python -m extractor.onet_map --input output\test_jobthai_esco.json
  -> output\test_jobthai_esco_onet.json  (เพิ่ม onet_label / onet_commodity / onet_hot)
  -> สรุปความครอบคลุมรวม ESCO + O*NET

เกณฑ์จับคู่ (เข้มงวดแบบเดียวกับ ESCO: ตรงความหมายเท่านั้น)
  1.00 ชื่อตรงกัน                      React -> React
  0.90 ตรงหลังตัดวงเล็บ/ชื่อผู้ผลิต     Azure -> Microsoft Azure
  0.80 ตรงหลังตัดคำประเภททั่วไป        MongoDB -> MongoDB software
"""
import argparse
import csv
import json
import os
import re
import sys

from .normalize import SkillNormalizer, norm_key

DATA = os.path.join("data", "onet_technology_skills.csv")
VENDOR = ("microsoft", "apache", "oracle", "ibm", "adobe", "google", "amazon", "autodesk",
          "atlassian", "the mathworks", "sap", "salesforce", "mozilla", "jetbrains", "red hat")
GENERIC = ("software", "system", "systems", "tool", "tools", "framework", "frameworks",
           "language", "languages", "platform", "server", "database", "environment", "suite")


# ชื่อกว้างเกินไป / กำกวม — ไม่จับคู่กับ O*NET (กัน API -> API Healthcare ActiveStaffer)
TOO_GENERIC = {"software", "hardware", "system", "systems", "server", "api", "tool", "tools",
               "application", "applications", "program", "programs", "computer", "it",
               "database", "network", "data", "web", "cloud", "switch", "router", "word",
               "design", "development", "technology", "solution design", "system design",
               "software development", "application development", "web application"}


def _variants(name: str) -> set:
    """สร้างรูปแบบเทียบของชื่อหนึ่ง ๆ"""
    base = norm_key(re.sub(r"\s*\(.*?\)", " ", name))
    out = {base}
    for v in VENDOR:                                   # ตัดชื่อผู้ผลิตนำหน้า
        if base.startswith(v + " "):
            out.add(base[len(v) + 1:].strip())
    words = base.split()
    while words and words[-1] in GENERIC:              # ตัดคำประเภทท้ายชื่อ
        words = words[:-1]
        out.add(" ".join(words))
    return {v for v in out if len(v) >= 2}


LABEL_COLS = ("Workplace Example", "Example", "T2 Example")      # ชื่อเทคโนโลยี
GROUP_COLS = ("Element Name", "Commodity Title")                 # หมวดของเทคโนโลยี


def _pick(row: dict, names) -> str:
    for n in names:
        if row.get(n):
            return str(row[n]).strip()
    return ""


def load_onet(path: str) -> dict:
    """อ่านไฟล์ Software Skills / Technology Skills (CSV หรือ tab) -> {key: rec}"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        head = f.readline()
    delim = "\t" if head.count("\t") > head.count(",") else ","

    idx, rows = {}, 0
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=delim)
        if not any(c in (reader.fieldnames or []) for c in LABEL_COLS):
            print(f"❌ ไม่พบคอลัมน์ชื่อเทคโนโลยีในไฟล์ (พบ: {reader.fieldnames})")
            sys.exit(1)
        for row in reader:
            rows += 1
            label = _pick(row, LABEL_COLS)
            if not label:
                continue
            rec = {"label": label,
                   "commodity": _pick(row, GROUP_COLS),
                   "hot": _pick(row, ("Hot Technology",)).upper() in ("Y", "YES", "TRUE"),
                   "demand": _pick(row, ("In Demand",)).upper() in ("Y", "YES", "TRUE")}
            exact = norm_key(re.sub(r"\s*\(.*?\)", " ", label))
            keys = _variants(label)
            for tok in re.findall(r"\b[A-Z][A-Z0-9#+.]{1,7}\b", label):   # ตัวย่อ เช่น AWS
                keys.add(norm_key(tok))
            for i, v in enumerate(keys):
                if v == exact or v not in idx:
                    idx[v] = rec
    print(f"   (อ่าน {rows} แถว)")
    return idx


# ชื่อของเรา -> คีย์เพิ่มเติมที่ O*NET ใช้
# ชื่อของเราที่ห้ามจับคู่กับ label ของ O*NET ที่กว้างหรือแคบกว่า (คนละความหมาย)
BLOCK = {
    "mechanical": ("autodesk", "mechanical desktop"),      # วิศวกรรมเครื่องกล != โปรแกรม
    "windows batch": ("microsoft windows",),               # ภาษา script != ระบบปฏิบัติการ
    "machine vision": ("machine",),
}

ONET_ALIAS = {
    "wi-fi": ["wifi", "wireless fidelity wifi"],
    "computer networking": ["computer network", "network management software", "networking"],
    "windows file server": ["microsoft windows server", "file server software"],
    "windows batch": ["microsoft windows", "batch processing software"],
    "structured text": ["structured text st"],
    "vb.net": ["microsoft visual basic .net", "microsoft visual basic"],
    "oop": ["object oriented programming", "objectoriented programming"],
}
ONET_ALIAS = {norm_key(k): v for k, v in ONET_ALIAS.items()}     # ให้คีย์อยู่ในรูปเดียวกับ norm_key


def match(name: str, idx: dict, norm) -> tuple:
    canon, key, _ = norm.canonical(name)
    if key in TOO_GENERIC:
        return None, 0.0
    cands = sorted(_variants(canon), key=len, reverse=True)
    cands += [v.lstrip(".") for v in cands if v.startswith(".")]      # ".net" -> "net"
    cands += ["." + key] if not key.startswith(".") and len(key) <= 4 else []
    cands += [c.replace(" ", "") for c in cands if " " in c and len(c) <= 12]   # "wi fi" -> "wifi"
    cands += ONET_ALIAS.get(key, [])
    for i, v in enumerate(cands):
        rec = idx.get(v)
        if not rec:
            continue
        # ตัวย่อสั้น ๆ ต้องปรากฏเป็นคำเต็มใน label ของ O*NET (กัน API -> API Healthcare...)
        if len(v) <= 4 and not re.search(rf"(?<![A-Za-z0-9]){re.escape(v)}(?![A-Za-z0-9])",
                                         rec["label"], re.I):
            continue
        bad = BLOCK.get(key, ())
        if any(b in rec["label"].lower() for b in bad):
            continue
        score = 1.0 if v == key else 0.9 if i == 0 else 0.8
        return rec, round(score, 2)
    return None, 0.0


def dump_compact(o, ind=0) -> str:
    pad = "  " * ind
    flat = lambda x: not isinstance(x, (dict, list))  # noqa: E731
    if isinstance(o, dict):
        if all(flat(v) for v in o.values()):
            return json.dumps(o, ensure_ascii=False)
        body = ",\n".join(f'{pad}  {json.dumps(k, ensure_ascii=False)}: {dump_compact(v, ind + 1)}'
                          for k, v in o.items())
        return "{\n" + body + f"\n{pad}}}"
    if isinstance(o, list):
        if not o or all(flat(v) for v in o):
            return json.dumps(o, ensure_ascii=False)
        body = ",\n".join(f"{pad}  {dump_compact(v, ind + 1)}" for v in o)
        return "[\n" + body + f"\n{pad}]"
    return json.dumps(o, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True)
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--output", help="ใช้ได้เมื่อมี --input เดียว")
    a = ap.parse_args()

    if not os.path.exists(a.data):
        print(f"❌ ไม่พบไฟล์ {a.data}\n"
              f"   ดาวน์โหลด 'Technology Skills' (Text/tab-delimited) จาก\n"
              f"   https://www.onetcenter.org/database.html#individual-files\n"
              f"   แล้ววางเป็น {a.data}")
        sys.exit(1)

    idx = load_onet(a.data)
    print(f"📚 O*NET Technology Skills: {len(idx)} คีย์ค้นหา")
    norm = SkillNormalizer()

    for path in a.input:
        with open(path, encoding="utf-8") as f:
            jobs = json.load(f)
        seen, stats = {}, {"esco": 0, "onet": 0, "both": 0, "none": 0, "total": 0}
        for j in jobs:
            for k in ("hard_skills", "soft_skills"):
                for s in j.get(k, []):
                    rec, sc = match(s["name"], idx, norm)
                    if rec:
                        s["onet_label"] = rec["label"]
                        s["onet_commodity"] = rec["commodity"]
                        s["onet_hot"] = rec["hot"]
                        if rec.get("demand"):
                            s["onet_in_demand"] = True
                        s["onet_score"] = sc
                    if s["name"] not in seen:
                        seen[s["name"]] = (bool(s.get("esco_uri")), bool(rec),
                                           rec["label"] if rec else "", s.get("type", k[:4]))
        for name, (e, o, lab, _t) in seen.items():
            stats["total"] += 1
            stats["both" if e and o else "esco" if e else "onet" if o else "none"] += 1

        out = a.output if (a.output and len(a.input) == 1) else path.replace(".json", "_onet.json")
        with open(out, "w", encoding="utf-8") as f:
            f.write(dump_compact(jobs))

        new = [(n, lab) for n, (e, o, lab, _t) in seen.items() if o and not e]
        print(f"\n=== {os.path.basename(path)} — {stats['total']} skill ไม่ซ้ำ ===")
        for k, t in (("both", "ทั้ง ESCO + O*NET"), ("esco", "ESCO เท่านั้น"),
                     ("onet", "O*NET เท่านั้น (ที่ได้เพิ่ม)"), ("none", "ไม่มีในทั้งสองมาตรฐาน")):
            print(f"  {t:32} {stats[k]:3}  ({stats[k] * 100 // max(stats['total'], 1):2}%)")
        cov = stats["both"] + stats["esco"] + stats["onet"]
        print(f"  {'ครอบคลุมรวม':32} {cov:3}  ({cov * 100 // max(stats['total'], 1):2}%)"
              f"   [เดิม ESCO อย่างเดียว {(stats['both'] + stats['esco']) * 100 // max(stats['total'], 1)}%]")
        if new:
            print("\n  ▶ ทักษะที่ O*NET ช่วยได้เพิ่ม")
            for n, lab in sorted(new)[:40]:
                print(f"     {n[:28]:30} -> {lab}")
        left = [n for n, (e, o, _l, _t) in seen.items() if not e and not o]
        if left:
            print(f"\n  ▶ ยังไม่มีในมาตรฐานใด ({len(left)}): " + ", ".join(sorted(left)[:30]))
        print(f"\n  💾 {out}")


if __name__ == "__main__":
    main()