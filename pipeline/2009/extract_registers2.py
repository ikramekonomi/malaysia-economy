import sys, re; sys.path.insert(0,'/home/claude/pkkp/work/2009/pipeline')
import lib2009 as L, json
SRC=L.SRC; CHK=[]
def chk(cond,name,e,p): CHK.append(["PASS" if cond else "FAIL",name,e,p,'' if(e is None or p is None) else round(e-p,2)])

# ============ F1 loans_receivable (pdf175-177) ============
STMT="F1 Penyata Akaun Memorandum Pinjaman Boleh Dituntut"
rows=[]; section=None
for pdf in (175,176,177):
    pr=L.printed_of(pdf)
    for l in L.lines(pdf):
        s=l.strip(); toks=L.numtokens(l)
        if not s or 'Pinjaman Boleh Dituntut' in s or 'seperti pada' in s or '.indd' in s: continue
        if any(k in s for k in ['Perihal','Kumpulanwang','Pembangunan','Disatukan','Amanah Lain','Baki Belum','RM','(disambung','Dikenakan']): 
            if not toks: continue
        if not toks:
            if s.isupper(): section=s.title()
            continue
        m=[L.parse_num(t) for t in toks[-5:]] if len(toks)>=5 else None
        item=re.sub(r'\s{2,}.*$','',s).strip()
        rt='total' if s.startswith('JUMLAH') else ('subtotal' if s.startswith('Jumlah') else 'line')
        if m is None:
            continue
        pb,hd,al,b09,b08=m
        rows.append([section or '','',section or '' if rt!='line' else '',item,rt,2009,L.fmt(pb[0]),L.fmt(hd[0]),L.fmt(al[0]),L.fmt(b09[0]),SRC,pdf,pr,STMT])
        rows.append([section or '','',section or '' if rt!='line' else '',item,rt,2008,'','','',L.fmt(b08[0]),SRC,pdf,pr,STMT])
L.write_csv("fact_loans_receivable.csv",
 ["section_bm","category_no","category_bm","peminjam_bm","row_type","year","pembangunan_rm","hasil_disatukan_rm","amanah_lain_rm","baki_belum_selesai_rm","source_file","pdf_page","printed_page","statement"],rows)
tot=[float(r[9]) for r in rows if r[3].startswith('JUMLAH PINJAMAN BOLEH') and r[5]==2009]
if tot: chk(abs(tot[0]-73382745118.92)<0.5,"F1 JUMLAH PINJAMAN BOLEH DITUNTUT 2009==memo",tot[0],73382745118.92)
# additivity: sum of section subtotals baki == total
subs=sum(float(r[9]) for r in rows if r[4]=='subtotal' and r[5]==2009)
if tot: chk(abs(subs-tot[0])<0.5,"F1 sum section subtotals==JUMLAH 2009",round(subs,2),tot[0])

# ============ F2 investments (pdf178-181) best-effort ============
STMT="F2 Penyata Akaun Memorandum Pelaburan"
inv=[]; section=None
CCY=re.compile(r'\b(USD|GBP|EUR|JPY|SGD|RM|AUD|CHF|CAD)\b')
for pdf in (178,179,180,181):
    pr=L.printed_of(pdf)
    for l in L.lines(pdf):
        s=l.strip(); toks=L.numtokens(l)
        if not s or 'Memorandum Pelaburan' in s or 'seperti pada' in s or '.indd' in s: continue
        if any(k in s for k in ['Modal','Saham','Diterbitkan','Perihal','Nilai Nominal','Nilai Buku','Pegangan']) and not toks: continue
        if not toks:
            if s.isupper(): section=s.title()
            continue
        # nilai_buku = last 2 numbers; pegangan% = 3rd last (may be '–')
        vals=[L.parse_num(t) for t in toks]
        if len(vals)<2: continue
        nb09,nb08 = vals[-2][0], vals[-1][0]
        peg = None
        # find a token that's a small % (<=100 ish) before nb09 -- heuristic: 3rd last
        if len(vals)>=3: peg=vals[-3][0]
        entiti=re.sub(r'\s{2,}.*$','',s).strip()
        rt='subtotal' if s.startswith('Jumlah') else ('total' if s.startswith('JUMLAH') else 'line')
        ccy=CCY.findall(l)
        inv.append([section or '',entiti,'', (ccy[0] if ccy else ''),'', (ccy[-1] if ccy else ''),'', L.fmt(peg) if peg is not None else '',rt,('*' in l), '', 2009, L.fmt(nb09), SRC,pdf,pr,STMT])
        inv.append([section or '',entiti,'', '','', '','', '', rt, False,'',2008, L.fmt(nb08), SRC,pdf,pr,STMT])
L.write_csv("fact_investments.csv",
 ["section_bm","entiti_bm","perihal","modal_saham_ccy","modal_saham_amt","nilai_nominal_ccy","nilai_nominal_amt","pegangan_pct","row_type","has_footnote","footnote_ref","year","nilai_buku_rm","source_file","pdf_page","printed_page","statement"],inv)
itot=[float(r[12]) for r in inv if r[8]=='total' and r[11]==2009]
# find JUMLAH PELABURAN total
jt=[r for r in inv if r[1].upper().startswith('JUMLAH PELABURAN') and r[11]==2009]
if jt: chk(abs(float(jt[0][12])-27751414083.29)<0.5,"F2 JUMLAH PELABURAN 2009==memo",float(jt[0][12]),27751414083.29)
else: chk(False,"F2 JUMLAH PELABURAN row found",None,None)
print("F1 loans_receivable:",len(rows),"| F2 investments:",len(inv))
json.dump(CHK,open('/tmp/checks_reg2.json','w'))
for c in CHK: print(c)
