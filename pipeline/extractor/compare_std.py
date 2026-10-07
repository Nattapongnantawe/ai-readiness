# -*- coding: utf-8 -*-
r"""
เปรียบเทียบความครอบคลุมของมาตรฐาน ESCO vs O*NET (ใช้ไฟล์ *_esco_onet.json)

  python -m extractor.compare_std --input output\test_jobthai_esco_onet.json --input output\test_jobbkk_esco_onet.json

ผลลัพธ์
  จอภาพ                     ตารางเทียบ + สรุปแยก hard/soft   (แคปส่งอาจารย์)
  output\compare_std.csv    รายทักษะ: ESCO ได้อะไร / O*NET ได้อะไร
  output\compare_std.md     สรุปสำหรับแนบรายงาน
"""
import argparse
import csv
import json
import os

GROUPS = [("both", "ทั้งสองมาตรฐาน"), ("esco", "ESCO เท่านั้น"),
          ("onet", "O*NET เท่านั้น"), ("none", "ไม่มีในมาตรฐานใด")]


def collect(paths):
    skills = {}
    jobs_n = 0
    for p in paths:
        with open(p, encoding="utf-8") as f:
            jobs = json.load(f)
        jobs_n += len(jobs)
        for j in jobs:
            for k in ("hard_skills", "soft_skills"):
                for s in j.get(k, []):
                    r = skills.setdefault(s["name"], {
                        "skill": s["name"], "type": k.split("_")[0], "freq": 0,
                        "esco": s.get("esco_label", ""), "onet": s.get("onet_label", ""),
                        "onet_group": s.get("onet_commodity", ""),
                        "hot": "Y" if s.get("onet_hot") else ""})
                    r["freq"] += 1
                    r["esco"] = r["esco"] or s.get("esco_label", "")
                    r["onet"] = r["onet"] or s.get("onet_label", "")
    for r in skills.values():
        r["group"] = ("both" if r["esco"] and r["onet"] else "esco" if r["esco"]
                      else "onet" if r["onet"] else "none")
    return skills, jobs_n


def pct(a, b):
    return f"{a}/{b} ({a * 100 // max(b, 1)}%)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True)
    ap.add_argument("--out-csv", default=os.path.join("output", "compare_std.csv"))
    ap.add_argument("--out-md", default=os.path.join("output", "compare_std.md"))
    ap.add_argument("--top", type=int, default=25, help="จำนวนแถวที่แสดงบนจอ")
    a = ap.parse_args()

    skills, jobs_n = collect(a.input)
    rows = sorted(skills.values(), key=lambda r: (-r["freq"], r["skill"]))
    hard = [r for r in rows if r["type"] == "hard"]
    soft = [r for r in rows if r["type"] == "soft"]

    def stat(g):
        e = sum(1 for r in g if r["esco"])
        o = sum(1 for r in g if r["onet"])
        c = sum(1 for r in g if r["esco"] or r["onet"])
        return e, o, c, len(g)

    print(f"\n📊 เปรียบเทียบมาตรฐาน — {jobs_n} งาน · {len(rows)} skill ไม่ซ้ำ\n")
    print(f"{'':16}{'ESCO':>14}{'O*NET':>14}{'รวมสองมาตรฐาน':>20}")
    print("-" * 66)
    for label, g in (("ทั้งหมด", rows), ("Hard skills", hard), ("Soft skills", soft)):
        e, o, c, n = stat(g)
        print(f"{label:16}{pct(e, n):>14}{pct(o, n):>14}{pct(c, n):>22}")
    print("-" * 66)
    for key, name in GROUPS:
        n = sum(1 for r in rows if r["group"] == key)
        print(f"  {name:22} {n:3}  ({n * 100 // max(len(rows), 1):2}%)")

    print(f"\n{'ทักษะ':26}{'ครั้ง':>5}  {'ESCO':32}{'O*NET'}")
    print("-" * 110)
    for r in rows[:a.top]:
        print(f"{r['skill'][:24]:26}{r['freq']:>5}  {(r['esco'] or '—')[:30]:32}{(r['onet'] or '—')[:36]}")
    if len(rows) > a.top:
        print(f"... อีก {len(rows) - a.top} รายการ (ดูใน {a.out_csv})")

    os.makedirs(os.path.dirname(a.out_csv) or ".", exist_ok=True)
    with open(a.out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["skill", "type", "freq", "group", "esco", "onet",
                                          "onet_group", "hot"])
        w.writeheader()
        w.writerows(rows)

    e, o, c, n = stat(rows)
    md = ["# เปรียบเทียบความครอบคลุม: ESCO vs O*NET", "",
          f"ข้อมูล: {jobs_n} งาน · {len(rows)} skill ไม่ซ้ำ", "",
          "| กลุ่มทักษะ | ESCO | O*NET | รวมสองมาตรฐาน |", "|---|---|---|---|"]
    for label, g in (("ทั้งหมด", rows), ("Hard skills", hard), ("Soft skills", soft)):
        e2, o2, c2, n2 = stat(g)
        md.append(f"| {label} | {pct(e2, n2)} | {pct(o2, n2)} | **{pct(c2, n2)}** |")
    md += ["", "| การกระจาย | จำนวน |", "|---|---|"]
    md += [f"| {name} | {sum(1 for r in rows if r['group'] == k)} |" for k, name in GROUPS]
    md += ["", "## ข้อสังเกต", "",
           "- ESCO นิยามทักษะเป็น *ความสามารถ* จึงครอบคลุม soft skills ได้ดี",
           "- O*NET เป็นรายการ *ชื่อผลิตภัณฑ์/เทคโนโลยี* จึงครอบคลุม hard skills ได้ดีกว่า",
           "- การใช้สองมาตรฐานร่วมกันจึงเติมเต็มกัน ไม่ซ้ำซ้อน", ""]
    for key, name in GROUPS:
        g = [r for r in rows if r["group"] == key]
        if not g:
            continue
        md += [f"\n## {name} ({len(g)})", "", "| ทักษะ | ประเภท | ครั้ง | ESCO | O*NET |", "|---|---|---|---|---|"]
        md += [f"| {r['skill']} | {r['type']} | {r['freq']} | {r['esco'] or '—'} | {r['onet'] or '—'} |"
               for r in g]
    with open(a.out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"\n💾 {a.out_csv}\n💾 {a.out_md}")


if __name__ == "__main__":
    main()
