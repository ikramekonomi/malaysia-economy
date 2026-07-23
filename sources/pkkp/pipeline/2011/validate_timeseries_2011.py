#!/usr/bin/env python3
"""Validate warehouse2011/fact_timeseries_2002_2011.csv.

(a) Independent re-parse of the pdftotext -layout panel text and full-cell
    reconciliation vs the pdfplumber-produced CSV.
(b) Cross-foot every printed subtotal across ALL ten year columns.
(c) Tie the 2011 column to the audited primary statements.
"""
import csv, re
from collections import Counter, defaultdict

CSV = "/home/claude/pkkp/warehouse2011/fact_timeseries_2002_2011.csv"
TXT = "/home/claude/pkkp/work/2011/full.txt"
YEARS = list(range(2011, 2001, -1))  # 2011..2002 left-to-right

# ---------- load CSV ----------
rows = list(csv.reader(open(CSV)))[1:]
csv_items = defaultdict(dict)          # (section,label) -> {year: val}
order = []
for r in rows:
    k = (r[0], r[1]); y = int(r[2]); v = float(r[3])
    if k not in csv_items: order.append(k)
    csv_items[k][y] = v

def numtok(t):
    return bool(re.match(r"^\(?[\d,]+\)?$", t)) or t in ("–", "—", "-")
def parse(t):
    if t in ("–", "—", "-"): return 0.0
    neg = t.startswith("(") and t.endswith(")")
    return (-1 if neg else 1) * float(t.strip("()").replace(",", ""))

# ---------- (a) independent -layout re-parse ----------
pages = open(TXT, encoding="utf-8", errors="replace").read().split("\f")
layout_tuples = []   # (label, (v2011..v2002))
for idx in (319, 320, 321):
    for raw in pages[idx].splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        toks = line.split()
        # reverse-scan trailing numeric run
        tail = []
        i = len(toks) - 1
        while i >= 0 and numtok(toks[i]):
            tail.append(toks[i]); i -= 1
        tail = tail[::-1]
        label = " ".join(toks[:i+1]).strip()
        # drop leading footnote superscript captured as an 11th number
        if len(tail) == 11 and re.match(r"^\d{1,2}$", tail[0]):
            label = (label + " " + tail[0]).strip(); tail = tail[1:]
        if len(tail) != 10:
            continue
        # skip header/junk/footnote lines
        if re.search(r"indd|Apendices|\d+/\d+/\d+", line): continue
        if label.startswith(("Nota", "(1)", "(2)", "(3)", "(4)")): continue
        vals = tuple(parse(t) for t in tail)
        layout_tuples.append((label, vals))

# build multiset of value-tuples from each source
csv_tuples = Counter(tuple(csv_items[k][y] for y in YEARS) for k in order)
lay_tuples = Counter(v for _, v in layout_tuples)
print("=== (a) INDEPENDENT -LAYOUT RECONCILIATION ===")
print(f"CSV item rows: {sum(csv_tuples.values())}   layout number-lines: {sum(lay_tuples.values())}")
missing = lay_tuples - csv_tuples
extra = csv_tuples - lay_tuples
if not missing and not extra:
    print("PASS: every 10-value row in CSV matches a -layout line exactly (multiset equal).")
else:
    print("MISMATCH:")
    for t, c in missing.items(): print("  in layout not CSV:", t)
    for t, c in extra.items(): print("  in CSV not layout:", t)

# per-cell count
print(f"total data cells: {sum(csv_tuples.values())*10}")

# ---------- (b) cross-footing across all ten years ----------
print("\n=== (b) CROSS-FOOTING (all 10 years) ===")
def g(section, label):
    return csv_items.get((section, label))

checks = [
    ("Jumlah Wang Awam", ("Wang Awam","Jumlah Wang Awam"),
        [("Wang Awam","Wang Tunai"),("Wang Awam","Pelaburan")]),
    ("Jumlah Kumpulan Wang Disatukan", ("Kumpulan Wang Disatukan","Jumlah Kumpulan Wang Disatukan"),
        [("Kumpulan Wang Disatukan","Akaun Hasil Disatukan"),
         ("Kumpulan Wang Disatukan","Akaun Pinjaman Disatukan"),
         ("Kumpulan Wang Disatukan","Akaun Amanah Disatukan")]),
    ("Jumlah Hasil", ("Hasil","Jumlah Hasil"),
        [("Hasil","Cukai Langsung"),("Hasil","Cukai Tidak Langsung"),("Hasil","Terimaan Lain")]),
    ("Jumlah Perbelanjaan Mengurus", ("Perbelanjaan Mengurus","Jumlah Perbelanjaan Mengurus"),
        [("Perbelanjaan Mengurus","Emolumen"),("Perbelanjaan Mengurus","Perkhidmatan dan Bekalan"),
         ("Perbelanjaan Mengurus","Aset"),("Perbelanjaan Mengurus","Pemberian dan Kenaan Bayaran Tetap"),
         ("Perbelanjaan Mengurus","Perbelanjaan Lain")]),
    ("Jumlah Terimaan Pinjaman DN", ("Terimaan Pinjaman Dalam Negeri","Jumlah Terimaan Pinjaman Dalam Negeri"),
        [("Terimaan Pinjaman Dalam Negeri",x) for x in
         ("Bil Perbendaharaan","Terbitan Pelaburan Kerajaan","Sekuriti Kerajaan Malaysia",
          "Pinjaman Pasaran","SUKUK","Pinjaman Lain")]),
    ("Jumlah Terimaan Pinjaman LN", ("Terimaan Pinjaman Luar Negeri","Jumlah Terimaan Pinjaman Luar Negeri"),
        [("Terimaan Pinjaman Luar Negeri",x) for x in ("Pinjaman Pasaran","Pinjaman Projek","Pinjaman Lain")]),
    ("Jumlah Terimaan Pinjaman", ("Terimaan Pinjaman Luar Negeri","Jumlah Terimaan Pinjaman"),
        [("Terimaan Pinjaman Dalam Negeri","Jumlah Terimaan Pinjaman Dalam Negeri"),
         ("Terimaan Pinjaman Luar Negeri","Jumlah Terimaan Pinjaman Luar Negeri")]),
    ("Jumlah Bayaran Balik DN", ("Bayaran Balik Dalam Negeri","Jumlah Bayaran Balik Dalam Negeri"),
        [("Bayaran Balik Dalam Negeri",x) for x in
         ("Bil Perbendaharaan","Terbitan Pelaburan Kerajaan","Sekuriti Kerajaan Malaysia",
          "Pinjaman Pasaran","SUKUK","Pinjaman Lain")]),
    ("Jumlah Bayaran Balik LN", ("Bayaran Balik Luar Negeri","Jumlah Bayaran Balik Luar Negeri"),
        [("Bayaran Balik Luar Negeri",x) for x in ("Pinjaman Pasaran","Pinjaman Projek","Pinjaman Lain")]),
    ("Jumlah Bayaran Balik", ("Bayaran Balik Luar Negeri","Jumlah Bayaran Balik"),
        [("Bayaran Balik Dalam Negeri","Jumlah Bayaran Balik Dalam Negeri"),
         ("Bayaran Balik Luar Negeri","Jumlah Bayaran Balik Luar Negeri")]),
    ("Jumlah Pinjaman Bersih DN", ("Pinjaman Bersih Dalam Negeri","Jumlah Pinjaman Bersih Dalam Negeri"),
        [("Pinjaman Bersih Dalam Negeri",x) for x in
         ("Bil Perbendaharaan","Terbitan Pelaburan Kerajaan","Sekuriti Kerajaan Malaysia",
          "Pinjaman Pasaran","SUKUK","Pinjaman Lain")]),
    ("Jumlah Pinjaman Bersih LN", ("Pinjaman Bersih Luar Negeri","Jumlah Pinjaman Bersih Luar Negeri"),
        [("Pinjaman Bersih Luar Negeri",x) for x in ("Pinjaman Pasaran","Pinjaman Projek","Pinjaman Lain")]),
    ("Jumlah Pinjaman Bersih", ("Pinjaman Bersih Luar Negeri","Jumlah Pinjaman Bersih"),
        [("Pinjaman Bersih Dalam Negeri","Jumlah Pinjaman Bersih Dalam Negeri"),
         ("Pinjaman Bersih Luar Negeri","Jumlah Pinjaman Bersih Luar Negeri")]),
    ("Jumlah Wang Tunai", ("Wang Tunai","Jumlah Wang Tunai"),
        [("Wang Tunai","Wang Tunai Dalam Bank"),("Wang Tunai","Wang Tunai Dalam Tangan dan Dalam Perjalanan")]),
    ("Jumlah Pelaburan", ("Pelaburan","Jumlah Pelaburan"),
        [("Pelaburan","Pelaburan Kumpulan Wang Amanah"),("Pelaburan","Pelaburan Am")]),
    ("Jumlah Pinjaman Boleh Dituntut", ("Pinjaman Boleh Dituntut","Jumlah Pinjaman Boleh Dituntut"),
        [("Pinjaman Boleh Dituntut",x) for x in
         ("Kerajaan Negeri","Pihak Berkuasa Tempatan","Badan Berkanun","Koperasi","Syarikat","Perseorangan","Pelbagai")]),
    ("Jumlah Hutang Awam DN", ("Hutang Awam Dalam Negeri","Jumlah Hutang Awam Dalam Negeri"),
        [("Hutang Awam Dalam Negeri",x) for x in
         ("Bil Perbendaharaan","Terbitan Pelaburan Kerajaan","Sekuriti Kerajaan Malaysia","SUKUK","Pinjaman Lain")]),
    ("Jumlah Hutang Awam LN", ("Hutang Awam Luar Negeri","Jumlah Hutang Awam Luar Negeri"),
        [("Hutang Awam Luar Negeri",x) for x in ("Pinjaman Pasaran","Bantuan Luar Negeri","Pinjaman Lain")]),
    ("Jumlah Hutang Awam", ("Hutang Awam Luar Negeri","Jumlah Hutang Awam"),
        [("Hutang Awam Dalam Negeri","Jumlah Hutang Awam Dalam Negeri"),
         ("Hutang Awam Luar Negeri","Jumlah Hutang Awam Luar Negeri")]),
    ("Jumlah Jaminan", ("Jaminan","Jumlah Jaminan"),
        [("Jaminan","Pinjaman Dalam Negeri"),("Jaminan","Pinjaman Luar Negeri")]),
    ("Jumlah Punca Dana", ("Punca Dana","Jumlah Punca Dana"),
        [("Punca Dana","Hasil"),("Punca Dana","Terimaan Kumpulan Wang Pembangunan"),
         ("Punca Dana","Terimaan Bersih Kumpulan Wang Amanah Lain")]),
    ("Jumlah Penggunaan Dana", ("Penggunaan Dana","Jumlah Penggunaan Dana"),
        [("Penggunaan Dana","Perbelanjaan Mengurus (tidak termasuk pindahan ke Kumpulan Wang Pembangunan)"),
         ("Penggunaan Dana","Perbelanjaan Pembangunan"),
         ("Penggunaan Dana","Bayaran Bersih Kumpulan Wang Amanah Lain")]),
    ("Jumlah Penerimaan (KWP)", ("Kumpulan Wang Pembangunan / Penerimaan","Jumlah Penerimaan"),
        [("Kumpulan Wang Pembangunan / Penerimaan",x) for x in
         ("Caruman dari Akaun Hasil Disatukan","Pindahan dari Akaun Pinjaman Disatukan","Lain-lain")]),
    ("Jumlah Pembayaran (KWP)", ("Kumpulan Wang Pembangunan / Perbelanjaan Pembangunan","Jumlah Pembayaran"),
        [("Kumpulan Wang Pembangunan / Perbelanjaan Pembangunan","Langsung"),
         ("Kumpulan Wang Pembangunan / Perbelanjaan Pembangunan","Pinjaman")]),
]
npass = nfail = 0
fails = []
for name, tot_k, parts in checks:
    tot = g(*tot_k)
    if tot is None:
        print(f"  ?? {name}: total row not found {tot_k}"); nfail += 1; continue
    partvals = [g(*p) for p in parts]
    if any(p is None for p in partvals):
        miss = [pk for pk,pv in zip(parts,partvals) if pv is None]
        print(f"  ?? {name}: missing parts {miss}"); nfail += 1; continue
    bad = []
    for y in YEARS:
        s = round(sum(pv[y] for pv in partvals), 6)
        if abs(s - tot[y]) > 0.5:
            bad.append((y, tot[y], s))
    if bad:
        nfail += 1
        fails.append((name, bad))
        print(f"  FAIL {name}: " + "; ".join(f"{y}: printed {t:,.0f} vs sum {s:,.0f} (d={t-s:+,.0f})" for y,t,s in bad))
    else:
        npass += 1
        print(f"  pass {name}")
print(f"\ncross-foot: {npass} pass / {nfail} fail")

# ---------- (c) 2011 column vs audited primary statements ----------
print("\n=== (c) 2011 COLUMN vs AUDITED PRIMARY STATEMENTS ===")
anchors = {
    ("Wang Awam","Wang Tunai"): 24467,
    ("Wang Awam","Pelaburan"): 22843,
    ("Wang Awam","Jumlah Wang Awam"): 47310,
    ("Kumpulan Wang Disatukan","Akaun Hasil Disatukan"): 11863,
    ("Kumpulan Wang Disatukan","Akaun Pinjaman Disatukan"): 38909,
    ("Kumpulan Wang Disatukan","Akaun Amanah Disatukan"): -3462,
}
allok = True
for k, exp in anchors.items():
    got = csv_items[k][2011]
    ok = abs(got - exp) < 0.5
    allok &= ok
    print(f"  {'OK ' if ok else 'XX '}{k[1]:45s} 2011 = {got:>12,.0f}  (audited {exp:>12,.0f})")
print("ALL ANCHORS TIE" if allok else "ANCHOR MISMATCH")
