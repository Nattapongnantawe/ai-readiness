import { useId } from 'react'

interface Props { size?: number; dark?: boolean; className?: string }

/** Logo D "Faceted Spire": derived from the Kalasin University spire, in university blues. */
export function LogoMark({ size = 36, dark = false, className }: Props) {
  const [left, right, top] = dark ? ['#7BA3D9', '#5C84C2', '#DCE7F8'] : ['#3B6FC4', '#234C91', '#A9C3EE']
  // the arch at the bottom is cut out (transparent), so the mark works on any background
  const mask = `spire-${useId().replace(/:/g, '')}`
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" className={className}>
      <mask id={mask}>
        <rect width="64" height="64" fill="#fff" />
        <path d="M21 61C21 50 27 44 32 38C37 44 43 50 43 61Z" fill="#000" />
      </mask>
      <g mask={`url(#${mask})`}>
        <path d="M32 4C28 14 12 22 8 36C4 50 14 60 32 60Z" fill={left} />
        <path d="M32 4C36 14 52 22 56 36C60 50 50 60 32 60Z" fill={right} />
        <path d="M32 4C33.5 8 36 11.5 39 15L32 24L25 15C28 11.5 30.5 8 32 4Z" fill={top} />
      </g>
    </svg>
  )
}

export function Wordmark({ dark = false, size = 16 }: { dark?: boolean; size?: number }) {
  return (
    <span className="font-semibold tracking-[-0.03em]" style={{ fontSize: size }}>
      <span className={dark ? 'text-brand-400' : 'text-brand-700'}>AI</span>{' '}
      <span className={dark ? 'text-white' : 'text-ink'}>Readiness</span>
    </span>
  )
}