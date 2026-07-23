#!/usr/bin/env python3
"""CROSS-YEAR comparison: the 2016 volume's own 2016 figures vs the 2017 volume's
printed 2016 comparatives (read from /home/claude/pkkp/warehouse2017/*.csv, year=2016).
Every difference is reported as a RESTATEMENT finding (build does not fail on these).
Output: warehouse2016/_restatements_2016_vs_2017volume.csv + stdout list.
"""
import csv
import pandas as pd

WH16 = "/home/claude/pkkp/warehouse2016"
WH17 = "/home/claude/pkkp/warehouse2017"
findings = []
matched = {}


def rep(table, key, v16, v17, note=""):
    findings.append((table, key, v16, v17,
                     (v16 - v17) if (v16 is not None and v17 is not None) else None, note))


import re as _re

def norm_label(x):
    if pd.isna(x):
        return ""
    x = str(x)
    x = _re.sub(r"\s*\(Dahulu dikenali sebagai[^)]*\)", "", x)
    x = _re.sub(r"\*+$", "", x.strip())
    x = x.replace("Sdn.Bhd", "Sdn. Bhd").replace("Sdn. Bhd.", "Sdn. Bhd")
    x = _re.sub(r"\s*[–-]?\s*\(SAMB\.?\)\s*$", "", x)
    x = _re.sub(r"\s+", " ", x).strip()
    return x


def compare(table, name, keycols, valcol, y16=2016, y17=2016, f16=None, f17=None,
            val16col=None, val17col=None, tol=0.5):
    d16 = pd.read_csv(f"{WH16}/{name}")
    d17 = pd.read_csv(f"{WH17}/{name}")
    a = d16[d16.year == y16].copy() if "year" in d16.columns else d16.copy()
    b = d17[d17.year == y17].copy() if "year" in d17.columns else d17.copy()
    if f16 is not None:
        a = a[f16(a)]
    if f17 is not None:
        b = b[f17(b)]
    for kc in keycols:
        a[kc] = a[kc].map(norm_label)
        b[kc] = b[kc].map(norm_label)
    vc16 = val16col or valcol
    vc17 = val17col or valcol
    a = a.groupby(keycols, dropna=False)[vc16].sum(min_count=1)
    b = b.groupby(keycols, dropna=False)[vc17].sum(min_count=1)
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
# 2. Penyata Prestasi Kewangan (sebenar only)
compare("financial_performance", "fact_financial_performance.csv", ["line_code", "basis"], "amount_rm",
        f16=lambda d: d.basis == "sebenar", f17=lambda d: d.basis == "sebenar")
# 3. Cash statement
compare("cash_statement", "fact_cash_statement.csv", ["flow", "category_bm", "item_bm"], "amount_rm")
# 4. Memorandum summary
compare("memorandum_summary", "fact_memorandum.csv", ["line_item_bm"], "amount_rm")
# 5. Nota 9/10 debt summary
compare("debt_nota", "fact_debt.csv", ["item_bm", "kind"], "amount_rm")
# 6. Nota 5(a) revenue: 2016 volume sebenar vs 2017 volume sebenar_prior
compare("revenue_nota5a", "fact_revenue.csv", ["item_bm"], None, y16=2016, y17=2017,
        val16col="sebenar_rm", val17col="sebenar_prior_rm")
# 7. Nota 5 statement
compare("revenue_account_stmt", "fact_revenue_account_statement.csv", ["line_item_bm"], "sebenar_rm")
# 8. Nota 3 / 4 / 7 / 8 / 9 details
compare("cash_components_nota3", "fact_cash_components.csv", ["line_item_bm"], "amount_rm")
compare("investment_summary_nota4", "fact_investment_summary.csv",
        ["category_bm", "line_item_bm"], "amount_rm")
compare("trust_fund_detail_nota7", "fact_trust_fund_detail.csv",
        ["fund_group_bm", "fund_bm", "section_bm", "line_item_bm"], "amount_rm")
compare("memo_assets_nota8", "fact_memo_assets_detail.csv", ["section_bm", "line_item_bm"], "amount_rm")
compare("commitment_detail", "fact_commitment_detail.csv", ["parent_bm", "item_bm"], "amount_rm")
# 9. Trust accounts table: 2016 closing vs 2017 volume's opening
compare("trust_accounts_nota7", "fact_trust_accounts.csv", ["account_bm"], None,
        y16=2016, y17=2017, val16col="baki_akhir_rm", val17col="baki_awal_rm")
# 9b. Nota 6 loan account statement
compare("loan_account_stmt_nota6", "fact_loan_account_statement.csv",
        ["group_bm", "sub_bm", "line_item_bm"], "amount_rm")
# 10. Registers: 2016 rows in both volumes
compare("loans_receivable", "fact_loans_receivable.csv",
        ["section_bm", "category_bm", "peminjam_bm"], "baki_belum_selesai_rm")
compare("investments_register", "fact_investments.csv",
        ["section_bm", "entiti_bm"], "nilai_buku_rm")
compare("statutory_guarantees_register", "fact_statutory_guarantees.csv",
        ["jenis_jaminan_bm", "kategori_bm", "agensi_bm"], "jumlah_rm")
# 10b. Devex cumulative: 2016 volume terkumpul RMKe-11 to 31.12.2016 vs the 2017
# volume's printed 'terkumpul RMKe-11 hingga 31.12.2016' comparative, per maksud
da = pd.read_csv(f"{WH16}/fact_devex_maksud.csv").groupby("maksud_code")["terkumpul_rmke11_rm"].sum()
db = pd.read_csv(f"{WH17}/fact_devex_maksud.csv").groupby("maksud_code")["terkumpul_rmke11_prior_rm"].sum()
n_match = n_diff = 0
for k in sorted(set(da.index) | set(db.index), key=str):
    va = float(da[k]) if k in da.index else None
    vb = float(db[k]) if k in db.index else None
    if va is None or vb is None:
        rep("devex_cumulative_rmke11_2016", k, va, vb, "maksud present in only one volume")
        n_diff += 1
    elif abs(va - vb) > 0.5:
        rep("devex_cumulative_rmke11_2016", k, va, vb)
        n_diff += 1
    else:
        n_match += 1
matched["devex_cumulative_rmke11_2016"] = (n_match, n_diff)
# 11. Timeseries: 2016 column of the 2007-2016 panel vs the 2017 volume's 2008-2017 panel
d16t = pd.read_csv(f"{WH16}/fact_timeseries_2007_2016.csv")
d17t = pd.read_csv(f"{WH17}/fact_timeseries_2008_2017.csv")
a = d16t[d16t.year == 2016].set_index(["section_bm", "line_item_bm"])["amount_rm_juta"]
b = d17t[d17t.year == 2016].set_index(["section_bm", "line_item_bm"])["amount_rm_juta"]
n_match = n_diff = 0
for k in sorted(set(a.index) | set(b.index), key=str):
    va = float(a[k]) if k in a.index else None
    vb = float(b[k]) if k in b.index else None
    if va is None or vb is None:
        rep("timeseries_2016col", k, va, vb, "line item present in only one panel")
        n_diff += 1
    elif abs(va - vb) > 0.5:
        rep("timeseries_2016col", k, va, vb, "RM juta")
        n_diff += 1
    else:
        n_match += 1
matched["timeseries_2016col"] = (n_match, n_diff)
# overlap years 2008-2015 summarized
ov_diff = 0
ov = []
a_all = d16t.set_index(["section_bm", "line_item_bm", "year"])["amount_rm_juta"]
b_all = d17t.set_index(["section_bm", "line_item_bm", "year"])["amount_rm_juta"]
shared = set(a_all.index) & set(b_all.index)
for k in sorted(shared, key=str):
    if 2008 <= k[2] <= 2015 and abs(float(a_all[k]) - float(b_all[k])) > 0.5:
        ov_diff += 1
        ov.append((k, float(a_all[k]), float(b_all[k])))
print(f"timeseries overlap 2008-2015: {ov_diff} cell differences (RM juta) out of "
      f"{sum(1 for k in shared if 2008 <= k[2] <= 2015)} shared cells")
for k, va, vb in ov:
    rep("timeseries_overlap_2008_2015", k, va, vb, "RM juta")

with open(f"{WH16}/_restatements_2016_vs_2017volume.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["table", "key", "value_2016_volume", "value_2017_volume", "difference", "note"])
    w.writerows(findings)

print("\nper-table match/diff counts:")
for t, (m, d) in matched.items():
    print(f"  {t}: {m} match, {d} diff")
print(f"\nRESTATEMENT FINDINGS: {len(findings)}")
for t, k, va, vb, d, note in findings:
    fa = f"{va:,.2f}" if va is not None else "n/a"
    fb = f"{vb:,.2f}" if vb is not None else "n/a"
    fd = f"{d:,.2f}" if d is not None else ""
    print(f"  [{t}] {k}: 2016vol={fa} 2017vol={fb} diff={fd} {note}")
