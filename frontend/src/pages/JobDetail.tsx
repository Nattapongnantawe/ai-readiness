import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import { Icon } from '../components/icons'
import { PageBody, PageHeader } from '../components/layout/PageHeader'
import { CompanyLogo } from '../components/ui/CompanyLogo'
import { Ring } from '../components/ui/Ring'
import { ErrorState, Skeleton } from '../components/ui/States'
import { api } from '../lib/api'
import { date, experience, salaryRange, sourceLabel, when } from '../lib/format'

export default function JobDetail() {
  const { id } = useParams()
  const { state } = useLocation() as { state: { similarity?: number; query?: string } | null }
  const job = useQuery({ queryKey: ['job', id], queryFn: () => api.job(Number(id)), enabled: !!id })
  const [copied, setCopied] = useState(false)
  const j = job.data
  const queryWords = (state?.query ?? '').toLowerCase()
  const backTo = state?.query ? `/search?q=${encodeURIComponent(state.query)}` : '/search'

  const copy = async () => {
    try { await navigator.clipboard.writeText(j?.source_url ?? location.href); setCopied(true); setTimeout(() => setCopied(false), 1600) } catch { /* clipboard blocked */ }
  }

  if (job.isError) return <><PageHeader crumbs={['ค้นหางาน', 'รายละเอียดงาน']} title="รายละเอียดงาน" back={backTo} /><PageBody><ErrorState error={job.error} onRetry={() => job.refetch()} /></PageBody></>

  const meta = j ? [
    ['เงินเดือน', salaryRange(j.salary_min, j.salary_max)], ['ระดับ', j.level ?? '–'], ['รูปแบบงาน', j.work_mode ?? '–'],
    ['จังหวัด', j.province ?? '–'], ['ประสบการณ์', experience(j.experience_years)],
    ['วุฒิการศึกษา', j.education_level ?? '–'], ['ประเภทการจ้าง', j.employment_type ?? '–'],
    ['แหล่งข้อมูล', sourceLabel(j.source)], ['เก็บข้อมูลล่าสุด', when(j.last_updated_at)],
  ] : []
  const withStd = j?.skills.filter((s) => s.standards?.length).length ?? 0
  const hard = j?.skills.filter((s) => s.type === 'hard') ?? []
  const soft = j?.skills.filter((s) => s.type === 'soft') ?? []

  return (
    <>
      <PageHeader crumbs={['ค้นหางาน', j?.title ?? '…']} back={backTo} title={j?.title ?? 'กำลังโหลด…'}
        subtitle={j && <span className="flex flex-wrap items-center gap-2.5 pt-1">
          <CompanyLogo src={j.company_logo} name={j.company} size={40} />
          {j.is_ai_related && <span className="rounded-[5px] bg-navy px-1.5 py-0.5 text-[10px] font-bold text-white">AI</span>}
          <span className="flex flex-col"><span className="font-medium text-ink">{j.company ?? 'ไม่ระบุบริษัท'}</span>
            <span>{j.province ?? 'ไม่ระบุจังหวัด'} · {sourceLabel(j.source)} · ประกาศ {date(j.posted_at)}</span></span>
        </span>} />
      <PageBody>
        {!j ? <Skeleton className="h-80" /> : (
          <div className="grid items-start gap-5 pb-24 lg:grid-cols-[minmax(0,1fr)_340px] lg:gap-10 lg:pb-0">
            <div className="flex min-w-0 flex-col gap-6 lg:gap-8">
              {state?.similarity != null && (
                <div className="flex items-center gap-3.5 rounded-[18px] bg-navy p-4 text-white lg:hidden">
                  <Ring value={state.similarity} size={56} stroke={6} track="#1A2C4D" color="#9DB8E3" label={`ตรงกับคำค้น ${Math.round(state.similarity * 100)}%`}>
                    <span className="num text-[13px] font-semibold">{Math.round(state.similarity * 100)}%</span>
                  </Ring>
                  <div className="flex min-w-0 flex-col"><span className="text-[15px] font-semibold">ตรงกับคำค้นของคุณ</span><span className="truncate text-[13px] text-navy-text">“{state.query}”</span></div>
                </div>
              )}
              <div className="grid grid-cols-2 gap-2 lg:hidden">
                {meta.slice(0, 4).map(([k, v]) => (
                  <div key={k} className="flex flex-col rounded-[14px] bg-white px-3.5 py-3"><span className="text-xs text-muted">{k}</span><span className="num text-base font-semibold">{v}</span></div>
                ))}
              </div>
              <section className="flex flex-col gap-4 rounded-2xl border border-line bg-white p-5 lg:p-[22px]">
                <div className="flex items-center justify-between"><h2 className="card-title">ทักษะที่ระบบสกัดได้</h2><span className="text-xs text-muted">มีมาตรฐานรองรับ {withStd}/{j.skills.length} ทักษะ</span></div>
                {[['Hard skills', hard], ['Soft skills', soft]].map(([label, list]) => (list as typeof hard).length > 0 && (
                  <div key={label as string} className="flex flex-col gap-2">
                    <span className="text-xs font-semibold text-muted">{label as string}</span>
                    <div className="flex flex-wrap gap-1.5">
                      {(list as typeof hard).map((s) => {
                        const match = queryWords.includes(s.name.toLowerCase())
                        return (
                          <span key={s.id} title={s.standards?.length ? s.standards.join('\n') : 'ยังไม่มีมาตรฐานรองรับ'}
                            className={clsx('chip px-3 py-1.5 text-[13px]', s.type === 'soft' ? 'border border-line' : s.is_ai_skill ? 'bg-navy font-medium text-white' : 'border border-[#EDEDF0] bg-canvas',
                              s.is_required === false && 'border-dashed opacity-80')}>
                            {s.name}{match && <Icon name="check" size={12} strokeWidth={3} className={s.is_ai_skill ? 'text-brand-400' : 'text-brand-700'} />}
                            {!!s.standards?.length && <span className="ml-1 rounded bg-brand-100 px-1 text-[10px] font-semibold text-brand-800">{s.standards.length}</span>}
                          </span>
                        )
                      })}
                    </div>
                  </div>
                ))}
                <div className="flex flex-wrap gap-4 border-t border-line-soft pt-3 text-xs text-muted">
                  <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded bg-navy" />ทักษะ AI</span>
                  {queryWords && <span className="flex items-center gap-1.5"><Icon name="check" size={12} strokeWidth={3} className="text-brand-700" />ตรงกับคำค้น</span>}
                  <span className="flex items-center gap-1.5"><span className="rounded bg-brand-100 px-1 text-[10px] font-semibold text-brand-800">n</span>จำนวนมาตรฐานที่รองรับ (ชี้เพื่อดู)</span>
                  <span className="flex items-center gap-1.5"><span className="h-3 w-5 rounded border border-dashed border-line" />ไม่บังคับ / พิจารณาพิเศษ</span>
                </div>
              </section>
              <section className="flex flex-col gap-3">
                <h2 className="card-title">รายละเอียดงาน</h2>
                <p className="whitespace-pre-line text-[15px] leading-[1.8] text-ink-2">{j.description || 'ประกาศนี้ไม่มีคำอธิบายงาน'}</p>
                {j.qualification && (<><h3 className="pt-2 text-[15px] font-semibold">คุณสมบัติผู้สมัคร</h3>
                  <p className="whitespace-pre-line text-[15px] leading-[1.8] text-ink-2">{j.qualification}</p></>)}
                {j.welfare && (<><h3 className="pt-2 text-[15px] font-semibold">สวัสดิการ</h3>
                  <p className="whitespace-pre-line text-[15px] leading-[1.8] text-ink-2">{j.welfare}</p></>)}
                <div className="flex items-center gap-2.5 rounded-xl border border-line-soft bg-[#FAFAFA] px-3.5 py-3 text-[13px] text-ink-3">
                  <Icon name="lock" size={16} />ไม่แสดงชื่อ เบอร์โทร หรืออีเมลผู้ติดต่อ ตาม PDPA
                </div>
              </section>
            </div>

            <aside className="hidden flex-col gap-5 rounded-2xl border border-line p-[22px] shadow-[0_8px_24px_rgba(16,24,40,0.06)] lg:sticky lg:top-6 lg:flex">
              {state?.similarity != null && (
                <div className="flex items-center gap-4">
                  <Ring value={state.similarity} label={`ตรงกับคำค้น ${Math.round(state.similarity * 100)}%`}>
                    <span className="num text-base font-semibold">{Math.round(state.similarity * 100)}%</span>
                  </Ring>
                  <div className="flex min-w-0 flex-col"><span className="text-sm font-semibold">ตรงกับคำค้นของคุณ</span><span className="truncate text-xs text-muted">“{state.query}”</span></div>
                </div>
              )}
              <dl className="flex flex-col border-t border-line-soft">
                {meta.map(([k, v]) => (
                  <div key={k} className="flex min-h-[42px] items-center justify-between border-b border-line-soft text-sm"><dt className="text-muted">{k}</dt><dd className="num font-medium">{v}</dd></div>
                ))}
              </dl>
              <a href={j.source_url} target="_blank" rel="noreferrer" className="btn-primary h-[46px]">เปิดประกาศต้นฉบับ<Icon name="external" size={15} /></a>
              <button type="button" onClick={copy} className="btn-outline h-11">{copied ? 'คัดลอกแล้ว' : 'คัดลอกลิงก์'}</button>
            </aside>
          </div>
        )}
      </PageBody>
      {j && (
        <div className="fixed inset-x-0 bottom-0 z-40 flex gap-2.5 border-t border-line bg-white px-4 pt-3 lg:hidden" style={{ paddingBottom: 'max(env(safe-area-inset-bottom), 16px)' }}>
          <button type="button" onClick={copy} aria-label={copied ? 'คัดลอกแล้ว' : 'คัดลอกลิงก์'} className="flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-[14px] border border-line"><Icon name={copied ? 'check' : 'link'} size={20} /></button>
          <a href={j.source_url} target="_blank" rel="noreferrer" className="flex h-[52px] flex-1 items-center justify-center gap-2 rounded-[15px] bg-ink text-base font-semibold text-white">เปิดประกาศต้นฉบับ<Icon name="external" size={16} /></a>
        </div>
      )}
    </>
  )
}