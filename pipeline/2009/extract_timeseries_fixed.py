import sys, re; sys.path.insert(0,'/home/claude/pkkp/work/2009/pipeline')
import lib2009 as L, json
SRC=L.SRC; STMT="Lampiran I Perangkaan Kewangan Kerajaan Persekutuan"
YEARS=list(range(2009,1999,-1))
rows=[]
# FIX: also match a standalone bare hyphen '-' (0x2d) as a zero token, in addition to en-dash
NUMRE=re.compile(r'\(?-?[\d][\d,]*(?:\.\d+)?\)?|–|(?<=\s)-(?=\s|$)')
for pdf in range(264,267):
    section=None
    for l in L.lines(pdf):
        s=l.strip()
        if not s or 'Perangkaan' in s or 'dalam RM juta' in s or 'Sambungan' in s or '.indd' in s: continue
        if re.match(r'^(19|20)\d\d\b', s) and s.count('20')>=1 and len(NUMRE.findall(s))>=8 and 'Nota' not in s:
            continue
        if s.startswith('Nota'): continue
        toks=NUMRE.findall(l)
        if len(toks)>=10:
            yvals=toks[-10:]
            extra=toks[:-10]
            fn=len(extra)>0
            # label = text before first year token. FIX: boundary also handles bare hyphen columns
            m=re.match(r'^\s*(.*?)(?=\s{2,}\(?-?\d|\s{2,}–|\s{2,}-(?:\s|$))', l)
            label=(m.group(1).strip() if m else s)
            label=re.sub(r'\s+\d$','',label).strip()
            for y,tv in zip(YEARS,yvals):
                v=L.parse_num(tv)[0]
                rows.append([section or '',label,y,L.fmt(v),'juta',SRC,pdf,L.printed_of(pdf),STMT,fn])
        elif len(toks)==0:
            section=s
import csv
with open('/tmp/ts_fixed.csv','w',newline='',encoding='utf-8') as f:
    w=csv.writer(f)
    w.writerow(["section_bm","line_item_bm","year","amount_rm_juta","unit","source_file","pdf_page","printed_page","statement","has_footnote"])
    for r in rows: w.writerow(r)
print("rows:",len(rows))
