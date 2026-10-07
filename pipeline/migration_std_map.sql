-- =====================================================================
-- ตารางเชื่อมทักษะ <-> มาตรฐาน (1 ทักษะ อยู่ได้หลายมาตรฐาน) — เพิ่มมาตรฐานใหม่ไม่ต้องแก้ schema
--   psql -U postgres -d jobmarket_test -f migration_std_map.sql
-- =====================================================================
CREATE TABLE IF NOT EXISTS skill_standard_map (
    skill_id   INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    standard   TEXT    NOT NULL,          -- ESCO / ONET / SKILLSFUTURE / DSD / TPQI
    std_code   TEXT,                      -- uri / skill_id ของมาตรฐานนั้น
    std_label  TEXT    NOT NULL,
    std_type   TEXT,                      -- เช่น TSC / CCS (SkillsFuture)
    score      REAL,
    mapped_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (skill_id, standard)
);
CREATE INDEX IF NOT EXISTS ix_ssm_standard ON skill_standard_map (standard);

-- ย้ายผล ESCO / O*NET เดิมเข้าตารางใหม่ (รันซ้ำได้)
INSERT INTO skill_standard_map (skill_id, standard, std_code, std_label, score)
SELECT id, 'ESCO', esco_uri, esco_label, esco_score FROM skills WHERE esco_uri IS NOT NULL
ON CONFLICT (skill_id, standard) DO UPDATE
    SET std_code = EXCLUDED.std_code, std_label = EXCLUDED.std_label, score = EXCLUDED.score, mapped_at = now();
INSERT INTO skill_standard_map (skill_id, standard, std_label, std_type)
SELECT id, 'ONET', onet_label, onet_group FROM skills WHERE onet_label IS NOT NULL
ON CONFLICT (skill_id, standard) DO UPDATE
    SET std_label = EXCLUDED.std_label, std_type = EXCLUDED.std_type, mapped_at = now();

-- ความครอบคลุมแยกรายมาตรฐาน + รวม (ถ่วงตามความถี่ในประกาศ)
CREATE OR REPLACE VIEW v_std_coverage_by_standard AS
WITH mentions AS (SELECT skill_id, count(*) AS n FROM job_skills GROUP BY skill_id),
     tot AS (SELECT sum(n) AS total, count(*) AS uniq FROM mentions)
SELECT m.standard,
       count(*)                                           AS skills,
       round(100.0 * count(*) / (SELECT uniq FROM tot), 1) AS unique_pct,
       round(100.0 * sum(mn.n) / (SELECT total FROM tot), 1) AS weighted_pct
FROM skill_standard_map m JOIN mentions mn ON mn.skill_id = m.skill_id
GROUP BY m.standard
UNION ALL
SELECT 'ANY (รวมทุกมาตรฐาน)',
       count(*),
       round(100.0 * count(*) / (SELECT uniq FROM tot), 1),
       round(100.0 * sum(mn.n) / (SELECT total FROM tot), 1)
FROM mentions mn WHERE EXISTS (SELECT 1 FROM skill_standard_map m WHERE m.skill_id = mn.skill_id);
