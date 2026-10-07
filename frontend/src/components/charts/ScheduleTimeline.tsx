import type { Run, Source } from '../../lib/types'
import { sourceLabel } from '../../lib/format'
import { useWidth } from '../ui/useWidth'

/** Today's runs per source on a 24h axis, with the current time and upcoming scheduled runs. */
export function ScheduleTimeline({ sources, runs }: { sources: Source[]; runs: Run[] }) {
  const [ref, width] = useWidth<HTMLDivElement>(900)
  const start = new Date(); start.setHours(0, 0, 0, 0)
  const day0 = start.getTime(), day1 = day0 + 86400_000
  const L = 90, R = 10
  const x = (t: number) => L + ((Math.min(Math.max(t, day0), day1) - day0) / 86400_000) * (width - L - R)
  const now = Date.now()
  const laneH = 44, top = 24
  const height = top + sources.length * laneH + 26

  const upcoming = (s: Source): number[] => {
    if (!s.enabled || !s.next_run_at) return []
    const out: number[] = []
    let t = new Date(s.next_run_at).getTime()
    const step = s.mode === 'interval' ? (s.every_hours ?? 6) * 3600_000 : 86400_000
    while (t < day1 && out.length < 24) { out.push(t); t += step }
    return out
  }

  return (
    <div ref={ref} className="overflow-hidden">
      <svg width={width} height={height} role="img" aria-label="ไทม์ไลน์การรันของแต่ละแหล่งในวันนี้">
        {Array.from({ length: 9 }, (_, i) => day0 + i * 3 * 3600_000).map((t, i) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={top - 6} y2={height - 26} stroke="#F0F0F2" />
            <text x={x(t)} y={height - 8} fontSize={11} fill="#71717A" textAnchor={i === 0 ? 'start' : i === 8 ? 'end' : 'middle'} className="font-mono">
              {String(i * 3).padStart(2, '0')}:00
            </text>
          </g>
        ))}
        {sources.map((s, li) => {
          const cy = top + li * laneH + laneH / 2
          const todays = runs.filter((r) => r.source === s.source && new Date(r.started_at).getTime() >= day0)
          return (
            <g key={s.source}>
              <text x={0} y={cy + 4} fontSize={13} fontWeight={500} fill="#09090B">{sourceLabel(s.source)}</text>
              <rect x={L} y={cy - 12} width={width - L - R} height={24} rx={6} fill="#FAFAFA" />
              {todays.map((r) => {
                const a = new Date(r.started_at).getTime()
                const b = r.finished_at ? new Date(r.finished_at).getTime() : now
                const running = r.status === 'running' || r.status === 'queued'
                const fill = running ? '#2F63B8' : r.status === 'failed' ? '#FBEAEF' : r.status === 'warning' ? '#FEF3C7'
                  : r.status === 'cancelled' ? '#F4F4F5' : '#BBF7D0'
                const stroke = running ? 'none' : r.status === 'failed' ? '#8E1F3D' : r.status === 'warning' ? '#D97706'
                  : r.status === 'cancelled' ? '#A1A1AA' : '#16A34A'
                return <rect key={r.id} x={x(a)} y={cy - 9} width={Math.max(6, x(b) - x(a))} height={18} rx={4} fill={fill} stroke={stroke}><title>{`${sourceLabel(r.source)} · ${r.status}`}</title></rect>
              })}
              {upcoming(s).map((t) => (
                <rect key={t} x={x(t)} y={cy - 9} width={Math.max(10, x(t + 3600_000) - x(t))} height={18} rx={4} fill="none" stroke="#7BA3D9" strokeWidth={1.5} strokeDasharray="4 3" />
              ))}
            </g>
          )
        })}
        <line x1={x(now)} x2={x(now)} y1={top - 8} y2={height - 26} stroke="#09090B" strokeWidth={1.5} />
        <rect x={x(now) - 26} y={0} width={52} height={18} rx={9} fill="#09090B" />
        <text x={x(now)} y={13} textAnchor="middle" fontSize={11} fill="#FFFFFF" className="font-mono">
          {new Date(now).toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' })}
        </text>
      </svg>
    </div>
  )
}