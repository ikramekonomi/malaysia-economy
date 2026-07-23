#!/usr/bin/env python3
"""Cross-year restatement audit: 2012 volume own-year (year=2012) vs the 2013
volume's printed 2012 comparatives. Every difference reported as a restatement.
Output: warehouse2012/_restatements_2012_vs_2013volume.csv
"""
import csv, re as _re
import pandas as pd
WA="/home/claude/pkkp/warehouse2012"   # 2012 volume (own year)
WB="/home/claude/pkkp/warehouse2013"   # 2013 volume (2012 comparative)
findings=[]; matched={}
def rep(table,key,va,vb,note=""):
    findings.append((table,key,va,vb,(va-vb) if (va is not None and vb is not None) else None,note))
def norm_label(x):
    if pd.isna(x): return ""
    x=str(x)
    x=_re.sub(r"\s*\(Dahulu dikenali sebagai[^)]*\)","",x)
    x=_re.sub(r"\*+$","",x.strip())
    x=x.replace("Sdn.Bhd","Sdn. Bhd").replace("Sdn. Bhd.","Sdn. Bhd")
    x=_re.sub(r"\s*[–-]?\s*\(SAMB\.?\)\s*$","",x)
    x=_re.sub(r"\s+"," ",x).strip()
    return x
def compare(table,name,keycols,valcol,yA=2012,yB=2012,fA=None,fB=None,valAcol=None,valBcol=None,tol=0.5,nameB=None):
    dA=pd.read_csv(f"{WA}/{name}"); dB=pd.read_csv(f"{WB}/{nameB or name}")
    a=dA[dA.year==yA].copy() if "year" in dA.columns else dA.copy()
    b=dB[dB.year==yB].copy() if "year" in dB.columns else dB.copy()
    if fA is not None: a=a[fA(a)]
    if fB is not None: b=b[fB(b)]
    for kc in keycols:
        a[kc]=a[kc].map(norm_label); b[kc]=b[kc].map(norm_label)
    vcA=valAcol or valcol; vcB=valBcol or valcol
    a=a.groupby(keycols,dropna=False)[vcA].sum(min_count=1)
    b=b.groupby(keycols,dropna=False)[vcB].sum(min_count=1)
    nm=nd=0
    for k in sorted(set(a.index)|set(b.index),key=str):
        va=a.get(k); vb=b.get(k)
        va=None if va is None or pd.isna(va) else float(va)
        vb=None if vb is None or pd.isna(vb) else float(vb)
        if va is None or vb is None:
            note="present in only one volume"
            if (va==0.0 and vb is None) or (vb==0.0 and va is None): note="zero/nil row in only one volume (not a value restatement)"
            rep(table,k,va,vb,note); nd+=1
        elif abs(va-vb)>tol: rep(table,k,va,vb); nd+=1
        else: nm+=1
    matched[table]=(nm,nd)

compare("financial_position","fact_financial_position.csv",["line_item_bm"],"amount_rm")
compare("financial_performance","fact_financial_performance.csv",["line_code","basis"],"amount_rm",
        fA=lambda d:d.basis=="sebenar",fB=lambda d:d.basis=="sebenar")
compare("cash_statement","fact_cash_statement.csv",["flow","category_bm","item_bm"],"amount_rm")
compare("memorandum_summary","fact_memorandum.csv",["line_item_bm"],"amount_rm")
compare("debt_nota","fact_debt.csv",["item_bm","kind"],"amount_rm")
compare("revenue_nota5a","fact_revenue.csv",["item_bm"],None,yA=2012,yB=2013,valAcol="sebenar_rm",valBcol="sebenar_prior_rm")
compare("revenue_account_stmt","fact_revenue_account_statement.csv",["line_item_bm"],"sebenar_rm")
compare("cash_components_nota3","fact_cash_components.csv",["line_item_bm"],"amount_rm")
compare("investment_summary_nota4","fact_investment_summary.csv",["category_bm","line_item_bm"],"amount_rm")
compare("trust_fund_detail_nota7","fact_trust_fund_detail.csv",["fund_group_bm","fund_bm","section_bm","line_item_bm"],"amount_rm")
compare("memo_assets_nota8","fact_memo_assets_detail.csv",["section_bm","line_item_bm"],"amount_rm")
compare("commitment_detail","fact_commitment_detail.csv",["parent_bm","item_bm"],"amount_rm")
compare("trust_accounts_nota7","fact_trust_accounts.csv",["account_bm"],None,yA=2012,yB=2013,valAcol="baki_akhir_rm",valBcol="baki_awal_rm")
compare("loan_account_stmt_nota6","fact_loan_account_statement.csv",["group_bm","sub_bm","line_item_bm"],"amount_rm")
compare("loans_receivable","fact_loans_receivable.csv",["section_bm","category_bm","peminjam_bm"],"baki_belum_selesai_rm")
compare("investments_register","fact_investments.csv",["section_bm","entiti_bm"],"nilai_buku_rm")
compare("statutory_guarantees_register","fact_statutory_guarantees.csv",["jenis_jaminan_bm","kategori_bm","agensi_bm"],"jumlah_rm")
# devex cumulative RMKe-10 hingga 31.12.2012: 2012 vol terkumpul_rmke10_rm vs 2013 vol terkumpul_rmke10_prior_rm
da=pd.read_csv(f"{WA}/fact_devex_maksud.csv").groupby("maksud_code")["terkumpul_rmke10_rm"].sum()
db=pd.read_csv(f"{WB}/fact_devex_maksud.csv").groupby("maksud_code")["terkumpul_rmke10_prior_rm"].sum()
nm=nd=0
for k in sorted(set(da.index)|set(db.index),key=str):
    va=float(da[k]) if k in da.index else None; vb=float(db[k]) if k in db.index else None
    if va is None or vb is None: rep("devex_cumulative_rmke10_2012",k,va,vb,"maksud in only one volume"); nd+=1
    elif abs(va-vb)>0.5: rep("devex_cumulative_rmke10_2012",k,va,vb); nd+=1
    else: nm+=1
matched["devex_cumulative_rmke10_2012"]=(nm,nd)
# timeseries 2012 column: 2012 vol panel vs 2013 vol panel
dA=pd.read_csv(f"{WA}/fact_timeseries_2003_2012.csv"); dB=pd.read_csv(f"{WB}/fact_timeseries_2004_2013.csv")
a=dA[dA.year==2012].set_index(["section_bm","line_item_bm"])["amount_rm_juta"]
b=dB[dB.year==2012].set_index(["section_bm","line_item_bm"])["amount_rm_juta"]
nm=nd=0
for k in sorted(set(a.index)|set(b.index),key=str):
    va=float(a[k]) if k in a.index else None; vb=float(b[k]) if k in b.index else None
    if va is None or vb is None: rep("timeseries_2012col",k,va,vb,"line item in only one panel"); nd+=1
    elif abs(va-vb)>0.5: rep("timeseries_2012col",k,va,vb,"RM juta"); nd+=1
    else: nm+=1
matched["timeseries_2012col"]=(nm,nd)
# overlap years 2004-2011
a_all=dA.set_index(["section_bm","line_item_bm","year"])["amount_rm_juta"]
b_all=dB.set_index(["section_bm","line_item_bm","year"])["amount_rm_juta"]
shared=set(a_all.index)&set(b_all.index); ovd=0
for k in sorted(shared,key=str):
    if 2004<=k[2]<=2011 and abs(float(a_all[k])-float(b_all[k]))>0.5:
        ovd+=1; rep("timeseries_overlap_2004_2011",k,float(a_all[k]),float(b_all[k]),"RM juta")

with open(f"{WA}/_restatements_2012_vs_2013volume.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["table","key","value_2012_volume","value_2013_volume","difference","note"]); w.writerows(findings)
print("per-table match/diff:")
for t,(m,d) in matched.items(): print(f"  {t}: {m} match, {d} diff")
print(f"timeseries overlap 2004-2011: {ovd} cell diffs")
print(f"\nRESTATEMENT FINDINGS: {len(findings)}")
for t,k,va,vb,d,note in findings:
    fa=f"{va:,.2f}" if va is not None else "n/a"; fb=f"{vb:,.2f}" if vb is not None else "n/a"; fd=f"{d:,.2f}" if d is not None else ""
    print(f"  [{t}] {k}: 2012vol={fa} 2013vol={fb} diff={fd} {note}")
