import sys; sys.path.insert(0,'/home/claude/pkkp/work/2009/pipeline')
import lib2009 as L, json
SRC=L.SRC
CHECKS=json.load(open('/tmp/checks_bs.json'))
def chk(status,name,ext,pr):
    diff=(None if(ext is None or pr is None) else round(ext-pr,2))
    CHECKS.append([status,name,ext,pr,'' if diff is None else diff])

def getline(pdf,key):
    for l in L.lines(pdf):
        if key in l: return l
    return None

# ================= fact_cash_statement (pdf39 printed32) =================
pdf=39; pr=L.printed_of(pdf); STMT="Penyata Penerimaan dan Pembayaran Wang Tunai"
# structure: (flow, category, item, matchkey, is_last_in_cat)
struct=[
 ("TERIMAAN","Hasil","Hasil Cukai","Hasil Cukai",0),
 ("TERIMAAN","Hasil","Hasil Bukan Cukai","Hasil Bukan Cukai",0),
 ("TERIMAAN","Hasil","Pelbagai Terimaan","Pelbagai Terimaan ",0),
 ("TERIMAAN","Hasil","Hasil Wilayah Persekutuan","Hasil Wilayah Persekutuan",1),
 ("TERIMAAN","Pinjaman","Pinjaman Dalam Negeri","Pinjaman Dalam Negeri",0),
 ("TERIMAAN","Pinjaman","Pinjaman Luar Negeri","Pinjaman Luar Negeri",1),
 ("TERIMAAN","Terimaan Modal","Terimaan Balik Pinjaman","Terimaan Balik Pinjaman",0),
 ("TERIMAAN","Terimaan Modal","Jualan Aset Modal","Jualan Aset Modal",0),
 ("TERIMAAN","Terimaan Modal","Pelbagai Terimaan Modal","Pelbagai Terimaan Modal",1),
 ("TERIMAAN","Terimaan Lain","Terimaan Amanah","Terimaan Amanah",0),
 ("TERIMAAN","Terimaan Lain","Inisiatif Pembiayaan Swasta (PFI)","Inisiatif Pembiayaan Swasta (PFI)     6,838",1),
 ("BAYARAN","Perbelanjaan Mengurus","Emolumen","Emolumen ",0),
 ("BAYARAN","Perbelanjaan Mengurus","Perkhidmatan dan Bekalan","Perkhidmatan dan Bekalan (",0),
 ("BAYARAN","Perbelanjaan Mengurus","Aset","Aset  ",0),
 ("BAYARAN","Perbelanjaan Mengurus","Pemberian dan Kenaan Bayaran Tetap","Kenaan Bayaran Tetap    (84",0),
 ("BAYARAN","Perbelanjaan Mengurus","Perbelanjaan Lain","Perbelanjaan Lain ",1),
 ("BAYARAN","Perbelanjaan Pembangunan","Langsung","Langsung ",0),
 ("BAYARAN","Perbelanjaan Pembangunan","Pinjaman","Pinjaman  (4,221",1),
 ("BAYARAN","Perbelanjaan Pembangunan","Inisiatif Pembiayaan Swasta (PFI)","Inisiatif Pembiayaan Swasta (PFI)		",0),
 ("BAYARAN","Perbelanjaan Modal","Pembelian Instrumen Kewangan","Pembelian Instrumen Kewangan",0),
 ("BAYARAN","Bayaran Balik Pinjaman","Pinjaman Dalam Negeri","Pinjaman Dalam Negeri     (44",0),
 ("BAYARAN","Bayaran Balik Pinjaman","Pinjaman Luar Negeri","Pinjaman Luar Negeri     (6,736",1),
 ("BAYARAN","Bayaran Lain","Bayaran Lain","Bayaran Lain",0),
]
rows=[]; cat_sub={}
for flow,cat,item,key,islast in struct:
    l=getline(pdf,key)
    if l is None:
        chk("FAIL","cash MISSING line "+item,None,None); continue
    nums=L.numtokens(l)
    vals=[L.parse_num(t)[0] for t in nums]
    if len(vals)>=4:
        v9,s9,v8,s8=vals[0],vals[1],vals[2],vals[3]
        cat_sub[(flow,cat)]=(s9,s8)
    elif len(vals)==2:
        v9,v8=vals[0],vals[1]
    elif len(vals)==1:
        v9=vals[0]; v8=None
    else:
        v9,v8=vals[0],vals[-1]
    rows.append([flow,cat,item,2009,L.fmt(v9),SRC,pdf,pr,STMT])
    rows.append([flow,cat,item,2008,L.fmt(v8),SRC,pdf,pr,STMT])
# category subtotals as rows
for (flow,cat),(s9,s8) in cat_sub.items():
    rows.append([flow,cat,"Jumlah "+cat,2009,L.fmt(s9),SRC,pdf,pr,STMT])
    rows.append([flow,cat,"Jumlah "+cat,2008,L.fmt(s8),SRC,pdf,pr,STMT])
# grand totals & roll-forward
grand=[
 ("TERIMAAN","","Jumlah Terimaan",273249151048.0,237990193271.0),
 ("BAYARAN","","Jumlah Bayaran",-266928818302.0,-239530895502.0),
 ("","","Tambahan/(Kurangan) Wang Tunai",6320332746.0,-1540702231.0),
 ("","","Wang Tunai pada 1 Januari",15401985728.0,16942687959.0),
 ("","","WANG TUNAI PADA 31 DISEMBER",21722318474.0,15401985728.0),
]
for flow,cat,item,v9,v8 in grand:
    rows.append([flow,cat,item,2009,L.fmt(v9),SRC,pdf,pr,STMT])
    rows.append([flow,cat,item,2008,L.fmt(v8),SRC,pdf,pr,STMT])
L.write_csv("fact_cash_statement.csv",
 ["flow","category_bm","item_bm","year","amount_rm","source_file","pdf_page","printed_page","statement"],rows)
# validations
chk("PASS" if abs((273249151048.0-266928818302.0)-6320332746.0)<1 else "FAIL","cash JumTerimaan-JumBayaran=Tambahan 2009",273249151048.0-266928818302.0,6320332746.0)
chk("PASS" if abs((15401985728.0+6320332746.0)-21722318474.0)<1 else "FAIL","cash opening+delta=closing 2009",15401985728.0+6320332746.0,21722318474.0)

# ================= fact_memorandum (pdf40 printed33) =================
pdf=40; pr=L.printed_of(pdf); STMT="Penyata Akaun Memorandum"
mrows=[]
mdef=[
 ("ASET","PINJAMAN BOLEH DITUNTUT",73382745119.0,68505057469.0),
 ("ASET","PELABURAN",27751414083.0,25463523640.0),
 ("ASET","JAMINAN DEPOSIT BERKANUN",39200286.0,38688387.0),
 ("LIABILITI","HUTANG AWAM",362386171110.0,306437413983.0),
 ("LIABILITI","JAMINAN",84314650396.0,69235707622.0),
 ("LIABILITI","PELBAGAI LIABILITI",173364115.0,175703153.0),
]
for sec,item,v9,v8 in mdef:
    mrows.append([sec,item,2009,L.fmt(v9),SRC,pdf,pr,STMT])
    mrows.append([sec,item,2008,L.fmt(v8),SRC,pdf,pr,STMT])
L.write_csv("fact_memorandum.csv",["section","line_item_bm","year","amount_rm","source_file","pdf_page","printed_page","statement"],mrows)

# ================= fact_cash_components (Penyata A, pdf46 printed40) =================
pdf=46; pr=L.printed_of(pdf); STMT="Penyata A Wang Tunai"
crows=[]
cdef=[("Wang Tunai Dalam Bank","WANG TUNAI DALAM BANK","detail"),
      ("Wang Tunai Dalam Perjalanan","WANG TUNAI DALAM PERJALANAN","detail"),
      ("Wang Tunai Dalam Tangan","WANG TUNAI DALAM TANGAN","detail"),
      ("JUMLAH WANG TUNAI","JUMLAH WANG TUNAI","total")]
for item,key,rt in cdef:
    l=getline(pdf,key); nums=L.numtokens(l)
    v9=L.parse_num(nums[-2])[0]; v8=L.parse_num(nums[-1])[0]
    for yr,v in [(2009,v9),(2008,v8)]:
        crows.append([item,yr,L.fmt(v),rt,False,SRC,pdf,pr,STMT])
L.write_csv("fact_cash_components.csv",["line_item_bm","year","amount_rm","row_type","has_footnote","source_file","pdf_page","printed_page","statement"],crows)
tot9=sum(float(r[2]) for r in crows if r[3]=='detail' and r[1]==2009)
chk("PASS" if abs(tot9-21722318474.47)<0.01 else "FAIL","cash_components sum=JUMLAH 2009",round(tot9,2),21722318474.47)

# ================= fact_investment_summary (Penyata B, pdf47 printed41) =================
pdf=47; pr=L.printed_of(pdf); STMT="Penyata B Pelaburan"
irows=[]
idef=[
 ("PELABURAN KUMPULAN WANG AMANAH","Sekuriti Kerajaan Luar Negeri","Sekuriti Kerajaan Luar Negeri                2,886","detail"),
 ("PELABURAN KUMPULAN WANG AMANAH","Sekuriti Kerajaan Malaysia","Sekuriti Kerajaan Malaysia","detail"),
 ("PELABURAN KUMPULAN WANG AMANAH","Saham","Saham                                               784","detail"),
 ("PELABURAN KUMPULAN WANG AMANAH","Deposit Luar Negeri","Deposit Luar Negeri                            207","detail"),
 ("PELABURAN KUMPULAN WANG AMANAH","Deposit Dalam Negeri","Deposit Dalam Negeri                        10,966","detail"),
 ("PELABURAN KUMPULAN WANG AMANAH","Jumlah Pelaburan Kumpulan Wang Amanah","Jumlah Pelaburan Kumpulan Wang Amanah","subtotal"),
 ("PELABURAN AM","Sekuriti Kerajaan Luar Negeri","Sekuriti Kerajaan Luar Negeri                  360","detail"),
 ("PELABURAN AM","Saham","Saham                                        4,582","detail"),
 ("PELABURAN AM","Deposit Luar Negeri","Deposit Luar Negeri                             33","detail"),
 ("PELABURAN AM","Deposit Dalam Negeri","Deposit Dalam Negeri                         2,000","detail"),
 ("PELABURAN AM","Pelbagai","Pelbagai                                           1,670","detail"),
 ("PELABURAN AM","Jumlah Pelaburan Am","Jumlah Pelaburan Am","subtotal"),
 ("","JUMLAH PELABURAN","JUMLAH PELABURAN","total"),
]
for cat,item,key,rt in idef:
    l=getline(pdf,key); nums=L.numtokens(l)
    v9=L.parse_num(nums[-2])[0]; v8=L.parse_num(nums[-1])[0]
    for yr,v in [(2009,v9),(2008,v8)]:
        irows.append([cat,item,yr,L.fmt(v),rt,False,SRC,pdf,pr,STMT])
L.write_csv("fact_investment_summary.csv",["category_bm","line_item_bm","year","amount_rm","row_type","has_footnote","source_file","pdf_page","printed_page","statement"],irows)
amanah9=sum(float(r[3]) for r in irows if r[0]=="PELABURAN KUMPULAN WANG AMANAH" and r[4]=='detail' and r[2]==2009)
am9=sum(float(r[3]) for r in irows if r[0]=="PELABURAN AM" and r[4]=='detail' and r[2]==2009)
chk("PASS" if abs(amanah9-14834564921.40)<0.01 else "FAIL","inv_summary Amanah sum 2009",round(amanah9,2),14834564921.40)
chk("PASS" if abs(am9-6978659903.44)<0.01 else "FAIL","inv_summary Am sum 2009",round(am9,2),6978659903.44)
chk("PASS" if abs((amanah9+am9)-21813224824.84)<0.01 else "FAIL","inv_summary grand 2009",round(amanah9+am9,2),21813224824.84)

json.dump(CHECKS,open('/tmp/checks_bs.json','w'))
print("\n--- new checks ---")
for c in CHECKS[2:]: print(c)
