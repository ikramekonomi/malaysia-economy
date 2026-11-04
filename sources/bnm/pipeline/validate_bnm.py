#!/usr/bin/env python3
"""Validate the BNM MSB tables against themselves and the rest of the warehouse.

  V1 internal: per-quarter current surplus/deficit == revenue - opex (table 3.1);
     annual rows (period='') vs sum of quarters where both exist
  V2 cross-source (the triangulation): BNM annual sums vs audited PKKP
     (revenue, opex, gross DE), FY2010-FY2024 — tolerance RM1 million
     (BNM serves RM million floats; PKKP is sen-exact)
  V3 FY2025 measured (sum of quarters) vs MOF official revised estimate —
     reported as INFO findings, not pass/fail. (The comparison with our own model
     nowcast moved out of source validation with the model, to apps/models/.)
  V4 component-vs-total identities inside each table that prints subtotals
     (3.1.1-3.1.6 and, where present, the wider MSB tables from
     fetch_bnm_msb_wide.py: 1.1 reserve money, 1.3 monetary aggregates,
     3.8 reserves)
  V5 grain consistency for the fiscal tables (the 3.1.x set serves quarterly +
     annual, no monthly): annual == sum of quarters for flows, annual == 4Q for
     stocks — across every numeric column
  V6 grain consistency for the wider monthly tables: annual row == December for
     stocks / end-period columns, annual == sum of months for flows (2.9/2.10)

Identity breaks beyond printed-rounding tolerance are recorded with status
SOURCE_DIVERGENCE (the CSVs are the API verbatim, so the inconsistency is the
source's own — a finding, kept as printed). FAIL is reserved for genuine
pipeline/extraction problems. Writes data/_validation_bnm.csv. Discrepancies
reported, never corrected.
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

# V3 FY2025 measured vs official
off = {}
for r in csv.DictReader(open(OFF)):
    k = (int(r["edition_year"]), int(r["target_year"]), r["line"])
    off[k] = float(r["amount_rm_bil"])
m25 = {k: sum(float(q[2025][p][k]) for p in q[2025]) / 1e3 for k in
       ("cur_bud_rev", "cur_bud_exp", "dev_exp_gro_dev_exp", "dev_exp_les_loa_rec")}
deficit25 = (m25["cur_bud_rev"] - m25["cur_bud_exp"]) - (m25["dev_exp_gro_dev_exp"] - m25["dev_exp_les_loa_rec"])
rec("V3_fy2025_measured", "revenue RM bil: BNM measured vs MOF revised",
    off[(2026, 2025, "revenue")], round(m25["cur_bud_rev"], 3), status="INFO")
rec("V3_fy2025_measured", "opex RM bil: BNM measured vs MOF revised",
    off[(2026, 2025, "operating_expenditure")], round(m25["cur_bud_exp"], 3), status="INFO")
rec("V3_fy2025_measured", "gross DE RM bil: BNM measured vs MOF revised",
    off[(2026, 2025, "development_expenditure")], round(m25["dev_exp_gro_dev_exp"], 3), status="INFO")
rec("V3_fy2025_measured", "overall deficit RM bil: BNM measured vs MOF revised",
    off[(2026, 2025, "overall_deficit")], round(deficit25, 3), status="INFO")

# ---------------------------------------------------------------------------
# V4-V6: identities + grain consistency, tables from both fetchers (additive)
# ---------------------------------------------------------------------------
TOL = 2.5  # RM million; BNM prints components rounded to RM1m, so sums of many
           # components can drift by a couple of million — beyond that it is the
           # source's own inconsistency (SOURCE_DIVERGENCE), kept as printed


def load(name):
    path = os.path.join(DATA, f"msb_{name.replace('.', '_')}.csv")
    if not os.path.exists(path):
        return []
    return list(csv.DictReader(open(path)))


def fl(v):
    return None if v in (None, "", "None") else float(v)


def rec_id(check, scope, expected, got, tol=TOL):
    ok = "PASS" if abs(expected - got) <= tol else "SOURCE_DIVERGENCE"
    out.append([check, scope, round(expected, 3), round(got, 3), ok])


def period_of(r):
    # fiscal tables: period (1Q..4Q / '' = annual); monthly tables: month_dt / ''
    if "period" in r:
        return r["period"] or "annual"
    return r.get("month_dt") or "annual"


# V4: component-vs-total identities (skip a row when the total or every
# component is blank — era differences, not divergences)
IDENTITIES = {  # table -> [(name, total_col, [component_cols])]
    "3.1.1": [
        ("direct_tax_subtotal", "tax_rev_dir_tax_sub_tot",
         ["tax_rev_dir_tax_com_inc_tax", "tax_rev_dir_tax_ind_inc_tax",
          "tax_rev_dir_tax_pet_inc_tax", "tax_rev_dir_tax_sta_dut", "tax_rev_dir_tax_oth"]),
        ("indirect_tax_subtotal", "tax_rev_ind_tax_sub_tot",
         ["tax_rev_ind_tax_exc_dut", "tax_rev_ind_tax_exp_dut", "tax_rev_ind_tax_imp_dut",
          "tax_rev_ind_tax_goo_and_ser_tax", "tax_rev_ind_tax_sal_tax",
          "tax_rev_ind_tax_ser_tax", "tax_rev_ind_tax_oth"]),
        ("nontax_subtotal", "non_tax_rev_sub_tot",
         ["non_tax_rev_int_and_ret_on_inv", "non_tax_rev_lic_and_per",
          "non_tax_rev_pet_roy", "non_tax_rev_oth"]),
        ("revenue_total", "total",
         ["tax_rev_dir_tax_sub_tot", "tax_rev_ind_tax_sub_tot",
          "non_tax_rev_sub_tot", "non_rev_rec"]),
    ],
    "3.1.2": [
        ("debt_service_total", "deb_ser_cha_tot", ["deb_ser_cha_dom", "deb_ser_cha_ext"]),
        ("opex_total", "total",
         ["emoluments", "pen_and_gra", "deb_ser_cha_tot", "sup_and_ser",
          "subsidies", "ass_acq", "gra_and_tra", "oth_exp"]),
    ],
    "3.1.3": [
        ("economic_subtotal", "eco_ser_sub_tot",
         ["eco_ser_agr_and_rur_dev", "eco_ser_pub_uti", "eco_ser_tra",
          "eco_ser_tra_and_ind", "eco_ser_oth"]),
        ("social_subtotal", "soc_ser_sub_tot",
         ["soc_ser_edu", "soc_ser_hea", "soc_ser_hou", "soc_ser_soc_and_com_ser"]),
        ("devex_total", "total",
         ["def_and_sec", "gen_adm", "eco_ser_sub_tot", "soc_ser_sub_tot"]),
    ],
    "3.1.4": [
        ("mgs_maturity_subtotal", "dom_deb_mas_gov_sec_sub_tot",
         ["dom_deb_mas_gov_sec_les_thr_yr", "dom_deb_mas_gov_sec_thr_to_fiv_yr",
          "dom_deb_mas_gov_sec_fiv_to_ten_yr", "dom_deb_mas_gov_sec_ten_to_fif_yr",
          "dom_deb_mas_gov_sec_abo_fif_yr"]),
        ("mgii_maturity_subtotal", "dom_deb_mas_gov_inv_sub_tot",
         ["dom_deb_mas_gov_inv_les_thr_yr", "dom_deb_mas_gov_inv_thr_to_fiv_yr",
          "dom_deb_mas_gov_inv_fiv_to_ten_yr", "dom_deb_mas_gov_inv_ten_to_fif_yr",
          "dom_deb_mas_gov_inv_fif_yr"]),
        ("domestic_debt_subtotal", "dom_deb_sub_tot",
         ["dom_deb_mas_gov_sec_sub_tot", "dom_deb_mas_gov_inv_sub_tot",
          "dom_deb_tre_bil", "dom_deb_oth_loa"]),
        ("external_debt_subtotal", "ext_deb_sub_tot",
         ["ext_deb_for_cur_deb_mar_loa", "ext_deb_for_cur_deb_pro_loa",
          "ext_deb_non_res_hol"]),
        ("debt_total", "tot", ["dom_deb_sub_tot", "ext_deb_sub_tot"]),
    ],
    "3.1.5": [
        ("mgs_holder_subtotal", "mgs_sub_tot",
         ["mgs_fin_sec_bnm", "mgs_fin_sec_ban_ins", "mgs_fin_sec_dev_fin_ins",
          "mgs_fin_sec_non_ban_fin_ins", "mgs_soc_sec_emp_pro_fun",
          "mgs_soc_sec_ins_kwap", "mgs_ins_com", "mgs_for_hol", "mgs_oth"]),
        ("mgii_holder_subtotal", "mgii_sub_tot",
         ["mgii_fin_sec_bnm", "mgii_fin_sec_ban_ins", "mgii_fin_sec_dev_fin_ins",
          "mgii_fin_sec_non_ban_fin_ins", "mgii_soc_sec_emp_pro_fun",
          "mgii_soc_sec_kwap", "mgii_ins_com", "mgii_for_hol", "mgii_oth"]),
        ("trebil_holder_subtotal", "tre_bil_sub_tot",
         ["tre_bil_bnm", "tre_bil_ban_ins", "tre_bil_for_hol", "tre_bil_oth"]),
        ("holders_total", "tot",
         ["mgs_sub_tot", "mgii_sub_tot", "tre_bil_sub_tot", "oth_loan"]),
    ],
    "3.1.6": [
        ("currency_total", "out_fed_gov_deb_by_cur_tot",
         ["out_fed_gov_deb_by_cur_rm", "out_fed_gov_deb_by_cur_usd",
          "out_fed_gov_deb_by_cur_yen", "out_fed_gov_deb_by_cur_oth"]),
    ],
    # wider tables (fetch_bnm_msb_wide.py)
    "1.1": [
        ("reserve_money_components", "tot_res_mon",
         ["com_res_mon_cur_in_cir", "com_res_mon_req_res",
          "com_res_mon_exc_res", "com_res_mon_dep_pri_sec"]),
        ("reserve_money_factors", "tot_res_mon",
         ["net_claim_gov_tot", "cla_pri_sec", "ext_ope", "oth_infl"]),
    ],
    "1.3": [
        ("m1", "m_one_tot", ["cur_in_cir", "dem_dep"]),
        ("m2", "m_two_tot",
         ["m_one_tot", "nqm_fix_dep", "nqm_sav_dep", "nqm_nid", "nqm_rep",
          "nqm_for_cur_dep", "nqm_oth_dep"]),
        ("m3", "m_thr_tot", ["m_two_tot", "dep_pla_oth_ban_ins"]),
    ],
    "3.8": [
        ("net_international_reserves", "bnm_net_int_res",
         ["bnm_gro_int_res_tot", "-bnm_ext_lia"]),
    ],
}
for table, specs in IDENTITIES.items():
    trs = load(table)
    for name, total_col, comps in specs:
        n = 0
        for r in trs:
            t = fl(r.get(total_col))
            if t is None:
                continue
            vals = []
            for c in comps:
                sign = -1.0 if c.startswith("-") else 1.0
                vals.append((sign, fl(r.get(c.lstrip("-")))))
            if all(v is None for _, v in vals):
                continue
            s = sum(sign * v for sign, v in vals if v is not None)
            n += 1
            if abs(s - t) > TOL:
                rec_id(f"V4_{table}_{name}", f"{r['year_dt']} {period_of(r)}", t, s)
        if n:
            passed = n - len([o for o in out if o[0] == f"V4_{table}_{name}"])
            out.append([f"V4_{table}_{name}", f"all rows ({n} checked)", n, passed,
                        "PASS" if passed == n else "SOURCE_DIVERGENCE"])

# V5: fiscal-table grain consistency (quarterly vs annual; the 3.1.x tables
# serve no monthly rows — checked against the API 2026-07-31)
FISCAL_GRAIN = {"3.1": "flow", "3.1.1": "flow", "3.1.2": "flow", "3.1.3": "flow",
                "3.1.4": "stock", "3.1.5": "stock", "3.1.6": "stock"}
for table, kind in FISCAL_GRAIN.items():
    trs = load(table)
    qq, aa = defaultdict(dict), {}
    num_cols = [c for c in (trs[0] if trs else {})
                if c not in ("year_dt", "period", "endpoint", "retrieved_date",
                             "api_last_updated", "_year_requested")]
    for r in trs:
        y = int(r["year_dt"])
        if r["period"] in ("1Q", "2Q", "3Q", "4Q"):
            qq[y][r["period"]] = r
        elif r["period"] == "":
            aa[y] = r
    n = div = 0
    for y in sorted(set(aa) & set(qq)):
        for c in num_cols:
            a = fl(aa[y].get(c))
            if a is None:
                continue
            if kind == "flow":
                if len(qq[y]) < 4 or any(fl(qq[y][p].get(c)) is None for p in qq[y]):
                    continue
                s = sum(fl(qq[y][p][c]) for p in qq[y])
            else:
                s = fl(qq[y].get("4Q", {}).get(c))
                if s is None:
                    continue
            n += 1
            if abs(s - a) > TOL:
                div += 1
                rec_id(f"V5_{table}_annual_vs_quarters", f"{y} {c}", a, s)
    if n:
        out.append([f"V5_{table}_annual_vs_quarters", f"all cols ({n} checked)", n,
                    n - div, "PASS" if div == 0 else "SOURCE_DIVERGENCE"])

# V6: monthly-table grain consistency (annual row vs the 12 months)
# stocks/end-period: annual == December; flows: annual == sum of months
MONTHLY_GRAIN = {"1.1": "stock", "1.2": "stock", "1.4": "stock", "1.5": "stock",
                 "2.9": "flow", "2.10": "flow", "3.8": "stock",
                 # 2.6 exchange rates: only the end-period (_ep) columns are a stock;
                 # the annual average (_ap) columns are not December values
                 "2.6": "stock_ep_only"}
for table, kind in MONTHLY_GRAIN.items():
    trs = load(table)
    if not trs:
        continue
    num_cols = [c for c in trs[0]
                if c not in ("year_dt", "month_dt", "period", "endpoint",
                             "retrieved_date", "api_last_updated", "_year_requested")]
    if kind == "stock_ep_only":
        kind = "stock"
        num_cols = [c for c in num_cols if c.endswith("_ep")]
    mm, aa = defaultdict(dict), {}
    for r in trs:
        y = int(r["year_dt"])
        if r.get("month_dt"):
            mm[y][int(float(r["month_dt"]))] = r
        else:
            aa[y] = r
    n = div = 0
    for y in sorted(set(aa) & set(mm)):
        if len(mm[y]) < 12:
            continue
        for c in num_cols:
            a = fl(aa[y].get(c))
            if a is None:
                continue
            if kind == "flow":
                if any(fl(mm[y][m].get(c)) is None for m in mm[y]):
                    continue
                s = sum(fl(mm[y][m][c]) for m in mm[y])
            else:
                s = fl(mm[y][12].get(c))
                if s is None:
                    continue
            n += 1
            if abs(s - a) > TOL:
                div += 1
                rec_id(f"V6_{table}_annual_vs_months", f"{y} {c}", a, s)
    if n:
        out.append([f"V6_{table}_annual_vs_months", f"all cols ({n} checked)", n,
                    n - div, "PASS" if div == 0 else "SOURCE_DIVERGENCE"])

# V7: banking-system tables served with an institution-type breakdown
# (Commercial / Islamic / Investment banks + a printed Total row per month):
# Total row == sum of the three institution rows, every numeric column
META_COLS = {"year_dt", "month_dt", "period", "endpoint", "retrieved_date",
             "api_last_updated", "_year_requested"}
for table in ("1.7", "1.9", "1.10", "1.12", "1.14", "1.18"):
    trs = load(table)
    if not trs:
        continue
    dim_col = next((c for c in trs[0] if c not in META_COLS and
                    any(not r[c].replace(".", "").replace("-", "").isdigit()
                        for r in trs[:8] if r[c])), None)
    if dim_col is None:
        continue
    num_cols = [c for c in trs[0] if c not in META_COLS and c != dim_col]
    groups = defaultdict(list)
    for r in trs:
        groups[(r["year_dt"], r.get("month_dt") or "annual")].append(r)
    n = div = 0
    for key, rs in groups.items():
        tot_row = next((r for r in rs if "Total" in r[dim_col]), None)
        parts = [r for r in rs if "Total" not in r[dim_col]]
        if tot_row is None or not parts:
            continue
        for c in num_cols:
            t = fl(tot_row.get(c))
            vals = [fl(p.get(c)) for p in parts]
            if t is None or all(v is None for v in vals):
                continue
            s = sum(v for v in vals if v is not None)
            n += 1
            if abs(s - t) > TOL:
                div += 1
                rec_id(f"V7_{table}_bank_type_total", f"{key[0]} m{key[1]} {c}", t, s)
    if n:
        out.append([f"V7_{table}_bank_type_total", f"all cols ({n} checked)", n,
                    n - div, "PASS" if div == 0 else "SOURCE_DIVERGENCE"])

dest = os.path.join(DATA, "_validation_bnm.csv")
with open(dest, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["check", "scope", "expected", "got", "status"])
    w.writerows(out)
fails = [r for r in out if r[-1] == "FAIL"]
divs = [r for r in out if r[-1] == "SOURCE_DIVERGENCE"]
print(f"{len(out)} checks, {len(fails)} FAIL, {len(divs)} SOURCE_DIVERGENCE -> {dest}")
for r in fails[:15]:
    print("FAIL:", r)
for r in divs[:40]:
    print("SOURCE_DIVERGENCE:", r)
for r in out:
    if r[0] == "V3_fy2025_measured":
        print("INFO:", r[1], "| official/model:", r[2], "| measured:", r[3])
