import re, subprocess, csv, json
import thai_pua as T
NAMES = {256:"ช่างไฟฟ้าการควบคุมทางอุตสาหกรรม",258:"ช่างไฟฟ้าภายนอกอาคาร",259:"ช่างเทคนิคเครื่องปรับอากาศสำหรับห้องสะอาด",261:"ผู้ดูแลระบบเครือข่ายคอมพิวเตอร์",262:"นักเขียนโปรแกรมคอมพิวเตอร์ (ภาษาซี)",263:"ช่างไฟฟ้าภายในอาคาร",264:"ช่างเครื่องทำความเย็นในบ้านและการพาณิชย์",265:"ช่างไฟฟ้าอุตสาหกรรม",266:"ช่างซ่อมไมโครคอมพิวเตอร์",267:"ช่างโทรทัศน์",268:"ช่างเครื่องปรับอากาศในบ้าน",269:"นักออกแบบระบบสื่อสาร",270:"ช่างเครือข่ายมีสาย",271:"ช่างไมโครเวฟ",272:"ตารางทำการ",273:"การนำเสนอผลงาน",274:"ประมวลผลคำ",1494:"ช่างติดตั้งระบบทำน้ำอุ่นและน้ำร้อนด้วยไฟฟ้า",1495:"ช่างระบบการต่อลงดินและป้องกันฟ้าผ่า",4738:"ช่างอิเล็กทรอนิกส์"}
SKIP = re.compile(r'^(หน้า \d+|เล่ม \d+.*ราชกิจจานุเบกษา.*)$')
LEVEL = re.compile(r'มาตรฐานฝีมือแรงงานแห่งชาติ\s*ระดับ\s*(\d+)\s*ได้แก่')
SEC = re.compile(r'^(\d+(?:\.\d+)*)\.?\s*(ความรู้|ความสามารถ|ทัศนคติ)')
ITEM = re.compile(r'^(\d+\.\d+(?:\.\d+){0,2})\s+(\S.*)$')
SUB = re.compile(r'^\((\d+|[ก-ฮ])\)\s*(.*)$')
END = re.compile(r'^(ข้อ\s*4|ประกาศ\s*ณ)')
SECMAP = {"ความรู้":"knowledge","ความสามารถ":"ability","ทัศนคติ":"attitude"}

def join(a, b):
    if not a: return b
    if re.search(r'[ก-๎]$', a) and re.match(r'[ก-๎]', b): return a + b
    return a + ' ' + b

def parse(doc):
    raw = subprocess.run(['pdftotext','-raw',f'dsd/{doc}.pdf','-'],capture_output=True,text=True).stdout
    lines = [T.fix_line(l).translate(T.THDIG).strip() for l in raw.splitlines()]
    lines = [l for l in lines if l and not SKIP.match(l) and l != '\x0c']
    rows, level, sec, cur, parent, started = [], None, None, None, None, False
    def flush():
        nonlocal cur
        if cur and cur['text']:
            cur['text'] = re.sub(r'\s+', ' ', cur['text']).strip(' :')
            rows.append(cur)
        cur = None
    for l in lines:
        l = l.replace('\x0c','').strip()
        if not l: continue
        m = LEVEL.search(l)
        if m:
            flush(); level = int(m.group(1)); sec = None; started = True; continue
        if not started: continue
        if END.match(l): flush(); break
        m = SEC.match(l)
        if m and ('ประกอบด้วย' in l or len(l) < 25):
            flush(); sec = SECMAP[m.group(2)]
            if sec == 'attitude':
                txt = re.sub(r'^.*?ประกอบด้วย\s*', '', l)
                cur = dict(doc=doc, level=level, section=sec, code=m.group(1), text=txt, parent=None)
            continue
        m = ITEM.match(l)
        if m and sec and sec != 'attitude':
            flush(); cur = dict(doc=doc, level=level, section=sec, code=m.group(1), text=m.group(2), parent=None)
            parent = cur; continue
        m = SUB.match(l)
        if m and sec and parent is not None:
            flush(); cur = dict(doc=doc, level=level, section=sec, code=parent['code']+f"({m.group(1)})",
                                text=m.group(2), parent=parent['text'] if isinstance(parent.get('text'),str) else None)
            continue
        if cur: cur['text'] = join(cur['text'], l)
    flush()
    return rows

def label_of(r):
    t = r['text']
    if r['parent'] and (len(t) < 30):
        p = re.sub(r'\s*(เช่น|ได้แก่).*$', '', r['parent'])
        t = f"{p}: {t}"
    return t

if __name__ == '__main__':
    allr = []
    for d in NAMES:
        rs = parse(d)
        lv = sorted({r['level'] for r in rs})
        print(d, NAMES[d], len(rs), 'levels', lv, {s: sum(1 for r in rs if r['section']==s) for s in ('knowledge','ability','attitude')})
        allr += rs
    json.dump(allr, open('dsd_rows.json','w'), ensure_ascii=False, indent=1)
