import clsx from 'clsx'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../../lib/auth'
import { Icon, type IconName } from '../icons'

function Tab({ to, icon, label }: { to: string; icon: IconName; label: string }) {
  return (
    <NavLink to={to} end={to === '/'} className={({ isActive }) => clsx('flex min-h-[52px] flex-col items-center justify-center gap-1 text-[11px]',
      isActive ? 'font-semibold text-white' : 'font-medium text-navy-text')}>
      {({ isActive }) => (
        <>
          <span className={clsx('flex h-7 w-[52px] items-center justify-center rounded-full', isActive && 'bg-navy-500')}>
            <Icon name={icon} size={20} strokeWidth={1.9} />
          </span>
          {label}
        </>
      )}
    </NavLink>
  )
}

export function TabBar({ className }: { className?: string }) {
  const { isAdmin } = useAuth()
  return (
    <nav aria-label="แท็บหลัก" className={clsx('fixed inset-x-0 bottom-0 z-30 grid border-t border-navy-600 bg-navy px-3 pt-2', className)}
      style={{ gridTemplateColumns: `repeat(${isAdmin ? 4 : 3}, minmax(0, 1fr))`, paddingBottom: 'max(env(safe-area-inset-bottom), 12px)' }}>
      <Tab to="/" icon="dashboard" label="ภาพรวม" />
      <Tab to="/search" icon="search" label="ค้นหา" />
      <Tab to="/gap" icon="target" label="หลักสูตร" />
      {isAdmin && <Tab to="/admin/crawler" icon="refresh" label="Crawler" />}
    </nav>
  )
}
