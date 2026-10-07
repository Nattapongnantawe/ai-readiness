import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { api } from '../lib/api'
import { num } from '../lib/format'
import { Icon } from './icons'

type Item = { kind: 'query' | 'skill' | 'title'; text: string; jobs?: number }

function useDebounced<T>(value: T, ms = 200): T {
  const [v, setV] = useState(value)
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t) }, [value, ms])
  return v
}

/** Bold the part of `text` that matches what was typed. */
function highlight(text: string, q: string): ReactNode {
  const i = q ? text.toLowerCase().indexOf(q.toLowerCase()) : -1
  if (i < 0) return text
  return <>{text.slice(0, i)}<strong className="font-semibold text-ink">{text.slice(i, i + q.length)}</strong>{text.slice(i + q.length)}</>
}

/**
 * Search input with type-ahead: while typing, suggests skills and job titles that exist in the
 * database (GET /search/suggest), most common first. On focus with an empty box it shows the most
 * demanded skills and most common titles. Arrow keys + Enter to pick, Esc to close.
 */
export function SearchBox({ value, onChange, onSubmit, onClear }: {
  value: string; onChange: (v: string) => void; onSubmit: (v: string) => void; onClear?: () => void
}) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const term = useDebounced(value.trim(), 200)
  const inputRef = useRef<HTMLInputElement>(null)
  const sugg = useQuery({ queryKey: ['suggest', term], queryFn: () => api.suggest(term, 6), enabled: open, staleTime: 60_000 })

  const items: Item[] = [
    ...(value.trim().length >= 2 ? [{ kind: 'query' as const, text: value.trim() }] : []),
    ...(sugg.data?.skills ?? []).map((s) => ({ kind: 'skill' as const, ...s })),
    ...(sugg.data?.titles ?? []).map((s) => ({ kind: 'title' as const, ...s })),
  ]
  useEffect(() => setActive(-1), [term])

  const pick = (it: Item) => {
    onChange(it.text)
    onSubmit(it.text)
    setOpen(false)
    inputRef.current?.blur()
  }
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive((a) => Math.min(items.length - 1, a + 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(-1, a - 1)) }
    else if (e.key === 'Escape') setOpen(false)
    else if (e.key === 'Enter' && open && active >= 0 && items[active]) { e.preventDefault(); pick(items[active]) }
  }

  const section = (kind: Item['kind'], title: string) => {
    const list = items.map((it, i) => ({ it, i })).filter((x) => x.it.kind === kind)
    if (!list.length) return null
    return (
      <div className="flex flex-col py-1">
        {title && <span className="px-4 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-faint">{title}</span>}
        {list.map(({ it, i }) => (
          <button key={`${kind}-${it.text}`} type="button" role="option" aria-selected={i === active} id={`sugg-${i}`}
            onMouseDown={(e) => e.preventDefault()} onMouseEnter={() => setActive(i)} onClick={() => pick(it)}
            className={clsx('flex min-h-10 items-center gap-3 px-4 text-left text-[15px] text-ink-3', i === active && 'bg-brand-50')}>
            <Icon name={kind === 'query' ? 'search' : kind === 'skill' ? 'target' : 'building'} size={15} className="shrink-0 text-faint" />
            <span className="min-w-0 flex-1 truncate">{kind === 'query' ? <>ค้นหา “<strong className="font-semibold text-ink">{it.text}</strong>”</> : highlight(it.text, term)}</span>
            {it.jobs != null && <span className="num shrink-0 text-xs text-faint">{num(it.jobs)} งาน</span>}
          </button>
        ))}
      </div>
    )
  }
  const showList = open && (items.length > 0 || sugg.isFetching)

  return (
    <div className="relative">
      <form role="search" onSubmit={(e) => { e.preventDefault(); setOpen(false); onSubmit(value) }}
        className="flex h-14 items-center gap-2.5 rounded-2xl border-[1.5px] border-brand-700 bg-white pl-4 pr-1.5 shadow-[0_0_0_4px_#E3ECF9] lg:h-[60px]">
        <Icon name="search" size={20} className="shrink-0 text-brand-700" />
        <label htmlFor="q" className="sr-only">คำค้นหา</label>
        <input id="q" ref={inputRef} value={value} maxLength={500} autoComplete="off" spellCheck={false}
          role="combobox" aria-expanded={showList} aria-controls="search-suggest" aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? `sugg-${active}` : undefined}
          onChange={(e) => { onChange(e.target.value); setOpen(true) }} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} onKeyDown={onKey}
          placeholder="พิมพ์ตำแหน่ง ทักษะ หรือประโยค เช่น งาน AI ที่ใช้ Python"
          className="min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-faint lg:text-[17px]" />
        {value && onClear && (
          <button type="button" aria-label="ล้างคำค้น" onMouseDown={(e) => e.preventDefault()} onClick={() => { onChange(''); onClear() }}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-faint hover:bg-canvas"><Icon name="close" size={16} /></button>
        )}
        <button type="submit" aria-label="ค้นหา" className="flex h-11 shrink-0 items-center justify-center rounded-[11px] bg-ink px-4 text-sm font-medium text-white lg:px-5">
          <span className="hidden lg:inline">ค้นหา</span><Icon name="arrowRight" className="lg:hidden" />
        </button>
      </form>
      {showList && (
        <div id="search-suggest" role="listbox" aria-label="คำแนะนำ"
          className="absolute inset-x-0 top-full z-30 mt-2 max-h-[420px] overflow-y-auto rounded-2xl border border-line bg-white py-1 shadow-[0_12px_32px_rgba(16,24,40,0.12)]">
          {section('query', '')}
          {section('skill', term ? 'ทักษะ' : 'ทักษะที่ตลาดต้องการมากที่สุด')}
          {section('title', term ? 'ตำแหน่งงาน' : 'ตำแหน่งที่ประกาศบ่อย')}
          {!items.length && sugg.isFetching && <span className="block px-4 py-3 text-sm text-faint">กำลังค้นหาคำแนะนำ…</span>}
        </div>
      )}
    </div>
  )
}
