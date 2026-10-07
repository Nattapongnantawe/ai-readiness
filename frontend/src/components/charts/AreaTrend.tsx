import { useState, type PointerEvent } from 'react'
import { useWidth } from '../ui/useWidth'
import { smoothPath } from './smooth'

interface Point { label: string; value: number; note?: string }
interface Props { data: Point[]; height?: number; format: (v: number) => string; ariaLabel: string; tickLabel?: (p: Point, i: number) => string | null }

/** Area chart on a dark card, with a hover/tap tooltip. */
export function AreaTrend({ data, height = 230, format, ariaLabel, tickLabel }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  if (data.length < 2) return <div ref={ref} className="py-10 text-sm text-navy-text">ข้อมูลยังไม่พอสำหรับแนวโน้ม</div>

  const left = 40, right = 12, top = 14, bottom = 30
  const w = width - left - right, h = height - top - bottom
  const vals = data.map((d) => d.value)
  const pad = (Math.max(...vals) - Math.min(...vals)) * 0.35 || 0.05
  const lo = Math.max(0, Math.min(...vals) - pad), hi = Math.max(...vals) + pad
  const x = (i: number) => left + (i / (data.length - 1)) * w
  const y = (v: number) => top + (1 - (v - lo) / (hi - lo)) * h
  const pts = data.map((d, i) => [x(i), y(d.value)] as [number, number])
  const line = smoothPath(pts)
  const ticks = [hi, (hi + lo) / 2, lo]
  const active = hover ?? data.length - 1

  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const i = Math.round(((e.clientX - rect.left - left) / w) * (data.length - 1))
    setHover(Math.max(0, Math.min(data.length - 1, i)))
  }
  const tipLeft = x(active)
  const flip = tipLeft > width * 0.6

  return (
    <div ref={ref} className="relative">
      <svg width={width} height={height} role="img" aria-label={ariaLabel} onPointerMove={onMove} onPointerLeave={() => setHover(null)} className="touch-none">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={left} x2={width - right} y1={y(t)} y2={y(t)} stroke="#FFFFFF" strokeOpacity={0.08} />
            <text x={0} y={y(t) + 4} fontSize={11} fill="#7F93B5" className="font-mono">{format(t)}</text>
          </g>
        ))}
        <path d={`${line} L${x(data.length - 1)},${top + h} L${left},${top + h} Z`} fill="#5C84C2" fillOpacity={0.22} />
        <path d={line} fill="none" stroke="#9DB8E3" strokeWidth={2.5} strokeLinecap="round" />
        <line x1={tipLeft} x2={tipLeft} y1={top} y2={top + h} stroke="#9DB8E3" strokeOpacity={0.55} strokeDasharray="3 4" />
        <circle cx={tipLeft} cy={y(data[active].value)} r={6} fill="#0B1A33" stroke="#FFFFFF" strokeWidth={2.5} />
        {data.map((d, i) => {
          const t = tickLabel ? tickLabel(d, i) : d.label
          return t ? <text key={i} x={x(i)} y={height - 8} fontSize={11} fill="#7F93B5" textAnchor={i === 0 ? 'start' : i === data.length - 1 ? 'end' : 'middle'}>{t}</text> : null
        })}
      </svg>
      {hover !== null && (
        <div className="pointer-events-none absolute top-8 flex min-w-[140px] flex-col gap-0.5 rounded-[10px] bg-white px-3 py-2.5 text-ink shadow-pop"
          style={{ left: tipLeft, transform: flip ? 'translateX(calc(-100% - 14px))' : 'translateX(14px)' }}>
          <span className="text-xs text-muted">{data[active].label}</span>
          <span className="num text-[17px] font-semibold">{format(data[active].value)}</span>
          {data[active].note && <span className="text-xs text-muted">{data[active].note}</span>}
        </div>
      )}
    </div>
  )
}
