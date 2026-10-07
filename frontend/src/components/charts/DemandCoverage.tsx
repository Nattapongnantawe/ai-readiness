import clsx from 'clsx'
import { useState } from 'react'
import { num, pct } from '../../lib/format'
import type { GapPoint } from '../../lib/types'

/**
 * Top skills by market demand, one bar each: length = % of jobs, colour = taught or not.
 * Replaces the demand × coverage scatter, which did not work here because coverage is almost
 * always 0 or 1 (a course either teaches the skill or not) → every point sat on the top or bottom edge.
 */
export function DemandCoverage({ points, covThreshold, initial = 15 }: { points: GapPoint[]; covThreshold: number; initial?: number }) {
  const [all, setAll] = useState(false)
  const list = [...points].sort((a, b) => b.demand_pct - a.demand_pct)
  const shown = all ? list : list.slice(0, initial)
  const max = Math.max(0.01, ...list.map((p) => p.demand_pct))
  const missing = list.filter((p) => p.coverage < covThreshold).length
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <span>Top {list.length} ทักษะที่ตลาดต้องการ · <strong className="text-maroon">{missing} ทักษะยังไม่มีวิชาสอน</strong></span>
        <span className="flex items-center gap-3">
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-maroon" />ยังไม่มีวิชาสอน</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-brand-700" />สอนแล้ว</span>
        </span>
      </div>
      <ol className="flex flex-col">
        {shown.map((p, i) => {
          const gap = p.coverage < covThreshold
          return (
            <li key={p.skill} className="grid grid-cols-[22px_minmax(0,150px)_minmax(0,1fr)_76px] items-center gap-2.5 border-t border-line-soft py-1.5 text-sm first:border-0 lg:grid-cols-[22px_180px_minmax(0,1fr)_92px]"
              title={p.course_names?.length ? `สอนใน:\n${p.course_names.join('\n')}` : 'ยังไม่มีวิชาที่สอนทักษะนี้'}>
              <span className="num font-mono text-[11px] text-faint">{String(i + 1).padStart(2, '0')}</span>
              <span className={clsx('truncate', gap ? 'font-semibold text-ink' : 'text-ink-2')}>
                {p.skill}{p.is_ai_skill && <span className="ml-1.5 rounded bg-navy px-1 py-px text-[9px] font-bold text-white">AI</span>}
              </span>
              <span className="flex items-center gap-2">
                <span className="h-3.5 rounded-[4px]" style={{ width: `${Math.max(2, (p.demand_pct / max) * 100)}%`, background: gap ? '#8E1F3D' : '#234C91', opacity: gap ? 1 : 0.85 }} />
                <span className="num shrink-0 text-xs text-muted">{pct(p.demand_pct)}{p.jobs != null && <span className="hidden lg:inline"> · {num(p.jobs)} งาน</span>}</span>
              </span>
              <span className={clsx('num text-right text-xs', gap ? 'font-medium text-maroon' : 'text-brand-800')}>
                {gap ? 'ยังไม่มีวิชา' : p.courses != null ? `${p.courses} วิชา` : 'สอนแล้ว'}
              </span>
            </li>
          )
        })}
      </ol>
      {list.length > initial && (
        <button type="button" onClick={() => setAll((x) => !x)} className="self-start text-[13px] font-medium text-brand-800 hover:underline">
          {all ? `แสดง ${initial} อันดับแรก` : `ดูทั้งหมด ${list.length} ทักษะ`}
        </button>
      )}
    </div>
  )
}