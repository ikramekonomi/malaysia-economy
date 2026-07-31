#!/usr/bin/env python3
"""Reconcile fact_anggaran_maksud_2024.csv against the book's own printed totals.

Printed constants below are transcribed from Anggaran_Perbelanjaan_Persekutuan_2024.pdf:
  - "Ringkasan Maksud Tanggungan" block, printed page ~22
  - final "Ringkasan" block (Mengurus/Pembangunan/JUMLAH BESAR), printed page ~33
Column order everywhere: sebenar_2022, sebenar_2023, anggaran_asal_2024, anggaran_2025.

Checks:
  A. per-maksud leaf sums vs the maksud's own printed total row
  B. sum over T maksud vs printed Tanggungan totals (emolumen / lain / jumlah)
  C. sum over T+B vs printed Perbelanjaan Mengurus totals (emolumen / lain / jumlah)
  D. sum over P vs printed Pembangunan totals (cara langsung / pinjaman / jumlah incl. P.70)
  E. mengurus + pembangunan vs printed JUMLAH BESAR
Writes _validation_2024.csv next to the fact table. Discrepancies are reported, never
corrected (CLAUDE.md golden rules).
"""
import csv
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "..", "data", "2024")
MEASURES = ["sebenar_2021", "sebenar_2022", "anggaran_asal_2023", "anggaran_2024"]

PRINTED = {  # (block, line) -> 4 amounts, RM, as printed
    ("tanggungan_p22", "emolumen"): [105_075_984, 106_843_351, 110_696_900, 112_791_800],
    ("tanggungan_p22", "lain"): [72_345_841_158, 78_317_766_531, 83_281_949_800, 89_132_943_900],
    ("tanggungan_p22", "jumlah"): [72_450_917_142, 78_424_609_882, 83_392_646_700, 89_245_735_700],
    ("mengurus_p31", "emolumen"): [85_853_502_802, 87_789_106_716, 90_765_441_600, 95_640_670_600],
    ("mengurus_p31", "lain"): [147_898_552_227, 206_567_653_899, 198_374_558_400, 208_159_329_400],
    ("mengurus_p31", "jumlah"): [233_752_055_029, 294_356_760_615, 289_140_000_000, 303_800_000_000],
    ("pembangunan_p31", "cara_langsung"): [63_275_221_796, 69_928_178_121, 95_614_462_300, 88_990_054_000],
    ("pembangunan_p31", "pinjaman"): [981_443_959, 1_645_783_305, 1_385_537_700, 1_009_946_000],
    ("pembangunan_p31", "jumlah"): [64_256_665_755, 71_573_961_426, 99_000_000_000, 92_000_000_000],
    ("grand_p31", "jumlah_besar"): [298_008_720_784, 365_930_722_041, 388_140_000_000, 395_800_000_000],
}

amt = defaultdict(dict)  # (code, component) -> {measure: amount}
meta = {}
for r in csv.DictReader(open(os.path.join(DATA, "fact_anggaran_maksud_2024.csv"))):
    amt[(r["maksud_code"], r["component"])][r["measure"]] = int(r["amount_rm"])
    meta[r["maksud_code"]] = r["jenis"]

codes = sorted(meta)
out = []


def rec(check, scope, m, expected, got):
    out.append([check, scope, m, expected, got, "PASS" if expected == got else "FAIL"])


# A. per-maksud identities
for c in codes:
    for m in MEASURES:
        if c.startswith("T."):
            rec("A_maksud_total", c, m, amt[(c, "jumlah")][m],
                amt[(c, "emolumen")].get(m, 0) + amt[(c, "lain")].get(m, 0))
        elif c.startswith("B."):
            # a component row can be absent as printed (e.g. B.12 prints no Emolumen)
            rec("A_maksud_total", c, m, amt[(c, "mengurus")][m],
                amt[(c, "emolumen")].get(m, 0) + amt[(c, "lain")].get(m, 0))
        elif c.startswith("P.") and (c, "cara_langsung") in amt:
            rec("A_maksud_total", c, m, amt[(c, "pembangunan")][m],
                amt[(c, "cara_langsung")][m] + amt[(c, "pinjaman")].get(m, 0)
                if (c, "pinjaman") in amt else amt[(c, "cara_langsung")][m])

# B-E. printed grand totals
for i, m in enumerate(MEASURES):
    t_emol = sum(amt[(c, "emolumen")].get(m, 0) for c in codes if c.startswith("T."))
    t_lain = sum(amt[(c, "lain")].get(m, 0) for c in codes if c.startswith("T."))
    t_jum = sum(amt[(c, "jumlah")][m] for c in codes if c.startswith("T."))
    rec("B_tanggungan", "emolumen", m, PRINTED[("tanggungan_p22", "emolumen")][i], t_emol)
    rec("B_tanggungan", "lain", m, PRINTED[("tanggungan_p22", "lain")][i], t_lain)
    rec("B_tanggungan", "jumlah", m, PRINTED[("tanggungan_p22", "jumlah")][i], t_jum)

    b_emol = sum(amt[(c, "emolumen")].get(m, 0) for c in codes if c.startswith("B."))
    b_lain = sum(amt[(c, "lain")].get(m, 0) for c in codes if c.startswith("B."))
    b_meng = sum(amt[(c, "mengurus")][m] for c in codes if c.startswith("B."))
    rec("C_mengurus", "emolumen", m, PRINTED[("mengurus_p31", "emolumen")][i], t_emol + b_emol)
    rec("C_mengurus", "lain", m, PRINTED[("mengurus_p31", "lain")][i], t_lain + b_lain)
    rec("C_mengurus", "jumlah", m, PRINTED[("mengurus_p31", "jumlah")][i], t_jum + b_meng)

    p_cl = sum(amt[(c, "cara_langsung")][m] for c in codes
               if c.startswith("P.") and (c, "cara_langsung") in amt)
    p_pj = sum(amt[(c, "pinjaman")][m] for c in codes
               if c.startswith("P.") and (c, "pinjaman") in amt)
    p_all = sum(amt[(c, "pembangunan")][m] for c in codes if c.startswith("P."))
    rec("D_pembangunan", "cara_langsung_excl_P70", m, PRINTED[("pembangunan_p31", "cara_langsung")][i], p_cl)
    rec("D_pembangunan", "pinjaman", m, PRINTED[("pembangunan_p31", "pinjaman")][i], p_pj)
    rec("D_pembangunan", "jumlah_incl_P70", m, PRINTED[("pembangunan_p31", "jumlah")][i], p_all)

    rec("E_jumlah_besar", "mengurus+pembangunan", m, PRINTED[("grand_p31", "jumlah_besar")][i],
        t_jum + b_meng + p_all)

dest = os.path.join(DATA, "_validation_2024.csv")
with open(dest, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["check", "scope", "measure", "expected_printed", "derived_from_leaves", "status"])
    w.writerows(out)

fails = [r for r in out if r[-1] == "FAIL"]
print(f"{len(out)} checks, {len(fails)} FAIL -> {dest}")
for r in fails[:20]:
    print("FAIL:", r)
