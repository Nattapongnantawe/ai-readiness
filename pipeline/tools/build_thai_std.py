import csv, json, re
import dsd_parse as D
out = []
seen = set()
def add(std, code, label, typ, desc):
    label = re.sub(r'\s+', ' ', label).strip(' :-•')[:300]
    if len(label) < 4 or not re.search(r'[A-Za-z\u0e01-\u0e2e]{3}', label) or (std, label) in seen: return
    seen.add((std, label)); out.append(dict(standard=std, std_code=code, label=label, std_type=typ, description=desc))

# DSD
SECTH = {'knowledge':'ความรู้','ability':'ความสามารถ','attitude':'ทัศนคติ'}
for r in json.load(open('dsd_rows.json')):
    if r['section'] == 'attitude': continue      # ทัศนคติ = ข้อความรวมทั่วไป ไม่ใช่ทักษะเฉพาะ
    br = D.NAMES[r['doc']]
    add('DSD', f"DSD-{r['doc']}-L{r['level']}-{r['code']}", D.label_of(r),
        f"{SECTH[r['section']]}", f"สาขา{br} ระดับ {r['level']}")

# TPQI units
CODE2 = re.compile(r'^([A-Z]{2,6}-[A-Z0-9]{2,6}(?:-\d)?-\d{3}[A-Z]{0,2})\s+')
units = {}
for r in csv.DictReader(open('tpqi_units.csv', encoding='utf-8-sig')):
    t = r['unit_title'].strip(); c = r['unit_code']
    m = CODE2.match(t)
    if m: c = c or m.group(1); t = t[m.end():]
    occ = r['occupation'] or re.sub(r'^.*?อาชีพ', '', r['qualification'])
    units[r['unit_id']] = (c, t, f"{r['sector']} | {occ} ระดับ {r['level']}")
    add('TPQI', c or f"TPQI-U{r['unit_id']}", t, 'หน่วยสมรรถนะ', f"{r['sector']} | {occ} ระดับ {r['level']}")

# TPQI elements: เก็บเฉพาะชื่อหน่วยย่อย (ตัดเกณฑ์การปฏิบัติงาน/รหัสที่ติดมา)
CUT = re.compile(r'\s(?:\d+\.\d+|\d+\.)\s|\s\d{5,6}\.\d{2}\.\d{2}|\s12\.\s*ความรู้|\(ก\)')
n_el = 0
for r in csv.DictReader(open('tpqi_elements.csv', encoding='utf-8-sig')):
    t = r['element_title']
    t = re.sub(r'^(\d{5,7}\s+)+', '', t)                 # 182403 10133 ...
    if t.startswith(('ความรู้และทักษะ', '12.', '13.')): continue
    t = CUT.split(' ' + t, 1)[0].strip()
    t = re.sub(r'\s\d+\.?$', '', t)
    u = units.get(r['unit_id'])
    if len(t) < 6 or not u: continue
    add('TPQI', r['element_code'], t, 'หน่วยสมรรถนะย่อย', f"{u[1]} | {u[2]}"); n_el += 1

with open('thai_std.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['standard','std_code','label','std_type','description'])
    w.writeheader(); w.writerows(out)
from collections import Counter
print(Counter((o['standard'], o['std_type']) for o in out))
