import sys, re; sys.path.insert(0,'/home/claude/pkkp/work/2009/pipeline')
import lib2009 as L, json
SRC=L.SRC
CHK=[]
def chk(cond,name,e,p):
    CHK.append(["PASS" if cond else "FAIL",name,e,p,'' if (e is None or p is None) else round(e-p,2)])
# ---------- fact_revenue (C1, pdf50) ----------
pdf=50; pr=L.printed_of(pdf); STMT="C1 Penyata Hasil"
rows=[]; cat=None
cat_re=re.compile(r'^(\d{5})\s+([A-Z].*)$')
for l in L.lines(pdf):
    s=l.strip(); toks=L.numtokens(l)
    if not s or 'Penyata Hasil' in s or 'bagi tahun' in s: continue
    m=cat_re.match(s)
    if m and len(toks)==1:  # category header (code + allcaps, no money)
        cat=re.sub(r'\s{2,}.*$','',m.group(2)).strip(); continue
    if m and len(toks)>=7:  # item: code + name + 6 numbers
        code=m.group(1); nums=[L.parse_num(t) for t in toks[1:]]
        name=re.sub(r'\s{2,}.*$','',m.group(2)).strip()
        aa,ad,se09,pc09,se08,pc08=nums[-6],nums[-5],nums[-4],nums[-3],nums[-2],nums[-1]
        rows.append([3,cat,'',name,2009,L.fmt(aa[0]),L.fmt(ad[0]),L.fmt(se09[0]),L.fmt(pc09[0]),L.fmt(se08[0]),L.fmt(pc08[0]),SRC,pdf,pr,STMT])
        continue
    if s.startswith('Jumlah') and len(toks)>=5:
        nums=[L.parse_num(t) for t in toks]
        lbl=re.sub(r'\s{2,}.*$','',s).strip()
        aa,ad,se09,pc09,se08,pc08=nums[-6],nums[-5],nums[-4],nums[-3],nums[-2],nums[-1]
        rows.append([1,lbl.replace('Jumlah ',''),'',lbl,2009,L.fmt(aa[0]),L.fmt(ad[0]),L.fmt(se09[0]),L.fmt(pc09[0]),L.fmt(se08[0]),L.fmt(pc08[0]),SRC,pdf,pr,STMT])
        continue
    if s.startswith('JUMLAH HASIL') and len(toks)>=5:
        nums=[L.parse_num(t) for t in toks]
        aa,ad,se09,pc09,se08,pc08=nums[-6],nums[-5],nums[-4],nums[-3],nums[-2],nums[-1]
        rows.append([0,'JUMLAH HASIL','','JUMLAH HASIL',2009,L.fmt(aa[0]),L.fmt(ad[0]),L.fmt(se09[0]),L.fmt(pc09[0]),L.fmt(se08[0]),L.fmt(pc08[0]),SRC,pdf,pr,STMT])
L.write_csv("fact_revenue.csv",
 ["level","category_l1_bm","category_l2_bm","item_bm","year","anggaran_asal_rm","anggaran_disemak_rm","sebenar_rm","pct_anggaran","sebenar_prior_rm","pct_anggaran_prior","source_file","pdf_page","printed_page","statement"],rows)
# validation: sum item sebenar per category == category Jumlah; sum categories == JUMLAH HASIL
from collections import defaultdict
itemsum=defaultdict(float); catjum={}; grand=None
for r in rows:
    if r[0]==3: itemsum[r[1]]+=float(r[7])
    elif r[0]==1: catjum[r[1]]=float(r[7])
    elif r[0]==0: grand=float(r[7])
for c,js in catjum.items():
    # match category name (Hasil Cukai vs HASIL CUKAI)
    key=[k for k in itemsum if k.lower()==c.lower()]
    if key: chk(abs(itemsum[key[0]]-js)<0.5,f"revenue {c} items==Jumlah 2009",round(itemsum[key[0]],2),round(js,2))
chk(abs(sum(catjum.values())-grand)<0.5,"revenue sum categories==JUMLAH HASIL 2009",round(sum(catjum.values()),2),round(grand,2))
chk(abs(grand-158639304227.70)<0.5,"revenue JUMLAH HASIL 2009==printed",round(grand,2),158639304227.70)

# ---------- fact_revenue_account_statement (C, pdf49) ----------
pdf=49; pr=L.printed_of(pdf); STMT="C Penyata Akaun Hasil Disatukan"
rr=[]
spec=[
 ("","BAKI PADA 1 JANUARI","opening","BAKI PADA 1 JANUARI"),
 ("C1 HASIL","Hasil Cukai","detail","Hasil Cukai"),
 ("C1 HASIL","Hasil Bukan Cukai","detail","Hasil Bukan Cukai"),
 ("C1 HASIL","Pelbagai Terimaan","detail","Pelbagai Terimaan"),
 ("C1 HASIL","Hasil Wilayah-wilayah Persekutuan","detail","Hasil Wilayah-wilayah Persekutuan"),
 ("C1 HASIL","Jumlah Hasil","subtotal","Jumlah Hasil"),
 ("C2 PERBELANJAAN MENGURUS","Emolumen","detail","Emolumen"),
 ("C2 PERBELANJAAN MENGURUS","Perkhidmatan dan Bekalan","detail","Perkhidmatan dan Bekalan"),
 ("C2 PERBELANJAAN MENGURUS","Aset","detail","Aset "),
 ("C2 PERBELANJAAN MENGURUS","Pemberian dan Kenaan Bayaran Tetap","detail","Pemberian dan Kenaan Bayaran Tetap"),
 ("C2 PERBELANJAAN MENGURUS","Perbelanjaan-perbelanjaan Lain","detail","Perbelanjaan-perbelanjaan Lain"),
 ("C2 PERBELANJAAN MENGURUS","Perbelanjaan Mengurus (Tanpa Pindahan)","subtotal","Perbelanjaan Mengurus (Tanpa Pindahan)"),
 ("C2 PERBELANJAAN MENGURUS","Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan","detail","Pindahan Lebihan Hasil"),
 ("C2 PERBELANJAAN MENGURUS","Jumlah Perbelanjaan Mengurus","subtotal","Jumlah Perbelanjaan Mengurus"),
 ("","Lebihan/(Kurangan) bagi Tahun","total","Lebihan/(Kurangan) bagi Tahun"),
 ("","BAKI PADA 31 DISEMBER","closing","BAKI PADA 31 DISEMBER"),
]
lines=L.lines(pdf); cur=[0]
def nl(key):
    for i in range(cur[0],len(lines)):
        if lines[i].lstrip().startswith(key.strip()) and (key!="Aset " or 'Aset' in lines[i]):
            cur[0]=i+1; return lines[i]
    return None
for sec,item,rt,key in spec:
    l=nl(key)
    if l is None: 
        chk(False,"rev_acct MISSING "+item,None,None); continue
    toks=L.numtokens(l); fn=any('*' in t for t in toks)
    # C statement: [Bajet(disemak), Sebenar2009, %2009, Sebenar2008, %2008] but opening/some have fewer
    nums=[L.parse_num(t) for t in toks]
    if rt in ('opening','closing') or item.startswith('Pindahan') or 'Lebihan' in item or 'Jumlah Perbelanjaan Mengurus'==item:
        # these may have en-dash bajet; take sebenar as first big number
        ad='' ; se=nums[0][0] if nums else None; pc=''
        # for detail rows w/ bajet:
    if len(nums)>=5 and rt in ('detail','subtotal'):
        ad,se,pc=nums[-5][0],nums[-4][0],nums[-3][0]
        rr.append([sec,item,rt,2009,L.fmt(ad),L.fmt(se),L.fmt(pc),fn,SRC,pdf,pr,STMT])
    else:
        se=nums[0][0] if nums else None
        rr.append([sec,item,rt,2009,'',L.fmt(se),'',fn,SRC,pdf,pr,STMT])
L.write_csv("fact_revenue_account_statement.csv",
 ["section_bm","line_item_bm","row_type","year","anggaran_disemak_rm","sebenar_rm","pct_anggaran","has_footnote","source_file","pdf_page","printed_page","statement"],rr)
json.dump(CHK,open('/tmp/checks_rev.json','w'))
print("revenue rows:",len(rows),"| rev_acct rows:",len(rr))
for c in CHK: print(c)
