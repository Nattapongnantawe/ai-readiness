"""ดาวน์โหลดมาตรฐานไทย 2 แหล่ง (รันบนเครื่องตัวเอง — เว็บราชการไทยเข้าได้ปกติ)

  1) DSD  กรมพัฒนาฝีมือแรงงาน: มาตรฐานฝีมือแรงงานแห่งชาติ กลุ่มช่างไฟฟ้า อิเล็กทรอนิกส์และคอมพิวเตอร์ (PDF)
  2) TPQI สถาบันคุณวุฒิวิชาชีพ: มาตรฐานอาชีพ -> คุณวุฒิ -> หน่วยสมรรถนะ (+หน่วยย่อย)
         สาขา: อุตสาหกรรมดิจิทัล(81), ไฟฟ้าและอิเล็กทรอนิกส์(91), หุ่นยนต์และระบบอัตโนมัติ(85)

ใช้:
  pip install requests beautifulsoup4
  python -m extractor.std_fetch dsd
  python -m extractor.std_fetch tpqi              # หน่วยสมรรถนะ (เร็ว)
  python -m extractor.std_fetch tpqi --detail     # + หน่วยสมรรถนะย่อย (ช้ากว่า ~10 นาที)
ผลลัพธ์: std_data/dsd/*.pdf, std_data/tpqi_units.csv, std_data/tpqi_elements.csv
HTML ที่โหลดเก็บไว้ใน std_data/cache/ (รันซ้ำไม่โหลดใหม่)
"""
import argparse, csv, hashlib, re, sys, time
from pathlib import Path

import requests
import urllib3

OUT = Path("std_data")
CACHE = OUT / "cache"
UA = {"User-Agent": "Mozilla/5.0 (capstone research; job-market skill study)"}

DSD_BASE = "https://www.dsd.go.th/standard/Region/Download_Doc/"
DSD_DOCS = {   # กลุ่มสาขาอาชีพช่างไฟฟ้า อิเล็กทรอนิกส์และคอมพิวเตอร์ (ไม่รวมฉบับที่ยกเลิก 257, 260)
    256: "ช่างไฟฟ้าการควบคุมทางอุตสาหกรรม",
    258: "ช่างไฟฟ้าภายนอกอาคาร",
    259: "ช่างเทคนิคเครื่องปรับอากาศสำหรับห้องสะอาด",
    261: "ผู้ดูแลระบบเครือข่ายคอมพิวเตอร์",
    262: "นักเขียนโปรแกรมคอมพิวเตอร์ (ภาษาซี)",
    263: "ช่างไฟฟ้าภายในอาคาร",
    264: "ช่างเครื่องทำความเย็นในบ้านและการพาณิชย์",
    265: "ช่างไฟฟ้าอุตสาหกรรม",
    266: "ช่างซ่อมไมโครคอมพิวเตอร์",
    267: "ช่างโทรทัศน์",
    268: "ช่างเครื่องปรับอากาศในบ้าน",
    269: "นักออกแบบระบบสื่อสาร",
    270: "ช่างเครือข่ายมีสาย",
    271: "ช่างไมโครเวฟ",
    272: "ตารางทำการ",
    273: "การนำเสนอผลงาน",
    274: "ประมวลผลคำ",
    1494: "ช่างติดตั้งระบบทำน้ำอุ่นและน้ำร้อนด้วยไฟฟ้า",
    1495: "ช่างระบบการต่อลงดินและป้องกันฟ้าผ่า",
    4738: "ช่างอิเล็กทรอนิกส์",
}

TPQI_BASE = "https://tpqi-net.tpqi.go.th"
TPQI_SECTORS = {81: "อุตสาหกรรมดิจิทัล", 91: "ไฟฟ้าและอิเล็กทรอนิกส์", 85: "หุ่นยนต์และระบบอัตโนมัติ"}

_insecure = False


def get(url, binary=False, delay=0.4):
    """GET + cache; ถ้าใบรับรอง SSL ของเว็บราชการมีปัญหา จะลองซ้ำแบบไม่ตรวจใบรับรอง (เอกสารสาธารณะ)"""
    global _insecure
    CACHE.mkdir(parents=True, exist_ok=True)
    fn = CACHE / (hashlib.md5(url.encode()).hexdigest() + (".bin" if binary else ".html"))
    if fn.exists() and fn.stat().st_size > 0:
        return fn.read_bytes() if binary else fn.read_text(encoding="utf-8")
    for attempt in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=60, verify=not _insecure)
            r.raise_for_status()
            break
        except requests.exceptions.SSLError:
            if not _insecure:
                print("   ⚠️ SSL ของเว็บไม่ผ่าน — ลองใหม่แบบไม่ตรวจใบรับรอง")
                urllib3.disable_warnings()
                _insecure = True
                continue
            raise
        except requests.RequestException as e:
            if attempt == 3:
                print(f"   ❌ {url}: {e}")
                return None
            time.sleep(2 * (attempt + 1))
    time.sleep(delay)
    if binary:
        fn.write_bytes(r.content)
        return r.content
    r.encoding = r.apparent_encoding if r.encoding in (None, "ISO-8859-1") else r.encoding
    fn.write_text(r.text, encoding="utf-8")
    return r.text


# ---------------- DSD ----------------
def cmd_dsd(a):
    d = OUT / "dsd"; d.mkdir(parents=True, exist_ok=True)
    ok = 0
    for doc_id, name in DSD_DOCS.items():
        fn = d / f"{doc_id}_{name}.pdf"
        if fn.exists() and fn.stat().st_size > 1000:
            ok += 1; continue
        data = get(DSD_BASE + str(doc_id), binary=True)
        if not data or not data[:5] == b"%PDF-":
            print(f"   ❌ {doc_id} {name}: ไม่ใช่ PDF ({len(data or b'')} bytes)")
            continue
        fn.write_bytes(data); ok += 1
        print(f"   ✔ {fn.name}  {len(data)//1024} KB")
    print(f"📄 DSD: {ok}/{len(DSD_DOCS)} ไฟล์ -> {d}")
    print("   ขั้นต่อไป: zip โฟลเดอร์ std_data\\dsd แล้วส่งมาให้สกัดข้อความ")


# ---------------- TPQI ----------------
def soup(html):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "html.parser")


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


UNIT_CODE = re.compile(r"\b([A-Z]{2,6}-[A-Z0-9]{3,6}-\d{3}[A-Z]?|\d{5,6})\b")
LEVEL = re.compile(r"ระดับ\s*(\d)")


def parse_sector(html):
    s = soup(html); out = {}
    for a in s.find_all("a", href=True):
        m = re.search(r"/qualifications/(\d+)/?$", a["href"])
        if m:
            out.setdefault(int(m.group(1)), clean(a.get_text(" ")))
    return out


def parse_qual(html):
    s = soup(html)
    text = clean(s.get_text(" "))
    title = ""
    for tag in s.find_all(["h1", "h2", "h3", "h4", "h5", "p", "div", "span", "td"]):
        t = clean(tag.get_text(" "))
        if t.startswith("สาขาวิชาชีพ") and "ระดับ" in t and len(t) < 250:
            title = t; break
    if not title:
        m = re.search(r"(สาขาวิชาชีพ.{5,200}?ระดับ\s*\d)", text)
        title = m.group(1) if m else ""
    lv = LEVEL.search(title)
    occ = re.search(r"อาชีพ\s*(.+?)\s*ระดับ", title)
    units, seen = [], set()
    for a in s.find_all("a", href=True):
        m = re.search(r"unitinfo/(\d+)", a["href"])
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        row = a.find_parent("tr") or a.find_parent("li") or a.parent
        t = clean(row.get_text(" ")) if row else clean(a.get_text(" "))
        cm = UNIT_CODE.search(t)
        code = cm.group(1) if cm else ""
        name = clean(t.replace(code, "", 1)) if code else t
        name = re.sub(r"^(รหัส|หน่วยสมรรถนะ|ชื่อหน่วยสมรรถนะ)\s*", "", name)
        units.append({"unit_id": int(m.group(1)), "unit_code": code, "unit_title": name})
    return {"title": title, "level": int(lv.group(1)) if lv else None,
            "occupation": clean(occ.group(1)) if occ else "", "units": units}


ELEM = re.compile(r"(\d{5,6}\.\d{2})\s+(.+?)(?=\s+\d{5,6}\.\d{2}\s|\s+\d{6}\s|$)")


def parse_unit(html):
    s = soup(html)
    text = clean(s.get_text(" "))
    code = UNIT_CODE.search(text)
    elems = []
    seen = set()
    for m in ELEM.finditer(text):
        k = m.group(1)
        if k in seen:
            continue
        seen.add(k)
        elems.append({"element_code": k, "element_title": clean(m.group(2))[:200]})
    return elems


def cmd_tpqi(a):
    OUT.mkdir(exist_ok=True)
    quals = {}
    for sid, sname in TPQI_SECTORS.items():
        html = get(f"{TPQI_BASE}/tpqi-industrialInfo/detail/{sid}")
        q = parse_sector(html or "")
        print(f"🏷️  {sname}: {len(q)} คุณวุฒิ")
        for qid, qname in q.items():
            quals.setdefault(qid, (sid, sname, qname))
    if not quals:
        sys.exit("❌ ไม่พบลิงก์คุณวุฒิ — ส่งไฟล์ใน std_data/cache มาให้ดูโครง HTML")

    rows, elements = [], []
    for i, (qid, (sid, sname, qname)) in enumerate(quals.items(), 1):
        html = get(f"{TPQI_BASE}/qualifications/{qid}")
        if not html:
            continue
        q = parse_qual(html)
        if i % 20 == 0 or i == len(quals):
            print(f"   {i}/{len(quals)} คุณวุฒิ, หน่วยสมรรถนะสะสม {len(rows)}")
        for u in q["units"]:
            rows.append({"sector_id": sid, "sector": sname, "qual_id": qid,
                         "qualification": q["title"] or qname, "occupation": q["occupation"],
                         "level": q["level"], **u})
    # หน่วยเดียวกันใช้ซ้ำหลายคุณวุฒิ
    uniq = {r["unit_id"] for r in rows}
    print(f"📚 TPQI: {len(quals)} คุณวุฒิ, {len(rows)} แถว, หน่วยสมรรถนะไม่ซ้ำ {len(uniq)}")
    if rows and sum(1 for r in rows if r["unit_code"]) < len(rows) * 0.5:
        print("   ⚠️ อ่านรหัสหน่วยได้ไม่ถึงครึ่ง — ส่ง tpqi_units.csv มาให้ตรวจ")

    cols = ["sector_id", "sector", "qual_id", "qualification", "occupation", "level",
            "unit_id", "unit_code", "unit_title"]
    with open(OUT / "tpqi_units.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    print(f"💾 {OUT / 'tpqi_units.csv'}")

    if a.detail:
        for j, uid in enumerate(sorted(uniq), 1):
            html = get(f"{TPQI_BASE}/qualifications/unitinfo/{uid}")
            for e in parse_unit(html or ""):
                elements.append({"unit_id": uid, **e})
            if j % 50 == 0 or j == len(uniq):
                print(f"   {j}/{len(uniq)} หน่วย, หน่วยย่อย {len(elements)}")
        with open(OUT / "tpqi_elements.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["unit_id", "element_code", "element_title"])
            w.writeheader(); w.writerows(elements)
        print(f"💾 {OUT / 'tpqi_elements.csv'}")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("dsd")
    p = sp.add_parser("tpqi"); p.add_argument("--detail", action="store_true")
    a = ap.parse_args()
    {"dsd": cmd_dsd, "tpqi": cmd_tpqi}[a.cmd](a)


if __name__ == "__main__":
    main()
