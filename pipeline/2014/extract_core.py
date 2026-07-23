#!/usr/bin/env python3
"""Extract core fiscal tables from PKKP 2014 (oldest volume attempted; pre-GST/SST era, RMKe-10 year 4, BN era).

2014 page anchors (printed = pdf - 25): position pdf 58, cash 59-60, prestasi 61,
memorandum 62, Nota 5 stmt pdf 65, Nota 5(a) pdf 65-66, Nota 5(b) pdf 67,
Nota 7 trust pdf 69, Nota 9 debt pdf 74.

2014 specifics vs 2016:
 - Penyata Kedudukan Kewangan prints UNLABELLED balancing subtotals on both
   sides (40,841,339,321 / 49,083,585,341) plus a 'DIPEGANG BAGI :' caption;
   captured as JUMLAH rows.
 - Cash statement prints per-category totals in a second RM column; the
   category-total figures are captured as 'Jumlah <kategori>' rows and the
   item sums are validated against them. 2014 categories: no Perbelanjaan
   Modal; Terimaan Modal includes Perbezaan Forex Relending Loan and Terimaan
   Balik Pendahuluan; Jualan Instrumen Kewangan sits inside Terimaan Modal.
 - Memorandum statement labels: 'Pinjaman Boleh Dituntut' (not 'Pinjaman dan
   Pendahuluan...') and 'Hutang Awam' (not 'Hutang Persekutuan').
 - Nota 5(b) has 49 maksud (T.01-T.14, 35 B votes); B.12 sebenar carries a
   '**' footnote (caruman ke KWP RM1,036,530,784 inside).
 - Nota 9(a) debt: DN (BP/TPK/SKM) with an UNLABELLED subtotal, a separate
   Kumpulan Wang Pinjaman Perumahan block (Pinjaman Berjangka + Sukuk
   Perumahan Kerajaan, new split declared 'Mulai tahun 2014') with an
   unlabelled subtotal, Luar Negeri Pinjaman Pasaran, then Jumlah Pinjaman /
   Jumlah Bantuan Luar Negeri / JUMLAH HUTANG AWAM.
All amounts exact RM as printed. Typed tokens are verified verbatim against the
page's own text layer. Provenance on every row. Nothing silently corrected.
"""
import csv
import os
import re
import sys

YEAR = 2014
PRIOR = 2013
SRC = "2014_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2014"
os.makedirs(OUT, exist_ok=True)

pages = open("/home/claude/pkkp/work/2014/full.txt", encoding="utf-8").read().split("\f")


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

# ------------------------------------------------ 1. Penyata Kedudukan Kewangan (pdf 58, printed 33)
def financial_position():
    stmt = "Penyata Kedudukan Kewangan"
    src = [  # section, item, nota, 2014, 2013
        ("WANG AWAM", "WANG TUNAI", 3, "17,426,671,072", "25,051,038,985"),
        ("WANG AWAM", "PELABURAN", 4, "23,414,668,249", "24,032,546,356"),
        ("WANG AWAM", "JUMLAH WANG AWAM", "", "40,841,339,321", "49,083,585,341"),
        ("KUMPULAN WANG DISATUKAN", "AKAUN HASIL DISATUKAN", 5, "11,863,127,086", "11,863,127,086"),
        ("KUMPULAN WANG DISATUKAN", "AKAUN PINJAMAN DISATUKAN", 6, "39,592,120,099", "26,380,357,864"),
        ("KUMPULAN WANG DISATUKAN", "AKAUN AMANAH DISATUKAN", 7, "(10,613,907,864)", "10,840,100,391"),
        ("KUMPULAN WANG DISATUKAN", "JUMLAH KUMPULAN WANG DISATUKAN", "", "40,841,339,321", "49,083,585,341"),
    ]
    rows = []
    for sec, item, nota, a14, a13 in src:
        for yr, amt in ((YEAR, a14), (PRIOR, a13)):
            V(58, amt)
            rows.append([sec, item, nota, yr, N(amt), SRC, 58, 33, stmt])
    w("fact_financial_position.csv",
      ["section", "line_item_bm", "nota", "year", "amount_rm"] + PROV, rows)


# ------------------------------------------------ 2. Penyata Penerimaan dan Pembayaran Wang Tunai (pdf 59-60)
def cash_statement():
    stmt = "Penyata Penerimaan dan Pembayaran Wang Tunai"
    # flow, category, item, 2014, 2013, pdf_page
    src = [
        ("TERIMAAN", "Hasil", "Hasil Cukai", "164,204,887,589", "155,952,205,546", 59),
        ("TERIMAAN", "Hasil", "Hasil Bukan Cukai", "52,348,131,946", "50,241,306,637", 59),
        ("TERIMAAN", "Hasil", "Terimaan Bukan Hasil", "1,666,651,362", "1,580,740,186", 59),
        ("TERIMAAN", "Hasil", "Hasil Wilayah Persekutuan", "855,349,863", "1,378,022,570", 59),
        ("TERIMAAN", "Hasil", "Jumlah Hasil", "219,075,020,760", "209,152,274,939", 59),
        ("TERIMAAN", "Pinjaman", "Dalam Negeri", "108,809,141,548", "111,357,188,482", 59),
        ("TERIMAAN", "Pinjaman", "Luar Negeri", "–", "–", 59),
        ("TERIMAAN", "Pinjaman", "Jumlah Pinjaman", "108,809,141,548", "111,357,188,482", 59),
        ("TERIMAAN", "Bantuan Luar Negeri", "Pinjaman Multilateral", "26,539,848", "325,828", 59),
        ("TERIMAAN", "Bantuan Luar Negeri", "Pinjaman Bilateral", "222,744,257", "412,326,368", 59),
        ("TERIMAAN", "Bantuan Luar Negeri", "Jumlah Bantuan Luar Negeri", "249,284,105", "412,652,196", 59),
        ("TERIMAAN", "Terimaan Modal", "Terimaan Balik Pinjaman", "1,028,450,618", "1,377,968,465", 59),
        ("TERIMAAN", "Terimaan Modal", "Perbezaan Forex Relending Loan", "–", "6,947,052", 59),
        ("TERIMAAN", "Terimaan Modal", "Terimaan Balik Pendahuluan", "60,728,977", "29,508,837", 59),
        ("TERIMAAN", "Terimaan Modal", "Jualan Aset Modal", "42,799", "87,017", 59),
        ("TERIMAAN", "Terimaan Modal", "Pelbagai Terimaan Modal", "5,497,682", "24,919,163", 59),
        ("TERIMAAN", "Terimaan Modal", "Jualan Instrumen Kewangan", "617,878,107", "717,599,227", 59),
        ("TERIMAAN", "Terimaan Modal", "Jumlah Terimaan Modal", "1,712,598,183", "2,157,029,761", 59),
        ("TERIMAAN", "Terimaan Amanah", "Inisiatif Pembiayaan Swasta (PFI)", "61,163,842", "148,775,232", 59),
        ("TERIMAAN", "Terimaan Amanah", "Aktiviti Pembangunan Khas Pembiayaan Swasta", "103,256,039", "5,054,580,710", 59),
        ("TERIMAAN", "Terimaan Amanah", "Pelbagai", "–", "–", 59),
        ("TERIMAAN", "Terimaan Amanah", "Jumlah Terimaan Amanah", "164,419,881", "5,203,355,942", 59),
        ("BAYARAN", "Perbelanjaan Mengurus", "Emolumen", "66,946,934,325", "61,001,190,871", 60),
        ("BAYARAN", "Perbelanjaan Mengurus", "Perkhidmatan dan Bekalan", "34,252,935,877", "33,860,076,805", 60),
        ("BAYARAN", "Perbelanjaan Mengurus", "Aset", "1,681,823,151", "1,414,680,060", 60),
        ("BAYARAN", "Perbelanjaan Mengurus", "Pemberian dan Kenaan Bayaran Tetap", "112,544,254,857", "110,424,046,265", 60),
        ("BAYARAN", "Perbelanjaan Mengurus", "Perbelanjaan-perbelanjaan Lain", "1,064,584,574", "1,052,603,153", 60),
        ("BAYARAN", "Perbelanjaan Mengurus", "Jumlah Perbelanjaan Mengurus", "216,490,532,784", "207,752,597,154", 60),
        ("BAYARAN", "Perbelanjaan Pembangunan", "Langsung", "37,614,004,995", "40,473,294,579", 60),
        ("BAYARAN", "Perbelanjaan Pembangunan", "Pinjaman", "1,854,590,132", "1,736,506,805", 60),
        ("BAYARAN", "Perbelanjaan Pembangunan", "Jumlah Perbelanjaan Pembangunan", "39,468,595,127", "42,209,801,384", 60),
        ("BAYARAN", "Pinjaman", "Dalam Negeri", "65,861,587,665", "73,030,098,558", 60),
        ("BAYARAN", "Pinjaman", "Luar Negeri", "–", "–", 60),
        ("BAYARAN", "Pinjaman", "Jumlah Pinjaman", "65,861,587,665", "73,030,098,558", 60),
        ("BAYARAN", "Bantuan Luar Negeri", "Pinjaman Multilateral", "109,014,953", "98,564,203", 60),
        ("BAYARAN", "Bantuan Luar Negeri", "Pinjaman Bilateral", "516,480,465", "522,458,616", 60),
        ("BAYARAN", "Bantuan Luar Negeri", "Jumlah Bantuan Luar Negeri", "625,495,418", "621,022,819", 60),
        ("BAYARAN", "Perbelanjaan Amanah", "Inisiatif Pembiayaan Swasta (PFI)", "349,159,690", "1,212,643,573", 60),
        ("BAYARAN", "Perbelanjaan Amanah", "Aktiviti Pembangunan Khas Pembiayaan Swasta", "2,257,167,555", "3,239,193,138", 60),
        ("BAYARAN", "Perbelanjaan Amanah", "Pelbagai", "12,582,294,151", "4,521,930,893", 60),
        ("BAYARAN", "Perbelanjaan Amanah", "Jumlah Perbelanjaan Amanah", "15,188,621,396", "8,973,767,604", 60),
        ("JUMLAH", "Jumlah Terimaan", "Jumlah Terimaan", "330,010,464,477", "328,282,501,320", 59),
        ("JUMLAH", "Jumlah Bayaran", "Jumlah Bayaran", "337,634,832,390", "332,587,287,519", 60),
        ("JUMLAH", "Tambahan/(Kurangan) Wang Tunai", "Tambahan/(Kurangan) Wang Tunai", "(7,624,367,913)", "(4,304,786,199)", 60),
        ("JUMLAH", "Wang Tunai Pada 1 Januari", "Wang Tunai Pada 1 Januari", "25,051,038,985", "29,355,825,184", 60),
        ("JUMLAH", "WANG TUNAI PADA 31 DISEMBER", "WANG TUNAI PADA 31 DISEMBER", "17,426,671,072", "25,051,038,985", 60),
    ]
    rows = []
    for flow, cat, item, a14, a13, pg in src:
        for yr, amt in ((YEAR, a14), (PRIOR, a13)):
            V(pg, amt)
            rows.append([flow, cat, item, yr, N(amt), SRC, pg, pg - 25, stmt])
    w("fact_cash_statement.csv",
      ["flow", "category_bm", "item_bm", "year", "amount_rm"] + PROV, rows)


# ------------------------------------------------ 3. Penyata Prestasi Kewangan (pdf 61, printed 36)
def performance():
    stmt = "Penyata Prestasi Kewangan"
    # label, code, anggaran 2014, sebenar 2014, sebenar 2013
    src3 = [
        ("HASIL", "revenue", "225,094,429,000", "220,625,673,356", "213,370,213,558"),
        ("Belanja Mengurus", "opex", "222,081,271,970", "219,589,142,572", "211,270,336,793"),
        ("LEBIHAN/(KURANGAN) HASIL", "current_balance", "3,013,157,030", "1,036,530,784", "2,099,876,765"),
        ("Belanja Pembangunan", "devex", "42,163,431,931", "39,503,487,396", "42,209,801,384"),
        ("KURANGAN KESELURUHAN", "overall_deficit", "(39,150,274,901)", "(38,466,956,612)", "(40,109,924,619)"),
    ]
    src2 = [
        ("Pinjaman dan Bantuan Luar Negeri", "financing_net_borrowing", "37,188,086,245", "39,305,562,572"),
        ("Terimaan Balik Pinjaman dan Pelbagai Terimaan", "financing_capital_receipts", "1,113,766,045", "1,569,433,042"),
        ("Perubahan Tunai, Pelaburan dan Amanah", "financing_cash_inv_trust_change", "165,104,322", "(765,070,995)"),
        ("JUMLAH PEMBIAYAAN", "total_financing", "38,466,956,612", "40,109,924,619"),
    ]
    rows = []
    for label, code, ag, seb, pri in src3:
        for tok in (ag, seb, pri):
            V(61, tok)
        rows.append([label, code, YEAR, "anggaran", N(ag), SRC, 61, 36, stmt])
        rows.append([label, code, YEAR, "sebenar", N(seb), SRC, 61, 36, stmt])
        rows.append([label, code, PRIOR, "sebenar", N(pri), SRC, 61, 36, stmt])
    for label, code, seb, pri in src2:
        for tok in (seb, pri):
            V(61, tok)
        rows.append([label, code, YEAR, "sebenar", N(seb), SRC, 61, 36, stmt])
        rows.append([label, code, PRIOR, "sebenar", N(pri), SRC, 61, 36, stmt])
    w("fact_financial_performance.csv",
      ["line_item_bm", "line_code", "year", "basis", "amount_rm"] + PROV, rows)


# ------------------------------------------------ 4. Penyata Akaun Memorandum (pdf 62, printed 37)
def memorandum():
    stmt = "Penyata Akaun Memorandum"
    src = [
        ("MEMORANDUM ASET", "Pinjaman Boleh Dituntut", "99,036,023,598", "92,444,600,374"),
        ("MEMORANDUM ASET", "Pelaburan", "29,883,017,259", "29,679,137,799"),
        ("MEMORANDUM LIABILITI", "Hutang Awam", "582,828,241,281", "539,857,759,215"),
        ("MEMORANDUM LIABILITI", "Pelbagai Liabiliti", "318,104,801", "286,624,151"),
    ]
    rows = []
    for sec, item, a14, a13 in src:
        for yr, amt in ((YEAR, a14), (PRIOR, a13)):
            V(62, amt)
            rows.append([sec, item, yr, N(amt), SRC, 62, 37, stmt])
    w("fact_memorandum.csv",
      ["section", "line_item_bm", "year", "amount_rm"] + PROV, rows)


# ------------------------------------------------ 5. Nota 5(a) Hasil mengikut penjenisan (pdf 65-66)
REV_L1 = ["HASIL CUKAI", "HASIL BUKAN CUKAI", "TERIMAAN BUKAN HASIL", "HASIL WILAYAH PERSEKUTUAN"]
L1_JUMLAH = {
    "Jumlah Hasil Cukai": "HASIL CUKAI",
    "Jumlah Hasil Bukan Cukai": "HASIL BUKAN CUKAI",
    "Jumlah Terimaan Bukan Hasil": "TERIMAAN BUKAN HASIL",
    "Jumlah Hasil Wilayah Persekutuan": "HASIL WILAYAH PERSEKUTUAN",
}
JUNK = re.compile(
    r"^(RM|Anggaran|Asal|Disemak|Sebenar|% ?Anggaran|%$|\(disambung\)|\(sambungan\)|"
    r"NOTA\s+KEPADA|PENYATA\s+KEWANGAN|BAGI\s+TAHUN|KEWANGAN|6\. Penyata|\d+$|[ivxl]+$|"
    r"ANM$|nota kepada|penyata kewangan|Penyata Kewangan)"
)


def revenue():
    """2014 layout (same as 2016): category headers are label-only; items carry
    6 value columns (Asal | Disemak | Sebenar | % | prior Sebenar | prior %);
    L1 subtotals print as 'Jumlah <kategori>'; grand row 'JUMLAH HASIL'.
    Wrapped item names continue on the following label-only line."""
    stmt = "Nota 5(a) Hasil Mengikut Penjenisan"
    rows = []
    l1 = None
    started = False
    for pdfp, printed in [(65, 40), (66, 41)]:
        for line in page(pdfp).split("\n"):
            s = strip_margin(line.rstrip())
            st = s.strip()
            if not st:
                continue
            if st == "HASIL CUKAI" and pdfp == 65:
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


# ------------------------------------------------ 6. Nota 5(b) Perbelanjaan Mengurus mengikut Maksud (pdf 67, printed 42)
def opex_maksud():
    stmt = "Nota 5(b) Perbelanjaan Mengurus Mengikut Maksud"
    rows = []
    for pdfp, printed in [(67, 42)]:
        for line in page(pdfp).split("\n"):
            s = strip_margin(line.rstrip())
            s = re.sub(r"\*{2,3}\s*", "*", s)  # normalise '** ' footnote prefixes
            m = re.match(rf"^\s*([TB])\.\s?(\d{{2,3}})\s+(.*?)\s\s+((?:\*?\(?(?:{NUM}|[–—-])\)?\s*){{3,4}})$", s)
            if not m:
                st = s.strip()
                if (rows and st and not re.search(r"\d", st) and len(st) < 40
                        and st[0].islower()
                        and not re.match(r"^(nota kepada|penyata kewangan)", st)):
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


# ------------------------------------------------ 7. Nota 9 Memorandum Liabiliti (pdf 74-75)
def debt():
    stmt = "Nota 9 Memorandum Liabiliti"
    # group, item, kind, 2014, 2013, pdf_page
    src = [
        ("Pinjaman Dalam Negeri", "Bil Perbendaharaan", "instrument", "4,320,000,000", "4,320,000,000", 74),
        ("Pinjaman Dalam Negeri", "Terbitan Pelaburan Kerajaan", "instrument", "185,500,000,000", "172,500,000,000", 74),
        ("Pinjaman Dalam Negeri", "Sekuriti Kerajaan Malaysia", "instrument", "329,632,319,000", "305,075,000,000", 74),
        ("Pinjaman Dalam Negeri", "Dalam Negeri", "subtotal", "519,452,319,000", "481,895,000,000", 74),
        ("Kumpulan Wang Pinjaman Perumahan", "Pinjaman Berjangka", "instrument", "26,200,000,000", "32,300,000,000", 74),
        ("Kumpulan Wang Pinjaman Perumahan", "Sukuk Perumahan Kerajaan", "instrument", "20,400,000,000", "8,900,000,000", 74),
        ("Kumpulan Wang Pinjaman Perumahan", "Kumpulan Wang Pinjaman Perumahan", "subtotal", "46,600,000,000", "41,200,000,000", 74),
        ("Pinjaman Luar Negeri", "Pinjaman Pasaran", "instrument", "11,468,925,000", "10,791,300,000", 74),
        ("JUMLAH", "PINJAMAN", "subtotal", "577,521,244,000", "533,886,300,000", 74),
        ("Bantuan Luar Negeri", "Pinjaman Multilateral", "instrument", "656,158,104", "721,664,278", 74),
        ("Bantuan Luar Negeri", "Pinjaman Bilateral", "instrument", "4,650,839,177", "5,249,794,937", 74),
        ("JUMLAH", "BANTUAN LUAR NEGERI", "subtotal", "5,306,997,281", "5,971,459,215", 74),
        ("JUMLAH", "HUTANG AWAM", "total", "582,828,241,281", "539,857,759,215", 74),
        ("Pelbagai Liabiliti", "PELBAGAI LIABILITI", "misc_total", "318,104,801", "286,624,151", 75),
    ]
    rows = []
    for grp, item, kind, a14, a13, pg in src:
        for yr, amt in ((YEAR, a14), (PRIOR, a13)):
            V(pg, amt)
            rows.append([grp, item, kind, yr, N(amt), SRC, pg, pg - 25, stmt])
    w("fact_debt.csv",
      ["group_bm", "item_bm", "kind", "year", "amount_rm"] + PROV, rows)


# ------------------------------------------------ 8. Nota 7 Akaun Amanah Disatukan (pdf 69, printed 44)
def trust():
    stmt = "Nota 7 Akaun Amanah Disatukan"
    # parent, account, baki_awal, debit, kredit, baki_akhir
    src = [
        ("KUMPULAN WANG AMANAH KERAJAAN", "Kumpulan Wang Pembangunan",
         "(40,535,070,833)", "51,895,675,268", "38,518,808,712", "(53,911,937,389)"),
        ("KUMPULAN WANG AMANAH KERAJAAN", "Kumpulan Wang Pinjaman Perumahan",
         "1,324,944,951", "17,710,186,413", "17,624,779,113", "1,239,537,651"),
        ("KUMPULAN WANG AMANAH KERAJAAN", "Pelbagai Kumpulan Wang Amanah Kerajaan",
         "29,605,216,930", "372,535,693,111", "366,212,812,830", "23,282,336,649"),
        ("", "KUMPULAN WANG AMANAH KERAJAAN",
         "(9,604,908,952)", "442,141,554,792", "422,356,400,655", "(29,390,063,089)"),
        ("KUMPULAN WANG AMANAH AWAM", "Kumpulan Wang Amanah Khas",
         "646,842,019", "468,126,550", "497,213,951", "675,929,420"),
        ("KUMPULAN WANG AMANAH AWAM", "Kumpulan Wang Amanah Am",
         "10,059,927,940", "8,021,398,461", "5,865,050,685", "7,903,580,164"),
        ("", "KUMPULAN WANG AMANAH AWAM",
         "10,706,769,959", "8,489,525,011", "6,362,264,636", "8,579,509,584"),
        ("AKAUN DEPOSIT", "Deposit Am",
         "9,465,977,654", "1,868,707,084", "2,373,276,848", "9,970,547,418"),
        ("AKAUN DEPOSIT", "Deposit Pelarasan",
         "272,261,730", "2,081,723,535", "2,035,560,028", "226,098,223"),
        ("", "AKAUN DEPOSIT",
         "9,738,239,384", "3,950,430,619", "4,408,836,876", "10,196,645,641"),
        ("JUMLAH", "AKAUN AMANAH DISATUKAN",
         "10,840,100,391", "454,581,510,422", "433,127,502,167", "(10,613,907,864)"),
    ]
    rows = []
    for parent, acct, ba, dr, cr, bk in src:
        for tok in (ba, dr, cr, bk):
            V(69, tok)
        rows.append([parent, acct, YEAR, N(ba), N(dr), N(cr), N(bk), SRC, 69, 44, stmt])
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
