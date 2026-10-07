import clsx from 'clsx'

interface Props<T extends string | number> {
  label: string
  value: T
  options: { value: T; label: string }[]
  onChange: (v: T) => void
  dark?: boolean
  size?: 'sm' | 'md'
  full?: boolean
}

export function Segmented<T extends string | number>({ label, value, options, onChange, dark, size = 'sm', full }: Props<T>) {
  return (
    <div role="group" aria-label={label}
      className={clsx('flex rounded-[10px] p-[3px]', full && 'grid', dark ? 'border border-navy-500 bg-navy-700' : 'border border-[#EDEDF0] bg-canvas')}
      style={full ? { gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` } : undefined}>
      {options.map((o) => {
        const on = o.value === value
        return (
          <button key={String(o.value)} type="button" aria-pressed={on} onClick={() => onChange(o.value)}
            className={clsx('rounded-[7px] px-3 text-[13px] transition-colors', size === 'md' ? 'min-h-[38px] text-sm' : 'min-h-[30px]',
              on ? (dark ? 'bg-navy-500 font-medium text-white' : 'bg-white font-medium text-ink shadow-seg') : dark ? 'text-navy-text' : 'text-muted hover:text-ink')}>
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
