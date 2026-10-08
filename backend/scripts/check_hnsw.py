"""Check (and optionally create) the pgvector HNSW indexes used by semantic search.

    python -m scripts.check_hnsw          # show indexes + whether queries use them
    python -m scripts.check_hnsw --fix    # create missing cosine HNSW indexes, then check again

Search ranks with cosine distance (<=>), so the index must be built with vector_cosine_ops;
an index built with vector_l2_ops (<->) is ignored by those queries.
"""
import argparse
import time

from sqlalchemy import create_engine, text

from app.config import settings

TABLES = ["jobs", "skills", "curriculum_courses"]
SQL = "SELECT {pk} FROM {t} ORDER BY embedding <=> CAST(:q AS vector) LIMIT 20"


def indexes(c, t: str) -> list[tuple[str, str]]:
    return [(r[0], r[1]) for r in c.execute(text(
        "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = :t AND indexdef ILIKE '%embedding%'"),
        {"t": t})]


def check(c, t: str) -> None:
    pk = "course_code" if t == "curriculum_courses" else "id"
    idx = indexes(c, t)
    print(f"\n[{t}]")
    if not idx:
        print("  ❌ ไม่มีดัชนีบน embedding")
    for name, d in idx:
        ops = "cosine ✅" if "cosine" in d else ("L2 (ใช้กับ <=> ไม่ได้)" if "l2" in d or "ops" not in d else d)
        kind = "HNSW" if "hnsw" in d.lower() else ("IVFFlat" if "ivfflat" in d.lower() else "อื่น")
        print(f"  {name}: {kind} · {ops}")
    q = c.execute(text(f"SELECT embedding::text FROM {t} WHERE embedding IS NOT NULL LIMIT 1")).scalar()
    if not q:
        print("  (ยังไม่มีเวกเตอร์)")
        return
    plan = "\n".join(r[0] for r in c.execute(text("EXPLAIN " + SQL.format(pk=pk, t=t)), {"q": q}))
    used = next((ln.strip() for ln in plan.splitlines() if "Index Scan" in ln), None)
    print(f"  แผนปกติ: {'ใช้ ' + used if used else 'Seq Scan (อ่านทุกแถว)'}")
    if not used and idx:
        c.execute(text("SET enable_seqscan = off"))
        plan2 = "\n".join(r[0] for r in c.execute(text("EXPLAIN " + SQL.format(pk=pk, t=t)), {"q": q}))
        c.execute(text("RESET enable_seqscan"))
        print("  บังคับใช้ดัชนี: " + ("ใช้ได้ (ตารางเล็ก ตัววางแผนเลยเลือกอ่านทั้งตาราง)" if "Index Scan" in plan2
                                    else "❌ ใช้ไม่ได้ — ดัชนีไม่ตรงกับ <=> (cosine)"))
    for label, off in (("Seq Scan", False), ("HNSW", True)):
        if off and not idx:
            continue
        if off:
            c.execute(text("SET enable_seqscan = off"))
        ms = []
        for _ in range(20):
            s = time.perf_counter()
            c.execute(text(SQL.format(pk=pk, t=t)), {"q": q}).all()
            ms.append((time.perf_counter() - s) * 1000)
        c.execute(text("RESET enable_seqscan"))
        ms.sort()
        print(f"  เวลา {label:8}: มัธยฐาน {ms[len(ms) // 2]:.1f} ms")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="create missing cosine HNSW indexes")
    a = ap.parse_args()
    eng = create_engine(settings.database_url)
    if a.fix:
        with eng.begin() as c:
            for t in TABLES:
                if not any("hnsw" in d.lower() and "cosine" in d for _, d in indexes(c, t)):
                    print(f"สร้างดัชนี {t}_embedding_hnsw_cos ...")
                    c.execute(text(f"CREATE INDEX IF NOT EXISTS {t}_embedding_hnsw_cos ON {t} "
                                   "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"))
            c.execute(text("ANALYZE jobs"))
    with eng.connect() as c:
        c.execute(text(f"SET hnsw.ef_search = {int(settings.hnsw_ef_search)}"))
        for t in TABLES:
            try:
                check(c, t)
            except Exception as e:  # noqa: BLE001
                c.rollback()
                print(f"\n[{t}] ข้าม: {str(e).splitlines()[0]}")


if __name__ == "__main__":
    main()
