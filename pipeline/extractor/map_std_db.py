# -*- coding: utf-8 -*-
r"""
จับคู่ทักษะในฐานข้อมูลกับ ESCO + O*NET — ครั้งเดียวต่อทักษะไม่ซ้ำ (ตาราง skills)
ทุกงานที่อ้างถึงทักษะนั้นผ่าน job_skills ได้ผลไปด้วยอัตโนมัติ

  python -m extractor.map_std_db                # ทำเฉพาะทักษะที่ยังไม่เคยจับคู่
  python -m extractor.map_std_db --force        # ทำใหม่ทั้งหมด (หลังแก้กฎ/alias)
  python -m extractor.map_std_db --limit 50     # ทดลองชุดเล็ก

ต้องรัน migration_skill_std.sql ก่อน และมีไฟล์ data\onet_technology_skills.csv
หยุดกลางทางได้ — รันใหม่จะทำต่อจากทักษะที่ค้าง
"""
import argparse
import os
import sys
import time

import psycopg2

from . import config
from .esco_map import EscoMapper
from .normalize import SkillNormalizer
from .onet_map import DATA as ONET_DATA, load_onet, match as onet_match

SQL_TODO = """
SELECT s.id, s.name, s.skill_type, count(js.job_id) AS freq
FROM skills s LEFT JOIN job_skills js ON js.skill_id = s.id
WHERE %(force)s OR s.std_mapped_at IS NULL
GROUP BY s.id ORDER BY freq DESC, s.id
LIMIT %(limit)s
"""
SQL_SAVE = """
UPDATE skills SET
    esco_uri = %(esco_uri)s, esco_label = %(esco_label)s, esco_score = %(esco_score)s,
    esco_description = %(esco_description)s,
    onet_label = %(onet_label)s, onet_group = %(onet_group)s,
    onet_hot = %(onet_hot)s, onet_in_demand = %(onet_in_demand)s,
    std_mapped_at = now()
WHERE id = %(id)s
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--onet", default=ONET_DATA)
    a = ap.parse_args()

    if not os.path.exists(a.onet):
        print(f"❌ ไม่พบ {a.onet} — ดาวน์โหลด O*NET 'Software Skills' (CSV) ก่อน")
        sys.exit(1)
    onet_idx = load_onet(a.onet)
    esco = EscoMapper()
    norm = SkillNormalizer()

    conn = psycopg2.connect(config.DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute(SQL_TODO, {"force": a.force, "limit": a.limit})
        todo = cur.fetchall()
    print(f"🔎 ทักษะที่ต้องจับคู่: {len(todo)} (เรียงจากที่พบบ่อยที่สุดก่อน)\n")

    n = e_hit = o_hit = 0
    t0 = time.time()
    try:
        for sid, name, stype, freq in todo:
            m = esco.map(name)
            rec, _ = onet_match(name, onet_idx, norm)
            row = {"id": sid, **{k: m.get(k) for k in ("esco_uri", "esco_label", "esco_score",
                                                      "esco_description")},
                   "onet_label": rec["label"] if rec else None,
                   "onet_group": rec["commodity"] if rec else None,
                   "onet_hot": rec["hot"] if rec else None,
                   "onet_in_demand": rec.get("demand") if rec else None}
            if m.get("esco_uri") is None and m.get("esco_score") is None:
                row.pop("esco_uri")                     # API ล้มเหลว: ไม่ปิดงาน ให้รอบหน้าลองใหม่
                print(f"  ⚠️ ESCO ล้มเหลว: {name} — จะลองใหม่รอบหน้า")
                continue
            with conn.cursor() as cur:
                cur.execute(SQL_SAVE, row)
            conn.commit()
            n += 1
            e_hit += bool(row["esco_uri"])
            o_hit += bool(row["onet_label"])
            if n % 25 == 0:
                esco.save()
                print(f"  [{n}/{len(todo)}] ESCO {e_hit} · O*NET {o_hit}  ({(time.time() - t0) / 60:.1f} นาที)")
    except KeyboardInterrupt:
        print("\n⏸ หยุดโดยผู้ใช้ — ที่บันทึกแล้วไม่หาย รันใหม่จะทำต่อ")
    finally:
        esco.save()

    with conn.cursor() as cur:
        cur.execute("SELECT skill_type, skills, esco, onet, covered, covered_pct FROM v_std_coverage")
        cov = cur.fetchall()
        cur.execute("SELECT mentions, esco_pct, onet_pct, covered_pct FROM v_std_coverage_weighted")
        w = cur.fetchone()
    conn.close()

    print(f"\n✅ จับคู่รอบนี้ {n} ทักษะ\n")
    print(f"{'ประเภท':10}{'ทักษะ':>8}{'ESCO':>8}{'O*NET':>8}{'รวม':>8}{'%':>8}")
    for t, s, e, o, c, p in cov:
        print(f"{(t or 'ทั้งหมด'):10}{s:>8}{e:>8}{o:>8}{c:>8}{p:>7}%")
    if w and w[0]:
        print(f"\nถ่วงน้ำหนักตามความถี่ ({w[0]} ครั้งที่พบในประกาศ): "
              f"ESCO {w[1]}% · O*NET {w[2]}% · รวม {w[3]}%")


if __name__ == "__main__":
    main()
