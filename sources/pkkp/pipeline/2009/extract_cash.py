import sys; sys.path.insert(0,'/home/claude/pkkp/work/2009/pipeline')
import lib2009 as L, json
SRC=L.SRC
CHECKS=json.load(open('/tmp/checks_bs.json'))
# remove any prior cash checks to avoid dupes
CHECKS=[c for c in CHECKS if not c[1].startswith('cash ')]
def chk(status,name,ext,pr):
    diff=(None if(ext is None or pr is None) else round(ext-pr,2))
    CHECKS.append([status,name,ext,pr,'' if diff is None else diff])

pdf=39; pr=L.printed_of(pdf); STMT="Penyata Penerimaan dan Pembayaran Wang Tunai"
lines=L.lines(pdf)
cur=[0]
def nextline(label):
    for i in range(cur[0],len(lines)):
        s=lines[i]
        if s.lstrip().startswith(label):
            cur[0]=i+1; return s
    return None
# (flow,category,item,label_prefix,last_in_cat)
struct=[
 ("TERIMAAN","Hasil","Hasil Cukai","Hasil Cukai",0),
 ("TERIMAAN","Hasil","Hasil Bukan Cukai","Hasil Bukan Cukai",0),
 ("TERIMAAN","Hasil","Pelbagai Terimaan","Pelbagai Terimaan",0),
 ("TERIMAAN","Hasil","Hasil Wilayah Persekutuan","Hasil Wilayah Persekutuan",1),
 ("TERIMAAN","Pinjaman","Pinjaman Dalam Negeri","Pinjaman Dalam Negeri",0),
 ("TERIMAAN","Pinjaman","Pinjaman Luar Negeri","Pinjaman Luar Negeri",1),
 ("TERIMAAN","Terimaan Modal","Terimaan Balik Pinjaman","Terimaan Balik Pinjaman",0),
 ("TERIMAAN","Terimaan Modal","Jualan Aset Modal","Jualan Aset Modal",0),
 ("TERIMAAN","Terimaan Modal","Pelbagai Terimaan Modal","Pelbagai Terimaan Modal",1),
 ("TERIMAAN","Terimaan Lain","Terimaan Amanah","Terimaan Amanah",0),
 ("TERIMAAN","Terimaan Lain","Inisiatif Pembiayaan Swasta (PFI)","Inisiatif Pembiayaan Swasta (PFI)",1),
 ("BAYARAN","Perbelanjaan Mengurus","Emolumen","Emolumen",0),
 ("BAYARAN","Perbelanjaan Mengurus","Perkhidmatan dan Bekalan","Perkhidmatan dan Bekalan",0),
 ("BAYARAN","Perbelanjaan Mengurus","Aset","Aset",0),
 ("BAYARAN","Perbelanjaan Mengurus","Pemberian dan Kenaan Bayaran Tetap","Kenaan Bayaran Tetap",0),
 ("BAYARAN","Perbelanjaan Mengurus","Perbelanjaan Lain","Perbelanjaan Lain",1),
 ("BAYARAN","Perbelanjaan Pembangunan","Langsung","Langsung",0),
 ("BAYARAN","Perbelanjaan Pembangunan","Pinjaman","Pinjaman",1),
 ("BAYARAN","Perbelanjaan Pembangunan","Inisiatif Pembiayaan Swasta (PFI)","Inisiatif Pembiayaan Swasta (PFI)",0),
 ("BAYARAN","Perbelanjaan Modal","Pembelian Instrumen Kewangan","Pembelian Instrumen Kewangan",0),
 ("BAYARAN","Bayaran Balik Pinjaman","Pinjaman Dalam Negeri","Pinjaman Dalam Negeri",0),
 ("BAYARAN","Bayaran Balik Pinjaman","Pinjaman Luar Negeri","Pinjaman Luar Negeri",1),
 ("BAYARAN","Bayaran Lain","Bayaran Lain","Bayaran Lain",0),
]
rows=[]; cat_sub={}
for flow,cat,item,pref,islast in struct:
    l=nextline(pref)
    if l is None:
        chk("FAIL","cash MISSING "+item,None,None); continue
    vals=[L.parse_num(t)[0] for t in L.numtokens(l)]
    if len(vals)>=4:
        v9,s9,v8,s8=vals[0],vals[1],vals[2],vals[3]; cat_sub[(flow,cat)]=(s9,s8)
    elif len(vals)==2:
        v9,v8=vals[0],vals[1]
    elif len(vals)==1:
        v9,v8=vals[0],None
    else:
        v9,v8=(None,None)
    rows.append([flow,cat,item,2009,L.fmt(v9),SRC,pdf,pr,STMT])
    rows.append([flow,cat,item,2008,L.fmt(v8),SRC,pdf,pr,STMT])
for (flow,cat),(s9,s8) in cat_sub.items():
    rows.append([flow,cat,"Jumlah "+cat,2009,L.fmt(s9),SRC,pdf,pr,STMT])
    rows.append([flow,cat,"Jumlah "+cat,2008,L.fmt(s8),SRC,pdf,pr,STMT])
grand=[("TERIMAAN","","Jumlah Terimaan",273249151048.0,237990193271.0),
 ("BAYARAN","","Jumlah Bayaran",-266928818302.0,-239530895502.0),
 ("","","Tambahan/(Kurangan) Wang Tunai",6320332746.0,-1540702231.0),
 ("","","Wang Tunai pada 1 Januari",15401985728.0,16942687959.0),
 ("","","WANG TUNAI PADA 31 DISEMBER",21722318474.0,15401985728.0)]
for flow,cat,item,v9,v8 in grand:
    rows.append([flow,cat,item,2009,L.fmt(v9),SRC,pdf,pr,STMT])
    rows.append([flow,cat,item,2008,L.fmt(v8),SRC,pdf,pr,STMT])
L.write_csv("fact_cash_statement.csv",
 ["flow","category_bm","item_bm","year","amount_rm","source_file","pdf_page","printed_page","statement"],rows)
# check: sum of TERIMAAN category subtotals + standalone = Jumlah Terimaan
ter9=cat_sub[("TERIMAAN","Hasil")][0]+cat_sub[("TERIMAAN","Pinjaman")][0]+cat_sub[("TERIMAAN","Terimaan Modal")][0]+cat_sub[("TERIMAAN","Terimaan Lain")][0]
chk("PASS" if abs(ter9-273249151048.0)<1 else "FAIL","cash sum TERIMAAN cats=Jumlah Terimaan 2009",ter9,273249151048.0)
d={(r[2],r[3]):r[4] for r in rows}
chk("PASS" if abs((273249151048.0-266928818302.0)-6320332746.0)<1 else "FAIL","cash JumTerimaan-Bayaran=Tambahan 2009",273249151048.0-266928818302.0,6320332746.0)
chk("PASS" if abs((15401985728.0+6320332746.0)-21722318474.0)<1 else "FAIL","cash open+delta=close 2009",15401985728.0+6320332746.0,21722318474.0)
json.dump(CHECKS,open('/tmp/checks_bs.json','w'))
for c in CHECKS:
    if c[1].startswith('cash'): print(c)
