#!/usr/bin/env python3
"""Extract core fiscal tables from PKKP 2016 (oldest volume attempted).

2016 page anchors (printed = pdf - 11): position pdf 56, cash 57-58, prestasi 59,
memorandum 60, Nota 5 stmt pdf 63, Nota 5(a) pdf 63-64, Nota 5(b) pdf 65,
Nota 7 trust pdf 67, Nota 9 debt pdf 71-72.

2016 specifics (BM-only volume, BN-era ministries, GST era, RMKe-11 year 1):
 - Cash statement page 58 is DOUBLE-OVERPRINTED (every glyph run printed twice at
   dx=+80pt) and carries page 57's content as 2-up crop bleed at negative x, so
   the cash statement is TRANSCRIBED with verbatim per-token verification
   against the page text plus full chain validation (validate.py).
 - Memorandum statement prints only 4 lines (PPBD / Pelaburan / Hutang /
   Pelbagai Liabiliti): NO Jumlah Aset/Liabiliti, NO PFI, NO Komitmen Kewangan.
 - Nota numbering: memo aset = Nota 8, memo liabiliti = Nota 9 (2018: 9/10).
 - Nota 9(a) debt includes 'Pinjaman Berjangka Kumpulan Wang Pinjaman
   Perumahan' (nil 2016 / 21.9b 2015 - corporatised into LPPSA in 2016); the
   Dalam Negeri subtotal prints UNLABELLED.
 - Nota 7 KWAK has a Kumpulan Wang Pinjaman Perumahan row (wound up in 2016).
 - Nota 5(a) prints 6 value columns; GST items live; residual Cukai Jualan /
   Perkhidmatan rows carry 2015 comparatives (pre-GST arrears).
 - Nota 5(b) has 50 maksud (T.01-T.14, 36 B votes); names wrap to a following
   line; B.12 sebenar carries a '**' footnote (caruman ke KWP inside).
All amounts exact RM as printed. Typed tokens are verified verbatim against the
page's own text layer. Provenance on every row. Nothing silently corrected.
"""
import csv
import os
import re
import sys

YEAR = 2016
PRIOR = 2015
SRC = "2016_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2016"
os.makedirs(OUT, exist_ok=True)

pages = open("/home/claude/pkkp/work/2016/full.txt", encoding="utf-8").read().split("\f")


def page(n):
    return pages[n - 1]


NUM = r"[\d,]+(?:\.\d+)?"


def parse_amount(tok):
    tok = tok.strip().replace("*", "")
    if tok in {"–", "-", "—", ""}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()").replace(",", "")
    v = float(tok)
    return -v if neg else v


verify_fail = []


def V(pdf_page, s):
    """Verify a typed token appears verbatim on its source page."""
    s = s.strip()
    if s in ("-", "–", ""):
        return
    if s not in page(pdf_page):
        verify_fail.append((pdf_page, s))


def N(s):
    return parse_amount(s)


def strip_margin(s):
    s = re.sub(r"^(\s*)\d{1,3}(\s{3,})", r"\1\2", s)
    s = re.sub(r"(\s{6,})\d{1,3}\s*$", "", s)
    return s


def w(name, header, rows):
    path = os.path.join(OUT, name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        cw = csv.writer(f)
        cw.writerow(header)
        cw.writerows(rows)
    print(f"{name}: {len(rows)} rows")


PROV = ["source_file", "pdf_page", "printed_page", "statement"]

# ------------------------------------------------ 1. Penyata Kedudukan Kewangan (pdf 56, printed 45)
def financial_position():
    stmt = "Penyata Kedudukan Kewangan"
    src = [  # section, item, nota, 2016, 2015
        ("WANG AWAM", "WANG TUNAI", 3, "16,063,461,692", "22,972,548,115"),
        ("WANG AWAM", "PELABURAN", 4, "23,309,872,026", "25,754,372,536"),
        ("KUMPULAN WANG DISATUKAN", "AKAUN HASIL DISATUKAN", 5, "11,863,127,086", "11,863,127,086"),
        ("KUMPULAN WANG DISATUKAN", "AKAUN PINJAMAN DISATUKAN", 6, "20,323,759,248", "28,385,609,134"),
        ("KUMPULAN WANG DISATUKAN", "AKAUN AMANAH DISATUKAN", 7, "7,186,447,384", "8,478,184,431"),
    ]
    rows = []
    for sec, item, nota, a16, a15 in src:
        for yr, amt in ((YEAR, a16), (PRIOR, a15)):
            V(56, amt)
            rows.append([sec, item, nota, yr, N(amt), SRC, 56, 45, stmt])
    w("fact_financial_position.csv",
      ["section", "line_item_bm", "nota", "year", "amount_rm"] + PROV, rows)


# ------------------------------------------------ 2. Penyata Penerimaan dan Pembayaran Wang Tunai (pdf 57-58)
def cash_statement():
    stmt = "Penyata Penerimaan dan Pembayaran Wang Tunai"
    # flow, category, item, 2016, 2015, pdf_page
    src = [
        ("TERIMAAN", "Hasil", "Hasil Cukai", "169,343,339,135", "165,440,651,772", 57),
        ("TERIMAAN", "Hasil", "Hasil Bukan Cukai", "39,802,803,140", "51,466,248,034", 57),
        ("TERIMAAN", "Hasil", "Terimaan Bukan Hasil", "1,914,344,320", "1,289,802,714", 57),
        ("TERIMAAN", "Hasil", "Hasil Wilayah Persekutuan", "958,103,848", "891,552,775", 57),
        ("TERIMAAN", "Pinjaman", "Dalam Negeri", "93,876,452,672", "115,804,279,579", 57),
        ("TERIMAAN", "Pinjaman", "Luar Negeri", "5,837,065,920", "5,303,204,400", 57),
        ("TERIMAAN", "Bantuan Luar Negeri", "Pinjaman Multilateral", "–", "–", 57),
        ("TERIMAAN", "Bantuan Luar Negeri", "Pinjaman Bilateral", "145,355,562", "256,238,110", 57),
        ("TERIMAAN", "Terimaan Modal", "Terimaan Balik Pinjaman", "1,079,107,702", "779,787,608", 57),
        ("TERIMAAN", "Terimaan Modal", "Jualan Aset Modal", "12,105", "14,322", 57),
        ("TERIMAAN", "Terimaan Modal", "Pelbagai Terimaan Modal", "267,459,764", "250,030,850", 57),
        ("TERIMAAN", "Terimaan Modal", "Jualan Instrumen Kewangan", "2,544,500,510", "–", 57),
        ("TERIMAAN", "Terimaan Amanah", "Inisiatif Pembiayaan Swasta", "173,773,202", "56,248,418", 57),
        ("TERIMAAN", "Terimaan Amanah", "Aktiviti Pembangunan Khas Pembiayaan Swasta", "68,906,161", "153,707,965", 57),
        ("TERIMAAN", "Terimaan Amanah", "Pelbagai", "–", "478,238,962", 57),
        ("BAYARAN", "Perbelanjaan Mengurus", "Emolumen", "73,108,357,069", "70,050,168,154", 58),
        ("BAYARAN", "Perbelanjaan Mengurus", "Perkhidmatan dan Bekalan", "30,070,477,311", "36,372,752,985", 58),
        ("BAYARAN", "Perbelanjaan Mengurus", "Aset", "675,652,714", "1,722,703,353", 58),
        ("BAYARAN", "Perbelanjaan Mengurus", "Pemberian dan Kenaan Bayaran Tetap", "103,681,612,764", "106,049,029,982", 58),
        ("BAYARAN", "Perbelanjaan Mengurus", "Perbelanjaan-perbelanjaan Lain", "845,349,913", "849,856,842", 58),
        ("BAYARAN", "Perbelanjaan Pembangunan", "Langsung", "40,052,263,265", "38,596,110,048", 58),
        ("BAYARAN", "Perbelanjaan Pembangunan", "Pinjaman", "1,942,774,432", "2,171,601,619", 58),
        ("BAYARAN", "Pinjaman", "Dalam Negeri", "56,193,846,424", "72,788,110,445", 58),
        ("BAYARAN", "Pinjaman", "Luar Negeri", "4,670,400,000", "4,420,000,000", 58),
        ("BAYARAN", "Bantuan Luar Negeri", "Pinjaman Multilateral", "156,925,423", "127,773,160", 58),
        ("BAYARAN", "Bantuan Luar Negeri", "Pinjaman Bilateral", "320,293,408", "282,391,376", 58),
        ("BAYARAN", "Perbelanjaan Modal", "Pembelian Instrumen Kewangan", "–", "1,864,888,405", 58),
        ("BAYARAN", "Perbelanjaan Amanah", "Inisiatif Pembiayaan Swasta", "989,435,259", "296,283,422", 58),
        ("BAYARAN", "Perbelanjaan Amanah", "Aktiviti Pembangunan Khas Pembiayaan Swasta", "534,914,807", "1,032,458,675", 58),
        ("BAYARAN", "Perbelanjaan Amanah", "Pelbagai", "9,678,007,675", "–", 58),
        ("JUMLAH", "Jumlah Terimaan", "Jumlah Terimaan", "316,011,224,041", "342,170,005,509", 57),
        ("JUMLAH", "Jumlah Bayaran", "Jumlah Bayaran", "322,920,310,464", "336,624,128,466", 58),
        ("JUMLAH", "Tambahan/(Kurangan) Wang Tunai", "Tambahan/(Kurangan) Wang Tunai", "(6,909,086,423)", "5,545,877,043", 58),
        ("JUMLAH", "Wang Tunai Pada 1 Januari", "Wang Tunai Pada 1 Januari", "22,972,548,115", "17,426,671,072", 58),
        ("JUMLAH", "WANG TUNAI PADA 31 DISEMBER", "WANG TUNAI PADA 31 DISEMBER", "16,063,461,692", "22,972,548,115", 58),
    ]
    rows = []
    for flow, cat, item, a16, a15, pg in src:
        for yr, amt in ((YEAR, a16), (PRIOR, a15)):
            V(pg, amt)
            rows.append([flow, cat, item, yr, N(amt), SRC, pg, pg - 11, stmt])
    w("fact_cash_statement.csv",
      ["flow", "category_bm", "item_bm", "year", "amount_rm"] + PROV, rows)


# ------------------------------------------------ 3. Penyata Prestasi Kewangan (pdf 59, printed 48)
def performance():
    stmt = "Penyata Prestasi Kewangan"
    # label, code, anggaran 2016, sebenar 2016, sebenar 2015
    src3 = [
        ("HASIL", "revenue", "212,595,375,000", "212,421,098,894", "219,088,760,826"),
        ("Belanja Mengurus", "opex", "212,300,553,048", "210,172,661,334", "216,997,528,507"),
        ("LEBIHAN/(KURANGAN) HASIL", "current_balance", "294,821,952", "2,248,437,560", "2,091,232,319"),
        ("Belanja Pembangunan", "devex", "45,002,664,316", "41,995,037,697", "40,767,711,667"),
        ("KURANGAN KESELURUHAN", "overall_deficit", "(44,707,842,364)", "(39,746,600,137)", "(38,676,479,348)"),
    ]
    src2 = [
        ("Pinjaman dan Bantuan Luar Negeri", "financing_net_borrowing", "38,517,408,898", "38,042,949,038"),
        ("Terimaan Balik Pinjaman dan Pelbagai Terimaan", "financing_capital_receipts", "1,346,579,571", "1,482,583,087"),
        ("Perubahan Tunai, Pelaburan dan Amanah", "financing_cash_inv_trust_change", "(117,388,332)", "(849,052,777)"),
        ("JUMLAH PEMBIAYAAN", "total_financing", "39,746,600,137", "38,676,479,348"),
    ]
    rows = []
    for label, code, ag, seb, pri in src3:
        for tok in (ag, seb, pri):
            V(59, tok)
        rows.append([label, code, YEAR, "anggaran", N(ag), SRC, 59, 48, stmt])
        rows.append([label, code, YEAR, "sebenar", N(seb), SRC, 59, 48, stmt])
        rows.append([label, code, PRIOR, "sebenar", N(pri), SRC, 59, 48, stmt])
    for label, code, seb, pri in src2:
        for tok in (seb, pri):
            V(59, tok)
        rows.append([label, code, YEAR, "sebenar", N(seb), SRC, 59, 48, stmt])
        rows.append([label, code, PRIOR, "sebenar", N(pri), SRC, 59, 48, stmt])
    w("fact_financial_performance.csv",
      ["line_item_bm", "line_code", "year", "basis", "amount_rm"] + PROV, rows)


# ------------------------------------------------ 4. Penyata Akaun Memorandum (pdf 60, printed 49)
def memorandum():
    stmt = "Penyata Akaun Memorandum"
    src = [
        ("MEMORANDUM ASET", "Pinjaman dan Pendahuluan Boleh Dituntut", "55,813,494,515", "106,821,651,022"),
        ("MEMORANDUM ASET", "Pelaburan", "30,926,284,939", "30,316,159,989"),
        ("MEMORANDUM LIABILITI", "Hutang Persekutuan", "648,475,304,686", "630,540,436,110"),
        ("MEMORANDUM LIABILITI", "Pelbagai Liabiliti", "765,004,321", "710,116,666"),
    ]
    rows = []
    for sec, item, a16, a15 in src:
        for yr, amt in ((YEAR, a16), (PRIOR, a15)):
            V(60, amt)
            rows.append([sec, item, yr, N(amt), SRC, 60, 49, stmt])
    w("fact_memorandum.csv",
      ["section", "line_item_bm", "year", "amount_rm"] + PROV, rows)


# ------------------------------------------------ 5. Nota 5(a) Hasil mengikut penjenisan (pdf 63-64)
REV_L1 = ["HASIL CUKAI", "HASIL BUKAN CUKAI", "TERIMAAN BUKAN HASIL", "HASIL WILAYAH PERSEKUTUAN"]
L1_JUMLAH = {
    "Jumlah Hasil Cukai": "HASIL CUKAI",
    "Jumlah Hasil Bukan Cukai": "HASIL BUKAN CUKAI",
    "Jumlah Terimaan Bukan Hasil": "TERIMAAN BUKAN HASIL",
    "Jumlah Hasil Wilayah Persekutuan": "HASIL WILAYAH PERSEKUTUAN",
}
JUNK = re.compile(
    r"^(RM|Anggaran|Asal|Disemak|Sebenar|% ?Anggaran|%$|\(disambung\)|\(sambungan\)|"
    r"NOTA\s+KEPADA|PENYATA\s+KEWANGAN|BAGI\s+TAHUN|KEWANGAN|5\. Penyata|\$10|\d+$|[ivxl]+$)"
)


def revenue():
    """2016 layout: category headers are label-only; items carry 6 value
    columns (Asal | Disemak | Sebenar | % | prior Sebenar | prior %); L1
    subtotals print as 'Jumlah <kategori>'; grand row 'JUMLAH HASIL'.
    Wrapped item names continue on the following label-only line."""
    stmt = "Nota 5(a) Hasil Mengikut Penjenisan"
    rows = []
    l1 = None
    started = False
    for pdfp, printed in [(63, 52), (64, 53)]:
        for line in page(pdfp).split("\n"):
            s = strip_margin(line.rstrip())
            st = s.strip()
            if not st:
                continue
            if st == "HASIL CUKAI" and pdfp == 63:
                started = True
            if not started:
                continue
            if "(b) Perbelanjaan Mengurus" in st:
                started = False
                break
            if st in REV_L1:
                l1 = st
                continue
            m = re.match(rf"^(.*?)\s\s+((?:\*?\(?(?:{NUM}|[–—-])\)?\s+){{3,5}}\*?\(?(?:{NUM}|[–—-])\)?)\s*$", s)
            if not m:
                if (rows and not re.search(r"[\d%]", st) and len(st) < 60
                        and not JUNK.match(st) and st not in REV_L1):
                    rows[-1][3] = rows[-1][3] + " " + st
                continue
            label = m.group(1).strip()
            if not label or JUNK.match(label):
                continue
            toks = re.findall(rf"\*?\(?(?:{NUM}|[–—-])\)?", m.group(2))
            nums = [parse_amount(x) for x in toks]
            if len(nums) == 6:
                a_asal, a_disemak, sebenar, pct, pri, pct_pri = nums
            elif len(nums) == 4:
                a_asal, a_disemak, sebenar, pri = nums
                pct = pct_pri = None
            else:
                continue
            if label == "JUMLAH HASIL":
                rows.append([0, None, None, "HASIL", YEAR, a_asal, a_disemak, sebenar, pct, pri, pct_pri, SRC, pdfp, printed, stmt])
            elif label in L1_JUMLAH:
                cat = L1_JUMLAH[label]
                rows.append([1, cat, None, cat, YEAR, a_asal, a_disemak, sebenar, pct, pri, pct_pri, SRC, pdfp, printed, stmt])
            else:
                rows.append([3, l1, None, label, YEAR, a_asal, a_disemak, sebenar, pct, pri, pct_pri, SRC, pdfp, printed, stmt])
    w("fact_revenue.csv",
      ["level", "category_l1_bm", "category_l2_bm", "item_bm", "year",
       "anggaran_asal_rm", "anggaran_disemak_rm", "sebenar_rm", "pct_anggaran",
       "sebenar_prior_rm", "pct_anggaran_prior"] + PROV, rows)


# ------------------------------------------------ 6. Nota 5(b) Perbelanjaan Mengurus mengikut Maksud (pdf 65, printed 54)
def opex_maksud():
    stmt = "Nota 5(b) Perbelanjaan Mengurus Mengikut Maksud"
    rows = []
    for pdfp, printed in [(65, 54)]:
        for line in page(pdfp).split("\n"):
            s = strip_margin(line.rstrip())
            s = re.sub(r"\*{2,3}\s*", "*", s)  # normalise '** ' footnote prefixes
            m = re.match(rf"^\s*([TB])\.\s?(\d{{2,3}})\s+(.*?)\s\s+((?:\*?\(?(?:{NUM}|[–—-])\)?\s*){{3,4}})$", s)
            if not m:
                st = s.strip()
                if (rows and st and not re.search(r"\d", st) and len(st) < 40
                        and st[0].islower()):
                    rows[-1][2] = rows[-1][2] + " " + st  # wrapped maksud name
                continue
            kind, code, name, numstr = m.groups()
            raw = re.findall(rf"\*?\(?(?:{NUM}|[–—-])\)?", numstr)
            flagged = any("*" in x for x in raw)
            nums = [parse_amount(x) for x in raw]
            if len(nums) == 4:
                asal, dipinda, sebenar, pct = nums
            else:
                asal, dipinda, sebenar = nums
                pct = None
            rows.append([f"{kind}.{code}", "Tanggungan" if kind == "T" else "Bekalan", name.strip(),
                         YEAR, asal, dipinda, sebenar, pct, flagged, SRC, pdfp, printed, stmt])
    w("fact_opex_maksud.csv",
      ["maksud_code", "jenis_bm", "maksud_name_bm", "year",
       "anggaran_asal_rm", "anggaran_dipinda_rm", "sebenar_rm", "pct_anggaran", "has_footnote"] + PROV, rows)


# ------------------------------------------------ 7. Nota 9 Memorandum Liabiliti (pdf 71-72)
def debt():
    stmt = "Nota 9 Memorandum Liabiliti"
    # group, item, kind, 2016, 2015, pdf_page
    src = [
        ("Pinjaman Dalam Negeri", "Bil Perbendaharaan", "instrument", "4,500,000,000", "4,700,000,000", 71),
        ("Pinjaman Dalam Negeri", "Terbitan Pelaburan Kerajaan", "instrument", "234,500,000,000", "214,000,000,000", 71),
        ("Pinjaman Dalam Negeri", "Sekuriti Kerajaan Malaysia", "instrument", "357,421,726,000", "340,062,879,000", 71),
        ("Pinjaman Dalam Negeri", "Sukuk", "instrument", "28,400,000,000", "28,400,000,000", 71),
        ("Pinjaman Dalam Negeri", "Pinjaman Berjangka Kumpulan Wang Pinjaman Perumahan", "instrument", "–", "21,900,000,000", 71),
        ("Pinjaman Dalam Negeri", "Dalam Negeri", "subtotal", "624,821,726,000", "609,062,879,000", 71),
        ("Pinjaman Luar Negeri", "Pinjaman Pasaran", "instrument", "17,211,340,000", "15,179,150,000", 71),
        ("JUMLAH", "PINJAMAN", "subtotal", "642,033,066,000", "624,242,029,000", 71),
        ("Bantuan Luar Negeri", "Pinjaman Multilateral", "instrument", "498,540,786", "647,112,909", 71),
        ("Bantuan Luar Negeri", "Pinjaman Bilateral", "instrument", "5,943,697,900", "5,651,294,201", 71),
        ("JUMLAH", "BANTUAN LUAR NEGERI", "subtotal", "6,442,238,686", "6,298,407,110", 71),
        ("JUMLAH", "HUTANG PERSEKUTUAN", "total", "648,475,304,686", "630,540,436,110", 71),
        ("Pelbagai Liabiliti", "PELBAGAI LIABILITI", "misc_total", "765,004,321", "710,116,666", 72),
    ]
    rows = []
    for grp, item, kind, a16, a15, pg in src:
        for yr, amt in ((YEAR, a16), (PRIOR, a15)):
            V(pg, amt)
            rows.append([grp, item, kind, yr, N(amt), SRC, pg, pg - 11, stmt])
    w("fact_debt.csv",
      ["group_bm", "item_bm", "kind", "year", "amount_rm"] + PROV, rows)


# ------------------------------------------------ 8. Nota 7 Akaun Amanah Disatukan (pdf 67, printed 56)
def trust():
    stmt = "Nota 7 Akaun Amanah Disatukan"
    # parent, account, baki_awal, debit, kredit, baki_akhir
    src = [
        ("KUMPULAN WANG AMANAH KERAJAAN", "Kumpulan Wang Pembangunan",
         "(41,856,373,646)", "42,006,710,486", "50,185,948,705", "(33,677,135,427)"),
        ("KUMPULAN WANG AMANAH KERAJAAN", "Kumpulan Wang Pinjaman Perumahan",
         "1,784,376,301", "100,356,583,921", "98,572,207,620", "–"),
        ("KUMPULAN WANG AMANAH KERAJAAN", "Pelbagai Kumpulan Wang Amanah Kerajaan",
         "29,980,191,463", "403,648,169,547", "396,759,784,936", "23,091,806,852"),
        ("", "KUMPULAN WANG AMANAH KERAJAAN",
         "(10,091,805,882)", "546,011,463,954", "545,517,941,261", "(10,585,328,575)"),
        ("KUMPULAN WANG AMANAH AWAM", "Kumpulan Wang Amanah Khas",
         "2,705,924,586", "625,410,049", "787,422,457", "2,867,936,994"),
        ("KUMPULAN WANG AMANAH AWAM", "Kumpulan Wang Amanah Am",
         "6,750,503,372", "3,743,525,341", "2,345,696,936", "5,352,674,967"),
        ("", "KUMPULAN WANG AMANAH AWAM",
         "9,456,427,958", "4,368,935,390", "3,133,119,393", "8,220,611,961"),
        ("AKAUN DEPOSIT", "Deposit Am",
         "8,650,254,768", "1,776,487,751", "2,014,873,398", "8,888,640,415"),
        ("AKAUN DEPOSIT", "Deposit Pelarasan",
         "463,307,587", "2,089,627,794", "2,288,843,790", "662,523,583"),
        ("", "AKAUN DEPOSIT",
         "9,113,562,355", "3,866,115,545", "4,303,717,188", "9,551,163,998"),
        ("JUMLAH", "AKAUN AMANAH DISATUKAN",
         "8,478,184,431", "554,246,514,889", "552,954,777,842", "7,186,447,384"),
    ]
    rows = []
    for parent, acct, ba, dr, cr, bk in src:
        for tok in (ba, dr, cr, bk):
            V(67, tok)
        rows.append([parent, acct, YEAR, N(ba), N(dr), N(cr), N(bk), SRC, 67, 56, stmt])
    w("fact_trust_accounts.csv",
      ["parent_group_bm", "account_bm", "year", "baki_awal_rm", "debit_rm", "kredit_rm", "baki_akhir_rm"] + PROV, rows)


financial_position()
cash_statement()
performance()
memorandum()
revenue()
opex_maksud()
debt()
trust()

if verify_fail:
    print("RAW-TEXT VERIFICATION FAILURES:")
    for pg, s in verify_fail:
        print(f"  pdf_page {pg}: {s!r}")
    sys.exit(1)
print("core: all typed tokens verified verbatim on their source pages")
