# -*- coding: utf-8 -*-
import psycopg2
from psycopg2.extras import Json, RealDictCursor, execute_batch

SQL_PENDING = """
SELECT id, title, experience_years, attributes
FROM jobs
WHERE (%(force)s OR llm_extracted_at IS NULL)
  AND (%(job_id)s::bigint IS NULL OR id = %(job_id)s::bigint)
ORDER BY id
LIMIT %(limit)s
"""
SQL_ITEMS = """
SELECT id, job_id, source::text AS source, seq, content
FROM job_requirement_items WHERE job_id = ANY(%s) ORDER BY job_id, source, seq
"""
SQL_ALIASES = """
SELECT a.alias_norm, s.name FROM skill_aliases a JOIN skills s ON s.id = a.skill_id
"""
SQL_ITEM_UPD = """
UPDATE job_requirement_items
SET category = %(category)s::req_category_t, confidence = %(confidence)s, classified_at = now()
WHERE id = %(item_id)s AND job_id = %(job_id)s
"""
SQL_SKILL = """
INSERT INTO skills (name, name_norm, category, skill_type)
VALUES (%s, %s, %s, %s)
ON CONFLICT (name_norm) DO UPDATE
    SET category   = COALESCE(skills.category, EXCLUDED.category),
        skill_type = COALESCE(skills.skill_type, EXCLUDED.skill_type)
RETURNING id
"""
SQL_ALIAS = """
INSERT INTO skill_aliases (alias_norm, skill_id, source) VALUES (%s, %s, %s)
ON CONFLICT (alias_norm) DO NOTHING
"""
SQL_JOB_SKILL = """
INSERT INTO job_skills (job_id, skill_id, item_id, is_required) VALUES (%s, %s, %s, %s)
ON CONFLICT (job_id, skill_id) DO UPDATE
    SET is_required = job_skills.is_required OR EXCLUDED.is_required,
        item_id     = COALESCE(job_skills.item_id, EXCLUDED.item_id)
"""
SQL_JOB_DONE = """
UPDATE jobs SET seniority = %s, work_mode = %s, llm_extracted_at = now(), llm_model = %s,
                experience_years = COALESCE(experience_years, %s), llm_raw = %s
WHERE id = %s
"""


class Repo:
    def __init__(self, dsn: str):
        self.conn = psycopg2.connect(dsn)
        self._skill_cache = {}

    def close(self):
        self.conn.close()

    def pending_jobs(self, limit: int, force: bool = False, job_id=None) -> list:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(SQL_PENDING, {"limit": limit, "force": force, "job_id": job_id})
            return [dict(r) for r in cur.fetchall()]

    def items_for(self, job_ids: list) -> dict:
        out = {j: [] for j in job_ids}
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(SQL_ITEMS, (job_ids,))
            for r in cur.fetchall():
                out[r["job_id"]].append(dict(r))
        return out

    def db_aliases(self) -> dict:
        from .normalize import norm_key
        with self.conn.cursor() as cur:
            cur.execute(SQL_ALIASES)
            return {norm_key(a): n for a, n in cur.fetchall()}

    def _skill_id(self, cur, name, key, group, stype) -> int:
        if key not in self._skill_cache:
            cur.execute(SQL_SKILL, (name, key, group, stype))
            self._skill_cache[key] = cur.fetchone()[0]
        return self._skill_cache[key]

    def save_job(self, job_id: int, result, header_ids: list, normalizer, model: str,
                 years=None) -> int:
        """บันทึกผล 1 งานใน transaction เดียว คืนจำนวน skill"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM job_skills WHERE job_id = %s", (job_id,))
                rows = [{"job_id": job_id, "item_id": i, "category": "other", "confidence": 1.0}
                        for i in header_ids]
                rows += [{"job_id": job_id, "item_id": it.item_id,
                          "category": it.category.value, "confidence": it.confidence}
                         for it in result.items]
                if rows:
                    execute_batch(cur, SQL_ITEM_UPD, rows)

                n = 0
                for sk in result.skills:
                    if not sk.name or normalizer.is_generic(sk.name):
                        continue
                    canon, key, alias_key = normalizer.canonical(sk.name)
                    sid = self._skill_id(cur, canon, key, sk.group.value, sk.skill_type.value)
                    if alias_key and alias_key != key:
                        cur.execute(SQL_ALIAS, (alias_key, sid, "llm"))
                    cur.execute(SQL_JOB_SKILL, (job_id, sid, sk.item_id, sk.is_required))
                    n += 1

                cur.execute(SQL_JOB_DONE,
                            (result.seniority.value, result.work_mode.value, model, years,
                             Json(result.model_dump(mode="json")), job_id))
            self.conn.commit()
            return n
        except Exception:
            self.conn.rollback()
            self._skill_cache.clear()        # id ใน cache อาจถูก rollback ไปแล้ว
            raise
