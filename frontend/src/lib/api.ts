import { readToken } from './auth'
import { mockRequest } from './mock'
import type {
  AiTrend, Course, CrawlerStatus, CourseInput, FeedItem, FilterOptions, Gap, JobDetail, JobFilterParams, PipelineStatus, RelatedSkill, Run, SalaryBand,
  SalaryRow, ScheduleInput, SearchFilters, SearchResponse, Source, StandardCoverage, SearchSuggest, Summary, TopSkill } from './types'

const BASE = import.meta.env.VITE_API_URL ?? '/api/v1'
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message)
  }
}

function qs(params: object = {}): string {
  const p = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') p.set(k, String(v))
  })
  const s = p.toString()
  return s ? `?${s}` : ''
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (USE_MOCK) return mockRequest<T>(path, init)
  const token = readToken()
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  })
  if (!res.ok) {
    let code = 'HTTP_ERROR'
    let message = `คำขอล้มเหลว (${res.status})`
    try {
      const body = await res.json()
      code = body?.error?.code ?? code
      message = body?.error?.message ?? message
    } catch { /* not JSON */ }
    if (res.status === 401) window.dispatchEvent(new Event('air:auth-expired'))
    throw new ApiError(res.status, code, message)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

const json = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string; expires_at: string }>('/auth/login', json('POST', { username, password })),

  summary: (f: JobFilterParams) => request<Summary>(`/analytics/summary${qs(f)}`),
  topSkills: (type: 'hard' | 'soft' | 'all', limit: number, f: JobFilterParams) => request<TopSkill[]>(`/analytics/top-skills${qs({ ...f, type, limit })}`),
  salary: (f: JobFilterParams) => request<SalaryRow[]>(`/analytics/salary-distribution${qs(f)}`),
  salaryHistogram: (f: JobFilterParams) => request<SalaryBand[]>(`/analytics/salary-histogram${qs(f)}`),
  aiTrend: (f: JobFilterParams) => request<AiTrend>(`/analytics/ai-trend${qs({ ...f, weeks: 8 })}`),
  standards: () => request<StandardCoverage[]>('/analytics/standards'),
  pipeline: () => request<PipelineStatus>('/analytics/pipeline'),
  filters: () => request<FilterOptions>('/analytics/filters'),

  search: (query: string, filters: SearchFilters, page = 1, page_size = 20) => request<SearchResponse>('/search', json('POST', { query, filters, page, page_size })),
  suggest: (q: string, limit = 6) => request<SearchSuggest>(`/search/suggest${qs({ q, limit })}`),
  relatedSkills: (q: string, k = 10) => request<RelatedSkill[]>(`/search/related-skills${qs({ q, k })}`),
  job: (id: number) => request<JobDetail>(`/jobs/${id}`),

  sources: () => request<Source[]>('/crawler/sources'),
  runs: (limit = 20, source?: string) => request<Run[]>(`/crawler/runs${qs({ limit, source })}`),
  updateSchedule: (source: string, body: ScheduleInput) => request<Source>(`/crawler/sources/${source}/schedule`, json('PUT', body)),
  runNow: (source: string) => request<{ run_id: number }>(`/crawler/sources/${source}/runs`, json('POST')),
  crawlerStatus: () => request<CrawlerStatus>('/crawler/status'),
  processPending: () => request<{ run_id: number }>('/crawler/process', json('POST')),
  run: (id: number) => request<Run>(`/crawler/runs/${id}`),
  runFeed: (id: number) => request<FeedItem[]>(`/crawler/runs/${id}/feed`),
  cancelRun: (id: number) => request<{ ok: boolean }>(`/crawler/runs/${id}/cancel`, json('POST')),

  courses: () => request<Course[]>('/curriculum/courses'),
  createCourse: (body: CourseInput) => request<Course>('/curriculum/courses', json('POST', body)),
  updateCourse: (code: string, body: Partial<CourseInput>) => request<Course>(`/curriculum/courses/${encodeURIComponent(code)}`, json('PUT', body)),
  deleteCourse: (code: string) => request<void>(`/curriculum/courses/${encodeURIComponent(code)}`, json('DELETE')),
  extractCourse: (code: string) => request<Course>(`/curriculum/courses/${encodeURIComponent(code)}/extract`, json('POST')),
  setCourseSkills: (code: string, skills: string[]) => request<Course>(`/curriculum/courses/${encodeURIComponent(code)}/skills`, json('PUT', { skills })),

  gap: (courses: string[] = [], excludeManual = false) =>
    request<Gap>(`/gap-analysis${qs({ courses: courses.join(','), exclude_manual: excludeManual || undefined })}`),
  recalcGap: () => request<Gap>('/gap-analysis/recalculate', json('POST')),
  skillNames: (q: string) => request<string[]>(`/curriculum/skills${qs({ q, limit: 20 })}`),
}

/** Downloads the full log file of a pipeline run (admin only). */
export async function downloadRunLog(id: number): Promise<void> {
  let text: string
  if (USE_MOCK) {
    text = (await api.run(id)).log.join('\n')
  } else {
    const token = readToken()
    const res = await fetch(`${BASE}/crawler/runs/${id}/log`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    if (!res.ok) throw new ApiError(res.status, 'LOG_FAILED', 'ดาวน์โหลด log ไม่สำเร็จ')
    text = await res.text()
  }
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = `run_${id}.log`
  a.click()
  URL.revokeObjectURL(url)
}

/** Downloads the gap CSV (UTF-8 with BOM so Thai opens correctly in Excel). */
export async function downloadGapCsv(courses: string[] = [], excludeManual = false): Promise<void> {
  let blob: Blob
  if (USE_MOCK) {
    const { mockGapCsv } = await import('./mock')
    blob = new Blob([mockGapCsv()], { type: 'text/csv;charset=utf-8' })
  } else {
    const res = await fetch(`${BASE}/gap-analysis/export.csv${qs({ courses: courses.join(','), exclude_manual: excludeManual || undefined })}`)
    if (!res.ok) throw new ApiError(res.status, 'EXPORT_FAILED', 'ส่งออก CSV ไม่สำเร็จ')
    blob = await res.blob()
  }
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'gap-analysis.csv'
  a.click()
  URL.revokeObjectURL(url)
}
