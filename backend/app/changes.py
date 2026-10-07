"""Content-change log for jobs (installed by init_db, Module 4's own objects only).

When load.py upserts a job whose content really changed (the scraper re-opened a posting
because its listing card showed a newer date), the trigger below:
  1. writes one row to m4_job_changes: which fields changed, old and new values
  2. if title / description / qualification changed: clears llm_extracted_at and embedding,
     so the next pipeline steps re-extract skills (Gemini) and re-embed that job.
     (extractor.run already deletes the job's old job_skills before saving new ones.)
load.py upserts every line on every run; rows whose content is the same are not logged.
"""
from sqlalchemy import text
from sqlalchemy.engine import Connection

# field in jobs -> label shown on the web
TRACKED = {
    "title": "ชื่อตำแหน่ง", "company_id": "บริษัท", "salary_raw": "เงินเดือน", "num_positions": "จำนวนที่รับ",
    "province": "จังหวัด", "description": "รายละเอียดงาน", "qualification": "คุณสมบัติ", "welfare": "สวัสดิการ",
}
RE_EXTRACT = ("title", "description", "qualification")

TABLE = """
CREATE TABLE IF NOT EXISTS m4_job_changes (
    id          bigserial PRIMARY KEY,
    job_id      bigint      NOT NULL,
    changed_at  timestamptz NOT NULL DEFAULT now(),
    fields      text[]      NOT NULL,
    old_values  jsonb       NOT NULL,
    new_values  jsonb       NOT NULL,
    reextract   boolean     NOT NULL DEFAULT false
)"""
INDEX = "CREATE INDEX IF NOT EXISTS m4_job_changes_job ON m4_job_changes (job_id, changed_at DESC)"


def _function(cols: set[str]) -> str:
    tracked = [c for c in TRACKED if c in cols]
    checks = "\n".join(
        f"  IF NEW.{c} IS DISTINCT FROM OLD.{c} THEN f := f || '{c}'::text;"
        f" o := o || jsonb_build_object('{c}', OLD.{c}); n := n || jsonb_build_object('{c}', NEW.{c}); END IF;"
        for c in tracked)
    resets = " ".join(f"NEW.{c} := NULL;" for c in ("llm_extracted_at", "embedding") if c in cols)
    redo = " OR ".join(f"'{c}' = ANY(f)" for c in RE_EXTRACT if c in tracked) or "false"
    return f"""
CREATE OR REPLACE FUNCTION m4_track_job_change() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
  f text[] := '{{}}';
  o jsonb := '{{}}'::jsonb;
  n jsonb := '{{}}'::jsonb;
  redo boolean;
BEGIN
{checks}
  IF cardinality(f) = 0 THEN
    RETURN NEW;
  END IF;
  redo := {redo};
  IF redo THEN
    {resets or 'NULL;'}
  END IF;
  INSERT INTO m4_job_changes (job_id, fields, old_values, new_values, reextract)
  VALUES (NEW.id, f, o, n, redo);
  RETURN NEW;
END
$fn$"""


def install(conn: Connection) -> None:
    cols = {r[0] for r in conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = 'jobs'"))}
    conn.exec_driver_sql(TABLE)
    conn.exec_driver_sql(INDEX)
    conn.exec_driver_sql(_function(cols))
    conn.exec_driver_sql("DROP TRIGGER IF EXISTS m4_job_change_trg ON jobs")
    conn.exec_driver_sql("CREATE TRIGGER m4_job_change_trg BEFORE UPDATE ON jobs "
                         "FOR EACH ROW EXECUTE FUNCTION m4_track_job_change()")
