# -*- coding: utf-8 -*-
r"""
Module 2 แบบไม่ใช้ฐานข้อมูล: raw JSON (scraper) -> Gemini -> structured JSON

  python -m extractor.run_json --input data\jobthai_sample.json --input data\jobbkk_sample.json
  python -m extractor.run_json --input "C:\...\jobs_data.json" --limit 10 --output output\test.json
"""
import argparse
import json
import os

from adapters import adapt
from load import read_json

from . import config
from .gemini_client import GeminiExtractor, QuotaExhausted
from .merge import enrich
from .normalize import SkillNormalizer
from .preprocess import build_job_payload, clean_text
from .run import validate
from .schemas import BulletOut, ItemCategory, SkillOut


def read_any(path: str) -> list:
    """รองรับ: งานเดียว {...}, array [...], dict ของหลายงาน, .jsonl"""
    with open(path, encoding="utf-8") as f:
        head = f.read(1)
    if head == "{" and not path.endswith(".jsonl"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return [data] if ("job_title" in data or "url_hash" in data) else list(data.values())
    return read_json(path)


def to_jobs(rows: list) -> list:
    out, item_id = [], 1
    for n, raw in enumerate(rows, 1):
        rec = adapt(raw)
        job = {"id": n, "title": rec["title"], "experience_years": rec["experience_years"],
               "attributes": rec["attributes"]}
        items = []
        for it in rec["requirement_items"]:
            items.append({"id": item_id, **it})
            item_id += 1
        out.append((job, items, rec))
    return out


def dump_compact(o, ind=0) -> str:
    """object ที่ข้างในไม่มี dict/list ซ้อน -> เขียนบรรทัดเดียว"""
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


def build_output(rec, r, items, header_ids, years, norm) -> dict:
    cats = {it.item_id: it for it in r.items}
    text = {it["id"]: it["content"] for it in items}
    bullets, skipped = [], []
    for it in items:
        if it["id"] in header_ids:                     # C3: หัวข้อไม่เข้า output/DB
            skipped.append(it["content"])
            continue
        c = cats.get(it["id"])
        cleaned = clean_text(it["content"])
        bullets.append(BulletOut(
            source=it["source"],
            category=c.category if c else ItemCategory.other,
            confidence=round(c.confidence, 2) if c else None,
            text=it["content"],
            cleaned=cleaned if cleaned != it["content"] else None,
        ).model_dump(mode="json", exclude_none=True))

    hard, soft, seen = [], [], set()
    for sk in r.skills:
        canon, key, _ = norm.canonical(sk.name)
        if not key or key in seen or norm.is_generic(sk.name):
            continue
        seen.add(key)
        s = SkillOut(name=canon, name_norm=key, type=sk.skill_type, group=sk.group,
                     required=sk.is_required, from_text=text.get(sk.item_id),
                     raw_name=sk.name if sk.name != canon else None
                     ).model_dump(mode="json", exclude_none=True)
        (soft if s["type"] == "soft" else hard).append(s)

    edu = rec["education_level"]
    out = {
        "source_url": rec["source_url"],
        "job_info": {
            "title": rec["title"], "company": rec["company_name"],
            "province": rec["province"], "district": rec["district"],
            "salary_type": rec["salary_type"], "salary_min": rec["salary_min"],
            "salary_max": rec["salary_max"],
            "salary_period": rec.get("salary_period", "month"),   # หน่วยเดิม (min/max แปลงเป็นต่อเดือนแล้ว)
            "posted_date": str(rec["posted_date"]) if rec["posted_date"] else None,
            "experience_years": years,
            "education_level": clean_text(edu) if edu else None,
            "seniority": r.seniority.value, "work_mode": r.work_mode.value,
        },
        "classified_bullets": bullets,
        "hard_skills": hard,
        "soft_skills": soft,
    }
    if skipped:
        out["skipped_headers"] = skipped
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True)
    ap.add_argument("--output", default=os.path.join("output", "structured.json"))
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--batch-size", type=int, default=config.BATCH_SIZE)
    ap.add_argument("--match", help="คัดเฉพาะงานที่ชื่อตำแหน่ง/หมวดตรงกับ regex เช่น 'ไฟฟ้า|อิเล็ก|electric'")
    ap.add_argument("--sample", action="store_true", help="สุ่มงาน (แทนการเอา N งานแรก)")
    ap.add_argument("--seed", type=int, default=42, help="เลขสุ่ม — ใช้ค่าเดิมจะได้ชุดเดิมเสมอ")
    a = ap.parse_args()

    rows = []
    for path in a.input:
        rows.extend(read_any(path))
    if a.match:
        import re as _re
        pat = _re.compile(a.match, _re.I)

        def _hay(r):
            attrs = r.get("attributes") or {}
            return " ".join(str(x) for x in (
                r.get("job_title"), r.get("title"), r.get("job_category"), r.get("category"),
                attrs.get("สาขาอาชีพหลัก"), attrs.get("สาขาอาชีพรอง"), attrs.get("ประเภทธุรกิจ")) if x)
        before = len(rows)
        rows = [r for r in rows if pat.search(_hay(r))]
        print(f"🔎 --match '{a.match}': {len(rows)} จาก {before} งาน")
    if a.sample:
        import random as _random
        _random.Random(a.seed).shuffle(rows)
    jobs = to_jobs(rows[:a.limit])
    n_items = sum(len(i) for _, i, _ in jobs)
    print(f"📄 อ่านได้ {len(jobs)} งาน | bullet เฉลี่ย {n_items / max(len(jobs), 1):.1f}/งาน "
          f"| model={config.GEMINI_MODEL}")

    llm = GeminiExtractor(config.GEMINI_API_KEY, config.GEMINI_MODEL, config.GEMINI_RPM)
    norm = SkillNormalizer()
    results = []

    try:
        for i in range(0, len(jobs), a.batch_size):
            chunk = jobs[i:i + a.batch_size]
            payloads, headers = {}, {}
            for job, items, _ in chunk:
                payloads[job["id"]], headers[job["id"]] = build_job_payload(job, items)
            try:
                res = validate(llm.extract(list(payloads.values())), payloads)
            except QuotaExhausted:
                raise
            except Exception as e:                       # noqa: BLE001
                print(f"  ✗ batch {i // a.batch_size + 1} ล้มเหลว: {str(e)[:150]}")
                continue

            for job, items, rec in chunk:
                r = res.get(job["id"])
                if r is None:
                    print(f"  ✗ {rec['title'][:50]}: LLM ไม่คืนผล")
                    continue
                body = [it for it in items if it["id"] not in headers[job["id"]]]
                years = enrich(r, job, body, norm)
                out = build_output(rec, r, items, headers[job["id"]], years, norm)
                results.append(out)
                print(f"  ✓ {rec['title'][:50]}  -> {len(out['hard_skills'])} hard / "
                      f"{len(out['soft_skills'])} soft")
    except QuotaExhausted as e:
        print(f"⛔ quota เต็ม: {str(e)[:200]}")
    except KeyboardInterrupt:
        print("\n⏸ หยุดโดยผู้ใช้")
    finally:
        os.makedirs(os.path.dirname(a.output) or ".", exist_ok=True)
        with open(a.output, "w", encoding="utf-8") as f:
            f.write(dump_compact(results))
        print(f"\n💾 {a.output}  ({len(results)} งาน)")


if __name__ == "__main__":
    main()
