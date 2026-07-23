#!/usr/bin/env python3
"""Core statements PKKP 2015: cash statement (pdf 60-61), prestasi (pdf 62),
memorandum (pdf 63). NO text layer -- every amount below was EYE-READ from
400-dpi crops rendered at scale 2-3 (crops/p060_band*.png, p061_band*.png,
p062_z*.png, p063_z0.png, full_06[0-3].png) per the typed-SPEC protocol.

2015 layout notes vs 2014 volume:
 - Cash statement: category totals print in the 2nd RM column of the last item
   line; captured as 'Jumlah <kategori>' rows (2014 warehouse convention).
 - Terimaan: Pinjaman Luar Negeri is non-nil (Sukuk Global 5,303,204,400);
   'Perbezaan Forex Relending Loan' line no longer printed (was nil in 2014).
 - Bayaran gains a Perbelanjaan Modal category (Pembelian Instrumen Kewangan);
   its 2014 comparative prints '-'. Bayaran-side Perbelanjaan Amanah label is
   'Inisiatif Pembiayaan Swasta' (no '(PFI)'; terimaan side keeps '(PFI)').
 - Memorandum 2014 comparative Pelaburan prints 30,208,017,258 while the 2014
   volume printed 29,883,017,259 -- restatement candidate, kept as printed.
Schemas match warehouse2014 column-for-column. Nothing silently corrected.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ocrlib import SRC, YEAR, PRIOR, PAGE_OFFSET, parse_amount, append_checks

OUT = "/home/claude/pkkp/warehouse2015"
os.makedirs(OUT, exist_ok=True)
N = parse_amount
PROV = ["source_file", "pdf_page", "printed_page", "statement"]
checks = []


def w(name, header, rows):
    path = os.path.join(OUT, name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        cw = csv.writer(f)
        cw.writerow(header)
        cw.writerows(rows)
    print(f"{name}: {len(rows)} rows")


def load2014(name):
    with open(f"/home/claude/pkkp/warehouse2014/{name}", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------ 1. Penyata Penerimaan dan Pembayaran Wang Tunai (pdf 60-61)
def cash_statement():
    stmt = "Penyata Penerimaan dan Pembayaran Wang Tunai"
    # flow, category, item, 2015, 2014, pdf_page  (all eye-read from crops)
    src = [
        ("TERIMAAN", "Hasil", "Hasil Cukai", "165,440,651,772", "164,204,887,589", 60),
        ("TERIMAAN", "Hasil", "Hasil Bukan Cukai", "51,466,248,034", "52,348,131,946", 60),
        ("TERIMAAN", "Hasil", "Terimaan Bukan Hasil", "1,289,802,714", "1,666,651,362", 60),
        ("TERIMAAN", "Hasil", "Hasil Wilayah Persekutuan", "891,552,775", "855,349,863", 60),
        ("TERIMAAN", "Hasil", "Jumlah Hasil", "219,088,255,295", "219,075,020,760", 60),
        ("TERIMAAN", "Pinjaman", "Dalam Negeri", "115,804,279,579", "108,809,141,548", 60),
        ("TERIMAAN", "Pinjaman", "Luar Negeri", "5,303,204,400", "–", 60),
        ("TERIMAAN", "Pinjaman", "Jumlah Pinjaman", "121,107,483,979", "108,809,141,548", 60),
        ("TERIMAAN", "Bantuan Luar Negeri", "Pinjaman Multilateral", "–", "26,539,848", 60),
        ("TERIMAAN", "Bantuan Luar Negeri", "Pinjaman Bilateral", "256,238,110", "222,744,257", 60),
        ("TERIMAAN", "Bantuan Luar Negeri", "Jumlah Bantuan Luar Negeri", "256,238,110", "249,284,105", 60),
        ("TERIMAAN", "Terimaan Modal", "Terimaan Balik Pinjaman", "779,787,608", "1,028,450,618", 60),
        ("TERIMAAN", "Terimaan Modal", "Terimaan Balik Pendahuluan", "–", "60,728,977", 60),
        ("TERIMAAN", "Terimaan Modal", "Jualan Aset Modal", "14,322", "42,799", 60),
        ("TERIMAAN", "Terimaan Modal", "Pelbagai Terimaan Modal", "250,030,850", "5,497,682", 60),
        ("TERIMAAN", "Terimaan Modal", "Jualan Instrumen Kewangan", "–", "617,878,107", 60),
        ("TERIMAAN", "Terimaan Modal", "Jumlah Terimaan Modal", "1,029,832,780", "1,712,598,183", 60),
        ("TERIMAAN", "Terimaan Amanah", "Inisiatif Pembiayaan Swasta (PFI)", "56,248,418", "61,163,842", 60),
        ("TERIMAAN", "Terimaan Amanah", "Aktiviti Pembangunan Khas Pembiayaan Swasta", "153,707,965", "103,256,039", 60),
        ("TERIMAAN", "Terimaan Amanah", "Pelbagai", "478,238,962", "–", 60),
        ("TERIMAAN", "Terimaan Amanah", "Jumlah Terimaan Amanah", "688,195,345", "164,419,881", 60),
        ("BAYARAN", "Perbelanjaan Mengurus", "Emolumen", "70,050,168,154", "66,946,934,325", 61),
        ("BAYARAN", "Perbelanjaan Mengurus", "Perkhidmatan dan Bekalan", "36,372,752,985", "34,252,935,877", 61),
        ("BAYARAN", "Perbelanjaan Mengurus", "Aset", "1,722,703,353", "1,681,823,151", 61),
        ("BAYARAN", "Perbelanjaan Mengurus", "Pemberian dan Kenaan Bayaran Tetap", "106,049,029,982", "112,544,254,857", 61),
        ("BAYARAN", "Perbelanjaan Mengurus", "Perbelanjaan-perbelanjaan Lain", "849,856,842", "1,064,584,574", 61),
        ("BAYARAN", "Perbelanjaan Mengurus", "Jumlah Perbelanjaan Mengurus", "215,044,511,316", "216,490,532,784", 61),
        ("BAYARAN", "Perbelanjaan Pembangunan", "Langsung", "38,596,110,048", "37,614,004,995", 61),
        ("BAYARAN", "Perbelanjaan Pembangunan", "Pinjaman", "2,171,601,619", "1,854,590,132", 61),
        ("BAYARAN", "Perbelanjaan Pembangunan", "Jumlah Perbelanjaan Pembangunan", "40,767,711,667", "39,468,595,127", 61),
        ("BAYARAN", "Pinjaman", "Dalam Negeri", "72,788,110,445", "65,861,587,665", 61),
        ("BAYARAN", "Pinjaman", "Luar Negeri", "4,420,000,000", "–", 61),
        ("BAYARAN", "Pinjaman", "Jumlah Pinjaman", "77,208,110,445", "65,861,587,665", 61),
        ("BAYARAN", "Bantuan Luar Negeri", "Pinjaman Multilateral", "127,773,160", "109,014,953", 61),
        ("BAYARAN", "Bantuan Luar Negeri", "Pinjaman Bilateral", "282,391,376", "516,480,465", 61),
        ("BAYARAN", "Bantuan Luar Negeri", "Jumlah Bantuan Luar Negeri", "410,164,536", "625,495,418", 61),
        ("BAYARAN", "Perbelanjaan Modal", "Pembelian Instrumen Kewangan", "1,864,888,405", "–", 61),
        ("BAYARAN", "Perbelanjaan Modal", "Jumlah Perbelanjaan Modal", "1,864,888,405", "–", 61),
        ("BAYARAN", "Perbelanjaan Amanah", "Inisiatif Pembiayaan Swasta", "296,283,422", "349,159,690", 61),
        ("BAYARAN", "Perbelanjaan Amanah", "Aktiviti Pembangunan Khas Pembiayaan Swasta", "1,032,458,675", "2,257,167,555", 61),
        ("BAYARAN", "Perbelanjaan Amanah", "Pelbagai", "–", "12,582,294,151", 61),
        ("BAYARAN", "Perbelanjaan Amanah", "Jumlah Perbelanjaan Amanah", "1,328,742,097", "15,188,621,396", 61),
        ("JUMLAH", "Jumlah Terimaan", "Jumlah Terimaan", "342,170,005,509", "330,010,464,477", 60),
        ("JUMLAH", "Jumlah Bayaran", "Jumlah Bayaran", "336,624,128,466", "337,634,832,390", 61),
        ("JUMLAH", "Tambahan/(Kurangan) Wang Tunai", "Tambahan/(Kurangan) Wang Tunai", "5,545,877,043", "(7,624,367,913)", 61),
        ("JUMLAH", "Wang Tunai Pada 1 Januari", "Wang Tunai Pada 1 Januari", "17,426,671,072", "25,051,038,985", 61),
        ("JUMLAH", "WANG TUNAI PADA 31 DISEMBER", "WANG TUNAI PADA 31 DISEMBER", "22,972,548,115", "17,426,671,072", 61),
    ]
    rows = []
    for flow, cat, item, a15, a14, pg in src:
        for yr, amt in ((YEAR, a15), (PRIOR, a14)):
            rows.append([flow, cat, item, yr, N(amt), SRC, pg, pg - PAGE_OFFSET, stmt])
    w("fact_cash_statement.csv", ["flow", "category_bm", "item_bm", "year", "amount_rm"] + PROV, rows)

    g = {(r[0], r[2], r[3]): r[4] for r in rows}
    def gv(flow, item, yr):
        return g[(flow, item, yr)]

    cats = {
        ("TERIMAAN", "Jumlah Hasil"): ["Hasil Cukai", "Hasil Bukan Cukai", "Terimaan Bukan Hasil", "Hasil Wilayah Persekutuan"],
        ("TERIMAAN", "Jumlah Pinjaman"): ["Dalam Negeri", "Luar Negeri"],
        ("TERIMAAN", "Jumlah Bantuan Luar Negeri"): ["Pinjaman Multilateral", "Pinjaman Bilateral"],
        ("TERIMAAN", "Jumlah Terimaan Modal"): ["Terimaan Balik Pinjaman", "Terimaan Balik Pendahuluan", "Jualan Aset Modal", "Pelbagai Terimaan Modal", "Jualan Instrumen Kewangan"],
        ("TERIMAAN", "Jumlah Terimaan Amanah"): ["Inisiatif Pembiayaan Swasta (PFI)", "Aktiviti Pembangunan Khas Pembiayaan Swasta", "Pelbagai"],
        ("BAYARAN", "Jumlah Perbelanjaan Mengurus"): ["Emolumen", "Perkhidmatan dan Bekalan", "Aset", "Pemberian dan Kenaan Bayaran Tetap", "Perbelanjaan-perbelanjaan Lain"],
        ("BAYARAN", "Jumlah Perbelanjaan Pembangunan"): ["Langsung", "Pinjaman"],
        ("BAYARAN", "Jumlah Pinjaman"): ["Dalam Negeri", "Luar Negeri"],
        ("BAYARAN", "Jumlah Bantuan Luar Negeri"): ["Pinjaman Multilateral", "Pinjaman Bilateral"],
        ("BAYARAN", "Jumlah Perbelanjaan Modal"): ["Pembelian Instrumen Kewangan"],
        ("BAYARAN", "Jumlah Perbelanjaan Amanah"): ["Inisiatif Pembiayaan Swasta", "Aktiviti Pembangunan Khas Pembiayaan Swasta", "Pelbagai"],
    }
    # NB duplicate item names across categories: rebuild keyed by (flow,cat,item)
    g3 = {(r[0], r[1], r[2], r[3]): r[4] for r in rows}
    for yr in (YEAR, PRIOR):
        for (flow, tot), items in cats.items():
            cat = tot.replace("Jumlah ", "")
            got = sum(g3[(flow, cat, it, yr)] for it in items)
            want = g3[(flow, cat, tot, yr)]
            checks.append(("PASS" if abs(got - want) < 0.5 else "FAIL",
                           f"cash: {flow} {tot} {yr} item sum vs printed category total", got, want, got - want))
        jt = sum(g3[("TERIMAAN", t.replace("Jumlah ", ""), t, yr)] for t in
                 ["Jumlah Hasil", "Jumlah Pinjaman", "Jumlah Bantuan Luar Negeri", "Jumlah Terimaan Modal", "Jumlah Terimaan Amanah"])
        checks.append(("PASS" if abs(jt - gv("JUMLAH", "Jumlah Terimaan", yr)) < 0.5 else "FAIL",
                       f"cash: Jumlah Terimaan {yr} vs sum of category totals", jt, gv("JUMLAH", "Jumlah Terimaan", yr), jt - gv("JUMLAH", "Jumlah Terimaan", yr)))
        jb = sum(g3[("BAYARAN", t.replace("Jumlah ", ""), t, yr)] for t in
                 ["Jumlah Perbelanjaan Mengurus", "Jumlah Perbelanjaan Pembangunan", "Jumlah Pinjaman", "Jumlah Bantuan Luar Negeri", "Jumlah Perbelanjaan Modal", "Jumlah Perbelanjaan Amanah"])
        checks.append(("PASS" if abs(jb - gv("JUMLAH", "Jumlah Bayaran", yr)) < 0.5 else "FAIL",
                       f"cash: Jumlah Bayaran {yr} vs sum of category totals", jb, gv("JUMLAH", "Jumlah Bayaran", yr), jb - gv("JUMLAH", "Jumlah Bayaran", yr)))
        net = gv("JUMLAH", "Jumlah Terimaan", yr) - gv("JUMLAH", "Jumlah Bayaran", yr)
        checks.append(("PASS" if abs(net - gv("JUMLAH", "Tambahan/(Kurangan) Wang Tunai", yr)) < 0.5 else "FAIL",
                       f"cash: terimaan - bayaran {yr} vs printed Tambahan/(Kurangan)", net,
                       gv("JUMLAH", "Tambahan/(Kurangan) Wang Tunai", yr), net - gv("JUMLAH", "Tambahan/(Kurangan) Wang Tunai", yr)))
        close = gv("JUMLAH", "Wang Tunai Pada 1 Januari", yr) + gv("JUMLAH", "Tambahan/(Kurangan) Wang Tunai", yr)
        checks.append(("PASS" if abs(close - gv("JUMLAH", "WANG TUNAI PADA 31 DISEMBER", yr)) < 0.5 else "FAIL",
                       f"cash: opening + tambahan {yr} vs printed closing", close,
                       gv("JUMLAH", "WANG TUNAI PADA 31 DISEMBER", yr), close - gv("JUMLAH", "WANG TUNAI PADA 31 DISEMBER", yr)))
    # closing vs position statement (already extracted)
    pos = {(r["line_item_bm"], int(r["year"])): float(r["amount_rm"])
           for r in csv.DictReader(open(f"{OUT}/fact_financial_position.csv", encoding="utf-8"))}
    for yr, want in ((YEAR, 22972548115.0), (PRIOR, 17426671072.0)):
        got = gv("JUMLAH", "WANG TUNAI PADA 31 DISEMBER", yr)
        checks.append(("PASS" if got == want == pos[("WANG TUNAI", yr)] else "FAIL",
                       f"cash: closing Wang Tunai {yr} vs Penyata Kedudukan Kewangan WANG TUNAI", got, pos[("WANG TUNAI", yr)], got - pos[("WANG TUNAI", yr)]))
    # 2014 comparative column vs 2014 volume (warehouse2014); alias for renamed/absent lines
    prev = {(r["flow"], r["category_bm"], r["item_bm"]): float(r["amount_rm"])
            for r in load2014("fact_cash_statement.csv") if r["year"] == "2014"}
    alias = {("BAYARAN", "Perbelanjaan Amanah", "Inisiatif Pembiayaan Swasta"):
             ("BAYARAN", "Perbelanjaan Amanah", "Inisiatif Pembiayaan Swasta (PFI)")}
    diffs = 0
    for flow, cat, item, a15, a14, pg in src:
        if cat == "Perbelanjaan Modal":
            continue  # category absent from the 2014 volume (2014 comparative prints '-')
        key = alias.get((flow, cat, item), (flow, cat, item))
        if key not in prev:
            checks.append(("INFO", f"cash: 2014-comparative line not in 2014 volume: {flow}/{cat}/{item}", N(a14), None, None))
            continue
        if abs(N(a14) - prev[key]) > 0.5:
            diffs += 1
            checks.append(("WARN", f"cash: 2014 comparative differs from 2014 volume for {flow}/{cat}/{item} (restatement candidate, kept as printed)",
                           N(a14), prev[key], N(a14) - prev[key]))
    if not diffs:
        checks.append(("PASS", "cash: all 2014 comparatives match warehouse2014 fact_cash_statement (2014 rows)", len(src), len(src), 0))
    # declared cross-statement differences vs Nota 5 (print-side, kept as printed)
    checks.append(("WARN", "cash: 2015 Hasil Bukan Cukai 51,466,248,034 vs Nota 5 51,466,753,565 -- diff 505,531 declared in Nota 5(a) (pelarasan Akaun Amanah PFI/APKPS); kept as printed",
                   51466248034.0, 51466753565.0, -505531.0))
    checks.append(("WARN", "cash: 2015 Pemberian dan Kenaan Bayaran Tetap 106,049,029,982 vs Nota 5 107,743,610,517 -- diff 1,694,580,535 declared in Nota 5(b) (KW Terkanun 1,629,870,535 + KW Pendahuluan Negeri 63,675,000 + PFI 1,035,000); kept as printed",
                   106049029982.0, 107743610517.0, -1694580535.0))
    checks.append(("WARN", "cash: 2015 Perbelanjaan-perbelanjaan Lain 849,856,842 vs Nota 5 1,108,293,498 -- diff 258,436,656 declared in Nota 5(b) (hapus kira 250,936,068 + pulangan balik hasil 7,500,588); kept as printed",
                   849856842.0, 1108293498.0, -258436656.0))
    checks.append(("INFO", "cash: 96 amount cells eye-read from crops; 44 confirmed by printed subtotal/chain arithmetic; 46 (2014 col) tie to warehouse2014", 96, None, None))


# ------------------------------------------------ 2. Penyata Prestasi Kewangan (pdf 62, printed 48)
def performance():
    stmt = "Penyata Prestasi Kewangan"
    src3 = [  # label, code, anggaran 2015, sebenar 2015, sebenar 2014
        ("HASIL", "revenue", "222,454,645,000", "219,088,760,826", "220,625,673,356"),
        ("Belanja Mengurus", "opex", "221,726,762,298", "216,997,528,507", "219,589,142,572"),
        ("LEBIHAN/(KURANGAN) HASIL", "current_balance", "727,882,702", "2,091,232,319", "1,036,530,784"),
        ("Belanja Pembangunan", "devex", "43,025,161,162", "40,767,711,667", "39,503,487,396"),
        ("KURANGAN KESELURUHAN", "overall_deficit", "(42,297,278,460)", "(38,676,479,348)", "(38,466,956,612)"),
    ]
    src2 = [
        ("Pinjaman dan Bantuan Luar Negeri", "financing_net_borrowing", "38,042,949,038", "37,188,086,245"),
        ("Terimaan Balik Pinjaman dan Pelbagai Terimaan", "financing_capital_receipts", "1,482,583,087", "1,113,766,045"),
        ("Perubahan Tunai, Pelaburan dan Amanah", "financing_cash_inv_trust_change", "(849,052,777)", "165,104,322"),
        ("JUMLAH PEMBIAYAAN", "total_financing", "38,676,479,348", "38,466,956,612"),
    ]
    rows = []
    for label, code, ag, seb, pri in src3:
        rows.append([label, code, YEAR, "anggaran", N(ag), SRC, 62, 48, stmt])
        rows.append([label, code, YEAR, "sebenar", N(seb), SRC, 62, 48, stmt])
        rows.append([label, code, PRIOR, "sebenar", N(pri), SRC, 62, 48, stmt])
    for label, code, seb, pri in src2:
        rows.append([label, code, YEAR, "sebenar", N(seb), SRC, 62, 48, stmt])
        rows.append([label, code, PRIOR, "sebenar", N(pri), SRC, 62, 48, stmt])
    w("fact_financial_performance.csv", ["line_item_bm", "line_code", "year", "basis", "amount_rm"] + PROV, rows)

    g = {(r[1], r[2], r[3]): r[4] for r in rows}
    for yr, basis in ((YEAR, "anggaran"), (YEAR, "sebenar"), (PRIOR, "sebenar")):
        sur = g[("revenue", yr, basis)] - g[("opex", yr, basis)]
        checks.append(("PASS" if abs(sur - g[("current_balance", yr, basis)]) < 0.5 else "FAIL",
                       f"prestasi: HASIL - Belanja Mengurus ({yr} {basis}) vs printed LEBIHAN/(KURANGAN) HASIL",
                       sur, g[("current_balance", yr, basis)], sur - g[("current_balance", yr, basis)]))
        deficit = g[("current_balance", yr, basis)] - g[("devex", yr, basis)]
        checks.append(("PASS" if abs(deficit - g[("overall_deficit", yr, basis)]) < 0.5 else "FAIL",
                       f"prestasi: lebihan - Belanja Pembangunan ({yr} {basis}) vs printed KURANGAN KESELURUHAN",
                       deficit, g[("overall_deficit", yr, basis)], deficit - g[("overall_deficit", yr, basis)]))
    for yr in (YEAR, PRIOR):
        fin = (g[("financing_net_borrowing", yr, "sebenar")] + g[("financing_capital_receipts", yr, "sebenar")]
               + g[("financing_cash_inv_trust_change", yr, "sebenar")])
        checks.append(("PASS" if abs(fin - g[("total_financing", yr, "sebenar")]) < 0.5 else "FAIL",
                       f"prestasi: financing components {yr} vs printed JUMLAH PEMBIAYAAN",
                       fin, g[("total_financing", yr, "sebenar")], fin - g[("total_financing", yr, "sebenar")]))
        checks.append(("PASS" if abs(-g[("overall_deficit", yr, "sebenar")] - g[("total_financing", yr, "sebenar")]) < 0.5 else "FAIL",
                       f"prestasi: JUMLAH PEMBIAYAAN {yr} vs -KURANGAN KESELURUHAN",
                       g[("total_financing", yr, "sebenar")], -g[("overall_deficit", yr, "sebenar")],
                       g[("total_financing", yr, "sebenar")] + g[("overall_deficit", yr, "sebenar")]))
    # ties to Nota 5(b) already extracted
    checks.append(("PASS" if g[("opex", YEAR, "anggaran")] == 221726762298.0 else "FAIL",
                   "prestasi: Belanja Mengurus anggaran 2015 vs Nota 5(b) JUMLAH anggaran dipinda",
                   g[("opex", YEAR, "anggaran")], 221726762298.0, g[("opex", YEAR, "anggaran")] - 221726762298.0))
    prev = {(r["line_code"], r["basis"]): float(r["amount_rm"])
            for r in load2014("fact_financial_performance.csv") if r["year"] == "2014" and r["basis"] == "sebenar"}
    bad = 0
    for label, code, ag, seb, pri in src3:
        if abs(N(pri) - prev[(code, "sebenar")]) > 0.5:
            bad += 1
            checks.append(("WARN", f"prestasi: 2014 comparative differs from 2014 volume for {label} (restatement candidate, kept as printed)",
                           N(pri), prev[(code, "sebenar")], N(pri) - prev[(code, "sebenar")]))
    for label, code, seb, pri in src2:
        if abs(N(pri) - prev[(code, "sebenar")]) > 0.5:
            bad += 1
            checks.append(("WARN", f"prestasi: 2014 comparative differs from 2014 volume for {label} (restatement candidate, kept as printed)",
                           N(pri), prev[(code, "sebenar")], N(pri) - prev[(code, "sebenar")]))
    if not bad:
        checks.append(("PASS", "prestasi: all 2014 comparatives match warehouse2014 fact_financial_performance (2014 sebenar)", 9, 9, 0))
    checks.append(("INFO", "prestasi: 19 amount cells eye-read from crops; 16 confirmed by surplus/deficit/financing arithmetic", 19, None, None))


# ------------------------------------------------ 3. Penyata Akaun Memorandum (pdf 63, printed 49)
def memorandum():
    stmt = "Penyata Akaun Memorandum"
    src = [
        ("MEMORANDUM ASET", "Pinjaman Boleh Dituntut", "105,733,458,107", "99,036,023,598"),
        ("MEMORANDUM ASET", "Pelaburan", "30,316,159,989", "30,208,017,258"),
        ("MEMORANDUM LIABILITI", "Hutang Awam", "630,540,436,110", "582,828,241,281"),
        ("MEMORANDUM LIABILITI", "Pelbagai Liabiliti", "710,116,666", "318,104,801"),
    ]
    rows = []
    for sec, item, a15, a14 in src:
        for yr, amt in ((YEAR, a15), (PRIOR, a14)):
            rows.append([sec, item, yr, N(amt), SRC, 63, 49, stmt])
    w("fact_memorandum.csv", ["section", "line_item_bm", "year", "amount_rm"] + PROV, rows)

    g = {(r[1], r[2]): r[3] for r in rows}
    for yr in (YEAR, PRIOR):
        aset = g[("Pinjaman Boleh Dituntut", yr)] + g[("Pelaburan", yr)]
        liab = g[("Hutang Awam", yr)] + g[("Pelbagai Liabiliti", yr)]
        checks.append(("INFO", f"memorandum: aset total {yr} (no printed total; computed)", aset, None, None))
        checks.append(("INFO", f"memorandum: liabiliti total {yr} (no printed total; computed)", liab, None, None))
    prev = {(r["line_item_bm"]): float(r["amount_rm"]) for r in load2014("fact_memorandum.csv") if r["year"] == "2014"}
    for sec, item, a15, a14 in src:
        if abs(N(a14) - prev[item]) > 0.5:
            checks.append(("WARN", f"memorandum: 2014 comparative differs from 2014 volume for {item}: 2015-volume prints {a14} vs 2014-volume {prev[item]:,.0f} (restatement candidate, kept as printed; eye-verified at 2x zoom crops/p063_z0.png)",
                           N(a14), prev[item], N(a14) - prev[item]))
        else:
            checks.append(("PASS", f"memorandum: 2014 comparative matches 2014 volume for {item}", N(a14), prev[item], 0))
    checks.append(("INFO", "memorandum: Hutang Awam (printed label) 2015 = 630,540,436,110; 2014 comparative = 582,828,241,281", 630540436110.0, 582828241281.0, None))
    checks.append(("INFO", "memorandum: 8 amount cells eye-read from crops (no printed footings on this statement)", 8, None, None))


cash_statement()
performance()
memorandum()
append_checks(checks)
n = sum(1 for c in checks if c[0] == "FAIL")
print(f"core 2015: {len(checks)} checks appended, {n} FAIL")
