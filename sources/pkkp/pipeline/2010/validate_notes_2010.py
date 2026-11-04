#!/usr/bin/env python3
import csv, os
W2010 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "2010")
W2012 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "2012")

FILES = ["fact_cash_components", "fact_investment_summary", "fact_revenue",
         "fact_revenue_account_statement", "fact_loan_account_statement",
         "fact_trust_accounts", "fact_trust_fund_detail", "fact_memo_assets_detail",
         "fact_debt", "fact_commitment_detail", "fact_other_notes"]

def load(w, name):
    with open(os.path.join(w, name + ".csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f)), open(os.path.join(w, name + ".csv"), encoding="utf-8").readline().strip()

def num(s):
    if s is None or s == "":
        return 0.0
    return float(s)

print("=" * 60)
print("HEADER CHECK vs 2012")
print("=" * 60)
for name in FILES:
    r10, h10 = load(W2010, name)
    _, h12 = load(W2012, name)
    ok = h10 == h12
    print(f"{'OK ' if ok else 'FAIL'} {name}: {'headers match' if ok else 'MISMATCH'}")
    if not ok:
        print("   2012:", h12)
        print("   2010:", h10)

PASS = 0; FAIL = 0; fails = []
def check(label, a, b, tol=0.5):
    global PASS, FAIL
    if abs(a - b) <= tol:
        PASS += 1
    else:
        FAIL += 1
        fails.append(f"{label}: got {a:,.2f} expected {b:,.2f} (diff {a-b:,.2f})")

print("\n" + "=" * 60); print("RECONCILIATIONS"); print("=" * 60)

# --- Nota 3 cash ---
r, _ = load(W2010, "fact_cash_components")
for yr in (2010, 2009):
    comp = sum(num(x["amount_rm"]) for x in r if x["year"] == str(yr) and x["row_type"] == "detail")
    tot = [num(x["amount_rm"]) for x in r if x["year"] == str(yr) and x["row_type"] == "total"][0]
    check(f"N3 cash {yr}", comp, tot)

# --- Nota 4 investment: category subtotals + grand ---
r, _ = load(W2010, "fact_investment_summary")
for yr in (2010, 2009):
    for cat in ("Pelaburan Kumpulan Wang Amanah", "Pelaburan Am"):
        comp = sum(num(x["amount_rm"]) for x in r if x["year"] == str(yr) and x["category_bm"] == cat and x["row_type"] == "detail")
        sub = [num(x["amount_rm"]) for x in r if x["year"] == str(yr) and x["category_bm"] == cat and x["row_type"] == "subtotal"][0]
        check(f"N4 {cat} {yr}", comp, sub)
    subs = sum(num(x["amount_rm"]) for x in r if x["year"] == str(yr) and x["row_type"] == "subtotal")
    tot = [num(x["amount_rm"]) for x in r if x["year"] == str(yr) and x["row_type"] == "total"][0]
    check(f"N4 JUMLAH PELABURAN {yr}", subs, tot)

# --- Nota 5(a) revenue chain ---
r, _ = load(W2010, "fact_revenue")
def get(item, col):
    return num([x[col] for x in r if x["item_bm"] == item][0])
# category chain: sum of level-1 subtotals = JUMLAH HASIL
for col in ("sebenar_rm", "anggaran_disemak_rm", "anggaran_asal_rm", "sebenar_prior_rm"):
    l1 = sum(num(x[col]) for x in r if x["level"] == "1")
    grand = num([x[col] for x in r if x["level"] == "0"][0])
    check(f"N5a chain {col}", l1, grand)
# each level-1 subtotal = sum of its level-3 details
for cat in ("HASIL CUKAI", "HASIL BUKAN CUKAI", "TERIMAAN BUKAN HASIL", "HASIL WILAYAH-WILAYAH PERSEKUTUAN"):
    for col in ("sebenar_rm", "anggaran_asal_rm", "anggaran_disemak_rm", "sebenar_prior_rm"):
        det = sum(num(x[col]) for x in r if x["category_l1_bm"] == cat and x["level"] == "3")
        sub = num([x[col] for x in r if x["category_l1_bm"] == cat and x["level"] == "1"][0])
        check(f"N5a {cat} {col}", det, sub)

# --- Nota 5 lead table ---
r, _ = load(W2010, "fact_revenue_account_statement")
for yr in (2010, 2009):
    hasil = sum(num(x["sebenar_rm"]) for x in r if x["section_bm"] == "HASIL" and x["row_type"] == "detail" and x["year"] == str(yr))
    jh = num([x["sebenar_rm"] for x in r if x["line_item_bm"] == "Jumlah Hasil" and x["year"] == str(yr)][0])
    check(f"N5 lead Jumlah Hasil {yr}", hasil, jh)
    pm = sum(num(x["sebenar_rm"]) for x in r if x["section_bm"] == "PERBELANJAAN MENGURUS" and x["row_type"] == "detail" and x["year"] == str(yr))
    pmsub = num([x["sebenar_rm"] for x in r if x["line_item_bm"].startswith("Perbelanjaan Mengurus (sebelum") and x["year"] == str(yr)][0])
    check(f"N5 lead PM sebelum {yr}", pm, pmsub)
    # selepas = sebelum + pindahan
    pind = num([x["sebenar_rm"] for x in r if x["row_type"] == "transfer" and x["year"] == str(yr)][0])
    selepas = num([x["sebenar_rm"] for x in r if "selepas pindahan" in x["line_item_bm"] and x["year"] == str(yr)][0])
    check(f"N5 lead selepas=sebelum+pindahan {yr}", pmsub + pind, selepas)

# --- Nota 6 loan ---
r, _ = load(W2010, "fact_loan_account_statement")
def loan(item, sub, yr):
    return num([x["amount_rm"] for x in r if x["line_item_bm"] == item and x["sub_bm"] == sub and x["year"] == str(yr)][0])
for yr in (2010, 2009):
    # Jumlah Pinjaman = sum of the three "Baki pada 31 Disember" under PINJAMAN
    baki_sum = sum(num(x["amount_rm"]) for x in r if x["group_bm"] == "PINJAMAN" and x["line_item_bm"] == "Baki pada 31 Disember" and x["year"] == str(yr))
    jp = num([x["amount_rm"] for x in r if x["line_item_bm"] == "Jumlah Pinjaman pada 31 Disember" and x["year"] == str(yr)][0])
    check(f"N6 Jumlah Pinjaman {yr}", baki_sum, jp)
    bln = sum(num(x["amount_rm"]) for x in r if x["group_bm"] == "BANTUAN LUAR NEGERI" and x["line_item_bm"] == "Baki pada 31 Disember" and x["year"] == str(yr))
    jbln = num([x["amount_rm"] for x in r if x["line_item_bm"] == "Jumlah Bantuan Luar Negeri pada 31 Disember" and x["year"] == str(yr)][0])
    check(f"N6 Jumlah Bantuan LN {yr}", bln, jbln)
    grand = num([x["amount_rm"] for x in r if x["group_bm"] == "JUMLAH" and x["year"] == str(yr)][0])
    check(f"N6 JUMLAH P+BLN {yr}", jp + jbln, grand)
    # BAKI = grand + transfers
    trans = sum(num(x["amount_rm"]) for x in r if x["group_bm"] == "PINDAHAN KE" and x["year"] == str(yr))
    baki = num([x["amount_rm"] for x in r if x["group_bm"] == "BAKI" and x["year"] == str(yr)][0])
    check(f"N6 BAKI=grand+pindahan {yr}", grand + trans, baki)

# --- Nota 7 trust accounts roll-forward: baki_akhir = baki_awal - debit + kredit ---
r, _ = load(W2010, "fact_trust_accounts")
for x in r:
    ba, dr, kr, bk = num(x["baki_awal_rm"]), num(x["debit_rm"]), num(x["kredit_rm"]), num(x["baki_akhir_rm"])
    check(f"N7 rollfwd {x['account_bm'][:25]}", ba - dr + kr, bk)
# subtotals = sum of member accounts
for grp, sub_acc in (("KUMPULAN WANG AMANAH KERAJAAN", "KUMPULAN WANG AMANAH KERAJAAN"),
                     ("KUMPULAN WANG AMANAH AWAM", "KUMPULAN WANG AMANAH AWAM"),
                     ("AKAUN DEPOSIT", "AKAUN DEPOSIT")):
    for col in ("baki_awal_rm", "debit_rm", "kredit_rm", "baki_akhir_rm"):
        det = sum(num(x[col]) for x in r if x["parent_group_bm"] == grp)
        sub = num([x[col] for x in r if x["parent_group_bm"] == "" and x["account_bm"] == sub_acc][0])
        check(f"N7 subtotal {grp[:15]} {col}", det, sub)
# grand total = sum of the 3 subtotals
for col in ("baki_awal_rm", "debit_rm", "kredit_rm", "baki_akhir_rm"):
    subs = sum(num(x[col]) for x in r if x["parent_group_bm"] == "")
    grand = num([x[col] for x in r if x["parent_group_bm"] == "JUMLAH"][0])
    check(f"N7 grand {col}", subs, grand)

# --- Nota 7 fund detail: subtotals within Pelbagai KWAK, Awam, Deposit; roll-forwards ---
r, _ = load(W2010, "fact_trust_fund_detail")
# KW Pembangunan roll-forward per year
for yr in (2010, 2009):
    def fd(sec, item):
        m = [x["amount_rm"] for x in r if x["fund_bm"] == "Kumpulan Wang Pembangunan" and x["section_bm"] == sec and x["line_item_bm"] == item and x["year"] == str(yr)]
        return num(m[0]) if m else None
    op = num([x["amount_rm"] for x in r if x["fund_bm"] == "Kumpulan Wang Pembangunan" and x["row_type"] == "opening" and x["year"] == str(yr)][0])
    jt = num([x["amount_rm"] for x in r if x["fund_bm"] == "Kumpulan Wang Pembangunan" and x["line_item_bm"] == "Jumlah Terimaan" and x["year"] == str(yr)][0])
    jb = num([x["amount_rm"] for x in r if x["fund_bm"] == "Kumpulan Wang Pembangunan" and x["line_item_bm"] == "Jumlah Bayaran" and x["year"] == str(yr)][0])
    cl = num([x["amount_rm"] for x in r if x["fund_bm"] == "Kumpulan Wang Pembangunan" and x["row_type"] == "closing" and x["year"] == str(yr)][0])
    check(f"N7d KWPembangunan rollfwd {yr}", op + jt + jb, cl)
    # terimaan detail sum
    td = sum(num(x["amount_rm"]) for x in r if x["fund_bm"] == "Kumpulan Wang Pembangunan" and x["section_bm"].startswith("TERIMAAN") and x["row_type"] == "detail" and x["year"] == str(yr))
    check(f"N7d KWPemb Jumlah Terimaan {yr}", td, jt)
# KW Pinjaman Perumahan roll-forward
for yr in (2010, 2009):
    op = num([x["amount_rm"] for x in r if x["fund_bm"] == "Kumpulan Wang Pinjaman Perumahan" and x["row_type"] == "opening" and x["year"] == str(yr)][0])
    jt = num([x["amount_rm"] for x in r if x["fund_bm"] == "Kumpulan Wang Pinjaman Perumahan" and x["line_item_bm"] == "Jumlah Terimaan" and x["year"] == str(yr)][0])
    jb = num([x["amount_rm"] for x in r if x["fund_bm"] == "Kumpulan Wang Pinjaman Perumahan" and x["line_item_bm"] == "Jumlah Bayaran" and x["year"] == str(yr)][0])
    tr = sum(num(x["amount_rm"]) for x in r if x["fund_bm"] == "Kumpulan Wang Pinjaman Perumahan" and x["row_type"] == "transfer" and x["year"] == str(yr))
    cl = num([x["amount_rm"] for x in r if x["fund_bm"] == "Kumpulan Wang Pinjaman Perumahan" and x["row_type"] == "closing" and x["year"] == str(yr)][0])
    check(f"N7d KWPinjPerumahan rollfwd {yr}", op + jt + jb + tr, cl)
# Pelbagai KWAK subtotals & grand
for yr in (2010, 2009):
    for sec in ("AKAUN PENYELESAIAN", "AKAUN PERNIAGAAN", "AKAUN PINJAMAN", "KUMPULAN WANG LUAR JANGKA", "PELBAGAI KUMPULAN WANG"):
        det = sum(num(x["amount_rm"]) for x in r if x["fund_bm"] == "Pelbagai Kumpulan Wang Amanah Kerajaan" and x["section_bm"] == sec and x["row_type"] == "detail" and x["year"] == str(yr))
        sub = num([x["amount_rm"] for x in r if x["fund_bm"] == "Pelbagai Kumpulan Wang Amanah Kerajaan" and x["section_bm"] == sec and x["row_type"] == "subtotal" and x["year"] == str(yr)][0])
        check(f"N7d PelbagaiKWAK {sec[:18]} {yr}", det, sub)
    subs = sum(num(x["amount_rm"]) for x in r if x["fund_bm"] == "Pelbagai Kumpulan Wang Amanah Kerajaan" and x["row_type"] == "subtotal" and x["year"] == str(yr))
    grand = num([x["amount_rm"] for x in r if x["fund_bm"] == "Pelbagai Kumpulan Wang Amanah Kerajaan" and x["row_type"] == "total" and x["year"] == str(yr)][0])
    check(f"N7d PelbagaiKWAK grand {yr}", subs, grand)
# Awam
for yr in (2010, 2009):
    for sec in ("AMANAH KHAS", "AMANAH AM"):
        det = sum(num(x["amount_rm"]) for x in r if x["fund_group_bm"] == "KUMPULAN WANG AMANAH AWAM" and x["section_bm"] == sec and x["row_type"] == "detail" and x["year"] == str(yr))
        sub = num([x["amount_rm"] for x in r if x["fund_group_bm"] == "KUMPULAN WANG AMANAH AWAM" and x["section_bm"] == sec and x["row_type"] == "subtotal" and x["year"] == str(yr)][0])
        check(f"N7d Awam {sec} {yr}", det, sub)
    subs = sum(num(x["amount_rm"]) for x in r if x["fund_group_bm"] == "KUMPULAN WANG AMANAH AWAM" and x["row_type"] == "subtotal" and x["section_bm"] != "Penyata Ringkasan" and x["year"] == str(yr))
    grand = num([x["amount_rm"] for x in r if x["fund_group_bm"] == "KUMPULAN WANG AMANAH AWAM" and x["row_type"] == "total" and x["year"] == str(yr)][0])
    check(f"N7d Awam grand {yr}", subs, grand)
# Deposit
for yr in (2010, 2009):
    for sec in ("DEPOSIT AM", "DEPOSIT PELARASAN"):
        det = sum(num(x["amount_rm"]) for x in r if x["fund_group_bm"] == "AKAUN DEPOSIT" and x["section_bm"] == sec and x["row_type"] == "detail" and x["year"] == str(yr))
        sub = num([x["amount_rm"] for x in r if x["fund_group_bm"] == "AKAUN DEPOSIT" and x["section_bm"] == sec and x["row_type"] == "subtotal" and x["year"] == str(yr)][0])
        check(f"N7d Deposit {sec} {yr}", det, sub)
    subs = sum(num(x["amount_rm"]) for x in r if x["fund_group_bm"] == "AKAUN DEPOSIT" and x["row_type"] == "subtotal" and x["section_bm"] != "Penyata Ringkasan" and x["year"] == str(yr))
    grand = num([x["amount_rm"] for x in r if x["fund_group_bm"] == "AKAUN DEPOSIT" and x["row_type"] == "total" and x["year"] == str(yr)][0])
    check(f"N7d Deposit grand {yr}", subs, grand)

# --- Nota 8 memo assets ---
r, _ = load(W2010, "fact_memo_assets_detail")
for yr in (2010, 2009):
    for sec in ("Pinjaman Boleh Dituntut", "Pelaburan"):
        det = sum(num(x["amount_rm"]) for x in r if x["section_bm"] == sec and x["row_type"] == "detail" and x["year"] == str(yr))
        tot = num([x["amount_rm"] for x in r if x["section_bm"] == sec and x["row_type"] == "total" and x["year"] == str(yr)][0])
        check(f"N8 {sec} {yr}", det, tot)

# --- Nota 9a debt ---
r, _ = load(W2010, "fact_debt")
for yr in (2010, 2009):
    dn = sum(num(x["amount_rm"]) for x in r if x["group_bm"] == "Pinjaman Dalam Negeri" and x["kind"] == "instrument" and x["year"] == str(yr))
    dnsub = num([x["amount_rm"] for x in r if x["item_bm"] == "Dalam Negeri" and x["kind"] == "subtotal" and x["year"] == str(yr)][0])
    check(f"N9a Dalam Negeri subtotal {yr}", dn, dnsub)
    jp = num([x["amount_rm"] for x in r if x["item_bm"] == "Jumlah Pinjaman" and x["year"] == str(yr)][0])
    jp_comp = dnsub + num([x["amount_rm"] for x in r if x["item_bm"] == "Pinjaman Pasaran" and x["year"] == str(yr)][0]) + num([x["amount_rm"] for x in r if x["item_bm"] == "Pembiayaan Kumpulan Wang Pinjaman Perumahan" and x["year"] == str(yr)][0])
    check(f"N9a Jumlah Pinjaman {yr}", jp_comp, jp)
    jbln = num([x["amount_rm"] for x in r if x["item_bm"] == "Jumlah Bantuan Luar Negeri" and x["year"] == str(yr)][0])
    bln_comp = sum(num(x["amount_rm"]) for x in r if x["group_bm"] == "Bantuan Luar Negeri" and x["year"] == str(yr))
    check(f"N9a Jumlah Bantuan LN {yr}", bln_comp, jbln)
    tot = num([x["amount_rm"] for x in r if x["item_bm"] == "JUMLAH HUTANG AWAM" and x["year"] == str(yr)][0])
    check(f"N9a JUMLAH HUTANG AWAM {yr}", jp + jbln, tot)

# --- Nota 9b commitment ---
r, _ = load(W2010, "fact_commitment_detail")
for yr in (2010, 2009):
    det = sum(num(x["amount_rm"]) for x in r if x["row_type"] == "detail" and x["year"] == str(yr))
    tot = num([x["amount_rm"] for x in r if x["row_type"] == "total" and x["year"] == str(yr)][0])
    check(f"N9b Pelbagai Liabiliti {yr}", det, tot)

# --- KEY VALUE assertions ---
print("\n--- KEY VALUE cross-checks ---")
def keyval(name, got, exp):
    ok = abs(got - exp) < 0.5
    print(f"{'OK ' if ok else 'FAIL'} {name}: {got:,.0f} (exp {exp:,.0f})")
    return ok
r, _ = load(W2010, "fact_cash_components")
keyval("N3 JUMLAH 2010", num([x["amount_rm"] for x in r if x["row_type"]=="total" and x["year"]=="2010"][0]), 21573280678)
keyval("N3 JUMLAH 2009", num([x["amount_rm"] for x in r if x["row_type"]=="total" and x["year"]=="2009"][0]), 27520118474)
r, _ = load(W2010, "fact_revenue")
keyval("N5a Jumlah Hasil sebenar 2010", num([x["sebenar_rm"] for x in r if x["level"]=="0"][0]), 159652962318)
r, _ = load(W2010, "fact_memo_assets_detail")
keyval("N8a Pinjaman Boleh Dituntut 2010", num([x["amount_rm"] for x in r if x["line_item_bm"]=="JUMLAH PINJAMAN BOLEH DITUNTUT" and x["year"]=="2010"][0]), 82319087678)
keyval("N8b Pelaburan 2010", num([x["amount_rm"] for x in r if x["line_item_bm"]=="JUMLAH PELABURAN" and x["year"]=="2010"][0]), 27723148058)
r, _ = load(W2010, "fact_debt")
keyval("N9a Hutang Awam 2010", num([x["amount_rm"] for x in r if x["item_bm"]=="JUMLAH HUTANG AWAM" and x["year"]=="2010"][0]), 407101235939)
keyval("N9b Pelbagai Liabiliti 2010", num([x["amount_rm"] for x in r if x["item_bm"]=="PELBAGAI LIABILITI" and x["year"]=="2010"][0]), 206605049)

print("\n" + "=" * 60)
print(f"VALIDATION RESULT: {PASS} pass / {FAIL} fail")
print("=" * 60)
for f in fails:
    print("  FAIL:", f)
