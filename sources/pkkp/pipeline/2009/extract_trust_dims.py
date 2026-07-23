import sys, re, csv; sys.path.insert(0,'/home/claude/pkkp/work/2009/pipeline')
import lib2009 as L, json
SRC=L.SRC; CHK=[]
def chk(cond,name,e,p): CHK.append(["PASS" if cond else "FAIL",name,e,p,'' if(e is None or p is None) else round(e-p,2)])
def tail2(l):
    t=L.numtokens(l)
    return [L.parse_num(x) for x in t[-2:]] if len(t)>=2 else None

# ===== fact_trust_accounts (E summary pdf95) =====
STMT="E Penyata Akaun Amanah Disatukan"; pdf=95; pr=L.printed_of(pdf)
ta=[]; grp=None
for l in L.lines(pdf):
    s=l.strip()
    if not s or 'Akaun Amanah' in s or 'seperti pada' in s or '.indd' in s or 'Butir' in s or s=='RM': continue
    m=tail2(l)
    if not m:
        if s.isupper(): grp=s.title()
        continue
    item=re.sub(r'\s{2,}.*$','',s).strip()
    # store balances: baki_akhir=2009, baki_awal=2008
    ta.append([grp or '',item,2009,L.fmt(m[1][0]),'','',L.fmt(m[0][0]),SRC,pdf,pr,STMT])
L.write_csv("fact_trust_accounts.csv",
 ["parent_group_bm","account_bm","year","baki_awal_rm","debit_rm","kredit_rm","baki_akhir_rm","source_file","pdf_page","printed_page","statement"],ta)

# ===== fact_trust_fund_detail (E2 pdf152-160 + E3 pdf161-169) =====
STMT2="E2/E3 Kumpulan Wang Amanah Awam / Wang Deposit"
td=[]; fg=None; section=None
def proc(pdf, default_fg):
    global fg, section
    pr=L.printed_of(pdf)
    for l in L.lines(pdf):
        s=l.strip()
        if not s or 'Kumpulan Wang Amanah Awam' in s or 'Wang Deposit' in s or 'seperti pada' in s or '.indd' in s or s in('RM',) or '(Sambungan)' in s or '(Debit)/Kredit' in s or s=='Perihal': continue
        m=tail2(l)
        if not m:
            up=s.replace(' – (SAMB.)','').replace('– (SAMB.)','').strip()
            if up in ('AMANAH KHAS','AMANAH AM','DEPOSIT AM','DEPOSIT PELARASAN'): fg=up.title(); section=None
            elif s.isupper(): section=up.title()
            continue
        item=re.sub(r'\s{2,}.*$','',s).strip()
        rt='total' if s.startswith('JUMLAH') else ('subtotal' if s.startswith('Jumlah') else 'detail')
        td.append([fg or default_fg,section or '',section or '',item,2009,L.fmt(m[0][0]),rt,('*' in l),SRC,pdf,pr,STMT2])
        td.append([fg or default_fg,section or '',section or '',item,2008,L.fmt(m[1][0]),rt,False,SRC,pdf,pr,STMT2])
for pdf in range(152,161): proc(pdf,'Amanah Awam')
for pdf in range(161,170): proc(pdf,'Wang Deposit')
L.write_csv("fact_trust_fund_detail.csv",
 ["fund_group_bm","fund_bm","section_bm","line_item_bm","year","amount_rm","row_type","has_footnote","source_file","pdf_page","printed_page","statement"],td)
e2=[float(r[5]) for r in td if r[3].startswith('JUMLAH KUMPULAN WANG AMANAH AWAM') and r[4]==2009]
if e2: chk(abs(e2[0]-9403151496.18)<0.5,"E2 JUMLAH AMANAH AWAM 2009==E summary",e2[0],9403151496.18)
khas=[float(r[5]) for r in td if r[3].startswith('JUMLAH AMANAH KHAS') and r[4]==2009]
am=[float(r[5]) for r in td if r[3].startswith('JUMLAH AMANAH AM') and r[4]==2009]
if khas and am and e2: chk(abs(khas[0]+am[0]-e2[0])<0.5,"E2 Khas+Am==Awam 2009",khas[0]+am[0],e2[0])

# ===== dim_maksud (from opex + devex) =====
dim=[]
seen=set()
for f,jenis_map in [("fact_opex_maksud.csv",None),("fact_devex_maksud.csv",None)]:
    for r in csv.DictReader(open("/home/claude/pkkp/warehouse2009/"+f)):
        code=r.get('maksud_code','')
        if not code or code in ('TOTAL','') or code in seen: continue
        seen.add(code)
        if code[0]=='T': jenis='Tanggungan'
        elif code[0]=='B': jenis='Bekalan'
        elif code[0]=='P': jenis='Pembangunan'
        else: jenis=''
        name=r.get('maksud_name_bm','')
        num=re.sub(r'\D','',code)
        dim.append([code,int(num) if num else '',jenis,name,'','',2009])
dim.sort(key=lambda x:(x[2],x[1]))
L.write_csv("dim_maksud.csv",["maksud_code","code_num","jenis","name_bm","name_en","note","year"],dim)

# ===== append narrative note scalars to fact_other_notes =====
# read existing G3 rows, append Nota scalars
existing=list(csv.reader(open("/home/claude/pkkp/warehouse2009/fact_other_notes.csv")))
hdr=existing[0]; body=existing[1:]
notes=[
 ("3","Liabiliti Luar Jangka (Third Party War Risk - MAHB)",467000000.0,"scalar_juta_approx"),
 ("4","Akaun Belum Terima",21930769621.0,"scalar"),
 ("5","Wang Pendahuluan kepada Kontraktor",1749364360.0,"scalar"),
]
for nota,item,val,rt in notes:
    body.append([nota,item,2009,L.fmt(val),rt,False,SRC,41,34,"Nota kepada Penyata Kewangan"])
with open("/home/claude/pkkp/warehouse2009/fact_other_notes.csv","w",newline='') as f:
    w=csv.writer(f); w.writerow(hdr); w.writerows(body)
print("trust_accounts:",len(ta),"trust_fund_detail:",len(td),"dim_maksud:",len(dim),"other_notes:",len(body))
json.dump(CHK,open('/tmp/checks_trust.json','w'))
for c in CHK: print(c)
