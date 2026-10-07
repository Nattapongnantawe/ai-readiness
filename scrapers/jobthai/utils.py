# -*- coding: utf-8 -*-
"""utils.py — ความสุภาพต่อเซิร์ฟเวอร์ + อ่าน/เขียนไฟล์"""
import hashlib
import json
import os
import random
import time
from typing import Dict, List

from playwright.sync_api import Page, TimeoutError as PWTimeout

import config
from models import Job


# ---------------- ระบุงานแบบไม่ซ้ำ ----------------
def url_hash(url: str) -> str:
    clean = (url or "").split("?")[0].rstrip("/")
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


# ---------------- ความสุภาพ ----------------
def polite_delay(reason: str = "") -> None:
    secs = random.uniform(config.MIN_DELAY, config.MAX_DELAY)
    print(f"   ⏳ หน่วง {secs:.1f}s{f' ({reason})' if reason else ''}")
    time.sleep(secs)


def _retry_after(resp) -> int:
    try:
        return int(resp.headers.get("retry-after", "0"))
    except Exception:
        return 0


def safe_goto(page: Page, url: str, wait_selector: str = "") -> bool:
    """เปิดหน้าแบบสุภาพ: ตรวจ robots.txt + จัดการ 429 / 5xx / timeout พร้อม retry"""
    import polite
    if not polite.allowed(url):
        print(f"   ⛔ robots.txt ไม่อนุญาต: {url}")
        return False
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = page.goto(url, timeout=config.PAGE_TIMEOUT, wait_until="domcontentloaded")
            status = resp.status if resp else 0

            if status in (429, 503):
                polite.slow_down(f"HTTP {status}")
                wait = max(_retry_after(resp), config.COOLDOWN_429 * attempt)
                print(f"   ⚠️ HTTP {status} (ขอถี่เกินไป) — พัก {wait}s ({attempt}/{config.MAX_RETRIES})")
                time.sleep(wait)
                continue
            if status >= 500:
                polite.slow_down(f"Server error {status}")
                wait = config.BACKOFF_BASE * attempt
                print(f"   ⚠️ Server error {status} — พัก {wait}s ({attempt}/{config.MAX_RETRIES})")
                time.sleep(wait)
                continue
            if status >= 400:
                print(f"   ✗ HTTP {status}: {url}")
                return False

            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=config.WAIT_TIMEOUT)
                except PWTimeout:
                    pass      # selector ไม่เจอ ≠ เน็ตมีปัญหา
            return True

        except PWTimeout:
            polite.slow_down("Timeout")
            wait = config.BACKOFF_BASE * attempt
            print(f"   ⚠️ Timeout — พัก {wait}s ({attempt}/{config.MAX_RETRIES})")
            time.sleep(wait)
        except Exception as e:
            wait = config.BACKOFF_BASE * attempt
            print(f"   ⚠️ {e} — พัก {wait}s ({attempt}/{config.MAX_RETRIES})")
            time.sleep(wait)
    return False


# ---------------- ไฟล์ ----------------
def _ensure(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def load_existing(path: str) -> Dict[str, Job]:
    """อ่าน .jsonl ที่เคยเก็บไว้ → {url_hash: Job} (ใช้กันงานซ้ำ + รันต่อ)"""
    out: Dict[str, Job] = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                job = Job.from_dict(json.loads(ln))
            except json.JSONDecodeError:
                continue          # บรรทัดเสีย (เช่นแครชกลางบรรทัด) ข้ามไป
            if not job.url_hash:
                job.url_hash = url_hash(job.source_url)
            out[job.url_hash] = job
    return out


def append_jsonl(job: Job, path: str) -> None:
    """เขียนต่อท้ายทีละงาน — แครชเมื่อไหร่ ของที่เก็บแล้วไม่หาย"""
    _ensure(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(job.to_dict(), ensure_ascii=False) + "\n")


def log_failed(url: str, reason: str, path: str) -> None:
    """จดงานที่ดึงไม่สำเร็จไว้ — จะได้ไม่หายเงียบ และตามเก็บทีหลังได้"""
    _ensure(path)
    rec = {"url": url, "reason": reason,
           "at": __import__("datetime").datetime.now().isoformat(timespec="seconds")}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_failed(path: str) -> List[str]:
    """อ่านรายการงานที่เคยดึงไม่สำเร็จ (ตัดซ้ำ คงลำดับเดิม)"""
    if not os.path.exists(path):
        return []
    seen, out = set(), []
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                u = json.loads(ln).get("url")
            except json.JSONDecodeError:
                continue
            if u and u not in seen:
                seen.add(u)
                out.append(u)
    return out


def clear_failed(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)


def write_json_array(jobs: List[Job], path: str) -> None:
    """เขียนไฟล์ JSON array (สำหรับส่งงาน / เข้า pipeline)"""
    _ensure(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump([j.to_dict() for j in jobs], f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ---------------- ทะเบียนลิงก์ที่เคยเห็น ----------------
# เก็บทุกลิงก์ที่เจอบนหน้ารายการ พร้อมสถานะ เพื่อพิสูจน์ว่าไม่มีงานหาย
#   pending = เห็นแล้วแต่ยังไม่ได้ดึง | done = ดึงสำเร็จ | failed = ดึงไม่สำเร็จ
def load_seen(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_seen(seen: dict, path: str) -> None:
    _ensure(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)