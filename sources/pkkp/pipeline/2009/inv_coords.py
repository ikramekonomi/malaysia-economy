import pdfplumber, re, json
from collections import defaultdict
PDF='/home/claude/pkkp/work/2009/2009.pdf'
CCY=re.compile(r'^(USD|GBP|EUR|JPY|SGD|RM|AUD|CHF|CAD|Baht|SDR|IDR|THB)$')
AMT=re.compile(r'^\(?[\d,]+\.\d{2}\)?$')
DASH={'–','-','—','−'}
pdf=pdfplumber.open(PDF)

def amt(t):
    if t is None: return None
    if t in DASH: return 0.0
    neg=t.startswith('(') and t.endswith(')')
    v=float(t.strip('()').replace(',',''))
    return -v if neg else v

# 178-frame zone boundaries (using dx-corrected coords)
def zone(x0,x1,text):
    # right edges for amounts; x0 for text/ccy
    if x1 < 178: return 'entity'
    if CCY.match(text) and 175<=x0<200: return 'modal_ccy'
    if 195 < x1 <= 268 and (AMT.match(text) or text in DASH): return 'modal_amt'
    if text in DASH and 195<x1<=268: return 'modal_amt'
    if 262 <= x0 < 360: return 'perihal'
    if CCY.match(text) and 358<=x0<390: return 'nominal_ccy'
    if 384 < x1 <= 437 and (AMT.match(text) or text in DASH): return 'nominal_amt'
    if 437 <= x0 < 467: return 'pct'
    if 465 < x1 <= 521 and (AMT.match(text) or text in DASH): return 'nb2009'
    if x1 > 519 and (AMT.match(text) or text in DASH): return 'nb2008'
    if x0 < 262: return 'entity'
    return 'perihal'

results=[]
for pno in (178,179,180,181):
    pg=pdf.pages[pno-1]
    words=[w for w in pg.extract_words(keep_blank_chars=False) if 0<=w['x0']<660]
    pcth=[w for w in words if w['text']=='%' and 130<w['top']<200 and w['x0']>0]
    dx=pcth[0]['x0']-443.4 if pcth else 0.0
    # group into visual lines by single-linkage on 'top' (merge within 5px)
    ws_sorted=sorted(words,key=lambda w:w['top'])
    groups=[]; cur=[]; last=None
    for w in ws_sorted:
        if last is not None and w['top']-last>5.0:
            groups.append(cur); cur=[]
        cur.append(w); last=w['top']
    if cur: groups.append(cur)
    for grp in groups:
        ws=sorted(grp,key=lambda w:w['x0'])
        top=min(w['top'] for w in ws)
        if top<190 or top>835: continue
        z=defaultdict(list)
        for w in ws:
            t=w['text']
            zz=zone(w['x0']-dx,w['x1']-dx,t)
            z[zz].append(t)
        joined=' '.join(w['text'] for w in ws)
        results.append(dict(pno=pno,top=round(top,1),
            entity=' '.join(z.get('entity',[])),
            modal_ccy=(z.get('modal_ccy') or [None])[0],
            modal_amt=(z.get('modal_amt') or [None])[0],
            perihal=' '.join(z.get('perihal',[])),
            nominal_ccy=(z.get('nominal_ccy') or [None])[0],
            nominal_amt=(z.get('nominal_amt') or [None])[0],
            pct=(z.get('pct') or [None])[0],
            nb2009=(z.get('nb2009') or [None])[0],
            nb2008=(z.get('nb2008') or [None])[0],
            raw=joined))
json.dump(results,open('/tmp/inv_coords.json','w'))
# print first 25 for inspection
for r in results[:25]:
    print(r['pno'],str(r['top']).ljust(6),'|E:',r['entity'][:26].ljust(26),'|Mccy',str(r['modal_ccy']),'Mamt',str(r['modal_amt']),'|Nccy',str(r['nominal_ccy']),'Namt',str(r['nominal_amt']),'|pct',str(r['pct']),'|b09',str(r['nb2009']))
