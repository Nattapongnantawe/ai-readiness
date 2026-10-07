-- Module 3: Curriculum Courses (มคอ.2 วศ.บ. วิศวกรรมคอมพิวเตอร์ ปรับปรุง 2566)
-- รัน:  psql -d jobmarket_test -f migration_curriculum.sql   (ต้องรัน migration_module3.sql ก่อน — ใช้ extension vector)
BEGIN;

CREATE TABLE IF NOT EXISTS curriculum_courses (
    course_code     TEXT PRIMARY KEY,               -- EN-013-333
    program         TEXT NOT NULL,
    name_th         TEXT NOT NULL,
    name_en         TEXT,
    credits         SMALLINT,
    hours_theory    SMALLINT,
    hours_practice  SMALLINT,
    hours_self      SMALLINT,
    category        TEXT,       -- general_education / core / major_required / major_elective / field_experience
    course_group    TEXT,       -- กลุ่มวิชา เช่น กลุ่มวิชาการพัฒนาซอฟต์แวร์
    prerequisite    TEXT[],
    description_th  TEXT,
    description_en  TEXT,
    embedding       vector(1024),                   -- bge-m3: ชื่อ + คำอธิบาย (ไทย+อังกฤษ)
    embedded_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- หัวข้อย่อยในคำอธิบายรายวิชา (แยกด้วย ; , :) — ใช้จับคู่กับทักษะได้ละเอียดกว่าทั้งวิชา
CREATE TABLE IF NOT EXISTS course_topics (
    course_code  TEXT REFERENCES curriculum_courses(course_code) ON DELETE CASCADE,
    seq          INT,
    topic        TEXT NOT NULL,
    embedding    vector(1024),
    PRIMARY KEY (course_code, seq)
);

-- วิชา ↔ ทักษะจากประกาศงาน
CREATE TABLE IF NOT EXISTS course_skill_map (
    course_code   TEXT REFERENCES curriculum_courses(course_code) ON DELETE CASCADE,
    skill_id      INT NOT NULL,                     -- skills.skill_id
    similarity    REAL,
    method        TEXT,                             -- exact / semantic
    matched_topic TEXT,
    mapped_at     TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (course_code, skill_id)
);
CREATE INDEX IF NOT EXISTS idx_csm_skill ON course_skill_map(skill_id);

CREATE INDEX IF NOT EXISTS idx_cc_emb ON curriculum_courses USING hnsw (embedding vector_cosine_ops);

COMMIT;
