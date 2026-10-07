# -*- coding: utf-8 -*-
"""
extract.py — ดึงเนื้อหาจากหน้าเว็บ โดยค้นจาก "ข้อความหัวข้อ" ไม่ใช่ CSS class
เหตุผล: JobThai ใช้ class สุ่ม (sc-1k7b98y-12) ที่เปลี่ยนทุกครั้งที่เว็บอัปเดต
"""
from typing import Dict, List, Optional

from playwright.sync_api import Page

import config
from textutil import clean_text, dedupe_within

# ---------------------------------------------------------------- หัวข้อ
_JS_SECTIONS = r"""
(names) => {
  const out = {};
  const norm = t => (t || '').replace(/\s+/g, ' ').trim();
  const all = Array.from(document.querySelectorAll('span,h1,h2,h3,h4,div,p,strong,b'));

  for (const name of names) {
    const heads = all.filter(el =>
      norm(el.textContent) === name &&
      el.children.length === 0 &&
      el.offsetParent !== null
    );
    if (!heads.length) continue;

    let best = '';
    for (const head of heads) {
      let node = head, body = '';
      for (let i = 0; i < 4 && node.parentElement; i++) {
        node = node.parentElement;
        const full = norm(node.innerText);
        if (full.length > name.length + 15) {
          let t = node.innerText;
          const idx = t.indexOf(name);
          if (idx !== -1) t = t.slice(idx + name.length);
          body = t.trim();
          break;
        }
      }
      if (body.length > best.length) best = body;
    }
    if (best) out[name] = best;
  }
  return out;
}
"""


def grab_sections(page: Page) -> Dict[str, str]:
    """คืน {ชื่อฟิลด์: เนื้อหา} ตาม config.SECTIONS"""
    wanted: List[str] = []
    for names in config.SECTIONS.values():
        wanted.extend(names)
    try:
        raw = page.evaluate(_JS_SECTIONS, wanted) or {}
    except Exception:
        return {}

    out: Dict[str, str] = {}
    for field, names in config.SECTIONS.items():
        for n in names:
            if raw.get(n):
                body = clean_text(raw[n])
                body = _strip_heading_lines(body, names)   # ตัดชื่อหัวข้อที่ติดมา
                body = _strip_excluded(body)               # เงื่อนไข 2: หัวข้อต้องห้าม
                body = _cut_at_stop_label(body)            # กันเนื้อหาลากไปหัวข้ออื่น
                if body:
                    out[field] = dedupe_within(body)
                break
    return out


def _strip_heading_lines(text: str, names: List[str]) -> str:
    """ตัดบรรทัดแรก ๆ ที่เป็นชื่อหัวข้อออก (บางครั้งติดมากับเนื้อหา)"""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        s = lines[i].strip().rstrip(":：").strip()
        if s in names or s in config.SECTIONS.get("job_description", []):
            i += 1
        else:
            break
    return "\n".join(lines[i:]).strip()


def _strip_excluded(text: str) -> str:
    """ตัดตั้งแต่หัวข้อต้องห้ามเป็นต้นไป (วิธีการสมัคร / Tags)"""
    for i, ln in enumerate(text.splitlines()):
        s = ln.strip().rstrip(":：").strip()
        if any(s == ex or s.startswith(ex) for ex in config.EXCLUDE_SECTIONS):
            return "\n".join(text.splitlines()[:i]).strip()
    return text


def _cut_at_stop_label(text: str) -> str:
    """
    ตัดตรงบรรทัดที่เป็น 'ป้ายหัวข้ออื่น' ล้วน ๆ
    เช่น สถานที่ปฏิบัติงานลากไปติด 'เงินเดือน' / 'อัตรา'
    ตัดเฉพาะบรรทัดที่ตรงเป๊ะ เพื่อไม่ไปตัดเนื้อหาจริงที่บังเอิญมีคำนั้น
    """
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        s = ln.strip().rstrip(":：").strip()
        if s in config.STOP_LABELS:
            return "\n".join(lines[:i]).strip()
    return text


# ---------------------------------------------------------------- โลโก้
_JS_LOGO = r"""
(cfg) => {
  const imgs = Array.from(document.querySelectorAll('img'));
  let best = null, bestScore = -1;
  for (const im of imgs) {
    // รูปบางรูปโหลดแบบ lazy — src ยังว่าง ต้องดู data-src / srcset ด้วย
    let src = im.currentSrc || im.getAttribute('src') || '';
    if (!src || src.startsWith('data:')) {
      src = im.getAttribute('data-src') || im.getAttribute('data-original') || '';
    }
    if (!src) {
      const ss = im.getAttribute('srcset') || '';
      if (ss) src = ss.split(',')[0].trim().split(' ')[0];
    }
    if (!src || src.startsWith('data:')) continue;

    const low = src.toLowerCase();
    if (cfg.reject.some(r => low.includes(r))) continue;   // ตัดรูปปก/แบนเนอร์/แผนที่

    let score = 0;
    cfg.prefer.forEach((p, i) => { if (low.includes(p)) score += (cfg.prefer.length - i) * 10; });
    const id = (im.id || '').toLowerCase();
    if (id.includes('logo')) score += 15;
    if ((im.alt || '').toLowerCase().includes('logo')) score += 5;

    // ขนาดใช้เป็นคะแนนเสริมเท่านั้น (รูป lazy ยังไม่มีขนาด)
    const w = im.naturalWidth || 0, h = im.naturalHeight || 0;
    if (w && h) {
      const ratio = w / h;
      if (ratio > 0.7 && ratio < 1.4) score += 8;
      if (w > 1200) score -= 10;
    }
    if (score > bestScore) { bestScore = score; best = src; }
  }
  // สำรอง 1: <picture><source srcset> (บางหน้าใส่รูปไว้ตรงนี้ img ไม่มี src)
  if (bestScore <= 0) {
    for (const so of document.querySelectorAll('picture source[srcset]')) {
      const u = (so.getAttribute('srcset') || '').split(',')[0].trim().split(' ')[0];
      if (u && u.includes('media.jobthai.com') && !u.includes('_pic_')) return u;
    }
  }
  // สำรอง 2: รูปที่ใส่เป็น CSS background-image
  if (bestScore <= 0) {
    for (const el of document.querySelectorAll('div,span,a')) {
      const bg = getComputedStyle(el).backgroundImage || '';
      const m = bg.match(/url\(["']?([^"')]+)["']?\)/);
      if (m && m[1].includes('media.jobthai.com') && !m[1].includes('_pic_')) return m[1];
    }
  }
  // สำรอง 3: รูปใดก็ได้ในโฟลเดอร์โลโก้ของ JobThai
  if (bestScore <= 0) {
    for (const im of imgs) {
      const src = im.currentSrc || im.getAttribute('src') ||
                  im.getAttribute('data-src') || '';
      if (src && src.includes('logo-pic-map') && !src.includes('_pic_')) return src;
    }
  }
  return bestScore > 0 ? best : null;
}
"""


def grab_logo(page: Page) -> Optional[str]:
    """เลือกรูปโลโก้บริษัทด้วยการให้คะแนน (ไม่ใช่เดา selector)"""
    try:
        src = page.evaluate(_JS_LOGO, {"prefer": config.LOGO_PREFER,
                                       "reject": config.LOGO_REJECT})
    except Exception:
        return None
    return _clean_url(src)


def _clean_url(u: Optional[str]) -> Optional[str]:
    if not u:
        return None
    u = u.strip().rstrip("&?")            # ตัด & หรือ ? ที่ห้อยท้าย
    if u.startswith("//"):
        u = "https:" + u
    elif u.startswith("/"):
        u = config.BASE_DOMAIN + u
    return u or None


# ---------------------------------------------------------------- ทั่วไป
def grab_text(page: Page, selector: str) -> str:
    if not selector:
        return ""
    try:
        el = page.query_selector(selector)
        return clean_text(el.inner_text()) if el else ""
    except Exception:
        return ""


def grab_all_text(page: Page, selector: str, sep: str = " ") -> str:
    """รวม text จากทุก element ที่เจอ (เช่น สถานที่ปฏิบัติงานที่มีหลายบรรทัด)"""
    if not selector:
        return ""
    try:
        parts = [clean_text(e.inner_text()) for e in page.query_selector_all(selector)]
        return sep.join(p for p in parts if p)
    except Exception:
        return ""


def grab_attr(page: Page, selector: str, attr: str) -> Optional[str]:
    if not selector:
        return None
    try:
        el = page.query_selector(selector)
        return _clean_url(el.get_attribute(attr)) if el else None
    except Exception:
        return None


def grab_detail_url(page: Page) -> Optional[str]:
    """
    URL หน้า 'รายละเอียดงาน' จากปุ่มสีส้ม
    ปุ่มเป็น <a href> จึงอ่าน href ไปเปิดตรง ๆ แทนการคลิก (ผลเหมือนกันแต่เสถียรกว่า)
    """
    href = grab_attr(page, config.SEL["detail_button"], "href")
    if href:
        return href.split("?")[0]
    u = page.url.split("?")[0]
    if "/th/company/job/" in u:
        return u.replace("/th/company/job/", "/th/job/")
    return None


# ---------------------------------------------------------------- แนะนำบริษัท
_JS_COMPANY_DESC = r"""
(cfg) => {
  const norm = t => (t || '').replace(/\s+/g, ' ').trim();

  // แนะนำบริษัทอยู่ "ก่อน" หัวข้อแรกของประกาศเสมอ
  const marks = ['สวัสดิการ', 'รายละเอียดงาน', 'คุณสมบัติผู้สมัคร', 'ติดต่อ'];
  let limit = null;
  for (const el of document.querySelectorAll('span,h1,h2,h3,h4,div,p')) {
    if (el.children.length === 0 && marks.includes(norm(el.textContent))) {
      if (!limit || (limit.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_PRECEDING)) {
        limit = el;
      }
    }
  }

  // สัญญาณว่าเป็น "กล่องข้อมูลงาน" ไม่ใช่คำแนะนำบริษัท
  const fieldLabels = ['สถานที่ปฏิบัติงาน', 'เงินเดือน', 'อัตรา', 'ดูรายละเอียดงาน',
                       'ดูรายละเอียดบริษัท', 'สมัครงาน', 'สนใจ', 'พิมพ์', 'แชร์',
                       'รับสมัครด่วน', 'Urgently Required', 'สัมภาษณ์งานออนไลน์',
                       'วิธีการสมัคร', 'Tags', 'เข้าสู่ระบบ', 'สมัครสมาชิก', 'ฝากประวัติ'];
  const dateRe = /\d{1,2}\s*(ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|ต\.ค\.|พ\.ย\.|ธ\.ค\.)\s*\d{2}/;
  const salaryRe = /\d{1,3}(,\d{3})+\s*(-|–|ถึง)?\s*(\d{1,3}(,\d{3})+)?\s*บาท/;

  const ok = (el) => {
    if (el.offsetParent === null) return null;
    if (el.closest('a')) return null;
    // ห้ามเป็นกล่องที่ "ครอบ" หัวข้อแรก (จะกินเนื้อหาส่วนอื่นมาด้วย)
    if (limit && (el === limit || el.contains(limit))) return null;
    if (limit) {
      const pos = el.compareDocumentPosition(limit);
      if (!(pos & Node.DOCUMENT_POSITION_FOLLOWING)) return null;
    }
    const t = norm(el.innerText);
    if (t.length < 60 || t.length > 4000) return null;
    if (fieldLabels.some(w => t.includes(w))) return null;
    if (dateRe.test(t)) return null;
    if (salaryRe.test(t)) return null;
    if (cfg.title && cfg.title.length > 3 && t.includes(cfg.title)) return null;
    if (cfg.company && t === cfg.company) return null;
    return el.innerText.trim();   // คงบรรทัดเดิมไว้ (ไม่ใช่ norm)
  };

  // เลือกกล่องที่ "ยาวที่สุด" ที่ยังผ่านเงื่อนไขทั้งหมด
  // เพราะคำแนะนำบริษัทมักมีหลายย่อหน้า — ต้องได้กล่องแม่ที่ครอบครบทุกย่อหน้า
  let best = '';
  for (const el of document.querySelectorAll('div,section,article,p,span')) {
    const t = ok(el);
    if (t && t.length > best.length) best = t;
  }
  return best || null;
}
"""


def grab_company_desc(page: Page, job_title: str = "", company: str = "") -> str:
    """
    หาย่อหน้าแนะนำบริษัท — หน้าเว็บไม่มีหัวข้อกำกับ จึงต้องใช้การกรอง
    ส่ง job_title/company เข้ามาช่วยตัดกล่องสรุปหัวประกาศออก
    """
    try:
        t = page.evaluate(_JS_COMPANY_DESC,
                          {"title": job_title or "", "company": company or ""})
    except Exception:
        return ""
    if not t:
        return ""
    t = _cut_at_stop_label(_strip_excluded(clean_text(t)))
    return t if len(t) >= 50 else ""


# ---------------------------------------------------------------- debug
_JS_ALL_IMAGES = r"""
() => {
 const out = Array.from(document.querySelectorAll('img')).map(im => ({
  id: im.id || '',
  src: (im.currentSrc || im.getAttribute('src') || '').slice(0, 130),
  dataSrc: (im.getAttribute('data-src') || '').slice(0, 130),
  srcset: (im.getAttribute('srcset') || '').slice(0, 130),
  alt: (im.alt || '').slice(0, 60),
  w: im.naturalWidth, h: im.naturalHeight,
 }));
 // เพิ่ม <source srcset> และ CSS background-image ที่ชี้ไป media.jobthai.com
 for (const so of document.querySelectorAll('picture source[srcset]')) {
   const u = (so.getAttribute('srcset') || '').split(',')[0].trim().split(' ')[0];
   if (u) out.push({id:'<source>', src:u.slice(0,130), dataSrc:'', srcset:'', alt:'', w:0, h:0});
 }
 for (const el of document.querySelectorAll('div,span,a')) {
   const bg = getComputedStyle(el).backgroundImage || '';
   const m = bg.match(/url\(["']?([^"')]+)["']?\)/);
   if (m && m[1].includes('media.jobthai.com')) {
     out.push({id:'<css-bg>', src:m[1].slice(0,130), dataSrc:'', srcset:'', alt:'', w:0, h:0});
   }
 }
 return out;
}
"""


def list_images(page: Page):
    """คืนรายการรูปทั้งหมดในหน้า — ใช้หาสาเหตุเวลาโลโก้ดึงไม่ได้"""
    try:
        return page.evaluate(_JS_ALL_IMAGES) or []
    except Exception:
        return []