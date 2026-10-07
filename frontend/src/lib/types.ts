export type Level = 'Entry' | 'Mid' | 'Senior'
export type WorkMode = 'Onsite' | 'Hybrid' | 'Remote'

export interface JobFilterParams {
  days?: number
  source?: string
  province?: string
  work_mode?: string
  level?: string
}

export interface Summary {
  total_jobs: number
  total_jobs_prev: number | null
  new_7d: number
  new_7d_prev: number
  ai_jobs: number
  ai_share: number
  ai_share_prev: number | null
  median_salary: number | null
  median_salary_prev: number | null
  salary_disclosed_share: number
  curriculum_match: number | null
  window_days: number
  companies: number
  unique_skills: number
  job_skill_pairs: number
  courses: number
  last_scraped_at: string | null
  std_coverage: number | null
  std_skills: number | null
}

export interface TopSkill { skill: string; type?: string; jobs?: number; pct: number; delta_pct: number | null; is_ai_skill: boolean }
export interface SalaryBand { band: string; min: number; max: number | null; n: number }
export interface StandardCoverage { standard: string; label: string; is_total: boolean; skills: number; unique_pct: number; weighted_pct: number }
export interface PipelineStatus {
  jobs: number; extracted: number; jobs_embedded: number; skills: number; skills_embedded: number; skills_std_mapped: number
  courses: number; course_links: number; first_scraped_at: string | null; last_scraped_at: string | null; last_extracted_at: string | null
  by_source: { source: string; jobs: number }[]
}
export interface RelatedSkill { skill: string; similarity: number }
export interface SalaryRow { level: string; n: number; min: number; p25: number; median: number; p75: number; max: number }
export interface AiTrend {
  weeks: { week_start: string; total: number; ai: number; share: number }[]
  groups: { group: string; pct: number; delta_pct: number | null }[]
  top_ai_skills?: { skill: string; group: string; jobs: number }[]
  bucket?: 'week' | 'day'
  min_jobs_per_day?: number
}
export interface Facet { value: string; count: number }
export interface FilterOptions { sources: Facet[]; provinces: Facet[]; levels: Facet[]; work_modes: Facet[] }

export interface SearchFilters {
  min_salary?: number | null
  level?: Level[]
  work_mode?: WorkMode[]
  province?: string[]
  source?: string[]
}
export interface JobCard {
  job_id: number
  title: string
  company: string | null
  province: string | null
  salary_min: number | null
  salary_max: number | null
  level: string | null
  work_mode: string | null
  source: string
  source_url: string
  top_skills: string[]
  similarity: number | null
  posted_at?: string | null
  company_logo?: string | null
  similar_postings?: number
}
export interface Suggestion { text: string; jobs: number }
export interface SearchSuggest { skills: Suggestion[]; titles: Suggestion[] }
export interface SearchResponse { mode?: 'semantic' | 'browse'; took_ms: { embed: number; db: number }; results: JobCard[]; page?: number; page_size?: number; total?: number; max_results?: number; capped?: boolean }

export interface SkillOut { id: number; name: string; type: 'hard' | 'soft'; is_ai_skill: boolean; is_required?: boolean; standards?: string[] }
export interface JobDetail {
  id: number
  title: string
  company: string | null
  company_logo?: string | null
  province: string | null
  salary_min: number | null
  salary_max: number | null
  level: string | null
  work_mode: string | null
  source: string
  source_url: string
  description: string | null
  qualification?: string | null
  welfare?: string | null
  experience_years?: number | null
  education_level?: string | null
  employment_type?: string | null
  seniority_raw?: string | null
  is_ai_related: boolean
  posted_at: string | null
  last_updated_at: string | null
  skills: SkillOut[]
}

export interface CourseSkillLink { name: string; method: 'exact' | 'semantic' | 'manual' | string; similarity: number | null; jobs: number }
export interface Course {
  code: string
  name_th: string
  name_en: string | null
  description: string
  description_en?: string | null
  year: number | null
  credits: string | null
  category?: string | null
  course_group?: string | null
  prerequisite?: string[]
  skills: string[]
  skill_links?: CourseSkillLink[]
}
export type CourseInput = Omit<Course, 'skills' | 'skill_links' | 'prerequisite'>

export interface GapCourse { code: string; name: string; name_en?: string | null; category?: string | null; contribution: number; relevance: number; skill_count?: number; covered_skills: string[] }
export interface GapMissing { skill: string; demand_pct: number; jobs?: number; coverage: number; priority: number; suggested_course: string; suggested_course_code: string; suggested_topic?: string; suggested_similarity?: number | null; is_ai_skill?: boolean }
export interface GapPoint { skill: string; demand_pct: number; coverage: number; is_ai_skill: boolean; jobs?: number; courses?: number; course_names?: string[] }
export interface Gap {
  overall_match_score: number
  overall_match_score_no_manual?: number
  selected_courses?: string[]
  total_courses?: number
  methods?: Record<string, number>
  skills_analyzed: number
  covered: number
  missing: number
  missing_min_jobs?: number
  missing_min_jobs_threshold?: number
  courses: GapCourse[]
  missing_skills: GapMissing[]
  matrix: GapPoint[]
  heatmap: { courses: string[]; course_codes?: string[]; skills: string[]; values: number[][] }
  params: { top_n: number; tau: number; cov_threshold: number; matrix_demand_threshold: number; relevance_top?: number }
  total_jobs: number
  computed_at: string
}

export type RunStatus = 'queued' | 'running' | 'success' | 'warning' | 'failed' | 'cancelled'
export type StepStatus = 'pending' | 'running' | 'success' | 'warning' | 'failed' | 'skipped' | 'cancelled'
export interface RunStep { key: string; label: string; status: StepStatus; started_at: string | null; finished_at: string | null; summary: string; counts: Record<string, unknown>; feed_count?: number | null }
export type FeedKind = 'new' | 'updated' | 'bumped' | 'partial' | 'failed'
export interface FieldChange { field: string; label: string; old: string | null; new: string | null }
/** One job scraped in a run (GET /crawler/runs/{id}/feed), newest first. */
export interface FeedItem {
  kind: FeedKind
  url: string
  title?: string
  company?: string
  salary?: string
  location?: string
  post_date?: string
  at?: string
  changed?: string[]        // fields the scraper saw change
  before?: string           // date the job had before this run
  missing?: string[]
  job_id: number | null     // the job in our database (null until the load step ran)
  db_changes: { reextract: boolean; fields: FieldChange[] } | null
}
export interface Run {
  id: number
  source: string
  trigger: 'manual' | 'scheduled'
  status: RunStatus
  started_at: string
  finished_at: string | null
  found: number
  inserted: number
  duplicated: number
  pages_done: number
  pages_total: number | null
  log: string[]
  steps?: RunStep[]
  error_message: string | null
}
export interface Source {
  source: string
  label?: string
  categories?: string[]
  problems?: string[]
  mode: 'interval' | 'daily'
  every_hours: number | null
  daily_at: string | null
  enabled: boolean
  next_run_at: string | null
  last_run: Run | null
}
export interface CrawlerStatus { active_run_id: number | null; process_problems: string[]; extract_limit_per_run: number; auto_delay: string; robots_txt: boolean }
export interface ScheduleInput { mode: 'interval' | 'daily'; every_hours?: number | null; daily_at?: string | null; enabled: boolean }
