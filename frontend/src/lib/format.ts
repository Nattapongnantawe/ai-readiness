const nf = new Intl.NumberFormat('en-US')

export const num = (n: number | null | undefined) => (n == null ? '–' : nf.format(Math.round(n)))
export const baht = (n: number | null | undefined) => (n == null ? '–' : `฿${nf.format(Math.round(n))}`)
export const bahtK = (n: number | null | undefined) => (n == null ? '–' : `฿${Math.round(n / 1000)}k`)
export const pct = (x: number | null | undefined, digits = 1) => (x == null ? '–' : `${(x * 100).toFixed(digits)}%`)

export function salaryRange(min: number | null, max: number | null, short = false): string {
  const f = short ? bahtK : baht
  if (min != null && max != null) return `${f(min)}–${f(max).replace('฿', '')}`
  if (min != null) return `${f(min)}+`
  if (max != null) return `≤ ${f(max)}`
  return 'ไม่ระบุเงินเดือน'
}

const dtf = new Intl.DateTimeFormat('th-TH', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
const tf = new Intl.DateTimeFormat('th-TH', { hour: '2-digit', minute: '2-digit' })
const df = new Intl.DateTimeFormat('th-TH', { day: 'numeric', month: 'short', year: 'numeric' })

export function when(iso: string | null | undefined): string {
  if (!iso) return '–'
  const d = new Date(iso)
  const now = new Date()
  const days = Math.floor((new Date(now.toDateString()).getTime() - new Date(d.toDateString()).getTime()) / 86400000)
  if (days === 0) return `วันนี้ ${tf.format(d)}`
  if (days === 1) return `เมื่อวาน ${tf.format(d)}`
  if (days === -1) return `พรุ่งนี้ ${tf.format(d)}`
  return dtf.format(d)
}
const dmf = new Intl.DateTimeFormat('th-TH', { day: 'numeric', month: 'short' })
export const dayMonth = (iso: string | null | undefined) => (iso ? dmf.format(new Date(iso)) : '–')
export const date = (iso: string | null | undefined) => (iso ? df.format(new Date(iso)) : '–')
export const time = (iso: string | null | undefined) => (iso ? tf.format(new Date(iso)) : '–')

export function duration(from: string, to: string | null): string {
  const ms = (to ? new Date(to) : new Date()).getTime() - new Date(from).getTime()
  const m = Math.max(0, Math.round(ms / 60000))
  if (m < 60) return `${m} นาที`
  return `${Math.floor(m / 60)} ชม. ${m % 60} นาที`
}

/** Experience requirement in years: 0 → no experience needed. */
export const experience = (y: number | null | undefined) => (y == null ? '–' : y <= 0 ? 'ไม่ต้องมีประสบการณ์' : `${Number.isInteger(y) ? y : y.toFixed(1)} ปีขึ้นไป`)

export const sourceLabel = (s: string) => ({ jobthai: 'JobThai', jobbkk: 'JobBKK', process: 'งานที่ค้าง', demo: 'Demo' }[s] ?? s)
export const sourceInitials = (s: string) => ({ jobthai: 'JT', jobbkk: 'JB', process: 'PR' }[s] ?? s.slice(0, 2).toUpperCase())