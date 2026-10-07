import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useEffect, useState, type FormEvent } from 'react'
import { Icon } from '../../components/icons'
import { PageBody, PageHeader } from '../../components/layout/PageHeader'
import { Empty, ErrorState, Skeleton } from '../../components/ui/States'
import { api } from '../../lib/api'
import type { Course, CourseInput } from '../../lib/types'

const blank: CourseInput = { code: '', name_th: '', name_en: '', description: '', description_en: '', year: null, credits: '3(2-2-5)', category: 'major_elective', course_group: null }
const CATEGORY: Record<string, string> = {
  general_education: 'ศึกษาทั่วไป', core: 'วิชาแกน', major_required: 'เฉพาะด้าน', major_elective: 'วิชาเลือก', field_experience: 'สัมมนา/โครงงาน/สหกิจ',
}
const METHOD: Record<string, { label: string; cls: string }> = {
  exact: { label: 'ตรงตัว', cls: 'bg-brand-100 text-brand-800' },
  semantic: { label: 'ความหมาย', cls: 'bg-canvas text-ink-3' },
  manual: { label: 'ผู้วิจัยตรวจ', cls: 'bg-maroon-soft text-maroon' },
}

function Editor({ course, onClose }: { course: Course | null; onClose: () => void }) {
  const qc = useQueryClient()
  const isNew = course === null
  const [form, setForm] = useState<CourseInput>(course ?? blank)
  const [skills, setSkills] = useState<string[]>(course?.skills ?? [])
  const [newSkill, setNewSkill] = useState('')
  useEffect(() => { setForm(course ?? blank); setSkills(course?.skills ?? []) }, [course])

  const done = (c?: Course) => { qc.invalidateQueries({ queryKey: ['courses'] }); if (c) setSkills(c.skills) }
  const save = useMutation({
    mutationFn: async () => {
      const saved = isNew ? await api.createCourse(form) : await api.updateCourse(course!.code, {
        name_th: form.name_th, name_en: form.name_en, description: form.description, description_en: form.description_en,
        credits: form.credits, category: form.category, course_group: form.course_group })
      if (!isNew && skills.join() !== saved.skills.join()) return api.setCourseSkills(saved.code, skills)
      return saved
    },
    onSuccess: (c) => { done(c); onClose() },
  })
  const extract = useMutation({ mutationFn: () => api.extractCourse(course!.code), onSuccess: done })
  const set = (k: keyof CourseInput) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value })
  const links = new Map((course?.skill_links ?? []).map((l) => [l.name, l]))
  const addSkill = () => { const v = newSkill.trim(); if (v && !skills.includes(v)) setSkills([...skills, v]); setNewSkill('') }
  const submit = (e: FormEvent) => { e.preventDefault(); save.mutate() }

  return (
    <form onSubmit={submit} aria-label={isNew ? 'เพิ่มรายวิชา' : `แก้ไข ${course?.name_th ?? ''}`}
      className="fixed inset-0 z-50 flex flex-col gap-4 overflow-y-auto bg-white p-5 lg:static lg:z-auto lg:w-[380px] lg:shrink-0 lg:border-l lg:border-line lg:p-6 lg:shadow-[-12px_0_32px_rgba(16,24,40,0.05)]">
      <div className="flex items-center justify-between">
        <div className="flex flex-col"><span className="text-xs text-muted">{isNew ? 'เพิ่มรายวิชา' : 'แก้ไขรายวิชา'}</span><h2 className="text-lg font-semibold tracking-[-0.01em]">{form.name_th || 'รายวิชาใหม่'}</h2></div>
        <button type="button" aria-label="ปิด" onClick={onClose} className="flex h-10 w-10 items-center justify-center rounded-[9px] border border-line"><Icon name="close" size={14} strokeWidth={2.4} /></button>
      </div>
      <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-3">ชื่อวิชา (ไทย)<input required className="input" value={form.name_th} onChange={set('name_th')} /></label>
      <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-3">ชื่อวิชา (อังกฤษ)<input className="input" value={form.name_en ?? ''} onChange={set('name_en')} /></label>
      <div className="grid grid-cols-3 gap-2.5">
        <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-3">รหัส<input required disabled={!isNew} className="input disabled:bg-canvas" value={form.code} onChange={set('code')} /></label>
        <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-3">หมวด
          <select className="input" value={form.category ?? ''} onChange={set('category')}>
            {Object.entries(CATEGORY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select></label>
        <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-3">หน่วยกิต<input className="input" value={form.credits ?? ''} onChange={set('credits')} /></label>
      </div>
      <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-3">คำอธิบายรายวิชา (ไทย)
        <textarea rows={5} className="input h-auto py-2.5 leading-relaxed" value={form.description} onChange={set('description')} placeholder="คำอธิบายรายวิชาจาก มคอ.2" />
      </label>
      <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-3">คำอธิบายรายวิชา (อังกฤษ)
        <textarea rows={5} className="input h-auto py-2.5 leading-relaxed" value={form.description_en ?? ''} onChange={set('description_en')} placeholder="Course description (English) — ใช้จับคู่ทักษะแบบตรงตัว" />
      </label>
      {!isNew && (
        <div className="flex flex-col gap-2.5 rounded-xl border border-brand-150 bg-brand-50 p-3.5">
          <div className="flex items-center justify-between">
            <span className="text-[13px] font-semibold text-brand-800">ทักษะที่สกัดได้ · {skills.length}</span>
            <button type="button" onClick={() => extract.mutate()} disabled={extract.isPending} className="h-8 rounded-md px-2 text-[13px] font-medium text-brand-800 hover:bg-brand-100">
              {extract.isPending ? 'กำลังสกัด…' : 'สกัดใหม่'}
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {skills.map((s) => {
              const m = METHOD[links.get(s)?.method ?? 'manual'] ?? METHOD.manual
              return (
                <button key={s} type="button" onClick={() => setSkills(skills.filter((x) => x !== s))} aria-label={`ลบทักษะ ${s}`}
                  title={links.get(s) ? `${m.label} · ${links.get(s)!.jobs} งานต้องการ` : 'เพิ่มใหม่ (ผู้วิจัยตรวจ)'}
                  className="chip border border-line bg-white py-1 text-xs hover:border-maroon hover:text-maroon">
                  <span className={clsx('rounded px-1 text-[10px] font-semibold', m.cls)}>{m.label}</span>{s}<Icon name="close" size={10} strokeWidth={2.6} />
                </button>
              )
            })}
            <span className="flex items-center gap-1">
              <label htmlFor="new-skill" className="sr-only">เพิ่มทักษะ</label>
              <input id="new-skill" value={newSkill} onChange={(e) => setNewSkill(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addSkill() } }}
                placeholder="+ เพิ่ม" className="h-7 w-24 rounded-md border border-dashed border-brand-400 bg-transparent px-2 text-xs outline-none focus:border-brand-700" />
            </span>
          </div>
          <span className="text-xs text-muted">ชื่อทักษะต้องตรงกับตาราง skills · ทักษะที่เพิ่มเองจะบันทึกเป็น "ผู้วิจัยตรวจ" และนับแยกใน Match Score</span>
        </div>
      )}
      {(save.error || extract.error) && <p role="alert" className="text-[13px] text-maroon">{((save.error ?? extract.error) as Error).message}</p>}
      <div className="mt-auto grid grid-cols-2 gap-2">
        <button type="button" onClick={onClose} className="btn-outline h-11">ยกเลิก</button>
        <button type="submit" disabled={save.isPending} className="btn-primary h-11">{save.isPending ? 'กำลังบันทึก…' : isNew ? 'เพิ่มรายวิชา' : 'บันทึก'}</button>
      </div>
    </form>
  )
}

export default function Courses() {
  const qc = useQueryClient()
  const courses = useQuery({ queryKey: ['courses'], queryFn: api.courses })
  const [editing, setEditing] = useState<Course | null | 'new'>(null)
  const remove = useMutation({ mutationFn: (code: string) => api.deleteCourse(code), onSuccess: () => qc.invalidateQueries({ queryKey: ['courses'] }) })
  const recalc = useMutation({ mutationFn: api.recalcGap, onSuccess: () => qc.invalidateQueries({ queryKey: ['gap'] }) })
  const list = courses.data ?? []

  return (
    <div className="flex min-h-full">
      <div className="min-w-0 flex-1">
        <PageHeader crumbs={['ผู้ดูแลระบบ', 'รายวิชา']} title="รายวิชาในหลักสูตร" subtitle={`${list.length} วิชา จาก มคอ.2 · ${list.reduce((a, c) => a + c.skills.length, 0)} คู่ วิชา–ทักษะ · แก้แล้วกดคำนวณ Gap ใหม่`}
          actions={
            <>
              <button type="button" className="btn-outline" onClick={() => recalc.mutate()} disabled={recalc.isPending}>
                <Icon name="refresh" size={16} />{recalc.isPending ? 'กำลังคำนวณ…' : recalc.isSuccess ? 'คำนวณแล้ว' : 'คำนวณ Gap ใหม่'}
              </button>
              <button type="button" className="btn-primary" onClick={() => setEditing('new')}><Icon name="plus" size={16} strokeWidth={2.4} />เพิ่มรายวิชา</button>
            </>
          } />
        <PageBody>
          {remove.isError && <ErrorState error={remove.error} />}
          {courses.isError ? <ErrorState error={courses.error} onRetry={() => courses.refetch()} /> : !courses.data ? <Skeleton className="h-80" /> : list.length === 0 ? (
            <Empty title="ยังไม่มีรายวิชา">โหลดรายวิชาจาก มคอ.2 ด้วย <code>python -m extractor.curriculum load</code> ในโฟลเดอร์ pipeline แล้วรัน embed และ map</Empty>
          ) : (
            <section className="overflow-hidden rounded-[14px] border border-line bg-white">
              <div className="hidden grid-cols-[minmax(0,1fr)_120px_110px_88px] gap-3 border-b border-line-soft bg-[#FAFAFA] px-4 py-2.5 text-xs font-medium text-muted lg:grid">
                <span>รายวิชา</span><span>หมวด</span><span>ทักษะ</span><span />
              </div>
              <ul>
                {list.map((c, i) => {
                  const sel = editing !== 'new' && editing?.code === c.code
                  return (
                    <li key={c.code} className={clsx('grid grid-cols-[minmax(0,1fr)_88px] items-center gap-3 border-b border-[#F4F4F6] px-4 py-2.5 last:border-0 lg:grid-cols-[minmax(0,1fr)_120px_110px_88px]', sel && 'bg-brand-50')}>
                      <div className="flex min-w-0 items-center gap-3">
                        <span className={clsx('num flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] font-mono text-xs', sel ? 'bg-brand-700 text-white' : 'bg-canvas text-ink-3')}>{String(i + 1).padStart(2, '0')}</span>
                        <div className="flex min-w-0 flex-col"><span className="truncate text-sm font-medium">{c.name_th}</span><span className="truncate text-xs text-muted">{c.code} · {c.name_en}</span></div>
                      </div>
                      <span className="hidden truncate text-[13px] text-ink-3 lg:block">{CATEGORY[c.category ?? ''] ?? c.category ?? '–'}</span>
                      <span className="num hidden justify-self-start rounded-md bg-brand-100 px-2 py-0.5 text-xs font-medium text-brand-800 lg:block">{c.skills.length} ทักษะ</span>
                      <div className="flex justify-end gap-0.5">
                        <button type="button" aria-label={`แก้ไข ${c.name_th}`} onClick={() => setEditing(c)} className="flex h-10 w-10 items-center justify-center rounded-[9px] text-ink-3 hover:bg-canvas"><Icon name="edit" size={16} /></button>
                        <button type="button" aria-label={`ลบ ${c.name_th}`} onClick={() => { if (confirm(`ลบรายวิชา ${c.name_th}?`)) remove.mutate(c.code) }}
                          className="flex h-10 w-10 items-center justify-center rounded-[9px] text-maroon hover:bg-maroon-soft"><Icon name="trash" size={16} /></button>
                      </div>
                    </li>
                  )
                })}
              </ul>
            </section>
          )}
        </PageBody>
      </div>
      {editing && <Editor course={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  )
}
