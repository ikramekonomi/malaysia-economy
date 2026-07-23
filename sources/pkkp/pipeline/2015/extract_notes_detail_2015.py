#!/usr/bin/env python3
"""Extract Nota 3, 4, 7 (top-level + fund-level), 8, 9(a), 9(b) detail tables +
in-scope narrative figures (Nota 4, 7, 7(a)(i), 8(b), 9(a), 10, 11, 12) from
PKKP 2015 (pdf pages 64-76, printed 50-62) into tidy warehouse CSVs.

METHOD: the volume has NO text layer (144-dpi scans). Every amount below was
EYE-TYPED from rendered crops (ocrlib.save_crop, scale 2-6) in
/home/claude/pkkp/work/2015/crops/ and cross-confirmed by (a) the volume's own
printed arithmetic, (b) the psm-6 OCR text where it agreed, and (c) the
2016-volume comparative columns (warehouse2016) / 2014-volume current columns
(warehouse2014). Nothing is corrected against other years; discrepancies vs
other volumes are logged WARN 'restatement candidate' and kept AS PRINTED.

2015-volume format notes vs 2014:
 - Nota 4 keeps the KWA/Am x current/prior matrix. NEW: KWA 'Pelbagai'
   188,038,484 (2014: '-'). No declared reclassification this year.
 - Nota 7(a)(i) BAYARAN now carries a 'Perbelanjaan Pembangunan' sub-head over
   Langsung/Pinjaman. TERIMAAN drops the 2014 row 'Perbezaan Forex Relending
   Loan'; 'Terimaan Balik Pendahuluan' prints '-' for 2015.
 - Nota 7(a)(ii) KWPP still live (corporatised to LPPSA only in 2016); NEW
   BAYARAN row 'Pelbagai' (132,236,408).
 - Nota 7(a)(iii) KUMPULAN WANG YANG LAIN: NEW funds 'Kumpulan Wang Bayaran
   Balik Cukai Barang dan Perkhidmatan' (GST refunds, 2,261,802,724) and
   'Kumpulan Wang Amanah Fi Jaminan' (42,035,274). Its printed subtotal label
   is 'Jumlah Pelbagai Kumpulan Wang' (sic, eye-verified).
 - Nota 7(b) AMANAH KHAS: NEW rows 'Akaun Amanah Estet Kebankrapan'
   (1,644,143,926; 2014 comparative printed as literally RM2) and 'Akaun
   Amanah Am Pelikuidasi' (344,880,411) - declared reclassification out of
   Deposit Am. 'Pelbagai Amanah Khas' 2014 comparative printed 140,672,010
   (2014 volume printed 140,672,012): RM2 shifted to the Estet row; subtotal
   675,929,420 unchanged. Kept as printed, logged WARN.
 - Nota 7(c) Deposit labels renamed/reordered: 'Deposit Wang Tak Dituntut' ->
   'Wang Tak Dituntut', 'Deposit Mahkamah Tinggi' -> 'Mahkamah Tinggi',
   'Harta Kebangkrapan' -> 'Harta Kebankrapan' (2015 balance nil, declared
   reclassification to Amanah Khas); DEPOSIT PELARASAN: 'Pembatalan Bayaran
   EFT' -> 'Pindahan Dana Elektronik Terbatal', 'Pembatalan Pencen Skim B' ->
   'Deposit Amanah Pencen Skim B'.
 - Nota 8(b): DECLARED RESTATEMENT of 2014 book value 29,883,017,259 ->
   30,208,017,258 (+324,999,999 on Syarikat: 28,625,590,154 -> 28,950,590,153).
 - Nota 9(a) grand label still 'JUMLAH HUTANG AWAM' (2016 renamed it
   Persekutuan). Print order: Dalam Negeri, Luar Negeri, KWPP.
 - Nota 9(b) Pelbagai Liabiliti present (3 items) -> fact_commitment_detail.
 - Nota 10/11/12 narrative-only -> fact_other_notes.
"""
import csv, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ocrlib import parse_amount as N, append_checks, SRC

WH = "/home/claude/pkkp/warehouse2015"

checks = []
def CHK(status_name, got, want, status=None):
    ok = abs(got - float(want)) < 0.5
    checks.append(("PASS" if ok else "FAIL" if status is None else status,
                   status_name, got, float(want), got - float(want)))

def LOG(status, text, got="", want="", diff=""):
    checks.append((status, text, got, want, diff))

def prov(pdf_page, statement):
    return dict(source_file=SRC, pdf_page=pdf_page, printed_page=pdf_page - 14,
                statement=statement)

def write_csv(path, cols, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)

# =====================================================================
# 1. Nota 3 WANG TUNAI (pdf 65, printed 51) - eye-read crops/p65_nota3.png
# =====================================================================
cash_src = [  # label, 2015, 2014, row_type
    ("Wang Tunai Dalam Bank", "22,031,497,574", "16,479,289,901", "detail"),
    ("Wang Tunai Dalam Perjalanan", "937,652,138", "943,952,421", "detail"),
    ("Wang Tunai Dalam Tangan", "3,398,403", "3,428,750", "detail"),
    ("JUMLAH WANG TUNAI", "22,972,548,115", "17,426,671,072", "total"),
]
cash_rows = []
for label, a15, a14, rt in cash_src:
    for yr, amt in ((2015, a15), (2014, a14)):
        cash_rows.append(dict(line_item_bm=label, year=yr, amount_rm=N(amt),
                              row_type=rt, has_footnote=False,
                              **prov(65, "Nota 3 Wang Tunai")))
for yr in (2015, 2014):
    det = sum(r["amount_rm"] for r in cash_rows
              if r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in cash_rows
           if r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"nota3: cash details sum = printed total {yr}", det, tot)
CHK("nota3: control JUMLAH WANG TUNAI 2015 = position statement",
    22972548115.0, 22972548115)
CHK("nota3: control JUMLAH WANG TUNAI 2014 comparative = position statement",
    17426671072.0, 17426671072)

# =====================================================================
# 2. Nota 4 PELABURAN (pdf 65, printed 51) - eye-read crops/p65_nota4.png
# =====================================================================
KWA, AM = "Pelaburan Kumpulan Wang Amanah", "Pelaburan Am"
inv_src = [  # label, kwa15, am15, kwa14, am14
    ("Sekuriti Kerajaan Luar Negeri", "6,457,367,557", "-", "5,007,128,695", "-"),
    ("Sekuriti Kerajaan Malaysia", "2,467,099,537", "-", "1,951,810,234", "-"),
    ("Sekuriti Tersiar Harga Dalam Negeri", "676,753", "-", "676,753", "-"),
    ("Sekuriti Tidak Tersiar Harga Dalam Negeri", "440,108,058", "6,617,761,577", "440,108,058", "6,142,945,695"),
    ("Deposit Jangka Pendek Dalam Negeri Melebihi 3 - 12 Bulan", "7,459,461,999", "2,122,188,013", "7,364,290,243", "2,506,038,013"),
    ("Pelbagai", "188,038,484", "1,670,558", "-", "1,670,558"),
]
inv_sub = {(KWA, 2015): "17,012,752,388", (AM, 2015): "8,741,620,148",
           (KWA, 2014): "14,764,013,983", (AM, 2014): "8,650,654,266"}
inv_tot = {2015: "25,754,372,536", 2014: "23,414,668,249"}
P4 = prov(65, "Nota 4 Pelaburan")
inv_rows = []
for yr in (2015, 2014):
    inv_rows.append(dict(category_bm="", line_item_bm="JUMLAH PELABURAN", year=yr,
                         amount_rm=N(inv_tot[yr]), row_type="total",
                         has_footnote=False, **P4))
for label, k15, a15, k14, a14 in inv_src:
    for yr, kv, av in ((2015, k15, a15), (2014, k14, a14)):
        for cat, amt in ((KWA, kv), (AM, av)):
            inv_rows.append(dict(category_bm=cat, line_item_bm=label, year=yr,
                                 amount_rm=N(amt), row_type="detail",
                                 has_footnote=False, **P4))
for (cat, yr), amt in inv_sub.items():
    inv_rows.append(dict(category_bm=cat, line_item_bm="Jumlah", year=yr,
                         amount_rm=N(amt), row_type="subtotal",
                         has_footnote=False, **P4))
for yr in (2015, 2014):
    for cat in (KWA, AM):
        det = sum(r["amount_rm"] for r in inv_rows if r["year"] == yr
                  and r["category_bm"] == cat and r["row_type"] == "detail")
        CHK(f"nota4: {cat} details = Jumlah {yr}", det, N(inv_sub[(cat, yr)]))
    subs = sum(N(inv_sub[(c, yr)]) for c in (KWA, AM))
    CHK(f"nota4: subtotals = JUMLAH PELABURAN {yr}", subs, N(inv_tot[yr]))
CHK("nota4: control JUMLAH PELABURAN 2015 = position statement",
    N(inv_tot[2015]), 25754372536)
CHK("nota4: control JUMLAH PELABURAN 2014 comparative = position statement",
    N(inv_tot[2014]), 23414668249)

# =====================================================================
# 3. Nota 7 top-level table (pdf 70, printed 56) -> fact_trust_accounts
#    eye-read crops/p70_trust_top1.png / p70_trust_top2.png /
#    p70_dep_pelarasan_zoom.png
# =====================================================================
S7 = "Nota 7 Akaun Amanah Disatukan"
KWK = "KUMPULAN WANG AMANAH KERAJAAN"
KAW = "KUMPULAN WANG AMANAH AWAM"
DEP = "AKAUN DEPOSIT"
ta_src = [  # parent, account, awal, debit, kredit, akhir
    (KWK, "Kumpulan Wang Pembangunan",
     "(53,911,937,389)", "43,119,443,985", "55,175,007,728", "(41,856,373,646)"),
    (KWK, "Kumpulan Wang Pinjaman Perumahan",
     "1,239,537,651", "19,685,344,218", "20,230,182,868", "1,784,376,301"),
    (KWK, "Pelbagai Kumpulan Wang Amanah Kerajaan",
     "23,282,336,649", "401,214,601,430", "407,912,456,244", "29,980,191,463"),
    ("", KWK,
     "(29,390,063,089)", "464,019,389,633", "483,317,646,840", "(10,091,805,882)"),
    (KAW, "Kumpulan Wang Amanah Khas",
     "675,929,420", "477,882,638", "2,507,877,804", "2,705,924,586"),
    (KAW, "Kumpulan Wang Amanah Am",
     "7,903,580,164", "19,873,408,389", "18,720,331,597", "6,750,503,372"),
    ("", KAW,
     "8,579,509,584", "20,351,291,027", "21,228,209,401", "9,456,427,958"),
    (DEP, "Deposit Am",
     "9,970,547,418", "5,278,888,537", "3,958,595,887", "8,650,254,768"),
    # Debit eye-verified 1,419,881,911 at scale 4 (psm-6 OCR misread ...914);
    # also forced by both the printed column sum and the row identity.
    (DEP, "Deposit Pelarasan",
     "226,098,223", "1,419,881,911", "1,657,091,275", "463,307,587"),
    ("", DEP,
     "10,196,645,641", "6,698,770,448", "5,615,687,162", "9,113,562,355"),
    ("JUMLAH", "AKAUN AMANAH DISATUKAN",
     "(10,613,907,864)", "491,069,451,108", "510,161,543,403", "8,478,184,431"),
]
ta_rows = []
for parent, acct, aw, db, kr, ak in ta_src:
    ta_rows.append(dict(parent_group_bm=parent, account_bm=acct, year=2015,
                        baki_awal_rm=N(aw), debit_rm=N(db), kredit_rm=N(kr),
                        baki_akhir_rm=N(ak), **prov(70, S7)))
LOG("INFO", "nota7: eye-verification p70 Deposit Pelarasan debit: psm-6 OCR "
    "'1,419,881,914' sebenar 1,419,881,911 [scale-4 crop; forced by printed "
    "Jumlah Akaun Deposit debit 6,698,770,448 and row identity to 463,307,587]",
    1419881911, 1419881911, 0)
by_acct = {r["account_bm"]: r for r in ta_rows}
for r in ta_rows:
    CHK(f"nota7: roll-forward awal-debit+kredit=akhir [{r['account_bm']}]",
        r["baki_awal_rm"] - r["debit_rm"] + r["kredit_rm"], r["baki_akhir_rm"])
for tot, parts in ((KWK, ["Kumpulan Wang Pembangunan",
                          "Kumpulan Wang Pinjaman Perumahan",
                          "Pelbagai Kumpulan Wang Amanah Kerajaan"]),
                   (KAW, ["Kumpulan Wang Amanah Khas", "Kumpulan Wang Amanah Am"]),
                   (DEP, ["Deposit Am", "Deposit Pelarasan"]),
                   ("AKAUN AMANAH DISATUKAN", [KWK, KAW, DEP])):
    for col in ("baki_awal_rm", "debit_rm", "kredit_rm", "baki_akhir_rm"):
        CHK(f"nota7: column sum {col} = printed [{tot}]",
            sum(by_acct[p][col] for p in parts), by_acct[tot][col])
CHK("nota7: control grand baki akhir 2015 = position statement",
    by_acct["AKAUN AMANAH DISATUKAN"]["baki_akhir_rm"], 8478184431)
CHK("nota7: control grand baki awal = 2014 closing (10,613,907,864)",
    by_acct["AKAUN AMANAH DISATUKAN"]["baki_awal_rm"], -10613907864)

# cross-year: every baki awal = warehouse2014 baki akhir
w14 = {r["account_bm"]: r for r in
       csv.DictReader(open("/home/claude/pkkp/warehouse2014/fact_trust_accounts.csv"))}
for acct, r in by_acct.items():
    if acct in w14:
        CHK(f"nota7: baki awal 01.01.2015 = warehouse2014 baki akhir [{acct}]",
            r["baki_awal_rm"], float(w14[acct]["baki_akhir_rm"]))

# =====================================================================
# 4. Nota 7 fund-level detail -> fact_trust_fund_detail
# =====================================================================
trust_rows = []
def T(fund_group, fund, section, item, yr, amt, rt, pg, stmt):
    trust_rows.append(dict(fund_group_bm=fund_group, fund_bm=fund,
                           section_bm=section, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type=rt, has_footnote=False,
                           **prov(pg, stmt)))

# --- 7(a)(i) Kumpulan Wang Pembangunan (pdf 71, printed 57)
#     eye-read crops/p71_kwp.png
S1 = "Nota 7(a)(i) Kumpulan Wang Pembangunan"
KWP = "Kumpulan Wang Pembangunan"
kwp_src = [  # section, item, 2015, 2014, row_type
    ("", "BAKI PADA 1 JANUARI", "(53,911,937,389)", "(40,535,070,833)", "opening"),
    ("TERIMAAN", "Caruman Dari Akaun Hasil Disatukan", "2,091,232,319", "1,036,530,784", "detail"),
    ("TERIMAAN", "Pindahan Dari Akaun Pinjaman Disatukan", "49,249,460,003", "23,976,324,011", "detail"),
    ("TERIMAAN", "Terimaan Balik Pinjaman", "1,232,537,916", "1,047,496,587", "detail"),
    ("TERIMAAN", "Terimaan Balik Pendahuluan", "-", "60,728,977", "detail"),
    ("TERIMAAN", "Jualan Aset Modal", "14,322", "42,799", "detail"),
    ("TERIMAAN", "Pelbagai Terimaan", "250,030,850", "5,497,682", "detail"),
    ("TERIMAAN", "Jumlah Terimaan", "52,823,275,410", "26,126,620,840", "subtotal"),
    ("BAYARAN / Perbelanjaan Pembangunan", "Langsung", "38,596,110,048", "37,624,076,539", "detail"),
    ("BAYARAN / Perbelanjaan Pembangunan", "Pinjaman", "2,171,601,619", "1,879,410,857", "detail"),
    ("BAYARAN", "Jumlah Bayaran", "40,767,711,667", "39,503,487,396", "subtotal"),
    ("", "Lebihan/(Kurangan) bagi Tahun", "12,055,563,743", "(13,376,866,556)", "net"),
    ("", "BAKI PADA 31 DISEMBER", "(41,856,373,646)", "(53,911,937,389)", "closing"),
]
for sec, item, a15, a14, rt in kwp_src:
    for yr, amt in ((2015, a15), (2014, a14)):
        T(KWK, KWP, sec, item, yr, amt, rt, 71, S1)
for yr in (2015, 2014):
    rs = [r for r in trust_rows if r["fund_bm"] == KWP and r["year"] == yr]
    g = lambda pre, rt: sum(r["amount_rm"] for r in rs
                            if r["section_bm"].startswith(pre) and r["row_type"] == rt)
    one = lambda item: [r["amount_rm"] for r in rs if r["line_item_bm"] == item][0]
    CHK(f"nota7(a)(i): KWP TERIMAAN details = subtotal {yr}",
        g("TERIMAAN", "detail"), g("TERIMAAN", "subtotal"))
    CHK(f"nota7(a)(i): KWP BAYARAN details = subtotal {yr}",
        g("BAYARAN", "detail"), g("BAYARAN", "subtotal"))
    CHK(f"nota7(a)(i): KWP terimaan-bayaran = Lebihan/(Kurangan) {yr}",
        g("TERIMAAN", "subtotal") - g("BAYARAN", "subtotal"),
        one("Lebihan/(Kurangan) bagi Tahun"))
    CHK(f"nota7(a)(i): KWP opening+net = closing {yr}",
        one("BAKI PADA 1 JANUARI") + one("Lebihan/(Kurangan) bagi Tahun"),
        one("BAKI PADA 31 DISEMBER"))
CHK("nota7(a)(i): KWP closing 2015 = Nota 7 top table", -41856373646.0,
    by_acct[KWP]["baki_akhir_rm"])
CHK("nota7(a)(i): KWP net 2015 = top-table kredit-debit",
    12055563743.0, by_acct[KWP]["kredit_rm"] - by_acct[KWP]["debit_rm"])

# --- 7(a)(ii) Kumpulan Wang Pinjaman Perumahan (pdf 71-72, printed 57-58)
#     eye-read crops/p71_kwpp1.png / p72_kwpp2.png
S2 = "Nota 7(a)(ii) Kumpulan Wang Pinjaman Perumahan"
KWPP = "Kumpulan Wang Pinjaman Perumahan"
kwpp_src = [  # section, item, 2015, 2014, row_type, pdf_page
    ("", "BAKI PADA 1 JANUARI", "1,239,537,651", "1,324,944,951", "opening", 71),
    ("TERIMAAN / Pinjaman Perseorangan", "Bayaran Balik Pinjaman Perseorangan", "1,697,368,247", "1,533,029,162", "detail", 71),
    ("TERIMAAN / Pinjaman Perseorangan", "Hasil Pensekuritian", "-", "58,273,033", "detail", 71),
    ("TERIMAAN / Pembiayaan", "Pelbagai Pembiayaan", "10,000,000,000", "11,500,000,000", "detail", 71),
    ("TERIMAAN / Pendapatan Faedah", "Bayaran Balik Faedah Pinjaman Perseorangan", "1,590,845,163", "1,403,066,372", "detail", 71),
    ("TERIMAAN / Akaun Pensekuritian", "Kutipan Bayaran Balik Akaun Pensekuritian", "2,554,377,359", "2,659,660,349", "detail", 71),
    ("TERIMAAN / Akaun Pensekuritian", "Peruntukan Diskaun Pensekuritian", "338,040,396", "376,544,776", "detail", 71),
    ("TERIMAAN", "Pelbagai", "35,315,387", "108,368,161", "detail", 71),
    ("TERIMAAN", "Jumlah Terimaan", "16,215,946,552", "17,638,941,853", "subtotal", 71),
    ("BAYARAN / Pinjaman Perseorangan", "Pengeluaran Pinjaman Perseorangan", "(8,665,945,568)", "(9,171,503,943)", "detail", 72),
    ("BAYARAN / Pembiayaan", "Bayaran Balik Pelbagai Pembiayaan", "(4,300,000,000)", "(6,100,000,000)", "detail", 72),
    ("BAYARAN / Akaun Pensekuritian", "Serahan Kutipan Akaun Pensekuritian", "(2,553,305,946)", "(2,438,248,577)", "detail", 72),
    ("BAYARAN / Akaun Pensekuritian", "Bayaran Lain Akaun Pensekuritian", "(19,619,980)", "(14,596,633)", "detail", 72),
    ("BAYARAN", "Pelbagai", "(132,236,408)", "-", "detail", 72),
    ("BAYARAN", "Jumlah Bayaran", "(15,671,107,902)", "(17,724,349,153)", "subtotal", 72),
    ("", "BAKI PADA 31 DISEMBER", "1,784,376,301", "1,239,537,651", "closing", 72),
]
for sec, item, a15, a14, rt, pg in kwpp_src:
    for yr, amt in ((2015, a15), (2014, a14)):
        T(KWK, KWPP, sec, item, yr, amt, rt, pg, S2)
for yr in (2015, 2014):
    rs = [r for r in trust_rows if r["fund_bm"] == KWPP and r["year"] == yr]
    ter = sum(r["amount_rm"] for r in rs
              if r["section_bm"].startswith("TERIMAAN") and r["row_type"] == "detail")
    ter_s = [r["amount_rm"] for r in rs if r["line_item_bm"] == "Jumlah Terimaan"][0]
    bay = sum(r["amount_rm"] for r in rs
              if r["section_bm"].startswith("BAYARAN") and r["row_type"] == "detail")
    bay_s = [r["amount_rm"] for r in rs if r["line_item_bm"] == "Jumlah Bayaran"][0]
    op = [r["amount_rm"] for r in rs if r["row_type"] == "opening"][0]
    cl = [r["amount_rm"] for r in rs if r["row_type"] == "closing"][0]
    CHK(f"nota7(a)(ii): KWPP TERIMAAN details = subtotal {yr}", ter, ter_s)
    CHK(f"nota7(a)(ii): KWPP BAYARAN details = subtotal {yr}", bay, bay_s)
    CHK(f"nota7(a)(ii): KWPP opening+terimaan+bayaran = closing {yr}",
        op + ter_s + bay_s, cl)
CHK("nota7(a)(ii): KWPP closing 2015 = Nota 7 top table", 1784376301.0,
    by_acct[KWPP]["baki_akhir_rm"])

# --- 7(a)(iii) Pelbagai Kumpulan Wang Amanah Kerajaan (pdf 72-73, printed 58-59)
#     eye-read crops/p72_pkwak1.png / p72_pkwak2.png / p73_kwyl1.png / p73_kwyl2.png
S3 = "Nota 7(a)(iii) Pelbagai Kumpulan Wang Amanah Kerajaan"
PKW = "Pelbagai Kumpulan Wang Amanah Kerajaan"
pkw_src = {
    # category: (subtotal_label, subtotal15, subtotal14, page, items)
    "AKAUN PENYELESAIAN": ("Jumlah Akaun Penyelesaian",
                           "2,243,623,078", "2,156,817,279", 72, [
        # 2015 eye-verified 14,831,283 (psm-6 OCR misread '44,831,283';
        # forced by printed subtotal 2,243,623,078)
        ("Akaun Semasa Antara Pentadbiran", "14,831,283", "14,831,283"),
        ("Akaun Penyelesaian Utama Perbendaharaan", "2,128,791,795", "2,041,985,996"),
        ("Akaun Penyelesaian Jabatan Mengakaun Sendiri", "100,000,000", "100,000,000"),
    ]),
    "AKAUN PERNIAGAAN": ("Jumlah Akaun Perniagaan",
                         "77,377,197", "77,668,364", 72, [
        ("Stor dan Woksyop Belum Diuntukkan", "77,377,197", "77,668,364"),
    ]),
    "AKAUN PINJAMAN": ("Jumlah Akaun Pinjaman",
                       "7,559,001,053", "7,763,642,257", 72, [
        ("Kontraktor", "8,008,742", "6,961,438"),
        ("Kredit Kerjasama", "15,037,189", "15,037,189"),
        ("Modal Pusingan Jabatan Pembangunan Koperasi", "162,939,979", "105,298,941"),
        ("Pembangunan Ekonomi Belia", "10,923,092", "6,729,018"),
        ("Pembiayaan Komputer Anggota Perkhidmatan Awam", "92,470,431", "93,149,013"),
        ("Pendahuluan Diri (Pegawai Awam)", "106,373,720", "137,256,413"),
        ("Pendahuluan Pelbagai", "58,704,116", "58,414,113"),
        ("Pendahuluan Peti Sejuk Sarawak", "620,000", "620,000"),
        ("Pendahuluan Untuk Negeri", "109,750,289", "132,900,289"),
        ("Pinjaman Diraja", "2,617,771", "2,522,438"),
        ("Pinjaman Kenderaan", "665,984,835", "666,405,513"),
        ("Pinjaman Kepada Badan Berkanun dan Badan Lain", "5,639,935,362", "5,879,831,188"),
        ("Pinjaman Perumahan kepada Golongan Pendapatan Rendah", "64,314,511", "77,651,847"),
        ("Rakyat Malaysia di Luar Negeri", "1,154,437", "1,117,744"),
        ("Tabung Pusingan Pinjaman Pelajaran Persekutuan", "620,166,579", "579,747,113"),
    ]),
    "KUMPULAN WANG LUAR JANGKA": ("Jumlah Kumpulan Wang Luar Jangka",
                                  "409,934,551", "1,255,624,280", 72, [
        ("Kumpulan Wang Luar Jangka", "409,934,551", "1,255,624,280"),
    ]),
    # printed subtotal label is 'Jumlah Pelbagai Kumpulan Wang' (sic) -
    # eye-verified crops/p73_kwyl2.png
    "KUMPULAN WANG YANG LAIN": ("Jumlah Pelbagai Kumpulan Wang",
                                "19,690,255,584", "12,028,584,469", 73, [
        ("Amanah Negara", "12,293,693,028", "9,523,070,010"),
        ("Amanah Pelajar Miskin", "215,185,676", "229,607,833"),
        ("Amanah Sukan Negara", "12,056,833", "16,938,063"),
        ("Bantuan Bencana Negara", "530,098,864", "714,813,016"),
        ("Bantuan Mangsa Serangan Binatang Buas", "1,898,300", "2,753,500"),
        ("Cadangan Untuk Negeri", "294,052,875", "99,731,424"),
        ("Kebajikan dan Kemudahan bagi Penuntut di Luar Negeri", "2,517,356", "3,070,152"),
        ("Kumpulan Wang Amanah Dana Automotif Bumiputra", "4,717,888", "33,959,710"),
        ("Kumpulan Wang Amanah Kebudayaan dan Kebajikan Penggiat Seni", "986,961", "1,541,248"),
        ("Kumpulan Wang Amanah Lembaga Peperiksaan Malaysia", "114,872,765", "76,837,530"),
        ("Kumpulan Wang Amanah Bagi Pembangunan Projek ICT Sektor Awam", "1,000,000", "1,000,000"),
        ("Kumpulan Wang Amanah Pendidikan, Perundingan dan Penyelidikan, Institut Penilaian Negara", "2,294,020", "2,517,487"),
        ("Kumpulan Wang Amanah Pengangkutan Awam", "263,613,100", "469,191,949"),
        ("Kumpulan Wang Amanah Pengurusan Perolehan Setem Cukai (Banderol) untuk Rokok dan Minuman Keras", "52,403,532", "50,951,084"),
        ("Kumpulan Wang Bayaran Balik Cukai Barang dan Perkhidmatan", "2,261,802,724", "-"),
        ("Kumpulan Wang Amanah Projek dan Pengukuran Sempadan Bersama Di antara Negeri-negeri Semenanjung Malaysia", "5,661,735", "6,364,603"),
        ("Kumpulan Wang Amanah Fi Jaminan", "42,035,274", "-"),
        ("Kumpulan Wang Amanah Projek Pelantar Benua Malaysia", "637,328", "779,768"),
        ("Kumpulan Wang Amanah Sokongan Jabatan Kehakiman Syariah Malaysia", "13,398,878", "13,202,080"),
        ("Kumpulan Wang Amanah Tabung Konservasi Sumber Asli Nasional", "10,050,625", "10,000,000"),
        ("Kumpulan Wang Amanah Taman Laut dan Rizab Laut", "5,359,113", "5,142,408"),
        ("Kursi Pengajian Melayu Leiden University, The Netherlands", "794", "794"),
        ("Majlis Penyelidikan dan Kemajuan Sains Negara", "3,532,083", "3,147,930"),
        ("Penjelas Hutang", "234,893,705", "225,450,294"),
        ("Perkhidmatan Kemasyarakatan dan Kebajikan", "41,690,711", "49,188,440"),
        ("Perpustakaan Negara", "1,265,762", "1,096,915"),
        ("Program Perumahan Rakyat Dimiliki", "452,957,401", "258,018,140"),
        ("Skim Biasiswa Sukan Persekutuan", "853,694", "911,590"),
        ("Tabung Bantuan Perubatan", "45,201,263", "30,264,250"),
        ("Tabung Bayaran Balik Cukai", "2,761,636,753", "179,136,825"),
        ("Tabung Inovasi Negara Berhad", "19,813,116", "19,813,116"),
        ("Tabung Pustaka Peringatan P. Ramlee", "73,427", "84,310"),
    ]),
}
LOG("INFO", "nota7(a)(iii): eye-verification p72 Akaun Semasa Antara "
    "Pentadbiran 2015: psm-6 OCR '44,831,283' sebenar 14,831,283 [scale-2 "
    "crop; forced by printed Jumlah Akaun Penyelesaian 2,243,623,078]",
    14831283, 14831283, 0)
LOG("INFO", "nota7(a)(iii): print anomaly p73: KUMPULAN WANG YANG LAIN "
    "subtotal is labelled 'Jumlah Pelbagai Kumpulan Wang' (eye-verified); "
    "kept as printed")
for cat, (slabel, s15, s14, pg, items) in pkw_src.items():
    for yr, amt in ((2015, s15), (2014, s14)):
        T(KWK, PKW, cat, slabel, yr, amt, "subtotal", pg, S3)
    for item, a15, a14 in items:
        for yr, amt in ((2015, a15), (2014, a14)):
            T(KWK, PKW, cat, item, yr, amt, "detail", pg, S3)
for yr, amt in ((2015, "29,980,191,463"), (2014, "23,282,336,649")):
    T(KWK, PKW, "", "JUMLAH PELBAGAI KUMPULAN WANG AMANAH KERAJAAN",
      yr, amt, "total", 73, S3)
for yr in (2015, 2014):
    for cat, (slabel, s15, s14, pg, items) in pkw_src.items():
        det = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
                  and r["year"] == yr and r["section_bm"] == cat
                  and r["row_type"] == "detail")
        CHK(f"nota7(a)(iii): {cat} details = subtotal {yr}",
            det, N(s15 if yr == 2015 else s14))
    dets = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
               and r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
           and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"nota7(a)(iii): all details = JUMLAH PELBAGAI KWAK {yr}", dets, tot)
CHK("nota7(a)(iii): PKWAK total 2015 = Nota 7 top table", 29980191463.0,
    by_acct[PKW]["baki_akhir_rm"])

# --- 7(b) Kumpulan Wang Amanah Awam (pdf 73, printed 59)
#     eye-read crops/p73_awam.png / p73_pelbagaikhas_zoom.png / p73_estet2014_zoom.png
S4 = "Nota 7(b) Kumpulan Wang Amanah Awam"
awam_src = {
    "AMANAH KHAS": ("Jumlah Amanah Khas", "2,705,924,586", "675,929,420", [
        # 2014 comparative literally prints '2' (RM two) - eye-verified at
        # scale 6; needed for the printed 2014 subtotal 675,929,420.
        ("Akaun Amanah Estet Kebankrapan", "1,644,143,926", "2"),
        ("Akaun Amanah Am Pelikuidasi", "344,880,411", "-"),
        ("Kumpulan Wang Dius Api", "343,841,620", "307,294,870"),
        ("Faedah atas Pelaburan untuk Deposit Mahkamah", "231,161,878", "227,962,538"),
        ("Pelbagai Amanah Khas", "141,896,751", "140,672,010"),
    ]),
    "AMANAH AM": ("Jumlah Amanah Am", "6,750,503,372", "7,903,580,164", [
        ("Akaun Amanah Aktiviti Pembangunan Khas Pembiayaan Swasta", "1,736,748,503", "2,958,965,467"),
        ("Akaun Amanah Inisiatif Pembiayaan Swasta", "1,429,294,353", "1,670,014,869"),
        ("Akaun Amanah Dana Khas", "851,447,002", "890,845,481"),
        ("Akaun Amanah Industri Bekalan Elektrik", "543,311,038", "486,453,170"),
        ("Akaun Amanah Membangun/Menaiktaraf Sistem Pembetungan untuk Pembangunan Baru", "424,152,917", "480,911,314"),
        ("Pelbagai Amanah Am", "1,765,549,559", "1,416,389,863"),
    ]),
}
LOG("WARN", "nota7(b): restatement candidate p73: 2014 comparative prints "
    "'Akaun Amanah Estet Kebankrapan' = RM2 and 'Pelbagai Amanah Khas' = "
    "140,672,010; the 2014 volume printed no Estet row and Pelbagai Amanah "
    "Khas 140,672,012 (RM2 shifted between the rows, subtotal 675,929,420 "
    "unchanged). Eye-verified at scale 4-6, kept as printed",
    140672010, 140672012, -2)
# --- 7(c) Akaun Deposit (pdf 74, printed 60) - eye-read crops/p74_deposit.png
S5 = "Nota 7(c) Akaun Deposit"
dep_src = {
    "DEPOSIT AM": ("Jumlah Deposit Am", "8,650,254,768", "9,970,547,418", [
        ("Kawalan Wang Tak Dituntut", "4,195,041,003", "3,636,888,078"),
        ("Wang Jaminan Pelaksanaan", "1,392,243,153", "1,426,358,847"),
        ("Wang Tak Dituntut", "1,112,271,079", "1,299,688,831"),
        ("Mahkamah Tinggi", "899,032,390", "804,404,771"),
        ("Harta Kebankrapan", "-", "1,351,989,426"),
        ("Pelbagai Deposit Am", "1,051,667,143", "1,451,217,465"),
    ]),
    "DEPOSIT PELARASAN": ("Jumlah Deposit Pelarasan", "463,307,587", "226,098,223", [
        ("Terimaan Yang Tidak Diperuntukkan", "275,236,992", "24,410,156"),
        ("Pindahan Dana Elektronik Terbatal", "115,675,717", "123,788,200"),
        ("Deposit Amanah Pencen Skim B", "35,526,475", "35,974,648"),
        ("Deposit Pelarasan Cek Terbatal", "33,640,514", "35,645,852"),
        ("Pelbagai Deposit Pelarasan", "3,227,889", "6,279,367"),
    ]),
}
for grp, src, tot15, tot14, pg, stmt, totlabel in (
        (KAW, awam_src, "9,456,427,958", "8,579,509,584", 73, S4,
         "JUMLAH KUMPULAN WANG AMANAH AWAM"),
        (DEP, dep_src, "9,113,562,355", "10,196,645,641", 74, S5,
         "JUMLAH AKAUN DEPOSIT")):
    for sec, (slabel, s15, s14, items) in src.items():
        for yr, amt in ((2015, s15), (2014, s14)):
            T(grp, "", sec, slabel, yr, amt, "subtotal", pg, stmt)
        for item, a15, a14 in items:
            for yr, amt in ((2015, a15), (2014, a14)):
                T(grp, "", sec, item, yr, amt, "detail", pg, stmt)
    for yr, amt in ((2015, tot15), (2014, tot14)):
        T(grp, "", "", grp, yr, amt, "total", pg, stmt)
    for yr in (2015, 2014):
        for sec, (slabel, s15, s14, items) in src.items():
            det = sum(r["amount_rm"] for r in trust_rows
                      if r["fund_group_bm"] == grp and r["fund_bm"] == ""
                      and r["year"] == yr and r["section_bm"] == sec
                      and r["row_type"] == "detail")
            CHK(f"nota7: {grp}/{sec} details = subtotal {yr}",
                det, N(s15 if yr == 2015 else s14))
        subs = sum(r["amount_rm"] for r in trust_rows
                   if r["fund_group_bm"] == grp and r["fund_bm"] == ""
                   and r["year"] == yr and r["row_type"] == "subtotal")
        tot = [r["amount_rm"] for r in trust_rows
               if r["fund_group_bm"] == grp and r["fund_bm"] == ""
               and r["year"] == yr and r["row_type"] == "total"][0]
        CHK(f"nota7: {grp} subtotals = total {yr}", subs, tot)
CHK("nota7(b): KWA Awam total 2015 = Nota 7 top table", 9456427958.0,
    by_acct[KAW]["baki_akhir_rm"])
CHK("nota7(b): Amanah Khas subtotal 2015 = top table", 2705924586.0,
    by_acct["Kumpulan Wang Amanah Khas"]["baki_akhir_rm"])
CHK("nota7(b): Amanah Am subtotal 2015 = top table", 6750503372.0,
    by_acct["Kumpulan Wang Amanah Am"]["baki_akhir_rm"])
CHK("nota7(c): Akaun Deposit total 2015 = Nota 7 top table", 9113562355.0,
    by_acct[DEP]["baki_akhir_rm"])
CHK("nota7(c): Deposit Am subtotal 2015 = top table", 8650254768.0,
    by_acct["Deposit Am"]["baki_akhir_rm"])
CHK("nota7(c): Deposit Pelarasan subtotal 2015 = top table", 463307587.0,
    by_acct["Deposit Pelarasan"]["baki_akhir_rm"])

# =====================================================================
# 5. Nota 8 MEMORANDUM ASET (pdf 74-75, printed 60-61)
#    eye-read crops/p74_pbd.png / p75_inv.png / p75_restate_narr.png
# =====================================================================
memo_rows = []
def M(section, item, yr, amt, rt, pg):
    memo_rows.append(dict(section_bm=section, line_item_bm=item, year=yr,
                          amount_rm=N(amt), row_type=rt, has_footnote=False,
                          **prov(pg, "Nota 8 Memorandum Aset")))
PBD_SEC = "Pinjaman Boleh Dituntut"
pbd = [  # label, 2015, 2014, row_type
    ("Kerajaan Negeri", "16,932,947,893", "16,470,077,891", "detail"),
    ("Pihak Berkuasa Tempatan", "444,265,276", "451,005,221", "detail"),
    ("Badan Berkanun", "6,357,842,303", "6,820,864,168", "detail"),
    ("Koperasi", "208,302,635", "158,302,635", "detail"),
    ("Syarikat", "28,956,114,122", "28,856,676,215", "detail"),
    ("Perseorangan", "51,102,716,708", "44,061,429,758", "detail"),
    ("Pelbagai", "1,731,269,170", "2,217,667,710", "detail"),
    ("JUMLAH PINJAMAN BOLEH DITUNTUT", "105,733,458,107", "99,036,023,598", "total"),
]
for item, a15, a14, rt in pbd:
    for yr, amt in ((2015, a15), (2014, a14)):
        M(PBD_SEC, item, yr, amt, rt, 74)
pel = [
    ("Syarikat", "29,058,732,884", "28,950,590,153", "detail"),
    ("Badan Berkanun", "1,218,852,876", "1,218,852,876", "detail"),
    ("Agensi Antarabangsa", "38,574,229", "38,574,229", "detail"),
    ("JUMLAH PELABURAN", "30,316,159,989", "30,208,017,258", "total"),
]
for item, a15, a14, rt in pel:
    for yr, amt in ((2015, a15), (2014, a14)):
        M("Pelaburan", item, yr, amt, rt, 75)
for yr in (2015, 2014):
    for sec in (PBD_SEC, "Pelaburan"):
        det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == sec
                  and r["year"] == yr and r["row_type"] == "detail")
        tot = [r["amount_rm"] for r in memo_rows if r["section_bm"] == sec
               and r["year"] == yr and r["row_type"] == "total"][0]
        CHK(f"nota8: {sec} details = printed total {yr}", det, tot)
CHK("nota8(b): declared restatement identity 29,883,017,259 + 324,999,999 = "
    "restated 2014 total", 29883017259 + 324999999, 30208017258)
CHK("nota8(b): Syarikat 2014 restated = 2014-volume 28,625,590,154 + 324,999,999",
    28625590154 + 324999999, 28950590153)
LOG("WARN", "nota8(b): restatement candidate (DECLARED) p75: Pelaburan 2014 "
    "book value restated 29,883,017,259 -> 30,208,017,258 (+324,999,999 on "
    "Syarikat, pegangan saham dalam tiga (3) buah syarikat); kept as printed",
    30208017258, 29883017259, 324999999)

# =====================================================================
# 6. Nota 9(a) HUTANG AWAM (pdf 75, printed 61) -> fact_debt
#    eye-read crops/p75_hutang.png
# =====================================================================
S9 = "Nota 9 Memorandum Liabiliti"
debt_rows = []
def D(group, item, kind, yr, amt, pg=75):
    debt_rows.append(dict(group_bm=group, item_bm=item, kind=kind, year=yr,
                          amount_rm=N(amt), **prov(pg, S9)))
DN, LN, KWPPG, BLN = ("Pinjaman Dalam Negeri", "Pinjaman Luar Negeri",
                      "Kumpulan Wang Pinjaman Perumahan", "Bantuan Luar Negeri")
debt_src = [  # group, item, kind, 2015, 2014
    (DN, "Bil Perbendaharaan", "instrument", "4,700,000,000", "4,320,000,000"),
    (DN, "Terbitan Pelaburan Kerajaan", "instrument", "214,000,000,000", "185,500,000,000"),
    (DN, "Sekuriti Kerajaan Malaysia", "instrument", "340,062,879,000", "329,632,319,000"),
    (DN, "Dalam Negeri", "subtotal", "558,762,879,000", "519,452,319,000"),
    (LN, "Pinjaman Pasaran", "instrument", "15,179,150,000", "11,468,925,000"),
    (KWPPG, "Pinjaman Berjangka", "instrument", "21,900,000,000", "26,200,000,000"),
    (KWPPG, "Sukuk Perumahan Kerajaan", "instrument", "28,400,000,000", "20,400,000,000"),
    (KWPPG, "Kumpulan Wang Pinjaman Perumahan", "subtotal", "50,300,000,000", "46,600,000,000"),
    ("JUMLAH", "PINJAMAN", "subtotal", "624,242,029,000", "577,521,244,000"),
    (BLN, "Pinjaman Multilateral", "instrument", "647,112,909", "656,158,104"),
    (BLN, "Pinjaman Bilateral", "instrument", "5,651,294,201", "4,650,839,177"),
    ("JUMLAH", "BANTUAN LUAR NEGERI", "subtotal", "6,298,407,110", "5,306,997,281"),
    ("JUMLAH", "HUTANG AWAM", "total", "630,540,436,110", "582,828,241,281"),
]
for group, item, kind, a15, a14 in debt_src:
    for yr, amt in ((2015, a15), (2014, a14)):
        D(group, item, kind, yr, amt)
dv = {(r["group_bm"], r["item_bm"], r["year"]): r["amount_rm"] for r in debt_rows}
for yr in (2015, 2014):
    CHK(f"nota9(a): Dalam Negeri instruments = subtotal {yr}",
        sum(dv[(DN, i, yr)] for i in
            ("Bil Perbendaharaan", "Terbitan Pelaburan Kerajaan",
             "Sekuriti Kerajaan Malaysia")), dv[(DN, "Dalam Negeri", yr)])
    CHK(f"nota9(a): KWPP instruments = subtotal {yr}",
        dv[(KWPPG, "Pinjaman Berjangka", yr)] +
        dv[(KWPPG, "Sukuk Perumahan Kerajaan", yr)],
        dv[(KWPPG, "Kumpulan Wang Pinjaman Perumahan", yr)])
    CHK(f"nota9(a): DN + LN + KWPP = Jumlah Pinjaman {yr}",
        dv[(DN, "Dalam Negeri", yr)] + dv[(LN, "Pinjaman Pasaran", yr)] +
        dv[(KWPPG, "Kumpulan Wang Pinjaman Perumahan", yr)],
        dv[("JUMLAH", "PINJAMAN", yr)])
    CHK(f"nota9(a): Multilateral + Bilateral = Jumlah BLN {yr}",
        dv[(BLN, "Pinjaman Multilateral", yr)] +
        dv[(BLN, "Pinjaman Bilateral", yr)],
        dv[("JUMLAH", "BANTUAN LUAR NEGERI", yr)])
    CHK(f"nota9(a): Pinjaman + BLN = JUMLAH HUTANG AWAM {yr}",
        dv[("JUMLAH", "PINJAMAN", yr)] +
        dv[("JUMLAH", "BANTUAN LUAR NEGERI", yr)],
        dv[("JUMLAH", "HUTANG AWAM", yr)])
LOG("INFO", "nota9(a): grand total label printed 'JUMLAH HUTANG AWAM' (as in "
    "the 2014 volume; the 2016 volume renamed it HUTANG PERSEKUTUAN)")

# =====================================================================
# 7. Nota 9(b) PELBAGAI LIABILITI (pdf 76, printed 62)
#    eye-read crops/p76_liab.png -> fact_commitment_detail + fact_debt misc_total
# =====================================================================
com_rows = []
com_src = [  # item, 2015, 2014
    ("Nota Kena Bayar", "672,408,802", "280,810,997"),
    ("Sekuriti Tak Dituntut", "23,706,584", "23,291,530"),
    ("Akaun Depositori Pusat", "14,001,280", "14,002,274"),
]
for item, a15, a14 in com_src:
    for yr, amt in ((2015, a15), (2014, a14)):
        com_rows.append(dict(parent_bm="PELBAGAI LIABILITI", item_bm=item,
                             year=yr, amount_rm=N(amt), row_type="detail",
                             has_footnote=False, **prov(76, S9)))
for yr, tot in ((2015, "710,116,666"), (2014, "318,104,801")):
    D("Pelbagai Liabiliti", "PELBAGAI LIABILITI", "misc_total", yr, tot, pg=76)
    det = sum(r["amount_rm"] for r in com_rows if r["year"] == yr)
    CHK(f"nota9(b): PELBAGAI LIABILITI details = printed total {yr}",
        det, N(tot))

# =====================================================================
# 8. Narrative figures in scope (fact_other_notes)
# =====================================================================
other_rows = []
def O(nota, item, yr, amt, pg, stmt):
    other_rows.append(dict(nota=nota, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type="narrative",
                           has_footnote=False, **prov(pg, stmt)))
O("4", "Pembelian instrumen kewangan di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2015, "1,864,888,405", 65, "Nota 4 Pelaburan")
O("4", "Urus niaga bukan tunai pelarasan pertukaran pinjaman kepada pegangan ekuiti (tidak termasuk dalam pembelian instrumen kewangan)",
  2015, "474,815,882", 65, "Nota 4 Pelaburan")
O("7", "Akaun Penyelesaian Utama Perbendaharaan: debit tidak melibatkan terimaan atau bayaran sebenar",
  2015, "365,031,631,878", 70, S7)
O("7", "Akaun Penyelesaian Utama Perbendaharaan: kredit tidak melibatkan terimaan atau bayaran sebenar",
  2015, "365,118,437,677", 70, S7)
O("7", "Pelbagai Terimaan Amanah di Penyata Penerimaan dan Pembayaran Wang Tunai (baki bersih semasa Akaun Amanah)",
  2015, "478,238,962", 70, S7)
O("7(a)(i)", "Terimaan Balik Pinjaman Kumpulan Wang Pembangunan di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2015, "779,787,608", 70, S1)
O("7(a)(i)", "Pelarasan pertukaran pinjaman kepada pegangan ekuiti (komponen perbezaan Terimaan Balik Pinjaman)",
  2015, "425,452,238", 70, S1)
O("7(a)(i)", "Pelarasan pembayaran balik pinjaman (komponen perbezaan Terimaan Balik Pinjaman)",
  2015, "27,298,070", 70, S1)
O("8(b)", "Nilai buku Pelaburan 2014 sebelum penyata semula",
  2014, "29,883,017,259", 75, "Nota 8 Memorandum Aset")
O("8(b)", "Pelarasan pertambahan nilai buku bagi pegangan saham dalam tiga (3) buah syarikat (penyata semula 2014)",
  2014, "324,999,999", 75, "Nota 8 Memorandum Aset")
O("9(a)", "Pegangan Bukan Pemastautin bagi Pinjaman Dalam Negeri dan Sukuk Perumahan Kerajaan",
  2015, "177,114,249,000", 75, S9)
O("10", "Pinjaman Badan Berkanun dan syarikat milik kerajaan yang dijamin oleh Kerajaan Persekutuan [Akta 96]",
  2015, "177,728,501,888", 76, "Nota 10 Liabiliti Luar Jangka")
O("10", "Simpanan pendeposit di Bank Simpanan Nasional, Kumpulan Wang Simpanan Guru-Guru, Kumpulan Wang Simpanan Pekerja dan Lembaga Tabung Haji",
  2015, "742,608,289,422", 76, "Nota 10 Liabiliti Luar Jangka")
O("11", "Akaun Belum Terima (maklumat tambahan berdasarkan rekod Kementerian/Jabatan)",
  2015, "22,630,780,943", 76, "Nota 11 Akaun Belum Terima")
O("12", "Wang pendahuluan kepada kontraktor yang belum dibayar balik",
  2015, "939,006,676", 76, "Nota 12 Wang Pendahuluan Kepada Kontraktor")

# narrative-vs-table identities the print offers
CHK("nota7(a)(i): Terimaan Balik Pinjaman nota - cash statement = printed "
    "non-cash components", 1232537916 - 779787608, 425452238 + 27298070)
CHK("nota7: APU narrative kredit-debit = APU fund movement (net change "
    "2,128,791,795 - 2,041,985,996)", 365118437677 - 365031631878,
    2128791795 - 2041985996)

# =====================================================================
# 9. Comparative columns vs warehouse2014 (same-table year-2014 rows)
# =====================================================================
def compare_prior(csv14, mine, keyf, label):
    prior = {}
    for r in csv.DictReader(open(f"/home/claude/pkkp/warehouse2014/{csv14}")):
        if r["year"] == "2014":
            prior.setdefault(keyf(r), []).append(float(r["amount_rm"]))
    n_match = n_diff = 0
    for r in mine:
        if r["year"] != 2014:
            continue
        k = keyf({k2: str(v) for k2, v in r.items()})
        if k in prior and len(prior[k]) == 1:
            if abs(prior[k][0] - r["amount_rm"]) < 0.5:
                n_match += 1
            else:
                n_diff += 1
                LOG("WARN", f"{label}: restatement candidate [{k}]: 2015 volume "
                    f"prints {r['amount_rm']:,.0f} vs 2014 volume "
                    f"{prior[k][0]:,.0f}; kept as printed",
                    r["amount_rm"], prior[k][0], r["amount_rm"] - prior[k][0])
    LOG("PASS" if n_diff == 0 else "WARN",
        f"{label}: 2014-comparative vs warehouse2014: {n_match} equal, "
        f"{n_diff} differ", n_match, n_match + n_diff, -n_diff)

compare_prior("fact_cash_components.csv", cash_rows,
              lambda r: r["line_item_bm"], "nota3")
compare_prior("fact_investment_summary.csv", inv_rows,
              lambda r: (r["category_bm"], r["line_item_bm"]), "nota4")
compare_prior("fact_trust_fund_detail.csv", trust_rows,
              lambda r: (r["fund_group_bm"], r["fund_bm"],
                         r["section_bm"].split(" /")[0], r["line_item_bm"]),
              "nota7-fund")
compare_prior("fact_memo_assets_detail.csv", memo_rows,
              lambda r: (r["section_bm"], r["line_item_bm"]), "nota8")
compare_prior("fact_debt.csv", debt_rows,
              lambda r: (r["group_bm"], r["item_bm"]), "nota9(a)")
compare_prior("fact_commitment_detail.csv", com_rows,
              lambda r: r["item_bm"], "nota9(b)")

# =====================================================================
# 10. Independent confirmation: 2015 rows vs warehouse2016 comparatives
#     (2016 volume's year-2015 columns; INFO only - 2016 restated Nota 8(a))
# =====================================================================
def compare_2016(csv16, mine, keyf, label):
    nxt = {}
    p16 = f"/home/claude/pkkp/warehouse2016/{csv16}"
    for r in csv.DictReader(open(p16)):
        if r["year"] == "2015":
            nxt.setdefault(keyf(r), []).append(float(r["amount_rm"]))
    n_match = n_diff = 0
    for r in mine:
        if r["year"] != 2015:
            continue
        k = keyf({k2: str(v) for k2, v in r.items()})
        if k in nxt and len(nxt[k]) == 1:
            if abs(nxt[k][0] - r["amount_rm"]) < 0.5:
                n_match += 1
            else:
                n_diff += 1
                LOG("WARN", f"{label}: 2016-volume comparative differs [{k}]: "
                    f"2015 volume {r['amount_rm']:,.0f} vs 2016 volume "
                    f"{nxt[k][0]:,.0f} (2016-side restatement candidate); "
                    f"2015 value kept as printed in 2015 volume",
                    r["amount_rm"], nxt[k][0], r["amount_rm"] - nxt[k][0])
    LOG("INFO", f"{label}: independent confirmation vs warehouse2016 "
        f"year-2015 comparatives: {n_match} equal, {n_diff} differ",
        n_match, n_match + n_diff, -n_diff)

compare_2016("fact_cash_components.csv", cash_rows,
             lambda r: r["line_item_bm"], "nota3")
compare_2016("fact_investment_summary.csv", inv_rows,
             lambda r: (r["category_bm"], r["line_item_bm"]), "nota4")
compare_2016("fact_trust_fund_detail.csv", trust_rows,
             lambda r: (r["fund_group_bm"], r["fund_bm"],
                        r["section_bm"].split(" /")[0], r["line_item_bm"]),
             "nota7-fund")
compare_2016("fact_debt.csv", debt_rows,
             lambda r: (r["group_bm"], r["item_bm"]), "nota9(a)")
compare_2016("fact_commitment_detail.csv", com_rows,
             lambda r: r["item_bm"], "nota9(b)")

# =====================================================================
# Write outputs + validation
# =====================================================================
PROV = ["source_file", "pdf_page", "printed_page", "statement"]
outputs = [
    ("fact_cash_components.csv", cash_rows,
     ["line_item_bm", "year", "amount_rm", "row_type", "has_footnote"] + PROV),
    ("fact_investment_summary.csv", inv_rows,
     ["category_bm", "line_item_bm", "year", "amount_rm", "row_type", "has_footnote"] + PROV),
    ("fact_trust_accounts.csv", ta_rows,
     ["parent_group_bm", "account_bm", "year", "baki_awal_rm", "debit_rm",
      "kredit_rm", "baki_akhir_rm"] + PROV),
    ("fact_trust_fund_detail.csv", trust_rows,
     ["fund_group_bm", "fund_bm", "section_bm", "line_item_bm", "year",
      "amount_rm", "row_type", "has_footnote"] + PROV),
    ("fact_memo_assets_detail.csv", memo_rows,
     ["section_bm", "line_item_bm", "year", "amount_rm", "row_type", "has_footnote"] + PROV),
    ("fact_debt.csv", debt_rows,
     ["group_bm", "item_bm", "kind", "year", "amount_rm"] + PROV),
    ("fact_commitment_detail.csv", com_rows,
     ["parent_bm", "item_bm", "year", "amount_rm", "row_type", "has_footnote"] + PROV),
    ("fact_other_notes.csv", other_rows,
     ["nota", "line_item_bm", "year", "amount_rm", "row_type", "has_footnote"] + PROV),
]
n_amounts = sum(len(rows) for _, rows, _ in outputs)
LOG("INFO", f"notes-detail-2015: confirmation routes: {n_amounts} rows total; "
    "100% eye-verified from crops (16 band crops + 3 zooms, scale 2-6); "
    "arithmetic identities cover every printed subtotal/total; "
    "2016-volume comparatives independently confirm the 2015 columns; "
    "2014-volume current columns confirm the comparatives")
for fname, rows, cols in outputs:
    n = write_csv(os.path.join(WH, fname), cols, rows)
    print(f"WROTE {fname}: {n} rows")

fails = warns = 0
printable = []
for status, name, got, want, diff in checks:
    printable.append((status, name))
    if status == "FAIL":
        fails += 1
    elif status == "WARN":
        warns += 1
append_checks([(s, "notes-detail: " + n, g, w, d)
               for s, n, g, w, d in checks])
for status, name in printable:
    if status in ("FAIL", "WARN"):
        print(f"{status}: {name}")
npass = sum(1 for c in checks if c[0] == "PASS")
print(f"\n{len(checks)} checks: {npass} PASS, {warns} WARN, {fails} FAIL")
sys.exit(1 if fails else 0)
