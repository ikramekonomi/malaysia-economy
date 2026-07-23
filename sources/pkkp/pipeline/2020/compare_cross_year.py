#!/usr/bin/env python3
"""CROSS-YEAR comparison: the 2020 volume's own 2020 figures vs the 2021 volume's
printed 2020 comparatives (read from /home/claude/pkkp/warehouse2021/*.csv, year=2020).
Every difference is reported as a RESTATEMENT finding (build does not fail on these).
Output: warehouse2020/_restatements_2020_vs_2021volume.csv + stdout list.
"""
import csv
import pandas as pd

WH22 = "/home/claude/pkkp/warehouse2020"
WH23 = "/home/claude/pkkp/warehouse2021"
findings = []   # (table, key, val_2022_volume, val_2023_volume, diff, note)
matched = {}


def rep(table, key, v23, v24, note=""):
    findings.append((table, key, v23, v24,
                     (v23 - v24) if (v23 is not None and v24 is not None) else None, note))


import re as _re

def norm_label(x):
    """Normalise cosmetic label variants across the two volumes so that only
    substantive differences surface: collapse whitespace, strip footnote
    asterisks, strip '(Dahulu dikenali sebagai ...)' parentheticals, unify
    'Sdn.Bhd' spacing."""
    if pd.isna(x):
        return ""
    x = str(x)
    x = _re.sub(r"\s*\(Dahulu dikenali sebagai[^)]*\)", "", x)
    x = _re.sub(r"\*+$", "", x.strip())
    x = x.replace("Sdn.Bhd", "Sdn. Bhd").replace("Sdn. Bhd.", "Sdn. Bhd")
    # 2020 volume prints ministry acronym suffixes '(JPM)', '(KKM)' etc. and a few
    # English conjunctions ('And'); normalise so only substantive changes surface
    x = _re.sub(r"\s*\([A-Za-z0-9&./ -]{2,12}\)\s*$", "", x)
    x = _re.sub(r"\bAnd\b", "dan", x)
    x = _re.sub(r"\s+", " ", x).strip()
    return x


def compare(table, name, keycols, valcol, y23=2020, y24=2020, f23=None, f24=None,
            val23col=None, val24col=None, tol=0.5):
    d23 = pd.read_csv(f"{WH22}/{name}")
    d24 = pd.read_csv(f"{WH23}/{name}")
    a = d23[d23.year == y23].copy() if "year" in d23.columns else d23.copy()
    b = d24[d24.year == y24].copy() if "year" in d24.columns else d24.copy()
    if f23 is not None:
        a = a[f23(a)]
    if f24 is not None:
        b = b[f24(b)]
    for kc in keycols:
        a[kc] = a[kc].map(norm_label)
        b[kc] = b[kc].map(norm_label)
    vc23 = val23col or valcol
    vc24 = val24col or valcol
    a = a.groupby(keycols, dropna=False)[vc23].sum(min_count=1)
    b = b.groupby(keycols, dropna=False)[vc24].sum(min_count=1)
    n_match = n_diff = 0
    for k in sorted(set(a.index) | set(b.index), key=str):
        va = a.get(k)
        vb = b.get(k)
        va = None if va is None or pd.isna(va) else float(va)
        vb = None if vb is None or pd.isna(vb) else float(vb)
        if va is None or vb is None:
            note = "present in only one volume"
            if (va == 0.0 and vb is None) or (vb == 0.0 and va is None):
                note = "zero/nil row printed in only one volume (not a value restatement)"
            rep(table, k, va, vb, note)
            n_diff += 1
        elif abs(va - vb) > tol:
            rep(table, k, va, vb)
            n_diff += 1
        else:
            n_match += 1
    matched[table] = (n_match, n_diff)


# 1. Penyata Kedudukan Kewangan
compare("financial_position", "fact_financial_position.csv", ["line_item_bm"], "amount_rm")
# 2. Penyata Prestasi Kewangan (sebenar only; anggaran columns are not comparable —
# each volume prints its own budget-year estimate)
compare("financial_performance", "fact_financial_performance.csv", ["line_code", "basis"], "amount_rm",
        f23=lambda d: d.basis == "sebenar", f24=lambda d: d.basis == "sebenar")
# 3. Cash statement
compare("cash_statement", "fact_cash_statement.csv", ["flow", "category_bm", "item_bm"], "amount_rm")
# 4. Memorandum summary
compare("memorandum_summary", "fact_memorandum.csv", ["line_item_bm"], "amount_rm")
# 5. Nota 10 debt/commitments summary
compare("debt_nota10", "fact_debt.csv", ["item_bm", "kind"], "amount_rm")
# 6. Nota 5(a) revenue: 2022 volume sebenar_rm (y2022) vs 2023 volume sebenar_prior_rm (y2023 rows)
compare("revenue_nota5a", "fact_revenue.csv", ["item_bm"], None, y23=2020, y24=2021,
        val23col="sebenar_rm", val24col="sebenar_prior_rm")
# 7. Nota 5 statement
compare("revenue_account_stmt", "fact_revenue_account_statement.csv", ["line_item_bm"], "sebenar_rm",
        y23=2020, y24=2020)
# 8. Nota 3 / 4 / 7 / 9 / 10 details (2024 volume printed 2023 comparatives)
compare("cash_components_nota3", "fact_cash_components.csv", ["line_item_bm"], "amount_rm")
compare("investment_summary_nota4", "fact_investment_summary.csv",
        ["category_bm", "line_item_bm"], "amount_rm")
compare("trust_fund_detail_nota7", "fact_trust_fund_detail.csv",
        ["fund_group_bm", "fund_bm", "section_bm", "line_item_bm"], "amount_rm")
compare("memo_assets_nota9", "fact_memo_assets_detail.csv", ["section_bm", "line_item_bm"], "amount_rm")
compare("commitment_detail_nota10", "fact_commitment_detail.csv", ["parent_bm", "item_bm"], "amount_rm")
# 9. Trust accounts table: 2022 closing vs 2023 volume's opening (baki_awal, year=2023)
compare("trust_accounts_nota7", "fact_trust_accounts.csv", ["account_bm"], None,
        y23=2020, y24=2021, val23col="baki_akhir_rm", val24col="baki_awal_rm")
# 9b. Nota 6 loan account statement: 2022 rows in both volumes
compare("loan_account_stmt_nota6", "fact_loan_account_statement.csv",
        ["group_bm", "sub_bm", "line_item_bm"], "amount_rm")
# 9c. COVID-19 lampiran: cumulative-to-31.12.2022 per program in both volumes
d22c = pd.read_csv(f"{WH22}/fact_covid_fund_detail.csv")
d23c = pd.read_csv(f"{WH23}/fact_covid_fund_detail.csv")
a = d22c[d22c.projek_code.notna()].set_index("projek_code")["terkumpul_hingga_2020_rm"]
b = d23c[d23c.projek_code.notna()].set_index("projek_code")["terkumpul_hingga_2020_rm"] \
    if "terkumpul_hingga_2020_rm" in d23c.columns else None
n_match = n_diff = 0
if b is not None:
    for k in sorted(set(a.index.dropna()) | set(b.index.dropna()), key=str):
        va = float(a[k]) if k in a.index else None
        vb = float(b[k]) if k in b.index else None
        if va is None or vb is None:
            rep("covid_lampiran_cumulative2020", k, va, vb, "program present in only one volume")
            n_diff += 1
        elif abs(va - vb) > 0.5:
            rep("covid_lampiran_cumulative2020", k, va, vb)
            n_diff += 1
        else:
            n_match += 1
    matched["covid_lampiran_cumulative2020"] = (n_match, n_diff)
# 10. Registers (Lampiran): 2022 rows in both volumes
compare("loans_receivable", "fact_loans_receivable.csv",
        ["section_bm", "category_bm", "peminjam_bm"], "baki_belum_selesai_rm")
compare("investments_register", "fact_investments.csv",
        ["section_bm", "entiti_bm"], "nilai_buku_rm")
compare("pfi_register", "fact_pfi_liabilities.csv", ["agensi_bm", "tranche_bm"], "amaun_belum_selesai_rm")
compare("guarantees_register", "fact_guarantees.csv", ["agensi_bm"], "jumlah_rm",
        f23=lambda d: d.row_type.isin(["detail", "total"]),
        f24=lambda d: d.row_type.isin(["detail", "total"]))
compare("grants_register", "fact_guarantee_repayment_grants.csv",
        ["peruntukan_bm", "agensi_bm"], "amaun_penyaluran_rm")
compare("finance_leases_register", "fact_finance_leases.csv",
        ["sektor_bm", "kategori_bm", "perihal_bm"], "amaun_belum_selesai_rm")
compare("compensation_register", "fact_compensation_commitments.csv",
        ["kategori_bm", "perihal_bm"], "amaun_belum_selesai_rm",
        f23=lambda d: d.row_type != "listing")
compare("statutory_guarantees_register", "fact_statutory_guarantees.csv",
        ["jenis_jaminan_bm", "kategori_bm", "agensi_bm"], "jumlah_rm")
# 11. Timeseries: 2022 column of the 2008-2022 panel vs the 2023 volume's 2009-2023 panel
d23 = pd.read_csv(f"{WH22}/fact_timeseries_2011_2020.csv")
d24 = pd.read_csv(f"{WH23}/fact_timeseries_2012_2021.csv")
a = d23[d23.year == 2020].set_index(["section_bm", "line_item_bm"])["amount_rm_juta"]
b = d24[d24.year == 2020].set_index(["section_bm", "line_item_bm"])["amount_rm_juta"]
n_match = n_diff = 0
for k in sorted(set(a.index) | set(b.index), key=str):
    va = float(a[k]) if k in a.index else None
    vb = float(b[k]) if k in b.index else None
    if va is None or vb is None:
        rep("timeseries_2020col", k, va, vb, "line item present in only one panel")
        n_diff += 1
    elif abs(va - vb) > 0.5:   # RM juta
        rep("timeseries_2020col", k, va, vb, "RM juta")
        n_diff += 1
    else:
        n_match += 1
matched["timeseries_2020col"] = (n_match, n_diff)
# overlap years 2009-2021 summarized
ov_diff = 0
ov = []
a_all = d23.set_index(["section_bm", "line_item_bm", "year"])["amount_rm_juta"]
b_all = d24.set_index(["section_bm", "line_item_bm", "year"])["amount_rm_juta"]
for k in sorted(set(a_all.index) & set(b_all.index), key=str):
    if 2012 <= k[2] <= 2019 and abs(float(a_all[k]) - float(b_all[k])) > 0.5:
        ov_diff += 1
        ov.append((k, float(a_all[k]), float(b_all[k])))
print(f"timeseries overlap 2009-2021: {ov_diff} cell differences (RM juta) out of "
      f"{sum(1 for k in (set(a_all.index) & set(b_all.index)) if 2012 <= k[2] <= 2019)} shared cells")
for k, va, vb in ov:
    rep("timeseries_overlap_2012_2019", k, va, vb, "RM juta")

with open(f"{WH22}/_restatements_2020_vs_2021volume.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["table", "key", "value_2020_volume", "value_2021_volume", "difference", "note"])
    w.writerows(findings)

print("\nper-table match/diff counts:")
for t, (m, d) in matched.items():
    print(f"  {t}: {m} match, {d} diff")
print(f"\nRESTATEMENT FINDINGS: {len(findings)}")
for t, k, va, vb, d, note in findings:
    fa = f"{va:,.2f}" if va is not None else "n/a"
    fb = f"{vb:,.2f}" if vb is not None else "n/a"
    fd = f"{d:,.2f}" if d is not None else ""
    print(f"  [{t}] {k}: 2020vol={fa} 2021vol={fb} diff={fd} {note}")
