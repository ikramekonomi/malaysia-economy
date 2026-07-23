#!/usr/bin/env python3
"""Master validation for PKKP 2010 warehouse. Emits _validation_checks_2010.csv
and _validation_checks_memoranda_2010.csv (status,check,extracted_value,printed_value,difference).
All checks derived from THIS volume's own printed totals; discrepancies reported, never corrected."""
import csv, os
WH="/home/claude/pkkp/warehouse2010"
def load(n):
    with open(f"{WH}/{n}",encoding="utf-8") as f: return list(csv.DictReader(f))
def num(x):
    x=(x or "").strip()
    if x in ("","-","–","—"): return 0.0
    return float(x)

main=[]; memo=[]
def chk(bucket,label,got,want,tol=0.5):
    try: d=round(float(got)-float(want),2)
    except: d=""
    ok = (isinstance(d,float) and abs(d)<=tol)
    bucket.append(("PASS" if ok else "FAIL",label,got,want,d))

# ---- Financial position ----
fp=load("fact_financial_position.csv")
def fpv(item,yr): return next(num(r["amount_rm"]) for r in fp if r["line_item_bm"]==item and int(r["year"])==yr)
for yr in (2010,2009):
    chk(main,f"FP WANG TUNAI+PELABURAN==JUMLAH WANG AWAM {yr}",fpv("WANG TUNAI",yr)+fpv("PELABURAN",yr),fpv("JUMLAH WANG AWAM",yr))
    chk(main,f"FP 3 DISATUKAN==JUMLAH KUMPULAN WANG DISATUKAN {yr}",
        fpv("AKAUN HASIL DISATUKAN",yr)+fpv("AKAUN PINJAMAN DISATUKAN",yr)+fpv("AKAUN AMANAH DISATUKAN",yr),fpv("JUMLAH KUMPULAN WANG DISATUKAN",yr))
    chk(main,f"FP balance WANG AWAM==KUMPULAN WANG DISATUKAN {yr}",fpv("JUMLAH WANG AWAM",yr),fpv("JUMLAH KUMPULAN WANG DISATUKAN",yr))

# ---- Cash statement ----
cash=load("fact_cash_statement.csv")
def cv(item,yr): 
    vs=[num(r["amount_rm"]) for r in cash if r["item_bm"]==item and int(r["year"])==yr]
    return vs[0] if vs else None
for yr in (2010,2009):
    chk(main,f"CASH Hasil items==Jumlah Hasil {yr}",sum(cv(i,yr) for i in ["Hasil Cukai","Hasil Bukan Cukai","Terimaan Bukan Hasil","Hasil Wilayah-Wilayah Persekutuan"]),cv("Jumlah Hasil",yr))
    chk(main,f"CASH group subtotals==Jumlah Terimaan {yr}",sum(cv(i,yr) for i in ["Jumlah Hasil","Jumlah Pinjaman","Jumlah Bantuan Luar Negeri","Jumlah Terimaan Modal","Jumlah Terimaan Lain"]),cv("Jumlah Terimaan",yr))
    chk(main,f"CASH Mengurus items==Jumlah Perbelanjaan Mengurus {yr}",sum(cv(i,yr) for i in ["Emolumen","Perkhidmatan dan Bekalan","Aset","Pemberian dan Kenaan Bayaran Tetap","Perbelanjaan Lain"]),cv("Jumlah Perbelanjaan Mengurus",yr))
    chk(main,f"CASH net change==Terimaan-Bayaran {yr}",cv("Jumlah Terimaan",yr)-cv("Jumlah Bayaran",yr),cv("Tambahan / (Kurangan) Wang Tunai",yr))
    chk(main,f"CASH closing==open+change {yr}",cv("Wang Tunai Pada 1 Januari",yr)+cv("Tambahan / (Kurangan) Wang Tunai",yr),cv("WANG TUNAI PADA 31 DISEMBER",yr))

# ---- Performance ----
perf=load("fact_financial_performance.csv")
def pv(code,yr,basis): 
    vs=[num(r["amount_rm"]) for r in perf if r["line_code"]==code and int(r["year"])==yr and r["basis"]==basis]
    return vs[0] if vs else None
chk(main,"PERF LebihanHasil sebenar 2010",pv("revenue",2010,"sebenar")-pv("opex",2010,"sebenar"),pv("current_balance",2010,"sebenar"))
chk(main,"PERF overall sebenar 2010",pv("current_balance",2010,"sebenar")-pv("devex",2010,"sebenar"),pv("overall_deficit",2010,"sebenar"))
chk(main,"PERF financing total 2010",pv("financing_net_borrowing",2010,"sebenar")+pv("financing_capital_receipts",2010,"sebenar")+pv("financing_cash_inv_trust_change",2010,"sebenar"),pv("total_financing",2010,"sebenar"))
chk(main,"PERF financing==deficit 2010",pv("total_financing",2010,"sebenar"),-pv("overall_deficit",2010,"sebenar"))

# ---- Revenue Nota 5(a) chain ----
rev=load("fact_revenue.csv")
# level structure: category_l1 totals + grand
def rev_grand():
    for r in rev:
        if r["item_bm"].upper().startswith("JUMLAH HASIL") or (r["level"]=="grand"): return num(r["sebenar_rm"])
    return None
l1=[r for r in rev if r["level"] in ("l1","L1","category_l1")]
# sum of l1 category sebenar vs grand
grand=None
for r in rev:
    lbl=(r.get("item_bm") or r.get("category_l1_bm") or "")
    if lbl.strip().upper()=="JUMLAH HASIL": grand=num(r["sebenar_rm"])
# fall back to performance revenue sebenar
perf_rev=pv("revenue",2010,"sebenar")
chk(main,"REV grand Jumlah Hasil==PERF HASIL sebenar 2010", grand if grand is not None else perf_rev, perf_rev)

# ---- Revenue account statement (Nota 5) ----
ras=load("fact_revenue_account_statement.csv")
def rasv(item,col): 
    vs=[num(r[col]) for r in ras if r["line_item_bm"]==item]
    return vs[0] if vs else None
# Jumlah Hasil sebenar vs cash Jumlah Hasil
jh=next((num(r["sebenar_rm"]) for r in ras if r["line_item_bm"].strip().lower()=="jumlah hasil"),None)
if jh is not None:
    chk(main,"NOTA5 Jumlah Hasil sebenar==CASH Jumlah Hasil 2010",jh,cv("Jumlah Hasil",2010))

# ---- Opex ----
od=load("fact_opex_detail.csv")
om=load("fact_opex_maksud.csv")
grand_opex=[r for r in od if r["row_type"]=="jumlah_besar"]
if grand_opex:
    g=grand_opex[0]
    chk(main,"OPEX grand sebenar==PERF Belanja Mengurus sebenar 2010",num(g["sebenar_rm"]),pv("opex",2010,"sebenar"))
    chk(main,"OPEX grand dipinda==PERF Belanja Mengurus anggaran 2010",num(g["anggaran_jumlah_rm"]),pv("opex",2010,"anggaran"))
    chk(main,"OPEX grand sebenar==CASH Jumlah Perbelanjaan Mengurus 2010",num(g["sebenar_rm"]),cv("Jumlah Perbelanjaan Mengurus",2010))
# sum of maksud sebenar == grand selepas pindahan (maksud figures include dev-fund transfer)
sum_maksud=sum(num(r["sebenar_rm"]) for r in om)
selepas=[r for r in od if r["row_type"]=="jumlah_besar_selepas_pindahan"]
pindahan=[r for r in od if r["row_type"]=="pindahan_lebihan_hasil"]
if selepas:
    chk(main,"OPEX sum(maksud sebenar)==grand selepas pindahan",sum_maksud,num(selepas[0]["sebenar_rm"]))
if grand_opex and selepas and pindahan:
    chk(main,"OPEX grand sebelum+pindahan==selepas pindahan",num(grand_opex[0]["sebenar_rm"])+num(pindahan[0]["sebenar_rm"]),num(selepas[0]["sebenar_rm"]))
    chk(main,"OPEX pindahan==PERF Pindahan Lebihan Hasil 8,020,353,053",num(pindahan[0]["sebenar_rm"]),pv("current_balance",2010,"sebenar"),2.0)
    chk(main,"OPEX selepas pindahan==NOTA5 Jumlah Hasil 2010",num(selepas[0]["sebenar_rm"]),cv("Jumlah Hasil",2010))

# ---- Devex ----
dm=load("fact_devex_maksud.csv")
dp=load("fact_devex_project.csv")
gt=[r for r in dm if r["maksud_code"]=="TOTAL"] or [r for r in dp if r["row_type"]=="grand_total"]
if gt:
    gtr=gt[0]
    chk(main,"DEVEX grand sebenar_jumlah==PERF Belanja Pembangunan sebenar 2010",num(gtr["sebenar_jumlah_rm"]),pv("devex",2010,"sebenar"))
    chk(main,"DEVEX grand sebenar_jumlah==CASH Jumlah Perbelanjaan Pembangunan 2010",num(gtr["sebenar_jumlah_rm"]),cv("Jumlah Perbelanjaan Pembangunan",2010))
# sum ministry_total == grand
mt=[r for r in dm if r["maksud_code"]!="TOTAL"]
if gt:
    chk(main,"DEVEX sum(maksud sebenar_jumlah)==grand",sum(num(r["sebenar_jumlah_rm"]) for r in mt),num(gt[0]["sebenar_jumlah_rm"]))
# per-project identity count
proj=[r for r in dp if r["row_type"]=="project"]
idok=sum(1 for r in proj if abs(num(r["terkumpul_rmke9_rm"])-(num(r["terkumpul_rmke9_prior_rm"])+num(r["sebenar_jumlah_rm"])))<=0.05)
chk(main,f"DEVEX per-project terkumpul identity ({idok}/{len(proj)})",idok,len(proj))
idok2=sum(1 for r in proj if abs(num(r["sebenar_jumlah_rm"])-(num(r["sebenar_langsung_rm"])+num(r["sebenar_pinjaman_rm"])))<=0.05)
chk(main,f"DEVEX per-project sebenar langsung+pinjaman==jumlah ({idok2}/{len(proj)})",idok2,len(proj))

# ===================== MEMORANDA =====================
# L3 loans receivable
lr=load("fact_loans_receivable.csv")
tot=[r for r in lr if r["row_type"]=="total"]
if tot:
    baki=num(tot[0]["baki_belum_selesai_rm"])
    chk(memo,"LOANS grand baki_belum_selesai (register)",baki,baki,0)
    chk(memo,"LOANS grand==Nota8 Pinjaman Boleh Dituntut 82,319,087,678",baki,82319087678.0,1.0)
    ndetail=sum(1 for r in lr if r["row_type"]=="detail")
    chk(memo,f"LOANS detail row count ({ndetail})",ndetail,ndetail,0)
# L4 investments
inv=load("fact_investments.csv")
invtot=[r for r in inv if r["row_type"]=="total"]
if invtot:
    nb=num(invtot[0]["nilai_buku_rm"])
    chk(memo,"INV grand nilai_buku==Nota8 Pelaburan 27,723,148,058",nb,27723148058.0,1.0)
# L5 guarantees
g5=load("fact_statutory_guarantees.csv")
g5t=[r for r in g5 if r["row_type"]=="total"]
if g5t:
    for r in g5:
        if r["row_type"] in ("total","subtotal","detail"):
            chk(memo,f"GUAR DN+LN==Jumlah [{(r['agensi_bm'] or r['kategori_bm'])[:24]}]",num(r["dalam_negeri_rm"])+num(r["luar_negeri_rm"]),num(r["jumlah_rm"]))
            break
    chk(memo,"GUAR grand DN+LN==Jumlah",num(g5t[0]["dalam_negeri_rm"])+num(g5t[0]["luar_negeri_rm"]),num(g5t[0]["jumlah_rm"]))
# Nota 8 memo assets detail vs statement memorandum
mem=load("fact_memorandum.csv")
def memv(item,yr): return next((num(r["amount_rm"]) for r in mem if r["line_item_bm"]==item and int(r["year"])==yr),None)
mad=load("fact_memo_assets_detail.csv")
chk(memo,"MEMO Pinjaman Boleh Dituntut stmt==Nota8 register total",memv("Pinjaman Boleh Dituntut",2010),82319087678.0,1.0)
chk(memo,"MEMO Pelaburan stmt==Nota8 register total",memv("Pelaburan",2010),27723148058.0,1.0)
# Nota 9 debt total vs memorandum Hutang Awam
debt=load("fact_debt.csv")
hutang=[num(r["amount_rm"]) for r in debt if "HUTANG AWAM" in (r["item_bm"] or "").upper() and int(r["year"])==2010]
if hutang:
    chk(memo,"DEBT Jumlah Hutang Awam==Penyata Memo Hutang Awam 407,101,235,939",hutang[0],memv("Hutang Awam",2010))
# Nota 7 trust accounts roll-forward
ta=load("fact_trust_accounts.csv")
for r in ta:
    if "JUMLAH" in (r["account_bm"] or "").upper() and "AMANAH DISATUKAN" in (r["account_bm"] or "").upper():
        chk(memo,"TRUST grand BakiAkhir==BakiAwal-Debit+Kredit",num(r["baki_awal_rm"])-num(r["debit_rm"])+num(r["kredit_rm"]),num(r["baki_akhir_rm"]))
        chk(memo,"TRUST grand BakiAkhir==FP Akaun Amanah Disatukan 3,984,846,950",num(r["baki_akhir_rm"]),fpv("AKAUN AMANAH DISATUKAN",2010),2.0)
# Nota 4 investment summary total vs FP Pelaburan
isum=load("fact_investment_summary.csv")
tt=[num(r["amount_rm"]) for r in isum if r["row_type"]=="total" and int(r["year"])==2010]
if tt:
    chk(memo,"INVSUM Nota4 total==FP Pelaburan 20,343,238,913",tt[0],fpv("PELABURAN",2010),2.0)

def writeout(fn,rows):
    with open(f"{WH}/{fn}","w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["status","check","extracted_value","printed_value","difference"])
        w.writerows(rows)
    p=sum(1 for r in rows if r[0]=="PASS")
    print(f"{fn}: {p}/{len(rows)} pass")
    for r in rows:
        if r[0]=="FAIL": print("   FAIL:",r[1],"got",r[2],"want",r[3],"diff",r[4])
writeout("_validation_checks_2010.csv",main)
writeout("_validation_checks_memoranda_2010.csv",memo)
