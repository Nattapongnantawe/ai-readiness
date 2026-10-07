import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Heatmap } from '../components/charts/Heatmap'
import { DemandCoverage } from '../components/charts/DemandCoverage'
import { Icon } from '../components/icons'
import { PageBody, PageHeader } from '../components/layout/PageHeader'
import { Ring } from '../components/ui/Ring'
import { Empty, ErrorState, Skeleton } from '../components/ui/States'
import { api, downloadGapCsv } from '../lib/api'
import { useAuth } from '../lib/auth'
import { num, pct, when } from '../lib/format'
import type { Course } from '../lib/types'

const MAX_COURSES = 15
const CATEGORY: Record<string, string> = {
  general_education: 'หมวดศึกษาทั่วไป', core: 'วิชาแกน', major_required: 'วิชาเฉพาะด้าน (บังคับ)',
  major_elective: 'วิชาเลือก', field_experience: 'สัมมนา โครงงาน และสหกิจศึกษา',
}
const METHOD: Record<string, string> = { exact: 'ตรงตัว', semantic: 'ความหมาย', manual: 'ผู้วิจัยตรวจ' }

function CoursePicker({ courses, selected, onChange, onClose }: {
  courses: Course[]; selected: string[]; onChange: (codes: string[]) => void; onClose: () => void
}) {
  const [q, setQ] = useState('')
  const groups = useMemo(() => {
    const t = q.trim().toLowerCase()
    const list = courses.filter((c) => !t || `${c.code} ${c.name_th} ${c.name_en ?? ''}`.toLowerCase().includes(t))
    const by: Record<string, Course[]> = {}
    list.forEach((c) => { (by[c.category ?? 'other'] ??= []).push(c) })
    return Object.entries(by)
  }, [courses, q])
  const toggle = (code: string) =>
    onChange(selected.includes(code) ? selected.filter((x) => x !== code) : selected.length >= MAX_COURSES ? selected : [...selected, code])
  return (
    <section aria-label="เลือกรายวิชา" className="card flex flex-col gap-3 p-4 lg:px-[22px] lg:py-5">
      <div className="flex flex-col justify-between gap-2 lg:flex-row lg:items-center">
        <div><h2 className="card-title">เลือกรายวิชาที่จะเทียบ</h2>
          <p className="text-[13px] text-muted">เลือก 10–15 วิชา (สูงสุด {MAX_COURSES}) หรือไม่เลือกเลยเพื่อใช้ทั้งหลักสูตร {courses.length} วิชา</p></div>
        <div className="flex items-center gap-2">
          <span className="num rounded-full bg-brand-100 px-2.5 py-1 text-xs font-semibold text-brand-800">เลือก {selected.length}/{MAX_COURSES}</span>
          <button type="button" className="btn-outline h-9" onClick={() => onChange([])} disabled={!selected.length}>ใช้ทั้งหลักสูตร</button>
          <button type="button" className="btn-primary h-9" onClick={onClose}>เสร็จ</button>
        </div>
      </div>
      <label htmlFor="course-q" className="sr-only">ค้นหารายวิชา</label>
      <input id="course-q" className="input" placeholder="ค้นหารหัสหรือชื่อวิชา" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="grid max-h-[420px] gap-4 overflow-y-auto pr-1 lg:grid-cols-2">
        {groups.map(([cat, list]) => (
          <fieldset key={cat} className="flex flex-col gap-0.5">
            <legend className="pb-1.5 text-xs font-semibold text-muted">{CATEGORY[cat] ?? cat}</legend>
            {list.map((c) => {
              const on = selected.includes(c.code)
              const full = !on && selected.length >= MAX_COURSES
              return (
                <label key={c.code} className={`flex min-h-9 items-start gap-2.5 rounded-lg px-1.5 py-1 text-sm ${full ? 'opacity-50' : 'hover:bg-brand-50'}`}>
                  <input type="checkbox" checked={on} disabled={full} onChange={() => toggle(c.code)} className="mt-1 h-4 w-4 accent-brand-700" />
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate">{c.name_th}</span>
                    <span className="truncate text-xs text-muted"><span className="font-mono">{c.code}</span> · {c.skills.length} ทักษะ</span>
                  </span>
                </label>
              )
            })}
          </fieldset>
        ))}
      </div>
    </section>
  )
}

export default function Gap() {
  const { isAdmin } = useAuth()
  const qc = useQueryClient()
  const [params, setParams] = useSearchParams()
  const selected = (params.get('courses') ?? '').split(',').filter(Boolean)
  const noManual = params.get('no_manual') === '1'
  const setSelected = (codes: string[]) => setParams((p) => { if (codes.length) p.set('courses', codes.join(',')); else p.delete('courses'); return p }, { replace: true })
  const setNoManual = (v: boolean) => setParams((p) => { if (v) p.set('no_manual', '1'); else p.delete('no_manual'); return p }, { replace: true })
  const [picking, setPicking] = useState(false)
  const key = ['gap', selected.join(','), noManual]
  const gap = useQuery({ queryKey: key, queryFn: () => api.gap(selected, noManual) })
  const courses = useQuery({ queryKey: ['courses'], queryFn: api.courses, staleTime: 300_000 })
  const recalc = useMutation({ mutationFn: api.recalcGap, onSuccess: () => qc.invalidateQueries({ queryKey: ['gap'] }) })
  const [exportError, setExportError] = useState<string | null>(null)
  const g = gap.data

  const exportCsv = async () => {
    setExportError(null)
    try { await downloadGapCsv(selected, noManual) } catch (e) { setExportError(e instanceof Error ? e.message : 'ส่งออกไม่สำเร็จ') }
  }
  const maxPriority = Math.max(0.0001, ...(g?.missing_skills ?? []).map((m) => m.priority))

  return (
    <>
      <PageHeader crumbs={['หลักสูตร', 'Curriculum Gap Analysis']} title="หลักสูตรตรงกับตลาดแค่ไหน"
        subtitle={g ? `${selected.length ? `${g.courses.length} วิชาที่เลือก` : `ทั้งหลักสูตร ${g.courses.length} วิชา`} เทียบกับ ${num(g.skills_analyzed)} ทักษะจาก ${num(g.total_jobs)} ประกาศ · คำนวณ ${when(g.computed_at)}` : 'กำลังโหลด'}
        actions={
          <>
            <button type="button" className="btn-outline" aria-expanded={picking} onClick={() => setPicking((x) => !x)}>
              <Icon name="filter" size={16} />{selected.length ? `เลือก ${selected.length} วิชา` : 'เลือกรายวิชา'}
            </button>
            {isAdmin && (
              <button type="button" className="btn-outline" onClick={() => recalc.mutate()} disabled={recalc.isPending}>
                <Icon name="refresh" size={16} />{recalc.isPending ? 'กำลังคำนวณ…' : 'คำนวณใหม่'}
              </button>
            )}
            <button type="button" className="btn-primary" onClick={exportCsv}><Icon name="download" size={16} />ส่งออก CSV</button>
          </>
        } />
      <PageBody>
        {picking && courses.data && <CoursePicker courses={courses.data} selected={selected} onChange={setSelected} onClose={() => setPicking(false)} />}
        {exportError && <ErrorState error={new Error(exportError)} />}
        {recalc.isError && <ErrorState error={recalc.error} />}
        {gap.isError ? <ErrorState error={gap.error} onRetry={() => gap.refetch()} /> : !g ? <Skeleton className="h-64" /> : g.courses.length === 0 || g.skills_analyzed === 0 ? (
          <Empty title="ยังคำนวณไม่ได้">
            ต้องมีทั้งข้อมูลงานที่สกัดทักษะแล้ว และรายวิชาในหลักสูตร {isAdmin && <Link to="/admin/courses" className="text-brand-800 underline">เพิ่มรายวิชา</Link>}
          </Empty>
        ) : (
          <>
            <section className="dots-bg flex flex-col gap-5 overflow-hidden rounded-4xl bg-navy p-5 text-white lg:flex-row lg:items-center lg:gap-8 lg:rounded-2xl lg:px-7 lg:py-6">
              <div className="flex items-center gap-4 lg:contents">
                <Ring value={g.overall_match_score} size={128} stroke={12} track="#1A2C4D" color="#9DB8E3" label={`Match Score ${pct(g.overall_match_score, 1)}`}>
                  <span className="num text-[30px] font-semibold tracking-[-0.04em]">{pct(g.overall_match_score, 1)}</span>
                  <span className="text-[11px] text-navy-text">Match Score</span>
                </Ring>
                <div className="flex flex-1 flex-col gap-2">
                  <p className="text-lg font-semibold leading-snug tracking-[-0.015em] lg:text-[22px]">{selected.length ? `${g.courses.length} วิชาที่เลือก` : 'หลักสูตร'}ครอบคลุม {pct(g.overall_match_score, 1)} ของความต้องการตลาด</p>
                  <p className="hidden text-sm leading-relaxed text-navy-text lg:block">ถ่วงน้ำหนักตามจำนวนงานที่ต้องการแต่ละทักษะ จาก {g.total_jobs.toLocaleString('en-US')} ตำแหน่ง
                    {g.overall_match_score_no_manual != null && !noManual && <> · ไม่นับคู่ที่ผู้วิจัยตรวจ {pct(g.overall_match_score_no_manual, 1)}</>}</p>
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    {Object.entries(g.methods ?? {}).map(([m, n]) => (
                      <span key={m} className="rounded-full bg-white/10 px-2 py-0.5 text-navy-text">{METHOD[m] ?? m} {num(n)}</span>
                    ))}
                    <label className="flex items-center gap-1.5 rounded-full bg-white/10 px-2 py-0.5 text-navy-text">
                      <input type="checkbox" checked={noManual} onChange={(e) => setNoManual(e.target.checked)} className="h-3.5 w-3.5 accent-brand-300" />
                      ไม่นับคู่ที่ผู้วิจัยตรวจ
                    </label>
                  </div>
                </div>
              </div>
              <dl className="grid grid-cols-2 gap-y-3 border-t border-navy-500 pt-3.5 sm:grid-cols-4 lg:flex lg:shrink-0 lg:border-0 lg:pt-0">
                {[['ทักษะ', num(g.skills_analyzed), 'text-white'], ['ครอบคลุม', num(g.covered), 'text-brand-300'], ['ยังขาด', num(g.missing), 'text-maroon-light'],
                  ...(g.missing_min_jobs != null ? [[`ยังขาด (≥${g.missing_min_jobs_threshold ?? 10} งาน)`, num(g.missing_min_jobs), 'text-maroon-light']] : [])].map(([k, v, cls], i) => (
                  <div key={k as string} className={`flex flex-col gap-0.5 ${i % 2 === 1 ? 'border-l border-navy-500 pl-3.5' : ''} ${i > 0 ? 'sm:border-l sm:border-navy-500 sm:pl-3.5' : ''} lg:border-l lg:border-navy-500 lg:px-6`}>
                    <dt className="text-xs text-navy-text">{k}</dt><dd className={`num text-[26px] font-semibold tracking-[-0.03em] lg:text-[32px] ${cls}`}>{v}</dd>
                  </div>
                ))}
              </dl>
            </section>

            <div className="grid gap-4 lg:grid-cols-12">
              <section className="card flex flex-col gap-3 p-4 lg:col-span-7 lg:px-[22px] lg:py-5">
                <div><h2 className="card-title">ความต้องการของตลาด vs หลักสูตร</h2><p className="text-[13px] text-muted">ทักษะเรียงตาม % ของงานที่ต้องการ · แท่งแดง = ยังไม่มีวิชาที่เลือกสอน (ชี้เพื่อดูว่าสอนในวิชาไหน)</p></div>
                <DemandCoverage points={g.matrix} covThreshold={g.params.cov_threshold} />
              </section>

              <section className="card flex flex-col p-4 lg:col-span-5 lg:px-[22px] lg:py-5">
                <div className="pb-2"><h2 className="card-title">ทักษะที่ควรเพิ่ม</h2><p className="text-[13px] text-muted">ตลาดต้องการมาก แต่ยังไม่มีวิชาที่เลือกรองรับ · เรียงตาม Gap Priority = d × (1 − c)</p></div>
                <ol className="max-h-[560px] overflow-y-auto pr-1">
                  {g.missing_skills.slice(0, 15).map((m, i) => (
                    <li key={m.skill} className="grid grid-cols-[24px_minmax(0,1fr)] gap-2.5 border-t border-line-soft py-3">
                      <span className="num pt-0.5 font-mono text-xs text-faint">{String(i + 1).padStart(2, '0')}</span>
                      <div className="flex flex-col gap-2">
                        <div className="flex items-baseline justify-between gap-2"><span className="text-[15px] font-semibold">{m.skill}</span>
                          <span className="num text-xs text-muted">{m.jobs != null ? `${num(m.jobs)} งาน · ` : ''}{pct(m.demand_pct, 1)}</span></div>
                        <div className="h-1.5 rounded-full bg-maroon-200"><div className="h-1.5 rounded-full bg-maroon" style={{ width: `${(m.priority / maxPriority) * 100}%` }} /></div>
                        <span className="text-xs text-muted">{m.suggested_course
                          ? <>ต่อยอดได้ใน <span className="font-medium text-ink">{m.suggested_course_code} {m.suggested_course}</span>
                              {m.suggested_topic && m.suggested_topic !== m.suggested_course && <> · หัวข้อ “{m.suggested_topic}”</>}</>
                          : 'ไม่มีหัวข้อในวิชาที่ใกล้เคียง → ควรเป็นเนื้อหาใหม่'}</span>
                      </div>
                    </li>
                  ))}
                  {!g.missing_skills.length && <li className="py-4 text-sm text-muted">ทุกทักษะใน Top {g.skills_analyzed} ครอบคลุมแล้ว</li>}
                </ol>
              </section>
            </div>

            <section className="card flex flex-col gap-3.5 p-4 lg:px-[22px] lg:py-5">
              <div className="flex items-start justify-between gap-4">
                <div><h2 className="card-title">คะแนนรายวิชา</h2><p className="text-[13px] text-muted">Contribution = ส่วนของ demand ที่วิชาครอบคลุม · Relevance = % ทักษะของวิชาที่อยู่ใน Top {g.params.relevance_top ?? g.skills_analyzed} ทักษะที่ตลาดต้องการ</p></div>
                {isAdmin && <Link to="/admin/courses" className="hidden shrink-0 text-[13px] font-medium text-brand-800 hover:underline lg:block">จัดการรายวิชา</Link>}
              </div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4 lg:gap-3">
                {(selected.length ? g.courses : g.courses.slice(0, 16)).map((c) => (
                  <div key={c.code} className="flex items-center gap-3 rounded-xl border border-line-soft bg-[#FAFAFA] p-3.5 lg:flex-col lg:items-stretch lg:p-4">
                    <span className="flex flex-1 flex-col lg:min-h-9"><span className="text-sm font-medium leading-snug lg:text-[13px]">{c.name}</span>
                      <span className="text-[11px] text-muted"><span className="font-mono">{c.code}</span>{c.skill_count != null ? ` · ${c.skill_count} ทักษะ` : ''}</span></span>
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="num text-lg font-semibold tracking-[-0.03em] lg:text-2xl">{pct(c.contribution)}</span>
                      <span className="hidden text-xs text-muted lg:inline">contribution</span>
                    </div>
                    <div className="hidden flex-col gap-1 lg:flex">
                      <div className="h-1 rounded-full bg-brand-150"><div className="h-1 rounded-full bg-brand-700" style={{ width: `${c.relevance * 100}%` }} /></div>
                      <span className="num text-xs text-muted">relevance {pct(c.relevance)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="card flex flex-col gap-3 p-4 lg:px-[22px] lg:py-5">
              <div className="flex flex-col justify-between gap-2 lg:flex-row lg:items-center">
                <h2 className="card-title">Coverage heatmap · {selected.length ? 'วิชาที่เลือก' : `${g.heatmap.courses.length} วิชาที่ครอบคลุมมากที่สุด`} × {g.heatmap.skills.length} ทักษะยอดนิยม</h2>
                <div className="flex items-center gap-1 text-xs text-muted" aria-hidden="true">
                  <span className="mr-1">0</span>
                  {['#FAFAFA', '#E3ECF9', '#B9CDEE', '#7BA3D9', '#2F63B8'].map((c) => <span key={c} className="h-2.5 w-5 rounded-[3px] border border-line-soft" style={{ background: c }} />)}
                  <span className="ml-1">1</span>
                </div>
              </div>
              <Heatmap {...g.heatmap} />
            </section>
          </>
        )}
      </PageBody>
    </>
  )
}