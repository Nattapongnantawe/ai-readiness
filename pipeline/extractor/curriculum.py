"""Module 3 — Curriculum Courses ↔ ทักษะตลาดงาน (Skill Gap)

ขั้นตอน (รันจากโฟลเดอร์ pipeline):
  python -m extractor.curriculum migrate            # สร้างตาราง (แทน psql)
  python -m extractor.curriculum load  output/curriculum_courses.json
  python -m extractor.curriculum embed
  python -m extractor.curriculum map --dry-run      # ดูคู่ก่อน -> output/curriculum_skill_review.csv
  python -m extractor.curriculum map                # เขียน course_skill_map
  python -m extractor.curriculum gap --top 40       # ทักษะที่ตลาดต้องการแต่หลักสูตรไม่ครอบคลุม
  python -m extractor.curriculum search "เขียนเว็บ react"   # หาวิชาที่ใกล้กับคำค้น
"""
import argparse, csv, json, os, re, sys
from pathlib import Path

import numpy as np

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DSN = os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/jobmarket_test")
MODEL = "BAAI/bge-m3"
OUT = Path("output")

THRESHOLD = 0.80          # หัวข้อวิชา ↔ ชื่อทักษะ (ปรับด้วย --threshold)
REVIEW_LOW = 0.70         # 0.70–threshold เก็บลง review csv ไว้ตรวจ

# ทักษะคำเดียวที่ยอมให้จับแบบตรงตัว (คำเดียวทั่วไปอย่าง Communication/Design เสี่ยงจับผิดความหมาย)
EXACT_SINGLE_OK = {"unix", "linux", "python", "java", "arduino", "android", "matlab", "php",
                   "javascript", "html", "css", "sql", "nosql", "plc", "iot", "hdl", "vhdl",
                   "verilog", "gis", "tcp/ip", "fpga", "scada", "cad", "uml", "excel",
                   "agile", "scrum", "git", "docker", "kubernetes", "mysql", "oracle",
                   "postgresql", "mongodb", "vpn", "firewall", "arduino", "raspberry pi"}
# คู่ที่รู้ว่าผิดความหมาย (skill, course_code) หรือ (skill, None) = ห้ามทุกวิชา
MAP_BLOCK = {
    ("Communication", "EN-012-103"),               # Data Communication ≠ ทักษะการสื่อสาร
}
# แบบ regex: (รูปแบบชื่อทักษะ, course_code)
MAP_BLOCK_RE = [
    (re.compile(r"electrical", re.I), "EN-001-001"),   # เขียนแบบวิศวกรรม = งานเครื่องกล ไม่มีแบบไฟฟ้า
]

def blocked(skill, code):
    if (skill, None) in MAP_BLOCK or (skill, code) in MAP_BLOCK:
        return True
    return any(c == code and rx.search(skill) for rx, c in MAP_BLOCK_RE)
# จับคู่โดยผู้วิจัย (method='manual') — เฉพาะที่คำอธิบายรายวิชาระบุไว้ชัดแต่ใช้คำต่างกัน
# รายงานแยกจาก exact/semantic ได้เสมอ
CURRICULUM_ALLOW = {
    "SQL":                  ["EN-012-313"],                                   # "query language"
    "Microsoft Word":       ["GE-010-003"],                                   # "word processing"
    "Microsoft PowerPoint": ["GE-010-003"],                                   # "presentation tools"
    "Microsoft Excel":      ["GE-010-003"],                                   # "spreadsheet Excel"
    "Microsoft Office":     ["GE-010-003"],                                   # "office application skills"
    "Presentation":         ["GE-020-003", "GE-010-003", "EN-012-212", "EN-012-317", "EN-012-318"],
    "Communication":        ["GE-010-001", "GE-010-002", "GE-020-003"],       # "communicating/communication"
    "Teamwork":             ["EN-012-212", "EN-012-317", "EN-012-318"],       # "project in a team"
}


# ---------- DB ----------
def connect():
    import psycopg2
    conn = psycopg2.connect(DSN)
    print(f"🗄️  ฐานข้อมูล: {conn.get_dsn_parameters().get('dbname')}")
    return conn


def skill_cols(cur):
    cur.execute("""SELECT column_name FROM information_schema.columns
                   WHERE table_name='skills' AND table_schema='public'""")
    cols = {r[0] for r in cur.fetchall()}
    sid = "skill_id" if "skill_id" in cols else "id"
    name = next(c for c in ("name", "canonical_name", "skill_name") if c in cols)
    stype = "skill_type" if "skill_type" in cols else None
    return sid, name, stype


def vec_sql(v):
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def parse_vec(s):
    return np.array(s.strip("[]").split(","), dtype=np.float32)


# ---------- model ----------
_M = None
def model():
    global _M
    if _M is None:
        import torch
        from sentence_transformers import SentenceTransformer
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🧠 โหลด {MODEL} บน {dev.upper()}"
              + (f" ({torch.cuda.get_device_name(0)})" if dev == "cuda" else ""))
        _M = SentenceTransformer(MODEL, device=dev)
        if dev == "cuda":
            _M.half()
    return _M


def encode(texts, batch=32, max_len=512):
    m = model()
    m.max_seq_length = max_len
    return m.encode(texts, batch_size=batch, normalize_embeddings=True,
                    show_progress_bar=len(texts) > 64, convert_to_numpy=True).astype(np.float32)


# ---------- topics ----------
LEAD = re.compile(r"^(and|or|the|including|introduction to|basic|fundamentals? of|principles? of|"
                  r"concepts? of|study of|studies of)\s+", re.I)

def split_topics(c):
    """ชื่อวิชา + หัวข้อย่อยจากคำอธิบายภาษาอังกฤษ"""
    parts = [c["name_en"] or ""]
    desc = (c.get("description_en") or "").replace(". ", "; ")
    for p in re.split(r"[;:]|,(?![^()]*\))", desc):
        p = p.strip(" .")
        if p.count("(") != p.count(")"):
            p = p.strip("()").replace("(", "").replace(")", "") if p.count("(") + p.count(")") == 1 else p
        for _ in range(3):
            p = LEAD.sub("", p).strip()
        if len(p) >= 3 and not p.lower().startswith(("during the course", "students will")):
            parts.append(p)
    seen, out = set(), []
    for p in parts:
        k = p.lower()
        if p and k not in seen:
            seen.add(k); out.append(p)
    return out


def exact_ok(name):
    n = name.strip()
    if n.lower() in EXACT_SINGLE_OK:
        return True
    if len(n) < 3:
        return False
    if " " in n:                                   # หลายคำ: Machine Learning, Cloud Computing
        return True
    return bool(re.search(r"[A-Z].*[A-Z]|[0-9+#/.]", n[1:]))   # ตัวย่อ/CamelCase: PLC, NoSQL, JavaScript


def exact_regex(name):
    return re.compile(r"(?<![\w+#.])" + re.escape(name) + r"(?![\w+#])", re.I)


# ---------- commands ----------
def cmd_migrate(a):
    """รัน migration_curriculum.sql ผ่าน psycopg2 (ไม่ต้องใช้ psql)"""
    sql = Path(a.file).read_text(encoding="utf-8")
    sql = "\n".join(l for l in sql.splitlines() if l.strip().upper() not in ("BEGIN;", "COMMIT;"))
    conn = connect(); cur = conn.cursor()
    cur.execute(sql); conn.commit()
    cur.execute("""SELECT table_name FROM information_schema.tables
                   WHERE table_name IN ('curriculum_courses','course_topics','course_skill_map') ORDER BY 1""")
    print("✔ ตาราง:", ", ".join(r[0] for r in cur.fetchall()))


def cmd_load(a):
    src = Path(a.file)
    if src.suffix == ".json":
        rows = json.loads(src.read_text(encoding="utf-8"))
    else:
        with open(src, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            r["prerequisite"] = [x for x in (r.get("prerequisite") or "").split(";") if x]
    conn = connect(); cur = conn.cursor()
    for r in rows:
        cur.execute("""
        INSERT INTO curriculum_courses (course_code, program, name_th, name_en, credits,
            hours_theory, hours_practice, hours_self, category, course_group, prerequisite,
            description_th, description_en)
        VALUES (%(course_code)s, %(program)s, %(name_th)s, %(name_en)s, %(credits)s,
            %(hours_theory)s, %(hours_practice)s, %(hours_self)s, %(category)s, %(course_group)s,
            %(prerequisite)s, %(description_th)s, %(description_en)s)
        ON CONFLICT (course_code) DO UPDATE SET
            program=EXCLUDED.program, name_th=EXCLUDED.name_th, name_en=EXCLUDED.name_en,
            credits=EXCLUDED.credits, hours_theory=EXCLUDED.hours_theory,
            hours_practice=EXCLUDED.hours_practice, hours_self=EXCLUDED.hours_self,
            category=EXCLUDED.category, course_group=EXCLUDED.course_group,
            prerequisite=EXCLUDED.prerequisite, description_th=EXCLUDED.description_th,
            description_en=EXCLUDED.description_en, embedding=NULL, embedded_at=NULL
        """, {**r, "prerequisite": r.get("prerequisite") or None})
    conn.commit()
    cur.execute("SELECT category, count(*), sum(credits) FROM curriculum_courses GROUP BY 1 ORDER BY 2 DESC")
    print(f"📚 โหลด {len(rows)} รายวิชา")
    for cat, n, cr in cur.fetchall():
        print(f"   {cat:20s} {n:3d} วิชา  {cr:4d} หน่วยกิต")


def cmd_embed(a):
    conn = connect(); cur = conn.cursor()
    cur.execute("""SELECT course_code, name_th, name_en, description_th, description_en
                   FROM curriculum_courses""" + ("" if a.force else " WHERE embedding IS NULL"))
    rows = cur.fetchall()
    if not rows:
        print("✔ ทุกวิชามี embedding แล้ว (ใช้ --force เพื่อทำใหม่)"); return
    cols = ["course_code", "name_th", "name_en", "description_th", "description_en"]
    courses = [dict(zip(cols, r)) for r in rows]

    full = [f"{c['name_en']} / {c['name_th']}. {c['description_en'] or ''} {c['description_th'] or ''}"
            for c in courses]
    print(f"🔤 embed วิชา: {len(full)}")
    V = encode(full, batch=8, max_len=512)
    for c, v in zip(courses, V):
        cur.execute("UPDATE curriculum_courses SET embedding=%s::vector, embedded_at=now() WHERE course_code=%s",
                    (vec_sql(v), c["course_code"]))

    topics = [(c["course_code"], i, t) for c in courses for i, t in enumerate(split_topics(c))]
    print(f"🔤 embed หัวข้อย่อย: {len(topics)}")
    T = encode([t for _, _, t in topics], batch=64, max_len=64)
    codes = tuple({c["course_code"] for c in courses})
    cur.execute("DELETE FROM course_topics WHERE course_code IN %s", (codes,))
    for (code, i, t), v in zip(topics, T):
        cur.execute("INSERT INTO course_topics (course_code, seq, topic, embedding) VALUES (%s,%s,%s,%s::vector)",
                    (code, i, t, vec_sql(v)))
    conn.commit()
    print("✔ บันทึกแล้ว")


def load_skills(cur, min_jobs):
    sid, name, stype = skill_cols(cur)
    cur.execute(f"""
        SELECT s.{sid}, s.{name}, {('s.' + stype) if stype else 'NULL'}, s.embedding::text,
               COALESCE(d.n, 0)
        FROM skills s
        LEFT JOIN (SELECT skill_id, count(DISTINCT job_id) n FROM job_skills GROUP BY 1) d
               ON d.skill_id = s.{sid}
        WHERE s.embedding IS NOT NULL AND COALESCE(d.n, 0) >= %s""", (min_jobs,))
    rows = cur.fetchall()
    ids = [r[0] for r in rows]; names = [r[1] for r in rows]
    types = [r[2] for r in rows]; jobs = [r[4] for r in rows]
    S = np.stack([parse_vec(r[3]) for r in rows]) if rows else np.zeros((0, 1024), np.float32)
    return ids, names, types, jobs, S


def cmd_map(a):
    conn = connect(); cur = conn.cursor()
    ids, names, types, jobs, S = load_skills(cur, a.min_jobs)
    cur.execute("""SELECT t.course_code, t.topic, t.embedding::text
                   FROM course_topics t WHERE t.embedding IS NOT NULL ORDER BY 1, t.seq""")
    trows = cur.fetchall()
    if not trows:
        sys.exit("❌ ยังไม่มี course_topics — รัน embed ก่อน")
    t_code = [r[0] for r in trows]; t_text = [r[1] for r in trows]
    T = np.stack([parse_vec(r[2]) for r in trows])
    cur.execute("SELECT course_code, name_th, name_en, coalesce(description_en,''), coalesce(description_th,'') FROM curriculum_courses")
    courses = {r[0]: r[1:] for r in cur.fetchall()}
    print(f"🔗 ทักษะ {len(ids)} (≥{a.min_jobs} งาน) × หัวข้อ {len(T)} จาก {len(courses)} วิชา")

    sims = S @ T.T                                     # (skills, topics)
    code_idx = {}
    for j, c in enumerate(t_code):
        code_idx.setdefault(c, []).append(j)

    pairs, review = {}, []
    # 1) semantic: max ต่อวิชา
    for code, js in code_idx.items():
        sub = sims[:, js]
        best = sub.argmax(1); bs = sub.max(1)
        for i in np.where(bs >= REVIEW_LOW)[0]:
            s = float(bs[i]); topic = t_text[js[best[i]]]
            if blocked(names[i], code):
                continue
            # หัวข้อคำเดียว (เช่น «installation») ห้ามจับกับทักษะหลายคำ (Electrical Installation)
            if " " not in topic.strip() and " " in names[i].strip():
                continue
            row = (code, ids[i], s, "semantic", topic)
            if s >= a.threshold:
                pairs[(code, ids[i])] = row
            review.append((code, courses[code][1], names[i], jobs[i], round(s, 3), topic,
                           "PASS" if s >= a.threshold else "near"))
    # 2) exact: ชื่อทักษะปรากฏในชื่อ/คำอธิบายวิชาตรงตัว
    n_exact = 0
    for i, nm in enumerate(names):
        if not exact_ok(nm) or (nm, None) in MAP_BLOCK:
            continue
        rx = exact_regex(nm)
        for code, (nth, nen, den, dth) in courses.items():
            if blocked(nm, code):
                continue
            if rx.search(f"{nen} ; {den} ; {dth} ; {nth}"):
                if (code, ids[i]) not in pairs or pairs[(code, ids[i])][3] != "exact":
                    n_exact += (code, ids[i]) not in pairs
                    pairs[(code, ids[i])] = (code, ids[i], 1.0, "exact", nm)
                    review.append((code, nen, nm, jobs[i], 1.0, nm, "EXACT"))

    # 3) manual: ผู้วิจัยยืนยันจากถ้อยคำในคำอธิบายรายวิชา
    n_manual = 0
    idx = {n: i for i, n in enumerate(names)}
    for nm, codes in CURRICULUM_ALLOW.items():
        if nm not in idx:
            continue
        i = idx[nm]
        for code in codes:
            if code in courses and (code, ids[i]) not in pairs:
                pairs[(code, ids[i])] = (code, ids[i], None, "manual", "researcher-reviewed")
                review.append((code, courses[code][1], nm, jobs[i], 0.0, "researcher-reviewed", "MANUAL"))
                n_manual += 1

    OUT.mkdir(exist_ok=True)
    fn = OUT / "curriculum_skill_review.csv"
    with open(fn, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["course_code", "course_name_en", "skill", "job_count", "similarity", "matched_topic", "status"])
        for r in sorted(review, key=lambda r: (-r[3], -r[4])):
            w.writerow(r)

    pass_rows = [r for r in review if r[6] in ("PASS", "EXACT", "MANUAL")]
    from collections import Counter
    by = Counter(r[3] for r in pairs.values())
    print(f"\n✅ คู่ที่ผ่าน: {len(pairs)}  (exact {by['exact']}, semantic {by['semantic']} [≥ {a.threshold}], manual {by['manual']})")
    print("\n▶ ทักษะความต้องการสูงที่จับคู่ได้ — ตรวจความหมาย")
    shown = set()
    for r in sorted(pass_rows, key=lambda r: (-r[3], -r[4])):
        if r[2] in shown: continue
        shown.add(r[2])
        print(f"   {r[2][:26]:26s} ({r[3]:4d}) -> {r[0]} {r[1][:32]:32s} {r[4]:.3f}  «{r[5][:40]}»")
        if len(shown) >= a.show: break
    print("\n▶ ใกล้เกณฑ์แต่ไม่ผ่าน (ตัวอย่าง)")
    k = 0
    for r in sorted([r for r in review if r[6] == "near"], key=lambda r: (-r[3], -r[4])):
        if r[2] in shown: continue
        shown.add(r[2]); k += 1
        print(f"   {r[2][:26]:26s} ({r[3]:4d}) ~ {r[0]} {r[1][:32]:32s} {r[4]:.3f}  «{r[5][:40]}»")
        if k >= 15: break
    print(f"\n💾 ทุกคู่สำหรับตรวจ: {fn}")

    if a.dry_run:
        print("--dry-run: ไม่เขียน DB"); return
    # เก็บคู่ "manual" ไว้เสมอ — รวมคู่ที่ผู้วิจัยเพิ่มผ่านหน้าเว็บ (Module 4 → ผู้ดูแล → รายวิชา)
    # ลบ/สร้างใหม่เฉพาะคู่ที่ระบบจับเอง (exact / semantic)
    cur.execute("DELETE FROM course_skill_map WHERE method IS DISTINCT FROM 'manual'")
    for r in pairs.values():
        cur.execute("""INSERT INTO course_skill_map (course_code, skill_id, similarity, method, matched_topic)
                       VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT (course_code, skill_id) DO NOTHING""", r)
    create_views(cur)
    conn.commit()
    print(f"✔ เขียน course_skill_map {len(pairs)} คู่ + สร้าง view v_curriculum_skill_gap")
    cmd_gap(a, conn)


def create_views(cur):
    sid, name, stype = skill_cols(cur)
    cur.execute("DROP VIEW IF EXISTS v_curriculum_coverage")
    cur.execute("DROP VIEW IF EXISTS v_curriculum_skill_gap")
    cur.execute(f"""
    CREATE VIEW v_curriculum_skill_gap AS
    SELECT s.{sid} AS skill_id, s.{name} AS skill, {('s.' + stype) if stype else 'NULL::text'} AS skill_type,
           d.job_count,
           (m.skill_id IS NOT NULL) AS covered,
           m.courses, m.best_similarity
    FROM skills s
    JOIN (SELECT skill_id, count(DISTINCT job_id) job_count FROM job_skills GROUP BY 1) d
         ON d.skill_id = s.{sid}
    LEFT JOIN (SELECT skill_id, string_agg(course_code, ', ' ORDER BY similarity DESC) courses,
                      max(similarity) best_similarity
               FROM course_skill_map GROUP BY 1) m ON m.skill_id = s.{sid}""")
    cur.execute("DROP VIEW IF EXISTS v_course_skill_standard")
    cur.execute(f"""
    CREATE VIEW v_course_skill_standard AS
    SELECT m.course_code, c.name_th, c.name_en, s.{name} AS skill, m.method AS course_method,
           ssm.standard, ssm.std_code, ssm.std_label, ssm.method AS std_method
    FROM course_skill_map m
    JOIN curriculum_courses c ON c.course_code = m.course_code
    JOIN skills s ON s.{sid} = m.skill_id
    LEFT JOIN skill_standard_map ssm ON ssm.skill_id = m.skill_id""")
    cur.execute("""
    CREATE VIEW v_curriculum_coverage AS
    SELECT count(*) AS skills,
           count(*) FILTER (WHERE covered) AS covered,
           round(100.0 * count(*) FILTER (WHERE covered) / count(*), 1) AS pct_unique,
           round(100.0 * sum(job_count) FILTER (WHERE covered) / sum(job_count), 1) AS pct_weighted
    FROM v_curriculum_skill_gap""")


def cmd_gap(a, conn=None):
    conn = conn or connect(); cur = conn.cursor()
    create_views(cur); conn.commit()
    print("\n📊 ความครอบคลุมของหลักสูตรต่อทักษะที่ตลาดต้องการ")
    print(f"   {'ทักษะที่ต้องการ ≥ N งาน':24s} {'ทักษะ':>6s} {'ครอบคลุม':>9s} {'% ไม่ซ้ำ':>9s} {'% ถ่วงน้ำหนัก':>13s}")
    for n in (1, 10, 50):
        cur.execute("""SELECT count(*), count(*) FILTER (WHERE covered),
                              round(100.0*count(*) FILTER (WHERE covered)/nullif(count(*),0),1),
                              round(100.0*sum(job_count) FILTER (WHERE covered)/nullif(sum(job_count),0),1)
                       FROM v_curriculum_skill_gap WHERE job_count >= %s""", (n,))
        t, c, pu, pw = cur.fetchone()
        print(f"   ≥ {n:<22d} {t:6d} {c:9d} {pu:8}% {pw:12}%")

    cur.execute("""SELECT round(100.0*sum(g.job_count) FILTER (WHERE a.skill_id IS NOT NULL)/sum(g.job_count),1)
                   FROM v_curriculum_skill_gap g
                   LEFT JOIN (SELECT DISTINCT skill_id FROM course_skill_map WHERE method<>'manual') a
                          ON a.skill_id=g.skill_id""")
    print(f"   (ไม่นับคู่ manual: % ถ่วงน้ำหนัก = {cur.fetchone()[0]}%)")
    cur.execute("SELECT method, count(*) FROM course_skill_map GROUP BY 1 ORDER BY 2 DESC")
    print("   คู่วิชา-ทักษะ: " + ", ".join(f"{m} {n}" for m, n in cur.fetchall()))

    cur.execute("""SELECT skill, skill_type, job_count FROM v_curriculum_skill_gap
                   WHERE NOT covered ORDER BY job_count DESC LIMIT %s""", (a.top,))
    gap = cur.fetchall()
    print(f"\n❗ {a.top} ทักษะที่ตลาดต้องการมากแต่ไม่พบในคำอธิบายรายวิชา")
    for s, t, n in gap:
        print(f"   {n:5d}  {s}" + (f"  [{t}]" if t else ""))

    cur.execute("""SELECT c.course_code, c.name_en, count(m.skill_id), coalesce(sum(d.n),0)
                   FROM curriculum_courses c
                   LEFT JOIN course_skill_map m ON m.course_code=c.course_code
                   LEFT JOIN (SELECT skill_id, count(DISTINCT job_id) n FROM job_skills GROUP BY 1) d
                          ON d.skill_id=m.skill_id
                   GROUP BY 1,2 ORDER BY 4 DESC""")
    rows = cur.fetchall()
    print("\n🏫 วิชาที่เชื่อมกับความต้องการตลาดมากที่สุด (ผลรวมจำนวนงานของทักษะที่จับคู่)")
    for code, nm, k, n in rows[:15]:
        print(f"   {code}  {nm[:45]:45s} ทักษะ {int(k):3d}  งาน {int(n):6d}")
    zero = [r for r in rows if r[2] == 0]
    if zero:
        print(f"\n   วิชาที่ไม่จับคู่ทักษะใดเลย: {len(zero)} วิชา — " + ", ".join(r[0] for r in zero[:12]) + (" ..." if len(zero) > 12 else ""))

    OUT.mkdir(exist_ok=True)
    cur.execute("SELECT * FROM v_curriculum_skill_gap ORDER BY job_count DESC")
    cols = [d[0] for d in cur.description]
    with open(OUT / "curriculum_skill_gap.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(cols); w.writerows(cur.fetchall())
    print(f"\n💾 {OUT / 'curriculum_skill_gap.csv'}")


def cmd_search(a):
    conn = connect(); cur = conn.cursor()
    q = vec_sql(encode([a.query], max_len=64)[0])
    cur.execute("""SELECT course_code, name_th, name_en, 1 - (embedding <=> %s::vector) s
                   FROM curriculum_courses WHERE embedding IS NOT NULL
                   ORDER BY embedding <=> %s::vector LIMIT %s""", (q, q, a.k))
    print(f"\n🔎 วิชาที่ใกล้เคียง: {a.query!r}")
    for code, nth, nen, s in cur.fetchall():
        print(f"   {s:.3f}  {code}  {nth[:35]:35s} {nen}")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("migrate"); p.add_argument("file", nargs="?", default="migration_curriculum.sql")
    p = sp.add_parser("load"); p.add_argument("file", nargs="?", default="output/curriculum_courses.json")
    p = sp.add_parser("embed"); p.add_argument("--force", action="store_true")
    p = sp.add_parser("map")
    p.add_argument("--threshold", type=float, default=THRESHOLD)
    p.add_argument("--min-jobs", type=int, default=1)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--show", type=int, default=30)
    p.add_argument("--top", type=int, default=30)
    p = sp.add_parser("gap"); p.add_argument("--top", type=int, default=30)
    p = sp.add_parser("search"); p.add_argument("query"); p.add_argument("-k", type=int, default=8)
    a = ap.parse_args()
    {"migrate": cmd_migrate, "load": cmd_load, "embed": cmd_embed, "map": cmd_map, "gap": cmd_gap, "search": cmd_search}[a.cmd](a)


if __name__ == "__main__":
    main()
