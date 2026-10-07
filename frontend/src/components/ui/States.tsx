import type { ReactNode } from 'react'

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-line-soft ${className}`} />
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : 'เกิดข้อผิดพลาด'
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-2xl border border-maroon-200 bg-maroon-soft p-4 text-sm text-maroon">
      <span>โหลดข้อมูลไม่สำเร็จ: {message}</span>
      {onRetry && <button type="button" onClick={onRetry} className="btn-outline h-9">ลองใหม่</button>}
    </div>
  )
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-line bg-white px-6 py-10 text-center">
      <span className="text-[15px] font-semibold">{title}</span>
      {children && <div className="max-w-sm text-sm text-muted">{children}</div>}
    </div>
  )
}
