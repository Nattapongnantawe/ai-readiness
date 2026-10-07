-- =====================================================================
-- Module 2 migration — รันต่อจาก schema.sql (ไม่ลบข้อมูลเดิม)
--   psql -U postgres -d jobmarket -f migration_module2.sql
-- =====================================================================

-- ผลจาก LLM ระดับงาน
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS seniority        TEXT;   -- entry / mid / senior / unknown
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS work_mode        TEXT;   -- onsite / remote / hybrid / unknown
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS llm_extracted_at TIMESTAMPTZ;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS llm_model        TEXT;
CREATE INDEX IF NOT EXISTS ix_jobs_llm_pending ON jobs (id) WHERE llm_extracted_at IS NULL;

-- ทักษะ: แยก hard / soft + เตรียมช่อง ESCO
ALTER TABLE skills ADD COLUMN IF NOT EXISTS skill_type TEXT;       -- hard / soft
ALTER TABLE skills ADD COLUMN IF NOT EXISTS esco_uri   TEXT;
DO $$ BEGIN
    ALTER TABLE skills ADD CONSTRAINT ck_skill_type CHECK (skill_type IN ('hard','soft'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Skill Normalization: คำพ้อง -> skill เดียว
CREATE TABLE IF NOT EXISTS skill_aliases (
    alias_norm TEXT PRIMARY KEY,                 -- 'reactjs', 'การทำงานเป็นทีม'
    skill_id   INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    source     TEXT NOT NULL DEFAULT 'llm'       -- seed / llm / manual
);
CREATE INDEX IF NOT EXISTS ix_skill_aliases_skill ON skill_aliases (skill_id);

-- views
DROP VIEW IF EXISTS v_skill_demand;
CREATE VIEW v_skill_demand AS
SELECT  s.name, s.skill_type, s.category,
        count(DISTINCT js.job_id)                                AS job_count,
        count(DISTINCT js.job_id) FILTER (WHERE js.is_required)  AS required_count
FROM skills s
JOIN job_skills js ON js.skill_id = s.id
GROUP BY s.id, s.name, s.skill_type, s.category
ORDER BY job_count DESC;

CREATE OR REPLACE VIEW v_extraction_progress AS
SELECT  count(*)                                        AS total_jobs,
        count(*) FILTER (WHERE llm_extracted_at IS NOT NULL) AS extracted,
        count(*) FILTER (WHERE llm_extracted_at IS NULL)     AS pending
FROM jobs;
