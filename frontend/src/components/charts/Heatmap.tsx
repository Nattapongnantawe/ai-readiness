function shade(v: number) {
  if (v === 0) return { bg: '#FAFAFA', fg: '#A1A1AA', ring: true }
  if (v < 0.35) return { bg: '#E3ECF9', fg: '#234C91', ring: false }
  if (v < 0.6) return { bg: '#B9CDEE', fg: '#1B3C75', ring: false }
  if (v < 0.85) return { bg: '#7BA3D9', fg: '#0F2A57', ring: false }
  return { bg: '#2F63B8', fg: '#FFFFFF', ring: false }
}

export function Heatmap({ courses, skills, values }: { courses: string[]; skills: string[]; values: number[][] }) {
  const cols = { gridTemplateColumns: `minmax(170px, 230px) repeat(${skills.length}, minmax(44px, 1fr))` }
  return (
    <div className="no-scrollbar overflow-x-auto">
      <div role="table" aria-label="ความครอบคลุมทักษะของแต่ละรายวิชา (0 ถึง 1)" className="flex min-w-[640px] flex-col gap-[5px]">
        <div role="row" className="grid gap-[5px]" style={cols}>
          <span role="columnheader" className="sr-only">รายวิชา</span>
          {skills.map((s) => <span key={s} role="columnheader" className="truncate text-center text-xs font-medium text-muted">{s}</span>)}
        </div>
        {courses.map((c, i) => (
          <div key={c} role="row" className="grid items-center gap-[5px]" style={cols}>
            <span role="rowheader" className="truncate text-[13px]">{c}</span>
            {skills.map((s, j) => {
              const v = values[i]?.[j] ?? 0
              const st = shade(v)
              return (
                <span key={s} role="cell" aria-label={`${s} ${v.toFixed(1)}`} className="num flex h-9 items-center justify-center rounded-lg text-xs font-medium"
                  style={{ background: st.bg, color: st.fg, boxShadow: st.ring ? 'inset 0 0 0 1px #F0F0F2' : undefined }}>
                  {v === 0 ? '–' : v.toFixed(1)}
                </span>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
