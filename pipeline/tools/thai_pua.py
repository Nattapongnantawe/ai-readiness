import re
PUA = {0xF700:'ฐ',0xF701:'ิ',0xF702:'ี',0xF703:'ึ',0xF704:'ื',
0xF705:'่',0xF706:'้',0xF707:'๊',0xF708:'๋',0xF709:'์',
0xF70A:'่',0xF70B:'้',0xF70C:'๊',0xF70D:'๋',0xF70E:'์',
0xF70F:'ญ',0xF710:'ั',0xF711:'ํ',0xF712:'็',0xF713:'่',
0xF714:'้',0xF715:'๊',0xF716:'๋',0xF717:'์',0xF718:'ุ',
0xF719:'ู',0xF71A:'ฺ'}
THDIG = str.maketrans('๐๑๒๓๔๕๖๗๘๙','0123456789')
TH = 'ก-๎'
NOSTART = 'ะัาำิ-ฺๅ็-๎'
def fix_line(s):
    s = s.translate(PUA).replace('ํา','ำ').replace('ํ า','ำ')
    # justified text: many 1-2 char Thai tokens -> remove spaces between Thai chars
    toks = s.split()
    short = sum(1 for t in toks if len(t) <= 2 and re.match(f'[{TH}]', t))
    if short >= 3:
        s = re.sub(f'(?<=[{TH}]) +(?=[{TH}])', '', s)
    s = re.sub(f' +(?=[{NOSTART}])', '', s)
    s = re.sub(r'(?<=[เ-ไ]) +', '', s)
    # reorder: tone mark before upper vowel (e.g. ่ี -> ี่)
    s = re.sub('([่-๋])([ัิ-ื็])', r'\2\1', s)
    return s
