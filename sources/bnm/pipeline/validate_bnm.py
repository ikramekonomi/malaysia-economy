#!/usr/bin/env python3
"""Validate the BNM fiscal tables against themselves and the rest of the warehouse.

  V1 internal: per-quarter current surplus/deficit == revenue - opex (table 3.1);
     annual rows (period='') vs sum of quarters where both exist
  V2 cross-source (the triangulation): BNM annual sums vs audited PKKP
     (revenue, opex, gross DE), FY2010-FY2024 — tolerance RM1 million
     (BNM serves RM million floats; PKKP is sen-exact)
  V3 FY2025 measured (sum of quarters) vs MOF official revised estimate and the
     warehouse signature nowcast — reported as INFO findings, not pass/fail
Writes data/_validation_bnm.csv. Discrepancies reported, never corrected.
"""
import csv
import os
from collections import defaultdict

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
ROOT = os.path.join(HERE, "..", "..", "..")
DB = os.path.join(ROOT, "sources", "pkkp", "pkkp.duckdb")
OFF = os.path.join(ROOT, "sources", "mof-fiscal-outlook", "data", "fiscal_outlook_headline.csv")
NOW = os.path.join(ROOT, "curated", "forecast", "fact_nowcast_2025.csv")

rows = list(csv.DictReader(open(os.path.join(DATA, "msb_3_1.csv"))))
out = []


def rec(check, scope, expected, got, status=None, tol=0.0):
    ok = status or ("PASS" if abs(float(expected) - float(got)) <= tol else "FAIL")
    out.append([check, scope, expected, got, ok])


q = defaultdict(dict)
ann = {}
for r in rows:
    y = int(r["year_dt"])
    if r["period"] in ("1Q", "2Q", "3Q", "4Q"):
        q[y][r["period"]] = r
    elif r["period"] == "":
        ann[y] = r

# V1 internal
for y in sorted(q):
    for p, r in q[y].items():
        if r["cur_bud_rev"] and r["cur_bud_exp"] and r["cur_bud_sur_def"]:
            rec("V1_quarter_identity", f"{y}{p}", round(float(r["cur_bud_rev"]) - float(r["cur_bud_exp"]), 2),
                round(float(r["cur_bud_sur_def"]), 2), tol=1.01)  # BNM serves the balance rounded to RM1 million
for y in sorted(set(ann) & set(q)):
    if len(q[y]) == 4 and ann[y]["cur_bud_rev"]:
        rec("V1_annual_vs_quarters", f"{y} revenue", round(float(ann[y]["cur_bud_rev"]), 1),
            round(sum(float(q[y][p]["cur_bud_rev"]) for p in q[y]), 1), tol=1.0)

# V2 vs PKKP audited
con = duckdb.connect(DB, read_only=True)
pk = {int(r[0]): (float(r[1]), float(r[2])) for r in con.sql("""
    SELECT year, max(CASE WHEN line_code='revenue' THEN amount_rm END)/1e6,
           max(CASE WHEN line_code='opex' THEN amount_rm END)/1e6
    FROM fact_financial_performance WHERE basis='sebenar'
    AND source_file ILIKE year || '_PENYATA%' GROUP BY year""").fetchall()}
# gross DE on the PERFORMANCE-STATEMENT basis (line devex): BNM follows that
# presentation, which differs from the by-vote devex register in 2019-2020 - an
# intra-PKKP presentational difference already visible in the warehouse
pk_de = {int(r[0]): float(r[1]) for r in con.sql("""
    SELECT year, max(CASE WHEN line_code='devex' THEN amount_rm END)/1e6
    FROM fact_financial_performance WHERE basis='sebenar'
    AND source_file ILIKE year || '_PENYATA%' GROUP BY year""").fetchall()}
for y in range(2010, 2025):
    if y not in q or len(q[y]) < 4:
        continue
    brev = sum(float(q[y][p]["cur_bud_rev"]) for p in q[y])
    bexp = sum(float(q[y][p]["cur_bud_exp"]) for p in q[y])
    bde = sum(float(q[y][p]["dev_exp_gro_dev_exp"]) for p in q[y])
    rec("V2_vs_pkkp", f"{y} revenue (RM mil)", round(pk[y][0], 1), round(brev, 1), tol=1.0)
    rec("V2_vs_pkkp", f"{y} opex (RM mil)", round(pk[y][1], 1), round(bexp, 1), tol=1.0)
    rec("V2_vs_pkkp", f"{y} gross DE (RM mil)", round(pk_de[y], 1), round(bde, 1), tol=2.0)

# V3 FY2025 measured vs official/nowcast
off = {}
for r in csv.DictReader(open(OFF)):
    k = (int(r["edition_year"]), int(r["target_year"]), r["line"])
    off[k] = float(r["amount_rm_bil"])
m25 = {k: sum(float(q[2025][p][k]) for p in q[2025]) / 1e3 for k in
       ("cur_bud_rev", "cur_bud_exp", "dev_exp_gro_dev_exp", "dev_exp_les_loa_rec")}
deficit25 = (m25["cur_bud_rev"] - m25["cur_bud_exp"]) - (m25["dev_exp_gro_dev_exp"] - m25["dev_exp_les_loa_rec"])
now_mid = None
for r in csv.DictReader(open(NOW)):
    if r["maksud_code"] == "TOTAL_OE":
        now_mid = float(r["expected_mid_rm"]) / 1e9
rec("V3_fy2025_measured", "revenue RM bil: BNM measured vs MOF revised",
    off[(2026, 2025, "revenue")], round(m25["cur_bud_rev"], 3), status="INFO")
rec("V3_fy2025_measured", "opex RM bil: BNM measured vs MOF revised",
    off[(2026, 2025, "operating_expenditure")], round(m25["cur_bud_exp"], 3), status="INFO")
rec("V3_fy2025_measured", "gross DE RM bil: BNM measured vs MOF revised",
    off[(2026, 2025, "development_expenditure")], round(m25["dev_exp_gro_dev_exp"], 3), status="INFO")
rec("V3_fy2025_measured", "overall deficit RM bil: BNM measured vs MOF revised",
    off[(2026, 2025, "overall_deficit")], round(deficit25, 3), status="INFO")
rec("V3_fy2025_measured", "opex RM bil: BNM measured vs signature-nowcast mid",
    round(now_mid, 3), round(m25["cur_bud_exp"], 3), status="INFO")

dest = os.path.join(DATA, "_validation_bnm.csv")
with open(dest, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["check", "scope", "expected", "got", "status"])
    w.writerows(out)
fails = [r for r in out if r[-1] == "FAIL"]
print(f"{len(out)} checks, {len(fails)} FAIL -> {dest}")
for r in fails[:15]:
    print("FAIL:", r)
for r in out:
    if r[0] == "V3_fy2025_measured":
        print("INFO:", r[1], "| official/model:", r[2], "| measured:", r[3])
