import type { GapPoint } from '../../lib/types'
import { useState } from 'react'
import { useWidth } from '../ui/useWidth'

interface Placed { p: GapPoint; q: string; cx: number; cy: number; flip: boolean }

/** Pick which labels to draw and nudge them vertically so they do not overlap (≥ 15px apart on the same side). */
function placeLabels(items: Placed[], labelled: Set<string>, hover: string | null) {
  const taken: { x: number; y: number; flip: boolean }[] = []
  const order = [...items].sort((a, b) => b.p.demand_pct - a.p.demand_pct)
  const out = new Map<string, Placed & { ly: number; show: boolean }>()
  for (const it of order) {
    const show = labelled.has(it.p.skill) || hover === it.p.skill
    let ly = it.cy
    if (show && hover !== it.p.skill) {
      for (let tries = 0; tries < 6 && taken.some((t) => t.flip === it.flip && Math.abs(t.x - it.cx) < 140 && Math.abs(t.y - ly) < 15); tries++)
        ly += tries % 2 === 0 ? 16 * (tries + 1) : -16 * (tries + 1)
      taken.push({ x: it.cx, y: ly, flip: it.flip })
    }
    out.set(it.p.skill, { ...it, ly, show })
  }
  // draw the hovered point last so it sits on top
  return items.map((it) => out.get(it.p.skill)!).sort((a, b) => Number(a.p.skill === hover) - Number(b.p.skill === hover))
}

interface Props { points: GapPoint[]; demandThreshold: number; covThreshold: number; labelTop?: number }

const quadrant = (p: GapPoint, dT: number, cT: number) =>
  p.demand_pct >= dT ? (p.coverage < cT ? 'urgent' : 'strength') : p.coverage < cT ? 'watch' : 'surplus'

/** Scatter of market demand (x) vs curriculum coverage (y). Desktop. */
export function PriorityMatrix({ points, demandThreshold, covThreshold, labelTop = 8 }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<string | null>(null)
  // label only the most-demanded skills; the rest show their name on hover
  const labelled = new Set([...points].sort((a, b) => b.demand_pct - a.demand_pct).slice(0, labelTop).map((p) => p.skill))
  const height = 400
  const L = 50, R = 14, T = 20, B = 50
  const maxD = Math.max(0.2, ...points.map((p) => p.demand_pct)) * 1.1
  const x = (d: number) => L + (d / maxD) * (width - L - R)
  const y = (c: number) => T + (1 - c) * (height - T - B)
  const xT = x(demandThreshold), yT = y(covThreshold)
  const ticks = [0, maxD / 3, (2 * maxD) / 3, maxD]
  return (
    <div ref={ref}>
      <svg width={width} height={height} role="img"
        aria-label={`Priority matrix: ${points.filter((p) => quadrant(p, demandThreshold, covThreshold) === 'urgent').map((p) => p.skill).join(', ')} อยู่ในกลุ่มต้องเร่งเพิ่ม`}>
        <rect x={xT} y={yT} width={width - R - xT} height={y(0) - yT} fill="#FBEAEF" />
        <rect x={L} y={T} width={width - L - R} height={height - T - B} fill="none" stroke="#F0F0F2" />
        <line x1={xT} x2={xT} y1={T} y2={y(0)} stroke="#D4D4D8" strokeDasharray="4 4" />
        <line x1={L} x2={width - R} y1={yT} y2={yT} stroke="#D4D4D8" strokeDasharray="4 4" />
        <g fontSize={11} fontWeight={600}>
          <text x={width - R - 10} y={y(0) - 10} textAnchor="end" fill="#8E1F3D">ต้องเร่งเพิ่ม</text>
          <text x={width - R - 10} y={yT - 10} textAnchor="end" fill="#52525B">จุดแข็งของหลักสูตร</text>
          <text x={L + 10} y={T + 18} fill="#52525B">สอนแล้ว ตลาดยังน้อย</text>
          <text x={L + 10} y={yT + 18} fill="#52525B">เฝ้าดู</text>
        </g>
        {placeLabels(points.map((p) => {
          const q = quadrant(p, demandThreshold, covThreshold)
          const cx = x(p.demand_pct), cy = Math.min(y(p.coverage), y(0) - 8)
          return { p, q, cx, cy, flip: cx > width - 110 }
        }), labelled, hover).map(({ p, q, cx, cy, flip, ly, show }) => {
          const fill = q === 'urgent' ? '#8E1F3D' : q === 'watch' ? '#B9CDEE' : '#7BA3D9'
          return (
            <g key={p.skill} onMouseEnter={() => setHover(p.skill)} onMouseLeave={() => setHover(null)} className="cursor-default">
              <title>{`${p.skill} · ตลาดต้องการ ${(p.demand_pct * 100).toFixed(1)}% · ครอบคลุม ${p.coverage.toFixed(2)}`}</title>
              <circle cx={cx} cy={cy} r={q === 'urgent' ? 7.5 : 6} fill={fill} stroke="#FFFFFF" strokeWidth={2} />
              {show && (
                <text x={flip ? cx - 11 : cx + 11} y={ly + 4} fontSize={12} textAnchor={flip ? 'end' : 'start'}
                  fontWeight={q === 'urgent' ? 600 : 500} fill={q === 'urgent' ? '#09090B' : '#3F3F46'}
                  stroke="#FFFFFF" strokeWidth={3} paintOrder="stroke">{p.skill}</text>
              )}
            </g>
          )
        })}
        <g fontSize={11} fill="#71717A" className="font-mono">
          {ticks.map((t) => <text key={t} x={x(t)} y={height - 32} textAnchor="middle">{Math.round(t * 100)}%</text>)}
          <text x={L - 8} y={y(0) + 4} textAnchor="end">0</text>
          <text x={L - 8} y={yT + 4} textAnchor="end">{covThreshold}</text>
          <text x={L - 8} y={y(1) + 4} textAnchor="end">1.0</text>
        </g>
        <text x={(width + L) / 2} y={height - 8} textAnchor="middle" fontSize={12} fill="#52525B">ความต้องการของตลาด (% ของงาน) →</text>
        <text x={12} y={(T + y(0)) / 2} textAnchor="middle" fontSize={12} fill="#52525B" transform={`rotate(-90 12 ${(T + y(0)) / 2})`}>ความครอบคลุม →</text>
      </svg>
    </div>
  )
}

/** The same grouping as four cards, for narrow screens. */
export function PriorityQuadrants({ points, demandThreshold, covThreshold }: Props) {
  const groups = [
    { key: 'urgent', title: 'ต้องเร่งเพิ่ม', sub: 'ตลาดต้องการ แต่ยังสอนน้อย', cls: 'border-maroon-200 bg-maroon-soft', tcls: 'text-maroon' },
    { key: 'strength', title: 'จุดแข็ง', sub: 'ตลาดต้องการ และสอนแล้ว', cls: 'border-brand-200 bg-brand-50', tcls: 'text-brand-800' },
    { key: 'watch', title: 'เฝ้าดู', sub: 'ตลาดยังน้อย และยังไม่สอน', cls: 'border-line bg-white', tcls: 'text-ink' },
    { key: 'surplus', title: 'สอนแล้ว ตลาดยังน้อย', sub: `ต้องการน้อยกว่า ${Math.round(demandThreshold * 100)}%`, cls: 'border-line bg-white', tcls: 'text-ink' },
  ]
  return (
    <div className="grid grid-cols-2 gap-2">
      {groups.map((g) => (
        <div key={g.key} className={`flex min-h-[132px] flex-col gap-2.5 rounded-[18px] border p-3.5 ${g.cls}`}>
          <div className="flex flex-col"><span className={`text-sm font-semibold ${g.tcls}`}>{g.title}</span><span className="text-xs text-muted">{g.sub}</span></div>
          <div className="flex flex-wrap gap-1.5">
            {points.filter((p) => quadrant(p, demandThreshold, covThreshold) === g.key).map((p) => (
              <span key={p.skill} className="rounded-[7px] border border-line bg-white px-2 py-0.5 text-xs font-medium">{p.skill}</span>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}