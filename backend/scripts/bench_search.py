"""Measure semantic search speed (rubric: < 300 ms).

    python -m scripts.bench_search                 # API at http://127.0.0.1:8000
    python -m scripts.bench_search --url http://127.0.0.1:8000

Needs start.bat running. Sends each query once to POST /api/v1/search and reads the
server's own timing (took_ms: embed = bge-m3 query vector, db = pgvector HNSW + filters + skills),
plus wall time of the whole HTTP call. The first call loads the model and is excluded (warm-up).
The API caches query vectors, so each run adds a short run tag to every query: the vector is
really computed every time (no cache hit), even when the script is run again.
Also times the vector index alone (HNSW, top 20, straight SQL on jobs.embedding).
Writes output/bench_search.csv and prints mean / median / p95.

Use 127.0.0.1, not "localhost": on Windows "localhost" tries IPv6 (::1) first and waits ~2 s before
falling back to IPv4, where uvicorn listens. That delay is the client, not the system.
"""
import argparse
import csv
import json
import statistics
import time
import urllib.request
from pathlib import Path

QUERIES = [
    "full stack developer", "data engineer", "machine learning engineer", "นักพัฒนาเว็บ",
    "วิศวกรไฟฟ้า", "PLC programmer", "network administrator", "ผู้ดูแลระบบเครือข่าย",
    "python backend", "react frontend", "devops kubernetes", "embedded system engineer",
    "data analyst power bi", "โปรแกรมเมอร์ จบใหม่", "IT support", "cyber security",
    "AI engineer LLM", "ช่างซ่อมบำรุงอิเล็กทรอนิกส์", "mobile developer flutter", "QA tester automation",
]


def call(url: str, q: str) -> tuple[dict, float]:
    body = json.dumps({"query": q, "page": 1, "page_size": 20}).encode()
    req = urllib.request.Request(url + "/api/v1/search", data=body, headers={"Content-Type": "application/json"})
    t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    return data, (time.perf_counter() - t) * 1000


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    a = ap.parse_args()

    for w in ("warm up", "อุ่นเครื่อง", "warm up GPU kernels for longer queries"):  # loads bge-m3, not counted
        call(a.url, w)
    rows = []
    tag = f" #{int(time.time()) % 100000}"  # new text each run -> no query-vector cache hit
    for q in QUERIES:
        data, wall = call(a.url, q + tag)
        t = data.get("took_ms", {})
        rows.append({"query": q, "embed_ms": t.get("embed", 0), "db_ms": t.get("db", 0),
                     "server_ms": round(t.get("embed", 0) + t.get("db", 0), 1), "wall_ms": round(wall, 1),
                     "results": data.get("total", 0)})

    Path("output").mkdir(exist_ok=True)
    with open("output/bench_search.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    print(f"{len(rows)} คำค้น\n")
    print(f"{'':12}{'เฉลี่ย':>10}{'มัธยฐาน':>10}{'p95':>10}{'สูงสุด':>10}  (ms)")
    for k, label in [("embed_ms", "embed"), ("db_ms", "db"), ("server_ms", "server"), ("wall_ms", "ทั้ง HTTP")]:
        xs = [r[k] for r in rows]
        print(f"{label:12}{statistics.mean(xs):10.1f}{statistics.median(xs):10.1f}{pct(xs, .95):10.1f}{max(xs):10.1f}")
    p95 = pct([r["wall_ms"] for r in rows], .95)
    print(f"\n{'✅ ผ่าน' if p95 < 300 else '❌ ไม่ผ่าน'} เกณฑ์ < 300 ms (p95 ทั้ง HTTP = {p95:.1f} ms)")
    print("รายละเอียด: output/bench_search.csv")
    hnsw_only()


def hnsw_only(n: int = 50) -> None:
    """Vector index alone: nearest 20 jobs for n stored job vectors (no embedding, no filters)."""
    try:
        from sqlalchemy import create_engine, text

        from app.config import settings
    except Exception as e:  # noqa: BLE001
        print(f"\n(ข้ามการวัด HNSW: {e})")
        return
    eng = create_engine(settings.database_url)
    with eng.connect() as c:
        c.execute(text(f"SET hnsw.ef_search = {int(settings.hnsw_ef_search)}"))
        qs = [r[0] for r in c.execute(text(
            "SELECT embedding::text FROM jobs WHERE embedding IS NOT NULL ORDER BY random() LIMIT :n"), {"n": n})]
        plan = "\n".join(r[0] for r in c.execute(text(
            "EXPLAIN SELECT id FROM jobs ORDER BY embedding <=> CAST(:q AS vector) LIMIT 20"), {"q": qs[0]}))
        ms = []
        for q in qs:
            t = time.perf_counter()
            c.execute(text("SELECT id FROM jobs ORDER BY embedding <=> CAST(:q AS vector) LIMIT 20"), {"q": q}).all()
            ms.append((time.perf_counter() - t) * 1000)
    used = "ใช้ดัชนี HNSW" if "Index Scan" in plan else "⚠️ ไม่ได้ใช้ดัชนี (Seq Scan)"
    print(f"\nค้นเวกเตอร์อย่างเดียว ({n} ครั้ง, {used}):")
    print(f"  เฉลี่ย {statistics.mean(ms):.1f} · มัธยฐาน {statistics.median(ms):.1f} · p95 {pct(ms, .95):.1f} ms")
    try:
        import torch
        dev = settings.embedding_device or ("cuda" if torch.cuda.is_available() else "cpu")
        name = torch.cuda.get_device_name(0) if dev == "cuda" else "CPU"
        print(f"embedding รันบน: {dev} ({name})")
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()