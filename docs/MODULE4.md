# AI Readiness — Module 4 (Web UI, Semantic Search, Gap Analysis)

ระบบส่วนที่ 4 ของโครงงาน *Automated Continuous Job Crawling to AI Readiness Database & Curriculum Gap Intelligence System*
วิศวกรรมคอมพิวเตอร์ มหาวิทยาลัยกาฬสินธุ์

- **frontend/** React 18 + TypeScript + Vite + Tailwind CSS
- **backend/** FastAPI + PostgreSQL/pgvector + APScheduler — **อ่านฐาน `jobmarket` ตัวเดียวกับ Module 1–3 โดยตรง**
- ไม่มีฐานข้อมูลแยก ไม่มีข้อมูลปลอม: ตัวเลขทุกหน้ามาจากตาราง `jobs`, `skills`, `job_skills`, `skill_standard_map`, `curriculum_courses`, `course_skill_map`

## เริ่มใช้งาน (Windows)

| ไฟล์ | ใช้เมื่อ |
| --- | --- |
| **`start.bat`** | ใช้งานจริง / demo: ดับเบิลคลิกไฟล์เดียว เปิดทั้ง API + หน้าเว็บ + ตัวตั้งเวลา ที่ **http://localhost:8000** (ครั้งแรกจะ build หน้าเว็บให้เอง) |
| `build-frontend.bat` | หลังแก้โค้ด frontend แล้วต้องการให้ `start.bat` ใช้หน้าเว็บเวอร์ชันใหม่ |
| `dev.bat` | ตอนพัฒนา: API แบบ auto-reload (:8000) + Vite (:5173) แก้โค้ดแล้วหน้าเว็บอัปเดตเอง |
| `share-online.bat` | เปิดให้คนอื่นเข้าชมผ่านอินเทอร์เน็ต (Cloudflare Quick Tunnel ฟรี ไม่ต้องสมัคร) ได้ลิงก์ `https://….trycloudflare.com` — ต้องเปิด `start.bat` ค้างไว้ |

ก่อนใช้ครั้งแรก
1. ติดตั้ง Node.js 18+ (สำหรับ build หน้าเว็บ) และมี PostgreSQL ที่มีฐาน `jobmarket`
2. `backend\.env` ตั้ง `DATABASE_URL` และ path ของ pipeline / scraper (ดู `backend\.env.example`)
3. ถ้า venv ไม่ได้อยู่ที่ `C:\projeb\pipeline\venv` แก้บรรทัด `set "PY=..."` ใน `start.bat` และ `dev.bat`

`start.bat` รันแบบไม่มี `--reload` จึงปลอดภัยกับรอบดึงข้อมูลที่ยาวหลายชั่วโมง (แก้ไฟล์ระหว่างรันไม่ทำให้รอบหยุด)
ถ้าต้องการให้เครื่องอื่นในวง LAN เปิดได้ เปลี่ยน `--host 127.0.0.1` เป็น `--host 0.0.0.0` ใน `start.bat`

### เปิดให้คนอื่นเข้าชม (share-online.bat)
- ใช้ได้เมื่อเครื่องเปิดอยู่และหน้าต่าง `start.bat` + `share-online.bat` เปิดค้าง ปิดหน้าต่าง = หยุดแชร์ ลิงก์เปลี่ยนทุกครั้งที่เปิดใหม่
- สคริปต์ไม่ยอมเปิดถ้า `ADMIN_PASSWORD` / `JWT_SECRET` ใน `backend\.env` ยังเป็นค่าตัวอย่าง (คนนอกจะสั่ง crawler ได้)
- ล็อกอินผิด 5 ครั้งจากผู้ใช้คนเดียว ล็อก 10 นาที · ข้อมูลติดต่อในประกาศถูกซ่อนเสมอ (PDPA)
- Quick Tunnel ของ Cloudflare ใช้สำหรับทดสอบ/สาธิต ไม่รับประกัน uptime และรับได้ 200 request พร้อมกัน

ดูหน้าเว็บแบบไม่มี Backend: `cd frontend && npm run dev:mock`

## ตอน API เริ่มทำงาน
1. ตรวจว่ามีตารางของ Module 1–3 ครบ ถ้าไม่ครบจะหยุดพร้อมบอกว่าขาดอะไร
2. สร้าง/อัปเดต view `m4_jobs` และ `m4_ai_skills` จาก `app/sql/views.sql`
3. สร้างเฉพาะตารางของ Module 4 เอง: `m4_crawl_schedules`, `m4_crawl_runs` (ไม่แตะตารางเดิม เช่น crawl_runs ของ Module 1)
4. โหลด bge-m3 (GPU ถ้ามี) สำหรับ semantic search

`app/sql/views.sql` คือจุดเดียวที่แปลงข้อมูลเดิมให้หน้าเว็บ:
- `level` Entry/Mid/Senior จาก `jobs.seniority`
- `work_mode` Onsite/Hybrid/Remote จาก `jobs.work_mode`
- `posted_at` = `posted_date` ถ้าไม่มีใช้ `scraped_at`
- `is_ai_related` = งานที่มีทักษะ AI อย่างน้อย 1 ตัว (`m4_ai_skills`: จับชื่อทักษะ เช่น Machine Learning, LLM, Computer Vision, NLP)
ถ้า `check_db` แสดงค่า seniority/work_mode ที่ไม่เข้ากฎ ให้แก้ CASE ในไฟล์นี้

## หน้าเว็บและข้อมูลที่แสดง
| หน้า | ข้อมูลจากฐาน |
| --- | --- |
| ภาพรวม | จำนวนงาน/บริษัท/ทักษะ/คู่ งาน–ทักษะ, Top skills (hard/soft), สัดส่วนงาน AI + กลุ่ม + ทักษะ AI ยอดนิยม, เงินเดือนตามระดับ, ฮิสโตแกรมเงินเดือน, ความครอบคลุม 5 มาตรฐาน, Match Score หลักสูตร |
| ค้นหางาน | ค้นด้วยความหมาย (bge-m3 ↔ `jobs.embedding`, HNSW) ไล่ 200 งานที่ใกล้ที่สุด แบ่งหน้าละ 20, รวมประกาศชื่อเดียวกันของบริษัทเดียวกัน (คนละสาขา), โลโก้บริษัท, ตัวกรอง, ทักษะที่ใกล้ความหมาย |
| รายละเอียดงาน | โลโก้บริษัท (`companies.logo_url`), รายละเอียด คุณสมบัติ สวัสดิการ ประสบการณ์ วุฒิ ประเภทการจ้าง ทักษะ (บังคับ/ไม่บังคับ) + มาตรฐานที่รองรับแต่ละทักษะ — ไม่แสดงข้อมูลติดต่อ (PDPA): เบอร์โทร/อีเมล/LINE ในชื่องานและเนื้อหาถูกลบก่อนส่ง (`app/privacy.py`) |
| Gap หลักสูตร | Match Score ทั้งหลักสูตรหรือ 10–15 วิชาที่เลือก, แยก/ไม่นับคู่ที่ผู้วิจัยตรวจ, priority matrix, ทักษะที่ควรเพิ่ม + วิชาที่ใกล้ที่สุด, คะแนนรายวิชา, heatmap, ส่งออก CSV |
| ผู้ดูแล · Crawler | สถานะ pipeline Module 1–3, ตั้งรอบเวลา, รันตอนนี้, ประมวลผลงานที่ค้าง, ขั้นตอน + log สดของแต่ละรอบ, หยุดรอบ |
| ผู้ดูแล · รายวิชา | 79 วิชาจาก มคอ.2 พร้อมคู่ทักษะแยกวิธี (ตรงตัว/ความหมาย/ผู้วิจัยตรวจ) แก้ไขได้ |

## Gap Analysis (app/gap.py)
- d(s) = สัดส่วนงานที่ต้องการทักษะ s · c_j(s) = 1 ถ้ามีคู่ใน `course_skill_map`
- MatchScore = Σ d·c / Σ d ทุกทักษะ (ค่าเริ่มต้น `GAP_TOP_N=0` → ทั้งหลักสูตร = 29.4 % ตรงกับรายงาน Module 3)
- ทักษะที่ควรเพิ่ม = ทักษะที่ยังไม่มีวิชารองรับ เรียงตามความต้องการ พร้อมวิชา + หัวข้อ (`course_topics`) ที่ใกล้ที่สุด ถ้าความคล้าย < `GAP_SUGGEST_MIN` (0.55) = ควรเป็นเนื้อหาใหม่
- `ยังขาด (≥10 งาน)` = ทักษะที่ยังไม่ครอบคลุมและมีงานต้องการอย่างน้อย `GAP_MISSING_MIN_JOBS` ตำแหน่ง

## ระบบดึงข้อมูลอัตโนมัติ (app/pipeline.py, หน้า ผู้ดูแล → Crawler)
หนึ่งรอบ = เรียกสคริปต์เดิมตามลำดับ (subprocess ในโฟลเดอร์และ venv ของแต่ละตัว):

| ขั้น | คำสั่ง |
| --- | --- |
| 1 ดึงประกาศ | `<scraper>\venv\Scripts\python main.py --new --auto --delay 4-7 [--url หมวด]` (JobThai วนทุกหมวดใน `JOBTHAI_URLS`) |
| 2 นำเข้า | `python load.py --file <scraper>\output\jobs.jsonl --site <แหล่ง>` |
| 3 สกัดทักษะ | `python -m extractor.run --limit EXTRACT_LIMIT_PER_RUN` (โควตาหมด = ทำต่อรอบหน้า) |
| 4 Embedding | `python -m extractor.embed jobs` |
| 5 ทักษะใหม่ | `python -m extractor.embed skills` (+ `embed map` เมื่อมีทักษะใหม่) |
| 6 หลักสูตร | จับคู่วิชาแบบตรงตัวให้ทักษะใหม่ (เพิ่มอย่างเดียว ไม่ลบคู่ที่ผู้วิจัยเพิ่ม) + ล้าง cache Gap |

- รันได้ทีละรอบทั้งระบบ (thread lock + PostgreSQL advisory lock) รอบตามเวลาที่ชนกันจะรอคิว
- ทุกขั้นทำเฉพาะแถวที่ยังไม่เสร็จ รอบที่ล้ม/ถูกหยุดจึงไม่ทำให้ข้อมูลเสีย รอบหน้าทำต่อเอง
- log เต็มของทุกรอบ: `backend/logs/run_<id>.log` (ดาวน์โหลดได้จากหน้าเว็บ)
- Scraper ต้องมี `polite.py`: ตรวจ robots.txt, โหมด `--auto` หน่วง `CRAWL_DELAY` (ค่าเริ่ม 4–7 วินาที สุ่ม) และ**ชะลอเอง 2 เท่า**เมื่อเว็บตอบ 429/503/5xx/timeout, ไม่โหลดฟอนต์/วิดีโอ, `--url`
- ตั้ง path ใน `backend/.env` (ดู `.env.example`) ถ้า path ผิด หน้า Crawler จะแจ้งและไม่ให้กดรัน
- ปุ่ม "ประมวลผลงานที่ค้าง" = ขั้น 2–6 ไม่ดึงประกาศใหม่ (นำเข้า jobs.jsonl ของทั้งสองเว็บก่อน เช่น งานจากรอบที่กดหยุดกลางทาง)

### งานใหม่ / งานที่ถูกอัปเดต (ตรวจความครบและความถูกต้อง)
- **รายการสด**: ระหว่างรัน หน้ารายละเอียดรอบแสดง "งานที่ดึงในรอบนี้" ทีละงาน (ใหม่ / อัปเดต / ดันประกาศ / ได้ไม่ครบ / ดึงไม่ได้)
  แต่ละงานมีปุ่ม **ต้นฉบับ** (เว็บจริง) และ **ในระบบ** (`/jobs/<id>`) ไว้เปิดเทียบ — API: `GET /crawler/runs/{id}/feed`
- **งานที่ถูกอัปเดต**: scraper อ่านวันที่บนการ์ดในหน้ารายการ (`freshness.py`) ถ้าใหม่กว่าที่เคยเก็บจะเปิดหน้ารายละเอียดใหม่
  แล้วเทียบเนื้อหา: เปลี่ยน = "อัปเดต" (บอกช่องที่เปลี่ยน) · เหมือนเดิม = "ดันประกาศ" · สูงสุด `MAX_UPDATES_PER_RUN` งาน/หมวด/รอบ
  ตรวจว่าการ์ดของเว็บมีวันที่ไหม: `python main.py --cards` ในโฟลเดอร์ scraper
- **ฐานข้อมูล**: trigger `m4_job_change_trg` (`app/changes.py`) บันทึกช่องที่เปลี่ยน เดิม→ใหม่ ลง `m4_job_changes`
  ถ้าชื่อตำแหน่ง/รายละเอียด/คุณสมบัติเปลี่ยน จะล้าง `llm_extracted_at` + `embedding` ให้ขั้นถัดไปสกัดทักษะ/embed ใหม่
- `jobs.jsonl` มีหลายบรรทัดต่องานได้ (ดึงซ้ำ) ขั้นนำเข้าใช้เฉพาะบรรทัดล่าสุดของแต่ละงาน (`logs/load_<แหล่ง>.jsonl`)

## API
| Method | Path |
| --- | --- |
| GET | /api/v1/analytics/summary, top-skills, salary-distribution, salary-histogram, ai-trend, standards, pipeline, filters |
| POST | /api/v1/search · GET /api/v1/search/related-skills |
| GET | /api/v1/jobs/{id} |
| GET/POST/PUT/DELETE | /api/v1/curriculum/courses… · GET /api/v1/curriculum/skills |
| GET | /api/v1/gap-analysis?courses=A,B&exclude_manual=true · /export.csv · POST /recalculate |
| POST/GET/PUT | /api/v1/auth/login · /api/v1/crawler/status, sources, sources/{s}/schedule, sources/{s}/runs, process, runs, runs/{id}, runs/{id}/cancel, runs/{id}/log |

## ทดสอบ
```bash
cd backend && pytest
```
