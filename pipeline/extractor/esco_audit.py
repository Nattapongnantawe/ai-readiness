# -*- coding: utf-8 -*-
r"""
ตรวจสอบกระบวนการจับคู่ ESCO (ESCO matching audit)
ตอบคำถาม: ทักษะที่จับคู่ไม่ได้ — ESCO "ไม่มีจริง" หรือ "มีแต่ระบบจับไม่เจอ" ?

  python -m extractor.esco_audit --input output\test_jobthai.json --input output\test_jobbkk.json

ผลลัพธ์
  จอภาพ            สรุป 4 กลุ่ม + รายการที่ต้องตรวจด้วยตา (ใช้แคปส่งอาจารย์)
  output\esco_audit.csv   ทุก skill พร้อมผู้สมัคร 5 อันดับแรกของ ESCO และคะแนน
  output\esco_audit.md    สรุปสำหรับแนบรายงาน

เกณฑ์ตัดสิน (best = คะแนนสูงสุดในบรรดาผู้สมัครทั้งหมด)
  MATCHED     best >= 0.75  จับคู่แล้ว
  NEAR_MISS   0.50–0.74     ESCO น่าจะมีแนวคิดนี้ แต่ใช้คำต่างจากเรา -> ต้องตรวจด้วยตา
  WEAK        0.30–0.49     น่าจะไม่มี แต่มีคำใกล้เคียง
  ABSENT      < 0.30        ไม่มีใน ESCO (ส่วนใหญ่เป็นชื่อผลิตภัณฑ์เฉพาะ)
"""
import argparse
import csv
import json
import os
import time
from difflib import SequenceMatcher

from .esco_map import QUERY_OVERRIDE, _score, _search, EscoMapper

CACHE = os.path.join("data", "esco_audit_cache_v2.json")
TOPN = 5


def _raw(name: str, label: str) -> float:
    """คะแนนดิบ (ไม่ผ่านกฎเข้มงวด) ใช้ดูว่า 'ใกล้' แค่ไหน"""
    return round(SequenceMatcher(None, name.lower().strip(), label.lower().strip()).ratio(), 3)


def verdict(best: float) -> str:
    return ("MATCHED" if best >= 0.75 else "NEAR_MISS" if best >= 0.50
            else "WEAK" if best >= 0.30 else "ABSENT")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True)
    ap.add_argument("--out-csv", default=os.path.join("output", "esco_audit.csv"))
    ap.add_argument("--out-md", default=os.path.join("output", "esco_audit.md"))
    ap.add_argument("--top", type=int, help="ตรวจเฉพาะ N ทักษะที่พบบ่อยที่สุด")
    ap.add_argument("--unmatched-only", action="store_true", help="ตรวจเฉพาะทักษะที่ยังไม่ได้จับคู่ ESCO")
    a = ap.parse_args()

    jobs = []
    for p in a.input:
        with open(p, encoding="utf-8") as f:
            jobs.extend(json.load(f))

    kinds, freq, mapped = {}, {}, set()
    for j in jobs:
        for k in ("hard_skills", "soft_skills"):
            for s in j.get(k, []):
                kinds[s["name"]] = k.split("_")[0]
                freq[s["name"]] = freq.get(s["name"], 0) + 1
                if s.get("esco_label"):
                    mapped.add(s["name"])
    names = sorted(kinds, key=lambda n: (-freq[n], n))
    if a.unmatched_only:
        names = [n for n in names if n not in mapped]
    if a.top:
        names = names[:a.top]

    cache = {}
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            cache = json.load(f)

    mapper = EscoMapper()            # ใช้ดึงชื่อพ้อง (alternative labels)
    rows, fails = [], 0
    print(f"🔬 ตรวจสอบการจับคู่ ESCO — {len(names)} skill ไม่ซ้ำ จาก {len(jobs)} งาน\n")

    for n in names:
        if n in cache:
            cands = cache[n]
        else:
            query = QUERY_OVERRIDE.get(n, n)
            try:
                hits = _search(query)
                time.sleep(0.2)
            except Exception as e:                         # noqa: BLE001
                print(f"  ⚠️ API ล้มเหลว ({n}): {str(e)[:60]}")
                fails += 1
                continue
            cands = []
            for h in hits[:TOPN]:
                title = h.get("title") or ""
                strict = _score(query, title)
                alt_best, alt_label = 0.0, ""
                for alt in mapper._get_detail(h["uri"])["alts"][:12]:
                    s = min(max(_score(query, alt), _score(n, alt)), 0.9)
                    if s > alt_best:
                        alt_best, alt_label = s, alt
                cands.append({"label": title, "uri": h.get("uri"),
                              "strict": max(strict, alt_best),
                              "raw": max(_raw(n, title), _raw(query, title)),
                              "via_alt": alt_label if alt_best > strict else ""})
            cache[n] = cands
            with open(CACHE, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=1)

        best_strict = max([c["strict"] for c in cands], default=0.0)
        best_raw = max([c["raw"] for c in cands], default=0.0)
        v = verdict(best_strict if best_strict >= 0.75 else best_raw)
        strict_win = max([c for c in cands if c["strict"] >= 0.75],
                         key=lambda c: c["strict"], default=None)
        top = strict_win or max(cands, key=lambda c: c["raw"], default=None)
        rows.append({"skill": n, "type": kinds[n], "freq": freq[n], "verdict": v,
                     "best_label": top["label"] if top else "", "score": round(best_raw, 2),
                     "strict": round(best_strict, 2), "via_alt": top["via_alt"] if top else "",
                     "uri": top["uri"] if top else "",
                     "candidates": " | ".join(f"{c['label']} ({c['raw']:.2f})" for c in cands)})

    # ---------- สรุปบนจอ ----------
    order = ["MATCHED", "NEAR_MISS", "WEAK", "ABSENT"]
    note = {"MATCHED": "จับคู่ได้", "NEAR_MISS": "ESCO น่าจะมี แต่ใช้คำต่างกัน (ต้องตรวจด้วยตา)",
            "WEAK": "มีคำใกล้เคียงแต่คนละความหมาย", "ABSENT": "ไม่มีใน ESCO"}
    print("=" * 78)
    for v in order:
        grp = [r for r in rows if r["verdict"] == v]
        print(f"{v:10} {len(grp):3} รายการ  ({len(grp) * 100 // max(len(rows), 1):2}%)  {note[v]}")
    print("=" * 78)

    for v in ("NEAR_MISS", "WEAK"):
        grp = [r for r in rows if r["verdict"] == v]
        if not grp:
            continue
        print(f"\n▶ {v} — {note[v]}")
        for r in sorted(grp, key=lambda r: -r["score"])[:20]:
            print(f"   {r['skill'][:26]:28} ({r['freq']:>4}) ~ {r['best_label'][:38]:40} {r['score']:.2f}")

    absent = [r for r in rows if r["verdict"] == "ABSENT"]
    if absent:
        print(f"\n▶ ABSENT — ไม่มีใน ESCO ({len(absent)} รายการ)")
        print("   " + ", ".join(f"{r['skill']}({r['freq']})" for r in sorted(absent, key=lambda r: -r["freq"])[:30]))
    if fails:
        print(f"\n⚠️ API ล้มเหลว {fails} รายการ — รันซ้ำอีกครั้งเพื่อเก็บให้ครบ")

    # ---------- ไฟล์ ----------
    os.makedirs(os.path.dirname(a.out_csv) or ".", exist_ok=True)
    with open(a.out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["skill"])
        w.writeheader()
        w.writerows(rows)

    def block(v, t):
        grp = sorted([r for r in rows if r["verdict"] == v], key=lambda r: -r["freq"])
        if not grp:
            return []
        out = [f"\n## {v} — {t} ({len(grp)})", "", "| skill | type | ครั้ง | ESCO ที่ใกล้ที่สุด | score |", "|---|---|---|---|---|"]
        return out + [f"| {r['skill']} | {r['type']} | {r['freq']} | {r['best_label'] or '-'} | {r['score']:.2f} |"
                      for r in grp]

    hard = [r for r in rows if r["type"] == "hard"]
    soft = [r for r in rows if r["type"] == "soft"]

    def rate(g):
        m = sum(1 for r in g if r["verdict"] == "MATCHED")
        return f"{m}/{len(g)} ({m * 100 // max(len(g), 1)}%)"
    md = ["# ผลตรวจสอบการจับคู่ ESCO", "",
          f"ข้อมูล: {len(jobs)} งาน · {len(rows)} skill ไม่ซ้ำ",
          f"- จับคู่ได้: hard {rate(hard)} · soft {rate(soft)}", "",
          "| กลุ่ม | ความหมาย | จำนวน |", "|---|---|---|"]
    md += [f"| {v} | {note[v]} | {sum(1 for r in rows if r['verdict'] == v)} |" for v in order]
    md += ["", "> NEAR_MISS คือทักษะที่ ESCO น่าจะมีแนวคิดนี้อยู่ แต่ใช้คำต่างจากประกาศงานไทย",
           "> ABSENT คือทักษะที่ไม่มีในมาตรฐาน ESCO ส่วนใหญ่เป็นชื่อผลิตภัณฑ์เฉพาะ",
           "> จึงควรใช้มาตรฐานอื่นเสริม (TPQI ของไทย / SkillsFuture ของสิงคโปร์)"]
    for v in order:
        md += block(v, note[v])
    with open(a.out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"\n💾 {a.out_csv}\n💾 {a.out_md}")


if __name__ == "__main__":
    main()