-- =====================================================================
-- Module 3: AI Readiness — pgvector + bge-m3 (1024 มิติ) + HNSW
--   psql -U postgres -d jobmarket_test -f migration_module3.sql
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE skills ADD COLUMN IF NOT EXISTS embedding vector(1024);
ALTER TABLE jobs   ADD COLUMN IF NOT EXISTS embedding vector(1024);

-- รายการทักษะของแต่ละมาตรฐาน (ใช้จับคู่ด้วยความหมาย)
CREATE TABLE IF NOT EXISTS std_skills (
    id          SERIAL PRIMARY KEY,
    standard    TEXT NOT NULL,           -- ESCO / ONET / SKILLSFUTURE / DSD / TPQI
    std_code    TEXT,
    label       TEXT NOT NULL,
    std_type    TEXT,
    description TEXT,
    embedding   vector(1024),
    CONSTRAINT uq_std_skills UNIQUE (standard, label)
);

-- วิธีที่ได้คู่มา: exact (กฎตัวอักษร ตรวจแล้ว) / semantic (bge-m3)
ALTER TABLE skill_standard_map ADD COLUMN IF NOT EXISTS method TEXT NOT NULL DEFAULT 'exact';

-- HNSW index สำหรับค้นหาความคล้ายเชิงความหมาย (cosine)
CREATE INDEX IF NOT EXISTS ix_skills_emb ON skills     USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS ix_jobs_emb   ON jobs       USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS ix_std_emb    ON std_skills USING hnsw (embedding vector_cosine_ops);
