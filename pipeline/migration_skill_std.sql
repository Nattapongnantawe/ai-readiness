-- =====================================================================
-- เก็บผลจับคู่มาตรฐานสากล (ESCO + O*NET) ไว้ที่ตาราง skills — 1 แถวต่อทักษะไม่ซ้ำ
--   $env:PGCLIENTENCODING="UTF8"
--   psql -U postgres -d jobmarket_test -f migration_skill_std.sql
-- =====================================================================
ALTER TABLE skills ADD COLUMN IF NOT EXISTS esco_label       TEXT;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS esco_score       REAL;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS esco_description TEXT;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS onet_label       TEXT;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS onet_group       TEXT;      -- Element Name (หมวดซอฟต์แวร์)
ALTER TABLE skills ADD COLUMN IF NOT EXISTS onet_hot         BOOLEAN;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS onet_in_demand   BOOLEAN;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS std_mapped_at    TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS ix_skills_unmapped ON skills (id) WHERE std_mapped_at IS NULL;

-- ความครอบคลุมของมาตรฐาน (นับตามทักษะไม่ซ้ำ)
CREATE OR REPLACE VIEW v_std_coverage AS
SELECT  coalesce(skill_type, '?') AS skill_type,
        count(*)                                                        AS skills,
        count(*) FILTER (WHERE esco_uri IS NOT NULL)                    AS esco,
        count(*) FILTER (WHERE onet_label IS NOT NULL)                  AS onet,
        count(*) FILTER (WHERE esco_uri IS NOT NULL OR onet_label IS NOT NULL) AS covered,
        round(100.0 * count(*) FILTER (WHERE esco_uri IS NOT NULL OR onet_label IS NOT NULL)
              / nullif(count(*), 0), 1)                                 AS covered_pct
FROM skills
WHERE std_mapped_at IS NOT NULL
GROUP BY ROLLUP (skill_type);

-- ความครอบคลุมแบบถ่วงน้ำหนักตามความถี่ในประกาศงาน (ทักษะยอดนิยมมีน้ำหนักมากกว่า)
CREATE OR REPLACE VIEW v_std_coverage_weighted AS
SELECT  count(*)                                                                AS mentions,
        round(100.0 * count(*) FILTER (WHERE s.esco_uri IS NOT NULL) / count(*), 1)   AS esco_pct,
        round(100.0 * count(*) FILTER (WHERE s.onet_label IS NOT NULL) / count(*), 1) AS onet_pct,
        round(100.0 * count(*) FILTER (WHERE s.esco_uri IS NOT NULL OR s.onet_label IS NOT NULL)
              / count(*), 1)                                                     AS covered_pct
FROM job_skills js JOIN skills s ON s.id = js.skill_id;
