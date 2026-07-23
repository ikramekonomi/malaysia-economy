#!/usr/bin/env python3
"""CROSS-YEAR comparison: the 2019 volume's own 2019 figures vs the 2020 volume's
printed 2019 comparatives (read from /home/claude/pkkp/warehouse2020/*.csv, year=2019).
Every difference is reported as a RESTATEMENT finding (build does not fail on these).
Output: warehouse2019/_restatements_2019_vs_2020volume.csv + stdout list.
"""
import csv
import pandas as pd

WH19 = "/home/claude/pkkp/warehouse2019"
WH20 = "/home/claude/pkkp/warehouse2020"
findings = []   # (table, key, val_2019_volume, val_2020_volume, diff, note)
matched = {}


def rep(table, key, v19, v20, note=""):
    findings.append((table, key, v19, v20,
                     (v19 - v20) if (v19 is not None and v20 is not None) else None, note))


import re as _re

# Cosmetic label renames between the 2019 and 2020 volumes (verified value-identical
# or exact regroupings; mapped so only substantive differences surface):
RENAME = {
    # Nota 7(a)(ii): category renamed; spelling fix
    "KUMPULAN WANG YANG LAIN": "PELBAGAI KUMPULAN WANG",
    "Stor dan Woksyop Belum Diuntukkan": "Stor dan Woksyop Belum Diperuntukkan",
    "Kumpulan Wang Amanah Fi Jaminan": "Kumpulan Wang Amanah Fi Jaminan - Urusniaga",
    # Nota 7(c): 2020 volume prefixes deposit items with 'Deposit ' and renames one
    "Kawalan Wang Tak Dituntut": "Deposit Kawalan Wang Tak Dituntut",
    "Wang Jaminan Pelaksanaan": "Deposit Wang Jaminan Pelaksanaan",
    "Mahkamah Tinggi": "Deposit Mahkamah Tinggi",
    "Wang Tak Dituntut": "Deposit Wang Tak Dituntut",
    "Terimaan Yang Tidak Diperuntukkan": "Akaun Terimaan Tidak Diperuntukkan",
    # Nota 7(c) Pelarasan: 2020 volume splits Pindahan Dana Elektronik Terbatal into
    # 3 lines (base/JPA Pencen/JHEV); aggregate for comparison
    "Deposit Pindahan Dana Elektronik Terbatal - JPA Pencen": "Pindahan Dana Elektronik Terbatal",
    "Deposit Pindahan Dana Elektronik Terbatal - JHEV": "Pindahan Dana Elektronik Terbatal",
    "Deposit Pindahan Dana Elektronik Terbatal": "Pindahan Dana Elektronik Terbatal",
    # Nota 7(c) Am: 2020 volume breaks Deposit Imigresen OUT of Pelbagai Deposit Am
    # (2019 Pelbagai 1,014,065,291 = 2020's Pelbagai 726,774,584 + Imigresen
    # 287,290,707 exactly); aggregate for comparison
    "Deposit Imigresen": "Pelbagai Deposit Am",
    # Nota 7(b): 2020 volume folds two named 2019 accounts into Pelbagai Amanah Am
    # (2019: 1,507,942,672 + IPS 464,195,942 + Pembetungan 427,040,883 =
    # 2020's Pelbagai Amanah Am 2,399,179,497 exactly); aggregate for comparison
    "Akaun Amanah Inisiatif Pembiayaan Swasta": "Pelbagai Amanah Am",
    "Akaun Amanah Membangun/Menaiktaraf Sistem Pembetungan untuk Pembangunan Baru": "Pelbagai Amanah Am",
}


def norm_label(x):
    """Normalise cosmetic label variants across the two volumes so that only
    substantive differences surface: collapse whitespace, strip footnote
    asterisks, strip '(Dahulu dikenali sebagai ...)' parentheticals, unify
    'Sdn Bhd' spellings and acronym suffixes."""
    if pd.isna(x):
        return ""
    x = str(x)
    x = _re.sub(r"\s*\(Dahulu dikenali sebagai[^)]*\)", "", x)
    x = _re.sub(r"\*+$", "", x.strip())
    x = x.replace("Sdn.Bhd", "Sdn. Bhd").replace("Sdn. Bhd.", "Sdn. Bhd")
    x = _re.sub(r"\bSdn Bhd\b", "Sdn. Bhd", x)
    # ministry acronym suffixes '(JPM)', '(KKM)' etc. and English conjunctions
    x = _re.sub(r"\s*\([A-Za-z0-9&./ -]{2,12}\)\s*$", "", x)
    x = _re.sub(r"\bAnd\b", "dan", x)
    x = _re.sub(r"\s+", " ", x).strip()
    x = RENAME.get(x, x)
    return x


def compare(table, name, keycols, valcol, y19=2019, y20=2019, f19=None, f20=None,
            val19col=None, val20col=None, tol=0.5):
    d19 = pd.read_csv(f"{WH19}/{name}")
    d20 = pd.read_csv(f"{WH20}/{name}")
    a = d19[d19.year == y19].copy() if "year" in d19.columns else d19.copy()
    b = d20[d20.year == y20].copy() if "year" in d20.columns else d20.copy()
    if f19 is not None:
        a = a[f19(a)]
    if f20 is not None:
        b = b[f20(b)]
    for kc in keycols:
        if kc not in a.columns:
            a[kc] = ""
        if kc not in b.columns:
            b[kc] = ""
        a[kc] = a[kc].map(norm_label)
        b[kc] = b[kc].map(norm_label)
    vc19 = val19col or valcol
    vc20 = val20col or valcol
    a = a.groupby(keycols, dropna=False)[vc19].sum(min_count=1)
    b = b.groupby(keycols, dropna=False)[vc20].sum(min_count=1)
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
        f19=lambda d: d.basis == "sebenar", f20=lambda d: d.basis == "sebenar")
# 3. Cash statement
compare("cash_statement", "fact_cash_statement.csv", ["flow", "category_bm", "item_bm"], "amount_rm")
# 4. Memorandum summary
compare("memorandum_summary", "fact_memorandum.csv", ["line_item_bm"], "amount_rm")
# 5. Nota 10 debt/commitments summary
compare("debt_nota10", "fact_debt.csv", ["item_bm", "kind"], "amount_rm")
# 6. Nota 5(a) revenue: 2019 volume sebenar_rm vs 2020 volume sebenar_prior_rm
compare("revenue_nota5a", "fact_revenue.csv", ["item_bm"], None, y19=2019, y20=2020,
        val19col="sebenar_rm", val20col="sebenar_prior_rm")
# 7. Nota 5 statement
compare("revenue_account_stmt", "fact_revenue_account_statement.csv", ["line_item_bm"], "sebenar_rm")
# 8. Nota 3 / 4 / 7 / 9 / 10 details
compare("cash_components_nota3", "fact_cash_components.csv", ["line_item_bm"], "amount_rm")
compare("investment_summary_nota4", "fact_investment_summary.csv",
        ["category_bm", "line_item_bm"], "amount_rm")
compare("trust_fund_detail_nota7", "fact_trust_fund_detail.csv",
        ["fund_group_bm", "fund_bm", "section_bm", "line_item_bm"], "amount_rm")
compare("memo_assets_nota9", "fact_memo_assets_detail.csv", ["section_bm", "line_item_bm"], "amount_rm")
compare("commitment_detail_nota10", "fact_commitment_detail.csv", ["parent_bm", "item_bm"], "amount_rm")
# 9. Trust accounts table: 2019 closing vs 2020 volume's opening (baki_awal, year=2020)
compare("trust_accounts_nota7", "fact_trust_accounts.csv", ["account_bm"], None,
        y19=2019, y20=2020, val19col="baki_akhir_rm", val20col="baki_awal_rm")
# 9b. Nota 6 loan account statement: 2019 rows in both volumes
compare("loan_account_stmt_nota6", "fact_loan_account_statement.csv",
        ["group_bm", "sub_bm", "line_item_bm"], "amount_rm")
# 10. Registers (Lampiran): 2019 rows in both volumes
compare("loans_receivable", "fact_loans_receivable.csv",
        ["section_bm", "category_bm", "peminjam_bm"], "baki_belum_selesai_rm")
compare("investments_register", "fact_investments.csv",
        ["section_bm", "entiti_bm"], "nilai_buku_rm")
compare("pfi_register", "fact_pfi_liabilities.csv", ["agensi_bm", "tranche_bm"], "amaun_belum_selesai_rm")
compare("guarantees_register", "fact_guarantees.csv", ["agensi_bm"], "jumlah_rm",
        f19=lambda d: d.row_type.isin(["detail", "total"]),
        f20=lambda d: d.row_type.isin(["detail", "total"]))
compare("finance_leases_register", "fact_finance_leases.csv",
        ["sektor_bm", "kategori_bm", "perihal_bm"], "amaun_belum_selesai_rm")
compare("compensation_register", "fact_compensation_commitments.csv",
        ["kategori_bm", "perihal_bm"], "amaun_belum_selesai_rm",
        f20=lambda d: d.row_type != "listing")
compare("statutory_guarantees_register", "fact_statutory_guarantees.csv",
        ["jenis_jaminan_bm", "kategori_bm", "agensi_bm"], "jumlah_rm")
# grants register: NOT printed in the 2019 volume; the 2020 volume's 2019
# comparatives are reported one-sided for the record
d20g = pd.read_csv(f"{WH20}/fact_guarantee_repayment_grants.csv")
g19 = d20g[d20g.year == 2019]
for _, r in g19[g19.row_type == "total"].iterrows():
    rep("grants_register", "JUMLAH KESELURUHAN PERUNTUKAN", None, float(r["amaun_penyaluran_rm"]),
        "statement not printed in the 2019 volume (grants were narrative-only in 2019); "
        "2020 volume introduced the register with 2019 comparatives")
matched["grants_register"] = (0, 1)
# 11. Timeseries: 2019 column of the 2010-2019 panel vs the 2020 volume's 2011-2020 panel
d19t = pd.read_csv(f"{WH19}/fact_timeseries_2010_2019.csv")
d20t = pd.read_csv(f"{WH20}/fact_timeseries_2011_2020.csv")
a = d19t[d19t.year == 2019].set_index(["section_bm", "line_item_bm"])["amount_rm_juta"]
b = d20t[d20t.year == 2019].set_index(["section_bm", "line_item_bm"])["amount_rm_juta"]
n_match = n_diff = 0
for k in sorted(set(a.index) | set(b.index), key=str):
    va = float(a[k]) if k in a.index else None
    vb = float(b[k]) if k in b.index else None
    if va is None or vb is None:
        rep("timeseries_2019col", k, va, vb, "line item present in only one panel")
        n_diff += 1
    elif abs(va - vb) > 0.5:   # RM juta
        rep("timeseries_2019col", k, va, vb, "RM juta")
        n_diff += 1
    else:
        n_match += 1
matched["timeseries_2019col"] = (n_match, n_diff)
# overlap years 2011-2018 summarized
ov_diff = 0
ov = []
a_all = d19t.set_index(["section_bm", "line_item_bm", "year"])["amount_rm_juta"]
b_all = d20t.set_index(["section_bm", "line_item_bm", "year"])["amount_rm_juta"]
shared = set(a_all.index) & set(b_all.index)
for k in sorted(shared, key=str):
    if 2011 <= k[2] <= 2018 and abs(float(a_all[k]) - float(b_all[k])) > 0.5:
        ov_diff += 1
        ov.append((k, float(a_all[k]), float(b_all[k])))
print(f"timeseries overlap 2011-2018: {ov_diff} cell differences (RM juta) out of "
      f"{sum(1 for k in shared if 2011 <= k[2] <= 2018)} shared cells")
for k, va, vb in ov:
    rep("timeseries_overlap_2011_2018", k, va, vb, "RM juta")

with open(f"{WH19}/_restatements_2019_vs_2020volume.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["table", "key", "value_2019_volume", "value_2020_volume", "difference", "note"])
    w.writerows(findings)

print("\nper-table match/diff counts:")
for t, (m, d) in matched.items():
    print(f"  {t}: {m} match, {d} diff")
print(f"\nRESTATEMENT FINDINGS: {len(findings)}")
for t, k, va, vb, d, note in findings:
    fa = f"{va:,.2f}" if va is not None else "n/a"
    fb = f"{vb:,.2f}" if vb is not None else "n/a"
    fd = f"{d:,.2f}" if d is not None else ""
    print(f"  [{t}] {k}: 2019vol={fa} 2020vol={fb} diff={fd} {note}")
