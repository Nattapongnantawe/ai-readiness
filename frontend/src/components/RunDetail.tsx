import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useEffect, useRef } from 'react'
import { api, downloadRunLog } from '../lib/api'
import { useAuth } from '../lib/auth'
import { duration, sourceLabel, when } from '../lib/format'
import type { Run, RunStep } from '../lib/types'
import { Icon } from './icons'
import { RunFeed } from './RunFeed'
import { ErrorState, Skeleton } from './ui/States'

export const isActive = (r?: Run | null) => r?.status === 'running' || r?.status === 'queued'

export const RUN_STATUS: Record<Run['status'], { label: string; cls: string; dot: string }> = {
  success: { label: 'สำเร็จ', cls: 'bg-good-soft text-good-text', dot: 'bg-good' },
  warning: { label: 'สำเร็จ (มีข้อสังเกต)', cls: 'bg-warn-soft text-warn-text', dot: 'bg-warn' },
  running: { label: 'กำลังรัน', cls: 'bg-brand-100 text-brand-800', dot: 'bg-brand-700' },
  queued: { label: 'รอคิว', cls: 'bg-brand-100 text-brand-800', dot: 'bg-brand-500' },
  failed: { label: 'ล้มเหลว', cls: 'bg-maroon-soft text-maroon', dot: 'bg-maroon' },
  cancelled: { label: 'หยุดแล้ว', cls: 'bg-canvas text-ink-3', dot: 'bg-faint' },
}

function StepIcon({ s, n }: { s: RunStep; n: number }) {
  const base = 'flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold'
  if (s.status === 'running') return <span className={clsx(base, 'bg-brand-700 text-white')}><span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" /></span>
  if (s.status === 'success') return <span className={clsx(base, 'bg-good-soft text-good-text')}><Icon name="check" size={14} strokeWidth={3} /></span>
  if (s.status === 'warning') return <span className={clsx(base, 'bg-warn-soft text-warn-text')}><Icon name="alert" size={14} /></span>
  if (s.status === 'failed') return <span className={clsx(base, 'bg-maroon-soft text-maroon')}><Icon name="close" size={14} strokeWidth={3} /></span>
  if (s.status === 'cancelled') return <span className={clsx(base, 'bg-canvas text-ink-3')}><Icon name="stop" size={12} /></span>
  if (s.status === 'skipped') return <span className={clsx(base, 'border border-dashed border-line text-faint')}><Icon name="minus" size={14} /></span>
  return <span className={clsx(base, 'border border-line text-muted')}>{n}</span>
}

/** One pipeline run: steps with their result, live log, cancel and full-log download. */
export function RunDetail({ runId }: { runId: number }) {
  const qc = useQueryClient()
  const { isAdmin } = useAuth()
  const run = useQuery({ queryKey: ['run', runId], queryFn: () => api.run(runId),
    refetchInterval: (q) => (isActive(q.state.data) ? 2000 : false) })
  const cancel = useMutation({ mutationFn: () => api.cancelRun(runId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['run', runId] }); qc.invalidateQueries({ queryKey: ['runs'] }) } })
  const logRef = useRef<HTMLDivElement>(null)
  const r = run.data
  const active = isActive(r)
  const lines = r?.log.slice(-80) ?? []

  useEffect(() => {  // keep the live log scrolled to the newest line
    const el = logRef.current
    if (el && active) el.scrollTop = el.scrollHeight
  }, [lines.length, active])

  if (run.isError) return <ErrorState error={run.error} onRetry={() => run.refetch()} />
  if (!r) return <Skeleton className="h-64" />
  const st = RUN_STATUS[r.status] ?? RUN_STATUS.failed
  const steps = r.steps ?? []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col justify-between gap-3 lg:flex-row lg:items-center">
        <div className="flex flex-wrap items-center gap-2.5">
          <h2 className="card-title">รอบ #{r.id} · {sourceLabel(r.source)}</h2>
          <span className={clsx('inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium', st.cls)}>
            <span className={clsx('h-1.5 w-1.5 rounded-full', st.dot, active && 'animate-pulse')} />{st.label}
          </span>
          <span className="text-[13px] text-muted">{r.trigger === 'manual' ? 'สั่งรันเอง' : 'ตามรอบเวลา'} · เริ่ม {when(r.started_at)} · {duration(r.started_at, r.finished_at)}</span>
        </div>
        <div className="flex gap-2">
          {isAdmin && (
            <button type="button" className="btn-outline h-9" onClick={() => downloadRunLog(r.id)}>
              <Icon name="download" size={15} />log ทั้งหมด
            </button>
          )}
          {isAdmin && active && (
            <button type="button" className="btn h-9 bg-maroon text-white hover:opacity-90 disabled:opacity-50" disabled={cancel.isPending}
              onClick={() => { if (confirm('หยุดรอบนี้? ข้อมูลที่บันทึกแล้วไม่หาย รอบหน้าจะทำต่อจากที่ค้าง')) cancel.mutate() }}>
              <Icon name="stop" size={13} />{cancel.isPending ? 'กำลังหยุด…' : 'หยุด'}
            </button>
          )}
        </div>
      </div>

      {r.error_message && (
        <p className={clsx('rounded-xl px-3.5 py-2.5 text-[13px]', r.status === 'cancelled' ? 'bg-canvas text-ink-3' : 'bg-maroon-soft text-maroon')}>{r.error_message}</p>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <ol className="flex flex-col">
          {steps.map((s, i) => (
            <li key={s.key} className="relative flex gap-3 pb-4 last:pb-0">
              {i < steps.length - 1 && <span className="absolute left-[13px] top-8 h-[calc(100%-28px)] w-px bg-line" aria-hidden="true" />}
              <StepIcon s={s} n={i + 1} />
              <div className="flex min-w-0 flex-1 flex-col gap-0.5 pt-0.5">
                <div className="flex items-baseline justify-between gap-2">
                  <span className={clsx('text-sm font-medium', s.status === 'skipped' || s.status === 'pending' ? 'text-muted' : 'text-ink')}>{s.label}</span>
                  {s.started_at && <span className="num shrink-0 text-xs text-faint">{duration(s.started_at, s.finished_at)}</span>}
                </div>
                {s.summary && <span className={clsx('text-[13px]', s.status === 'failed' ? 'text-maroon' : s.status === 'warning' ? 'text-warn-text' : 'text-muted')}>{s.summary}</span>}
                {s.status === 'running' && !s.summary && <span className="text-[13px] text-brand-800">กำลังทำงาน…</span>}
              </div>
            </li>
          ))}
          {!steps.length && <li className="text-sm text-muted">รอบนี้ไม่มีรายละเอียดขั้นตอน</li>}
        </ol>
        <div ref={logRef} aria-live="polite" aria-label="log การทำงาน"
          className="max-h-[340px] min-h-[200px] overflow-y-auto rounded-xl bg-navy px-3.5 py-3 font-mono text-[11.5px] leading-relaxed text-navy-text">
          {lines.length ? lines.map((l, i) => (
            <div key={i} className={clsx('whitespace-pre-wrap break-all', /✗|⛔|error|ล้มเหลว [1-9]/i.test(l) ? 'text-maroon-light' : /✅|✓|สำเร็จ/.test(l) ? 'text-good-bright' : '')}>{l}</div>
          )) : <span>ยังไม่มี log</span>}
        </div>
      </div>

      <RunFeed run={r} active={active} />
    </div>
  )
}
