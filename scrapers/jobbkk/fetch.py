# -*- coding: utf-8 -*-
"""
fetch.py — ดึงหน้าเว็บด้วย requests อย่างสุภาพ
หน้ารายละเอียดของ JobBKK เป็น server-rendered จึงไม่ต้องเปิดเบราว์เซอร์
(เร็วกว่าและกินทรัพยากรน้อยกว่า Playwright มาก)
"""
import json
import os
import random
import time
import hashlib
from typing import Optional, List, Dict

import requests
from bs4 import BeautifulSoup

import config

_session: Optional[requests.Session] = None


def session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(config.HEADERS)
    return _session


def url_hash(url: str) -> str:
    clean = (url or "").split("?")[0].rstrip("/")
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


def polite_delay(reason: str = "") -> None:
    secs = random.uniform(config.MIN_DELAY, config.MAX_DELAY)
    print(f"   ⏳ หน่วง {secs:.1f}s{f' ({reason})' if reason else ''}")
    time.sleep(secs)


def get_soup(url: str) -> Optional[BeautifulSoup]:
    """ดึงหน้าเว็บ + ตรวจ robots.txt + จัดการ 429 / 5xx / timeout พร้อม retry"""
    import polite
    if not polite.allowed(url):
        print(f"   ⛔ robots.txt ไม่อนุญาต: {url}")
        return None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            r = session().get(url, timeout=config.HTTP_TIMEOUT)

            if r.status_code in (429, 503):
                polite.slow_down(f"HTTP {r.status_code}")
                wait = max(int(r.headers.get("retry-after", 0) or 0),
                           config.COOLDOWN_429 * attempt)
                print(f"   ⚠️ HTTP {r.status_code} (ขอถี่เกินไป) — พัก {wait}s "
                      f"({attempt}/{config.MAX_RETRIES})")
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                polite.slow_down(f"Server error {r.status_code}")
                wait = config.BACKOFF_BASE * attempt
                print(f"   ⚠️ Server error {r.status_code} — พัก {wait}s "
                      f"({attempt}/{config.MAX_RETRIES})")
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                print(f"   ✗ HTTP {r.status_code}: {url}")
                return None

            r.encoding = r.apparent_encoding or "utf-8"
            return BeautifulSoup(r.text, "html.parser")

        except requests.Timeout:
            polite.slow_down("Timeout")
            wait = config.BACKOFF_BASE * attempt
            print(f"   ⚠️ Timeout — พัก {wait}s ({attempt}/{config.MAX_RETRIES})")
            time.sleep(wait)
        except Exception as e:
            wait = config.BACKOFF_BASE * attempt
            print(f"   ⚠️ {e} — พัก {wait}s ({attempt}/{config.MAX_RETRIES})")
            time.sleep(wait)
    return None


def page_text(soup: BeautifulSoup) -> str:
    """แปลงหน้าเว็บเป็นข้อความ โดยคงการขึ้นบรรทัดไว้ (ตัด script/style/nav/footer)"""
    for t in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        t.decompose()
    return soup.get_text(separator="\n")


def meta(soup: BeautifulSoup, prop: str) -> Optional[str]:
    """อ่านค่า meta tag เช่น og:image (โลโก้บริษัทของ JobBKK อยู่ตรงนี้)"""
    for attr in ("property", "name"):
        tag = soup.find("meta", attrs={attr: prop})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


# ---------------- ไฟล์ ----------------
def _ensure(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def load_existing(path: str) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except json.JSONDecodeError:
                continue
            h = d.get("url_hash") or url_hash(d.get("source_url", ""))
            out[h] = d
    return out


def append_jsonl(obj: dict, path: str) -> None:
    _ensure(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def write_json_array(rows: List[dict], path: str) -> None:
    _ensure(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def log_failed(url: str, reason: str, path: str) -> None:
    from datetime import datetime
    _ensure(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"url": url, "reason": reason,
                            "at": datetime.now().isoformat(timespec="seconds")},
                           ensure_ascii=False) + "\n")


def load_cache(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(cache: dict, path: str) -> None:
    _ensure(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def job_posting_jsonld(soup) -> dict:
    """
    อ่านข้อมูล schema.org JobPosting ที่เว็บฝังไว้ใน <script type="application/ld+json">
    (เว็บหางานใส่ไว้ให้ Google อ่าน — แม่นกว่าการเดาจากข้อความบนหน้า)
    ⚠️ ต้องเรียกก่อน page_text() เพราะ page_text ลบ <script> ทิ้ง
    """
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else [data]
        for it in list(items):
            if isinstance(it, dict) and isinstance(it.get("@graph"), list):
                items.extend(it["@graph"])
        for it in items:
            if not isinstance(it, dict):
                continue
            t = it.get("@type")
            if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
                return it
    return {}