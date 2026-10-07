import type { SalaryRow } from '../../lib/types'
import { bahtK } from '../../lib/format'

const COLORS: Record<string, string> = { Entry: '#B9CDEE', Mid: '#7BA3D9', Senior: '#2F63B8' }

export function SalaryRanges({ rows }: { rows: SalaryRow[] }) {
  const max = Math.max(60000, ...rows.map((r) => r.max)) * 1.02
  const at = (v: number) => `${(v / max) * 100}%`
  return (
    <div className="flex flex-col gap-4">
      {rows.map((r) => (
        <div key={r.level} className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between text-sm">
            <span className="font-medium">{r.level}</span>
            <span className="num text-[13px] text-muted">มัธยฐาน <strong className="text-[15px] text-ink">{bahtK(r.median)}</strong></span>
          </div>
          <div className="relative h-2.5" role="img" aria-label={`${r.level}: ${bahtK(r.min)} ถึง ${bahtK(r.max)}, มัธยฐาน ${bahtK(r.median)}`}>
            <div className="absolute top-1/2 h-0.5 -translate-y-1/2 rounded bg-[#D4D4D8]" style={{ left: at(r.min), width: `calc(${at(r.max)} - ${at(r.min)})` }} />
            <div className="absolute inset-y-0 rounded-full" style={{ left: at(r.p25), width: `calc(${at(r.p75)} - ${at(r.p25)})`, background: COLORS[r.level] ?? '#7BA3D9' }} />
            <div className="absolute -top-[3px] h-4 w-4 -translate-x-1/2 rounded-full border-[2.5px] border-ink bg-white" style={{ left: at(r.median) }} />
          </div>
        </div>
      ))}
      <div className="num flex justify-between text-xs text-faint"><span>฿0</span><span>{bahtK(max / 2)}</span><span>{bahtK(max)}</span></div>
      <div className="flex flex-wrap gap-4 text-xs text-muted">
        <span className="flex items-center gap-1.5"><span className="h-2 w-4 rounded-full bg-brand-500" />ช่วง 25–75%</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full border-2 border-ink" />มัธยฐาน</span>
        <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-[#D4D4D8]" />ต่ำสุด–สูงสุด</span>
      </div>
    </div>
  )
}
