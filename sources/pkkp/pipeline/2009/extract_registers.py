import sys, re; sys.path.insert(0,'/home/claude/pkkp/work/2009/pipeline')
import lib2009 as L, json
SRC=L.SRC; CHK=[]
def chk(cond,name,e,p): CHK.append(["PASS" if cond else "FAIL",name,e,p,'' if(e is None or p is None) else round(e-p,2)])
def money_tail(line,n):
    toks=L.numtokens(line); 
    if len(toks)<n: return None
    return [L.parse_num(t) for t in toks[-n:]]

# ============ D loan_account_statement (pdf93-94) ============
STMT="D Penyata Akaun Pinjaman Disatukan"
rr=[]; group=None; sub=None
for pdf in (93,94):
    if L.printed_of(pdf) and L.printed_of(pdf)>90: pass
    pr=L.printed_of(pdf)
    for l in L.lines(pdf):
        s=l.strip(); toks=L.numtokens(l)
        if not s or 'Penyata Akaun Pinjaman' in s or 'seperti pada' in s or '.indd' in s or s in('RM',): continue
        if 'Akaun Amanah' in s or 'E ' in s[:3] and 'Penyata' in s: break
        if not toks:
            if s.isupper(): 
                if s.startswith('PINJAMAN DALAM') or s.startswith('PINJAMAN LUAR'): group=s; sub=None
                else: sub=s
            continue
        m=money_tail(l,2)
        if m is None: continue
        rt='line'
        if s.startswith('JUMLAH'): rt='total'
        elif s.startswith('Jumlah'): rt='subtotal'
        elif s.startswith('Baki pada 31'): rt='closing'
        elif s.startswith('Baki pada 1'): rt='opening'
        rr.append([group or '',sub or '',re.sub(r'\s{2,}.*$','',s).strip(),rt,2009,L.fmt(m[0][0]),SRC,pdf,pr,STMT])
        rr.append([group or '',sub or '',re.sub(r'\s{2,}.*$','',s).strip(),rt,2008,L.fmt(m[1][0]),SRC,pdf,pr,STMT])
L.write_csv("fact_loan_account_statement.csv",
 ["group_bm","sub_bm","line_item_bm","row_type","year","amount_rm","source_file","pdf_page","printed_page","statement"],rr)

# ============ G1 fact_debt (pdf185) ============
STMT="G1 Penyata Akaun Memorandum Hutang Awam"; pdf=185; pr=L.printed_of(pdf)
dd=[]; group=None; kind=None
for l in L.lines(pdf):
    s=l.strip(); toks=L.numtokens(l)
    if not s or 'Hutang Awam' in s or 'seperti pada' in s or '.indd' in s or s=='RM': continue
    if not toks:
        if s in ('DALAM NEGERI','LUAR NEGERI'): group=s; kind=None
        elif s.isupper(): kind=s.title()
        continue
    m=money_tail(l,2)
    if not m: continue
    item=re.sub(r'\s{2,}.*$','',s).strip()
    rt='total' if s.startswith('JUMLAH') else ('subtotal' if s.startswith('Jumlah') else 'line')
    for yr,v in ((2009,m[0][0]),(2008,m[1][0])):
        dd.append([group or '',item,kind or '',yr,L.fmt(v),SRC,pdf,pr,STMT])
L.write_csv("fact_debt.csv",["group_bm","item_bm","kind","year","amount_rm","source_file","pdf_page","printed_page","statement"],dd)
tot=[float(r[4]) for r in dd if r[1].startswith('JUMLAH HUTANG AWAM') and r[3]==2009][0]
chk(abs(tot-362386171109.62)<0.5,"debt JUMLAH HUTANG AWAM 2009==memo",tot,362386171109.62)
dn=[float(r[4]) for r in dd if r[1]=='Jumlah Dalam Negeri' and r[3]==2009][0]
ln=[float(r[4]) for r in dd if r[1]=='Jumlah Luar Negeri' and r[3]==2009][0]
chk(abs(dn+ln-tot)<0.5,"debt Dalam+Luar==Jumlah 2009",dn+ln,tot)

# ============ G2 fact_statutory_guarantees (pdf186-...) ============
STMT="G2 Penyata Akaun Memorandum Jaminan"
gg=[]; jenis=None
for pdf in range(186,187):
    pr=L.printed_of(pdf)
    for l in L.lines(pdf):
        s=l.strip(); toks=L.numtokens(l)
        if not s or 'Memorandum Jaminan' in s or 'seperti pada' in s or '.indd' in s or s in('RM','Jumlah'): continue
        if not toks:
            if s.isupper(): jenis=s.title()
            continue
        m=money_tail(l,4)  # dalam, luar, jumlah2009, 2008
        if not m: continue
        item=re.sub(r'\s{2,}.*$','',s).strip()
        rt='subtotal' if s.startswith('Jumlah') else ('total' if s.startswith('JUMLAH') else 'line')
        gg.append([jenis or '','',item,rt,2009,L.fmt(m[0][0]),L.fmt(m[1][0]),L.fmt(m[2][0]),SRC,pdf,pr,STMT])
        gg.append([jenis or '','',item,rt,2008,'','',L.fmt(m[3][0]),SRC,pdf,pr,STMT])
L.write_csv("fact_statutory_guarantees.csv",
 ["jenis_jaminan_bm","kategori_bm","agensi_bm","row_type","year","dalam_negeri_rm","luar_negeri_rm","jumlah_rm","source_file","pdf_page","printed_page","statement"],gg)

# ============ G3 -> fact_other_notes (Pelbagai Liabiliti) ============
STMT="G3 Penyata Akaun Memorandum Pelbagai Liabiliti"; pdf=187; pr=L.printed_of(pdf)
on=[]
for l in L.lines(pdf):
    s=l.strip(); toks=L.numtokens(l)
    if not s or 'Pelbagai Liabiliti' in s or 'seperti pada' in s or '.indd' in s or s=='RM': continue
    m=money_tail(l,2)
    if not m: continue
    item=re.sub(r'\s{2,}.*$','',s).strip()
    rt='total' if s.startswith('JUMLAH') else 'line'
    for yr,v in ((2009,m[0][0]),(2008,m[1][0])):
        on.append(['G3(13c)',item,yr,L.fmt(v),rt,False,SRC,pdf,pr,STMT])
L.write_csv("fact_other_notes.csv",["nota","line_item_bm","year","amount_rm","row_type","has_footnote","source_file","pdf_page","printed_page","statement"],on)

# ============ F3 -> fact_memo_assets_detail (Jaminan Deposit Berkanun) ============
STMT="F3 Penyata Akaun Memorandum Jaminan Deposit Berkanun"; pdf=182; pr=L.printed_of(pdf)
fa=[]; section=None
for l in L.lines(pdf):
    s=l.strip(); toks=L.numtokens(l)
    if not s or 'Jaminan Deposit' in s or 'seperti pada' in s or '.indd' in s or s=='RM': continue
    if not toks:
        if s.isupper(): section=s.title()
        continue
    m=money_tail(l,2)
    if not m: continue
    item=re.sub(r'\s{2,}.*$','',s).strip()
    rt='total' if s.startswith('JUMLAH') else ('subtotal' if s.startswith('Jumlah') else 'line')
    for yr,v in ((2009,m[0][0]),(2008,m[1][0])):
        fa.append([section or '',item,yr,L.fmt(v),rt,False,SRC,pdf,pr,STMT])
L.write_csv("fact_memo_assets_detail.csv",["section_bm","line_item_bm","year","amount_rm","row_type","has_footnote","source_file","pdf_page","printed_page","statement"],fa)
f3tot=[float(r[3]) for r in fa if r[1].startswith('JUMLAH') and r[2]==2009]
if f3tot: chk(abs(f3tot[0]-39200285.96)<0.5,"F3 JUMLAH JAMINAN DEPOSIT 2009==memo",f3tot[0],39200285.96)
g3tot=[float(r[3]) for r in on if r[1].startswith('JUMLAH') and r[2]==2009]
if g3tot: chk(abs(g3tot[0]-173364115.20)<0.5,"G3 JUMLAH PELBAGAI LIABILITI 2009==memo",g3tot[0],173364115.20)
g2tot=[float(r[7]) for r in gg if r[2].startswith('JUMLAH') and r[4]==2009]
print("loan_acct:",len(rr),"debt:",len(dd),"g2_guarantees:",len(gg),"g3_other:",len(on),"f3_memo_assets:",len(fa))
json.dump(CHK,open('/tmp/checks_reg.json','w'))
for c in CHK: print(c)
