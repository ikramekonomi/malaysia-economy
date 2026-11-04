#!/usr/bin/env python3
"""Master internal validation suite for the FY2011 warehouse, from this volume's
OWN printed totals. Writes:
  warehouse2011/_validation_checks_2011.csv            (core/notes/lampiran chains)
  warehouse2011/_validation_checks_memoranda_2011.csv  (registers L3/L4/L5 + memo assets)
Columns: status,check,extracted_value,printed_value,difference
"""
import os
import csv
import pandas as pd
WH=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "2011")
core=[]; memo=[]
def C(bucket,label,got,want,tol=0.5):
    try:
        g=float(got); w=float(want); d=g-w; st="PASS" if abs(d)<=tol else "FAIL"
        bucket.append((st,label,f"{g:.2f}",f"{w:.2f}",f"{d:.2f}"))
    except Exception:
        bucket.append(("PASS" if str(got)==str(want) else "FAIL",label,str(got),str(want),""))
def L(name): return pd.read_csv(f"{WH}/{name}")

# ---------- financial position ----------
fp=L("fact_financial_position.csv"); fp11=fp[fp.year==2011].set_index("line_item_bm").amount_rm
C(core,"finpos: Wang Tunai+Pelaburan=Jumlah Wang Awam", fp11["WANG TUNAI"]+fp11["PELABURAN"], fp11["JUMLAH WANG AWAM"])
C(core,"finpos: Hasil+Pinjaman+Amanah Disatukan=Jumlah KWD", fp11["AKAUN HASIL DISATUKAN"]+fp11["AKAUN PINJAMAN DISATUKAN"]+fp11["AKAUN AMANAH DISATUKAN"], fp11["JUMLAH KUMPULAN WANG DISATUKAN"])
C(core,"finpos: Wang Awam=KWD (balance)", fp11["JUMLAH WANG AWAM"], fp11["JUMLAH KUMPULAN WANG DISATUKAN"])

# ---------- cash statement ----------
cs=L("fact_cash_statement.csv"); c=cs[cs.year==2011]
def cv(flow,cat,item):
    r=c[(c.flow==flow)&(c.category_bm==cat)&(c.item_bm==item)].amount_rm
    return float(r.iloc[0]) if len(r) else 0.0
C(core,"cash: Jumlah Hasil", cv("TERIMAAN","Hasil","Hasil Cukai")+cv("TERIMAAN","Hasil","Hasil Bukan Cukai")+cv("TERIMAAN","Hasil","Terimaan Bukan Hasil")+cv("TERIMAAN","Hasil","Hasil Wilayah Persekutuan"), cv("TERIMAAN","Hasil","Jumlah Hasil"))
ter=cv("TERIMAAN","Hasil","Jumlah Hasil")+cv("TERIMAAN","Pinjaman","Jumlah Pinjaman")+cv("TERIMAAN","Bantuan Luar Negeri","Jumlah Bantuan Luar Negeri")+cv("TERIMAAN","Terimaan Modal","Jumlah Terimaan Modal")+cv("TERIMAAN","Terimaan Lain","Jumlah Terimaan Lain")
C(core,"cash: Jumlah Terimaan", ter, cv("JUMLAH","Jumlah Terimaan","Jumlah Terimaan"))
bay=cv("BAYARAN","Perbelanjaan Mengurus","Jumlah Perbelanjaan Mengurus")+cv("BAYARAN","Perbelanjaan Pembangunan","Jumlah Perbelanjaan Pembangunan")+cv("BAYARAN","Inisiatif Pembiayaan Swasta (PFI)","Inisiatif Pembiayaan Swasta (PFI)")+cv("BAYARAN","Perbelanjaan Modal","Pembelian Instrumen Kewangan")+cv("BAYARAN","Pinjaman","Jumlah Pinjaman")+cv("BAYARAN","Bantuan Luar Negeri","Jumlah Bantuan Luar Negeri")+cv("BAYARAN","Bayaran Lain","Akaun Amanah")
C(core,"cash: Jumlah Bayaran", bay, cv("JUMLAH","Jumlah Bayaran","Jumlah Bayaran"))
C(core,"cash: Tambahan tunai = Terimaan-Bayaran", ter-bay, cv("JUMLAH","Tambahan/(Kurangan) Wang Tunai","Tambahan/(Kurangan) Wang Tunai"))
C(core,"cash: 31 Dis = 1 Jan + Tambahan", cv("JUMLAH","Wang Tunai Pada 1 Januari","Wang Tunai Pada 1 Januari")+cv("JUMLAH","Tambahan/(Kurangan) Wang Tunai","Tambahan/(Kurangan) Wang Tunai"), cv("JUMLAH","WANG TUNAI PADA 31 DISEMBER","WANG TUNAI PADA 31 DISEMBER"))
C(core,"cash: 31 Dis = finpos Wang Tunai", cv("JUMLAH","WANG TUNAI PADA 31 DISEMBER","WANG TUNAI PADA 31 DISEMBER"), fp11["WANG TUNAI"])

# ---------- performance ----------
pf=L("fact_financial_performance.csv"); ps=pf[(pf.year==2011)&(pf.basis=="sebenar")].set_index("line_code").amount_rm
C(core,"prestasi: Lebihan Hasil = Hasil-Belanja Mengurus", ps["revenue"]-ps["opex"], ps["current_balance"])
C(core,"prestasi: Kurangan Keseluruhan = Lebihan-Belanja Pembangunan", ps["current_balance"]-ps["devex"], ps["overall_deficit"])
C(core,"prestasi: Jumlah Pembiayaan = 3 komponen", ps["financing_net_borrowing"]+ps["financing_capital_receipts"]+ps["financing_cash_inv_trust_change"], ps["total_financing"])
C(core,"prestasi: Pembiayaan = -Kurangan", ps["total_financing"], -ps["overall_deficit"])

# ---------- revenue Nota 5(a) chains ----------
rv=L("fact_revenue.csv")
for col in ("anggaran_asal_rm","anggaran_disemak_rm","sebenar_rm"):
    for cat in ["HASIL CUKAI","HASIL BUKAN CUKAI","TERIMAAN BUKAN HASIL","HASIL WILAYAH PERSEKUTUAN"]:
        items=rv[(rv.level==3)&(rv.category_l1_bm==cat)][col].sum()
        sub=rv[(rv.level==1)&(rv.category_l1_bm==cat)][col].sum()
        C(core,f"revenue {cat} items=Jumlah [{col}]", items, sub)
    subs=rv[rv.level==1][col].sum(); grand=rv[rv.level==0][col].iloc[0]
    C(core,f"revenue sum(Jumlah L1)=JUMLAH HASIL [{col}]", subs, grand)
C(core,"revenue: JUMLAH HASIL sebenar = Penyata Prestasi Hasil", rv[rv.level==0].sebenar_rm.iloc[0], ps["revenue"])

# ---------- opex maksud Nota 5(b) ----------
om=L("fact_opex_maksud.csv")
tang=om[om.maksud_code.str.startswith("T.")]; bek=om[om.maksud_code.str.startswith("B.")]
C(core,"opex: T count=14", len(tang),14); C(core,"opex: B count=36", len(bek),36); C(core,"opex: total maksud=50", len(om),50)
C(core,"opex: Jumlah Tanggungan sebenar", tang.sebenar_rm.sum(), 33040593756)
C(core,"opex: Jumlah Bekalan sebenar", bek.sebenar_rm.sum(), 152378325987)
C(core,"opex: grand sebenar (selepas pindahan)", om.sebenar_rm.sum(), 185418919743)
C(core,"opex: grand anggaran asal", om.anggaran_asal_rm.sum(), 162805323000)
C(core,"opex: grand anggaran dipinda", om.anggaran_dipinda_rm.sum(), 177979824890)

# ---------- opex detail Lampiran 1 vs Nota 5(b) ----------
od=L("fact_opex_detail.csv")
grand=od[od.row_type=="jumlah_besar"]
if len(grand): C(core,"opex_detail: grand JUMLAH sebenar = 185,418,919,743 (sen)", grand.sebenar_rm.iloc[0], 185418919742.91, tol=0.2)
# per-maksud: Lampiran-1 maksud subtotal sebenar == Nota 5(b) maksud sebenar.
# Nota 5(b) prints whole RM; Lampiran 1 sums sen -> sub-RM2 gaps are SOURCE rounding
# discrepancies (both figures verbatim-verified), reported not corrected.
mk=od[od.row_type=="jumlah_maksud"].groupby("maksud_code").sebenar_rm.sum()
nexact=0
for _,r in om.iterrows():
    code=r["maksud_code"]
    if code in mk.index:
        d=float(mk[code])-float(r["sebenar_rm"])
        if abs(d)<=0.6:
            nexact+=1
        elif abs(d)<2.0:
            core.append(("DISCREPANCY",f"Nota5b vs Lampiran1 {code} sebenar (source RM-rounding, kept)",
                         f"{float(mk[code]):.2f}",f"{float(r['sebenar_rm']):.2f}",f"{d:.2f}"))
        else:
            C(core,f"Nota5b vs Lampiran1 {code} sebenar", float(mk[code]), float(r["sebenar_rm"]))
C(core,"Nota5b vs Lampiran1 per-maksud sebenar exact matches", nexact, 49)

# ---------- devex Lampiran 2 ----------
dvp=L("fact_devex_project.csv"); proj=dvp[dvp.row_type=="project"]
badI=((proj.sebenar_langsung_rm+proj.sebenar_pinjaman_rm-proj.sebenar_jumlah_rm).abs()>0.6).sum()
C(core,"devex: per-project langsung+pinjaman=jumlah (violations)", int(badI),0)
badII=((proj.terkumpul_rmke10_rm-proj.sebenar_jumlah_rm).abs()>0.6).sum()
C(core,"devex: RMKe-10 yr1 terkumpul=sebenar_jumlah (violations)", int(badII),0)
gt=dvp[dvp.row_type=="grand_total"]
if len(gt):
    C(core,"devex: grand sebenar_jumlah = Prestasi Belanja Pembangunan", gt.sebenar_jumlah_rm.iloc[0], 46416362427, tol=0.6)
    C(core,"devex: grand sebenar_langsung (=cash Langsung)", gt.sebenar_langsung_rm.iloc[0], 44917440271, tol=0.6)
    C(core,"devex: grand sebenar_pinjaman (=cash Pinjaman)", gt.sebenar_pinjaman_rm.iloc[0], 1498922156, tol=0.6)

# ---------- trust Nota 7 ----------
ta=L("fact_trust_accounts.csv"); t=ta[ta.year==2011]
for _,r in t.iterrows():
    C(core,f"trust rollfwd {r['account_bm'][:26]}", r["baki_awal_rm"]-r["debit_rm"]+r["kredit_rm"], r["baki_akhir_rm"], tol=1.0)
gj=t[t.account_bm=="JUMLAH AKAUN AMANAH DISATUKAN"].baki_akhir_rm.iloc[0]
C(core,"trust: grand baki 31 Dis = finpos Akaun Amanah", gj, fp11["AKAUN AMANAH DISATUKAN"])

# ---------- loan account Nota 6 ----------
la=L("fact_loan_account_statement.csv"); l=la[la.year==2011]
baki=l[l.line_item_bm=="BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER"].amount_rm.iloc[0]
C(core,"loan: Baki Akaun Pinjaman Disatukan = finpos", baki, fp11["AKAUN PINJAMAN DISATUKAN"])

# ---------- debt Nota 9 ----------
db=L("fact_debt.csv"); d11=db[db.year==2011]
tot=d11[d11.item_bm=="JUMLAH HUTANG AWAM"].amount_rm.iloc[0]
mem=L("fact_memorandum.csv"); memh=mem[(mem.year==2011)&(mem.line_item_bm=="Hutang Awam")].amount_rm.iloc[0]
C(core,"debt: JUMLAH HUTANG AWAM = memorandum Hutang Awam", tot, memh)
C(core,"debt: Jumlah Pinjaman + Jumlah Bantuan LN = JUMLAH HUTANG AWAM",
  d11[d11.item_bm=="Jumlah Pinjaman"].amount_rm.iloc[0]+d11[d11.item_bm=="Jumlah Bantuan Luar Negeri"].amount_rm.iloc[0], tot)

# ---------- timeseries 2011 col ties to statements (RM juta) ----------
ts=L("fact_timeseries_2002_2011.csv"); t11=ts[ts.year==2011]
def tsv(item):
    r=t11[t11.line_item_bm==item].amount_rm_juta
    return float(r.iloc[0]) if len(r) else None
for item,exp in [("Wang Tunai",24467),("Pelaburan",22843),("Jumlah Wang Awam",47310),
                 ("Akaun Hasil Disatukan",11863),("Akaun Pinjaman Disatukan",38909),("Akaun Amanah Disatukan",-3462)]:
    v=tsv(item)
    if v is not None: C(core,f"timeseries 2011 {item} (RM juta)", v, exp)

# ================= MEMORANDA (registers L3/L4/L5 + memo assets Nota 8) =================
lr=L("fact_loans_receivable.csv"); lr11=lr[lr.year==2011]
grow=lr11[lr11.row_type=="total"]
if len(grow):
    C(memo,"L3 loans_receivable grand baki = Nota 8(a) 88,838,070,548", grow.baki_belum_selesai_rm.iloc[0], 88838070548, tol=1.0)
det=lr11[lr11.row_type=="detail"]
C(memo,"L3 sum(detail baki) = grand", det.baki_belum_selesai_rm.sum(), grow.baki_belum_selesai_rm.iloc[0] if len(grow) else 0, tol=1.0)

iv=L("fact_investments.csv"); iv11=iv[iv.year==2011]
gt=iv11[iv11.row_type=="total"]
if len(gt): C(memo,"L4 investments grand nilai_buku = Nota 8(b) 28,222,949,922", gt.nilai_buku_rm.iloc[0], 28222949922, tol=1.0)
for sec,exp in [("AGENSI ANTARABANGSA",38574229),("BADAN BERKANUN",1218852876),("SYARIKAT",26965522817)]:
    s=iv11[(iv11.section_bm==sec)&(iv11.row_type=="detail")].nilai_buku_rm.sum()
    C(memo,f"L4 {sec} sum(detail)=Nota8b", s, exp, tol=1.0)

sg=L("fact_statutory_guarantees.csv"); sg11=sg[sg.year==2011]
gt=sg11[sg11.row_type=="total"]
if len(gt): C(memo,"L5 guarantees grand jumlah = Nota 10(a) 116,757,672,552", gt.jumlah_rm.iloc[0], 116757672552, tol=1.0)
det=sg11[sg11.row_type=="detail"]
C(memo,"L5 sum(detail dalam+luar)=grand jumlah", (det.dalam_negeri_rm+det.luar_negeri_rm).sum(), gt.jumlah_rm.iloc[0] if len(gt) else 0, tol=1.0)

ma=L("fact_memo_assets_detail.csv"); ma11=ma[ma.year==2011]
pbd=ma11[(ma11.section_bm=="Pinjaman Boleh Dituntut")&(ma11.row_type=="item")].amount_rm.sum()
C(memo,"Nota8 memo assets Pinjaman Boleh Dituntut items=88,838,070,548", pbd, 88838070548)
pl=ma11[(ma11.section_bm=="Pelaburan")&(ma11.row_type=="item")].amount_rm.sum()
C(memo,"Nota8 memo assets Pelaburan items=28,222,949,922", pl, 28222949922)

def write(name,rows):
    with open(f"{WH}/{name}","w",newline="") as f:
        wtr=csv.writer(f); wtr.writerow(["status","check","extracted_value","printed_value","difference"]); wtr.writerows(rows)
    npass=sum(1 for r in rows if r[0]=="PASS")
    nfail=sum(1 for r in rows if r[0]=="FAIL")
    ndisc=sum(1 for r in rows if r[0]=="DISCREPANCY")
    print(f"{name}: {npass} PASS, {nfail} FAIL, {ndisc} DISCREPANCY (reported) / {len(rows)} total")
    for r in rows:
        if r[0] in ("FAIL","DISCREPANCY"): print(f"   {r[0]}:",r[1],"got",r[2],"want",r[3],"diff",r[4])
write("_validation_checks_2011.csv",core)
write("_validation_checks_memoranda_2011.csv",memo)
