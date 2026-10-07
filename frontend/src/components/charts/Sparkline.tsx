export function Sparkline({ values, color = '#2F63B8' }: { values: number[]; color?: string }) {
  // fewer than 4 points is not a trend (e.g. a one-off snapshot) → leave the space empty
  if (values.length < 4) return <div className="h-[30px]" />
  const lo = Math.min(...values), hi = Math.max(...values)
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * 140},${28 - ((v - lo) / (hi - lo || 1)) * 24}`).join(' ')
  return (
    <svg width="100%" height="30" viewBox="0 0 140 30" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.8} strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}