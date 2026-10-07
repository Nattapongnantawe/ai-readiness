"""Remove contact details (PDPA) from a COPY of the database before it is shared.

    python scripts/pdpa_clean.py postgresql://postgres@localhost:5432/jobmarket_share

Never run this on the real jobmarket database: it rewrites rows in place.
Password comes from the PGPASSWORD environment variable (make-submission.bat sets it).

What it does (same rules the website uses, app/privacy.py):
  jobs.contact                      -> NULL
  jobs.title                        -> clean_title()  (phone / e-mail / LINE removed)
  jobs.description/qualification/welfare -> mask_text() ("[ซ่อนข้อมูลติดต่อ]")
  raw_jobs.payload (raw scraped JSON, holds contact + full text) -> {}
  m4_job_changes (old/new job text)  -> emptied
"""
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.privacy import clean_title, mask_text  # noqa: E402

TEXT_COLS = ("description", "qualification", "welfare")


def main(url: str) -> None:
    url = url.replace("+psycopg", "")
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT current_database()")
        if cur.fetchone()[0] == "jobmarket":
            sys.exit("⛔ refusing to clean the real 'jobmarket' database - use a copy")
        # rewriting text here is not a real content change: skip the Module 4 change trigger
        cur.execute("SET session_replication_role = replica")
        cur.execute("SELECT to_regclass('m4_job_changes') IS NOT NULL")
        if cur.fetchone()[0]:
            cur.execute("TRUNCATE m4_job_changes")      # holds old/new job text
            print("m4_job_changes emptied")
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs'")
        cols = {r[0] for r in cur.fetchall()}
        text_cols = [c for c in TEXT_COLS if c in cols]

        if "contact" in cols:
            cur.execute("UPDATE jobs SET contact = NULL WHERE contact IS NOT NULL")
            print(f"jobs.contact -> NULL : {cur.rowcount} rows")

        cur.execute(f"SELECT id, title{''.join(', ' + c for c in text_cols)} FROM jobs")
        changed = []
        for row in cur.fetchall():
            new = [clean_title(row[1]) if row[1] else row[1]] + [mask_text(v) for v in row[2:]]
            if list(row[1:]) != new:
                changed.append((*new, row[0]))
        if changed:
            sets = ", ".join(f"{c} = %s" for c in ["title", *text_cols])
            cur.executemany(f"UPDATE jobs SET {sets} WHERE id = %s", changed)
        print(f"jobs title/text masked : {len(changed)} rows")

        cur.execute("SELECT to_regclass('raw_jobs') IS NOT NULL")
        if cur.fetchone()[0]:
            cur.execute("UPDATE raw_jobs SET payload = '{}'")
            print(f"raw_jobs.payload -> {{}} : {cur.rowcount} rows")
        conn.commit()
    print("✅ PDPA clean done")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
