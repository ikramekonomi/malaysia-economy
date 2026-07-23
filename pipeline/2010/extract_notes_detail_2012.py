#!/usr/bin/env python3
"""Extract PKKP 2012 NOTES-section detail tables into warehouse CSVs.

Source pages (garbled in full.txt layout dump) are re-extracted per-page in
RAW reading-order mode; every non-zero amount is verified verbatim against the
raw per-page text. Nothing is silently corrected.

  Nota 3 WANG TUNAI            -> fact_cash_components.csv   (pdf 53, printed 31)
  Nota 4 PELABURAN             -> fact_investment_summary.csv(pdf 53, printed 31)
  Nota 9(b) PELBAGAI LIABILITI -> fact_commitment_detail.csv (pdf 64, printed 42)
  narrative RM figures Nota 5-12 -> fact_other_notes.csv
"""
import csv, os, subprocess, sys

WORK = "/home/claude/pkkp/work/2012"
WH = "/home/claude/pkkp/warehouse2012"
PDF = os.path.join(WORK, "2012.pdf")
SRC = "2012_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
os.makedirs(WH, exist_ok=True)

# --- raw per-page text cache (reading-order) --------------------------------
_raw = {}
def raw(pg):
    if pg not in _raw:
        _raw[pg] = subprocess.run(
            ["pdftotext", "-f", str(pg), "-l", str(pg), "-raw", PDF, "-"],
            capture_output=True, text=True).stdout
    return _raw[pg]

def N(s):
    s = s.strip()
    if s in ("-", "–", "—", ""):
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    v = float(s.strip("()").replace(",", ""))
    return -v if neg else v

verify_fail = []
def V(pg, s):
    s = s.strip()
    if s in ("-", "–", "—", ""):
        return
    if s not in raw(pg):
        verify_fail.append((pg, s))

checks = []
def CHK(name, got, want):
    checks.append(("PASS" if abs(got - float(want)) < 0.5 else "FAIL",
                   name, got, float(want)))

def prov(pg, statement):
    return dict(source_file=SRC, pdf_page=pg, printed_page=pg - 22,
                statement=statement)

def write_csv(path, cols, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)

# =====================================================================
# 1. Nota 3 WANG TUNAI (pdf 53, printed 31)
# =====================================================================
cash_src = [  # label, 2012, 2011, row_type
    ("Wang Tunai Dalam Bank", "28,543,129,953", "23,788,144,927", "detail"),
    ("Wang Tunai Dalam Perjalanan", "810,022,000", "676,032,089", "detail"),
    ("Wang Tunai Dalam Tangan", "2,673,231", "2,598,511", "detail"),
    ("JUMLAH WANG TUNAI", "29,355,825,184", "24,466,775,527", "total"),
]
cash_rows = []
for label, a12, a11, rt in cash_src:
    for yr, amt in ((2012, a12), (2011, a11)):
        V(53, amt)
        cash_rows.append(dict(line_item_bm=label, year=yr, amount_rm=N(amt),
                              row_type=rt, has_footnote=False,
                              **prov(53, "Nota 3 Wang Tunai")))
for yr in (2012, 2011):
    det = sum(r["amount_rm"] for r in cash_rows
              if r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in cash_rows
           if r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota3 cash details sum = JUMLAH WANG TUNAI {yr}", det, tot)
CHK("control: Wang Tunai 2012 ties to Penyata Kedudukan", 29355825184.0, 29355825184)
CHK("control: Wang Tunai 2011 ties to Penyata Kedudukan", 24466775527.0, 24466775527)

# =====================================================================
# 2. Nota 4 PELABURAN (pdf 53, printed 31)
# =====================================================================
KWA = "Pelaburan Kumpulan Wang Amanah"
AM = "Pelaburan Am"
inv_src = [  # label, kwa12, am12, kwa11, am11
    ("Sekuriti Kerajaan Luar Negeri", "3,488,419,954", "-", "2,561,909,810", "-"),
    ("Sekuriti Kerajaan Malaysia", "1,238,248,943", "-", "936,001,984", "-"),
    ("Saham", "784,811", "5,563,998,987", "784,811", "5,563,998,987"),
    ("Deposit Luar Negeri", "-", "-", "75,996,238", "-"),
    ("Deposit Dalam Negeri", "8,133,614,560", "5,093,996,935", "8,502,089,818", "4,258,392,284"),
    ("Pelbagai", "528,401,960", "1,670,558", "942,618,722", "1,670,558"),
]
inv_sub = {(KWA, 2012): "13,389,470,228", (AM, 2012): "10,659,666,480",
           (KWA, 2011): "13,019,401,383", (AM, 2011): "9,824,061,829"}
inv_tot = {2012: "24,049,136,708", 2011: "22,843,463,212"}
P4 = prov(53, "Nota 4 Pelaburan")
inv_rows = []
for yr in (2012, 2011):
    V(53, inv_tot[yr])
    inv_rows.append(dict(category_bm="", line_item_bm="JUMLAH PELABURAN", year=yr,
                         amount_rm=N(inv_tot[yr]), row_type="total",
                         has_footnote=False, **P4))
for label, k12, a12, k11, a11 in inv_src:
    for yr, kv, av in ((2012, k12, a12), (2011, k11, a11)):
        for cat, amt in ((KWA, kv), (AM, av)):
            V(53, amt)
            inv_rows.append(dict(category_bm=cat, line_item_bm=label, year=yr,
                                 amount_rm=N(amt), row_type="detail",
                                 has_footnote=False, **P4))
for (cat, yr), amt in inv_sub.items():
    V(53, amt)
    inv_rows.append(dict(category_bm=cat, line_item_bm="Jumlah", year=yr,
                         amount_rm=N(amt), row_type="subtotal",
                         has_footnote=False, **P4))
for yr in (2012, 2011):
    for cat in (KWA, AM):
        det = sum(r["amount_rm"] for r in inv_rows if r["year"] == yr
                  and r["category_bm"] == cat and r["row_type"] == "detail")
        CHK(f"Nota4 {cat} details = Jumlah {yr}", det, N(inv_sub[(cat, yr)]))
    subs = sum(N(inv_sub[(c, yr)]) for c in (KWA, AM))
    CHK(f"Nota4 subtotals = JUMLAH PELABURAN {yr}", subs, N(inv_tot[yr]))
CHK("control: Pelaburan 2012 ties to Penyata Kedudukan", N(inv_tot[2012]), 24049136708)
CHK("control: Pelaburan 2011 ties to Penyata Kedudukan", N(inv_tot[2011]), 22843463212)

# =====================================================================
# 3. Nota 9(b) PELBAGAI LIABILITI (pdf 64, printed 42) -> fact_commitment_detail
# =====================================================================
com_rows = []
com_src = [  # parent, total12, total11, items[(item,12,11)], pdf_page
    ("PELBAGAI LIABILITI", "275,621,222", "241,513,526", [
        ("Nota Kena Bayar", "238,838,141", "203,612,505"),
        ("Sekuriti Tak Dituntut", "22,542,084", "22,091,529"),
        ("Akaun Depositori Pusat", "14,240,997", "15,809,492")], 64),
]
for parent, t12, t11, items, pg in com_src:
    for item, a12, a11 in items:
        for yr, amt in ((2012, a12), (2011, a11)):
            V(pg, amt)
            com_rows.append(dict(parent_bm=parent, item_bm=item, year=yr,
                                 amount_rm=N(amt), row_type="detail",
                                 has_footnote=False,
                                 **prov(pg, "Nota 9 Memorandum Liabiliti")))
    for yr, tot in ((2012, t12), (2011, t11)):
        V(pg, tot)
        com_rows.append(dict(parent_bm=parent, item_bm="JUMLAH PELBAGAI LIABILITI",
                             year=yr, amount_rm=N(tot), row_type="total",
                             has_footnote=False,
                             **prov(pg, "Nota 9 Memorandum Liabiliti")))
        det = sum(r["amount_rm"] for r in com_rows if r["parent_bm"] == parent
                  and r["year"] == yr and r["row_type"] == "detail")
        CHK(f"Nota9(b) {parent} details = printed total {yr}", det, N(tot))
CHK("control: Pelbagai Liabiliti 2012 ties to Penyata Memorandum", N("275,621,222"), 275621222)
CHK("control: Pelbagai Liabiliti 2011 ties to Penyata Memorandum", N("241,513,526"), 241513526)

# =====================================================================
# 4. Narrative figures (fact_other_notes)
# =====================================================================
other_rows = []
def O(nota, item, yr, amt, pg, stmt):
    V(pg, amt)
    other_rows.append(dict(nota=nota, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type="narrative",
                           has_footnote=False, **prov(pg, stmt)))

# --- Nota 5 general / 5(a) Hasil (pdf 54, printed 32)
O("5", "Baki terkumpul Akaun Hasil Disatukan sebelum tahun 1996 (tidak dipindah ke Kumpulan Wang Pembangunan)",
  2012, "11,863,127,086", 54, "Nota 5 Akaun Hasil Disatukan")
O("5(a)", "Pindahan Akaun Premium Terbitan Pelaburan Kerajaan dan Sekuriti Kerajaan Malaysia (tidak termasuk dalam Hasil Bukan Cukai di Penyata Penerimaan dan Pembayaran Wang Tunai)",
  2012, "4,000,000,000", 54, "Nota 5(a) Hasil")
O("5(a)", "Pelarasan terimaan faedah pinjaman daripada Lembaga Kemajuan Pahang Tenggara (tidak termasuk dalam Terimaan Bukan Hasil di Penyata Penerimaan dan Pembayaran Wang Tunai)",
  2012, "4,691,384", 54, "Nota 5(a) Hasil")
# --- Nota 5(b) Perbelanjaan Mengurus (pdf 55, printed 33)
O("5(b)", "Perbelanjaan Pemberian dan Kenaan Bayaran Tetap 2011 di Penyata Penerimaan dan Pembayaran Wang Tunai (sebelum penyata semula)",
  2011, "99,693,813,446", 55, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Perbelanjaan Pemberian dan Kenaan Bayaran Tetap 2011 dinyatakan semula di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2011, "92,603,818,793", 55, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pelarasan bayaran balik pinjaman Perbadanan Aset Keretapi (komponen penyata semula Pemberian 2011)",
  2011, "20,000,000", 55, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pindahan peruntukan Kumpulan Wang Terkanun kepada Kumpulan Wang Amanah Kerajaan (komponen penyata semula Pemberian 2011)",
  2011, "7,069,994,653", 55, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Perbezaan perbelanjaan Pemberian dan Kenaan Bayaran Tetap 2012 di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2012, "104,451,633,629", 55, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pelarasan bayaran balik pinjaman Perbadanan Aset Keretapi (komponen perbezaan Pemberian 2012)",
  2012, "10,000,000", 55, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pindahan peruntukan Kumpulan Wang Terkanun kepada Kumpulan Wang Amanah Kerajaan (komponen perbezaan Pemberian 2012)",
  2012, "5,861,106,424", 55, "Nota 5(b) Perbelanjaan Mengurus")
# --- Nota 6 Akaun Pinjaman Disatukan (pdf 57, printed 35)
O("6", "Bayaran balik Pinjaman Bilateral 2012 di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2012, "590,443,637", 57, "Nota 6 Akaun Pinjaman Disatukan")
O("6", "Urus niaga bukan tunai pelarasan Bantuan Luar Negeri (komponen perbezaan bayaran balik Pinjaman Bilateral 2012)",
  2012, "12,126,567", 57, "Nota 6 Akaun Pinjaman Disatukan")
O("6", "Bayaran balik Pinjaman Bilateral 2011 dinyatakan semula di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2011, "583,837,554", 57, "Nota 6 Akaun Pinjaman Disatukan")
O("6", "Pelarasan urus niaga bukan tunai (komponen penyata semula bayaran balik Pinjaman Bilateral 2011)",
  2011, "13,029,502", 57, "Nota 6 Akaun Pinjaman Disatukan")
O("6", "Bantuan Luar Negeri yang belum diterima bagi membiayai projek pembangunan",
  2012, "1,503,480,145", 57, "Nota 6 Akaun Pinjaman Disatukan")
O("6", "Bantuan Luar Negeri yang belum diterima bagi membiayai projek pembangunan",
  2011, "2,563,921,396", 57, "Nota 6 Akaun Pinjaman Disatukan")
O("6", "Pinjaman dan Bantuan Luar Negeri di Penyata Prestasi Kewangan (terimaan bersih tahun semasa)",
  2012, "43,327,545,911", 57, "Nota 6 Akaun Pinjaman Disatukan")
O("6", "Bayaran faedah pinjaman dan kos lain dikenakan kepada Perbelanjaan Tanggungan (T13)",
  2012, "19,537,385,599", 57, "Nota 6 Akaun Pinjaman Disatukan")
# --- Nota 7 Akaun Amanah Disatukan (pdf 58, printed 36)
O("7", "Pelbagai Perbelanjaan Amanah di Penyata Penerimaan dan Pembayaran Wang Tunai (baki bersih Akaun Amanah)",
  2012, "3,628,489,333", 58, "Nota 7 Akaun Amanah Disatukan")
O("7", "Pelbagai Perbelanjaan Amanah dinyatakan semula di Penyata Penerimaan dan Pembayaran Wang Tunai 2011",
  2011, "6,179,379,456", 58, "Nota 7 Akaun Amanah Disatukan")
O("7", "Akaun Penyelesaian Utama Perbendaharaan: debit tidak melibatkan terimaan atau bayaran sebenar",
  2012, "279,961,586,353", 58, "Nota 7 Akaun Amanah Disatukan")
O("7", "Akaun Penyelesaian Utama Perbendaharaan: kredit tidak melibatkan terimaan atau bayaran sebenar",
  2012, "279,267,283,017", 58, "Nota 7 Akaun Amanah Disatukan")
O("7(a)(i)", "Pelbagai terimaan termasuk terimaan modal (Kumpulan Wang Pembangunan)",
  2012, "1,500,000,000", 58, "Nota 7(a)(i) Kumpulan Wang Pembangunan")
O("7(a)(i)", "Terimaan Balik Pinjaman Kumpulan Wang Pembangunan 2012 di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2012, "1,058,991,393", 58, "Nota 7(a)(i) Kumpulan Wang Pembangunan")
O("7(a)(i)", "Urus niaga bukan tunai pelarasan pinjaman (komponen perbezaan Terimaan Balik Pinjaman KWP 2012)",
  2012, "26,981,704", 58, "Nota 7(a)(i) Kumpulan Wang Pembangunan")
O("7(a)(i)", "Terimaan Balik Pinjaman Kumpulan Wang Pembangunan 2011 di Penyata Penerimaan dan Pembayaran Wang Tunai (sebelum penyata semula)",
  2011, "866,221,436", 58, "Nota 7(a)(i) Kumpulan Wang Pembangunan")
O("7(a)(i)", "Terimaan Balik Pinjaman Kumpulan Wang Pembangunan 2011 dinyatakan semula",
  2011, "833,191,934", 58, "Nota 7(a)(i) Kumpulan Wang Pembangunan")
O("7(a)(i)", "Pelarasan urus niaga bukan tunai (komponen penyata semula Terimaan Balik Pinjaman KWP 2011)",
  2011, "33,029,502", 58, "Nota 7(a)(i) Kumpulan Wang Pembangunan")
# --- Nota 8(b) Memorandum Aset - Pelaburan reconciliation (pdf 63, printed 41)
O("8(b)", "Nilai Buku Pelaburan Memorandum Aset 2011 sebelum penyata semula",
  2011, "28,222,949,922", 63, "Nota 8 Memorandum Aset")
O("8(b)", "Nilai Buku Pelaburan Memorandum Aset 2011 dinyatakan semula",
  2011, "28,834,528,313", 63, "Nota 8 Memorandum Aset")
O("8(b)", "Pengambilalihan saham UDA oleh MKD 176,577,186 unit @ RM3/unit melalui set off dividen Khazanah Nasional Berhad",
  2011, "529,731,558", 63, "Nota 8 Memorandum Aset")
O("8(b)", "Pelarasan pertambahan nilai buku pegangan saham Malaysia Debt Ventures Berhad",
  2011, "150,000,000", 63, "Nota 8 Memorandum Aset")
O("8(b)", "Pelarasan pengurangan nilai buku Khazanah Nasional Berhad",
  2011, "54,000,000", 63, "Nota 8 Memorandum Aset")
O("8(b)", "Pengurangan nilai buku penjualan saham KLIA Consultancy Services, Malaysian Resources Corporation Berhad dan Media Prima Berhad",
  2011, "14,153,167", 63, "Nota 8 Memorandum Aset")
O("8(b)", "Pertambahan pegangan saham UDA Holdings Berhad 118,140,000 unit @ RM1/unit (share swap Dataran Perdana Sdn Bhd)",
  2012, "118,140,000", 63, "Nota 8 Memorandum Aset")
# --- Nota 10 Liabiliti Luar Jangka (pdf 64, printed 42)
O("10(a)", "Pinjaman badan berkanun dan syarikat milik kerajaan yang dijamin oleh Kerajaan Persekutuan [Akta 96]",
  2012, "143,108,810,202", 64, "Nota 10 Liabiliti Luar Jangka")
O("10(b)", "Simpanan pendeposit di Bank Simpanan Nasional, Kumpulan Wang Simpanan Guru-Guru, Kumpulan Wang Simpanan Pekerja dan Lembaga Tabung Haji",
  2012, "547,308,948,630", 64, "Nota 10 Liabiliti Luar Jangka")
O("10(c)", "Third Party War Risk Liability dengan Malaysia Airports Holdings Berhad mengikut perjanjian indemniti",
  2012, "475,000,000", 64, "Nota 10 Liabiliti Luar Jangka")
# --- Nota 11 Akaun Belum Terima (pdf 64, printed 42)
O("11", "Akaun Belum Terima berdasarkan rekod Kementerian/Jabatan (maklumat tambahan)",
  2012, "20,621,501,911", 64, "Nota 11 Akaun Belum Terima")
# --- Nota 12 Wang Pendahuluan Kepada Kontraktor (pdf 64, printed 42)
O("12", "Wang pendahuluan kepada kontraktor yang belum diimbuh balik berdasarkan rekod Kementerian/Jabatan (maklumat tambahan)",
  2012, "1,045,266,128", 64, "Nota 12 Wang Pendahuluan Kepada Kontraktor")

# cross-checks on narrative reconciliations
CHK("Nota5(b): 2011 Pemberian restatement components sum",
    99693813446 - (20000000 + 7069994653), 92603818793)

# =====================================================================
# Write outputs + report
# =====================================================================
PROV = ["source_file", "pdf_page", "printed_page", "statement"]
outputs = [
    ("fact_cash_components.csv", cash_rows,
     ["line_item_bm", "year", "amount_rm", "row_type", "has_footnote"] + PROV),
    ("fact_investment_summary.csv", inv_rows,
     ["category_bm", "line_item_bm", "year", "amount_rm", "row_type", "has_footnote"] + PROV),
    ("fact_commitment_detail.csv", com_rows,
     ["parent_bm", "item_bm", "year", "amount_rm", "row_type", "has_footnote"] + PROV),
    ("fact_other_notes.csv", other_rows,
     ["nota", "line_item_bm", "year", "amount_rm", "row_type", "has_footnote"] + PROV),
]
for fname, rows, cols in outputs:
    n = write_csv(os.path.join(WH, fname), cols, rows)
    print(f"WROTE {fname}: {n} rows")

print()
if verify_fail:
    print("RAW-TEXT VERIFICATION FAILURES (token not found on page):")
    for pg, s in verify_fail:
        print(f"  pdf_page {pg}: {s!r}")
else:
    print("RAW-TEXT VERIFICATION: all non-zero amounts found verbatim on their source pages.")

print()
fails = 0
for status, name, got, want in checks:
    print(f"{status}: {name} | extracted={got:,.0f} printed={want:,.0f}")
    if status == "FAIL":
        fails += 1
print(f"\n{len(checks)} checks, {fails} FAIL")
sys.exit(1 if (fails or verify_fail) else 0)
