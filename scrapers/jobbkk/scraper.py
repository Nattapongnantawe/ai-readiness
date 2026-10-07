# -*- coding: utf-8 -*-
"""
scraper.py — JobBKK Single-Pass Extraction (จบครบใน 1 รอบต่อ 1 งาน)

Flow ต่อ 1 งาน:
  หน้ารายการ (Playwright — ผลค้นหาเรนเดอร์ด้วย JS)
    → เปิดหน้ารายละเอียด (requests — หน้านี้ server-rendered)
    → ดึงข้อมูลบริษัท + ภาพรวมงาน + รายละเอียด + คุณสมบัติ
    → ตัดหัวข้อต้องห้าม + ตัดข้อมูลซ้ำ
    → บันทึก JSON ทันที → งานถัดไป
"""
import re
from datetime import datetime
from typing import Dict, List, Optional

import config
from models import Job
from bkk_parse import (parse_labels, parse_sections, to_bullets,
                       clean_travel, clean, format_pairs, looks_like_date)
from scope import in_scope
from fetch import (get_soup, page_text, meta, url_hash, polite_delay,
                   job_posting_jsonld,
                   load_existing, append_jsonl, write_json_array,
                   log_failed, load_cache, save_cache)
import freshness

_company_cache: Dict[str, str] = {}


# ---------------------------------------------------------------- URL
def page_url(base: str, n: int) -> str:
    """เปลี่ยนเลขหน้าใน /jobs/lists/{n}/..."""
    return re.sub(r"(/jobs/lists/)\d+(/)", rf"\g<1>{n}\g<2>", base)


def split_ids(url: str) -> tuple:
    """/jobs/detailurgent/{companyId}/{jobId} -> ('223452', '1265807')"""
    m = re.search(r"/jobs/detail\w*/(\d+)/(\d+)", url)
    return (m.group(1), m.group(2)) if m else ("", "")


# ---------------------------------------------------------------- แนะนำบริษัท
def company_description(company_id: str) -> str:
    """
    ดึง "ข้อมูลบริษัท" จากหน้าโปรไฟล์ — หน้ารายละเอียดงานไม่มีข้อมูลนี้
    cache ต่อบริษัท เพราะบริษัทเดียวลงหลายงาน (ยิง request แค่ครั้งเดียว)
    """
    if not config.FETCH_COMPANY_PROFILE or not company_id:
        return ""
    if company_id in _company_cache:
        return _company_cache[company_id]

    url = config.COMPANY_PROFILE_URL.format(base=config.BASE, cid=company_id)
    soup = get_soup(url)
    desc = _pick_company_desc(clean(page_text(soup))) if soup else ""

    _company_cache[company_id] = desc
    save_cache(_company_cache, config.COMPANY_CACHE)
    return desc


def _pick_company_desc(text: str) -> str:
    """
    ตัดเอาเฉพาะย่อหน้าใต้หัวข้อ "ข้อมูลบริษัท" จนถึงหัวข้อถัดไป
    โครงสร้างหน้าเว็บ:
        ข้อมูลบริษัท
        (Company Information)
        <ย่อหน้าแนะนำบริษัท>
        สินค้าและบริการ   <- หยุดตรงนี้
    """
    lines = text.splitlines()

    # หาบรรทัดหัวข้อ "ข้อมูลบริษัท" (เอาอันที่มีเนื้อหาตามหลัง)
    start = -1
    for i, ln in enumerate(lines):
        if ln.strip().rstrip(":：").strip() in config.COMPANY_DESC_START:
            start = i
            break
    if start == -1:
        return ""

    body = []
    for ln in lines[start + 1:]:
        s_ = ln.strip()
        if not s_ or s_ in ("-", "(Company Information)"):
            continue
        # หน้าเว็บมีคำว่า "ข้อมูลบริษัท" ทั้งที่แท็บและหัวข้อ — ข้ามบรรทัดหัวข้อซ้ำ
        if s_.rstrip(":：").strip() in config.COMPANY_DESC_START:
            continue
        if any(s_ == e or s_.startswith(e) for e in config.COMPANY_DESC_END):
            break
        body.append(s_)

    out = "\n".join(body).strip()
    return out if len(out) >= 40 else ""


# ---------------------------------------------------------------- 1 งาน
def scrape_one(job_url: str) -> Optional[Job]:
    soup = get_soup(job_url)
    if soup is None:
        return None

    # ★ อ่าน schema.org JobPosting ก่อน — page_text() จะลบ <script> ทิ้ง
    jp = job_posting_jsonld(soup)

    txt = page_text(soup)
    lb = parse_labels(txt)
    sec = parse_sections(txt)
    cid, jid = split_ids(job_url)

    desc = sec.get("job_description", "")
    qual = sec.get("qualification", "")

    # ★ ตัดบรรทัดที่ซ้ำกับส่วนอื่น (สวัสดิการ/ติดต่อ) ออกจากรายละเอียด+คุณสมบัติ
    seen = _line_keys(sec.get("welfare", "")) | _line_keys(sec.get("contact", ""))
    desc = _drop_dup(desc, seen)
    seen |= _line_keys(desc)
    qual = _drop_dup(qual, seen)

    job = Job(
        url_hash=url_hash(job_url),
        source_url=job_url,
        detail_url=job_url,
        scraped_at=datetime.now().isoformat(timespec="seconds"),
        company_id=cid,
        company_name=_company_name(soup, txt),
        company_logo_url=meta(soup, "og:image"),      # โลโก้อยู่ใน meta tag
        company_description=company_description(cid),
        job_title=_job_title(soup, txt),
        location=lb.get("สถานที่", ""),
        salary=lb.get("เงินเดือน (บาท)", ""),
        num_positions=lb.get("จำนวนที่รับ", ""),
        post_date=_post_date(jp, lb),
        welfare=sec.get("welfare", ""),
        contact=format_pairs(sec.get("contact", "")),
        work_location=lb.get("สถานที่", ""),
        travel=clean_travel(sec.get("travel", "")),
        job_description=desc,
        qualification=qual,
    )
    job.job_description_items = to_bullets(desc)
    job.qualification_items = to_bullets(qual)

    from bkk_parse import SKIP_LABELS
    job.attributes = {k: v for k, v in lb.items()
                      if k not in SKIP_LABELS and k not in
                      ("สถานที่", "เงินเดือน (บาท)", "จำนวนที่รับ", "วันที่อัปเดต")}
    return job


def _post_date(jp: dict, lb: dict) -> str:
    """
    วันที่ประกาศ — ลำดับความน่าเชื่อถือ:
      1) datePosted จาก JSON-LD (schema.org) แม่นที่สุด
      2) ป้าย "วันที่อัปเดต" บนหน้า (ผ่านการตรวจว่าเป็นวันที่จริงแล้ว)
    """
    for v in (jp.get("datePosted"), lb.get("วันที่อัปเดต")):
        if v and looks_like_date(str(v)):
            return str(v).strip()
    return ""


def _company_name(soup, txt: str) -> str:
    t = meta(soup, "og:image:alt") or meta(soup, "twitter:image:alt")
    if t:
        return t.strip()
    h2 = soup.find("h2")
    if h2 and h2.get_text(strip=True):
        return h2.get_text(strip=True)
    m = re.search(r"^(บริษัท .+?|.+? (?:จำกัด|Co\.,? ?Ltd\.?))$",
                  clean(txt), re.M)
    return m.group(1).strip() if m else ""


def _job_title(soup, txt: str) -> str:
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    t = meta(soup, "og:title") or ""
    return t.split("|")[0].strip()


_BULLET = re.compile(r"^\s*(?:[-•·*▪◦–—]+|\d+(?:\.\d+)+|\d+[.)]|\(\d+\))\s*")


def _norm(ln: str) -> str:
    return re.sub(r"\s+", "", _BULLET.sub("", ln)).lower()


def _line_keys(text: str) -> set:
    return {k for k in (_norm(l) for l in clean(text).splitlines()) if len(k) >= 8}


def _drop_dup(text: str, seen: set) -> str:
    keep = []
    for ln in clean(text).splitlines():
        k = _norm(ln)
        if len(k) >= 8 and k in seen:
            continue
        keep.append(ln)
    return "\n".join(keep).strip()


# ---------------------------------------------------------------- ลูปหลัก
_JS_RESULT_LINKS = r"""
(cfg) => {
  const norm = t => (t || '').replace(/\s+/g, ' ').trim();
  const isVisible = el => el && (el.checkVisibility ? el.checkVisibility() : (el.offsetParent !== null || el.getClientRects().length > 0));
  const small = Array.from(document.querySelectorAll('h1,h2,h3,h4,div,span,p'))
                     .filter(el => el.children.length <= 1 && isVisible(el));

  // จุดเริ่มผลการค้นหา = ข้อความ "ผลการค้นหาพบ N ตำแหน่ง"
  let start = null;
  for (const el of small) {
    const t = norm(el.textContent);
    if (cfg.start.some(s => t.startsWith(s))) {
      if (!start || (start.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_PRECEDING)) {
        start = el;   // เอาอันแรกสุดในหน้า
      }
    }
  }

  // จุดจบ = หัวข้อถัดไปที่อยู่ "หลัง" จุดเริ่ม (ตำแหน่งงานแนะนำ / footer)
  let end = null;
  if (start) {
    for (const el of small) {
      const t = norm(el.textContent);
      if (!cfg.end.some(s => t === s || t.startsWith(s))) continue;
      const after = start.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING;
      if (!after) continue;
      if (!end || (end.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_PRECEDING)) {
        end = el;     // เอาอันแรกที่อยู่หลังจุดเริ่ม
      }
    }
  }

  // ข้อความทั้งการ์ดของลิงก์ (ใช้หา "วันที่" — freshness.py): ไล่ขึ้นไปจนกว่ากล่องจะมีงานอื่นปน
  const jobPath = el => (el.getAttribute('href') || '').split('?')[0];
  const cardText = a => {
    let box = a, me = jobPath(a);
    for (let up = 0; up < 8 && box.parentElement; up++) {
      const p = box.parentElement;
      const others = Array.from(p.querySelectorAll('a[href*="/jobs/detail"]')).some(x => jobPath(x) !== me);
      if (others) break;
      box = p;
    }
    return norm(box.innerText || box.textContent).slice(0, 600);
  };

  const out = [];
  for (const a of document.querySelectorAll(cfg.sel)) {
    const href = a.getAttribute('href') || '';
    if (!href.includes('/jobs/detail')) continue;
    const path = href.split('?')[0];                      // ตัด query ก่อนเทียบ
    if (cfg.ads.some(p => path.includes(p))) continue;     // ลิงก์โฆษณา
    if (start) {
      const afterStart = start.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING;
      if (!afterStart) continue;                       // อยู่ก่อนผลการค้นหา = เมนู/แนะนำ
    }
    if (end) {
      const beforeEnd = a.compareDocumentPosition(end) & Node.DOCUMENT_POSITION_FOLLOWING;
      if (!beforeEnd) continue;                        // อยู่หลังหัวข้อปิด = footer/แนะนำ
    }
    out.push({href, text: cardText(a)});
  }
  return {links: out, hasStart: !!start, hasEnd: !!end};
}
"""


_JS_TOTAL = r"""
() => {
  // อ่านตัวเลขจาก "ผลการค้นหาพบ 1,153 ตำแหน่ง"
  const norm = t => (t || '').replace(/\s+/g, ' ').trim();
  for (const el of document.querySelectorAll('h1,h2,h3,h4,div,span,p')) {
    if (el.children.length > 3) continue;
    const m = norm(el.textContent).match(/ผลการค้นหาพบ\s*([\d,]+)\s*ตำแหน่ง/);
    if (m) return parseInt(m[1].replace(/,/g, ''), 10);
  }
  return null;
}
"""


def total_results(page) -> Optional[int]:
    """จำนวนงานทั้งหมดจากข้อความ 'ผลการค้นหาพบ N ตำแหน่ง' (None ถ้าหาไม่เจอ)"""
    try:
        return page.evaluate(_JS_TOTAL)
    except Exception:
        return None


def collect_links(page) -> tuple:
    """
    เก็บลิงก์เฉพาะ "ผลการค้นหา"
    หน้ารายการของ JobBKK มีทั้งเมนู, ตำแหน่งงานแนะนำ และ footer ปนอยู่
    จึงเก็บเฉพาะลิงก์ที่อยู่ระหว่าง "ผลการค้นหาพบ..." กับหัวข้อถัดไป

    คืน (links, has_results)
      has_results = False แปลว่าหน้านี้ไม่มีผลการค้นหาแล้ว (เลยหน้าสุดท้าย)
    """
    hrefs, note, has_start = [], "", False
    global _card_text
    texts = {}
    try:
        r = page.evaluate(_JS_RESULT_LINKS,
                          {"sel": config.JOB_LINK,
                           "start": config.RESULT_START,
                           "end": config.RESULT_END,
                           "ads": config.AD_URL_PARTS}) or {}
        hrefs = []
        for x in r.get("links") or []:
            href = x.get("href") if isinstance(x, dict) else x
            hrefs.append(href)
            if isinstance(x, dict) and href:
                full = (config.BASE + href if href.startswith("/") else href).split("?")[0]
                texts.setdefault(full, x.get("text") or "")
        has_start = bool(r.get("hasStart"))
        if not has_start:
            note = " (ไม่พบจุดเริ่มผลค้นหา — เก็บทั้งหน้า)"
    except Exception:
        hrefs = []

    # สำรอง: ถ้ากรองแล้วไม่เหลืออะไรเลย ให้เก็บทั้งหน้าไว้ก่อน ดีกว่าได้ 0
    if not hrefs:
        hrefs = [(a.get_attribute("href") or "")
                 for a in page.query_selector_all(config.JOB_LINK)]
        if hrefs:
            note = " (ตัวกรองไม่เข้า — เก็บทั้งหน้า)"

    out, seen = [], set()
    for href in hrefs:
        href = (href or "").strip()
        if not href or "/jobs/detail" not in href:
            continue
        if href.startswith("/"):
            href = config.BASE + href
        href = href.split("?")[0]
        if href not in seen:
            seen.add(href)
            out.append(href)
    if note:
        print(f"   ℹ️{note}")
    _card_text = texts
    return out, has_start


_card_text: Dict[str, str] = {}   # ลิงก์ -> ข้อความบนการ์ด ของหน้ารายการล่าสุด (collect_links)


def run(page) -> Dict[str, dict]:
    global _company_cache
    _company_cache = load_cache(config.COMPANY_CACHE)

    done = load_existing(config.JSONL_PATH)
    # งานนอกสายที่เคยเจอ — จำไว้ไม่ให้ดึงซ้ำ แต่ "ไม่" รวมเข้าไฟล์หลัก
    seen_out = set(load_existing(config.OUT_OF_SCOPE_PATH).keys())
    print(f"มีงานที่เก็บไว้แล้ว {len(done)} รายการ | บริษัทใน cache {len(_company_cache)}\n")
    remembered = freshness.load_dates()   # วันที่บนการ์ดที่เคยเห็น {url_hash: "YYYY-MM-DD"}
    upd_limit = freshness.max_updates()
    updated = bumped = dated_cards = 0

    pg, empty, known_streak = 1, 0, 0
    new_ok = partial = fail = skip = seen_total = 0
    dup_pages = 0          # นับหน้าที่ "ไม่มีงานใหม่เลย" ติดกัน
    out_scope = 0          # งานนอกสายงานที่ถูกตัดทิ้ง
    max_page = None        # หน้าสุดท้ายที่คำนวณจาก "ผลการค้นหาพบ N ตำแหน่ง"

    try:
        while True:
            if config.MAX_JOBS and len(done) >= config.MAX_JOBS:
                print(f"ครบ {config.MAX_JOBS} งานแล้ว — หยุด")
                break

            if max_page and pg > max_page:
                print(f"เกินหน้าสุดท้ายที่คำนวณได้ ({max_page}) — จบ")
                break

            url = page_url(config.LISTING_URL, pg)
            print(f"[หน้า {pg}] {url[:95]}")
            try:
                page.goto(url, timeout=config.PAGE_TIMEOUT, wait_until="domcontentloaded")
                page.wait_for_selector(config.JOB_LINK, timeout=config.WAIT_TIMEOUT)
            except Exception:
                pass
            # การ์ดบางใบเรนเดอร์ทีหลัง — เลื่อนหน้าลงเพื่อกระตุ้นให้โหลดครบก่อนเก็บลิงก์
            page.wait_for_timeout(2000)
            for _ in range(4):
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(600)
            page.wait_for_timeout(1000)

            links, has_results = collect_links(page)

            # ★ ตัวหยุดที่ 2: หาคำว่า "ผลการค้นหาพบ" ไม่เจอ = เลยหน้าสุดท้ายแล้ว
            #   (JobBKK ไม่ตอบหน้าว่าง แต่ส่งงานแนะนำชุดเดิมกลับมา)
            if config.STOP_WHEN_NO_RESULTS and pg > 1 and not has_results:
                print(f"[หน้า {pg}] ไม่มีผลการค้นหาแล้ว (เป็นงานแนะนำ) — จบ")
                break

            # ★ ตัวหยุดที่ 1: คำนวณหน้าสุดท้ายจากจำนวนผลค้นหา (ทำครั้งเดียวที่หน้าแรก)
            if pg == 1 and links:
                total = total_results(page)
                if total:
                    per_page = len(links)
                    max_page = -(-total // per_page) + config.PAGE_LIMIT_MARGIN
                    print(f"ผลการค้นหาพบ {total:,} ตำแหน่ง | หน้าละ {per_page} "
                          f"| จะหยุดไม่เกินหน้า {max_page}")

            if not links:
                empty += 1
                print(f"[หน้า {pg}] ไม่พบงาน (streak {empty})")
                if empty >= config.MAX_EMPTY_PAGES:
                    print("หมดหน้าแล้ว — จบ")
                    break
                pg += 1
                polite_delay(f"ไปหน้า {pg}")
                continue
            empty = 0
            done_before_page = set(done.keys()) | seen_out
            print(f"[หน้า {pg}] พบ {len(links)} งาน (เฉพาะผลการค้นหา)")
            if getattr(config, "SHOW_CARDS", False):
                freshness.show_cards([{"url": l, "text": _card_text.get(l, "")} for l in links], done, url_hash)
                return done

            for i, link in enumerate(links, 1):
                if config.MAX_JOBS and len(done) >= config.MAX_JOBS:
                    break
                seen_total += 1
                h = url_hash(link)
                card_date = freshness.parse_date(_card_text.get(link))
                dated_cards += bool(card_date)
                old = done.get(h)
                refresh = (old is not None and freshness.is_updated(card_date, old, remembered.get(h))
                           and updated + bumped < upd_limit)
                if (h in done or h in seen_out) and not refresh:
                    known_streak += 1
                    skip += 1
                    print(f"  [{i}/{len(links)}] ⏭ เคยเก็บแล้ว")
                    if config.INCREMENTAL and known_streak >= config.STOP_AFTER_KNOWN:
                        print(f"\nเจองานเดิมติดกัน {known_streak} รายการ — หยุด")
                        raise StopIteration
                    continue
                known_streak = 0

                job = scrape_one(link)
                if refresh:
                    # ★ งานเดิมที่การ์ดบอกว่าอัปเดต: เทียบเนื้อหากับที่เคยเก็บ
                    if job is not None and job.is_usable():
                        d = job.to_dict()
                        diff = freshness.changed_fields(old, d)
                        done[h] = d
                        append_jsonl(d, config.JSONL_PATH)   # บรรทัดใหม่ทับของเดิม (อ่านบรรทัดล่าสุด)
                        freshness.remember(remembered, h, card_date)   # บันทึกทันที (กดหยุดกลางทางก็ไม่หาย)
                        if diff:
                            updated += 1
                            print(f"  [{i}/{len(links)}] ↻ อัปเดต ({', '.join(diff)}): {job.job_title[:35]}")
                            freshness.feed("updated", d, changed=diff, before=old.get("post_date", ""))
                        else:
                            bumped += 1
                            print(f"  [{i}/{len(links)}] ↑ ดันประกาศ (เนื้อหาเดิม): {job.job_title[:35]}")
                            freshness.feed("bumped", d, before=old.get("post_date", ""))
                    else:
                        skip += 1
                        print(f"  [{i}/{len(links)}] ⏭ เปิดงานที่อัปเดตไม่สำเร็จ — ใช้ข้อมูลเดิม")
                    polite_delay("งานถัดไป")
                    continue
                if job is None:
                    fail += 1
                    log_failed(link, "เปิดหน้าไม่สำเร็จ", config.FAILED_PATH)
                    print(f"  [{i}/{len(links)}] ✗ เปิดหน้าไม่สำเร็จ")
                    freshness.feed("failed", url=link)
                elif job.is_usable() and not in_scope(job.to_dict())[0]:
                    # ★ ด่านสุดท้าย: สาขาอาชีพไม่ตรงขอบเขต → ไม่บันทึก แต่จดไว้ให้ตรวจ
                    out_scope += 1
                    d = job.to_dict()
                    reason = in_scope(d)[1]
                    append_jsonl({**d, "_reason": reason}, config.OUT_OF_SCOPE_PATH)
                    seen_out.add(h)           # จำไว้ไม่ให้ดึงซ้ำ — ไม่ใส่ done (done จะถูกเขียนลงไฟล์หลัก)
                    print(f"  [{i}/{len(links)}] ⊘ {reason}: {job.job_title[:30]}")
                elif job.is_usable():
                    d = job.to_dict()
                    done[h] = d
                    append_jsonl(d, config.JSONL_PATH)
                    if card_date:
                        freshness.remember(remembered, h, card_date)   # บันทึกทันที (กดหยุดกลางทางก็ไม่หาย)
                    if job.is_complete():
                        new_ok += 1
                        print(f"  [{i}/{len(links)}] ✓ {job.job_title[:45]}")
                        freshness.feed("new", d)
                    else:
                        partial += 1
                        miss = ", ".join(job.missing_fields())
                        log_failed(link, f"ได้ไม่ครบ: ขาด {miss}", config.FAILED_PATH)
                        print(f"  [{i}/{len(links)}] ⚠ ได้ไม่ครบ ({miss}): {job.job_title[:32]}")
                        freshness.feed("partial", d, missing=job.missing_fields())
                else:
                    fail += 1
                    log_failed(link, "ไม่พบแม้แต่ชื่อตำแหน่ง", config.FAILED_PATH)
                    print(f"  [{i}/{len(links)}] ✗ ดึงไม่สำเร็จ")
                    freshness.feed("failed", url=link)

                if (new_ok + partial) and (new_ok + partial) % config.SAVE_EVERY == 0:
                    write_json_array(list(done.values()), config.JSON_PATH)
                polite_delay("งานถัดไป")

            # ★ ตัวหยุดที่ 3: ทั้งหน้าเป็นงานที่เคยเก็บแล้ว = อาจวนซ้ำ
            page_new = sum(1 for l in links if url_hash(l) not in done_before_page)
            if page_new == 0:
                dup_pages += 1
                print(f"[หน้า {pg}] ไม่มีงานใหม่เลย (ติดกัน {dup_pages}/{config.STOP_AFTER_DUP_PAGES})")
                if not config.INCREMENTAL and dup_pages >= config.STOP_AFTER_DUP_PAGES:
                    print("เจอหน้าที่ไม่มีงานใหม่ติดกันหลายหน้า — น่าจะเลยผลค้นหาแล้ว จบ")
                    break
            else:
                dup_pages = 0

            pg += 1
            polite_delay(f"ไปหน้า {pg}")

    except StopIteration:
        pass
    except KeyboardInterrupt:
        print(f"\nหยุดด้วย Ctrl+C — เก็บได้ {len(done)} รายการ (รันต่อได้)")

    write_json_array(list(done.values()), config.JSON_PATH)
    save_cache(_company_cache, config.COMPANY_CACHE)
    freshness.save_dates(remembered)

    print(f"\n{'-' * 46}")
    print(f"เจอในหน้ารายการ : {seen_total}")
    print(f"  เก็บใหม่สำเร็จ : {new_ok}")
    if updated:
        print(f"  อัปเดต (เนื้อหาเปลี่ยน) : {updated}")
    if bumped:
        print(f"  ดันประกาศ (เนื้อหาเดิม) : {bumped}")
    if seen_total and not dated_cards:
        print("  ℹ️ การ์ดในหน้ารายการไม่มีวันที่ — ตรวจงานที่ถูกอัปเดตไม่ได้")
    elif updated + bumped >= upd_limit:
        print(f"  ℹ️ ครบโควตาเปิดงานที่อัปเดต {upd_limit} งาน/รอบ — ที่เหลือทำรอบถัดไป")
    if partial:
        print(f"  เก็บแต่ไม่ครบ  : {partial}  (ดู {config.FAILED_PATH})")
    if skip:
        print(f"  ข้าม (เคยเก็บ) : {skip}")
    if fail:
        print(f"  ดึงไม่ได้เลย   : {fail}  (ดู {config.FAILED_PATH})")
    if out_scope:
        print(f"  นอกสายงาน      : {out_scope}  (ดู {config.OUT_OF_SCOPE_PATH})")
    checked = new_ok + partial + skip + fail + out_scope + updated + bumped
    if checked != seen_total:
        print(f"  ⚠️ ตัวเลขไม่ตรง: ตรวจแล้ว {checked} จาก {seen_total}")
    print(f"รวมในไฟล์      : {len(done)} รายการ")
    return done


# ---------------------------------------------------------------- debug
_JS_DIAG = r"""
(cfg) => {
  const norm = t => (t || '').replace(/\s+/g, ' ').trim();
  const isVisible = el => el && (el.checkVisibility ? el.checkVisibility() : (el.offsetParent !== null || el.getClientRects().length > 0));
  const small = Array.from(document.querySelectorAll('h1,h2,h3,h4,div,span,p'))
                     .filter(el => el.children.length <= 1 && isVisible(el));
  let start = null, end = null;
  for (const el of small) {
    const t = norm(el.textContent);
    if (cfg.start.some(s => t.startsWith(s))) {
      if (!start || (start.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_PRECEDING)) start = el;
    }
  }
  if (start) {
    for (const el of small) {
      const t = norm(el.textContent);
      if (!cfg.end.some(s => t === s || t.startsWith(s))) continue;
      if (!(start.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING)) continue;
      if (!end || (end.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_PRECEDING)) end = el;
    }
  }
  const rows = [];
  for (const a of document.querySelectorAll('a[href]')) {
    const href = a.getAttribute('href') || '';
    if (!href.includes('/jobs/detail')) continue;
    let why = 'เก็บ';
    if (cfg.ads.some(p => href.split('?')[0].includes(p))) why = 'ตัด: ลิงก์โฆษณา';
    else if (start && !(start.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING))
      why = 'ตัด: อยู่ก่อนผลค้นหา';
    else if (end && !(a.compareDocumentPosition(end) & Node.DOCUMENT_POSITION_FOLLOWING))
      why = 'ตัด: อยู่หลังหัวข้อปิด';
    rows.push({href, why, text: norm(a.innerText || a.textContent).slice(0, 55)});
  }
  return {
    rows,
    startText: start ? norm(start.textContent).slice(0, 60) : null,
    endText: end ? norm(end.textContent).slice(0, 60) : null,
  };
}
"""


def diagnose(page) -> None:
    """ดูว่าหน้ารายการมีลิงก์งานกี่อัน อันไหนถูกเก็บ/ถูกตัด เพราะอะไร"""
    url = page_url(config.LISTING_URL, 1)
    print(f"เปิด: {url[:95]}\n")
    page.goto(url, timeout=config.PAGE_TIMEOUT, wait_until="domcontentloaded")
    try:
        page.wait_for_selector(config.JOB_LINK, timeout=config.WAIT_TIMEOUT)
    except Exception:
        pass
    # เลื่อนหน้าแบบเดียวกับตอนรันจริง เพื่อให้ผลตรวจตรงกับที่ scraper เห็น
    page.wait_for_timeout(2000)
    for _ in range(4):
        page.mouse.wheel(0, 2500)
        page.wait_for_timeout(600)
    page.wait_for_timeout(1000)

    r = page.evaluate(_JS_DIAG, {"start": config.RESULT_START,
                                 "end": config.RESULT_END,
                                 "ads": config.AD_URL_PARTS}) or {}
    print(f"จุดเริ่ม: {r.get('startText') or '✗ ไม่พบ'}")
    print(f"จุดจบ  : {r.get('endText') or '(ไม่มี)'}\n")

    rows = r.get("rows", [])
    keep = [x for x in rows if x["why"] == "เก็บ"]
    print(f"ลิงก์งานในหน้า {len(rows)} อัน | เก็บ {len(keep)} | ตัด {len(rows)-len(keep)}\n")
    for i, x in enumerate(rows, 1):
        mark = "✓" if x["why"] == "เก็บ" else "✗"
        print(f"  {mark} [{i:2}] {x['text'][:48]}")
        if x["why"] != "เก็บ":
            print(f"        {x['why']}")
        print(f"        {x['href'][:80]}")