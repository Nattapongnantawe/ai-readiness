# -*- coding: utf-8 -*-
"""
main.py — JobBKK Single-Pass Scraper

รัน:
  python main.py              ดึงงาน (รันซ้ำได้ ไม่ดึงงานเดิม)
  python main.py --new        ดึงเฉพาะงานใหม่
  python main.py --check URL  ตรวจว่าหน้านั้นดึงอะไรได้บ้าง
  python main.py --retry      ดึงซ้ำเฉพาะงานที่เคยพลาด
  python main.py --links      ตรวจว่าหน้ารายการเก็บลิงก์ได้ครบไหม (debug)
  python main.py --fix-dates  ซ่อมวันที่ประกาศที่ผิด (ดึงเฉพาะหน้าที่มีปัญหา)

ตัวเลือกเสริม (ใช้ร่วมกับด้านบนได้ — ดู polite.py):
  --auto       โหมดรันอัตโนมัติจากระบบ: หน่วง 12–15 วินาที/request
  --url URL    ใช้หน้ารายการนี้แทน LISTING_URL ใน config.py
  ทุกโหมดตรวจ robots.txt ก่อนเปิดหน้าเสมอ
"""
import json
import os
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import config
import polite


def _browser(p):
    b = p.chromium.launch(headless=config.HEADLESS)
    ctx = b.new_context(user_agent=config.USER_AGENT, locale="th-TH")
    page = ctx.new_page()
    page.set_default_timeout(config.PAGE_TIMEOUT)
    return b, page


def check(url: str) -> None:
    """ตรวจหน้าเดียว — ไม่ต้องเปิดเบราว์เซอร์ (หน้ารายละเอียดเป็น server-rendered)"""
    from scraper import scrape_one
    job = scrape_one(url.split("?")[0])
    if not job:
        print("เปิดหน้าไม่สำเร็จ")
        return
    d = job.to_dict()
    print("\n" + "=" * 62)
    for k, v in d.items():
        if isinstance(v, list):
            print(f"{k:22}: {len(v)} รายการ")
        elif isinstance(v, dict):
            print(f"{k:22}: {len(v)} ค่า -> {list(v)[:5]}")
        elif v:
            print(f"{k:22}: {str(v)[:88].replace(chr(10), ' ⏎ ')}")
        else:
            print(f"{k:22}: — (ว่าง)")
    print("=" * 62)
    os.makedirs(config.DATA_DIR, exist_ok=True)
    out = os.path.join(config.DATA_DIR, "sample_job.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print(f"\nบันทึกตัวอย่างเต็ม -> {out}")


def retry() -> None:
    """ดึงซ้ำเฉพาะงานที่เคยพลาด พร้อมบอกเหตุผลว่าทำไมยังไม่สำเร็จ"""
    from scraper import scrape_one
    from scope import in_scope
    from fetch import (load_existing, append_jsonl, write_json_array,
                       log_failed, url_hash, polite_delay)
    if not os.path.exists(config.FAILED_PATH):
        print("ไม่มีงานค้างใน failed.jsonl")
        return
    urls, seen = [], set()
    with open(config.FAILED_PATH, encoding="utf-8") as f:
        for ln in f:
            try:
                u = json.loads(ln).get("url")
            except json.JSONDecodeError:
                continue
            if u and u not in seen:
                seen.add(u)
                urls.append(u)

    done = load_existing(config.JSONL_PATH)
    todo = [u for u in urls
            if url_hash(u) not in done or not done[url_hash(u)].get("job_description")]
    print(f"งานค้าง {len(urls)} | ต้องดึงซ้ำ {len(todo)}\n")

    os.remove(config.FAILED_PATH)
    ok = partial = gone = out = 0
    for i, u in enumerate(todo, 1):
        job = scrape_one(u)
        if job is None:
            gone += 1
            reason = "เปิดหน้าไม่ได้ (ประกาศอาจหมดอายุ/ถูกลบ)"
            log_failed(u, reason, config.FAILED_PATH)
            print(f"  [{i}/{len(todo)}] ✗ {reason}")
        elif job.is_usable() and not in_scope(job.to_dict())[0]:
            out += 1
            d = job.to_dict()
            append_jsonl({**d, "_reason": in_scope(d)[1]}, config.OUT_OF_SCOPE_PATH)
            print(f"  [{i}/{len(todo)}] ⊘ {in_scope(d)[1]}")
        elif job.is_complete():
            done[url_hash(u)] = job.to_dict()
            append_jsonl(job.to_dict(), config.JSONL_PATH)
            ok += 1
            print(f"  [{i}/{len(todo)}] ✓ {job.job_title[:45]}")
        else:
            partial += 1
            miss = ", ".join(job.missing_fields())
            reason = f"หน้าเปิดได้ แต่ไม่มี: {miss}"
            log_failed(u, reason, config.FAILED_PATH)
            # เก็บเท่าที่ได้ไว้ ดีกว่าไม่มีเลย
            if job.is_usable():
                done[url_hash(u)] = job.to_dict()
                append_jsonl(job.to_dict(), config.JSONL_PATH)
            print(f"  [{i}/{len(todo)}] ⚠ {reason} | {job.job_title[:30]}")
            print(f"        {u}")
        if i < len(todo):
            polite_delay("งานถัดไป")

    write_json_array(list(done.values()), config.JSON_PATH)
    print(f"\nสำเร็จ {ok} | ได้ไม่ครบ {partial} | เปิดไม่ได้ {gone} | นอกสาย {out}")
    print(f"รวมในไฟล์ {len(done)} รายการ")
    if partial:
        print("\nงานที่ 'ได้ไม่ครบ' ลองตรวจด้วย:  python main.py --check <URL ด้านบน>")


def fix_dates() -> None:
    """
    ซ่อม post_date ที่เก็บผิด (เคยได้ชื่อตำแหน่งมาแทนวันที่)
    ดึงซ้ำเฉพาะงานที่วันที่ไม่ถูกต้อง แล้วแก้ในไฟล์เดิม — ไม่ต้องดึงใหม่ทั้งหมด
    """
    import shutil
    from datetime import datetime
    from fetch import (get_soup, job_posting_jsonld, page_text, polite_delay,
                       load_existing, write_json_array)
    from bkk_parse import parse_labels, looks_like_date
    from scraper import _post_date

    done = load_existing(config.JSONL_PATH)
    bad = [h for h, d in done.items() if not looks_like_date(d.get("post_date", ""))]
    print(f"งานทั้งหมด {len(done)} | วันที่ผิด/ว่าง {len(bad)} งาน\n")
    if not bad:
        print("ไม่มีอะไรต้องซ่อม ✓")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = os.path.join(config.DATA_DIR, f"backup_dates_{stamp}")
    os.makedirs(bak, exist_ok=True)
    for p in (config.JSONL_PATH, config.JSON_PATH):
        if os.path.exists(p):
            shutil.copy2(p, bak)
    print(f"💾 สำรองไว้ที่ {bak}\n")

    fixed = still = 0
    try:
        for i, h in enumerate(bad, 1):
            d = done[h]
            old = d.get("post_date", "")
            soup = get_soup(d["source_url"])
            new = ""
            if soup:
                jp = job_posting_jsonld(soup)            # ต้องก่อน page_text
                new = _post_date(jp, parse_labels(page_text(soup)))
            if new:
                d["post_date"] = new
                fixed += 1
                print(f"  [{i}/{len(bad)}] ✓ {str(old)[:22]:24} -> {new}")
            else:
                d["post_date"] = ""                      # ล้างค่าผิดทิ้ง ดีกว่าเก็บชื่องานไว้
                still += 1
                print(f"  [{i}/{len(bad)}] ✗ หาวันที่ไม่เจอ ({str(old)[:22]}) -> ล้างเป็นค่าว่าง")
            if i < len(bad):
                polite_delay("งานถัดไป")
    except KeyboardInterrupt:
        print("\nหยุดด้วย Ctrl+C — บันทึกเท่าที่ซ่อมได้")

    # เขียนไฟล์ใหม่ (jsonl ต้องเขียนทับทั้งไฟล์ เพราะแก้ข้อมูลเดิม)
    with open(config.JSONL_PATH, "w", encoding="utf-8") as f:
        for d in done.values():
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    write_json_array(list(done.values()), config.JSON_PATH)
    print(f"\nซ่อมได้ {fixed} | หาไม่เจอ {still} | รวม {len(done)} งาน")


def main() -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    args = polite.apply_cli(sys.argv[1:])

    if args and args[0] == "--check":
        if len(args) < 2:
            print("ใช้: python main.py --check https://www.jobbkk.com/jobs/detailurgent/223452/1265807")
            return
        check(args[1])
        return

    if args and args[0] == "--retry":
        retry()
        return

    if args and args[0] == "--fix-dates":
        fix_dates()
        return

    if args and args[0] == "--links":
        from playwright.sync_api import sync_playwright
        from scraper import diagnose
        with sync_playwright() as p:
            b, page = _browser(p)
            try:
                diagnose(page)
            finally:
                b.close()
        return

    if args and args[0] == "--new":
        config.INCREMENTAL = True

    from playwright.sync_api import sync_playwright
    from scraper import run

    print(f"โหมด: {'เฉพาะงานใหม่' if config.INCREMENTAL else 'ดึงเต็ม'} | "
          f"เป้าหมาย: {config.MAX_JOBS or 'ไม่จำกัด'} งาน")
    print("หน้ารายการ: Playwright | หน้ารายละเอียด: requests (เร็วกว่า)")
    polite.check_start(config.LISTING_URL)
    print()

    with sync_playwright() as p:
        b, page = _browser(p)
        try:
            run(page)
        finally:
            b.close()

    print(f"\n{'=' * 50}\n✅ เสร็จสิ้น")
    print(f"   {config.JSONL_PATH}   (ทีละบรรทัด กันข้อมูลหาย)")
    print(f"   {config.JSON_PATH}   (JSON array สำหรับ pipeline)")
    if os.path.exists(config.FAILED_PATH):
        print(f"   {config.FAILED_PATH}   ← มีงานค้าง รันซ้ำ: python main.py --retry")


if __name__ == "__main__":
    main()