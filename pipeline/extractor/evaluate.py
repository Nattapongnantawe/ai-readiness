# -*- coding: utf-8 -*-
r"""
วัดความแม่นยำ (C8) — ทำ gold standard ด้วยมือแล้วคำนวณ precision / recall / F1

1) สร้างแบบฟอร์มให้คนตรวจ (เปิดด้วย Excel ได้ ภาษาไทยไม่เพี้ยน)
   python -m extractor.evaluate prep --input output\test_jobthai_esco.json --input output\test_jobbkk_esco.json

   ได้ 3 ไฟล์ใน output\eval\
     bullets.csv  : กรอก gold_category (เว้นว่าง = เห็นด้วยกับ pred)
     skills.csv   : กรอก correct = Y / N
     missing.csv  : กรอก missing_skills = skill ที่ระบบพลาด คั่นด้วย ,

2) คำนวณผล + ออกรายงาน
   python -m extractor.evaluate score
   -> output\eval\report.md
"""
import argparse
import csv
import json
import os
from collections import Counter

DIR = os.path.join("output", "eval")
CATS = ["skill", "experience", "education", "certificate", "language", "responsibility", "other"]


def _w(path, header, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _r(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def prep(inputs):
    os.makedirs(DIR, exist_ok=True)
    jobs = []
    for p in inputs:
        with open(p, encoding="utf-8") as f:
            jobs.extend(json.load(f))
    b, s, m = [], [], []
    for n, j in enumerate(jobs, 1):
        t = j["job_info"]["title"]
        for x in j["classified_bullets"]:
            b.append([n, t, x["source"], x["text"], x["category"], ""])
        for k in ("hard_skills", "soft_skills"):
            for x in j[k]:
                s.append([n, t, k.split("_")[0], x["name"], x.get("esco_label", ""),
                          x.get("from_text", ""), ""])
        m.append([n, t, j["source_url"], ""])
    _w(os.path.join(DIR, "bullets.csv"),
       ["job_no", "title", "source", "text", "pred_category", "gold_category"], b)
    _w(os.path.join(DIR, "skills.csv"),
       ["job_no", "title", "type", "pred_skill", "esco_label", "from_text", "correct"], s)
    _w(os.path.join(DIR, "missing.csv"), ["job_no", "title", "source_url", "missing_skills"], m)
    print(f"📝 {len(jobs)} งาน | {len(b)} bullets | {len(s)} skills -> {DIR}\\")
    print(f"   หมวดที่ใช้ได้ใน gold_category: {', '.join(CATS)}")


def score():
    b = _r(os.path.join(DIR, "bullets.csv"))
    s = _r(os.path.join(DIR, "skills.csv"))
    m = _r(os.path.join(DIR, "missing.csv"))

    # --- bullet classification ---
    ok = sum(1 for r in b if not r["gold_category"].strip()
             or r["gold_category"].strip().lower() == r["pred_category"])
    acc = ok / max(len(b), 1)
    confusion = Counter((r["pred_category"], r["gold_category"].strip().lower())
                        for r in b if r["gold_category"].strip()
                        and r["gold_category"].strip().lower() != r["pred_category"])

    # --- skill extraction ---
    judged = [r for r in s if r["correct"].strip().upper() in ("Y", "N")]
    tp = sum(1 for r in judged if r["correct"].strip().upper() == "Y")
    fp = len(judged) - tp
    fn = sum(len([x for x in r["missing_skills"].split(",") if x.strip()]) for r in m)
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-9)
    unjudged = len(s) - len(judged)

    # --- ESCO coverage ---
    mapped = sum(1 for r in s if r["esco_label"].strip())

    lines = [
        "# รายงานความแม่นยำ Module 2", "",
        f"- จำนวนงาน: {len(m)} | bullets: {len(b)} | skills ที่ระบบสกัด: {len(s)}", "",
        "## 1. การจำแนก bullet", f"- Accuracy: **{acc:.1%}** ({ok}/{len(b)})",
    ]
    if confusion:
        lines += ["", "| pred | gold | จำนวน |", "|---|---|---|"]
        lines += [f"| {p} | {g} | {c} |" for (p, g), c in confusion.most_common(10)]
    lines += ["", "## 2. การสกัด skill",
              f"- Precision: **{prec:.1%}** (ถูก {tp} / ผิด {fp})",
              f"- Recall: **{rec:.1%}** (หลุด {fn})",
              f"- F1: **{f1:.1%}**"]
    if unjudged:
        lines.append(f"- ⚠️ ยังไม่ได้ตรวจ {unjudged} แถว (ไม่นับในผล)")
    lines += ["", "## 3. ESCO coverage",
              f"- จับคู่ได้ {mapped}/{len(s)} ({mapped / max(len(s), 1):.1%})",
              "", f"เกณฑ์ผ่าน ≥85%: bullet {'✅' if acc >= .85 else '❌'} | "
              f"skill F1 {'✅' if f1 >= .85 else '❌'}"]
    path = os.path.join(DIR, "report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))
    print(f"\n💾 {path}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prep")
    p.add_argument("--input", action="append", required=True)
    sub.add_parser("score")
    a = ap.parse_args()
    prep(a.input) if a.cmd == "prep" else score()


if __name__ == "__main__":
    main()
