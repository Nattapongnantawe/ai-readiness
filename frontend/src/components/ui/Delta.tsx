import clsx from 'clsx'

type Kind = 'pct' | 'pts' | 'count'

/** Change chip. `value` is a relative change for pct, an absolute share difference for pts, a raw number for count. */
export function Delta({ value, kind, dark }: { value: number | null | undefined; kind: Kind; dark?: boolean }) {
  if (value == null || !Number.isFinite(value)) return null
  const up = value >= 0
  const text = kind === 'pct' ? `${Math.abs(value * 100).toFixed(1)}%` : kind === 'pts' ? `${Math.abs(value * 100).toFixed(1)} pts` : Math.abs(Math.round(value)).toLocaleString('en-US')
  return (
    <span className={clsx('num inline-flex items-center gap-0.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold',
      dark ? (up ? 'bg-good-deep text-good-bright' : 'bg-maroon/30 text-maroon-light') : up ? 'bg-good-soft text-good-text' : 'bg-maroon-soft text-maroon')}>
      {up ? '↑' : '↓'} {text}
    </span>
  )
}

export function change(cur: number | null | undefined, prev: number | null | undefined): number | null {
  if (cur == null || prev == null || prev === 0) return null
  return (cur - prev) / prev
}
