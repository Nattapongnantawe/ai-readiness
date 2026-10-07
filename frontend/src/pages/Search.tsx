import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Icon } from '../components/icons'
import { SearchBox } from '../components/SearchBox'
import { PageBody, PageHeader } from '../components/layout/PageHeader'
import { CompanyLogo } from '../components/ui/CompanyLogo'
import { Ring } from '../components/ui/Ring'
import { Empty, ErrorState, Skeleton } from '../components/ui/States'
import { api } from '../lib/api'
import { baht, dayMonth, num, salaryRange } from '../lib/format'
import type { FilterOptions, JobCard, Level, SearchFilters, WorkMode } from '../lib/types'

const EXAMPLES = ['ซ่อมบำรุงระบบไฟฟ้าในโรงงาน', 'data engineer ETL pipeline', 'พัฒนาเว็บ frontend react', 'ดูแลระบบเครือข่าย']

function toggle<T>(list: T[] | undefined, v: T): T[] {
  const l = list ?? []
  return l.includes(v) ? l.filter((x) => x !== v) : [...l, v]
}

function FilterFields({ filters, setFilters, options, variant }: {
  filters: SearchFilters; setFilters: (f: SearchFilters) => void; options?: FilterOptions; variant: 'rail' | 'sheet'
}) {
  const groups: { key: 'level' | 'work_mode' | 'province' | 'source'; title: string; opts: { value: string; count: number }[] }[] = [
    { key: 'level', title: 'ระดับประสบการณ์', opts: options?.levels ?? [] },
    { key: 'work_mode', title: 'รูปแบบงาน', opts: options?.work_modes ?? [] },
    { key: 'province', title: 'จังหวัด', opts: (options?.provinces ?? []).slice(0, 6) },
    { key: 'source', title: 'แหล่งข้อมูล', opts: options?.sources ?? [] },
  ]
  return (
    <>
      {groups.map((g) => (
        <fieldset key={g.key} className="flex flex-col gap-0.5">
          <legend className="pb-2 text-xs font-semibold text-muted">{g.title}</legend>
          <div className={clsx(variant === 'sheet' && 'flex flex-wrap gap-2')}>
            {g.opts.map((o) => {
              const on = ((filters[g.key] as string[] | undefined) ?? []).includes(o.value)
              const flip = () => setFilters({ ...filters, [g.key]: toggle(filters[g.key] as string[] | undefined, o.value) } as SearchFilters)
              return variant === 'rail' ? (
                <label key={o.value} className="flex min-h-8 items-center gap-2.5 text-sm">
                  <input type="checkbox" checked={on} onChange={flip} className="h-4 w-4 accent-brand-700" />
                  <span className="flex-1">{o.value}</span>
                  <span className="num text-xs text-faint">{num(o.count)}</span>
                </label>
              ) : (
                <button key={o.value} type="button" aria-pressed={on} onClick={flip}
                  className={clsx('flex min-h-11 items-center gap-1.5 rounded-xl px-4 text-[15px]',
                    on ? 'border-[1.5px] border-brand-700 bg-brand-100 font-semibold text-brand-800' : 'border border-line bg-white')}>
                  {o.value}<span className={clsx('num text-xs', on ? 'text-brand-800' : 'text-faint')}>{num(o.count)}</span>
                </button>
              )
            })}
          </div>
        </fieldset>
      ))}
      <div className="flex flex-col gap-2">
        <div className="flex justify-between text-xs font-semibold text-muted">
          <label htmlFor={`sal-${variant}`}>เงินเดือนขั้นต่ำ</label>
          <span className="num text-ink">{filters.min_salary ? baht(filters.min_salary) : 'ไม่กำหนด'}</span>
        </div>
        <input id={`sal-${variant}`} type="range" min={0} max={100000} step={5000} value={filters.min_salary ?? 0}
          onChange={(e) => setFilters({ ...filters, min_salary: Number(e.target.value) || null })} className="w-full accent-brand-700" />
      </div>
    </>
  )
}

function ResultRow({ r, query, first }: { r: JobCard; query: string; first: boolean }) {
  return (
    <Link to={`/jobs/${r.job_id}`} state={{ similarity: r.similarity, query }}
      className={clsx('flex flex-col gap-3 rounded-[20px] border border-line bg-white p-4 lg:grid lg:grid-cols-[44px_minmax(0,1fr)_150px_20px] lg:items-center lg:gap-4 lg:rounded-none lg:border-0 lg:px-[18px] lg:hover:bg-brand-50',
        !first && 'lg:border-t lg:border-line-soft')}>
      <CompanyLogo src={r.company_logo} name={r.company} className="hidden lg:flex" />
      <div className="flex min-w-0 flex-col gap-2">
        <div className="flex items-start justify-between gap-3 lg:block">
          <div className="flex flex-col gap-0.5 lg:flex-row lg:items-baseline lg:gap-2.5">
            <span className="text-[17px] font-semibold leading-snug tracking-[-0.015em] lg:text-[15px]">{r.title}</span>
            <span className="flex items-center gap-1.5 text-sm text-muted lg:text-[13px]">
              <CompanyLogo src={r.company_logo} name={r.company} size={20} className="rounded-md lg:hidden" />
              <span>{r.company ?? 'ไม่ระบุบริษัท'} · {r.province ?? 'ไม่ระบุจังหวัด'}</span>
            </span>
          </div>
          {r.similarity != null && (
            <div className="lg:hidden">
              <Ring value={r.similarity} size={48} stroke={5} label={`ความใกล้เคียง ${Math.round(r.similarity * 100)}%`}>
                <span className="num text-xs font-semibold">{Math.round(r.similarity * 100)}</span>
              </Ring>
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="chip num bg-brand-100 font-semibold text-brand-800 lg:text-xs">{salaryRange(r.salary_min, r.salary_max, true)}</span>
          {r.level && <span className="chip bg-canvas text-ink-3 lg:text-xs">{r.level}</span>}
          {r.work_mode && <span className="chip bg-canvas text-ink-3 lg:text-xs">{r.work_mode}</span>}
          {!!r.similar_postings && <span className="chip border border-dashed border-line text-ink-3 lg:text-xs" title="ประกาศชื่อเดียวกันจากบริษัทเดียวกัน (เช่น คนละสาขา) รวมไว้ในรายการนี้">+{r.similar_postings} ประกาศคล้ายกัน</span>}
          <span className="hidden h-3.5 w-px bg-line lg:block" />
          <span className="flex w-full flex-wrap gap-1.5 border-t border-line-soft pt-3 lg:w-auto lg:border-0 lg:pt-0">
            {r.top_skills.slice(0, 3).map((k) => <span key={k} className="chip border border-line py-0.5 text-ink-3 lg:text-xs">{k}</span>)}
          </span>
        </div>
      </div>
      {r.similarity != null ? (
        <div className="hidden flex-col items-end gap-1.5 lg:flex">
          <span className="num text-[15px] font-semibold">{Math.round(r.similarity * 100)}%</span>
          <div className="h-1 w-[110px] rounded-full bg-brand-100"><div className="h-1 rounded-full bg-brand-700" style={{ width: `${r.similarity * 100}%` }} /></div>
          <span className="text-[11px] text-faint">ความใกล้เคียง</span>
        </div>
      ) : (
        <div className="hidden flex-col items-end gap-0.5 lg:flex">
          <span className="num text-sm font-medium">{dayMonth(r.posted_at)}</span>
          <span className="text-[11px] text-faint">วันที่ประกาศ</span>
        </div>
      )}
      <Icon name="chevronRight" className="hidden text-[#A1A1AA] lg:block" />
    </Link>
  )
}

function Pager({ page, pages, onPage }: { page: number; pages: number; onPage: (p: number) => void }) {
  if (pages <= 1) return null
  const nums = Array.from(new Set([1, page - 1, page, page + 1, pages].filter((p) => p >= 1 && p <= pages))).sort((a, b) => a - b)
  const btn = 'flex h-10 min-w-10 items-center justify-center rounded-xl px-3 text-sm'
  return (
    <nav aria-label="เลือกหน้า" className="flex flex-wrap items-center justify-center gap-1.5 pt-2">
      <button type="button" className={clsx(btn, 'border border-line bg-white disabled:opacity-40')} disabled={page <= 1} onClick={() => onPage(page - 1)}>ก่อนหน้า</button>
      {nums.map((n, i) => (
        <span key={n} className="flex items-center gap-1.5">
          {i > 0 && n - nums[i - 1] > 1 && <span className="px-1 text-faint">…</span>}
          <button type="button" aria-current={n === page ? 'page' : undefined} onClick={() => onPage(n)}
            className={clsx(btn, 'num', n === page ? 'bg-ink font-semibold text-white' : 'border border-line bg-white hover:border-brand-300')}>{n}</button>
        </span>
      ))}
      <button type="button" className={clsx(btn, 'border border-line bg-white disabled:opacity-40')} disabled={page >= pages} onClick={() => onPage(page + 1)}>ถัดไป</button>
    </nav>
  )
}

const PAGE_SIZE = 20

export default function Search() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const page = Math.max(1, Number(params.get('p')) || 1)
  const [text, setText] = useState(q)
  const [filters, setFiltersRaw] = useState<SearchFilters>({})
  const go = (query: string, p = 1) => setParams({ ...(query ? { q: query } : {}), ...(p > 1 ? { p: String(p) } : {}) })
  const setPage = (p: number) => { go(q, p); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  const setFilters = (f: SearchFilters) => { setFiltersRaw(f); if (page > 1) go(q) }
  const [sheet, setSheet] = useState(false)
  useEffect(() => setText(q), [q])

  const options = useQuery({ queryKey: ['filters'], queryFn: api.filters, staleTime: 300_000 })
  const results = useQuery({ queryKey: ['search', q, filters, page], queryFn: () => api.search(q, filters, page, PAGE_SIZE), placeholderData: (prev) => prev })
  const related = useQuery({ queryKey: ['related', q], queryFn: () => api.relatedSkills(q, 10), enabled: q.trim().length >= 2, staleTime: 300_000 })

  const total = results.data ? (results.data.total ?? results.data.results.length) : 0
  const pages = Math.max(1, Math.ceil(total / (results.data?.page_size ?? PAGE_SIZE)))
  // the backend pages through the closest max_results jobs; hitting that cap means more exist
  const atCap = !!results.data?.capped
  const browse = results.data?.mode === 'browse' || !q
  const submit = (value = text) => {
    const v = value.trim()
    if (v.length >= 2 || v.length === 0) go(v)
  }
  const active: { label: string; clear: () => void }[] = [
    ...(filters.level ?? []).map((l) => ({ label: l, clear: () => setFilters({ ...filters, level: toggle<Level>(filters.level, l) }) })),
    ...(filters.work_mode ?? []).map((w) => ({ label: w, clear: () => setFilters({ ...filters, work_mode: toggle<WorkMode>(filters.work_mode, w) }) })),
    ...(filters.province ?? []).map((p) => ({ label: p, clear: () => setFilters({ ...filters, province: toggle(filters.province, p) }) })),
    ...(filters.source ?? []).map((p) => ({ label: p, clear: () => setFilters({ ...filters, source: toggle(filters.source, p) }) })),
    ...(filters.min_salary ? [{ label: `≥ ${baht(filters.min_salary)}`, clear: () => setFilters({ ...filters, min_salary: null }) }] : []),
  ]

  return (
    <>
      <PageHeader crumbs={['ค้นหางาน', 'Semantic Search']} title="ค้นหางาน"
        subtitle="พิมพ์ตำแหน่ง ทักษะ หรือประโยคธรรมดา ระบบเทียบความหมายกับชื่อตำแหน่ง รายละเอียดงาน และคุณสมบัติของทุกประกาศ ไม่ต้องตรงคำ" />
      <PageBody>
        <div className="grid items-start gap-6 lg:grid-cols-[250px_minmax(0,1fr)]">
          <aside aria-label="ตัวกรอง" className="hidden flex-col gap-5 rounded-[14px] border border-line p-[18px] lg:flex">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold">ตัวกรอง</span>
              <button type="button" className="text-[13px] text-brand-800 hover:underline disabled:text-faint" disabled={!active.length} onClick={() => setFilters({})}>ล้างทั้งหมด</button>
            </div>
            <FilterFields filters={filters} setFilters={setFilters} options={options.data} variant="rail" />
          </aside>

          <div className="flex min-w-0 flex-col gap-3.5 lg:gap-4">
            <SearchBox value={text} onChange={setText} onSubmit={submit} onClear={() => go('')} />

            <div className="-mr-4 flex gap-2 overflow-x-auto pr-4 no-scrollbar lg:mr-0 lg:flex-wrap lg:pr-0">
              <button type="button" onClick={() => setSheet(true)} className="flex min-h-10 shrink-0 items-center gap-1.5 rounded-full bg-ink px-3.5 text-sm font-medium text-white lg:hidden">
                <Icon name="filter" size={15} />ตัวกรอง{active.length ? <span className="flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-white text-[11px] font-bold text-ink">{active.length}</span> : null}
              </button>
              {active.map((a) => (
                <button key={a.label} type="button" onClick={a.clear} aria-label={`ลบตัวกรอง ${a.label}`} className="flex min-h-10 shrink-0 items-center gap-1.5 rounded-full bg-brand-100 pl-3.5 pr-3 text-sm font-medium text-brand-800 lg:min-h-8">
                  {a.label}<Icon name="close" size={13} strokeWidth={2.6} />
                </button>
              ))}
              {!active.length && !q && EXAMPLES.map((e) => (
                <button key={e} type="button" onClick={() => { setText(e); submit(e) }} className="hidden min-h-8 shrink-0 rounded-full border border-line bg-[#FAFAFA] px-3 text-[13px] text-ink-3 hover:border-brand-300 lg:block">{e}</button>
              ))}
            </div>

            {results.isError ? <ErrorState error={results.error} onRetry={() => results.refetch()} /> : (
              <>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted">{browse && <>งานทั้งหมด </>}<strong className="text-ink">{results.data ? num(total) : '…'}</strong>{atCap ? '+' : ''} {browse ? 'ตำแหน่ง · เรียงตามวันที่ประกาศล่าสุด' : 'ผลลัพธ์ · เรียงตามความใกล้เคียง'}
                    {pages > 1 && <> · หน้า <span className="num">{page}/{pages}</span></>}</span>
                  {results.data && !browse && (
                    <span className="num flex items-center gap-1.5 rounded-full bg-good-soft px-2 py-0.5 font-mono text-xs text-good-text" title="เวลาค้นในฐานข้อมูล / เวลารวม">
                      <span className="h-1.5 w-1.5 rounded-full bg-good" />DB {results.data.took_ms.db} ms · รวม {Math.round(results.data.took_ms.db + results.data.took_ms.embed)} ms
                    </span>
                  )}
                </div>
                {!browse && !!related.data?.length && (
                  <div className="flex flex-wrap items-center gap-1.5 text-[13px]">
                    <span className="text-muted">ทักษะที่ใกล้ความหมาย:</span>
                    {related.data.map((r) => (
                      <span key={r.skill} className="chip border border-line bg-white py-0.5 text-xs text-ink-3" title={`ความคล้าย ${r.similarity.toFixed(2)}`}>{r.skill}</span>
                    ))}
                  </div>
                )}
                {results.isLoading ? <div className="flex flex-col gap-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-28" />)}</div>
                  : results.data!.results.length === 0 ? <Empty title={browse ? 'ไม่มีงานที่ตรงกับตัวกรอง' : 'ไม่พบงานที่ตรงกับคำค้นและตัวกรอง'}>ลองลบตัวกรองบางตัว{browse ? '' : ' หรือพิมพ์คำค้นให้กว้างขึ้น'}</Empty>
                  : (
                    <div className="flex flex-col gap-3 lg:gap-0 lg:overflow-hidden lg:rounded-[14px] lg:border lg:border-line">
                      {results.data!.results.map((r, i) => <ResultRow key={r.job_id} r={r} query={q} first={i === 0} />)}
                    </div>
                  )}
                {results.data && <Pager page={page} pages={pages} onPage={setPage} />}
                {atCap && page === pages && <p className="text-center text-xs text-muted">แสดง {num(results.data!.max_results)} งานที่ใกล้ความหมายที่สุด ถ้ายังไม่เจอ ลองพิมพ์คำค้นให้เฉพาะขึ้นหรือใช้ตัวกรอง</p>}
              </>
            )}
          </div>
        </div>
      </PageBody>

      {sheet && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="ตัวกรอง">
          <button type="button" aria-label="ปิดตัวกรอง" className="absolute inset-0 bg-ink/45" onClick={() => setSheet(false)} />
          <div className="absolute inset-x-0 bottom-0 flex max-h-[88vh] flex-col gap-5 overflow-y-auto rounded-t-[26px] bg-white px-5 pt-2 shadow-[0_-12px_40px_rgba(0,0,0,0.18)]"
            style={{ paddingBottom: 'max(env(safe-area-inset-bottom), 20px)' }}>
            <div className="mx-auto h-[5px] w-10 rounded-full bg-[#D4D4D8]" />
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold tracking-[-0.02em]">ตัวกรอง</h2>
              <button type="button" className="min-h-11 text-[15px] font-medium text-brand-800" onClick={() => setFilters({})}>ล้างทั้งหมด</button>
            </div>
            <FilterFields filters={filters} setFilters={setFilters} options={options.data} variant="sheet" />
            <button type="button" onClick={() => setSheet(false)} className="flex min-h-[54px] items-center justify-center rounded-[15px] bg-ink text-base font-semibold text-white">
              {results.data ? `แสดง ${num(total)} ${browse ? 'ตำแหน่ง' : 'ผลลัพธ์'}` : 'ใช้ตัวกรอง'}
            </button>
          </div>
        </div>
      )}
    </>
  )
}