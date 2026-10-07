import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useEffect, useState } from 'react'
import { ScheduleTimeline } from '../../components/charts/ScheduleTimeline'
import { Icon } from '../../components/icons'
import { PageBody, PageHeader } from '../../components/layout/PageHeader'
import { RUN_STATUS, RunDetail, isActive } from '../../components/RunDetail'
import { Segmented } from '../../components/ui/Segmented'
import { ErrorState, Skeleton } from '../../components/ui/States'
import { api } from '../../lib/api'
import { duration, num, sourceInitials, sourceLabel, when } from '../../lib/format'
import type { Run, ScheduleInput, Source } from '../../lib/types'

const statusOf = (r: Run) => RUN_STATUS[r.status] ?? RUN_STATUS.failed

function SourceCard({ s, busy, visible, onStarted }: { s: Source; busy: boolean; visible: boolean; onStarted: (id: number) => void }) {
  const qc = useQueryClient()
  const [form, setForm] = useState<ScheduleInput>({ mode: s.mode, every_hours: s.every_hours ?? 24, daily_at: s.daily_at ?? '02:00', enabled: s.enabled })
  useEffect(() => setForm({ mode: s.mode, every_hours: s.every_hours ?? 24, daily_at: s.daily_at ?? '02:00', enabled: s.enabled }), [s.mode, s.every_hours, s.daily_at, s.enabled])
  const refresh = () => { qc.invalidateQueries({ queryKey: ['sources'] }); qc.invalidateQueries({ queryKey: ['runs'] }); qc.invalidateQueries({ queryKey: ['crawler-status'] }) }
  const save = useMutation({ mutationFn: () => api.updateSchedule(s.source, form), onSuccess: refresh })
  const run = useMutation({ mutationFn: () => api.runNow(s.source), onSuccess: (d) => { refresh(); onStarted(d.run_id) } })
  const r = s.last_run
  const running = isActive(r)
  const dirty = form.mode !== s.mode || form.enabled !== s.enabled || (form.mode === 'interval' ? form.every_hours !== s.every_hours : form.daily_at !== s.daily_at)
  const error = (save.error ?? run.error) as Error | null
  const notReady = (s.problems?.length ?? 0) > 0

  return (
    <section className={clsx('flex-col gap-4 rounded-[22px] border bg-white p-5 lg:flex lg:rounded-2xl', visible ? 'flex' : 'hidden', running ? 'border-brand-300' : 'border-line')}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className={clsx('flex h-10 w-10 items-center justify-center rounded-[11px] text-[13px] font-bold', running ? 'bg-brand-700 text-white' : 'border border-[#EDEDF0] bg-canvas text-ink-3')}>{sourceInitials(s.source)}</div>
          <div className="flex flex-col">
            <h2 className="text-base font-semibold">{s.label || sourceLabel(s.source)}</h2>
            {r ? (
              <span className="flex items-center gap-1.5 text-xs text-muted">
                <span className={clsx('h-1.5 w-1.5 rounded-full', statusOf(r).dot, running && 'animate-pulse')} />
                {running ? `กำลังรัน · เริ่ม ${when(r.started_at)}` : `${statusOf(r).label} · ${when(r.started_at)} · ${duration(r.started_at, r.finished_at)}`}
              </span>
            ) : <span className="text-xs text-muted">ยังไม่เคยรัน</span>}
          </div>
        </div>
        <label className="flex min-h-10 items-center gap-2.5 text-[13px] text-ink-3">รันอัตโนมัติ
          <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} className="h-[18px] w-[18px] accent-brand-700" />
        </label>
      </div>

      {r && !running && (
        <dl className="grid grid-cols-3 rounded-xl border border-line-soft">
          {[['เจอในหน้ารายการ', r.found], ['งานใหม่เข้าฐาน', r.inserted], ['ข้าม (เคยเก็บ)', r.duplicated]].map(([k, v], i) => (
            <div key={k as string} className={clsx('flex flex-col gap-0.5 px-3.5 py-3', i > 0 && 'border-l border-line-soft')}>
              <dt className="text-xs text-muted">{k}</dt>
              <dd className={clsx('num text-xl font-semibold tracking-[-0.02em]', i === 1 && 'text-brand-800')}>{num(v as number)}</dd>
            </div>
          ))}
        </dl>
      )}

      {!!s.categories?.length && (
        <div className="flex flex-col gap-1 text-xs text-muted">
          <span className="font-semibold">หน้ารายการที่ดึง ({s.categories.length})</span>
          {s.categories.map((c) => <span key={c} className="truncate font-mono text-[11px]" title={c}>{c}</span>)}
        </div>
      )}

      <fieldset className="flex flex-col gap-2">
        <legend className="pb-2 text-xs font-semibold text-muted">รอบเวลา</legend>
        <Segmented full size="md" label="รูปแบบรอบเวลา" value={form.mode} onChange={(mode) => setForm({ ...form, mode })}
          options={[{ value: 'daily', label: 'รายวัน' }, { value: 'interval', label: 'ทุก N ชั่วโมง' }]} />
        {form.mode === 'interval' ? (
          <label className="flex min-h-[52px] items-center justify-between gap-3 rounded-xl border border-line px-3.5 text-sm">ทุก ๆ
            <span className="flex items-center gap-2">
              <input type="number" min={1} max={168} value={form.every_hours ?? ''} onChange={(e) => setForm({ ...form, every_hours: Number(e.target.value) || null })}
                className="input num h-9 w-20 text-center text-ink" aria-label="จำนวนชั่วโมง" />ชั่วโมง
            </span>
          </label>
        ) : (
          <label className="flex min-h-[52px] items-center justify-between gap-3 rounded-xl border border-line px-3.5 text-sm">ทุกวัน เวลา
            <input type="time" value={form.daily_at ?? '02:00'} onChange={(e) => setForm({ ...form, daily_at: e.target.value })} className="input num h-9 w-28 text-ink" aria-label="เวลา" />
          </label>
        )}
      </fieldset>

      {error && <p role="alert" className="text-[13px] text-maroon">{error.message}</p>}
      <div className="mt-auto flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <span className="text-[13px] text-muted">
          รันถัดไป <strong className="text-ink">{s.enabled && s.next_run_at ? when(s.next_run_at) : 'ปิดอยู่'}</strong>
        </span>
        <div className="grid grid-cols-2 gap-2 lg:flex">
          <button type="button" className="btn h-11 border border-line bg-white hover:bg-canvas lg:h-10"
            disabled={!dirty || save.isPending} onClick={() => save.mutate()}>{save.isPending ? 'กำลังบันทึก…' : 'บันทึก'}</button>
          <button type="button" className="btn h-11 bg-brand-700 text-white hover:bg-brand-800 lg:h-10"
            disabled={busy || notReady || run.isPending} title={notReady ? s.problems!.join('\n') : busy ? 'มีรอบอื่นกำลังรันอยู่' : ''} onClick={() => run.mutate()}>
            {running ? 'กำลังรันอยู่…' : <><Icon name="play" size={12} />รันตอนนี้</>}
          </button>
        </div>
      </div>
    </section>
  )
}

export default function Crawler() {
  const qc = useQueryClient()
  const status = useQuery({ queryKey: ['crawler-status'], queryFn: api.crawlerStatus, refetchInterval: (q) => (q.state.data?.active_run_id ? 3000 : 15000) })
  const busy = !!status.data?.active_run_id
  const sources = useQuery({ queryKey: ['sources'], queryFn: api.sources, refetchInterval: busy ? 4000 : 20000 })
  const runs = useQuery({ queryKey: ['runs'], queryFn: () => api.runs(20), refetchInterval: busy ? 4000 : 20000 })
  const pipe = useQuery({ queryKey: ['pipeline'], queryFn: api.pipeline, refetchInterval: busy ? 10000 : 60000 })
  const [picked, setPicked] = useState<number | null>(null)
  const [tab, setTab] = useState<string | null>(null)
  const refreshAll = () => ['crawler-status', 'sources', 'runs', 'pipeline'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }))
  const processRun = useMutation({ mutationFn: api.processPending, onSuccess: (d) => { setPicked(d.run_id); refreshAll() } })

  // when a run finishes, refresh the counters on this page
  const [lastActive, setLastActive] = useState<number | null>(null)
  useEffect(() => {
    const a = status.data?.active_run_id ?? null
    if (lastActive && !a) refreshAll()
    setLastActive(a)
  }, [status.data?.active_run_id]) // eslint-disable-line react-hooks/exhaustive-deps

  const p = pipe.data
  const counts = p ? [
    ['Module 1', 'ดึงประกาศ', p.jobs, p.jobs, 'งาน'],
    ['Module 2', 'สกัดทักษะ (Gemini)', p.extracted, p.jobs, 'งาน'],
    ['Module 3', 'Embedding ประกาศ', p.jobs_embedded, p.jobs, 'งาน'],
    ['Module 3', 'จับคู่มาตรฐาน', p.skills_std_mapped, p.skills, 'ทักษะ'],
    ['Module 3', 'เชื่อมหลักสูตร', p.course_links, null, 'คู่ วิชา–ทักษะ'],
  ] as const : []
  const pendingExtract = p ? Math.max(0, p.jobs - p.extracted) : 0
  const pendingEmbed = p ? Math.max(0, p.jobs - p.jobs_embedded) : 0
  const list = sources.data ?? []
  const selected = tab ?? list.find((s) => isActive(s.last_run))?.source ?? list[0]?.source
  const shownRun = status.data?.active_run_id ?? picked ?? runs.data?.[0]?.id ?? null
  const problems = [...new Set([...(status.data?.process_problems ?? []), ...list.flatMap((s) => s.problems ?? [])])]

  return (
    <>
      <PageHeader crumbs={['ผู้ดูแลระบบ', 'Crawler']} title="ควบคุมการดึงข้อมูล"
        subtitle="ดึงประกาศ → นำเข้า → สกัดทักษะ → embedding → จับคู่มาตรฐานและหลักสูตร อัตโนมัติตามรอบเวลา"
        topRight={<span className="hidden text-xs text-muted xl:inline">Asia/Bangkok · ตรวจ robots.txt · รอบอัตโนมัติหน่วง {status.data?.auto_delay ?? '12–15 วินาที/request'}</span>} />
      <PageBody>
        {problems.length > 0 && (
          <section role="alert" className="flex flex-col gap-1.5 rounded-2xl border border-warn/40 bg-warn-soft px-4 py-3.5 text-[13px] text-warn-text">
            <span className="flex items-center gap-2 font-semibold"><Icon name="alert" size={16} />ยังรันไม่ได้ — ตั้งค่า path ใน backend/.env แล้วรีสตาร์ต API</span>
            <ul className="list-disc pl-6">{problems.map((x) => <li key={x}>{x}</li>)}</ul>
          </section>
        )}

        <section className="card flex flex-col gap-3.5 p-4 lg:px-[22px] lg:py-5">
          <div className="flex flex-col justify-between gap-1 lg:flex-row lg:items-baseline">
            <h2 className="card-title">สถานะข้อมูลในฐาน jobmarket</h2>
            {p && <span className="text-xs text-muted">เก็บข้อมูล {when(p.first_scraped_at)} – {when(p.last_scraped_at)} · {p.by_source.map((b) => `${sourceLabel(b.source)} ${num(b.jobs)}`).join(' · ')}</span>}
          </div>
          {pipe.isError ? <ErrorState error={pipe.error} /> : !p ? <Skeleton className="h-24" /> : (
            <ol className="grid grid-cols-2 gap-2.5 lg:grid-cols-5">
              {counts.map(([mod, label, done, total, unit], i) => (
                <li key={label} className="flex flex-col gap-1.5 rounded-xl border border-line-soft bg-[#FAFAFA] p-3.5">
                  <span className="flex items-center gap-2 text-xs font-semibold text-brand-800">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-brand-700 text-[11px] text-white">{i + 1}</span>{mod}
                  </span>
                  <span className="text-sm font-medium">{label}</span>
                  <span className="num text-lg font-semibold tracking-[-0.02em]">{num(done)}{total != null && <span className="text-sm font-normal text-muted"> / {num(total)}</span>}</span>
                  <span className="text-xs text-muted">{unit}</span>
                  {total != null && <div className="h-1.5 rounded-full bg-brand-100"><div className="h-1.5 rounded-full bg-brand-700" style={{ width: `${total ? Math.min(100, (done / total) * 100) : 0}%` }} /></div>}
                </li>
              ))}
            </ol>
          )}
          <div className="flex flex-col gap-2 border-t border-line-soft pt-3.5 lg:flex-row lg:items-center lg:justify-between">
            <span className="text-[13px] text-muted">
              {pendingExtract || pendingEmbed
                ? <>ค้างอยู่: รอสกัดทักษะ <strong className="text-ink">{num(pendingExtract)}</strong> งาน · รอ embedding <strong className="text-ink">{num(pendingEmbed)}</strong> งาน</>
                : 'ไม่มีงานค้าง ทุกประกาศผ่านครบทุกขั้นแล้ว'}
              {status.data && <> · Gemini สูงสุด {num(status.data.extract_limit_per_run)} งาน/รอบ</>}
            </span>
            <button type="button" className="btn-outline h-10" disabled={busy || processRun.isPending || (status.data?.process_problems.length ?? 0) > 0}
              title="นำเข้างานที่ดึงไว้แล้ว → สกัดทักษะ → embedding → จับคู่ (ไม่ดึงประกาศใหม่)" onClick={() => processRun.mutate()}>
              <Icon name="refresh" size={15} />ประมวลผลงานที่ค้าง
            </button>
          </div>
          {processRun.error && <p role="alert" className="text-[13px] text-maroon">{(processRun.error as Error).message}</p>}
        </section>

        {shownRun != null && (
          <section className={clsx('card p-4 lg:px-[22px] lg:py-5', busy && 'border-brand-300')}>
            <RunDetail runId={shownRun} />
          </section>
        )}

        {sources.isError ? <ErrorState error={sources.error} onRetry={() => sources.refetch()} /> : !sources.data ? <Skeleton className="h-72" /> : (
          <>
            <section className="card hidden flex-col gap-2.5 px-[22px] pb-3.5 pt-5 lg:flex">
              <div className="flex items-center justify-between">
                <h2 className="card-title">ตารางรันวันนี้</h2>
                <div className="flex gap-3.5 text-xs text-muted">
                  <span className="flex items-center gap-1.5"><span className="h-2 w-3.5 rounded-[3px] border border-good bg-[#BBF7D0]" />สำเร็จ</span>
                  <span className="flex items-center gap-1.5"><span className="h-2 w-3.5 rounded-[3px] border border-warn bg-warn-soft" />มีข้อสังเกต</span>
                  <span className="flex items-center gap-1.5"><span className="h-2 w-3.5 rounded-[3px] bg-brand-700" />กำลังรัน</span>
                  <span className="flex items-center gap-1.5"><span className="h-2 w-3.5 rounded-[3px] border-[1.5px] border-dashed border-brand-500" />ตามตาราง</span>
                </div>
              </div>
              <ScheduleTimeline sources={list} runs={runs.data ?? []} />
            </section>

            <div role="tablist" aria-label="แหล่งข้อมูล" className="grid rounded-xl bg-[#E9E9ED] p-[3px] lg:hidden" style={{ gridTemplateColumns: `repeat(${list.length}, minmax(0, 1fr))` }}>
              {list.map((s) => (
                <button key={s.source} type="button" role="tab" aria-selected={s.source === selected} onClick={() => setTab(s.source)}
                  className={clsx('flex min-h-10 items-center justify-center gap-2 rounded-[9px] text-[15px]', s.source === selected ? 'bg-white font-semibold shadow-seg' : 'text-muted')}>
                  <span className={clsx('h-[7px] w-[7px] rounded-full', s.last_run ? statusOf(s.last_run).dot : 'bg-line')} />
                  {sourceLabel(s.source)}
                </button>
              ))}
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              {list.map((s) => <SourceCard key={s.source} s={s} busy={busy} visible={s.source === selected} onStarted={setPicked} />)}
            </div>
          </>
        )}

        <section className="card overflow-hidden">
          <div className="flex items-center justify-between px-4 py-4 lg:px-[22px]"><h2 className="card-title">ประวัติการรัน</h2><span className="text-xs text-muted">คลิกแถวเพื่อดูขั้นตอนและ log</span></div>
          <div className="hidden grid-cols-[150px_110px_96px_150px_repeat(3,72px)_minmax(0,1fr)] gap-3 border-y border-line-soft bg-[#FAFAFA] px-[22px] py-2.5 text-xs font-medium text-muted lg:grid">
            <span>เวลาเริ่ม</span><span>แหล่ง</span><span>ประเภท</span><span>สถานะ</span><span className="text-right">เจอ</span><span className="text-right">ใหม่</span><span className="text-right">ข้าม</span><span>ใช้เวลา / หมายเหตุ</span>
          </div>
          <ul>
            {(runs.data ?? []).map((r) => {
              const st = statusOf(r)
              return (
                <li key={r.id}>
                  <button type="button" onClick={() => { setPicked(r.id); window.scrollTo({ top: 0, behavior: 'smooth' }) }} aria-current={r.id === shownRun}
                    className={clsx('flex min-h-[58px] w-full items-center gap-3 border-t border-line-soft px-4 text-left text-sm hover:bg-brand-50 lg:grid lg:min-h-11 lg:grid-cols-[150px_110px_96px_150px_repeat(3,72px)_minmax(0,1fr)] lg:border-t-0 lg:border-b lg:border-[#F4F4F6] lg:px-[22px]',
                      r.id === shownRun && 'bg-brand-50')}>
                    <span className={clsx('h-2 w-2 shrink-0 rounded-full lg:hidden', st.dot)} />
                    <div className="flex flex-1 flex-col lg:hidden">
                      <span className="font-medium">{sourceLabel(r.source)} · {st.label}</span>
                      <span className="text-[13px] text-muted">{when(r.started_at)} · {r.trigger === 'manual' ? 'สั่งเอง' : 'ตามรอบ'}</span>
                    </div>
                    <span className="num text-[15px] font-semibold lg:hidden">{r.status === 'failed' ? '–' : `+${r.inserted}`}</span>
                    <span className="num hidden text-[13px] text-ink-3 lg:block">{when(r.started_at)}</span>
                    <span className="hidden font-medium lg:block">{sourceLabel(r.source)}</span>
                    <span className="hidden text-[13px] text-muted lg:block">{r.trigger === 'manual' ? 'สั่งเอง' : 'ตามรอบ'}</span>
                    <span className="hidden lg:block"><span className={clsx('inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium', st.cls)}>
                      <span className={clsx('h-1.5 w-1.5 rounded-full', st.dot)} />{st.label}</span></span>
                    <span className="num hidden text-right lg:block">{num(r.found)}</span>
                    <span className="num hidden text-right lg:block">{num(r.inserted)}</span>
                    <span className="num hidden text-right lg:block">{num(r.duplicated)}</span>
                    <span className="hidden truncate text-[13px] text-muted lg:block">{r.error_message ?? (isActive(r) ? '—' : duration(r.started_at, r.finished_at))}</span>
                  </button>
                </li>
              )
            })}
            {runs.data?.length === 0 && <li className="px-5 py-6 text-sm text-muted">ยังไม่มีประวัติการรัน กด “รันตอนนี้” เพื่อเริ่มครั้งแรก</li>}
          </ul>
        </section>
      </PageBody>
    </>
  )
}
