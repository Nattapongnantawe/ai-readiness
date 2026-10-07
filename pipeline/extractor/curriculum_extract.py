"""สกัดรายวิชาจาก มคอ.2 (ข้อความ) -> curriculum_courses.csv / .json
ใช้: python extract_curriculum.py <ไฟล์ txt> [--out output]"""
import re, json, csv, sys, argparse
from pathlib import Path

CODE_RE = re.compile(r'^([A-Z]{2,3}-\d{3}-\d{3})\s*(.+?)\s+(\d+)\((\d+)-(\d+)-(\d+)\)\s*$')
PREREQ_TH = re.compile(r'^รายวิชาบังคับก่อน\s*[:：]\s*(.*)')
PREREQ_EN = re.compile(r'^Prerequisite\s*[:：]\s*(.*)', re.I)
THAI = re.compile(r'[฀-๿]')
PAGE = re.compile(r'^\s*\d{1,3}\s*$')

# หัวข้อหมวด/กลุ่ม -> (category, group)
SECTIONS = {
    'หมวดวิชาศึกษาทั่วไป': ('general_education', None),
    'หมวดวิชาเฉพาะ': ('major', None),
    'วิชาแกน': ('core', None),
    'วิชาเฉพาะด้าน': ('major_required', None),
    'วิชาเลือก': ('major_elective', None),
}
GROUP_PREFIX = 'กลุ่ม'
FIELD_EXP = re.compile(r'^\d\.\d\s*วิชาประสบการณ์ภาคสนาม')   # สัมมนา/โครงงาน/สหกิจ

def join_lines(lines, lang):
    # PDF ตัดบรรทัดกลางคำภาษาไทย: ต่อชิดกัน, ยกเว้นบรรทัดก่อนหน้าลงท้ายด้วยเว้นวรรค (= เว้นวรรคจริง)
    s, prev_space = '', False
    for raw in lines:
        ln = raw.strip()
        if not ln:
            continue
        if not s:
            s = ln
        elif lang == 'th' and not prev_space and THAI.match(ln[0]) and THAI.search(s[-1]):
            s += ln
        else:
            s += ' ' + ln
        prev_space = raw.endswith((' ', '\t'))
    s = s.replace('\u0e4d\u0e32', '\u0e33')          # ํา -> ำ
    s = s.replace('\x02', '-')                        # ขีดตัดคำจาก PDF (non\x02parametric)
    return re.sub(r'\s+', ' ', s).strip()

def parse(text):
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if 'คำอธิบายรายวิชา' in l and l.strip().startswith('3.1.6'))
    end = next(i for i, l in enumerate(lines) if i > start and l.strip().startswith('3.2 '))
    sec = [l.rstrip('\r\n') for l in lines[start + 1:end]]

    courses, cur = [], None
    category, group = None, None

    def flush():
        if not cur:
            return
        body = cur.pop('_body')
        th, en, in_en = [], [], False
        for ln in body:
            if not in_en and not THAI.search(ln):
                in_en = True
            (en if in_en else th).append(ln)
        cur['description_th'] = join_lines(th, 'th')
        cur['description_en'] = join_lines(en, 'en')
        courses.append(cur)

    for raw in sec:
        l = raw.strip()
        if not l or PAGE.match(l):
            continue
        m = CODE_RE.match(l)
        if m:
            flush()
            code, name, cr, t, p, s = m.groups()
            cur = dict(course_code=code, name_th=name.strip().replace('\u0e4d\u0e32', '\u0e33'), name_en=None,
                       credits=int(cr), hours_theory=int(t), hours_practice=int(p), hours_self=int(s),
                       category=category, course_group=group,
                       prerequisite=None, _body=[])
            continue
        if l in SECTIONS:
            flush(); cur = None
            category, group = SECTIONS[l]
            continue
        # หัวข้อกลุ่ม: ขึ้นต้น "กลุ่ม" สั้น ๆ และไม่มีเว้นวรรค (บรรทัดคำอธิบายมักยาว/มีเว้นวรรค)
        if l.startswith(GROUP_PREFIX) and len(l) < 60 and ' ' not in l:
            flush(); cur = None
            group = l
            continue
        if FIELD_EXP.match(l):
            flush(); cur = None
            category, group = 'field_experience', 'สัมมนา โครงงาน และสหกิจศึกษา'
            continue
        if cur is None:
            continue
        if cur['name_en'] is None:
            cur['name_en'] = l
            continue
        mp = PREREQ_TH.match(l)
        if mp:
            cur['prerequisite'] = re.findall(r'[A-Z]{2,3}-\d{3}-\d{3}', mp.group(1)) or [mp.group(1)]
            continue
        if PREREQ_EN.match(l):
            continue
        cur['_body'].append(raw)
    flush()
    for c in courses:
        if c['category'] == 'general_education' or c['course_code'].startswith('GE-'):
            c['category'] = 'general_education'
    return courses

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('--out', default='output')
    ap.add_argument('--program', default='วศ.บ. วิศวกรรมคอมพิวเตอร์ (ปรับปรุง พ.ศ. 2566) มหาวิทยาลัยกาฬสินธุ์')
    a = ap.parse_args()
    courses = parse(Path(a.src).read_text(encoding='utf-8'))
    for c in courses:
        c['program'] = a.program
    out = Path(a.out); out.mkdir(exist_ok=True)
    (out / 'curriculum_courses.json').write_text(json.dumps(courses, ensure_ascii=False, indent=2), encoding='utf-8')
    cols = ['course_code','name_th','name_en','credits','hours_theory','hours_practice','hours_self',
            'category','course_group','prerequisite','description_th','description_en','program']
    with open(out / 'curriculum_courses.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for c in courses:
            r = dict(c); r['prerequisite'] = ';'.join(c['prerequisite'] or [])
            w.writerow(r)
    from collections import Counter
    print(f'📚 สกัดได้ {len(courses)} รายวิชา')
    for k, v in Counter(c["category"] for c in courses).items():
        print(f'   {k:20s} {v}')
    bad = [c['course_code'] for c in courses if not c['description_en'] or not c['description_th']]
    if bad: print('⚠️ คำอธิบายไม่ครบ:', bad)

if __name__ == '__main__':
    main()
