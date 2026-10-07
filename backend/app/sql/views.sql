-- =====================================================================
-- Module 4 views over the jobmarket database (Modules 1-3).
-- The API reads ONLY these views plus the shared tables named below, so if a column
-- in your database has a different name, this is the one file to change.
-- Runs automatically at API startup (app/db.py: init_db). Safe to re-run.
--
-- Shared tables read (never written, except course_skill_map / curriculum_courses by admin):
--   jobs, companies, skills, job_skills, skill_standard_map, curriculum_courses, course_skill_map
-- =====================================================================

DROP VIEW IF EXISTS m4_jobs CASCADE;
DROP VIEW IF EXISTS m4_ai_skills CASCADE;

-- Skills that count as "AI skills" for the dashboard (AI Skill Proportion) and their group.
-- Rule: skill name matches the pattern. (Module 2 category 'ai_data' is NOT used: it also holds
-- data skills such as SQL / Power BI / Excel, which would inflate the AI share.)
CREATE VIEW m4_ai_skills AS
SELECT s.id AS skill_id,
       s.name,
       CASE
         WHEN s.name ~* '(llm|large language|generative|genai|gpt|openai|langchain|prompt eng|(^|[^a-z])rag([^a-z]|$)|hugging ?face|transformer model)'
           THEN 'LLM / Generative AI'
         WHEN s.name ~* '(computer vision|opencv|image processing|yolo|image recognition)'
           THEN 'Computer Vision'
         WHEN s.name ~* '(nlp|natural language)'
           THEN 'NLP'
         WHEN s.name ~* '(machine learning|deep learning|tensorflow|pytorch|keras|scikit|neural net|reinforcement learning|mlops|pattern recognition|data science)'
           THEN 'Machine Learning / Deep Learning'
         ELSE 'AI ทั่วไป'
       END AS ai_group
FROM skills s
WHERE s.name ~* '(machine learning|deep learning|artificial intelligence|(^|[^a-z])ai([^a-z]|$)|generative|genai|llm|large language|gpt|openai|langchain|prompt eng|(^|[^a-z])rag([^a-z]|$)|nlp|natural language|computer vision|opencv|image processing|yolo|tensorflow|pytorch|keras|scikit|neural net|reinforcement learning|mlops|data science|hugging ?face|pattern recognition)';

-- One row per job with the fields the web app filters and displays, already normalised:
--   level     : Entry / Mid / Senior           (from jobs.seniority, Module 2)
--   work_mode : Onsite / Hybrid / Remote       (from jobs.work_mode, Module 2)
--   posted_at : posted_date, else scraped_at
--   salary_mid: midpoint of salary_min/max (monthly baht, Module 1 parsers)
--   company_logo: companies.logo_url (NULL if that column does not exist, see app/db.py)
CREATE VIEW m4_jobs AS
SELECT j.id,
       j.title,
       c.name                                   AS company,
       c.logo_url                               AS company_logo,
       j.province,
       lower(j.source_site::text)               AS source,
       coalesce(j.source_url, j.detail_url)     AS url,
       CASE
         WHEN lower(j.seniority::text) ~ '(intern|entry|junior|fresh|graduate|trainee)' THEN 'Entry'
         WHEN lower(j.seniority::text) ~ '(mid|intermediate|middle|associate)'           THEN 'Mid'
         WHEN lower(j.seniority::text) ~ '(senior|lead|manager|head|director|executive|principal|chief|expert)' THEN 'Senior'
       END                                      AS level,
       CASE
         WHEN lower(j.work_mode::text) ~ 'hybrid'                    THEN 'Hybrid'
         WHEN lower(j.work_mode::text) ~ '(remote|wfh|work from home)' THEN 'Remote'
         WHEN lower(j.work_mode::text) ~ '(on.?site|office)'          THEN 'Onsite'
       END                                      AS work_mode,
       j.salary_min,
       j.salary_max,
       CASE
         WHEN j.salary_min IS NOT NULL AND j.salary_max IS NOT NULL THEN (j.salary_min + j.salary_max) / 2.0
         ELSE coalesce(j.salary_min, j.salary_max)::numeric
       END                                      AS salary_mid,
       coalesce(j.posted_date::timestamptz, j.scraped_at::timestamptz) AS posted_at,
       j.scraped_at::timestamptz                AS scraped_at,
       j.updated_at::timestamptz                AS updated_at,
       EXISTS (SELECT 1 FROM job_skills js JOIN m4_ai_skills a ON a.skill_id = js.skill_id
               WHERE js.job_id = j.id)          AS is_ai_related,
       j.embedding
FROM jobs j
LEFT JOIN companies c ON c.id = j.company_id;
