-- =====================================================================
-- v3: หน่วยค่าจ้าง + เก็บผลดิบของ LLM ไว้ตรวจย้อนหลัง
--   $env:PGCLIENTENCODING="UTF8"
--   psql -U postgres -d jobmarket_test -f migration_v3.sql
-- =====================================================================
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_period TEXT NOT NULL DEFAULT 'month';  -- month/day/hour/year
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS llm_raw JSONB;          -- ผลดิบจาก Gemini (ก่อน normalize)
COMMENT ON COLUMN jobs.salary_min IS 'บาทต่อเดือน (แปลงจากหน่วยเดิมแล้ว ดู salary_period)';
