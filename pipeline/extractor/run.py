# -*- coding: utf-8 -*-
"""
Module 2 — AI Skill Extraction (Gemini)

  python -m extractor.run --limit 10 --dry-run      # ทดสอบ ไม่เขียน DB
  python -m extractor.run --job-id 123 --dry-run    # ดูผลงานเดียว
  python -m extractor.run                           # รันทั้งหมด (ทำต่อจากจุดเดิมอัตโนมัติ)
  python -m extractor.run --force --limit 50        # ประมวลผลซ้ำ
"""
import argparse
import json
import time

from . import config
from .db import Repo
from .gemini_client import GeminiExtractor, QuotaExhausted
from .normalize import SkillNormalizer
from .preprocess import build_job_payload
from .merge import enrich


def validate(batch_result, payloads: dict) -> dict:
    """ตัดผลที่ LLM แต่ง job_id/item_id ขึ้นมาเอง"""
    out = {}
    for jr in batch_result.jobs:
        p = payloads.get(jr.job_id)
        if not p:
            continue
        valid_ids = {it["item_id"] for it in p["items"]}
        jr.items = [it for it in jr.items if it.item_id in valid_ids]
        for sk in jr.skills:
            if sk.item_id not in valid_ids:
                sk.item_id = None
        out[jr.job_id] = jr
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--batch-size", type=int, default=config.BATCH_SIZE)
    ap.add_argument("--job-id", type=int)
    ap.add_argument("--force", action="store_true", help="ประมวลผลงานที่ทำไปแล้วซ้ำ")
    ap.add_argument("--dry-run", action="store_true", help="ไม่เขียน DB แสดงผลอย่างเดียว")
    ap.add_argument("--export", metavar="FILE", help="บันทึก input+output เป็น JSON (ใช้ประกอบ ppt)")
    a = ap.parse_args()

    repo = Repo(config.DATABASE_URL)
    llm = GeminiExtractor(config.GEMINI_API_KEY, config.GEMINI_MODEL, config.GEMINI_RPM)
    normalizer = SkillNormalizer(repo.db_aliases())

    jobs = repo.pending_jobs(a.limit, a.force or bool(a.job_id), a.job_id)
    print(f"🔎 งานที่ต้องประมวลผล: {len(jobs)}  | model={config.GEMINI_MODEL} "
          f"batch={a.batch_size} rpm={config.GEMINI_RPM}")

    done = skills = failed = 0
    exported = []
    t0 = time.time()
    try:
        for i in range(0, len(jobs), a.batch_size):
            chunk = jobs[i:i + a.batch_size]
            items = repo.items_for([j["id"] for j in chunk])

            payloads, headers = {}, {}
            for j in chunk:
                p, h = build_job_payload(j, items[j["id"]])
                payloads[j["id"]], headers[j["id"]] = p, h

            try:
                res = validate(llm.extract(list(payloads.values())), payloads)
            except QuotaExhausted:
                raise
            except Exception as e:                      # noqa: BLE001
                failed += len(chunk)
                print(f"  ✗ batch {i // a.batch_size + 1} ล้มเหลว: {str(e)[:150]}")
                continue

            for j in chunk:
                r = res.get(j["id"])
                if r is None:
                    failed += 1
                    print(f"  ✗ job {j['id']}: LLM ไม่คืนผล")
                    continue
                years = enrich(r, j, [i for i in items[j["id"]] if i["id"] not in headers[j["id"]]], normalizer)
                rec = {"input": payloads[j["id"]], "output": r.model_dump(mode="json")}
                if a.export:
                    exported.append(rec)
                if a.dry_run:
                    print(json.dumps(rec, ensure_ascii=False, indent=2))
                    done += 1
                    continue
                try:
                    skills += repo.save_job(j["id"], r, headers[j["id"]], normalizer, config.GEMINI_MODEL, years)
                    done += 1
                except Exception as e:                  # noqa: BLE001
                    failed += 1
                    print(f"  ✗ job {j['id']} บันทึกไม่ได้: {str(e)[:150]}")

            el = time.time() - t0
            print(f"  [{min(i + a.batch_size, len(jobs))}/{len(jobs)}] สำเร็จ {done} "
                  f"ล้มเหลว {failed} skills {skills}  ({el / 60:.1f} นาที)")
    except QuotaExhausted as e:
        print(f"\n⛔ quota เต็ม: {e}\n   รันคำสั่งเดิมอีกครั้งภายหลัง จะทำต่อจากงานที่ค้างอัตโนมัติ")
    except KeyboardInterrupt:
        print("\n⏸ หยุดโดยผู้ใช้ — งานที่บันทึกแล้วไม่หาย รันใหม่จะทำต่อ")
    finally:
        repo.close()
        if a.export and exported:
            with open(a.export, "w", encoding="utf-8") as f:
                json.dump(exported, f, ensure_ascii=False, indent=2)
            print(f"💾 structured JSON -> {a.export} ({len(exported)} งาน)")

    print(f"\n✅ สำเร็จ {done} | ล้มเหลว {failed} | skills ที่ผูกกับงาน {skills}")


if __name__ == "__main__":
    main()
