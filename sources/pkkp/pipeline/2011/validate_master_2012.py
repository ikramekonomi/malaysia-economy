#!/usr/bin/env python3
"""Master validation for PKKP 2012 warehouse. Emits:
 - _validation_checks_2012.csv           (full internal suite)
 - _validation_checks_memoranda_2012.csv (register family)
Checks derive from THIS volume's own printed totals. Discrepancies reported, never corrected.
"""
import csv, os
from collections import defaultdict
WH=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "2012")
def load(name):
    with open(f"{WH}/{name}.csv",encoding="utf-8") as f: return list(csv.DictReader(f))
def F(x):
    x=(x or "").strip()
    if x in ("","-","–","—","None"): return 0.0
    return float(x)

main=[]; memo=[]
def add(bucket,check,ext,pr,tol=1.0):
    try: d=float(ext)-float(pr); ok=abs(d)<=tol
    except (TypeError,ValueError): d=""; ok=False
    bucket.append(("PASS" if ok else "FAIL",check,ext,pr,d))
def amt(rows,pred,col):
    v=[F(r[col]) for r in rows if pred(r)]
    return v[0] if len(v)==1 else (sum(v) if v else None)

# A. Financial position
fp=load("fact_financial_position")
for yr in (2012,2011):
    g=lambda item: amt(fp,lambda r:r["line_item_bm"]==item and int(r["year"])==yr,"amount_rm")
    add(main,f"FP WANG TUNAI+PELABURAN==JUMLAH WANG AWAM {yr}", g("WANG TUNAI")+g("PELABURAN"), g("JUMLAH WANG AWAM"))
    add(main,f"FP 3 DISATUKAN==JUMLAH KUMPULAN WANG DISATUKAN {yr}",
        g("AKAUN HASIL DISATUKAN")+g("AKAUN PINJAMAN DISATUKAN")+g("AKAUN AMANAH DISATUKAN"), g("JUMLAH KUMPULAN WANG DISATUKAN"))
    add(main,f"FP balance WANG AWAM==KUMPULAN WANG DISATUKAN {yr}", g("JUMLAH WANG AWAM"), g("JUMLAH KUMPULAN WANG DISATUKAN"))

# B. Cash statement
cs=load("fact_cash_statement")
def citem(item,yr,cat=None,flow=None):
    return amt(cs,lambda r:r["item_bm"]==item and int(r["year"])==yr and (cat is None or r["category_bm"]==cat) and (flow is None or r["flow"]==flow),"amount_rm")
for yr in (2012,2011):
    for cat,items,tot in [
        ("Hasil",["Hasil Cukai","Hasil Bukan Cukai","Terimaan Bukan Hasil","Hasil Wilayah Persekutuan"],"Jumlah Hasil"),
        ("Pinjaman",["Dalam Negeri","Luar Negeri"],"Jumlah Pinjaman"),
        ("Bantuan Luar Negeri",["Pinjaman Multilateral","Pinjaman Bilateral"],"Jumlah Bantuan Luar Negeri"),
        ("Terimaan Modal",["Terimaan Balik Pinjaman","Terimaan Balik Pendahuluan","Jualan Aset Modal","Pelbagai Terimaan Modal"],"Jumlah Terimaan Modal"),
        ("Terimaan Amanah",["Inisiatif Pembiayaan Swasta (PFI)","Aktiviti Pembangunan Khas Pembiayaan Swasta","Pelbagai"],"Jumlah Terimaan Amanah"),
        ("Perbelanjaan Mengurus",["Emolumen","Perkhidmatan dan Bekalan","Aset","Pemberian dan Kenaan Bayaran Tetap","Perbelanjaan-perbelanjaan Lain"],"Jumlah Perbelanjaan Mengurus"),
        ("Perbelanjaan Pembangunan",["Langsung","Pinjaman"],"Jumlah Perbelanjaan Pembangunan"),
        ("Perbelanjaan Amanah",["Inisiatif Pembiayaan Swasta (PFI)","Aktiviti Pembangunan Khas Pembiayaan Swasta","Pelbagai"],"Jumlah Perbelanjaan Amanah"),
    ]:
        s=sum(citem(i,yr,cat) or 0 for i in items)
        add(main,f"CASH {cat} items==total {yr}", s, citem(tot,yr,cat))
    jt=citem("Jumlah Terimaan",yr); jb=citem("Jumlah Bayaran",yr)
    ter=sum(citem("Jumlah "+c,yr,c,"TERIMAAN") or 0 for c in ["Hasil","Pinjaman","Bantuan Luar Negeri","Terimaan Modal","Terimaan Amanah"])
    add(main,f"CASH sum(terimaan cats)==Jumlah Terimaan {yr}", ter, jt)
    bay=sum(citem("Jumlah "+c,yr,c,"BAYARAN") or 0 for c in ["Perbelanjaan Mengurus","Perbelanjaan Pembangunan","Perbelanjaan Amanah","Pinjaman","Bantuan Luar Negeri","Perbelanjaan Modal"])
    add(main,f"CASH sum(bayaran cats)==Jumlah Bayaran {yr}", bay, jb)
    tamb=citem("Tambahan/(Kurangan) Wang Tunai",yr)
    add(main,f"CASH Terimaan-Bayaran==Tambahan {yr}", (jt or 0)-(jb or 0), tamb)
    add(main,f"CASH 1Jan+Tambahan==31Dis {yr}", (citem("Wang Tunai Pada 1 Januari",yr) or 0)+(tamb or 0), citem("WANG TUNAI PADA 31 DISEMBER",yr))
add(main,"CASH 31Dis 2012==FP WANG TUNAI 2012", citem("WANG TUNAI PADA 31 DISEMBER",2012),
    amt(fp,lambda r:r["line_item_bm"]=="WANG TUNAI" and int(r["year"])==2012,"amount_rm"))

# C. Performance
pf=load("fact_financial_performance")
def pfv(code,yr,basis="sebenar"):
    return amt(pf,lambda r:r["line_code"]==code and int(r["year"])==yr and r["basis"]==basis,"amount_rm")
for yr in (2012,2011):
    add(main,f"PERF HASIL-Belanja Mengurus==LEBIHAN HASIL {yr}", (pfv("revenue",yr) or 0)-(pfv("opex",yr) or 0), pfv("current_balance",yr))
    add(main,f"PERF LEBIHAN-Belanja Pembangunan==KURANGAN KESELURUHAN {yr}", (pfv("current_balance",yr) or 0)-(pfv("devex",yr) or 0), pfv("overall_deficit",yr))
    fin=sum(pfv(c,yr) or 0 for c in ["financing_net_borrowing","financing_capital_receipts","financing_cash_inv_trust_change"])
    add(main,f"PERF financing==JUMLAH PEMBIAYAAN {yr}", fin, pfv("total_financing",yr))
    add(main,f"PERF JUMLAH PEMBIAYAAN==-KURANGAN KESELURUHAN {yr}", pfv("total_financing",yr), -(pfv("overall_deficit",yr) or 0))

# D. Memorandum accessor
mem=load("fact_memorandum")
def memv(item,yr): return amt(mem,lambda r:r["line_item_bm"]==item and int(r["year"])==yr,"amount_rm")

# E. Revenue (Nota 5a)
rev=load("fact_revenue")
for col in ["anggaran_asal_rm","anggaran_disemak_rm","sebenar_rm"]:
    for cat in ["HASIL CUKAI","HASIL BUKAN CUKAI","TERIMAAN BUKAN HASIL","HASIL WILAYAH PERSEKUTUAN"]:
        items=[F(r[col]) for r in rev if r["level"]=="3" and r["category_l1_bm"]==cat]
        sub=[F(r[col]) for r in rev if r["level"]=="1" and r["category_l1_bm"]==cat]
        if items and sub: add(main,f"REV {cat} items==Jumlah [{col}]", sum(items), sub[0])
    subs=[F(r[col]) for r in rev if r["level"]=="1"]; grand=[F(r[col]) for r in rev if r["level"]=="0"]
    if grand: add(main,f"REV sum(L1)==JUMLAH HASIL [{col}]", sum(subs), grand[0])
add(main,"REV JUMLAH HASIL sebenar==PERF HASIL 2012", [F(r["sebenar_rm"]) for r in rev if r["level"]=="0"][0], pfv("revenue",2012))

# E2. Revenue account statement (Nota 5)
ras=load("fact_revenue_account_statement")
def rasv(item,yr,col="sebenar_rm"): return amt(ras,lambda r:r["line_item_bm"]==item and int(r["year"])==yr,col)
add(main,"NOTA5 Jumlah Hasil sebenar 2012==207,912,754,669", rasv("Jumlah Hasil",2012), 207912754669)
_before=[r for r in ras if "sebelum pindahan" in r["line_item_bm"].lower() and int(r["year"])==2012]
if _before: add(main,"NOTA5 Jumlah Perb Mengurus (sebelum pindahan)==205,537,081,525", F(_before[0]["sebenar_rm"]), 205537081525)

# F. Opex maksud + Nota5b vs Lampiran1
om=load("fact_opex_maksud"); om_sum=sum(F(r["sebenar_rm"]) for r in om)
add(main,"OPEX maksud count==50", len(om), 50, tol=0)
add(main,"OPEX maksud sum sebenar(selepas pindahan)==207,912,754,669", om_sum, 207912754669, tol=1.0)
add(main,"OPEX sebelum pindahan==Prestasi Belanja Mengurus", om_sum-2375673144, pfv("opex",2012))
add(main,"OPEX maksud asal sum==181,584,000,000", sum(F(r["anggaran_asal_rm"]) for r in om), 181584000000)
add(main,"OPEX maksud dipinda sum==198,737,824,368", sum(F(r["anggaran_dipinda_rm"]) for r in om), 198737824368)
od=load("fact_opex_detail")
jm={r["maksud_code"]:r for r in od if r["row_type"]=="jumlah_maksud"}
gl=[F(r["sebenar_rm"]) for r in od if r["row_type"]=="jumlah_besar"]
add(main,"LAMP1 jumlah_besar sebenar==207,912,754,669.08", gl[0] if gl else None, 207912754669.08)
add(main,"LAMP1 sum(jumlah_maksud)==jumlah_besar", sum(F(r["sebenar_rm"]) for r in jm.values()), gl[0] if gl else None)
omd={r["maksud_code"]:r for r in om}; nmatch=0
for code,r in omd.items():
    if code in jm:
        e=F(jm[code]["sebenar_rm"]); p=F(r["sebenar_rm"])
        if abs(e-p)<=1.0: nmatch+=1
        else: add(main,f"NOTA5b vs LAMP1 {code} sebenar", e, p)
add(main,f"NOTA5b vs LAMP1 per-maksud ({nmatch}/50 within sen-rounding)", nmatch, 50, tol=0)

# G. Lampiran1 additivity by level (object_program are class-recap duplicates of object_aktiviti,
#    so they are NOT summed with leaves). Check aktiviti->, program->maksud levels.
# (G1) aktiviti: sum(object_aktiviti) == jumlah_aktiviti
aktsum=defaultdict(float); akttot={}
for r in od:
    key=(r["maksud_code"],r["program_code"],r["aktiviti_code"])
    if r["row_type"]=="object_aktiviti": aktsum[key]+=F(r["sebenar_rm"])
    elif r["row_type"]=="jumlah_aktiviti": akttot[key]=F(r["sebenar_rm"])
ap=afail=0; afails=[]
for key,tot in akttot.items():
    if abs(aktsum.get(key,0)-tot)<=1.0: ap+=1
    else: afail+=1; afails.append((key,aktsum.get(key,0),tot))
add(main,f"LAMP1 aktiviti additivity sum(object)==jumlah_aktiviti ({ap} pass / {afail} fail; fails are SOURCE PRINT DISCREPANCIES kept as printed)", ap, ap+afail, tol=0)
for key,e,p in afails[:8]: add(main,f"LAMP1 aktiviti {key[0]}/{key[1]}/{key[2]} object-sum vs printed jumlah_aktiviti (SOURCE PRINT DISCREPANCY, KEPT AS PRINTED)", e, p)
# (G2) program -> maksud: contribution = jumlah_program if present, else sum(jumlah_aktiviti)
# (single-aktiviti programs may omit the printed program subtotal - use aktiviti subtotals then).
hasprog=set(); mprog=defaultdict(float); maktbyprog=defaultdict(float)
for r in od:
    pk=(r["maksud_code"],r["program_code"])
    if r["row_type"]=="jumlah_program": hasprog.add(pk); mprog[pk]+=F(r["sebenar_rm"])
    elif r["row_type"]=="jumlah_aktiviti": maktbyprog[pk]+=F(r["sebenar_rm"])
mcontrib=defaultdict(float)
allprogs={(r["maksud_code"],r["program_code"]) for r in od if r["program_code"]}
for pk in allprogs:
    mcontrib[pk[0]]+= mprog[pk] if pk in hasprog else maktbyprog[pk]
gp=gfail=0; gfails=[]
for code,r in jm.items():
    if abs(mcontrib.get(code,0)-F(r["sebenar_rm"]))<=1.5: gp+=1
    else: gfail+=1; gfails.append((code,mcontrib.get(code,0),F(r["sebenar_rm"])))
add(main,f"LAMP1 program->maksud sum(program contributions)==jumlah_maksud ({gp} pass / {gfail} fail)", gp, gp+gfail, tol=0)
for code,e,p in gfails[:8]: add(main,f"LAMP1 maksud {code} sum(programs)==jumlah_maksud", e, p)

# H. Devex
dp=load("fact_devex_project"); dm=load("fact_devex_maksud")
proj=[r for r in dp if r["row_type"]=="project"]
idp=sum(1 for r in proj if abs((F(r["sebenar_langsung_rm"])+F(r["sebenar_pinjaman_rm"]))-F(r["sebenar_jumlah_rm"]))<=0.5)
add(main,f"DEVEX per-row sebenar identity ({idp}/{len(proj)})", idp, len(proj), tol=0)
ida=sum(1 for r in proj if abs((F(r["anggaran_langsung_rm"])+F(r["anggaran_pinjaman_rm"]))-F(r["anggaran_jumlah_rm"]))<=0.5)
add(main,f"DEVEX per-row anggaran identity ({ida}/{len(proj)})", ida, len(proj), tol=0)
mp=defaultdict(lambda: defaultdict(float))
for r in proj:
    for c in ["sebenar_langsung_rm","sebenar_pinjaman_rm","sebenar_jumlah_rm"]: mp[r["maksud_code"]][c]+=F(r[c])
dmm={r["maksud_code"]:r for r in dm if r["maksud_code"]!="TOTAL"}; mpass=0
for code,r in dmm.items():
    if all(abs(mp[code][c]-F(r[c]))<=1.0 for c in ["sebenar_langsung_rm","sebenar_pinjaman_rm","sebenar_jumlah_rm"]): mpass+=1
    else: add(main,f"DEVEX maksud {code} project-sum==Jumlah", mp[code]["sebenar_jumlah_rm"], F(r["sebenar_jumlah_rm"]))
add(main,f"DEVEX maksud reconciliation ({mpass}/{len(dmm)})", mpass, len(dmm), tol=0)
tot=[r for r in dm if r["maksud_code"]=="TOTAL"]
gj=F(tot[0]["sebenar_jumlah_rm"]) if tot else sum(mp[c]["sebenar_jumlah_rm"] for c in dmm)
add(main,"DEVEX grand sebenar_jumlah==46,932,453,806", gj, 46932453806, tol=1.0)
add(main,"DEVEX grand==Prestasi Belanja Pembangunan", gj, pfv("devex",2012))
gl_=F(tot[0]["sebenar_langsung_rm"]) if tot else sum(mp[c]["sebenar_langsung_rm"] for c in dmm)
gp_=F(tot[0]["sebenar_pinjaman_rm"]) if tot else sum(mp[c]["sebenar_pinjaman_rm"] for c in dmm)
add(main,"DEVEX grand langsung==cash Langsung 44,978,124,405", gl_, citem("Langsung",2012,"Perbelanjaan Pembangunan"))
add(main,"DEVEX grand pinjaman==cash Pinjaman 1,954,329,401", gp_, citem("Pinjaman",2012,"Perbelanjaan Pembangunan"))

# I. Trust (Nota 7)
ta=load("fact_trust_accounts"); rf=0
for r in ta:
    e=F(r["baki_awal_rm"])+F(r["kredit_rm"])-F(r["debit_rm"])
    if abs(e-F(r["baki_akhir_rm"]))<=0.5: rf+=1
    else: add(main,f"TRUST roll-forward {r['account_bm']}", e, F(r["baki_akhir_rm"]))
add(main,f"TRUST roll-forward ({rf}/{len(ta)})", rf, len(ta), tol=0)
grand=[r for r in ta if r["parent_group_bm"]=="JUMLAH"][0]
add(main,"TRUST grand baki_akhir==12,637,039,514", grand["baki_akhir_rm"], 12637039514)
add(main,"TRUST grand==FP AKAUN AMANAH DISATUKAN 2012", F(grand["baki_akhir_rm"]),
    amt(fp,lambda r:r["line_item_bm"]=="AKAUN AMANAH DISATUKAN" and int(r["year"])==2012,"amount_rm"))
for col in ["baki_awal_rm","debit_rm","kredit_rm","baki_akhir_rm"]:
    subs=[F(r[col]) for r in ta if r["parent_group_bm"]==""]
    add(main,f"TRUST sum(group subtotals)==grand [{col}]", sum(subs), F(grand[col]))

# J. Debt (Nota 9)
dbt=load("fact_debt")
def dv(item,yr): return amt(dbt,lambda r:r["item_bm"]==item and int(r["year"])==yr,"amount_rm")
for yr in (2012,2011):
    dn=sum(dv(i,yr) or 0 for i in ["Bil Perbendaharaan","Terbitan Pelaburan Kerajaan","Sekuriti Kerajaan Malaysia","Sukuk"])
    add(main,f"DEBT DN instruments==Dalam Negeri subtotal {yr}", dn, dv("Dalam Negeri",yr))
    jp=(dv("Dalam Negeri",yr) or 0)+(dv("Pembiayaan Kumpulan Wang Pinjaman Perumahan",yr) or 0)+(dv("Pinjaman Pasaran",yr) or 0)
    add(main,f"DEBT DN+KWPP+LN==Jumlah Pinjaman {yr}", jp, dv("Jumlah Pinjaman",yr))
    add(main,f"DEBT Multi+Bi==Jumlah Bantuan {yr}", (dv("Pinjaman Multilateral",yr) or 0)+(dv("Pinjaman Bilateral",yr) or 0), dv("Jumlah Bantuan Luar Negeri",yr))
    add(main,f"DEBT Jumlah Pinjaman+Bantuan==JUMLAH HUTANG AWAM {yr}", (dv("Jumlah Pinjaman",yr) or 0)+(dv("Jumlah Bantuan Luar Negeri",yr) or 0), dv("JUMLAH HUTANG AWAM",yr))
    add(main,f"DEBT JUMLAH HUTANG AWAM==Memorandum {yr}", dv("JUMLAH HUTANG AWAM",yr), memv("Hutang Awam",yr))
    add(main,f"DEBT PELBAGAI LIABILITI==Memorandum {yr}", dv("PELBAGAI LIABILITI",yr), memv("Pelbagai Liabiliti",yr))

# K. Loan account statement (Nota 6)
las=load("fact_loan_account_statement")
clo=amt(las,lambda r:int(r["year"])==2012 and "BAKI AKAUN PINJAMAN DISATUKAN" in r["line_item_bm"].upper(),"amount_rm")
add(main,"NOTA6 BAKI 31 DIS 2012==28,904,795,292", clo, 28904795292)
add(main,"NOTA6 BAKI==FP AKAUN PINJAMAN DISATUKAN 2012", clo, amt(fp,lambda r:r["line_item_bm"]=="AKAUN PINJAMAN DISATUKAN" and int(r["year"])==2012,"amount_rm"))

# L. Timeseries 2012 ties (juta)
ts=load("fact_timeseries_2003_2012")
def tsv(item,yr=2012): return amt(ts,lambda r:r["line_item_bm"].strip()==item and int(r["year"])==yr,"amount_rm_juta")
for item,full in [("Wang Tunai",29355825184),("Pelaburan",24049136708),("Jumlah Wang Awam",53404961892)]:
    v=tsv(item)
    if v is not None: add(main,f"TS 2012 {item}(juta)~statement/1e6", v, round(full/1e6), tol=1.0)

# ============ MEMORANDA FAMILY ============
lr=load("fact_loans_receivable"); det=[r for r in lr if r["row_type"]=="detail"]
idl=sum(1 for r in det if abs((F(r["pembangunan_rm"])+F(r["hasil_disatukan_rm"])+F(r["amanah_lain_rm"]))-F(r["baki_belum_selesai_rm"]))<=0.5)
add(memo,f"LOANS row identity ({idl}/{len(det)})", idl, len(det), tol=0)
glr=[r for r in lr if r["row_type"]=="total"]
add(memo,"LOANS grand baki==95,492,612,802.62", F(glr[0]["baki_belum_selesai_rm"]) if glr else sum(F(r["baki_belum_selesai_rm"]) for r in det), 95492612802.62, tol=1.0)
add(memo,"LOANS grand==Memorandum Pinjaman Boleh Dituntut 2012", F(glr[0]["baki_belum_selesai_rm"]) if glr else 0, memv("Pinjaman Boleh Dituntut",2012), tol=1.0)
inv=load("fact_investments"); gi=[r for r in inv if r["row_type"]=="total"]
add(memo,"INV grand nilai_buku==27,194,316,450.28", F(gi[0]["nilai_buku_rm"]) if gi else sum(F(r["nilai_buku_rm"]) for r in inv if r["row_type"]=="detail"), 27194316450.28, tol=1.0)
add(memo,"INV grand==Memorandum Pelaburan 2012", F(gi[0]["nilai_buku_rm"]) if gi else 0, memv("Pelaburan",2012), tol=1.0)
gu=load("fact_statutory_guarantees"); gd=[r for r in gu if r["row_type"]=="detail"]
idg=sum(1 for r in gd if abs((F(r["dalam_negeri_rm"])+F(r["luar_negeri_rm"]))-F(r["jumlah_rm"]))<=0.5)
add(memo,f"GUAR row identity ({idg}/{len(gd)})", idg, len(gd), tol=0)
gg=[r for r in gu if r["row_type"]=="total"]
if gg: add(memo,"GUAR JUMLAH JAMINAN dalam+luar==jumlah", F(gg[0]["dalam_negeri_rm"])+F(gg[0]["luar_negeri_rm"]), F(gg[0]["jumlah_rm"]))
cc=load("fact_cash_components")
for yr,want in [(2012,29355825184),(2011,24466775527)]:
    comp=sum(F(r["amount_rm"]) for r in cc if int(r["year"])==yr and r["row_type"]=="detail")
    jum=amt(cc,lambda r:int(r["year"])==yr and r["row_type"]=="total","amount_rm")
    add(memo,f"CASHCOMP sum(detail)==JUMLAH {yr}", comp, jum if jum else want)
    add(memo,f"CASHCOMP JUMLAH=={want} {yr}", jum, want)
iv=load("fact_investment_summary")
for yr,want in [(2012,24049136708),(2011,22843463212)]:
    tot=amt(iv,lambda r:int(r["year"])==yr and r["row_type"]=="total" and "JUMLAH PELABURAN" in r["line_item_bm"].upper(),"amount_rm")
    add(memo,f"INVSUM JUMLAH PELABURAN=={want} {yr}", tot, want)
    add(memo,f"INVSUM==FP PELABURAN {yr}", tot, amt(fp,lambda r:r["line_item_bm"]=="PELABURAN" and int(r["year"])==yr,"amount_rm"))
ma=load("fact_memo_assets_detail")
for sec,yr,want in [("Pinjaman Boleh Dituntut",2012,95492612803),("Pelaburan",2012,27194316450)]:
    tot=amt(ma,lambda r:r["section_bm"]==sec and int(r["year"])==yr and r["row_type"] in ("total","subtotal"),"amount_rm")
    add(memo,f"MEMOASSET {sec} total {yr}=={want}", tot, want, tol=1.0)
cm=load("fact_commitment_detail")
for yr,want in [(2012,275621222),(2011,241513526)]:
    d=sum(F(r["amount_rm"]) for r in cm if int(r["year"])==yr and r["row_type"]=="detail")
    tot=amt(cm,lambda r:int(r["year"])==yr and r["row_type"]=="total","amount_rm")
    add(memo,f"COMMIT sum(detail)==JUMLAH {yr}", d, tot if tot else want)
    add(memo,f"COMMIT JUMLAH=={want} {yr}", tot, want)

def dump(path,rows):
    with open(path,"w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["status","check","extracted_value","printed_value","difference"]); w.writerows(rows)
dump(f"{WH}/_validation_checks_memoranda_2012.csv",memo)
allrows=main+[(s,"memoranda: "+c,e,p,d) for s,c,e,p,d in memo]
dump(f"{WH}/_validation_checks_2012.csv",allrows)
mpn=sum(1 for r in main if r[0]=="PASS"); kp=sum(1 for r in memo if r[0]=="PASS")
print(f"main checks: {mpn}/{len(main)} pass, {len(main)-mpn} fail")
print(f"memoranda checks: {kp}/{len(memo)} pass, {len(memo)-kp} fail")
print("FAILURES:")
for s,c,e,p,d in main+memo:
    if s=="FAIL": print(f"  {c}: ext={e} printed={p} diff={d}")
