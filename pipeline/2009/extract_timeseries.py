import sys, re; sys.path.insert(0,'/home/claude/pkkp/work/2009/pipeline')
import lib2009 as L, json
SRC=L.SRC; STMT="Lampiran I Perangkaan Kewangan Kerajaan Persekutuan"
YEARS=list(range(2009,1999,-1))
rows=[]; CHK=[]
NUMRE=re.compile(r'\(?-?[\d][\d,]*(?:\.\d+)?\)?|–')
for pdf in range(264,267):
    pr_folio=None
    # folio for this appendix page: the standalone small number near bottom
    section=None
    for l in L.lines(pdf):
        s=l.strip()
        if not s or 'Perangkaan' in s or 'dalam RM juta' in s or 'Sambungan' in s or '.indd' in s: continue
        if re.match(r'^(19|20)\d\d\b', s) and s.count('20')>=1 and len(NUMRE.findall(s))>=8 and 'Nota' not in s:
            # this is the year header row
            continue
        if s.startswith('Nota'): continue
        toks=NUMRE.findall(l)
        if len(toks)>=10:
            # take last 10 as years
            yvals=toks[-10:]
            extra=toks[:-10]
            fn=len(extra)>0  # leading footnote digit
            # label = text before first year token
            label=l
            # strip trailing numbers: find position of first of the last-10 tokens
            # simpler: remove all number tokens from a copy of the label region
            m=re.match(r'^\s*(.*?)(?=\s{2,}\(?-?\d|\s{2,}–)', l)
            label=(m.group(1).strip() if m else s)
            label=re.sub(r'\s+\d$','',label).strip()  # drop trailing footnote digit
            for y,tv in zip(YEARS,yvals):
                v=L.parse_num(tv)[0]
                rows.append([section or '',label,y,L.fmt(v),'juta',SRC,pdf,L.printed_of(pdf),STMT,fn])
        elif len(toks)==0:
            section=s
L.write_csv("fact_timeseries_2000_2009.csv",
 ["section_bm","line_item_bm","year","amount_rm_juta","unit","source_file","pdf_page","printed_page","statement","has_footnote"],rows)
# cross-foot: Cukai Langsung+Tidak Langsung+Terimaan Lain == Jumlah Hasil per year
from collections import defaultdict
byy=defaultdict(dict)
for r in rows:
    byy[r[1]][r[2]]=float(r[3])
def get(lbl,y): return byy.get(lbl,{}).get(y)
ok=True
for y in YEARS:
    a=get('Cukai Langsung',y);b=get('Cukai Tidak Langsung',y);c=get('Terimaan Lain',y);j=get('Jumlah Hasil',y)
    if None not in (a,b,c,j) and abs(a+b+c-j)>0: ok=False
CHK.append(["PASS" if ok else "FAIL","timeseries Hasil components cross-foot all years",'','',''])
# Wang Awam: Wang Tunai+Pelaburan==Jumlah Wang Awam
ok2=True
for y in YEARS:
    a=get('Wang Tunai',y);b=get('Pelaburan',y);j=get('Jumlah Wang Awam',y)
    if None not in (a,b,j) and abs(a+b-j)>0: ok2=False
CHK.append(["PASS" if ok2 else "FAIL","timeseries Wang Awam cross-foot all years",'','',''])
print("timeseries rows:",len(rows),"distinct line_items:",len(set(r[1] for r in rows)))
print("2009 Jumlah Hasil:",get('Jumlah Hasil',2009),"(expect 158639)")
for c in CHK: print(c)
json.dump(CHK,open('/tmp/checks_ts.json','w'))
