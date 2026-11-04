#!/usr/bin/env python3
"""Full internal validation for the PKKP 2013 warehouse. Extracted line items must
reproduce THIS volume's own printed totals. Never corrects; reports PASS/FAIL.
Writes _validation_checks_2013.csv (core+detail) and
_validation_checks_memoranda_2013.csv (registers)."""
import os
import csv
from collections import defaultdict

WH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "2013")
core, memo = [], []

def chk(bucket, name, got, want, tol=0.5):
    bucket.append((("PASS" if abs(got-want) <= tol else "FAIL"), name, got, want, got-want))
def load(n):
    return list(csv.DictReader(open(f"{WH}/{n}", encoding="utf-8")))
def F(r, k):
    v = r.get(k, "")
    return float(v) if v not in ("", "None", None) else 0.0

# ---------------- 1. Financial position ----------------
fp = load("fact_financial_position.csv")
def fpv(item, yr):
    return sum(F(r,"amount_rm") for r in fp if r["line_item_bm"]==item and int(r["year"])==yr)
for yr in (2013, 2012):
    wa = fpv("WANG TUNAI",yr)+fpv("PELABURAN",yr)
    chk(core,f"FP WANG TUNAI+PELABURAN=JUMLAH WANG AWAM {yr}", wa, fpv("JUMLAH WANG AWAM",yr))
    kwd = fpv("AKAUN HASIL DISATUKAN",yr)+fpv("AKAUN PINJAMAN DISATUKAN",yr)+fpv("AKAUN AMANAH DISATUKAN",yr)
    chk(core,f"FP KWD components=JUMLAH KWD {yr}", kwd, fpv("JUMLAH KUMPULAN WANG DISATUKAN",yr))
    chk(core,f"FP WANG AWAM==KWD balance {yr}", fpv("JUMLAH WANG AWAM",yr), fpv("JUMLAH KUMPULAN WANG DISATUKAN",yr))
chk(core,"FP JUMLAH WANG AWAM 2013", fpv("JUMLAH WANG AWAM",2013), 49_083_585_341)

# ---------------- 2. Performance ----------------
pf = load("fact_financial_performance.csv")
def pfv(code, yr, basis="sebenar"):
    return sum(F(r,"amount_rm") for r in pf if r["line_code"]==code and int(r["year"])==yr and r["basis"]==basis)
for yr in (2013, 2012):
    chk(core,f"PRESTASI HASIL-opex=LEBIHAN {yr}", pfv("revenue",yr)-pfv("opex",yr), pfv("current_balance",yr))
    chk(core,f"PRESTASI LEBIHAN-devex=KURANGAN {yr}", pfv("current_balance",yr)-pfv("devex",yr), pfv("overall_deficit",yr))
    chk(core,f"PRESTASI financing=-KURANGAN {yr}", pfv("total_financing",yr), -pfv("overall_deficit",yr))
chk(core,"PRESTASI HASIL sebenar 2013", pfv("revenue",2013), 213_370_213_558)
chk(core,"PRESTASI devex sebenar 2013", pfv("devex",2013), 42_209_801_384)

# ---------------- 3. Revenue Nota 5(a) chain ----------------
rev = load("fact_revenue.csv")
for col in ("anggaran_asal_rm","anggaran_disemak_rm","sebenar_rm","sebenar_prior_rm"):
    items = defaultdict(float); subs = {}; grand = 0.0
    for r in rev:
        v = F(r,col)
        if r["level"]=="3": items[r["category_l1_bm"]] += v
        elif r["level"]=="1": subs[r["item_bm"]] = v
        elif r["level"]=="0": grand = v
    for cat,tot in subs.items():
        chk(core,f"REV {col} items->{cat}", items[cat], tot)
    chk(core,f"REV {col} L1->grand", sum(subs.values()), grand)
chk(core,"REV grand sebenar 2013", sum(F(r,'sebenar_rm') for r in rev if r['level']=='0'), 213_370_213_558)

# ---------------- 4. Cash statement chains ----------------
cs = load("fact_cash_statement.csv")
CATTOT = {"Hasil":"Jumlah Hasil","Pinjaman":"Jumlah Pinjaman","Bantuan Luar Negeri":"Jumlah Bantuan Luar Negeri",
    "Terimaan Modal":"Jumlah Terimaan Modal","Terimaan Amanah":"Jumlah Terimaan Amanah",
    "Perbelanjaan Mengurus":"Jumlah Perbelanjaan Mengurus","Perbelanjaan Pembangunan":"Jumlah Perbelanjaan Pembangunan",
    "Perbelanjaan Amanah":"Jumlah Perbelanjaan Amanah","Perbelanjaan Modal":"Jumlah Perbelanjaan Modal"}
for yr in (2013,2012):
    for cat,tl in CATTOT.items():
        items = sum(F(r,"amount_rm") for r in cs if r["category_bm"]==cat and r["item_bm"]!=tl and int(r["year"])==yr)
        tot = sum(F(r,"amount_rm") for r in cs if r["category_bm"]==cat and r["item_bm"]==tl and int(r["year"])==yr)
        chk(core,f"CASH {cat} items->{tl} {yr}", items, tot)
    jt = sum(F(r,"amount_rm") for r in cs if r["item_bm"]=="Jumlah Terimaan" and int(r["year"])==yr)
    jb = sum(F(r,"amount_rm") for r in cs if r["item_bm"]=="Jumlah Bayaran" and int(r["year"])==yr)
    tamb = sum(F(r,"amount_rm") for r in cs if "Tambahan/(Kurangan)" in r["item_bm"] and int(r["year"])==yr)
    chk(core,f"CASH Jum Terimaan-Jum Bayaran=Tambahan {yr}", jt-jb, tamb)
    awal = sum(F(r,"amount_rm") for r in cs if r["item_bm"]=="Wang Tunai Pada 1 Januari" and int(r["year"])==yr)
    akhir = sum(F(r,"amount_rm") for r in cs if r["item_bm"]=="WANG TUNAI PADA 31 DISEMBER" and int(r["year"])==yr)
    chk(core,f"CASH awal+tambahan=akhir {yr}", awal+tamb, akhir)
chk(core,"CASH Jumlah Terimaan 2013", sum(F(r,'amount_rm') for r in cs if r['item_bm']=='Jumlah Terimaan' and int(r['year'])==2013), 328_282_501_320)

# ---------------- 5. Opex maksud Nota 5(b) ----------------
om = load("fact_opex_maksud.csv")
for col,want in [("anggaran_asal_rm",201_917_000_000),("anggaran_dipinda_rm",216_647_067_943),("sebenar_rm",213_370_213_558)]:
    chk(core,f"OPEX5b grand {col}", sum(F(r,col) for r in om), want)
chk(core,"OPEX5b Tanggungan sebenar", sum(F(r,'sebenar_rm') for r in om if r['maksud_code'].startswith('T')), 38_997_954_127, tol=1)
chk(core,"OPEX5b Bekalan sebenar", sum(F(r,'sebenar_rm') for r in om if r['maksud_code'].startswith('B')), 174_372_259_431, tol=1)
chk(core,"OPEX5b n_maksud", len(om), 50)

# ---------------- 6. Opex detail Lampiran 1 ----------------
od = load("fact_opex_detail.csv")
gb = [r for r in od if r["row_type"]=="jumlah_besar"]
chk(core,"L1 grand sebenar rounds to Nota5b", round(sum(F(r,'sebenar_rm') for r in gb)), 213_370_213_558)
# jumlah_maksud sebenar sum -> grand
jm = sum(F(r,"sebenar_rm") for r in od if r["row_type"]=="jumlah_maksud")
chk(core,"L1 sum(jumlah_maksud sebenar)->grand", round(jm), 213_370_213_558)
# each Nota5b maksud ties to L1 jumlah_maksud (tol 1)
l1m = {r["maksud_code"]: F(r,"sebenar_rm") for r in od if r["row_type"]=="jumlah_maksud"}
n5m = {r["maksud_code"]: F(r,"sebenar_rm") for r in om}
fails = sum(1 for c in n5m if abs(l1m.get(c,-1)-n5m[c])>1.0)
chk(core,"L1<->Nota5b maksud sebenar (all within RM1)", 0, fails)

# ---------------- 7. Devex Lampiran 2 ----------------
dp = load("fact_devex_project.csv")
def g(r,k): return F(r,k)
idf = {"anggaran L+P=J":0,"sebenar L+P=J":0,"prior+2013=terkumpul":0}
for r in dp:
    if r["row_type"]=="grand_total": continue
    if abs(g(r,"anggaran_langsung_rm")+g(r,"anggaran_pinjaman_rm")-g(r,"anggaran_jumlah_rm"))>0.5: idf["anggaran L+P=J"]+=1
    if abs(g(r,"sebenar_langsung_rm")+g(r,"sebenar_pinjaman_rm")-g(r,"sebenar_jumlah_rm"))>0.5: idf["sebenar L+P=J"]+=1
    if abs(g(r,"terkumpul_rmke10_prior_rm")+g(r,"sebenar_jumlah_rm")-g(r,"terkumpul_rmke10_rm"))>0.5: idf["prior+2013=terkumpul"]+=1
for k,v in idf.items(): chk(core,f"DEVEX per-row identity {k} (fails)", 0, v)
grand = [r for r in dp if r["row_type"]=="grand_total"]
chk(core,"DEVEX grand sebenar_jumlah->42.2bn", round(sum(g(r,"sebenar_jumlah_rm") for r in grand)), 42_209_801_384)
# project rows sum to ministry_total per maksud
proj = defaultdict(float); mtot = {}
for r in dp:
    if r["row_type"]=="project": proj[r["maksud_code"]] += g(r,"sebenar_jumlah_rm")
    elif r["row_type"]=="ministry_total": mtot[r["maksud_code"]] = g(r,"sebenar_jumlah_rm")
mfail = sum(1 for c in mtot if abs(proj[c]-mtot[c])>0.5)
chk(core,"DEVEX project->ministry_total sebenar (fails)", 0, mfail)
chk(core,"DEVEX sum(ministry_total)->grand", round(sum(mtot.values())), 42_209_801_384)

# ---------------- 8. Debt Nota 9 ----------------
db = load("fact_debt.csv")
def dv(item, yr): return sum(F(r,"amount_rm") for r in db if r["item_bm"]==item and int(r["year"])==yr)
for yr in (2013,2012):
    dn = sum(F(r,"amount_rm") for r in db if r["group_bm"]=="Pinjaman Dalam Negeri" and r["kind"]=="instrument" and int(r["year"])==yr)
    chk(core,f"DEBT DN instruments->subtotal {yr}", dn, dv("Dalam Negeri",yr))
    jp = dv("Dalam Negeri",yr)+dv("Pembiayaan Kumpulan Wang Pinjaman Perumahan",yr)+dv("Pinjaman Pasaran",yr)
    chk(core,f"DEBT Jumlah Pinjaman {yr}", jp, dv("PINJAMAN",yr))
    ha = dv("PINJAMAN",yr)+dv("BANTUAN LUAR NEGERI",yr)
    chk(core,f"DEBT Hutang Awam {yr}", ha, dv("HUTANG AWAM",yr))
chk(core,"DEBT Hutang Awam 2013", dv("HUTANG AWAM",2013), 539_857_759_215)

# ---------------- 9. Trust Nota 7 ----------------
tr = load("fact_trust_accounts.csv")
for r in tr:
    ba,dr,cr,bk = F(r,"baki_awal_rm"),F(r,"debit_rm"),F(r,"kredit_rm"),F(r,"baki_akhir_rm")
    chk(core,f"TRUST roll baki_awal+kredit-debit=akhir [{r['account_bm'][:25]}]", ba+cr-dr, bk)
gk = [r for r in tr if r["account_bm"]=="AKAUN AMANAH DISATUKAN"][0]
chk(core,"TRUST grand baki_akhir->position 2013", F(gk,"baki_akhir_rm"), 10_840_100_391)

# ---------------- 10. Nota 5 statement roll-forward ----------------
r5 = load("fact_revenue_account_statement.csv")
jh = [r for r in r5 if int(r["year"])==2013 and "Jumlah Hasil" in r["line_item_bm"]]
if jh: chk(core,"NOTA5 stmt Jumlah Hasil sebenar 2013", F(jh[0],"sebenar_rm"), 213_370_213_558)
op = [r for r in r5 if r["row_type"]=="opening" and int(r["year"])==2013]
clo = [r for r in r5 if r["row_type"]=="closing" and int(r["year"])==2013]
if op and clo: chk(core,"NOTA5 stmt opening==closing 2013", F(op[0],"sebenar_rm") or F(op[0],"anggaran_disemak_rm"), F(clo[0],"sebenar_rm") or F(clo[0],"anggaran_disemak_rm"))

# ---------------- 11. Nota 6 loan statement closing ----------------
r6 = load("fact_loan_account_statement.csv")
c6 = [r for r in r6 if r["row_type"]=="closing" and int(r["year"])==2013]
if c6: chk(core,"NOTA6 loan stmt closing 2013->position", F(c6[0],"amount_rm"), 26_380_357_864)

# ---------------- 12. Cash components / investment summary ----------------
cc = load("fact_cash_components.csv")
chk(core,"CASHCOMP items->JUMLAH 2013", sum(F(r,"amount_rm") for r in cc if r["row_type"]=="detail" and int(r["year"])==2013),
    sum(F(r,"amount_rm") for r in cc if r["row_type"]=="total" and int(r["year"])==2013))
isu = load("fact_investment_summary.csv")
chk(core,"INVSUM JUMLAH PELABURAN 2013", sum(F(r,"amount_rm") for r in isu if r["row_type"]=="total" and int(r["year"])==2013), 24_032_546_356)

# ---------------- 13. Timeseries headline (2013 juta) ----------------
ts = load("fact_timeseries_2004_2013.csv")
ts13 = [r for r in ts if int(r["year"])==2013]
def tsfind(sub):
    m=[r for r in ts13 if sub.lower() in r["line_item_bm"].lower()]
    return F(m[0],"amount_rm_juta") if m else None
chk(core,"TS rows", len(ts), 1360)

# ================= MEMORANDA registers =================
lr = load("fact_loans_receivable.csv")
lr_tot = sum(F(r,"baki_belum_selesai_rm") for r in lr if r["row_type"]=="total" and int(r["year"])==2013)
chk(memo,"L3 Pinjaman Boleh Dituntut total 2013 (as printed)", lr_tot, 92_547_188_214, tol=1)
lr_det = sum(F(r,"baki_belum_selesai_rm") for r in lr if r["row_type"]=="detail" and int(r["year"])==2013)
lr_sub = sum(F(r,"baki_belum_selesai_rm") for r in lr if r["row_type"]=="subtotal" and int(r["year"])==2013)
chk(memo,"L3 detail sum==subtotal sum 2013", lr_det, lr_sub, tol=1)
chk(memo,"L3 detail sum->total 2013 (0.04 sen print rounding)", lr_det, lr_tot, tol=1)
# per-column 2013 fund reconciliation (detail->total)
for col in ("pembangunan_rm","hasil_disatukan_rm","amanah_lain_rm"):
    d=sum(F(r,col) for r in lr if r["row_type"]=="detail" and int(r["year"])==2013)
    t=sum(F(r,col) for r in lr if r["row_type"]=="total" and int(r["year"])==2013)
    chk(memo,f"L3 {col} detail->total 2013", d, t, tol=1)

di = load("fact_debt_issues.csv")
di_tot = sum(F(r,"amaun_belum_selesai_rm") for r in di if r["row_type"]=="total")
chk(memo,"L5 Hutang Awam register total", di_tot, 539_857_759_215, tol=1)
di_det = sum(F(r,"amaun_belum_selesai_rm") for r in di if r["row_type"]=="detail")
chk(memo,"L5 detail sum->total", di_det, di_tot, tol=2)

sg = load("fact_statutory_guarantees.csv")
sg_fail = sum(1 for r in sg if r["row_type"]=="detail" and int(r["year"])==2013
              and abs(F(r,"dalam_negeri_rm")+F(r,"luar_negeri_rm")-F(r,"jumlah_rm"))>0.5)
chk(memo,"L6 dalam+luar=jumlah all 2013 detail (fails)", 0, sg_fail)
def sgsub(jenis, kat):
    return sum(F(r,"jumlah_rm") for r in sg if r["row_type"]=="subtotal" and int(r["year"])==2013
               and jenis in r["jenis_jaminan_bm"] and r.get("kategori_bm","")==kat)
loan_sub = sgsub("JAMINAN PINJAMAN","")
chk(memo,"L6 Jaminan Pinjaman subtotal ties Nota10(a)", loan_sub, 157_499_913_232, tol=1)
chk(memo,"L6 loan Badan Berkanun+Syarikat->subtotal",
    sgsub("JAMINAN PINJAMAN","Badan Berkanun")+sgsub("JAMINAN PINJAMAN","Syarikat"), loan_sub, tol=1)
dep_sub = sgsub("JAMINAN PENCARUM","")
chk(memo,"L6 Jaminan Pencarum/Pendeposit ties Nota10(b)", dep_sub, 610_908_127_026, tol=1)
sg_tot = sum(F(r,"jumlah_rm") for r in sg if r["row_type"]=="total" and int(r["year"])==2013)
chk(memo,"L6 grand total = loan_sub + deposit_sub", sg_tot, loan_sub+dep_sub, tol=1)

inv = load("fact_investments.csv")
inv_tot = sum(F(r,"nilai_buku_rm") for r in inv if r["row_type"]=="total" and int(r["year"])==2013)
chk(memo,"L4 Pelaburan register total 2013", inv_tot, 29_679_137_799, tol=1)
inv_det = sum(F(r,"nilai_buku_rm") for r in inv if r["row_type"]=="detail" and int(r["year"])==2013)
chk(memo,"L4 detail sum->total 2013", inv_det, inv_tot, tol=1)
inv_tot12 = sum(F(r,"nilai_buku_rm") for r in inv if r["row_type"]=="total" and int(r["year"])==2012)
chk(memo,"L4 Pelaburan register total 2012", inv_tot12, 28_110_412_577, tol=1)

ma = load("fact_memo_assets_detail.csv")
chk(memo,"Nota8b Pelaburan foots 2013", sum(F(r,"amount_rm") for r in ma if r["row_type"]=="total" and int(r["year"])==2013 and "PELABURAN" in r["line_item_bm"].upper()), 29_679_137_799, tol=1)

# ---------------- write ----------------
def write(path, rows):
    with open(path,"w",newline="",encoding="utf-8") as f:
        cw=csv.writer(f); cw.writerow(["status","check","extracted_value","printed_value","difference"])
        for st,nm,got,want,dif in rows: cw.writerow([st,nm,f"{got:.2f}",f"{want:.2f}",f"{dif:.2f}"])
write(f"{WH}/_validation_checks_2013.csv", core)
write(f"{WH}/_validation_checks_memoranda_2013.csv", memo)
cp=sum(1 for r in core if r[0]=="PASS"); mp=sum(1 for r in memo if r[0]=="PASS")
print(f"core: {cp}/{len(core)} PASS")
print(f"memoranda: {mp}/{len(memo)} PASS")
for r in core+memo:
    if r[0]=="FAIL": print("  FAIL:", r[1], "got",f"{r[2]:.2f}","want",f"{r[3]:.2f}","diff",f"{r[4]:.2f}")
