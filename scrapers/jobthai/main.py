# -*- coding: utf-8 -*-
"""
main.py — JobThai Single-Pass Scraper

รัน:
  python main.py              ดึงงาน (รันซ้ำได้ ไม่ดึงงานเดิม)
  python main.py --new        ดึงเฉพาะงานใหม่ (เจองานเดิมติดกันแล้วหยุด)
  python main.py --check URL  ตรวจว่าหน้านั้นดึงอะไรได้บ้าง (ใช้ตอน debug)
  python main.py --images URL แสดงรูปทั้งหมดในหน้า (ใช้ตอนโลโก้ดึงไม่ได้)
  python main.py --retry      ดึงซ้ำเฉพาะงานที่เคยพลาด (จาก failed.jsonl)

ตัวเลือกเสริม (ใช้ร่วมกับด้านบนได้ — ดู polite.py):
  --auto       โหมดรันอัตโนมัติจากระบบ: หน่วง 12–15 วินาที/request
  --url URL    ใช้หน้ารายการนี้แทน LISTING_URL ใน config.py (วนหลายหมวด)
  ทุกโหมดตรวจ robots.txt ก่อนเปิดหน้าเสมอ
"""
import os
import sys

from playwright.sync_api import sync_playwright

import config
import polite
from scraper import run

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _browser(p):
    b = p.chromium.launch(headless=config.HEADLESS)
    ctx = b.new_context(
        user_agent=config.USER_AGENT,
        extra_http_headers=config.DEFAULT_HEADERS,
        locale="th-TH",
    )
    page = ctx.new_page()
    page.set_default_timeout(config.PAGE_TIMEOUT)
    return b, page


def check(url: str) -> None:
    """เปิดหน้าเดียวแล้วโชว์ว่าดึงอะไรได้บ้าง — ใช้เวลาเว็บเปลี่ยนโครงสร้าง"""
    import json
    from scraper import scrape_one
    with sync_playwright() as p:
        b, page = _browser(p)
        try:
            job = scrape_one(page, url.split("?")[0])
            if not job:
                print("เปิดหน้าไม่สำเร็จ")
                return
            d = job.to_dict()
            print("\n" + "=" * 60)
            for k, v in d.items():
                if isinstance(v, list):
                    print(f"{k:22}: {len(v)} รายการ")
                elif v:
                    s = str(v).replace("\n", " ⏎ ")
                    print(f"{k:22}: {s[:90]}")
                else:
                    print(f"{k:22}: — (ว่าง)")
            print("=" * 60)
            os.makedirs(config.DATA_DIR, exist_ok=True)
            out = os.path.join(config.DATA_DIR, "sample_job.json")
            with open(out, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
            print(f"\nบันทึกตัวอย่างเต็ม → {out}")
        finally:
            b.close()


def show_images(url: str) -> None:
    """แสดงรูปทั้งหมดในหน้า — ใช้หาสาเหตุเวลา company_logo_url เป็น null"""
    from extract import list_images, grab_logo
    with sync_playwright() as p:
        b, page = _browser(p)
        try:
            page.goto(url.split("?")[0], timeout=config.PAGE_TIMEOUT,
                      wait_until="domcontentloaded")
            page.wait_for_timeout(2500)          # รอรูปที่โหลดแบบ lazy
            page.mouse.wheel(0, 600)             # เลื่อนกระตุ้น lazy load
            page.wait_for_timeout(1500)
            imgs = list_images(page)
            print(f"\nพบรูปทั้งหมด {len(imgs)} รูป\n" + "=" * 70)
            for i, im in enumerate(imgs, 1):
                print(f"[{i}] id={im['id'] or '-'}  ขนาด={im['w']}x{im['h']}")
                print(f"    src     : {im['src'] or '-'}")
                if im["dataSrc"]:
                    print(f"    data-src: {im['dataSrc']}")
                if im["srcset"]:
                    print(f"    srcset  : {im['srcset']}")
                if im["alt"]:
                    print(f"    alt     : {im['alt']}")
            print("=" * 70)
            print(f"\nโค้ดเลือกได้: {grab_logo(page)}")
        finally:
            b.close()


def main() -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    args = polite.apply_cli(sys.argv[1:])

    if args and args[0] == "--images":
        if len(args) < 2:
            print("ใช้: python main.py --images https://www.jobthai.com/th/company/job/123456")
            return
        show_images(args[1])
        return

    if args and args[0] == "--check":
        if len(args) < 2:
            print("ใช้: python main.py --check https://www.jobthai.com/th/company/job/123456")
            return
        check(args[1])
        return

    if args and args[0] == "--retry":
        from scraper import retry_failed
        with sync_playwright() as p:
            b, page = _browser(p)
            try:
                retry_failed(page)
            finally:
                b.close()
        return

    if args and args[0] == "--new":
        config.INCREMENTAL = True

    mode = "เฉพาะงานใหม่" if config.INCREMENTAL else "ดึงเต็ม"
    limit = config.MAX_JOBS or "ไม่จำกัด"
    print(f"โหมด: {mode} | เป้าหมาย: {limit} งาน")
    print(f"URL : {config.LISTING_URL}")
    polite.check_start(config.LISTING_URL)
    print()

    with sync_playwright() as p:
        b, page = _browser(p)
        try:
            run(page)
        finally:
            b.close()

    print(f"\n{'=' * 50}")
    print(f"✅ เสร็จสิ้น")
    print(f"   {config.JSONL_PATH}  (ทีละบรรทัด กันข้อมูลหาย)")
    print(f"   {config.JSON_PATH}  (JSON array สำหรับส่งงาน)")
    if os.path.exists(config.FAILED_PATH):
        print(f"   {config.FAILED_PATH}  ← มีงานที่ยังไม่สมบูรณ์ รันซ้ำด้วย: python main.py --retry")


if __name__ == "__main__":
    main()