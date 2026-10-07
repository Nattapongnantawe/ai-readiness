# -*- coding: utf-8 -*-
"""
polite.py — ความสุภาพต่อเว็บไซต์ (ใช้ไฟล์เดียวกันทั้ง JobThai และ JobBKK)

1) robots.txt : อ่านครั้งเดียวต่อโดเมน แล้วตรวจทุก URL ก่อนเปิด
                - ไม่อนุญาต  -> ไม่เปิดหน้านั้น (หน้ารายการไม่อนุญาต = หยุดทั้งรอบ, exit code 3)
                - มี Crawl-delay มากกว่าค่าหน่วงเดิม -> ใช้ค่าจาก robots.txt
                - ไม่มีไฟล์ (404)   -> ถือว่าอนุญาต (ตามมาตรฐาน)
                - 401/403          -> ถือว่าไม่อนุญาตทั้งเว็บ
                - อ่านไม่ได้เลย (เน็ต/เว็บล่ม) -> หยุดรอบนี้ ไม่เดาเอง (exit code 3)
2) --auto     : โหมดรันอัตโนมัติจากระบบ (Module 4) หน่วง 4–7 วินาทีต่อ request (สุ่ม)
                --delay 4-7 เปลี่ยนช่วงหน่วงได้ (ต่ำสุด 2 วินาที) · รันเองด้วยมือใช้ค่าใน config.py
   ปรับความเร็วเอง: ถ้าเว็บตอบ 429/503 (ขอถี่ไป) 5xx หรือ timeout จะหน่วงเพิ่มเป็น 2 เท่า
                (สูงสุด 60 วินาที) จนจบรอบ — ช้าลงทันทีที่เว็บเริ่มอึดอัด ไม่ฝืนจนโดนบล็อก
   ไม่โหลดฟอนต์/วิดีโอ (block_heavy) — หน้าเว็บโหลดเร็วขึ้นและเบาต่อเซิร์ฟเวอร์ ข้อความ/รูปยังครบ
3) --url URL  : เปลี่ยนหน้ารายการชั่วคราว (ไม่ต้องแก้ config.py) ใช้วนหลายหมวดในรอบเดียว
4) --max-updates N / --cards : ตรวจงานที่ถูกอัปเดต (ดู freshness.py)
5) --stop-after N : โหมด --new หยุดเมื่อเจองานเดิมติดกัน N งาน (ค่าเดิมใน config.py = 40)
                เว็บที่บริษัท "ดัน" ประกาศเก่าขึ้นบนสุดได้ ต้องใช้ N มากขึ้น ไม่งั้นหยุดก่อนเจองานใหม่
                งานเดิมถูกข้ามโดยไม่เปิดหน้ารายละเอียด เสียแค่เวลาเปิดหน้ารายการเพิ่ม
"""
import sys
import urllib.error
import urllib.request
import urllib.robotparser
from urllib.parse import urlsplit

import config

AUTO_MIN_DELAY = 4.0
AUTO_MAX_DELAY = 7.0
FLOOR_DELAY = 2.0          # --delay ต่ำกว่านี้ไม่ได้
SLOW_MAX_DELAY = 60.0      # หน่วงสูงสุดเมื่อเว็บส่งสัญญาณให้ช้าลง
EXIT_ROBOTS = 3
_slowdowns = 0

_parsers = {}


def apply_cli(argv):
    """ดึงตัวเลือก --auto / --url ออกจาก argv แล้วคืนตัวเลือกที่เหลือให้ main.py ใช้ตามเดิม"""
    rest, i = [], 0
    config.AUTO = False
    config.SHOW_CARDS = False
    while i < len(argv):
        a = argv[i]
        if a == "--auto":
            config.AUTO = True
            config.HEADLESS = True
            config.MIN_DELAY, config.MAX_DELAY = AUTO_MIN_DELAY, AUTO_MAX_DELAY
        elif a == "--delay" and i + 1 < len(argv):
            lo, _, hi = argv[i + 1].partition("-")
            lo = max(FLOOR_DELAY, float(lo))
            config.MIN_DELAY, config.MAX_DELAY = lo, max(lo, float(hi or lo + 3))
            i += 1
        elif a == "--url" and i + 1 < len(argv):
            config.LISTING_URL = argv[i + 1]
            i += 1
        elif a == "--stop-after" and i + 1 < len(argv):
            config.STOP_AFTER_KNOWN = max(1, int(argv[i + 1]))
            i += 1
        elif a == "--max-updates" and i + 1 < len(argv):
            config.MAX_UPDATES = max(0, int(argv[i + 1]))
            i += 1
        elif a == "--cards":
            config.SHOW_CARDS = True
            config.INCREMENTAL = True     # ใช้ทางเดิมของ --new แต่หยุดหลังแสดงการ์ดหน้าแรก
        else:
            rest.append(a)
        i += 1
    return rest


def _parser(url):
    p = urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base in _parsers:
        return _parsers[base]
    rp = urllib.robotparser.RobotFileParser()
    req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            rp.parse(r.read().decode("utf-8", "replace").splitlines())
        note = "อ่าน robots.txt แล้ว"
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            rp.disallow_all = True
            note = f"robots.txt ตอบ {e.code} -> ถือว่าไม่อนุญาต"
        else:
            rp.allow_all = True
            note = f"ไม่มี robots.txt ({e.code}) -> อนุญาต"
    except Exception as e:  # noqa: BLE001
        print(f"⛔ อ่าน {base}/robots.txt ไม่ได้ ({str(e)[:80]}) — หยุดรอบนี้เพื่อความปลอดภัย")
        sys.exit(EXIT_ROBOTS)

    delay = None
    try:
        delay = rp.crawl_delay(config.USER_AGENT) or rp.crawl_delay("*")
    except Exception:  # noqa: BLE001
        pass
    if delay and float(delay) > config.MIN_DELAY:
        config.MIN_DELAY = float(delay)
        config.MAX_DELAY = max(config.MAX_DELAY, float(delay) + 3)
        note += f" | Crawl-delay {delay}s"
    print(f"🤖 {base}: {note}")
    _parsers[base] = rp
    return rp


def slow_down(reason: str) -> None:
    """เว็บส่งสัญญาณว่าเราขอถี่ไป (429/503/5xx/timeout): หน่วงเพิ่ม 2 เท่าจนจบรอบ"""
    global _slowdowns
    _slowdowns += 1
    new_min = min(SLOW_MAX_DELAY, max(config.MIN_DELAY * 2, 10.0))
    if new_min > config.MIN_DELAY:
        config.MIN_DELAY, config.MAX_DELAY = new_min, min(SLOW_MAX_DELAY + 5, new_min + 5)
        print(f"   🐢 {reason} — ชะลอเป็น {config.MIN_DELAY:.0f}–{config.MAX_DELAY:.0f} วินาที/request จนจบรอบ")


def block_heavy(ctx) -> None:
    """ไม่โหลดฟอนต์และวิดีโอ (ไม่ใช้ในการดึงข้อมูล) — เร็วขึ้นและเบาต่อเซิร์ฟเวอร์ปลายทาง"""
    try:
        ctx.route("**/*", lambda route: route.abort()
                  if route.request.resource_type in ("font", "media") else route.continue_())
    except Exception:  # noqa: BLE001
        pass


def allowed(url: str) -> bool:
    """True ถ้า robots.txt อนุญาตให้เปิด url นี้"""
    return _parser(url).can_fetch(config.USER_AGENT, url)


def check_start(listing_url: str) -> None:
    """เรียกก่อนเริ่มดึง: หน้ารายการต้องได้รับอนุญาต ไม่งั้นหยุดทั้งรอบ"""
    if not allowed(listing_url):
        print(f"⛔ robots.txt ไม่อนุญาตหน้ารายการ: {listing_url}")
        sys.exit(EXIT_ROBOTS)
    mode = "อัตโนมัติ" if getattr(config, "AUTO", False) else "รันเอง"
    print(f"⏱ โหมด{mode}: หน่วง {config.MIN_DELAY:.0f}–{config.MAX_DELAY:.0f} วินาทีต่อ request"
          + (f" | --new หยุดเมื่อเจองานเดิมติดกัน {config.STOP_AFTER_KNOWN} งาน" if getattr(config, "INCREMENTAL", False) else ""))