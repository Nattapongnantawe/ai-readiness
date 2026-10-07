# -*- coding: utf-8 -*-
"""
rescue_scope.py — ดึงงานที่ "เคยถูกตัดทิ้ง" กลับมา หลังขยาย config.SCOPE
(คู่กับ clean_scope.py ที่ทำทางตรงข้าม)

จำเป็นเพราะ scraper.py ข้าม URL ที่อยู่ใน out_of_scope.jsonl
→ รัน main.py ใหม่จะไม่ดึงงานพวกนี้กลับมาเอง

รัน:
  python rescue_scope.py            ดูผลก่อน (ไม่แก้ไฟล์)
  python rescue_scope.py --apply    แก้ไฟล์จริง (สำรองของเดิมไว้ให้อัตโนมัติ)
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


def key(r):
    return r.get("url_hash") or r.get("source_url")


def main():
    apply = "--apply" in sys.argv

    jobs = {key(r): r for r in load_jsonl(config.JSONL_PATH)}
    oos = {key(r): r for r in load_jsonl(config.OUT_OF_SCOPE_PATH)}  # ตัดซ้ำในตัว

    rescue, still_out = [], []
    for k, r in oos.items():
        if k in jobs:
            continue                      # มีอยู่แล้ว ไม่ต้องดึงกลับ
        ok, _ = in_scope(r)
        (rescue if ok else still_out).append(r)

    print(f"ขอบเขตที่ตั้งไว้: {config.SCOPE}\n")
    print(f"jobs.jsonl เดิม      : {len(jobs)} งาน")
    print(f"out_of_scope (ไม่ซ้ำ): {len(oos)} งาน")
    print(f"ดึงกลับได้          : {len(rescue)} งาน")
    print(f"รวมหลังดึงกลับ       : {len(jobs) + len(rescue)} งาน\n")

    c = collections.Counter(" / ".join(x for x in job_category(r) if x) or "?"
                            for r in rescue)
    for k, v in c.most_common():
        print(f"  {v:5}  {k}")

    if not apply:
        print("\n(ยังไม่ได้แก้ไฟล์) ถ้าโอเคแล้วรัน:  python rescue_scope.py --apply")
        return
    if not rescue:
        print("\nไม่มีงานให้ดึงกลับ")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = os.path.join(config.DATA_DIR, f"backup_rescue_{stamp}")
    os.makedirs(bak, exist_ok=True)
    for p in (config.JSONL_PATH, config.JSON_PATH, config.OUT_OF_SCOPE_PATH):
        if os.path.exists(p):
            shutil.copy2(p, bak)
    print(f"\n💾 สำรองของเดิมไว้ที่ {bak}")

    for r in rescue:
        r = {k: v for k, v in r.items() if k != "_reason"}
        jobs[key(r)] = r
    rows = list(jobs.values())

    with open(config.JSONL_PATH, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(config.JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    with open(config.OUT_OF_SCOPE_PATH, "w", encoding="utf-8") as f:
        for r in still_out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"✅ {config.JSONL_PATH} / {config.JSON_PATH}  -> {len(rows)} งาน")
    print(f"   out_of_scope เหลือ {len(still_out)} งาน")


if __name__ == "__main__":
    main()
