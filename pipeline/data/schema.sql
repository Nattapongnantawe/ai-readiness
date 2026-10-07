-- =====================================================================
-- Job Market Data Warehouse — PostgreSQL Schema v2
-- รองรับข้อมูลจาก JobThai (single-pass) + JobBKK
-- และรองรับขั้นตอน "จำแนกข้อมูลจาก job description" ที่จะทำต่อ
--
-- ติดตั้ง:  psql -U postgres -d jobmarket -f schema.sql
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- ---------- ล้างของเดิม (ข้อมูลจะถูกโหลดใหม่ทั้งหมด) ----------
DROP VIEW IF EXISTS v_jobs_full, v_salary_by_province, v_source_summary,
                    v_skill_demand, v_requirement_breakdown CASCADE;
DROP TABLE IF EXISTS job_requirement_items, job_skills, skills,
                     job_tags, tags, jobs, companies, raw_jobs, crawl_runs CASCADE;
DROP TYPE IF EXISTS source_site_t, salary_type_t, req_source_t, req_category_t CASCADE;

-- ---------- Enum ----------
CREATE TYPE source_site_t AS ENUM ('jobthai', 'jobbkk');

CREATE TYPE salary_type_t AS ENUM (
    'range',        -- 18,000 - 20,000 บาท
    'fixed',        -- 20,000 บาท
    'negotiable',   -- ตามตกลง / ตามประสบการณ์ / ตามโครงสร้างบริษัท
    'unspecified'   -- ไม่ระบุ / ว่าง
);

-- แต่ละ bullet มาจากส่วนไหนของประกาศ
CREATE TYPE req_source_t AS ENUM ('description', 'qualification');

-- ผลการจำแนก bullet (เติมในขั้นตอนถัดไป)
CREATE TYPE req_category_t AS ENUM (
    'skill',         -- ทักษะ/เทคโนโลยี
    'experience',    -- ประสบการณ์
    'education',     -- วุฒิการศึกษา
    'certificate',   -- ใบรับรอง
    'language',      -- ภาษา
    'responsibility',-- หน้าที่งาน
    'other'
);


-- =====================================================================
-- 1) raw_jobs — JSON ดิบจาก scraper (ไม่แตะต้อง)
-- =====================================================================
CREATE TABLE raw_jobs (
    id            BIGSERIAL PRIMARY KEY,
    url_hash      CHAR(64)      NOT NULL,
    source_site   source_site_t NOT NULL,
    source_url    TEXT          NOT NULL,
    payload       JSONB         NOT NULL,
    scraped_at    TIMESTAMPTZ,                   -- เวลาที่ scraper ดึงมา
    loaded_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    processed_at  TIMESTAMPTZ,
    CONSTRAINT uq_raw_jobs_hash UNIQUE (url_hash)      -- ★ dedup ชั้นที่ 1
);

CREATE INDEX ix_raw_jobs_unprocessed ON raw_jobs (loaded_at) WHERE processed_at IS NULL;
CREATE INDEX ix_raw_jobs_payload     ON raw_jobs USING GIN (payload);


-- =====================================================================
-- 2) companies — โลโก้/คำแนะนำบริษัทเป็นของ "บริษัท" ไม่ใช่ของงาน
-- =====================================================================
CREATE TABLE companies (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    logo_url        TEXT,              -- จาก company_logo_url
    description     TEXT,              -- จาก company_description
    website         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_companies_norm UNIQUE (name_normalized)
);

CREATE INDEX ix_companies_name_trgm ON companies USING GIN (name gin_trgm_ops);


-- =====================================================================
-- 3) jobs — ตารางหลัก
-- =====================================================================
CREATE TABLE jobs (
    id              BIGSERIAL PRIMARY KEY,
    url_hash        CHAR(64)      NOT NULL,
    source_site     source_site_t NOT NULL,
    source_url      TEXT          NOT NULL,
    detail_url      TEXT,                          -- หน้ารายละเอียดเต็ม
    scraped_at      TIMESTAMPTZ,

    title           TEXT          NOT NULL,
    company_id      BIGINT        REFERENCES companies(id) ON DELETE SET NULL,

    -- เงินเดือน: ข้อมูลจริงส่วนใหญ่เป็นข้อความ จึงเก็บทั้งดิบและที่แปลงแล้ว
    salary_raw      TEXT,
    salary_type     salary_type_t NOT NULL DEFAULT 'unspecified',
    salary_min      NUMERIC(12,2),
    salary_max      NUMERIC(12,2),
    salary_currency CHAR(3)       NOT NULL DEFAULT 'THB',

    location_raw    TEXT,
    province        TEXT,
    district        TEXT,
    travel          TEXT,                          -- วิธีการเดินทาง

    num_positions   INTEGER,
    posted_date     DATE,
    valid_through   DATE,

    employment_type  TEXT,                         -- FULL_TIME / INTERN (JobBKK)
    job_category     TEXT,
    experience_years INTEGER,
    education_level  TEXT,

    -- เนื้อหา
    description     TEXT,                          -- รายละเอียดงาน
    qualification   TEXT,                          -- คุณสมบัติผู้สมัคร
    welfare         TEXT,
    contact         TEXT,
    work_location   TEXT,

    sections        JSONB NOT NULL DEFAULT '{}'::jsonb,   -- หัวข้อไม่คงที่ (JobBKK)
    attributes      JSONB NOT NULL DEFAULT '{}'::jsonb,   -- attribute อื่น ๆ

    search_vector   tsvector,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_jobs_hash UNIQUE (url_hash),             -- ★ dedup ชั้นที่ 2
    CONSTRAINT ck_salary_range CHECK (
        salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max),
    CONSTRAINT ck_num_positions CHECK (num_positions IS NULL OR num_positions > 0),
    CONSTRAINT ck_experience    CHECK (experience_years IS NULL OR experience_years >= 0)
);

CREATE INDEX ix_jobs_source     ON jobs (source_site);
CREATE INDEX ix_jobs_company    ON jobs (company_id);
CREATE INDEX ix_jobs_province   ON jobs (province);
CREATE INDEX ix_jobs_posted     ON jobs (posted_date DESC NULLS LAST);
CREATE INDEX ix_jobs_salary     ON jobs (salary_min, salary_max) WHERE salary_min IS NOT NULL;
CREATE INDEX ix_jobs_category   ON jobs (job_category);
CREATE INDEX ix_jobs_emptype    ON jobs (employment_type);
CREATE INDEX ix_jobs_title_trgm ON jobs USING GIN (title gin_trgm_ops);
CREATE INDEX ix_jobs_sections   ON jobs USING GIN (sections);
CREATE INDEX ix_jobs_attributes ON jobs USING GIN (attributes);
CREATE INDEX ix_jobs_search     ON jobs USING GIN (search_vector);


-- =====================================================================
-- 4) job_requirement_items — แต่ละ bullet แยกบรรทัด  ★ หัวใจของขั้นจำแนก
--    scraper แตก bullet มาให้แล้ว (job_description_items / qualification_items)
--    คอลัมน์ category จะถูกเติมในขั้นตอน "จำแนก skill / experience / certificate"
-- =====================================================================
CREATE TABLE job_requirement_items (
    id          BIGSERIAL PRIMARY KEY,
    job_id      BIGINT       NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    source      req_source_t NOT NULL,        -- มาจาก description หรือ qualification
    seq         INTEGER      NOT NULL,        -- ลำดับในประกาศ (คงลำดับเดิมไว้)
    content     TEXT         NOT NULL,
    category    req_category_t,               -- NULL = ยังไม่ได้จำแนก
    confidence  REAL,                         -- ความมั่นใจของการจำแนก (0-1)
    classified_at TIMESTAMPTZ,
    CONSTRAINT uq_req_item UNIQUE (job_id, source, seq)
);

CREATE INDEX ix_req_job        ON job_requirement_items (job_id);
CREATE INDEX ix_req_category   ON job_requirement_items (category);
CREATE INDEX ix_req_unclassified ON job_requirement_items (job_id) WHERE category IS NULL;
CREATE INDEX ix_req_content_trgm ON job_requirement_items USING GIN (content gin_trgm_ops);


-- =====================================================================
-- 5) skills / job_skills — ทักษะที่สกัดได้ (normalize เป็นรายการเดียวกัน)
-- =====================================================================
CREATE TABLE skills (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,              -- 'Python', 'VMware ESXi'
    name_norm   TEXT NOT NULL,              -- 'python' (ใช้จับคู่)
    category    TEXT,                       -- language / database / cloud / framework / soft
    CONSTRAINT uq_skills_norm UNIQUE (name_norm)
);

CREATE TABLE job_skills (
    job_id      BIGINT  NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    skill_id    INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    item_id     BIGINT  REFERENCES job_requirement_items(id) ON DELETE SET NULL,
    is_required BOOLEAN NOT NULL DEFAULT TRUE,   -- FALSE = "จะพิจารณาเป็นพิเศษ"
    PRIMARY KEY (job_id, skill_id)
);

CREATE INDEX ix_job_skills_skill ON job_skills (skill_id);


-- =====================================================================
-- 6) tags / job_tags
-- =====================================================================
CREATE TABLE tags (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    CONSTRAINT uq_tags_name UNIQUE (name)
);

CREATE TABLE job_tags (
    job_id BIGINT  NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, tag_id)
);

CREATE INDEX ix_job_tags_tag ON job_tags (tag_id);


-- =====================================================================
-- 7) crawl_runs — log การรัน scraper
-- =====================================================================
CREATE TABLE crawl_runs (
    id            BIGSERIAL PRIMARY KEY,
    source_site   source_site_t NOT NULL,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    pages_crawled INTEGER NOT NULL DEFAULT 0,
    jobs_found    INTEGER NOT NULL DEFAULT 0,
    jobs_new      INTEGER NOT NULL DEFAULT 0,
    jobs_failed   INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'running',
    note          TEXT
);


-- =====================================================================
-- 8) Trigger — updated_at + full-text
-- =====================================================================
CREATE OR REPLACE FUNCTION jobs_before_write() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    NEW.search_vector :=
        setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(NEW.description, '')), 'B') ||
        setweight(to_tsvector('simple', coalesce(NEW.qualification, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_jobs_before_write
    BEFORE INSERT OR UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION jobs_before_write();


-- =====================================================================
-- 9) Views
-- =====================================================================
CREATE VIEW v_jobs_full AS
SELECT  j.id, j.url_hash, j.source_site, j.source_url, j.detail_url,
        j.title, c.name AS company_name, c.logo_url AS company_logo_url,
        c.description AS company_description,
        j.salary_raw, j.salary_type, j.salary_min, j.salary_max,
        (j.salary_min + j.salary_max) / 2.0 AS salary_mid,
        j.province, j.district, j.travel, j.num_positions, j.posted_date,
        j.employment_type, j.job_category, j.experience_years, j.education_level,
        j.description, j.qualification, j.welfare, j.contact, j.sections,
        j.scraped_at, j.first_seen_at
FROM jobs j
LEFT JOIN companies c ON c.id = j.company_id;

CREATE VIEW v_salary_by_province AS
SELECT  province,
        count(*)                                  AS job_count,
        round(avg((salary_min + salary_max)/2.0)) AS avg_salary,
        min(salary_min)                           AS min_salary,
        max(salary_max)                           AS max_salary
FROM jobs
WHERE salary_min IS NOT NULL AND province IS NOT NULL
GROUP BY province
ORDER BY job_count DESC;

CREATE VIEW v_source_summary AS
SELECT  source_site,
        count(*)                                          AS total_jobs,
        count(*) FILTER (WHERE salary_min IS NOT NULL)     AS with_salary,
        count(*) FILTER (WHERE posted_date IS NOT NULL)    AS with_date,
        count(*) FILTER (WHERE description <> '')          AS with_description,
        count(DISTINCT company_id)                         AS companies,
        min(first_seen_at)::date                           AS first_crawl,
        max(first_seen_at)::date                           AS last_crawl
FROM jobs
GROUP BY source_site;

-- ทักษะที่ตลาดต้องการมากที่สุด (ใช้ได้หลังทำขั้นจำแนก)
CREATE VIEW v_skill_demand AS
SELECT  s.name, s.category,
        count(DISTINCT js.job_id) AS job_count
FROM skills s
JOIN job_skills js ON js.skill_id = s.id
GROUP BY s.name, s.category
ORDER BY job_count DESC;

-- ความคืบหน้าการจำแนก bullet
CREATE VIEW v_requirement_breakdown AS
SELECT  source,
        coalesce(category::text, '(ยังไม่จำแนก)') AS category,
        count(*) AS item_count
FROM job_requirement_items
GROUP BY source, category
ORDER BY source, item_count DESC;
