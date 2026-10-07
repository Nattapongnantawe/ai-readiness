import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AreaTrend } from '../components/charts/AreaTrend'
import { SalaryRanges } from '../components/charts/SalaryRanges'
import { Sparkline } from '../components/charts/Sparkline'
import { Icon } from '../components/icons'
import { PageBody, PageHeader } from '../components/layout/PageHeader'
import { Delta, change } from '../components/ui/Delta'
import { Segmented } from '../components/ui/Segmented'
import { ErrorState, Skeleton } from '../components/ui/States'
import { api } from '../lib/api'
import { baht, bahtK, date, dayMonth, num, pct } from '../lib/format'
import type { JobFilterParams } from '../lib/types'

const ALL_DAYS = 3650
const DAYS = [{ value: 30, label: '30 วัน' }, { value: 90, label: '90 วัน' }, { value: 365, label: '1 ปี' }, { value: ALL_DAYS, label: 'ทั้งหมด' }]
const FILTER_KEYS = ['source', 'province', 'work_mode', 'level'] as const
const GROUP_COLORS = ['#234C91', '#5C84C2', '#9DB8E3', '#DCE7F8']

function useFilters(): [JobFilterParams, (k: string, v: string | number | null) => void, () => void] {
  const [params, setParams] = useSearchParams()
  const f: JobFilterParams = { days: Number(params.get('days') ?? ALL_DAYS) }
  FILTER_KEYS.forEach((k) => { const v = params.get(k); if (v) f[k] = v })
  const set = (k: string, v: string | number | null) => setParams((p) => { if (v == null || v === '') p.delete(k); else p.set(k, String(v)); return p }, { replace: true })
  const clear = () => setParams((p) => { FILTER_KEYS.forEach((k) => p.delete(k)); return p }, { replace: true })
  return [f, set, clear]
}

function Kpi({ label, value, delta, children, first }: { label: string; value: string; delta?: ReactNode; children?: ReactNode; first?: boolean }) {
  return (
    <div className={clsx('flex w-[152px] shrink-0 flex-col gap-2 rounded-[18px] border border-line bg-white p-3.5 lg:w-auto lg:rounded-none lg:border-0 lg:px-5 lg:pb-3.5 lg:pt-[18px]',
      !first && 'lg:border-l lg:border-line-soft')}>
      <span className="text-[13px] text-muted">{label}</span>
      <div className="flex flex-col items-start gap-1.5 lg:flex-row lg:items-center lg:gap-2.5">
        <span className="num text-2xl font-semibold tracking-[-0.03em] lg:text-[28px]">{value}</span>
        {delta}
      </div>
      <div className="hidden lg:block">{children}</div>
    </div>
  )
}

export default function Dashboard() {
  const [f, setFilter, clearFilters] = useFilters()
  const [skillType, setSkillType] = useState<'hard' | 'soft'>('hard')
  const [showFilters, setShowFilters] = useState(FILTER_KEYS.some((k) => f[k]))

  const summary = useQuery({ queryKey: ['summary', f], queryFn: () => api.summary(f) })
  const trend = useQuery({ queryKey: ['ai-trend', f], queryFn: () => api.aiTrend(f) })
  const skills = useQuery({ queryKey: ['top-skills', skillType, f], queryFn: () => api.topSkills(skillType, 10, f) })
  const salary = useQuery({ queryKey: ['salary', f], queryFn: () => api.salary(f) })
  const options = useQuery({ queryKey: ['filters'], queryFn: api.filters, staleTime: 300_000 })
  const hist = useQuery({ queryKey: ['salary-hist', f], queryFn: () => api.salaryHistogram(f) })
  const standards = useQuery({ queryKey: ['standards'], queryFn: api.standards, staleTime: 300_000 })

  const s = summary.data
  const weeks = trend.data?.weeks ?? []
  const daily = trend.data?.bucket === 'day'
  const tickEvery = Math.max(1, Math.ceil(weeks.length / 7))
  // groups under 0.05% round to 0.0% → not worth a row
  const groups = (trend.data?.groups ?? []).filter((g) => g.pct >= 0.0005)
  const hiddenGroups = (trend.data?.groups ?? []).length - groups.length
  const groupTotal = groups.reduce((a, g) => a + g.pct, 0) || 1
  const fastest = groups.reduce<string | null>((best, g) => (g.delta_pct != null && (best == null || g.delta_pct > (groups.find((x) => x.group === best)?.delta_pct ?? -1)) ? g.group : best), null)
  const maxSkill = Math.max(0.01, ...(skills.data ?? []).map((x) => x.pct))
  const activeFilters = FILTER_KEYS.filter((k) => f[k]).length
  const maxBand = Math.max(1, ...(hist.data ?? []).map((b) => b.n))
  const histTotal = (hist.data ?? []).reduce((a, b) => a + b.n, 0)

  return (
    <>
      <PageHeader crumbs={['ภาพรวม', 'ตลาดแรงงาน']} title="ตลาดแรงงานสายคอมพิวเตอร์"
        subtitle={<>JobThai และ JobBKK · {s ? (s.window_days >= ALL_DAYS ? 'ข้อมูลทั้งหมด' : `ย้อนหลัง ${s.window_days} วัน`) : 'กำลังโหลด'}{s?.last_scraped_at ? ` · เก็บข้อมูลล่าสุด ${date(s.last_scraped_at)}` : ''}</>}
        actions={
          <>
            <div className="w-full lg:w-auto"><Segmented label="ช่วงเวลา" value={f.days ?? ALL_DAYS} options={DAYS} onChange={(v) => setFilter('days', v)} full size="md" /></div>
            <button type="button" className="btn-outline" aria-expanded={showFilters} onClick={() => setShowFilters((x) => !x)}>
              <Icon name="filter" size={16} />ตัวกรอง{activeFilters ? ` · ${activeFilters}` : ''}
            </button>
          </>
        } />
      <PageBody>
        {showFilters && (
          <div className="card grid grid-cols-2 gap-3 p-4 lg:flex lg:items-end">
            {([['source', 'แหล่งข้อมูล', options.data?.sources], ['province', 'จังหวัด', options.data?.provinces],
              ['work_mode', 'รูปแบบงาน', options.data?.work_modes], ['level', 'ระดับ', options.data?.levels]] as const).map(([key, label, opts]) => (
              <label key={key} className="flex flex-col gap-1.5 text-[13px] text-muted lg:min-w-[160px]">
                {label}
                <select className="input" value={f[key] ?? ''} onChange={(e) => setFilter(key, e.target.value || null)}>
                  <option value="">ทั้งหมด</option>
                  {opts?.map((o) => <option key={o.value} value={o.value}>{o.value} ({num(o.count)})</option>)}
                </select>
              </label>
            ))}
            <button type="button" className="btn-outline col-span-2 lg:ml-auto" onClick={clearFilters} disabled={!activeFilters}>ล้างตัวกรอง</button>
          </div>
        )}

        {summary.isError ? <ErrorState error={summary.error} onRetry={() => summary.refetch()} /> : (
          <section aria-label="ตัวชี้วัดหลัก" className="-mr-4 flex gap-2.5 overflow-x-auto pr-4 no-scrollbar lg:mr-0 lg:grid lg:grid-cols-4 lg:gap-0 lg:overflow-hidden lg:rounded-[14px] lg:border lg:border-line lg:bg-white lg:pr-0">
            {!s ? [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[112px] w-[152px] shrink-0 lg:m-4 lg:w-auto" />) : (
              <>
                <Kpi first label="ตำแหน่งงานทั้งหมด" value={num(s.total_jobs)} delta={<Delta kind="pct" value={change(s.total_jobs, s.total_jobs_prev)} />}>
                  <Sparkline values={weeks.map((w) => w.total)} />
                </Kpi>
                <Kpi label="บริษัทที่ประกาศรับ" value={num(s.companies)}>
                  <p className="text-xs text-muted">เฉลี่ย {s.companies ? (s.total_jobs / s.companies).toFixed(1) : '–'} ตำแหน่ง/บริษัท</p>
                </Kpi>
                <Kpi label="เงินเดือนมัธยฐาน" value={baht(s.median_salary)} delta={<Delta kind="pct" value={change(s.median_salary, s.median_salary_prev)} />}>
                  <p className="text-xs text-muted">ระบุเงินเดือน {pct(s.salary_disclosed_share)}</p>
                </Kpi>
                <Kpi label="หลักสูตรครอบคลุมตลาด" value={pct(s.curriculum_match)}>
                  <Link to="/gap" className="text-xs font-medium text-brand-800 hover:underline">ดูการวิเคราะห์หลักสูตร</Link>
                </Kpi>
              </>
            )}
          </section>
        )}

        {s && (
          <section aria-label="ข้อมูลในคลัง" className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
            {([['ทักษะไม่ซ้ำ', num(s.unique_skills)], ['คู่ งาน–ทักษะ', num(s.job_skill_pairs)],
              ['ทักษะที่มีมาตรฐานรองรับ', s.std_coverage == null ? '–' : `${pct(s.std_coverage, 1)}`], ['รายวิชาในหลักสูตร', num(s.courses)]] as const).map(([k, v]) => (
              <div key={k} className="flex flex-col gap-0.5 rounded-xl border border-line-soft bg-white px-4 py-3">
                <span className="text-xs text-muted">{k}</span>
                <span className="num text-lg font-semibold tracking-[-0.02em]">{v}</span>
              </div>
            ))}
          </section>
        )}

        <div className="grid gap-4 lg:grid-cols-12">
          <section className="dots-bg relative flex flex-col gap-3 overflow-hidden rounded-4xl bg-navy p-5 text-white lg:col-span-8 lg:rounded-2xl lg:p-6 lg:pb-3.5">
            <div className="flex items-start justify-between gap-4">
              <div className="flex flex-col gap-1">
                <span className="text-sm text-navy-text">สัดส่วนงานที่ต้องการทักษะ AI</span>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="num text-[52px] font-semibold leading-[1.1] tracking-[-0.045em] lg:text-[44px]">{s ? pct(s.ai_share, 1) : '–'}</span>
                  {s && s.ai_share_prev != null && s.window_days < ALL_DAYS && <Delta dark kind="pts" value={s.ai_share - s.ai_share_prev} />}
                </div>
                <span className="text-[13px] text-navy-text">{s ? `${num(s.ai_jobs)} จาก ${num(s.total_jobs)} ตำแหน่ง` : ''}</span>
              </div>
            </div>
            {trend.isError ? <ErrorState error={trend.error} /> : (
              <>
                <div className="flex flex-col gap-0.5 text-xs text-navy-text lg:flex-row lg:items-center lg:justify-between">
                  <span className="font-medium">{daily ? 'สัดส่วนงาน AI รายวัน' : 'สัดส่วนงาน AI รายสัปดาห์'}</span>
                  {daily && <span className="text-[11px] opacity-80">ข้อมูลยังไม่ถึง 4 สัปดาห์ จึงแสดงรายวัน · เฉพาะวันที่มีประกาศ ≥ {trend.data?.min_jobs_per_day ?? 20} ตำแหน่ง</span>}
                </div>
                <AreaTrend ariaLabel={daily ? 'สัดส่วนงาน AI รายวัน' : 'สัดส่วนงาน AI รายสัปดาห์'} format={(v) => pct(v, 1)}
                  data={weeks.map((w) => ({ label: daily ? dayMonth(w.week_start) : `สัปดาห์ของ ${dayMonth(w.week_start)}`,
                    value: w.share, note: `งาน AI ${num(w.ai)} จาก ${num(w.total)} ตำแหน่ง` }))}
                  tickLabel={(p, i) => (i % tickEvery === 0 || i === weeks.length - 1 ? (daily ? p.label : dayMonth(weeks[i].week_start)) : null)} />
              </>
            )}
          </section>

          <section className="card flex flex-col gap-4 p-5 lg:col-span-4">
            <div><h2 className="card-title">กลุ่มทักษะ AI</h2><p className="text-[13px] text-muted">% ของตำแหน่งทั้งหมด</p></div>
            <div className="flex h-3 gap-[3px]" aria-hidden="true">
              {groups.map((g, i) => <div key={g.group} className="first:rounded-l-full last:rounded-r-full" style={{ width: `${(g.pct / groupTotal) * 100}%`, background: GROUP_COLORS[i % 4] }} />)}
            </div>
            <ul className="flex flex-col">
              {groups.map((g, i) => (
                <li key={g.group} className="flex min-h-10 items-center gap-2.5 border-b border-line-soft text-sm last:border-0">
                  <span className="h-2 w-2 shrink-0 rounded-sm" style={{ background: GROUP_COLORS[i % 4] }} />
                  <span className="flex-1">{g.group}</span>
                  {g.group === fastest && <span className="rounded-full bg-brand-100 px-2 py-0.5 text-[11px] font-semibold text-brand-800">โตเร็วสุด</span>}
                  <span className="num w-12 text-right font-medium">{pct(g.pct)}</span>
                </li>
              ))}
              {!trend.isLoading && !groups.length && <li className="py-4 text-sm text-muted">ยังไม่มีงานที่ระบุทักษะ AI ในช่วงนี้</li>}
              {hiddenGroups > 0 && <li className="pt-2 text-xs text-muted">อีก {hiddenGroups} กลุ่มต่ำกว่า 0.1%</li>}
            </ul>
            {!!trend.data?.top_ai_skills?.length && (
              <div className="flex flex-wrap gap-1.5">
                {trend.data.top_ai_skills.map((t) => (
                  <span key={t.skill} className="chip border border-line py-0.5 text-xs text-ink-3" title={t.group}>{t.skill} · {num(t.jobs)}</span>
                ))}
              </div>
            )}
            <Link to="/search?q=งานสาย AI" className="mt-auto inline-flex items-center gap-1.5 text-[13px] font-medium text-brand-800 hover:underline">
              ค้นหางานสาย AI<Icon name="arrowRight" size={14} />
            </Link>
          </section>
        </div>

        <div className="grid gap-4 lg:grid-cols-12">
          <section className="card flex flex-col gap-2.5 px-4 py-4 lg:col-span-7 lg:px-[22px] lg:py-5">
            <div className="flex items-center justify-between pb-1">
              <h2 className="card-title">ทักษะที่ตลาดต้องการสูงสุด</h2>
              <Segmented label="ประเภททักษะ" value={skillType} onChange={setSkillType} options={[{ value: 'hard', label: 'Hard skills' }, { value: 'soft', label: 'Soft skills' }]} />
            </div>
            {skills.isError ? <ErrorState error={skills.error} onRetry={() => skills.refetch()} /> : (
              <ol className="flex flex-col">
                {(skills.data ?? []).map((x, i) => (
                  <li key={x.skill} className="grid min-h-[44px] grid-cols-[22px_minmax(0,1fr)_88px_40px] items-center gap-2.5 border-b border-line-soft last:border-0 lg:min-h-8 lg:grid-cols-[28px_minmax(0,1fr)_200px_48px_56px] lg:gap-3 lg:border-0">
                    <span className="num font-mono text-xs text-faint">{String(i + 1).padStart(2, '0')}</span>
                    <span className="flex items-center gap-2 text-[15px] font-medium lg:text-sm">
                      {x.skill}
                      {x.is_ai_skill && <span className="rounded-[5px] bg-navy px-1.5 py-0.5 text-[10px] font-bold text-white">AI</span>}
                    </span>
                    <div className="h-1.5 rounded-full bg-brand-100"><div className="h-1.5 rounded-full bg-brand-700" style={{ width: `${(x.pct / maxSkill) * 100}%` }} /></div>
                    <span className="num text-right text-sm font-medium lg:text-[13px]">{pct(x.pct)}</span>
                    <span className={clsx('num hidden text-right text-xs font-medium lg:block', x.delta_pct == null ? 'text-muted' : x.delta_pct >= 0 ? 'text-good-text' : 'text-maroon')}
                      title={x.delta_pct == null ? 'จำนวนประกาศ' : 'เปลี่ยนจากช่วงก่อนหน้า (จุด %)'}>
                      {x.delta_pct == null ? (x.jobs != null ? num(x.jobs) : '') : `${x.delta_pct >= 0 ? '+' : '−'}${Math.abs(x.delta_pct * 100).toFixed(1)}`}
                    </span>
                  </li>
                ))}
                {skills.isLoading && [0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="my-1.5 h-6" />)}
              </ol>
            )}
          </section>

          <section className="card flex flex-col gap-4 p-4 lg:col-span-5 lg:p-[22px]">
            <div><h2 className="card-title">ช่วงเงินเดือนตามระดับ</h2><p className="text-[13px] text-muted">ไม่รวมงานที่ไม่ระบุเงินเดือน</p></div>
            {salary.data && (
              <div className="grid grid-cols-3 gap-2">
                {salary.data.map((r) => (
                  <div key={r.level} className="flex flex-col rounded-xl border border-line-soft bg-[#FAFAFA] px-3.5 py-3">
                    <span className="text-xs text-muted">{r.level}</span>
                    <span className="num text-xl font-semibold tracking-[-0.02em]">{bahtK(r.median)}</span>
                  </div>
                ))}
              </div>
            )}
            {salary.isError ? <ErrorState error={salary.error} /> : salary.data ? <SalaryRanges rows={salary.data} /> : <Skeleton className="h-40" />}
          </section>
        </div>

        <div className="grid gap-4 lg:grid-cols-12">
          <section className="card flex flex-col gap-4 p-4 lg:col-span-7 lg:px-[22px] lg:py-5">
            <div><h2 className="card-title">การกระจายเงินเดือน</h2>
              <p className="text-[13px] text-muted">จำนวนประกาศตามช่วงเงินเดือนต่อเดือน (ค่ากลางของช่วงที่ประกาศ) · {num(histTotal)} ประกาศที่ระบุเงินเดือน</p></div>
            {hist.isError ? <ErrorState error={hist.error} /> : !hist.data ? <Skeleton className="h-48" /> : (
              <div role="img" aria-label={`ฮิสโตแกรมเงินเดือน: ${hist.data.map((b) => `${b.band} ${b.n} ประกาศ`).join(', ')}`} className="flex h-52 items-end gap-2">
                {hist.data.map((b) => (
                  <div key={b.band} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
                    <span className="num text-[11px] text-muted">{b.n ? num(b.n) : ''}</span>
                    <div className="w-full rounded-t-md bg-brand-700" style={{ height: `${(b.n / maxBand) * 78}%`, minHeight: b.n ? 3 : 0 }} />
                    <span className="num whitespace-nowrap text-[11px] text-ink-3">{b.band}</span>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="card flex flex-col gap-3.5 p-4 lg:col-span-5 lg:p-[22px]">
            <div><h2 className="card-title">ความครอบคลุมตามมาตรฐานทักษะ</h2>
              <p className="text-[13px] text-muted">% ของความต้องการทักษะ (ถ่วงตามจำนวนครั้งที่ปรากฏ) ที่มีมาตรฐานรองรับ</p></div>
            {standards.isError ? <ErrorState error={standards.error} /> : !standards.data ? <Skeleton className="h-48" /> : (
              <ul className="flex flex-col gap-3">
                {standards.data.map((d) => (
                  <li key={d.standard} className="flex flex-col gap-1.5">
                    <div className="flex items-baseline justify-between gap-2 text-sm">
                      <span className={d.is_total ? 'font-semibold' : ''}>{d.label}</span>
                      <span className="num text-[13px]"><span className="font-semibold">{pct(d.weighted_pct, 1)}</span><span className="text-muted"> · {num(d.skills)} ทักษะ</span></span>
                    </div>
                    <div className="h-2 rounded-full bg-brand-100"><div className={clsx('h-2 rounded-full', d.is_total ? 'bg-navy' : 'bg-brand-700')} style={{ width: `${d.weighted_pct * 100}%` }} /></div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </PageBody>
    </>
  )
}