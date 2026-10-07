import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { NavLink, useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { sourceLabel } from '../../lib/format'
import { Icon, type IconName } from '../icons'
import { LogoMark, Wordmark } from '../Logo'

function Item({ to, icon, label, badge }: { to: string; icon: IconName; label: string; badge?: boolean }) {
  return (
    <NavLink to={to} end={to === '/'}
      className={({ isActive }) => clsx('flex min-h-10 items-center gap-2.5 rounded-[10px] px-2.5 text-sm transition-colors',
        isActive ? 'bg-navy-600 font-medium text-white shadow-[inset_0_0_0_1px_#243A63]' : 'text-[#C3D0E6] hover:bg-navy-700 hover:text-white')}>
      {({ isActive }) => (
        <>
          <Icon name={icon} strokeWidth={1.9} className={isActive ? 'text-brand-400' : 'text-navy-dim'} />
          <span className="flex-1">{label}</span>
          {badge && (
            <span className="flex items-center gap-1 rounded-full bg-good-deep px-1.5 py-0.5 text-[11px] font-semibold text-good-bright">
              <span className="h-1.5 w-1.5 rounded-full bg-good-bright" />Live
            </span>
          )}
        </>
      )}
    </NavLink>
  )
}

export function Sidebar({ className }: { className?: string }) {
  const { isAdmin, signOut } = useAuth()
  const navigate = useNavigate()
  const runs = useQuery({ queryKey: ['runs'], queryFn: () => api.runs(10), enabled: isAdmin, refetchInterval: 5000 })
  const running = runs.data?.find((r) => r.status === 'running' || r.status === 'queued')
  // progress = pipeline steps done (the page count of a crawl is not known in advance)
  const steps = running?.steps ?? []
  const done = steps.filter((s) => !['pending', 'running'].includes(s.status)).length
  const current = steps.find((s) => s.status === 'running')
  const progress = steps.length ? done / steps.length : 0

  return (
    <nav aria-label="เมนูหลัก" className={clsx('w-60 shrink-0 flex-col gap-0.5 rounded-[18px] bg-navy px-3 py-4 text-white', className)}>
      <div className="flex items-center gap-2.5 px-2 pb-5 pt-1.5">
        <LogoMark size={36} dark />
        <div className="flex min-w-0 flex-col">
          <Wordmark dark />
          <span className="text-xs text-navy-text">วิศวกรรมคอมพิวเตอร์ · ม.กาฬสินธุ์</span>
        </div>
      </div>
      <div className="px-2.5 py-1.5 text-xs font-medium text-navy-dim">ทั่วไป</div>
      <Item to="/" icon="dashboard" label="ภาพรวมตลาดแรงงาน" />
      <Item to="/search" icon="search" label="ค้นหางาน" />
      <Item to="/gap" icon="target" label="วิเคราะห์หลักสูตร" />
      {isAdmin && (
        <>
          <div className="px-2.5 pb-1.5 pt-4 text-xs font-medium text-navy-dim">ผู้ดูแลระบบ</div>
          <Item to="/admin/crawler" icon="refresh" label="ควบคุม Crawler" badge={!!running} />
          <Item to="/admin/courses" icon="book" label="จัดการรายวิชา" />
        </>
      )}
      <div className="mt-auto flex flex-col gap-3">
        {running && (
          <div className="flex flex-col gap-2.5 rounded-[14px] border border-[#1F355C] bg-navy-700 p-3.5">
            <div className="flex items-center justify-between text-[13px]">
              <span className="font-semibold">{sourceLabel(running.source)} กำลังรัน</span>
              <span className="num font-mono text-xs text-navy-text">{Math.round(progress * 100)}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-navy-600"><div className="h-1.5 rounded-full bg-brand-400" style={{ width: `${progress * 100}%` }} /></div>
            <span className="text-xs text-navy-text">
              {steps.length ? `ขั้น ${Math.min(done + 1, steps.length)}/${steps.length} · ${current?.label ?? 'กำลังเริ่ม'}` : 'กำลังเริ่ม'}
              {running.pages_done ? ` · หน้า ${running.pages_done}` : ''}
            </span>
          </div>
        )}
        {isAdmin && (
          <div className="flex items-center gap-2.5 px-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-200 text-xs font-semibold text-brand-800">AD</div>
            <span className="flex-1 text-[13px] font-medium">ผู้ดูแลระบบ</span>
            <button type="button" aria-label="ออกจากระบบ" onClick={() => { signOut(); navigate('/') }}
              className="flex h-9 w-9 items-center justify-center rounded-lg text-navy-text hover:bg-navy-700 hover:text-white">
              <Icon name="logout" size={16} />
            </button>
          </div>
        )}
      </div>
    </nav>
  )
}