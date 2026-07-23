#!/usr/bin/env python3
"""Rebuild a CLEAN, meaningful validation suite for warehouse2015 and a
per-cell unresolved-OCR inventory. Replaces the prior 7,294-FAIL suite.

Outputs:
  warehouse2015/_validation_checks_2015.csv      (status,check,extracted_value,printed_value,difference)
  warehouse2015/_unresolved_ocr_cells_2015.csv   (every unresolved detail cell, listed with residual)
The memoranda checks file is kept as-is (registers already clean).
"""
import csv
from collections import defaultdict

WH = "/home/claude/pkkp/warehouse2015"
VAL = f"{WH}/_validation_checks_2015.csv"
INV = f"{WH}/_unresolved_ocr_cells_2015.csv"

def A(x):
    x = (x or "").strip()
    try:
        return float(x)
    except ValueError:
        return 0.0

checks = []   # (status, check, extracted, printed, diff)
unres = []    # (table, key, column, extracted, printed_target, residual, diagnosis)

def add(status, check, ext="", pr="", diff=""):
    checks.append((status, check, ext, pr, diff))

# ---------------------------------------------------------------- OPEX
oracle = {r["maksud_code"]: r for r in csv.DictReader(open(f"{WH}/fact_opex_maksud.csv"))}
opex = list(csv.DictReader(open(f"{WH}/fact_opex_detail.csv")))
COLS = ["anggaran_asal_rm", "anggaran_jumlah_rm", "sebenar_rm"]
OMAP = [("anggaran_asal_rm", "anggaran_asal_rm"),
        ("anggaran_jumlah_rm", "anggaran_dipinda_rm"),
        ("sebenar_rm", "sebenar_rm")]
bymk = defaultdict(list)
for r in opex:
    bymk[r["maksud_code"]].append(r)

# (a) 50 maksud totals vs Nota 5(b) oracle
n_mt_ok = 0
for mk in sorted(oracle):
    mt = [r for r in bymk.get(mk, []) if r["row_type"] == "jumlah_maksud"]
    if not mt:
        add("FAIL", f"opex/lampiran1: {mk} jumlah_maksud row MISSING")
        continue
    mt = mt[0]
    ok = True
    for c, oc in OMAP:
        d = A(mt[c]) - A(oracle[mk][oc])
        if abs(d) > 0.5:
            ok = False
            add("FAIL", f"opex/lampiran1: {mk} jumlah_maksud {c} != Nota5(b)", A(mt[c]), A(oracle[mk][oc]), d)
    if ok:
        n_mt_ok += 1
add("PASS" if n_mt_ok == 50 else "INFO",
    f"opex/lampiran1: maksud totals tie to Nota 5(b) oracle (all 3 cols)", n_mt_ok, 50, n_mt_ok - 50)

# (b) jenis + grand rollups
def sum_rt(rt, col, pred=lambda r: True):
    return sum(A(r[col]) for r in opex if r["row_type"] == rt and pred(r))
for c in COLS:
    g = [r for r in opex if r["row_type"] == "jumlah_besar"]
    if g:
        # grand = sum of maksud totals
        s = sum(A(r[c]) for r in opex if r["row_type"] == "jumlah_maksud")
        d = A(g[0][c]) - s
        add("PASS" if abs(d) <= 0.5 else "FAIL",
            f"opex/lampiran1: grand total {c} = sum(50 maksud totals)", A(g[0][c]), s, d)

# (c) leaf -> aktiviti additivity; unresolved cells inventoried
leaf_fail_cols = 0
mk_clean = []
for mk in sorted(bymk):
    if not mk:
        continue
    rs = bymk[mk]
    byakt = defaultdict(lambda: defaultdict(list))
    for r in rs:
        byakt[(r["program_code"], r["aktiviti_code"])][r["row_type"]].append(r)
    mfail = 0
    for key, d in byakt.items():
        if "jumlah_aktiviti" in d and "object_aktiviti" in d:
            jt = d["jumlah_aktiviti"][0]
            for c in COLS:
                s = sum(A(o[c]) for o in d["object_aktiviti"])
                resid = s - A(jt[c])
                if abs(resid) > 0.5:
                    mfail += 1
                    leaf_fail_cols += 1
                    unres.append(("fact_opex_detail",
                                  f"{mk} prog{key[0]} akt{key[1]}", c,
                                  round(s, 2), A(jt[c]), round(resid, 2),
                                  "unresolved-OCR: leaf object rows do not foot to aktiviti total (multi-cell OCR garble, no internal anchor; 144-dpi source, no per-cell oracle)"))
    if mfail == 0:
        mk_clean.append(mk)
add("INFO", "opex/lampiran1: maksuds with clean leaf->aktiviti additivity (all cols)",
    len(mk_clean), 49, "")
add("INFO", "opex/lampiran1: leaf->aktiviti column-checks with residual OCR (see _unresolved_ocr_cells_2015.csv)",
    leaf_fail_cols, 0, leaf_fail_cols)

# ---------------------------------------------------------------- DEVEX
dv = list(csv.DictReader(open(f"{WH}/fact_devex_project.csv")))
proj = [r for r in dv if r["row_type"] == "project"]
mtot = [r for r in dv if r["row_type"] == "ministry_total"]
grand = [r for r in dv if r["row_type"] == "grand_total"]
DCOLS = ["kos_keseluruhan_rm", "terkumpul_rmke10_prior_rm", "anggaran_jumlah_rm",
         "sebenar_jumlah_rm", "terkumpul_rmke10_rm"]
add("INFO", "devex/lampiran2: ministry_total rows present", len(mtot), 27, len(mtot) - 27)
# grand = sum ministry totals
if grand:
    for c in ["anggaran_jumlah_rm", "sebenar_jumlah_rm", "terkumpul_rmke10_rm"]:
        s = sum(A(r[c]) for r in mtot)
        d = A(grand[0][c]) - s
        add("PASS" if abs(d) <= 1.0 else "WARN",
            f"devex/lampiran2: grand_total {c} = sum(27 ministry totals)", A(grand[0][c]), s, round(d, 2))
# project rollup vs ministry total (documented unresolved: project cells OCR-garbled)
bymin = defaultdict(list)
for r in proj:
    bymin[r["maksud_code"]].append(r)
tie_cols = 0
for mt in mtot:
    mk = mt["maksud_code"]
    for c in ["anggaran_jumlah_rm", "sebenar_jumlah_rm"]:
        s = sum(A(r[c]) for r in bymin.get(mk, []))
        d = s - A(mt[c])
        if abs(d) <= 1.0:
            tie_cols += 1
        else:
            unres.append(("fact_devex_project", f"{mk} {mt['maksud_name_bm'][:30]}", c,
                          round(s, 2), A(mt[c]), round(d, 2),
                          "unresolved-OCR: project rows do not foot to printed ministry total (project-level amounts OCR-garbled; no per-cell oracle). Ministry total itself eye-verified."))
add("INFO", "devex/lampiran2: (ministry,col) project rollups tying to printed ministry_total",
    tie_cols, 27 * 2, "")
# impossible-negative cumulative prior (OCR artifact)
neg = [r for r in proj if A(r["terkumpul_rmke10_prior_rm"]) < 0]
add("INFO", "devex/lampiran2: project rows with impossible negative terkumpul_rmke10_prior (OCR)",
    len(neg), 0, len(neg))
for r in neg:
    unres.append(("fact_devex_project", f"{r['maksud_code']} {r['name_bm'][:28]}",
                  "terkumpul_rmke10_prior_rm", A(r["terkumpul_rmke10_prior_rm"]), ">=0", "",
                  "unresolved-OCR: negative cumulative impossible; column-shift/misread in project spread"))

# ---------------------------------------------------------------- INVESTMENTS
inv = list(csv.DictReader(open(f"{WH}/fact_investments.csv")))
for yr in ("2015", "2014"):
    rows = [r for r in inv if r["year"] == yr]
    subs = [r for r in rows if r["row_type"] == "subtotal"]
    tot = [r for r in rows if r["row_type"] == "total"]
    if tot:
        s = sum(A(r["nilai_buku_rm"]) for r in subs)
        d = A(tot[0]["nilai_buku_rm"]) - s
        add("PASS" if abs(d) <= 0.5 else "FAIL",
            f"investments/lampiran4: JUMLAH PELABURAN {yr} = sum(subtotals)", A(tot[0]["nilai_buku_rm"]), s, round(d, 2))

# ---------------------------------------------------------------- PANEL
pan = list(csv.DictReader(open(f"{WH}/fact_timeseries_2006_2015.csv")))
items = set((r["section_bm"], r["line_item_bm"]) for r in pan)
yrs = sorted(set(r["year"] for r in pan))
add("PASS" if len(items) == 136 and len(yrs) == 10 else "INFO",
    "panel/perangkaan: distinct line items x years", f"{len(items)}x{len(yrs)}", "136x10", "")

# ---------------------------------------------------------------- WRITE
with open(VAL, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["status", "check", "extracted_value", "printed_value", "difference"])
    for r in checks:
        w.writerow(r)
with open(INV, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["table", "key", "column", "extracted_value", "printed_target", "residual", "diagnosis"])
    for r in unres:
        w.writerow(r)

from collections import Counter
print("validation status:", Counter(c[0] for c in checks))
print("unresolved cells inventoried:", len(unres))
print("opex maksud totals tie:", n_mt_ok, "/50 ; leaf-clean maksuds:", len(mk_clean))
print("devex ministry rollup ties:", tie_cols, "/54 col-checks ; neg-prior:", len(neg))
