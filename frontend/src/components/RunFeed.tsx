import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import type { FeedItem, FeedKind, Run } from '../lib/types'
import { Icon } from './icons'

const KIND: Record<FeedKind, { label: string; cls: string }> = {
  new: { label: 'ใหม่', cls: 'bg-good-soft text-good-text' },
  updated: { label: 'อัปเดต', cls: 'bg-brand-100 text-brand-800' },
  bumped: { label: 'ดันประกาศ', cls: 'bg-canvas text-ink-3' },
  partial: { label: 'ได้ไม่ครบ', cls: 'bg-warn-soft text-warn-text' },
  failed: { label: 'ดึงไม่ได้', cls: 'bg-maroon-soft text-maroon' },
}
const ORDER: FeedKind[] = ['new', 'updated', 'bumped', 'partial', 'failed']

function Changes({ item }: { item: FeedItem }) {
  const fields = item.db_changes?.fields ?? []
  if (!fields.length) {
    return <p className="text-[13px] text-muted">ยังไม่มีบันทึกในฐานข้อมูล (รอขั้น "นำเข้าฐานข้อมูล")</p>
  }
  return (
    <div className="flex flex-col gap-2">
      {fields.map((f) => (
        <div key={f.field} className="grid gap-1.5 text-[13px] sm:grid-cols-[110px_minmax(0,1fr)_minmax(0,1fr)]">
          <span className="font-medium text-ink">{f.label}</span>
          {f.old === null && f.new === null ? (
            <span className="text-muted sm:col-span-2">เปลี่ยนเป็นบริษัทอื่น</span>
          ) : (
            <>
              <span className="whitespace-pre-wrap break-words rounded-lg bg-maroon-soft/60 px-2.5 py-1.5 text-ink-3">
                <span className="mb-0.5 block text-[11px] font-medium text-maroon">เดิม</span>{f.old || '–'}
              </span>
              <span className="whitespace-pre-wrap break-words rounded-lg bg-good-soft/70 px-2.5 py-1.5 text-ink">
                <span className="mb-0.5 block text-[11px] font-medium text-good-text">ใหม่</span>{f.new || '–'}
              </span>
            </>
          )}
        </div>
      ))}
      {item.db_changes?.reextract && (
        <p className="text-[12px] text-muted">ชื่อตำแหน่ง/รายละเอียด/คุณสมบัติเปลี่ยน → ระบบสกัดทักษะและทำ embedding ของงานนี้ใหม่</p>
      )}
    </div>
  )
}

function Row({ item, active, stopped }: { item: FeedItem; active: boolean; stopped: boolean }) {
  const [open, setOpen] = useState(false)
  const k = KIND[item.kind] ?? KIND.new
  const canDiff = item.kind === 'updated'
  const meta = [item.company, item.salary, item.location].filter(Boolean).join(' · ')
  return (
    <li className="flex flex-col gap-2 border-b border-line px-4 py-3 last:border-b-0">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
        <div className="flex shrink-0 items-center gap-2 sm:w-[118px] sm:flex-col sm:items-start sm:gap-1">
          <span className={clsx('rounded-full px-2 py-0.5 text-xs font-medium', k.cls)}>{k.label}</span>
          {item.at && <span className="num text-xs text-faint">{item.at}</span>}
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="text-sm font-medium text-ink">{item.title || <span className="break-all text-muted">{item.url}</span>}</span>
          {meta && <span className="text-[13px] text-muted">{meta}</span>}
          {(item.kind === 'updated' || item.kind === 'bumped') && (
            <span className="text-[13px] text-muted">
              วันที่ในประกาศ {item.before || '–'} <Icon name="arrowRight" size={12} className="inline" /> {item.post_date || '–'}
              {item.kind === 'bumped' && ' · เปิดดูแล้วเนื้อหาเหมือนเดิม'}
            </span>
          )}
          {item.changed && item.changed.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {item.changed.map((c) => <span key={c} className="rounded-md bg-brand-100 px-1.5 py-0.5 text-[12px] text-brand-800">{c}</span>)}
            </div>
          )}
          {item.missing && item.missing.length > 0 && <span className="text-[13px] text-warn-text">ขาด: {item.missing.join(', ')}</span>}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {canDiff && (
            <button type="button" className="btn-outline h-8 px-2.5 text-[13px]" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
              ที่เปลี่ยน <Icon name="chevronDown" size={14} className={clsx('transition-transform', open && 'rotate-180')} />
            </button>
          )}
          <a href={item.url} target="_blank" rel="noopener noreferrer" className="btn-outline h-8 px-2.5 text-[13px]">
            ต้นฉบับ <Icon name="external" size={13} />
          </a>
          {item.job_id ? (
            <Link to={`/jobs/${item.job_id}`} target="_blank" className="btn-outline h-8 px-2.5 text-[13px]">
              ในระบบ <Icon name="arrowRight" size={13} />
            </Link>
          ) : item.kind !== 'failed' && (
            <span className="inline-flex h-8 items-center px-1 text-[12px] text-faint">{active ? 'รอนำเข้า' : stopped ? 'ยังไม่นำเข้า' : 'ไม่อยู่ในฐาน'}</span>
          )}
        </div>
      </div>
      {open && <div className="rounded-xl border border-line bg-canvas/60 p-3"><Changes item={item} /></div>}
    </li>
  )
}

/** Jobs scraped in one run, live while it runs — open the real posting and our copy side by side to check them. */
export function RunFeed({ run, active }: { run: Run; active: boolean }) {
  const crawl = run.steps?.find((s) => s.key === 'crawl')
  const [kind, setKind] = useState<FeedKind | 'all'>('all')
  const feed = useQuery({
    queryKey: ['run-feed', run.id, run.status, crawl?.feed_count ?? 0],
    queryFn: () => api.runFeed(run.id),
    enabled: !!crawl,
    refetchInterval: active ? 5000 : false,
  })
  if (!crawl) return null

  const items = feed.data ?? []
  const count = (k: FeedKind) => items.filter((i) => i.kind === k).length
  // a filter whose items were all trimmed away (list keeps the newest FEED_MAX) falls back to "all"
  const sel = kind !== 'all' && count(kind) === 0 ? 'all' : kind
  const shown = sel === 'all' ? items : items.filter((i) => i.kind === sel)
  const capped = items.length >= 500
  const stopped = !active && (run.status === 'cancelled' || run.status === 'failed')
  const notLoaded = stopped && items.some((i) => !i.job_id && i.kind !== 'failed')
  const old = crawl.feed_count == null && !active   // run made before the live list existed

  return (
    <section className="flex flex-col gap-3" aria-label="งานที่ดึงในรอบนี้">
      <div className="flex flex-col gap-1">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
          {active && <span className="h-2 w-2 animate-pulse rounded-full bg-good" aria-hidden="true" />}
          งานที่ดึงในรอบนี้ <span className="num font-normal text-muted">{capped ? `${items.length} ล่าสุด` : items.length}</span>
        </h3>
        <p className="text-[13px] text-muted">
          เปิด <b className="font-medium text-ink-3">ต้นฉบับ</b> (เว็บจริง) คู่กับ <b className="font-medium text-ink-3">ในระบบ</b> (ข้อมูลที่เราเก็บ) เพื่อเทียบว่าดึงมาตรงและครบ
          · งานเดิมที่ไม่เปลี่ยนจะถูกข้ามและไม่แสดงที่นี่
        </p>
      </div>

      {notLoaded && (
        <p className="rounded-xl bg-warn-soft px-3.5 py-2.5 text-[13px] text-warn-text">
          รอบนี้หยุดก่อนนำเข้าฐานข้อมูล — งานที่ดึงได้ถูกบันทึกไว้แล้ว กด "ประมวลผลงานที่ค้าง" เพื่อนำเข้าตอนนี้ หรือรอรอบถัดไป
        </p>
      )}

      {items.length > 0 && (
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="กรองตามประเภท">
          {(['all', ...ORDER] as const).filter((k) => k === 'all' || count(k) > 0).map((k) => (
            <button key={k} type="button" aria-pressed={sel === k} onClick={() => setKind(k)}
              className={clsx('chip border', sel === k ? 'border-ink bg-ink text-white' : 'border-line bg-white text-ink-3 hover:bg-canvas')}>
              {k === 'all' ? 'ทั้งหมด' : KIND[k].label}
              <span className="num opacity-70">{k === 'all' ? items.length : count(k)}</span>
            </button>
          ))}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-line">
        {shown.length ? (
          <ul className="max-h-[460px] overflow-y-auto">
            {shown.map((it, i) => <Row key={`${it.url}-${i}`} item={it} active={active} stopped={stopped} />)}
          </ul>
        ) : (
          <p className="px-4 py-6 text-center text-sm text-muted">
            {feed.isLoading ? 'กำลังโหลด…'
              : old ? 'รอบนี้รันก่อนมีรายการสด — ดูรายละเอียดใน log'
              : active ? 'ยังไม่มีงาน — กำลังไล่หน้ารายการ (งานเดิมจะถูกข้าม)'
              : 'รอบนี้ไม่มีงานใหม่หรืองานที่อัปเดต'}
          </p>
        )}
      </div>
    </section>
  )
}
