import clsx from 'clsx'
import { useEffect, useState } from 'react'
import { Icon } from '../icons'

/** Company logo from companies.logo_url; falls back to the first letter (or a building icon) if missing or broken. */
export function CompanyLogo({ src, name, size = 44, className }: { src?: string | null; name?: string | null; size?: number; className?: string }) {
  const [broken, setBroken] = useState(false)
  useEffect(() => setBroken(false), [src])
  const letter = (name ?? '').replace(/^(บริษัท|บจก\.?|หจก\.?|ห้างหุ้นส่วน(จำกัด|สามัญ)?|company|the)\s*/i, '').trim().charAt(0).toUpperCase()
  const box = clsx('flex shrink-0 items-center justify-center overflow-hidden rounded-xl border border-[#EDEDF0] bg-white', className)
  if (src && !broken)
    return (
      <span className={box} style={{ width: size, height: size }}>
        <img src={src} alt={name ? `โลโก้ ${name}` : 'โลโก้บริษัท'} loading="lazy" referrerPolicy="no-referrer"
          onError={() => setBroken(true)} className="h-full w-full object-contain p-1" />
      </span>
    )
  return (
    <span className={clsx(box, 'bg-canvas text-faint')} style={{ width: size, height: size }} aria-hidden="true">
      {letter ? <span className="font-semibold text-ink-3" style={{ fontSize: size * 0.4 }}>{letter}</span> : <Icon name="building" size={size * 0.45} strokeWidth={1.8} />}
    </span>
  )
}