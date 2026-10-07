# -*- coding: utf-8 -*-
"""
scraper.py — Single-Pass Extraction: จบครบใน 1 รอบต่อ 1 งาน

Flow ต่อ 1 งาน:
  หน้ารายการ → คลิกงาน (Step 1)
  → ดึงข้อมูลบริษัท + ภาพรวมงาน (Step 2)
  → เปิดหน้ารายละเอียดเต็ม ดึง job description + คุณสมบัติ (Step 3)
  → ตัดข้อมูลซ้ำ + บันทึก JSON → ไปงานถัดไปทันที (Step 4)
"""
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from playwright.sync_api import Page

import config
from models import Job
from extract import (grab_sections, grab_text, grab_all_text,
                     grab_detail_url, grab_logo, grab_company_desc)
from textutil import line_keys, remove_duplicate_lines, to_bullets, clean_text
from utils import (url_hash, polite_delay, safe_goto, append_jsonl,
                   write_json_array, log_failed)
import freshness

CARD = config.SEL["job_card"]


def _page_url(base: str, n: int) -> str:
    """ต่อ page=N โดยคง filter เดิม (jobtype / subjobtype)"""
    p = urlsplit(base)
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k != "page"]
    q.append(("page", str(n)))
    return urlunsplit(p._replace(query=urlencode(q)))


def _collect_cards(page: Page) -> List[dict]:
    """
    เก็บลิงก์งาน + โลโก้บริษัทจากการ์ดในหน้ารายการ
    (การ์ดมี <img id="job-list-company-logo-..."> อยู่แล้ว ใช้เป็นทางสำรอง
     เวลาที่หน้ารายละเอียดไม่มีรูปโลโก้ — ไม่ต้องยิง request เพิ่ม)
    """
    out, seen = [], set()
    for card in page.query_selector_all(CARD):
        href = (card.get_attribute("href") or "").strip()
        if not href:
            continue
        if href.startswith("/"):
            href = config.BASE_DOMAIN + href
        href = href.split("?")[0]
        if href in seen:
            continue
        seen.add(href)

        try:
            text = card.inner_text() or ""     # ใช้หา "วันที่" บนการ์ด (freshness.py)
        except Exception:
            text = ""
        logo = None
        try:
            img = (card.query_selector('img[id^="job-list-company-logo"]')
                   or card.query_selector('img[src*="media.jobthai.com"]'))
            if img:
                src = (img.get_attribute("src") or "").strip()
                if src and "media.jobthai.com" in src and "_pic_" not in src:
                    logo = src.rstrip("&?")
        except Exception:
            pass
        out.append({"url": href, "logo": logo, "text": text})
    return out


# ---------------------------------------------------------------- Step 2 + 3
def scrape_one(page: Page, job_url: str, logo_hint: Optional[str] = None) -> Optional[Job]:
    """
    ดึงข้อมูลงาน 1 รายการให้จบ (Step 2 + Step 3 + ตัดซ้ำ)
    logo_hint = โลโก้ที่เก็บมาจากการ์ดในหน้ารายการ (ใช้เมื่อหน้ารายละเอียดไม่มีรูป)
    """
    # ---------- Step 2: หน้าแรกที่คลิกเข้ามา ----------
    if not safe_goto(page, job_url, wait_selector="body"):
        return None

    # รูปโลโก้บางหน้าโหลดแบบ lazy — เลื่อนหน้าเล็กน้อยแล้วรอให้โหลด
    try:
        page.mouse.wheel(0, 500)
        page.wait_for_timeout(700)
    except Exception:
        pass

    sec2 = grab_sections(page)
    _title = _job_title(page)
    _company = _company_name(page)
    job = Job(
        url_hash=url_hash(job_url),
        source_url=job_url,
        scraped_at=datetime.now().isoformat(timespec="seconds"),
        company_name=_company,
        company_logo_url=grab_logo(page) or logo_hint,
        company_description=(sec2.get("company_description")
                             or grab_company_desc(page, _title, _company)),
        job_title=_title,
        num_positions=grab_text(page, config.SEL["positions"]),
        post_date=grab_text(page, config.SEL["post_date"]),
        welfare=sec2.get("welfare", ""),
        contact=sec2.get("contact", ""),
        travel=sec2.get("travel", ""),
    )
    # สถานที่ปฏิบัติงาน: ใช้ id นิ่งก่อน (แม่นกว่า) ไม่มีค่อยหาจากหัวข้อ
    job.work_location = (grab_all_text(page, config.SEL["work_location_id"])
                         or sec2.get("work_location", ""))
    job.location = _first_line(job.work_location)
    job.salary = _salary(page)

    # เก็บทุกบรรทัดที่ได้จาก Step 2 ไว้เทียบหาข้อมูลซ้ำใน Step 3
    seen = set()
    for t in (job.company_description, job.welfare, job.contact,
              job.work_location, job.travel):
        seen |= line_keys(t)

    # ---------- Step 3: เปิดหน้ารายละเอียดเต็ม ----------
    detail = grab_detail_url(page)
    if detail and detail.split("?")[0] != job_url.split("?")[0]:
        polite_delay("เปิดหน้ารายละเอียด")
        if safe_goto(page, detail, wait_selector="body"):
            job.detail_url = detail
            sec3 = grab_sections(page)

            # เติมช่องที่ Step 2 ไม่มี (บางงานข้อมูลอยู่หน้านี้แทน)
            for f in ("welfare", "contact", "work_location", "travel",
                      "company_description"):
                if not getattr(job, f) and sec3.get(f):
                    setattr(job, f, sec3[f])
                    seen |= line_keys(sec3[f])

            if not job.work_location:
                job.work_location = (grab_all_text(page, config.SEL["work_location_id"])
                                     or sec3.get("work_location", ""))
                job.location = job.location or _first_line(job.work_location)
            if not job.company_logo_url:
                job.company_logo_url = grab_logo(page) or logo_hint
            if not job.num_positions:
                job.num_positions = grab_text(page, config.SEL["positions"])
            if not job.post_date:
                job.post_date = grab_text(page, config.SEL["post_date"])
            if not job.salary:
                job.salary = _salary(page)

            # เก็บข้อความดิบไว้ก่อน แล้วค่อยตัดซ้ำ
            job.job_description_raw = sec3.get("job_description", "")
            job.qualification_raw = sec3.get("qualification", "")

            # ★ เงื่อนไขข้อ 1: ตัดบรรทัดที่ซ้ำกับ Step 2 ออก
            job.job_description = remove_duplicate_lines(job.job_description_raw, seen)
            seen |= line_keys(job.job_description)
            job.qualification = remove_duplicate_lines(job.qualification_raw, seen)
    else:
        job.detail_url = job_url
        job.job_description_raw = sec2.get("job_description", "")
        job.qualification_raw = sec2.get("qualification", "")
        job.job_description = job.job_description_raw
        job.qualification = job.qualification_raw

    job.job_description_items = to_bullets(job.job_description)
    job.qualification_items = to_bullets(job.qualification)
    return job


def _company_name(page: Page) -> str:
    for sel in ('[id^="job-list-company-name-"]', '[id^="company-name"]',
                'a[href*="/th/company/"] h1', 'h2'):
        v = grab_text(page, sel)
        if v and len(v) < 200:
            return v.splitlines()[0]
    return ""


def _job_title(page: Page) -> str:
    v = grab_text(page, config.SEL["job_title"])
    return v.splitlines()[0] if v else ""


def _salary(page: Page) -> str:
    for sel in (config.SEL["salary"], '[id^="job-salary"]', '[id*="salary"]'):
        v = grab_text(page, sel)
        if v:
            return v.splitlines()[0]
    return ""


def _first_line(t: str) -> str:
    t = clean_text(t)
    return t.splitlines()[0] if t else ""


# ---------------------------------------------------------------- ลูปหลัก
def run(page: Page) -> Dict[str, Job]:
    """Step 1 + Step 4: วนหน้ารายการ → ดึงทีละงาน → บันทึกทันที → งานถัดไป"""
    from utils import load_existing
    done = load_existing(config.JSONL_PATH)
    print(f"มีงานที่เก็บไว้แล้ว {len(done)} รายการ\n")
    remembered = freshness.load_dates()   # วันที่บนการ์ดที่เคยเห็น {url_hash: "YYYY-MM-DD"}
    upd_limit = freshness.max_updates()
    updated_count = 0    # เปิดใหม่เพราะการ์ดใหม่กว่า + เนื้อหาเปลี่ยน
    bumped_count = 0     # เปิดใหม่เพราะการ์ดใหม่กว่า แต่เนื้อหาเดิม (บริษัทดันประกาศ)
    dated_cards = 0      # การ์ดที่อ่านวันที่ได้

    page_no, empty_streak, known_streak = 1, 0, 0
    new_count = 0        # เก็บใหม่สำเร็จ
    partial_count = 0    # เก็บได้แต่ข้อมูลไม่ครบ
    fail_count = 0       # ดึงไม่ได้เลย
    skip_count = 0       # ข้ามเพราะเคยเก็บแล้ว
    seen_total = 0       # เจอในหน้ารายการทั้งหมด

    try:
        while True:
            if config.MAX_JOBS and len(done) >= config.MAX_JOBS:
                print(f"ครบ {config.MAX_JOBS} งานแล้ว — หยุด")
                break

            url = _page_url(config.LISTING_URL, page_no)
            print(f"[หน้า {page_no}] {url}")
            if not safe_goto(page, url, wait_selector=CARD):
                empty_streak += 1
                if empty_streak >= config.MAX_EMPTY_PAGES:
                    break
                page_no += 1
                continue

            cards = _collect_cards(page)
            links = [c["url"] for c in cards]
            if not links:
                empty_streak += 1
                print(f"[หน้า {page_no}] ไม่พบงาน (streak {empty_streak})")
                if empty_streak >= config.MAX_EMPTY_PAGES:
                    print("หมดหน้าแล้ว — จบ")
                    break
                page_no += 1
                polite_delay(f"ไปหน้า {page_no}")
                continue
            empty_streak = 0
            print(f"[หน้า {page_no}] พบ {len(links)} งาน")
            if getattr(config, "SHOW_CARDS", False):
                freshness.show_cards(cards, done, url_hash)
                return done

            for i, card in enumerate(cards, 1):
                if config.MAX_JOBS and len(done) >= config.MAX_JOBS:
                    break

                link = card["url"]
                seen_total += 1
                h = url_hash(link)
                card_date = freshness.parse_date(card.get("text"))
                dated_cards += bool(card_date)
                old = done.get(h)
                refresh = (old is not None and freshness.is_updated(card_date, old, remembered.get(h))
                           and updated_count + bumped_count < upd_limit)
                if old is not None and not refresh:  # ★ กันประกาศซ้ำ
                    known_streak += 1
                    skip_count += 1
                    print(f"  [{i}/{len(cards)}] ⏭ เคยเก็บแล้ว")
                    if config.INCREMENTAL and known_streak >= config.STOP_AFTER_KNOWN:
                        print(f"\nเจองานเดิมติดกัน {known_streak} รายการ — ไม่มีงานใหม่แล้ว หยุด")
                        raise StopIteration
                    continue
                known_streak = 0

                job = scrape_one(page, link, card["logo"])   # Step 2 + 3 จบในรอบเดียว

                if refresh and job is not None and job.is_usable():
                    # ★ งานเดิมที่การ์ดบอกว่าอัปเดต: เทียบเนื้อหากับที่เคยเก็บ
                    diff = freshness.changed_fields(old, job)
                    done[h] = job
                    append_jsonl(job, config.JSONL_PATH)     # บรรทัดใหม่ทับของเดิม (อ่านบรรทัดล่าสุด)
                    freshness.remember(remembered, h, card_date)   # บันทึกทันที (กดหยุดกลางทางก็ไม่หาย)
                    if diff:
                        updated_count += 1
                        print(f"  [{i}/{len(cards)}] ↻ อัปเดต ({', '.join(diff)}): {job.job_title[:35]}")
                        freshness.feed("updated", job, changed=diff, before=old.post_date)
                    else:
                        bumped_count += 1
                        print(f"  [{i}/{len(cards)}] ↑ ดันประกาศ (เนื้อหาเดิม): {job.job_title[:35]}")
                        freshness.feed("bumped", job, before=old.post_date)
                    polite_delay("งานถัดไป")
                    continue
                if refresh:
                    # เปิดใหม่ไม่สำเร็จ: ของเดิมยังอยู่ นับเป็นข้าม
                    skip_count += 1
                    print(f"  [{i}/{len(cards)}] ⏭ เปิดงานที่อัปเดตไม่สำเร็จ — ใช้ข้อมูลเดิม")
                    polite_delay("งานถัดไป")
                    continue

                if job is None:
                    # เปิดหน้าไม่ได้เลย -> จดไว้ตามเก็บทีหลัง
                    fail_count += 1
                    log_failed(link, "เปิดหน้าไม่สำเร็จ", config.FAILED_PATH)
                    print(f"  [{i}/{len(cards)}] ✗ เปิดหน้าไม่สำเร็จ: {link}")
                    freshness.feed("failed", url=link)
                elif job.is_usable():
                    # เก็บไว้เสมอถ้ารู้ว่าเป็นงานอะไร (ดีกว่าทิ้งข้อมูลทิ้ง)
                    done[h] = job
                    append_jsonl(job, config.JSONL_PATH)   # Step 4: บันทึกทันที
                    if card_date:
                        freshness.remember(remembered, h, card_date)   # บันทึกทันที (กดหยุดกลางทางก็ไม่หาย)
                    new_count += 1
                    if job.is_complete():
                        print(f"  [{i}/{len(cards)}] ✓ {job.job_title[:45]}")
                        freshness.feed("new", job)
                    else:
                        partial_count += 1
                        miss = ", ".join(job.missing_fields())
                        log_failed(link, f"ได้ไม่ครบ: ขาด {miss}", config.FAILED_PATH)
                        print(f"  [{i}/{len(cards)}] ⚠ ได้ไม่ครบ (ขาด {miss}): {job.job_title[:35]}")
                        freshness.feed("partial", job, missing=job.missing_fields())
                else:
                    fail_count += 1
                    log_failed(link, "ไม่พบแม้แต่ชื่อตำแหน่ง", config.FAILED_PATH)
                    print(f"  [{i}/{len(cards)}] ✗ ดึงไม่สำเร็จ: {link}")
                    freshness.feed("failed", url=link)

                if new_count and new_count % config.SAVE_EVERY == 0:
                    write_json_array(list(done.values()), config.JSON_PATH)
                    print(f"   💾 บันทึก {len(done)} รายการ")

                polite_delay("งานถัดไป")

            page_no += 1
            polite_delay(f"ไปหน้า {page_no}")

    except StopIteration:
        pass
    except KeyboardInterrupt:
        print(f"\nหยุดด้วย Ctrl+C — เก็บได้ {len(done)} รายการ (รันต่อได้)")

    write_json_array(list(done.values()), config.JSON_PATH)
    freshness.save_dates(remembered)

    print(f"\n{'-' * 46}")
    print(f"เจอในหน้ารายการ : {seen_total}")
    print(f"  เก็บใหม่สำเร็จ : {new_count - partial_count}")
    if updated_count:
        print(f"  อัปเดต (เนื้อหาเปลี่ยน) : {updated_count}")
    if bumped_count:
        print(f"  ดันประกาศ (เนื้อหาเดิม) : {bumped_count}")
    if seen_total and not dated_cards:
        print("  ℹ️ การ์ดในหน้ารายการไม่มีวันที่ — ตรวจงานที่ถูกอัปเดตไม่ได้")
    elif updated_count + bumped_count >= upd_limit:
        print(f"  ℹ️ ครบโควตาเปิดงานที่อัปเดต {upd_limit} งาน/รอบ — ที่เหลือทำรอบถัดไป")
    if partial_count:
        print(f"  เก็บแต่ไม่ครบ  : {partial_count}  (ดู {config.FAILED_PATH})")
    if skip_count:
        print(f"  ข้าม (เคยเก็บ) : {skip_count}")
    if fail_count:
        print(f"  ดึงไม่ได้เลย   : {fail_count}  (ดู {config.FAILED_PATH})")
    checked = new_count + skip_count + fail_count + updated_count + bumped_count
    if checked != seen_total:
        print(f"  ⚠️ ตัวเลขไม่ตรง: ตรวจแล้ว {checked} จาก {seen_total}")
    print(f"รวมในไฟล์      : {len(done)} รายการ")
    return done


def retry_failed(page: Page) -> None:
    """ดึงซ้ำเฉพาะงานที่เคยพลาด (อ่านจาก failed.jsonl)"""
    from utils import load_existing, load_failed, clear_failed
    urls = load_failed(config.FAILED_PATH)
    if not urls:
        print("ไม่มีงานที่ค้างอยู่ใน failed.jsonl")
        return
    done = load_existing(config.JSONL_PATH)
    todo = [u for u in urls if url_hash(u) not in done
            or not done[url_hash(u)].is_complete()]
    print(f"มีงานค้าง {len(urls)} รายการ | ต้องดึงซ้ำ {len(todo)} รายการ\n")

    ok = 0
    clear_failed(config.FAILED_PATH)      # ล้างแล้วจดใหม่เฉพาะที่ยังพลาด
    for i, u in enumerate(todo, 1):
        job = scrape_one(page, u)
        if job and job.is_complete():
            done[url_hash(u)] = job
            append_jsonl(job, config.JSONL_PATH)
            ok += 1
            print(f"  [{i}/{len(todo)}] ✓ {job.job_title[:45]}")
        else:
            log_failed(u, "ยังดึงไม่สำเร็จ (ลองซ้ำ)", config.FAILED_PATH)
            print(f"  [{i}/{len(todo)}] ✗ ยังไม่สำเร็จ: {u}")
        if i < len(todo):
            polite_delay("งานถัดไป")

    write_json_array(list(done.values()), config.JSON_PATH)
    print(f"\nดึงซ้ำสำเร็จ {ok}/{len(todo)} | รวมในไฟล์ {len(done)} รายการ")