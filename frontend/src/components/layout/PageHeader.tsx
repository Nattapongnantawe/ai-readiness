import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Icon } from '../icons'
import { LogoMark, Wordmark } from '../Logo'

interface Props {
  crumbs: string[]
  title: string
  subtitle?: ReactNode
  actions?: ReactNode
  topRight?: ReactNode
  back?: string
}

export function PageHeader({ crumbs, title, subtitle, actions, topRight, back }: Props) {
  return (
    <header>
      <div className="hidden h-[60px] items-center justify-between border-b border-line-soft pl-8 pr-5 lg:flex">
        <div className="flex items-center gap-2 text-sm text-muted">
          {back && (
            <Link to={back} aria-label="ย้อนกลับ" className="mr-1 flex h-9 w-9 items-center justify-center rounded-[9px] border border-line text-ink-3 hover:bg-canvas">
              <Icon name="chevronLeft" size={16} />
            </Link>
          )}
          {crumbs.map((c, i) => (
            <span key={c} className="flex items-center gap-2">
              {i > 0 && <Icon name="chevronRight" size={14} />}
              <span className={i === crumbs.length - 1 ? 'font-medium text-ink' : ''}>{c}</span>
            </span>
          ))}
        </div>
        <div className="flex items-center gap-2">
          {topRight}
          <Link to="/search" className="flex h-10 w-[300px] items-center gap-2.5 rounded-[10px] border border-line bg-[#FAFAFA] px-3 text-sm text-muted hover:border-brand-300">
            <Icon name="search" size={16} />
            <span>ค้นหางาน ทักษะ หรือตำแหน่ง</span>
          </Link>
        </div>
      </div>
      <div className="flex flex-col gap-4 px-4 pt-[max(env(safe-area-inset-top),20px)] lg:flex-row lg:items-end lg:justify-between lg:gap-6 lg:px-8 lg:pt-7">
        <div className="flex flex-col gap-1.5">
          {back ? (
            <Link to={back} aria-label="ย้อนกลับ" className="mb-2 flex h-11 w-11 items-center justify-center rounded-full bg-white text-ink lg:hidden">
              <Icon name="chevronLeft" />
            </Link>
          ) : (
            <div className="mb-1 flex items-center gap-2 lg:hidden">
              <LogoMark size={22} />
              <Wordmark size={14} />
            </div>
          )}
          <h1 className="text-[30px] font-semibold leading-tight tracking-[-0.035em] lg:text-[28px] lg:tracking-[-0.025em]">{title}</h1>
          {subtitle && <p className="text-[13px] text-muted lg:text-sm">{subtitle}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </header>
  )
}

export function PageBody({ children }: { children: ReactNode }) {
  return <div className="flex flex-col gap-4 px-4 pb-8 pt-4 lg:gap-5 lg:px-8 lg:pt-5">{children}</div>
}
