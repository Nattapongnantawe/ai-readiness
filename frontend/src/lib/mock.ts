/**
 * In-browser mock of the Module 4 API, used when VITE_USE_MOCK=true (npm run dev:mock).
 * Headline numbers follow the real jobmarket run (4,210 jobs, 72.3 % standards coverage, 29.4 % curriculum match);
 * everything else is sample data only.
 */
import type { Course, Gap, JobCard, JobDetail, Run, RunStep, SearchFilters, Source } from './types'

const wait = (ms = 250) => new Promise((r) => setTimeout(r, ms))
const iso = (d: Date) => d.toISOString()
const now = () => new Date()
const hoursAgo = (h: number) => new Date(Date.now() - h * 3600_000)

class MockError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message) }
}

type MockJob = Omit<JobCard, 'company' | 'source' | 'source_url'> & { skills: { name: string; type: 'hard' | 'soft'; ai: boolean }[] }

const RAW_JOBS: MockJob[] = [
  { job_id: 1, title: 'AI Engineer', province: 'ขอนแก่น', salary_min: 30000, salary_max: 45000, level: 'Entry', work_mode: 'Hybrid', top_skills: ['Python', 'PyTorch', 'Docker'], similarity: 0.83,
    skills: [{ name: 'Python', type: 'hard', ai: false }, { name: 'PyTorch', type: 'hard', ai: true }, { name: 'Machine Learning', type: 'hard', ai: true }, { name: 'Docker', type: 'hard', ai: false }, { name: 'SQL', type: 'hard', ai: false }, { name: 'Git', type: 'hard', ai: false }, { name: 'Teamwork', type: 'soft', ai: false }, { name: 'Problem Solving', type: 'soft', ai: false }] },
  { job_id: 2, title: 'Machine Learning Engineer', province: 'กรุงเทพฯ', salary_min: 40000, salary_max: 60000, level: 'Mid', work_mode: 'Hybrid', top_skills: ['Python', 'TensorFlow', 'SQL'], similarity: 0.79,
    skills: [{ name: 'Python', type: 'hard', ai: false }, { name: 'TensorFlow', type: 'hard', ai: true }, { name: 'SQL', type: 'hard', ai: false }, { name: 'Communication', type: 'soft', ai: false }] },
  { job_id: 3, title: 'Data Scientist', province: 'ขอนแก่น', salary_min: 28000, salary_max: 40000, level: 'Entry', work_mode: 'Onsite', top_skills: ['Python', 'SQL', 'Pandas'], similarity: 0.76,
    skills: [{ name: 'Python', type: 'hard', ai: false }, { name: 'SQL', type: 'hard', ai: false }, { name: 'Pandas', type: 'hard', ai: true }] },
  { job_id: 4, title: 'Python Developer (AI Platform)', province: null, salary_min: 35000, salary_max: 50000, level: 'Mid', work_mode: 'Remote', top_skills: ['Python', 'FastAPI', 'LLM'], similarity: 0.72,
    skills: [{ name: 'Python', type: 'hard', ai: false }, { name: 'FastAPI', type: 'hard', ai: false }, { name: 'LLM', type: 'hard', ai: true }] },
  { job_id: 5, title: 'Computer Vision Engineer', province: 'ชลบุรี', salary_min: 35000, salary_max: 55000, level: 'Mid', work_mode: 'Onsite', top_skills: ['OpenCV', 'Python', 'C++'], similarity: 0.7,
    skills: [{ name: 'OpenCV', type: 'hard', ai: true }, { name: 'Python', type: 'hard', ai: false }, { name: 'C++', type: 'hard', ai: false }] },
  { job_id: 6, title: 'Data Engineer (ML Platform)', province: 'กรุงเทพฯ', salary_min: 45000, salary_max: 70000, level: 'Mid', work_mode: 'Hybrid', top_skills: ['Python', 'Spark', 'Airflow'], similarity: 0.68,
    skills: [{ name: 'Python', type: 'hard', ai: false }, { name: 'Spark', type: 'hard', ai: false }, { name: 'Airflow', type: 'hard', ai: false }] },
]
const JOBS = RAW_JOBS.map((j) => ({ ...j, company: null, source: 'jobthai', source_url: 'https://www.jobthai.com' }))

const SKILL_NAMES = ['Python', 'SQL', 'JavaScript', 'Docker', 'React', 'Linux', 'Git', 'Java', 'AWS', 'Machine Learning', 'TypeScript', 'Kubernetes', 'CI/CD', 'UML', 'Agile', 'Software Testing']

const sources: Source[] = [
  { source: 'jobbkk', mode: 'daily', every_hours: 12, daily_at: '02:00', enabled: true, next_run_at: null, last_run: null },
  { source: 'jobthai', mode: 'interval', every_hours: 6, daily_at: '02:00', enabled: true, next_run_at: null, last_run: null },
]
let runSeq = 100
const runs: Run[] = [
  { id: 7, source: 'jobthai', trigger: 'scheduled', status: 'success', started_at: iso(hoursAgo(4)), finished_at: iso(hoursAgo(3.03)), found: 277, inserted: 41, duplicated: 236, pages_done: 14, pages_total: 14, log: [], error_message: null },
  { id: 6, source: 'jobbkk', trigger: 'scheduled', status: 'success', started_at: iso(hoursAgo(10)), finished_at: iso(hoursAgo(8.9)), found: 310, inserted: 52, duplicated: 258, pages_done: 16, pages_total: 16, log: [], error_message: null },
  { id: 5, source: 'jobthai', trigger: 'scheduled', status: 'success', started_at: iso(hoursAgo(10)), finished_at: iso(hoursAgo(9.1)), found: 265, inserted: 33, duplicated: 232, pages_done: 13, pages_total: 13, log: [], error_message: null },
  { id: 4, source: 'jobthai', trigger: 'scheduled', status: 'failed', started_at: iso(hoursAgo(16)), finished_at: iso(hoursAgo(15.8)), found: 84, inserted: 0, duplicated: 0, pages_done: 6, pages_total: null, log: [], error_message: 'HTTP 429 · หยุดที่หน้า 6' },
  { id: 3, source: 'jobthai', trigger: 'scheduled', status: 'success', started_at: iso(hoursAgo(22)), finished_at: iso(hoursAgo(21.1)), found: 251, inserted: 29, duplicated: 222, pages_done: 12, pages_total: 12, log: [], error_message: null },
]
const runStart = new Map<number, number>()
const PAGES = 8
const STEP_DEFS: [string, string, string][] = [
  ['crawl', 'ดึงประกาศ (Module 1)', 'เจอ 180 · ใหม่ 24 · ข้าม 156'], ['load', 'นำเข้าฐานข้อมูล', 'งานใหม่ 24 · อัปเดต 2,043'],
  ['extract', 'สกัดทักษะด้วย Gemini (Module 2)', 'สกัดแล้ว 24 งาน · ทักษะ 187'], ['embed_jobs', 'Embedding ประกาศ (Module 3)', 'embed 24 ประกาศ'],
  ['skills', 'ทักษะใหม่ + จับคู่มาตรฐาน', 'ทักษะใหม่ 9 · คู่มาตรฐาน 4'], ['curriculum', 'จับคู่หลักสูตร + อัปเดตหน้าเว็บ', 'คู่วิชา–ทักษะใหม่ 1 · ล้าง cache หน้า Gap แล้ว'],
]
const mkSteps = (source: string, done: boolean): RunStep[] =>
  STEP_DEFS.filter(([k]) => source !== 'process' || !['crawl', 'load'].includes(k)).map(([key, label, summary]) => ({
    key, label, status: done ? 'success' : 'pending', started_at: null, finished_at: null, summary: done ? summary : '', counts: {} }))
for (const r of runs) r.steps = mkSteps(r.source, r.status === 'success')

function tickRuns() {
  for (const r of runs) {
    if (r.status !== 'running' && r.status !== 'queued') continue
    const elapsed = (Date.now() - (runStart.get(r.id) ?? Date.now())) / 1000
    const pages = Math.min(PAGES, Math.floor(elapsed / 3))
    r.status = 'running'
    r.pages_total = PAGES
    const steps = r.steps ?? []
    const idx = Math.min(steps.length, Math.floor(elapsed / 4))
    steps.forEach((s, i) => {
      if (i < idx && s.status !== 'success') { s.status = 'success'; s.summary = STEP_DEFS.find(([k]) => k === s.key)![2]; s.finished_at = iso(now()) }
      if (i === idx && s.status === 'pending') { s.status = 'running'; s.started_at = iso(now()) }
    })
    if (idx >= steps.length) { r.status = 'success'; r.finished_at = iso(now()); r.inserted = 24; continue }
    if (pages > r.pages_done) {
      for (let p = r.pages_done + 1; p <= pages; p++) {
        const n = 18 + (p % 5)
        const fresh = 3 + (p % 4)
        r.found += n
        r.inserted += fresh
        r.duplicated += n - fresh
        const t = new Date().toLocaleTimeString('th-TH', { hour12: false })
        r.log = [...r.log, `${t}    [หน้า ${p}] พบ ${n} งาน · ใหม่ ${fresh} · หน่วง 12.${p}s`].slice(-80)
      }
      r.pages_done = pages
    }
  }
}

function nextRun(s: Source): string | null {
  if (!s.enabled) return null
  const d = now()
  if (s.mode === 'daily') {
    const [h, m] = (s.daily_at ?? '02:00').split(':').map(Number)
    const t = new Date(d)
    t.setHours(h, m, 0, 0)
    if (t <= d) t.setDate(t.getDate() + 1)
    return iso(t)
  }
  const every = s.every_hours ?? 6
  const last = runs.find((r) => r.source === s.source)
  const base = last ? new Date(last.started_at).getTime() : Date.now()
  let t = base + every * 3600_000
  while (t <= Date.now()) t += every * 3600_000
  return iso(new Date(t))
}

const courses: Course[] = [
  ['CODE-01', 'การเขียนโปรแกรมคอมพิวเตอร์', 'Computer Programming', 1, ['Python', 'Git', 'Linux']],
  ['CODE-02', 'โครงสร้างข้อมูลและอัลกอริทึม', 'Data Structures and Algorithms', 2, ['Python']],
  ['CODE-03', 'ระบบฐานข้อมูล', 'Database Systems', 2, ['SQL']],
  ['CODE-04', 'เครือข่ายคอมพิวเตอร์', 'Computer Networks', 3, ['Linux']],
  ['CODE-05', 'วิศวกรรมซอฟต์แวร์', 'Software Engineering', 3, ['Git', 'UML', 'Agile', 'Software Testing']],
  ['CODE-06', 'ปัญญาประดิษฐ์', 'Artificial Intelligence', 3, ['Python', 'Machine Learning']],
  ['CODE-07', 'การเรียนรู้ของเครื่อง', 'Machine Learning', 4, ['Python', 'Machine Learning', 'SQL']],
  ['CODE-08', 'ระบบฝังตัว', 'Embedded Systems', 3, ['Linux']],
].map(([code, th, en, year, skills]) => ({
  code: code as string, name_th: th as string, name_en: en as string, year: year as number, credits: '3(2-2-5)',
  description: '[วางคำอธิบายรายวิชาจากเล่มหลักสูตร]', skills: skills as string[],
}))

function gapPayload(): Gap {
  const heatSkills = ['Python', 'SQL', 'Docker', 'React', 'Linux', 'Git', 'AWS', 'ML', 'K8s', 'TS']
  const values = [
    [1, 0, 0, 0, 0.3, 0.4, 0, 0, 0, 0], [0.8, 0, 0, 0, 0, 0.2, 0, 0, 0, 0], [0.3, 1, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0.4, 0, 0.8, 0, 0.3, 0, 0.2, 0],
    [0.3, 0.3, 0.4, 0.45, 0.3, 0.3, 0, 0, 0, 0], [0.9, 0, 0, 0, 0, 0, 0, 0.8, 0, 0], [1, 0.3, 0, 0, 0, 0, 0, 1, 0, 0], [0, 0, 0, 0, 0.5, 0, 0, 0, 0, 0],
  ]
  const contrib = [0.18, 0.12, 0.15, 0.1, 0.16, 0.14, 0.17, 0.05]
  const rel = [0.75, 0.6, 0.8, 0.45, 0.65, 0.7, 0.85, 0.3]
  return {
    overall_match_score: 0.62, skills_analyzed: 50, covered: 31, missing: 19, total_jobs: 3248,
    computed_at: iso(now()),
    params: { top_n: 50, tau: 0.55, cov_threshold: 0.5, matrix_demand_threshold: 0.12 },
    courses: courses.map((c, i) => ({ code: c.code, name: c.name_th, contribution: contrib[i] ?? 0.05, relevance: rel[i] ?? 0.5, covered_skills: c.skills }))
      .sort((a, b) => b.contribution - a.contribution),
    missing_skills: [
      ['AWS', 0.14, 0, 'เครือข่ายคอมพิวเตอร์'], ['Docker', 0.22, 0.41, 'วิศวกรรมซอฟต์แวร์'], ['Git', 0.18, 0.4, 'วิศวกรรมซอฟต์แวร์'],
      ['TypeScript', 0.1, 0, 'วิศวกรรมซอฟต์แวร์'], ['CI/CD', 0.08, 0, 'วิศวกรรมซอฟต์แวร์'], ['Kubernetes', 0.09, 0.2, 'เครือข่ายคอมพิวเตอร์'],
    ].map(([skill, d, c, course]) => ({ skill: skill as string, demand_pct: d as number, coverage: c as number, priority: (d as number) * (1 - (c as number)),
      suggested_course: course as string, suggested_course_code: '' }))
      .sort((a, b) => b.priority - a.priority),
    matrix: [
      ['Python', 0.41, 0.95], ['SQL', 0.36, 0.9], ['JavaScript', 0.29, 0.55], ['Docker', 0.22, 0.41], ['React', 0.21, 0.45], ['Linux', 0.19, 0.8],
      ['Git', 0.18, 0.4], ['Java', 0.16, 0.7], ['AWS', 0.14, 0], ['Machine Learning', 0.125, 0.95], ['TypeScript', 0.1, 0], ['Kubernetes', 0.09, 0.2],
      ['CI/CD', 0.06, 0], ['LLM', 0.07, 0.35],
    ].map(([skill, d, c]) => ({ skill: skill as string, demand_pct: d as number, coverage: c as number, is_ai_skill: ['Machine Learning', 'LLM'].includes(skill as string) })),
    heatmap: { courses: courses.map((c) => c.name_th), skills: heatSkills, values: courses.map((_, i) => values[i] ?? heatSkills.map(() => 0)) },
  }
}

function toCsv(g: Gap): string {
  const rows = [['Match Score', g.overall_match_score], [], ['Skill', 'Demand %', 'Coverage', 'Priority', 'Suggested course'],
    ...g.missing_skills.map((m) => [m.skill, (m.demand_pct * 100).toFixed(1), m.coverage, m.priority.toFixed(3), m.suggested_course])]
  return '\ufeff' + rows.map((r) => r.join(',')).join('\n')
}
export const mockGapCsv = () => toCsv(gapPayload())

function matches(j: JobCard, f: SearchFilters): boolean {
  if (f.min_salary && (j.salary_max ?? j.salary_min ?? 0) < f.min_salary) return false
  if (f.level?.length && !f.level.includes(j.level as never)) return false
  if (f.work_mode?.length && !f.work_mode.includes(j.work_mode as never)) return false
  if (f.province?.length && !f.province.includes(j.province ?? '')) return false
  return true
}

export async function mockRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  await wait()
  const method = (init.method ?? 'GET').toUpperCase()
  const body = init.body ? JSON.parse(String(init.body)) : undefined
  const [p] = path.split('?')
  tickRuns()
  const out = (x: unknown) => x as T

  if (p === '/auth/login') {
    if (!body?.username || !body?.password) throw new MockError(401, 'BAD_CREDENTIALS', 'ใส่ชื่อผู้ใช้และรหัสผ่าน')
    return out({ access_token: 'mock-token', expires_at: iso(new Date(Date.now() + 8 * 3600_000)) })
  }
  if (p === '/analytics/summary')
    return out({ total_jobs: 4210, total_jobs_prev: null, new_7d: 186, new_7d_prev: 165, ai_jobs: 877, ai_share: 0.21, ai_share_prev: null,
      median_salary: 25000, median_salary_prev: null, salary_disclosed_share: 0.61, curriculum_match: 0.294, window_days: 3650,
      companies: 2222, unique_skills: 4177, job_skill_pairs: 34549, courses: 79, last_scraped_at: iso(hoursAgo(30)),
      std_coverage: 0.723, std_skills: 1324 })
  if (p === '/analytics/top-skills') {
    const type = new URLSearchParams(path.split('?')[1]).get('type')
    const hard = [['Python', 0.41, 0.021], ['SQL', 0.36, 0.004], ['JavaScript', 0.29, -0.008], ['Docker', 0.22, 0.034], ['React', 0.21, 0.01],
      ['Linux', 0.19, -0.002], ['Git', 0.18, 0.006], ['Java', 0.16, -0.015], ['AWS', 0.14, 0.022], ['Machine Learning', 0.12, 0.012]]
    const soft = [['Teamwork', 0.48, 0.01], ['Communication', 0.44, 0.02], ['Problem Solving', 0.39, 0.005], ['Responsibility', 0.22, -0.01], ['English', 0.2, 0.01]]
    return out((type === 'soft' ? soft : hard).map(([skill, pct, delta]) => ({ skill, pct, jobs: Math.round((pct as number) * 4210), delta_pct: delta, is_ai_skill: skill === 'Machine Learning' })))
  }
  if (p === '/analytics/salary-histogram') {
    const bands: [string, number, number | null, number][] = [['<15k', 0, 15000, 120], ['15–20k', 15000, 20000, 480], ['20–25k', 20000, 25000, 610], ['25–30k', 25000, 30000, 420],
      ['30–40k', 30000, 40000, 380], ['40–50k', 40000, 50000, 210], ['50–70k', 50000, 70000, 140], ['70–100k', 70000, 100000, 60], ['100k+', 100000, null, 18]]
    return out(bands.map(([band, min, max, n]) => ({ band, min, max, n })))
  }
  if (p === '/analytics/standards')
    return out([['ANY', 'รวมทุกมาตรฐาน', 1324, 0.317, 0.723], ['ONET', 'O*NET (สหรัฐฯ)', 700, 0.168, 0.44], ['ESCO', 'ESCO (สหภาพยุโรป)', 370, 0.089, 0.374],
      ['SKILLSFUTURE', 'SkillsFuture (สิงคโปร์)', 258, 0.062, 0.211], ['DSD', 'กรมพัฒนาฝีมือแรงงาน', 218, 0.052, 0.145], ['TPQI', 'TPQI คุณวุฒิวิชาชีพ', 159, 0.038, 0.11]]
      .map(([standard, label, skills, u, w]) => ({ standard, label, is_total: standard === 'ANY', skills, unique_pct: u, weighted_pct: w })))
  if (p === '/analytics/pipeline')
    return out({ jobs: 4210, extracted: 4210, jobs_embedded: 4210, skills: 4177, skills_embedded: 4177, skills_std_mapped: 1324, courses: 79, course_links: 370,
      first_scraped_at: iso(hoursAgo(24 * 20)), last_scraped_at: iso(hoursAgo(30)), last_extracted_at: iso(hoursAgo(26)),
      by_source: [{ source: 'jobthai', jobs: 2310 }, { source: 'jobbkk', jobs: 1900 }] })
  if (p === '/search/suggest') {
    const q = String(new URLSearchParams(path.split('?')[1] ?? '').get('q') ?? '').toLowerCase()
    const skills = SKILL_NAMES.filter((s) => s.toLowerCase().includes(q)).slice(0, 6).map((text, i) => ({ text, jobs: 900 - i * 90 }))
    const titles = [...new Set(JOBS.map((j) => j.title))].filter((t) => t.toLowerCase().includes(q)).slice(0, 6).map((text) => ({ text, jobs: 12 }))
    return out({ skills, titles })
  }
  if (p === '/search/related-skills')
    return out([['Equipment Repair', 0.73], ['Electronics Repair', 0.71], ['Equipment Maintenance', 0.7], ['Electrical Repair', 0.69]].map(([skill, similarity]) => ({ skill, similarity })))
  if (p === '/curriculum/skills') return out(SKILL_NAMES.slice(0, 10))
  if (p === '/analytics/salary-distribution')
    return out([
      { level: 'Entry', n: 612, min: 15000, p25: 18000, median: 25000, p75: 32000, max: 45000 },
      { level: 'Mid', n: 811, min: 22000, p25: 28000, median: 38000, p75: 50000, max: 70000 },
      { level: 'Senior', n: 289, min: 35000, p25: 45000, median: 60000, p75: 80000, max: 120000 },
    ])
  if (p === '/analytics/ai-trend') {
    const shares = [0.22, 0.23, 0.23, 0.25, 0.24, 0.26, 0.27, 0.28]
    return out({
      weeks: shares.map((s, i) => ({ week_start: iso(new Date(Date.now() - (7 - i) * 7 * 86400_000)), total: 160 + i * 6 + (i % 3) * 8, ai: Math.round((160 + i * 6) * s), share: s })),
      groups: [{ group: 'Machine Learning', pct: 0.12, delta_pct: 0.012 }, { group: 'LLM / Generative AI', pct: 0.07, delta_pct: 0.03 },
        { group: 'Data Science', pct: 0.05, delta_pct: 0.008 }, { group: 'Computer Vision', pct: 0.03, delta_pct: 0.003 }],
    })
  }
  if (p === '/analytics/filters')
    return out({
      sources: [{ value: 'jobthai', count: 1730 }, { value: 'jobbkk', count: 1518 }],
      provinces: [{ value: 'กรุงเทพฯ', count: 1642 }, { value: 'ขอนแก่น', count: 214 }, { value: 'ชลบุรี', count: 188 }, { value: 'เชียงใหม่', count: 121 }],
      levels: [{ value: 'Entry', count: 812 }, { value: 'Mid', count: 1204 }, { value: 'Senior', count: 486 }],
      work_modes: [{ value: 'Onsite', count: 2011 }, { value: 'Hybrid', count: 842 }, { value: 'Remote', count: 395 }],
    })
  if (p === '/search') {
    const all = JOBS.filter((j) => matches(j, body.filters ?? {})).map(({ skills: _s, ...card }) => card)
    const page = body.page ?? 1, size = body.page_size ?? 20
    return out({ took_ms: { embed: 180, db: 42 }, results: all.slice((page - 1) * size, page * size), page, page_size: size, total: all.length, max_results: 200 })
  }
  const jobMatch = p.match(/^\/jobs\/(\d+)$/)
  if (jobMatch) {
    const j = JOBS.find((x) => x.job_id === Number(jobMatch[1]))
    if (!j) throw new MockError(404, 'JOB_NOT_FOUND', 'ไม่พบประกาศงานนี้')
    const detail: JobDetail = { id: j.job_id, title: j.title, company: null, province: j.province, salary_min: j.salary_min, salary_max: j.salary_max,
      level: j.level, work_mode: j.work_mode, source: j.source, source_url: j.source_url,
      description: '[ข้อความจาก description_clean ส่วนหน้าที่และคุณสมบัติ ที่ผ่านการทำความสะอาดแล้ว]', is_ai_related: true,
      posted_at: iso(hoursAgo(72)), last_updated_at: iso(hoursAgo(4)),
      skills: j.skills.map((s, i) => ({ id: i + 1, name: s.name, type: s.type, is_ai_skill: s.ai })) }
    return out(detail)
  }
  if (p === '/crawler/sources')
    return out(sources.map((s) => ({ ...s, next_run_at: nextRun(s), last_run: runs.find((r) => r.source === s.source) ?? null })))
  if (p === '/crawler/runs') return out(runs.slice(0, 20))
  if (p === '/crawler/status')
    return out({ active_run_id: runs.find((r) => r.status === 'running' || r.status === 'queued')?.id ?? null, process_problems: [],
      extract_limit_per_run: 500, auto_delay: '12–15 วินาที/request', robots_txt: true })
  const feedRun = p.match(/^\/crawler\/runs\/(\d+)\/feed$/)
  if (feedRun) {
    const r = runs.find((x) => x.id === Number(feedRun[1]))
    if (!r || r.source === 'process') return out([])
    const base = r.source === 'jobbkk' ? 'https://www.jobbkk.com/jobs/detailurgent/1000' : 'https://www.jobthai.com/th/company/job'
    return out(JOBS.slice(0, 6).map((j, i) => {
      const kind = (['new', 'new', 'updated', 'new', 'bumped', 'partial'] as const)[i]
      return { kind, url: `${base}/${1200 + i}`, title: j.title, company: 'บริษัทตัวอย่าง จำกัด', salary: '25,000 - 35,000', location: j.province,
        post_date: '6 ต.ค. 69', at: `0${9 + i}:1${i}:00`.slice(-8), before: kind === 'new' ? undefined : '18 ก.ย. 69',
        changed: kind === 'updated' ? ['เงินเดือน', 'คุณสมบัติ'] : undefined, missing: kind === 'partial' ? ['qualification'] : undefined,
        job_id: j.job_id,
        db_changes: kind === 'updated' ? { reextract: true, fields: [
          { field: 'salary_raw', label: 'เงินเดือน', old: '20,000 - 25,000', new: '25,000 - 35,000' },
          { field: 'qualification', label: 'คุณสมบัติ', old: 'ปริญญาตรี วิศวกรรมคอมพิวเตอร์', new: 'ปริญญาตรี วิศวกรรมคอมพิวเตอร์\nมีประสบการณ์ Python 1 ปีขึ้นไป' }] } : null }
    }))
  }
  const oneRun = p.match(/^\/crawler\/runs\/(\d+)(\/cancel)?$/)
  if (oneRun) {
    const r = runs.find((x) => x.id === Number(oneRun[1]))
    if (!r) throw new MockError(404, 'RUN_NOT_FOUND', 'ไม่พบรอบนี้')
    if (oneRun[2] && method === 'POST') {
      r.status = 'cancelled'; r.finished_at = iso(now()); r.error_message = 'หยุดโดยผู้ดูแล — ข้อมูลที่บันทึกแล้วไม่หาย รอบหน้าจะทำต่อ'
      r.steps?.forEach((s) => { if (s.status === 'running') s.status = 'cancelled'; else if (s.status === 'pending') s.status = 'skipped' })
      return out({ ok: true })
    }
    return out({ ...r })
  }
  const sched = p.match(/^\/crawler\/sources\/(\w+)\/schedule$/)
  if (sched && method === 'PUT') {
    const s = sources.find((x) => x.source === sched[1])
    if (!s) throw new MockError(404, 'UNKNOWN_SOURCE', 'ไม่พบแหล่งข้อมูล')
    if (body.mode === 'interval' && (!body.every_hours || body.every_hours < 1)) throw new MockError(422, 'INVALID_INPUT', 'รอบเวลาต้องไม่ต่ำกว่า 1 ชั่วโมง')
    Object.assign(s, { mode: body.mode, enabled: body.enabled, every_hours: body.every_hours ?? s.every_hours, daily_at: body.daily_at ?? s.daily_at })
    return out({ ...s, next_run_at: nextRun(s) })
  }
  const run = p === '/crawler/process' ? [p, 'process'] : p.match(/^\/crawler\/sources\/(\w+)\/runs$/)
  if (run && method === 'POST') {
    if (runs.some((r) => r.status === 'running' || r.status === 'queued'))
      throw new MockError(409, 'RUN_IN_PROGRESS', 'มีรอบอื่นกำลังรันอยู่ รอให้จบก่อน หรือกดหยุด')
    const r: Run = { id: ++runSeq, source: run[1], trigger: 'manual', status: 'queued', started_at: iso(now()), finished_at: null, found: 0, inserted: 0,
      duplicated: 0, pages_done: 0, pages_total: PAGES, log: [], steps: mkSteps(run[1], false), error_message: null }
    runs.unshift(r)
    runStart.set(r.id, Date.now())
    return out({ run_id: r.id })
  }
  if (p === '/curriculum/courses' && method === 'GET') return out(courses.map((c) => ({ ...c })))
  if (p === '/curriculum/courses' && method === 'POST') {
    if (courses.some((c) => c.code === body.code)) throw new MockError(409, 'COURSE_EXISTS', `มีรหัสวิชา ${body.code} แล้ว`)
    const c: Course = { ...body, skills: SKILL_NAMES.filter((s) => String(body.description).toLowerCase().includes(s.toLowerCase())) }
    courses.push(c)
    return out(c)
  }
  const course = p.match(/^\/curriculum\/courses\/([^/]+)(\/extract|\/skills)?$/)
  if (course) {
    const code = decodeURIComponent(course[1])
    const idx = courses.findIndex((c) => c.code === code)
    if (idx < 0) throw new MockError(404, 'COURSE_NOT_FOUND', 'ไม่พบรายวิชา')
    const c = courses[idx]
    if (method === 'DELETE') { courses.splice(idx, 1); return out(undefined) }
    if (course[2] === '/extract') {
      const found = SKILL_NAMES.filter((s) => `${c.name_en} ${c.description}`.toLowerCase().includes(s.toLowerCase()))
      c.skills = found.length ? found : c.skills
      return out({ ...c })
    }
    if (course[2] === '/skills') { c.skills = body.skills; return out({ ...c }) }
    Object.assign(c, body)
    return out({ ...c })
  }
  if (p === '/gap-analysis' || p === '/gap-analysis/recalculate') return out(gapPayload())
  throw new MockError(404, 'NOT_FOUND', `mock: no handler for ${method} ${p}`)
}
