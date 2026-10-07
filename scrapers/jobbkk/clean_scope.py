# -*- coding: utf-8 -*-
"""
clean_scope.py — กรองงานนอกสายงานออกจากข้อมูลที่ดึงมาแล้ว (ไม่ต้องดึงใหม่)

ใช้กับข้อมูลที่ดึงก่อนมีด่านตรวจสาขา เช่นตอนที่ pagination วนแล้วเก็บงานแนะนำปนมา

รัน:
  python clean_scope.py            ดูผลก่อน (ไม่แก้ไฟล์)
  python clean_scope.py --apply    แก้ไฟล์จริง (สำรองของเดิมไว้ให้อัตโนมัติ)
"""
import collections
import json
import os
import shutil
import sys
from datetime import datetime

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config
from scope import in_scope, job_category


def load_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                try:
                    rows.append(json.loads(ln))
                except json.JSONDecodeError:
                    pass
    return rows


def main():
    apply = "--apply" in sys.argv
    rows = load_jsonl(config.JSONL_PATH)
    if not rows:
        print(f"ไม่พบข้อมูลใน {config.JSONL_PATH}")
        return

    # ตัดซ้ำก่อน (กันไฟล์ jsonl มีบรรทัดซ้ำจากการรันหลายรอบ)
    uniq = {}
    for r in rows:
        uniq[r.get("url_hash") or r.get("source_url")] = r
    rows = list(uniq.values())

    keep, drop = [], []
    for r in rows:
        ok, why = in_scope(r)
        (keep if ok else drop).append((r, why))

    print(f"ขอบเขตที่ตั้งไว้: {config.SCOPE}\n")
    print(f"ทั้งหมด     : {len(rows)} งาน")
    print(f"เก็บไว้     : {len(keep)} งาน")
    print(f"ตัดออก      : {len(drop)} งาน\n")

    print("── เก็บไว้ (แยกตามสาขา) ──")
    c = collections.Counter(" / ".join(x for x in job_category(r) if x) or "?" for r, _ in keep)
    for k, v in c.most_common():
        print(f"  {v:5}  {k}")

    print("\n── ตัดออก (10 อันดับแรก) ──")
    c = collections.Counter(why for _, why in drop)
    for k, v in c.most_common(10):
        print(f"  {v:5}  {k}")

    # งานวิศวกรรมแยกตามสาขารอง — จะได้เห็นว่ามีวิศวกรคอมพิวเตอร์กี่งาน
    eng = collections.Counter(job_category(r)[1] or "?" for r in rows
                              if job_category(r)[0] == "วิศวกรรม")
    if eng:
        print("\n── วิศวกรรม แยกตามสาขารอง ──")
        for k, v in eng.most_common():
            mark = "✓" if k in (config.SCOPE.get("วิศวกรรม") or []) else "✗"
            print(f"  {mark} {v:4}  {k}")

    if not apply:
        print("\n(ยังไม่ได้แก้ไฟล์) ถ้าโอเคแล้วรัน:  python clean_scope.py --apply")
        return

    # ---- สำรองของเดิม ----
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = os.path.join(config.DATA_DIR, f"backup_{stamp}")
    os.makedirs(bak, exist_ok=True)
    for p in (config.JSONL_PATH, config.JSON_PATH):
        if os.path.exists(p):
            shutil.copy2(p, bak)
    print(f"\n💾 สำรองของเดิมไว้ที่ {bak}")

    # ---- เขียนไฟล์ใหม่ ----
    with open(config.JSONL_PATH, "w", encoding="utf-8") as f:
        for r, _ in keep:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(config.JSON_PATH, "w", encoding="utf-8") as f:
        json.dump([r for r, _ in keep], f, ensure_ascii=False, indent=2)
    with open(config.OUT_OF_SCOPE_PATH, "a", encoding="utf-8") as f:
        for r, why in drop:
            f.write(json.dumps({**r, "_reason": why}, ensure_ascii=False) + "\n")

    print(f"✅ {config.JSONL_PATH} / {config.JSON_PATH}  -> {len(keep)} งาน")
    print(f"   งานที่ตัดออก {len(drop)} งาน อยู่ใน {config.OUT_OF_SCOPE_PATH}")
    print("   (รัน main.py ซ้ำจะไม่ดึงงานพวกนี้กลับมาอีก)")


if __name__ == "__main__":
    main()
