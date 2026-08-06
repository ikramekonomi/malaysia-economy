#!/usr/bin/env python3
"""Reconcile fact_anggaran_maksud_2026.csv against the book's own printed totals,
the 2025 book (cross-book restatement check) and PKKP audited 2024 (cross-source).

Printed constants: "RINGKASAN KESELURUHAN" block of
Anggaran_Perbelanjaan_Persekutuan_2026.pdf (printed p.33). Column order:
sebenar_2023, sebenar_2024, anggaran_asal_2025, anggaran_2026.

Checks:
  A. per-vote identities (emol+lain = mengurus; jumlah = mengurus for T/standalone B;
     cara_langsung+pinjaman = pembangunan)
  C. sums over T+B votes vs printed Mengurus / Emolumen / Lain grand totals
  D. sums over P votes vs printed Pembangunan / Cara Langsung / Pinjaman (+P.70)
  E. JUMLAH BESAR
  X1. anggaran_asal_2025 (this book) vs anggaran_2025 tabled in the 2025 book, per vote
  X2. sebenar_2023 (this book) vs sebenar_2023 in the 2025 book, per vote
  X3. sebenar_2024 OE/DE totals vs PKKP audited FY2024
Cross-book/source mismatches are catalogued (INFO/FAIL), never corrected.
Writes _validation_2026.csv.
"""
import csv
import os
from collections import defaultdict

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "..", "data", "2026")
DATA25 = os.path.join(HERE, "..", "..", "data", "2025")
DB = os.path.join(HERE, "..", "..", "..", "..", "sources", "pkkp", "pkkp.duckdb")
MEASURES = ["sebenar_2023", "sebenar_2024", "anggaran_asal_2025", "anggaran_2026"]

PRINTED = {  # RINGKASAN KESELURUHAN, printed p.33
    "mengurus": [314_959_481_731, 324_617_649_252, 335_000_000_000, 338_202_000_000],
    "emolumen": [91_859_514_598, 95_935_832_990, 105_908_537_000, 109_365_679_900],
    "lain": [223_099_967_133, 228_681_816_259, 229_091_463_000, 228_836_320_100],
    "pembangunan": [96_089_737_122, 84_011_595_465, 88_000_000_000, 83_000_000_000],
    "cara_langsung": [94_868_859_829, 83_216_205_192, 84_587_068_900, 79_981_683_700],
    "pinjaman": [1_220_877_293, 795_390_272, 1_412_931_100, 1_018_316_300],
    "p70": [0, 0, 2_000_000_000, 2_000_000_000],
    "jumlah_besar": [411_049_218_853, 408_629_244_715, 423_000_000_000, 421_202_000_000],
}

amt = defaultdict(dict)
for r in csv.DictReader(open(os.path.join(DATA, "fact_anggaran_maksud_2026.csv"))):
    amt[(r["maksud_code"], r["component"])][r["measure"]] = int(r["amount_rm"])
codes = sorted({k[0] for k in amt})
out = []


def rec(check, scope, m, expected, got, status=None):
    out.append([check, scope, m, expected, got,
                status or ("PASS" if expected == got else "FAIL")])


for c in codes:
    for m in MEASURES:
        if c.startswith(("T.", "B.")):
            rec("A_vote_total", c, m, amt[(c, "mengurus")][m],
                amt[(c, "emolumen")].get(m, 0) + amt[(c, "lain")].get(m, 0))
            if (c, "jumlah") in amt:
                rec("A_vote_jumlah", c, m, amt[(c, "jumlah")][m], amt[(c, "mengurus")][m])
        elif c.startswith("P.") and (c, "cara_langsung") in amt:
            rec("A_vote_total", c, m, amt[(c, "pembangunan")][m],
                amt[(c, "cara_langsung")].get(m, 0) + amt[(c, "pinjaman")].get(m, 0))

for i, m in enumerate(MEASURES):
    tb = [c for c in codes if c.startswith(("T.", "B."))]
    rec("C_mengurus", "jumlah", m, PRINTED["mengurus"][i], sum(amt[(c, "mengurus")][m] for c in tb))
    rec("C_mengurus", "emolumen", m, PRINTED["emolumen"][i],
        sum(amt[(c, "emolumen")].get(m, 0) for c in tb))
    rec("C_mengurus", "lain", m, PRINTED["lain"][i], sum(amt[(c, "lain")].get(m, 0) for c in tb))
    pv = [c for c in codes if c.startswith("P.") and c != "P.70"]
    rec("D_pembangunan", "cara_langsung", m, PRINTED["cara_langsung"][i],
        sum(amt[(c, "cara_langsung")].get(m, 0) for c in pv))
    rec("D_pembangunan", "pinjaman", m, PRINTED["pinjaman"][i],
        sum(amt[(c, "pinjaman")].get(m, 0) for c in pv))
    rec("D_pembangunan", "jumlah_incl_P70", m, PRINTED["pembangunan"][i],
        sum(amt[(c, "pembangunan")][m] for c in codes if c.startswith("P.")))
    rec("E_jumlah_besar", "", m, PRINTED["jumlah_besar"][i],
        sum(amt[(c, "mengurus")][m] for c in tb)
        + sum(amt[(c, "pembangunan")][m] for c in codes if c.startswith("P.")))

# X1/X2: cross-book vs the 2025 book
a25 = defaultdict(dict)
for r in csv.DictReader(open(os.path.join(DATA25, "fact_anggaran_maksud_2025.csv"))):
    a25[(r["maksud_code"], r["component"])][r["measure"]] = int(r["amount_rm"])
n_same = n_diff = 0
for c in codes:
    if c.startswith(("T.", "B.")):
        comp26, comp25 = "mengurus", ("jumlah" if c.startswith("T.") else "mengurus")
    elif c == "P.70":
        continue
    else:
        comp26 = comp25 = "pembangunan"
    for m26, m25, tag in (("anggaran_asal_2025", "anggaran_2025", "X1_tabled_2025"),
                          ("sebenar_2023", "sebenar_2023", "X2_actual_2023")):
        v26, v25 = amt[(c, comp26)].get(m26), a25[(c, comp25)].get(m25)
        if v25 is None:
            continue
        if v26 == v25:
            n_same += 1
        else:
            n_diff += 1
            rec(tag, c, m26, v25, v26, "RESTATED")
rec("X_crossbook_summary", f"{n_same} identical", f"{n_diff} restated", "", "", "INFO")

# X3: sebenar_2024 vs PKKP audited FY2024 (by-vote OE incl. Development Fund transfer; gross DE)
con = duckdb.connect(DB, read_only=True)
pk_oe = con.sql("SELECT sum(sebenar_rm) FROM fact_opex_maksud WHERE source_file ILIKE '2024_PENYATA%' AND year=2024").fetchone()[0]
pk_de = con.sql("SELECT sum(sebenar_jumlah_rm) FROM fact_devex_maksud WHERE source_file ILIKE '2024_PENYATA%' AND year=2024 AND maksud_code LIKE 'P.%'").fetchone()[0]
for scope, pk, pr in (("OE (by-vote total)", int(pk_oe), PRINTED["mengurus"][1]),
                      ("DE (gross)", int(pk_de), PRINTED["pembangunan"][1])):
    d = pr - pk
    rec("X3_vs_pkkp_2024", scope, "sebenar_2024", pk, pr,
        "INFO" if abs(d) <= 60 else "FAIL")  # book prints whole RM, PKKP keeps sen:
        # agreement within ~RM1 per vote is rounding, not a discrepancy

dest = os.path.join(DATA, "_validation_2026.csv")
with open(dest, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["check", "scope", "measure", "expected", "got", "status"])
    w.writerows(out)
fails = [r for r in out if r[-1] == "FAIL"]
restated = [r for r in out if r[-1] == "RESTATED"]
print(f"{len(out)} checks: {len(fails)} FAIL, {len(restated)} RESTATED (cross-book) -> {dest}")
for r in fails[:15]:
    print("FAIL:", r)
for r in restated[:15]:
    print("RESTATED:", r)
