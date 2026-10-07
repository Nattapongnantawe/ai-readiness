# -*- coding: utf-8 -*-
r"""
Module 3 — Dense embeddings (BAAI/bge-m3) + pgvector

  python -m extractor.embed skills                         # embed ทักษะทั้งหมด (ครั้งเดียว)
  python -m extractor.embed std --sf "data\Unique-Skills-List-Sep-2026.xlsx" --onet data\onet_technology_skills.csv
                                                            # โหลด+embed รายการทักษะของมาตรฐาน
  python -m extractor.embed std --thai std_data\thai_std.csv   # มาตรฐานไทย DSD + TPQI (ภาษาไทย)
  python -m extractor.embed map --dry-run                  # จับคู่ด้วยความหมาย (ดูผลก่อน)
  python -m extractor.embed map --only DSD TPQI --dry-run  # เฉพาะมาตรฐานที่ระบุ
  python -m extractor.embed map --threshold 0.80           # บันทึกจริง
  python -m extractor.embed jobs                           # embed ประกาศงาน (semantic search)
  python -m extractor.embed search "พัฒนาเว็บ frontend react"

จับคู่ด้วยความหมายจะ "เติม" เฉพาะทักษะที่ยังไม่มีคู่ในมาตรฐานนั้น — ไม่ทับผลตรงตัวอักษรที่ตรวจแล้ว
"""
import argparse
import csv
import os
import re
import sys

import numpy as np
import psycopg2
from psycopg2.extras import execute_batch

from . import config

MODEL = "BAAI/bge-m3"
THRESHOLD = 0.87          # ตรวจแล้ว: ช่วง 0.80–0.86 จับผิดราว 1 ใน 3, ≥0.87 ถูกเกือบทั้งหมด
# มาตรฐานภาษาไทย: ชื่อทักษะเราเป็นอังกฤษ -> ความคล้ายข้ามภาษาต่ำกว่าโดยธรรมชาติ ใช้เกณฑ์แยก
STD_THRESHOLD = {"DSD": 0.75, "TPQI": 0.75}
THAI_STD = {"DSD", "TPQI"}

# คู่ที่ตรวจด้วยตาแล้วว่าถูก แม้คะแนนต่ำกว่าเกณฑ์: (ทักษะของเรา, มาตรฐาน) -> label ที่ยอมรับ
SEMANTIC_ALLOW = {
    ("Reading Electrical Drawings", "SKILLSFUTURE"): "Electrical Drawing",
    ("Reading Electrical Drawing", "SKILLSFUTURE"): "Electrical Drawing",
    ("Presentation", "SKILLSFUTURE"): "Technical Presentation",
    ("Incident Management", "SKILLSFUTURE"): "Incident Response",
}
# คู่ที่ตรวจแล้วว่าผิดแม้คะแนนผ่านเกณฑ์: (ทักษะของเรา, มาตรฐาน, label)
SEMANTIC_BLOCK = {
    ("Technical Support", "SKILLSFUTURE", "Technical Sales Support"),
    # DSD / TPQI (ตรวจจาก dry-run) — เทียบแบบ "ขึ้นต้นด้วย"
    ("System Design", "TPQI", "ออกแบบการทดสอบ System Test"),
    ("System Design", "DSD", "การออกแบบระบบเครือข่ายคอมพิวเตอร์"),
    ("System Integration", "TPQI", "ออกแบบระบบเพื่อพัฒนาโปรแกรมแบบ Integration"),
    ("Software Installation", "DSD", "การใช้โปรแกรมระบบปฏิบัติการ"),
    ("Security", "DSD", "ความปลอดภัย"),                       # IT security ≠ ความปลอดภัยในการทำงาน
    ("Electronics", "DSD", "IEEE"),                           # ชื่อองค์กร ไม่ใช่ทักษะ
}
SEMANTIC_ALLOW.update({
    ("Computer Networking", "DSD"): "การออกแบบระบบเครือข่ายคอมพิวเตอร์",
    ("PLC", "TPQI"): "เขียนโปรแกรมควบคุมด้วยพีแอลซี",
    ("Corrective Maintenance", "TPQI"): "ซ่อมแซมเครื่องจักรและอุปกรณ์",
})
LEXICAL_MIN = 0.55        # มาตรฐานไทย: ชื่อทักษะอังกฤษปรากฏตรงตัวในข้อความ (เช่น "เช่น MySQL") + ความคล้าย ≥ ค่านี้


def _blocked(name, std, label):
    return any(n == name and s == std and label.startswith(p) for n, s, p in SEMANTIC_BLOCK)


def _allowed(name, std, label):
    p = SEMANTIC_ALLOW.get((name, std))
    return bool(p) and label.startswith(p)


def _lexical_ok(name):
    n = name.strip()
    return len(n) >= 3 and not n.isdigit()
DIM = 1024


# ---------------- helpers ----------------
def connect():
    conn = psycopg2.connect(config.DATABASE_URL)
    from pgvector.psycopg2 import register_vector
    register_vector(conn)
    return conn


def to_np(v):
    """pgvector คืนค่าเป็น Vector (เวอร์ชันใหม่) หรือ numpy (เวอร์ชันเก่า) -> numpy เสมอ"""
    if hasattr(v, "to_numpy"):
        return v.to_numpy()
    if hasattr(v, "to_list"):
        return np.asarray(v.to_list(), dtype=np.float32)
    return np.asarray(v, dtype=np.float32)


_M = None


def model():
    global _M
    if _M is None:
        import torch
        from sentence_transformers import SentenceTransformer
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🧠 โหลด {MODEL} บน {dev.upper()}"
              + (f" ({torch.cuda.get_device_name(0)})" if dev == "cuda" else " — ช้ากว่า GPU มาก"))
        _M = SentenceTransformer(MODEL, device=dev)
        if dev == "cuda":
            _M.half()                                    # fp16: ประหยัด VRAM (GTX 1650 4GB)
    return _M


def encode(texts, batch=64, max_len=64):
    m = model()
    m.max_seq_length = max_len
    return m.encode(texts, batch_size=batch, normalize_embeddings=True,
                    show_progress_bar=True, convert_to_numpy=True).astype(np.float32)


# ---------------- skills ----------------
def cmd_skills(a):
    conn = connect()
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM skills WHERE %s OR embedding IS NULL ORDER BY id", (a.force,))
        rows = cur.fetchall()
    print(f"🔤 ทักษะที่ต้อง embed: {len(rows)}")
    if not rows:
        return
    vecs = encode([n for _, n in rows], batch=64, max_len=32)
    with conn.cursor() as cur:
        execute_batch(cur, "UPDATE skills SET embedding = %s WHERE id = %s",
                      [(v, i) for (i, _), v in zip(rows, vecs)], page_size=500)
    conn.commit()
    conn.close()
    print("✅ เสร็จ")


# ---------------- standards ----------------
def read_onet(path):
    seen = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        head = f.readline()
        f.seek(0)
        for r in csv.DictReader(f, delimiter="\t" if head.count("\t") > head.count(",") else ","):
            lab = (r.get("Workplace Example") or r.get("Example") or "").strip()
            if lab and lab not in seen:
                seen[lab] = {"code": None, "label": lab,
                             "type": (r.get("Element Name") or r.get("Commodity Title") or "").strip(),
                             "desc": None}
    return list(seen.values())


def read_esco(path):
    """ESCO skills_en.csv (ดาวน์โหลดจาก esco.ec.europa.eu) — ถ้ามี"""
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("preferredLabel"):
                out.append({"code": r.get("conceptUri"), "label": r["preferredLabel"].strip(),
                            "type": r.get("skillType"), "desc": (r.get("description") or "")[:500]})
    return out


def read_thai(path):
    """std_data/thai_std.csv: standard,std_code,label,std_type,description (DSD/TPQI)"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [(r["standard"], {"code": r["std_code"], "label": r["label"], "type": r["std_type"],
                                 "desc": r["description"]}) for r in csv.DictReader(f)]


def cmd_std(a):
    items = []
    if a.thai:
        items += read_thai(a.thai)
    if a.sf:
        from .sf_map import load_sf
        items += [("SKILLSFUTURE", {"code": x["id"], "label": x["title"], "type": x["type"],
                                    "desc": (x.get("desc") or "")[:500]}) for x in load_sf(a.sf)]
    if a.onet:
        items += [("ONET", x) for x in read_onet(a.onet)]
    if a.esco:
        items += [("ESCO", x) for x in read_esco(a.esco)]
    if not items:
        print("ระบุอย่างน้อย 1 ไฟล์: --sf / --onet / --esco / --thai")
        sys.exit(1)

    conn = connect()
    with conn.cursor() as cur:
        execute_batch(cur, """INSERT INTO std_skills (standard, std_code, label, std_type, description)
                              VALUES (%s,%s,%s,%s,%s) ON CONFLICT (standard, label) DO NOTHING""",
                      [(s, x["code"], x["label"], x["type"], x["desc"]) for s, x in items], page_size=1000)
        conn.commit()
        cur.execute("SELECT id, label, standard FROM std_skills WHERE embedding IS NULL ORDER BY id")
        rows = cur.fetchall()
    print(f"📚 รายการมาตรฐานที่ต้อง embed: {len(rows)}")
    for thai in (False, True):                           # ภาษาไทยยาวกว่า -> token มากกว่า
        part = [(i, l) for i, l, s in rows if (s in THAI_STD) == thai]
        if not part:
            continue
        vecs = encode([l for _, l in part], batch=32 if thai else 64, max_len=96 if thai else 32)
        with conn.cursor() as cur:
            execute_batch(cur, "UPDATE std_skills SET embedding = %s WHERE id = %s",
                          [(v, i) for (i, _), v in zip(part, vecs)], page_size=500)
        conn.commit()
    with conn.cursor() as cur:
        cur.execute("SELECT standard, count(*) FROM std_skills GROUP BY 1 ORDER BY 1")
        for s, n in cur.fetchall():
            print(f"   {s:14} {n:>6}")
    conn.close()


# ---------------- semantic mapping ----------------
def cmd_map(a):
    conn = connect()
    with conn.cursor() as cur:
        cur.execute("""SELECT s.id, s.name, s.embedding, count(js.job_id)
                       FROM skills s LEFT JOIN job_skills js ON js.skill_id = s.id
                       WHERE s.embedding IS NOT NULL GROUP BY s.id""")
        sk = cur.fetchall()
        cur.execute("SELECT skill_id, standard FROM skill_standard_map WHERE method <> 'semantic'")
        have = set(cur.fetchall())
        cur.execute("SELECT DISTINCT standard FROM std_skills WHERE embedding IS NOT NULL")
        stds = [r[0] for r in cur.fetchall()]
    if a.only:
        stds = [s for s in stds if s in {x.upper() for x in a.only}]
    print("มาตรฐานที่จับคู่: " + ", ".join(f"{s} (≥{STD_THRESHOLD.get(s, a.threshold)})" for s in stds))
    if not sk:
        print("❌ ยังไม่ได้ embed ทักษะ — รัน: python -m extractor.embed skills")
        return
    S = np.vstack([to_np(r[2]) for r in sk]).astype(np.float32)
    sk_idx = {r[0]: i for i, r in enumerate(sk)}
    review, new = [], []
    for std in stds:
        with conn.cursor() as cur:
            cur.execute("SELECT std_code, label, std_type, embedding, description FROM std_skills "
                        "WHERE standard = %s AND embedding IS NOT NULL", (std,))
            lab = cur.fetchall()
        E = np.vstack([to_np(r[3]) for r in lab]).astype(np.float32)
        low = [r[1].lower() for r in lab]
        best_i = np.empty(len(sk), dtype=np.int64)
        best_s = np.empty(len(sk), dtype=np.float32)
        for i in range(0, len(sk), 1024):                # คูณเป็นก้อน ประหยัด RAM
            sims = S[i:i + 1024] @ E.T
            best_i[i:i + 1024] = sims.argmax(1)
            best_s[i:i + 1024] = sims.max(1)
        th = STD_THRESHOLD.get(std, a.threshold)
        for (sid, name, _, freq), j, sc in zip(sk, best_i, best_s):
            if (sid, std) in have:
                continue                                  # มีคู่แบบ exact แล้ว ไม่ทับ
            ok = (sc >= th or _allowed(name, std, lab[j][1])) and not _blocked(name, std, lab[j][1])
            if not ok and std in THAI_STD and _lexical_ok(name):
                # ชื่อทักษะอังกฤษอยู่ในข้อความมาตรฐานไทยตรงตัว -> เลือกข้อที่คล้ายที่สุดในกลุ่มนั้น
                nl = name.lower()
                rx = re.compile(r"(?<![A-Za-z0-9])" + re.escape(nl) + r"(?![A-Za-z0-9])")
                cand = [k for k, lb in enumerate(low) if nl in lb and rx.search(lb)
                        and not _blocked(name, std, lab[k][1])]
                if cand:
                    k = max(cand, key=lambda k: float(S[sk_idx[sid]] @ E[k]))
                    s2 = float(S[sk_idx[sid]] @ E[k])
                    if s2 >= LEXICAL_MIN:
                        j, sc, ok = k, s2, True
            review.append((freq, name, std, lab[j][1], round(float(sc), 3), "Y" if ok else "",
                           lab[j][4] or "", th))
            if ok:
                new.append((sid, std, lab[j][0], lab[j][1], lab[j][2], float(sc)))

    review.sort(key=lambda r: (-r[0], -r[4]))
    os.makedirs("output", exist_ok=True)
    path = os.path.join("output", "semantic_review.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["freq", "skill", "standard", "nearest_label", "similarity", "accepted", "context"])
        w.writerows(r[:7] for r in review if r[4] >= r[7] - 0.10)
    acc = [r for r in review if r[5]]
    print(f"\n🔗 เติมคู่ใหม่ {len(new)} รายการ")
    for std in stds:
        k = sum(1 for r in acc if r[2] == std)
        print(f"   {std:14} {k:>5}")
    print(f"\n▶ {a.show} อันดับแรก (ทักษะที่พบบ่อย) — ตรวจว่าความหมายตรงไหม")
    for freq, name, std, lb, sc, *_ in acc[:a.show]:
        print(f"   {name[:26]:28}({freq:>4}) {std[:5]:6} -> {lb[:44]:46} {sc:.3f}")
    print(f"\n▶ ใกล้เกณฑ์แต่ไม่ผ่าน (ตัวอย่าง)")
    for freq, name, std, lb, sc, *_ in [r for r in review if not r[5] and r[4] >= r[7] - 0.10][:15]:
        print(f"   {name[:26]:28}({freq:>4}) {std[:5]:6} ~ {lb[:44]:46} {sc:.3f}")
    print(f"\n💾 ทุกคู่สำหรับตรวจ: {path}")

    if a.dry_run:
        print("--dry-run: ไม่เขียน DB")
        return
    with conn.cursor() as cur:
        cur.execute("DELETE FROM skill_standard_map WHERE method = 'semantic' AND standard = ANY(%s)",
                    (stds,))
        execute_batch(cur, """INSERT INTO skill_standard_map
                              (skill_id, standard, std_code, std_label, std_type, score, method)
                              VALUES (%s,%s,%s,%s,%s,%s,'semantic')
                              ON CONFLICT (skill_id, standard) DO NOTHING""", new, page_size=500)
        conn.commit()
        cur.execute("SELECT * FROM v_std_coverage_by_standard ORDER BY weighted_pct DESC")
        print(f"\n{'มาตรฐาน':22}{'ทักษะ':>8}{'% ไม่ซ้ำ':>12}{'% ถ่วงน้ำหนัก':>16}")
        for std, n, up, wp in cur.fetchall():
            print(f"{std:22}{n:>8}{up:>11}%{wp:>15}%")
    conn.close()


# ---------------- jobs + search ----------------
def cmd_jobs(a):
    conn = connect()
    with conn.cursor() as cur:
        cur.execute("""SELECT id, title, coalesce(description,''), coalesce(qualification,'')
                       FROM jobs WHERE %s OR embedding IS NULL ORDER BY id""", (a.force,))
        rows = cur.fetchall()
    print(f"📄 ประกาศที่ต้อง embed: {len(rows)}")
    if not rows:
        return
    texts = [f"{t}\n{d}\n{q}"[:2000] for _, t, d, q in rows]
    vecs = encode(texts, batch=8, max_len=512)          # ยาว -> batch เล็ก (VRAM 4GB)
    with conn.cursor() as cur:
        execute_batch(cur, "UPDATE jobs SET embedding = %s WHERE id = %s",
                      [(v, r[0]) for r, v in zip(rows, vecs)], page_size=200)
    conn.commit()
    conn.close()
    print("✅ เสร็จ")


def cmd_search(a):
    q = encode([a.query], batch=1, max_len=128)[0]
    conn = connect()
    with conn.cursor() as cur:
        cur.execute("""SELECT j.title, c.name, j.province, 1 - (j.embedding <=> %s) AS sim
                       FROM jobs j LEFT JOIN companies c ON c.id = j.company_id
                       WHERE j.embedding IS NOT NULL ORDER BY j.embedding <=> %s LIMIT %s""",
                    (q, q, a.k))
        print(f"\n🔎 งานที่ใกล้เคียง: '{a.query}'")
        for t, c, p, s in cur.fetchall():
            print(f"   {s:.3f}  {t[:50]:52} {(c or '')[:30]:32} {p or ''}")
        cur.execute("""SELECT name, 1 - (embedding <=> %s) FROM skills WHERE embedding IS NOT NULL
                       ORDER BY embedding <=> %s LIMIT 10""", (q, q))
        print("\n🧩 ทักษะที่เกี่ยวข้อง: " + ", ".join(f"{n} ({s:.2f})" for n, s in cur.fetchall()))
    conn.close()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("skills"); p.add_argument("--force", action="store_true")
    p = sub.add_parser("std"); p.add_argument("--sf"); p.add_argument("--onet"); p.add_argument("--esco")
    p.add_argument("--thai")
    p = sub.add_parser("map"); p.add_argument("--threshold", type=float, default=THRESHOLD)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", nargs="+", help="เฉพาะมาตรฐาน เช่น DSD TPQI")
    p.add_argument("--show", type=int, default=30)
    p = sub.add_parser("jobs"); p.add_argument("--force", action="store_true")
    p = sub.add_parser("search"); p.add_argument("query"); p.add_argument("-k", type=int, default=10)
    a = ap.parse_args()
    {"skills": cmd_skills, "std": cmd_std, "map": cmd_map, "jobs": cmd_jobs, "search": cmd_search}[a.cmd](a)


if __name__ == "__main__":
    main()