# -*- coding: utf-8 -*-
r"""
Skill Normalization -> มาตรฐานสากล ESCO (ไม่ต้องใช้ DB / Gemini)

  python -m extractor.esco_map --input output\test_jobthai.json
  -> output\test_jobthai_esco.json

วิธีจับคู่ (เข้มงวด: precision มาก่อน)
  1) ค้น ESCO API ด้วยชื่อ skill (หรือคำค้นใน QUERY_OVERRIDE)
  2) เทียบกับ preferred label ของผลลัพธ์
  3) ถ้าไม่ตรง -> ดึง alternative labels (ชื่อพ้อง) ของผล 5 อันดับแรกมาเทียบด้วย
  ทุก skill มี name_norm เสมอ แม้ ESCO ไม่เจอ (ใช้นับ Top skills ได้ไม่แตก)
ผลถูกเก็บใน data\esco_cache.json — แก้กฎแล้วต้องลบไฟล์นี้ก่อนรันใหม่
"""
import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request
from difflib import SequenceMatcher

from .normalize import norm_key

API = "https://ec.europa.eu/esco/api"
CACHE = os.path.join("data", "esco_cache.json")
CACHE_VERSION = 4
MIN_SCORE = 0.75
DETAIL_TOP = 5

QUERY_OVERRIDE = {
    "Teamwork": "work in teams",
    "Problem Solving": "solve problems",
    "Analytical Thinking": "think analytically",
    "Leadership": "lead others",
    "Responsibility": "assume responsibility",
    "Interpersonal Skills": "interpersonal skills",
    "Communication": "communication",
    "Time Management": "manage time",
    "Adaptability": "adapt to change",
    "Attention to Detail": "attend to detail",
    "Customer Service": "customer service",
    "Negotiation": "negotiation",
    "Networking": "computer networks",
    "Microsoft Excel": "use spreadsheets software",
    "Microsoft Office": "use microsoft office",
    "ERP": "enterprise resource planning",
    "PLC": "programmable logic controller",
    "LAN": "local area network",
    "Artificial Intelligence": "artificial intelligence",
    "Machine Learning": "machine learning",
    "Presentation": "give live presentation",
    "Negotiation": "negotiation principles",
    "Project Management": "project management principles",
    "Teamwork": "work in teams",
    "Google Workspace": "use google workspace",
    "Shell Script": "shell scripting",
    "Web Application": "web application development",
    "Software Development": "software development methodologies",
    "System Design": "systems development life-cycle",
}

# คู่ที่ตรวจด้วยตาแล้วว่าตรงความหมาย (จาก esco_audit) — บังคับจับกับ label นี้เท่านั้น
ESCO_EXACT = {
    "AutoCAD": "create AutoCAD drawings",
    "SAP": "SAP R3",
    "Solar PV": "solar energy",
    "Hardware Troubleshooting": "perform ICT troubleshooting",
}
FORCE_RECHECK = set(ESCO_EXACT) | {"Coordination"}   # ไม่ใช้ cache สำหรับรายการที่แก้กฎ

# คู่ที่ห้ามจับ (ตรวจแล้วว่าผิดความหมาย)
ESCO_BLOCK = {
    "Coordination": {"logistics"},
}

_STOP = {"a", "an", "the", "of", "to", "and", "for"}
# คำเกินที่ยอมให้มีใน label ESCO (คำกริยาทั่วไป / คำนามบอกประเภท) — สูงสุด 2 คำ
_ALLOWED = {"use", "implement", "apply", "operate", "manage", "configure", "maintain", "perform",
            "develop", "work", "program", "administer", "software", "programming", "computer",
            "language", "framework", "systems", "system", "tools", "tool", "database",
            "development", "applications", "application", "javascript", "technologies", "skills",
            "standard", "give", "live", "principles", "carry", "out", "based"}


def _http(path: str, params: dict) -> dict:
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "job-market-thesis/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def _search(query: str) -> list:
    d = _http("search", {"text": query, "type": "skill", "language": "en", "limit": 10, "full": "false"})
    return d.get("_embedded", {}).get("results", [])


def _detail(uri: str) -> dict:
    d = _http("resource/skill", {"uri": uri, "language": "en"})
    alts = (d.get("alternativeLabel") or {}).get("en") or []
    if isinstance(alts, str):
        alts = [alts]
    desc = (d.get("description") or {}).get("en") or {}
    desc = desc.get("literal") if isinstance(desc, dict) else desc
    return {"alts": alts, "desc": (desc or "")[:300] or None}


def _words(s: str) -> list:
    return re.findall(r"[a-z0-9#+.]+", s.lower())


def _score(name: str, label: str) -> float:
    a, b = name.lower().strip(), label.lower().strip()
    if a == b:
        return 1.0
    if a == re.sub(r"\s*\(.*\)\s*$", "", b):
        return 0.95                                   # "Python" = "Python (computer programming)"
    wa, wb = _words(a), _words(b)
    extra = [w for w in wb if w not in wa and w not in _STOP]
    if wa and all(w in wb for w in wa) and len(extra) <= 3 and all(w in _ALLOWED for w in extra):
        return 0.85                                   # "Firewall" -> "implement a firewall"
    return 0.0          # ความคล้ายของตัวอักษรอย่างเดียวไม่นับ (securities / deicing boot)


class EscoMapper:
    def __init__(self, cache_path: str = CACHE):
        self.cache_path = cache_path
        self.cache = {}
        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("_version") == CACHE_VERSION:
                self.cache = data
            else:
                print("  ♻️ cache เวอร์ชันเก่า -> เริ่มใหม่อัตโนมัติ")
        self.cache["_version"] = CACHE_VERSION
        self._details = {}

    def save(self):
        os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=1)

    def _get_detail(self, uri):
        if uri not in self._details:
            try:
                self._details[uri] = _detail(uri)
                time.sleep(0.2)
            except Exception:                           # noqa: BLE001
                self._details[uri] = {"alts": [], "desc": None}
        return self._details[uri]

    def map(self, name: str) -> dict:
        if name in self.cache and name not in FORCE_RECHECK:
            return self.cache[name]
        query = ESCO_EXACT.get(name) or QUERY_OVERRIDE.get(name, name)
        empty = {"esco_label": None, "esco_uri": None, "esco_score": None, "esco_description": None}
        try:
            hits = _search(query)
            time.sleep(0.2)
        except Exception as e:                          # noqa: BLE001
            print(f"  ⚠️ ESCO API ล้มเหลว ({name}): {str(e)[:80]}")
            return empty                                 # ไม่ cache -> รอบหน้าลองใหม่

        best, best_score = None, 0.0
        if name in ESCO_EXACT:                       # ตรวจแล้ว: รับเฉพาะ label ที่ระบุไว้
            want = ESCO_EXACT[name].lower()
            for h in hits:
                if (h.get("title") or "").lower() == want:
                    best, best_score = h, 1.0
                    break
            hits = [] if best else hits
        for q in {query, name}:
            for h in hits:
                s = _score(q, h.get("title") or "")
                if s > best_score:
                    best, best_score = h, s
        if best_score < MIN_SCORE:                       # ลองชื่อพ้องของผลอันดับต้น ๆ
            for h in hits[:DETAIL_TOP]:
                for alt in self._get_detail(h["uri"])["alts"]:
                    s = max(_score(query, alt), _score(name, alt))
                    s = 0.9 if s >= 0.95 else 0.0        # ชื่อพ้องต้องตรงจริงเท่านั้น
                    if s > best_score:
                        best, best_score = h, s

        if best is not None and (best.get("title") or "").lower() in ESCO_BLOCK.get(name, set()):
            best, best_score = None, 0.0
        if best is None or best_score < MIN_SCORE:
            res = dict(empty, esco_score=best_score)
        else:
            res = {"esco_label": best.get("title"), "esco_uri": best.get("uri"),
                   "esco_score": best_score, "esco_description": self._get_detail(best["uri"])["desc"]}
        self.cache[name] = res
        return res


def main():
    from .run_json import dump_compact

    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=os.path.join("output", "structured.json"))
    ap.add_argument("--output")
    a = ap.parse_args()
    out_path = a.output or a.input.replace(".json", "_esco.json")

    with open(a.input, encoding="utf-8") as f:
        jobs = json.load(f)

    mapper = EscoMapper()
    kinds = {}
    for j in jobs:
        for k in ("hard_skills", "soft_skills"):
            for s in j.get(k, []):
                kinds.setdefault(s["name"], k)
    names = sorted(kinds)
    print(f"🔎 skill ไม่ซ้ำ {len(names)} รายการ -> จับคู่กับ ESCO")

    stat = {"hard_skills": [0, 0], "soft_skills": [0, 0]}
    try:
        for n in names:
            m = mapper.map(n)
            hit = bool(m["esco_uri"])
            stat[kinds[n]][0] += hit
            stat[kinds[n]][1] += 1
            print(f"  {'✓' if hit else '✗'} {n:32} -> {m['esco_label'] or '-'}")
    finally:
        mapper.save()

    for j in jobs:
        for k in ("hard_skills", "soft_skills"):
            for s in j.get(k, []):
                s.setdefault("name_norm", norm_key(s["name"]))
                s.update(mapper.map(s["name"]))
                for f in list(s):
                    if s[f] is None:
                        del s[f]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(dump_compact(jobs))

    def pct(x):
        return f"{x[0]}/{x[1]} ({x[0] * 100 // max(x[1], 1)}%)"
    tot = [stat["hard_skills"][0] + stat["soft_skills"][0], stat["hard_skills"][1] + stat["soft_skills"][1]]
    print(f"\n✅ ESCO: hard {pct(stat['hard_skills'])} | soft {pct(stat['soft_skills'])} | รวม {pct(tot)}")
    print(f"💾 {out_path}")


if __name__ == "__main__":
    main()