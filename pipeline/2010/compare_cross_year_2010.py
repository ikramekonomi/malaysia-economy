#!/usr/bin/env python3
"""Cross-year restatement audit: 2010 volume own-year (year=2010) vs the 2011
volume's printed 2010 comparatives. Output warehouse2010/_restatements_2010_vs_2011volume.csv"""
import csv, re as _re, os
import pandas as pd
WA="/home/claude/pkkp/warehouse2010"   # 2010 volume own year
WB="/home/claude/pkkp/warehouse2011"   # 2011 volume 2010 comparative
findings=[]; matched={}
def rep(t,k,va,vb,note=""):
    findings.append((t,k,va,vb,(round(va-vb,2) if (va is not None and vb is not None) else None),note))
def norm(x):
    if pd.isna(x): return ""
    x=_re.sub(r"\*+$","",str(x).strip()); x=_re.sub(r"\s+"," ",x)
    return x.strip()
def compare(table,name,keycols,valAcol,valBcol=None,yA=2010,yB=2010,fA=None,fB=None,nameB=None,tol=0.5):
    pa=f"{WA}/{name}"; pb=f"{WB}/{nameB or name}"
    if not(os.path.exists(pa) and os.path.exists(pb)):
        matched[table]=("skip-missing-file",0); return
    dA=pd.read_csv(pa); dB=pd.read_csv(pb); valBcol=valBcol or valAcol
    for c in keycols+[valAcol]:
        if c not in dA.columns: matched[table]=(f"skip-no-col-{c}-A",0); return
    for c in keycols+[valBcol]:
        if c not in dB.columns: matched[table]=(f"skip-no-col-{c}-B",0); return
    a=dA[dA.year==yA].copy() if "year" in dA.columns else dA.copy()
    b=dB[dB.year==yB].copy() if "year" in dB.columns else dB.copy()
    if fA is not None: a=a[fA(a)]
    if fB is not None: b=b[fB(b)]
    for kc in keycols: a[kc]=a[kc].map(norm); b[kc]=b[kc].map(norm)
    a=a.groupby(keycols,dropna=False)[valAcol].sum(min_count=1)
    b=b.groupby(keycols,dropna=False)[valBcol].sum(min_count=1)
    nm=nd=0
    for k in sorted(set(a.index)|set(b.index),key=str):
        va=a.get(k); vb=b.get(k)
        va=None if va is None or pd.isna(va) else float(va)
        vb=None if vb is None or pd.isna(vb) else float(vb)
        if va is None or vb is None:
            note="present in only one volume"
            if (va==0.0 and vb is None) or (vb==0.0 and va is None): note="zero/nil row in only one volume"
            rep(table,k,va,vb,note); nd+=1
        elif abs(va-vb)>tol: rep(table,k,va,vb); nd+=1
        else: nm+=1
    matched[table]=(nm,nd)

compare("financial_position","fact_financial_position.csv",["line_item_bm"],"amount_rm")
compare("financial_performance","fact_financial_performance.csv",["line_code","basis"],"amount_rm",
        fA=lambda d:d.basis=="sebenar",fB=lambda d:d.basis=="sebenar")
compare("cash_statement","fact_cash_statement.csv",["flow","category_bm","item_bm"],"amount_rm")
compare("memorandum_summary","fact_memorandum.csv",["line_item_bm"],"amount_rm")
compare("cash_components_nota3","fact_cash_components.csv",["line_item_bm"],"amount_rm")
compare("investment_summary_nota4","fact_investment_summary.csv",["category_bm","line_item_bm"],"amount_rm")
compare("memo_assets_nota8","fact_memo_assets_detail.csv",["section_bm","line_item_bm"],"amount_rm")
compare("debt_nota9a","fact_debt.csv",["item_bm","kind"],"amount_rm")
compare("commitment_detail","fact_commitment_detail.csv",["parent_bm","item_bm"],"amount_rm")
compare("revenue_account_stmt","fact_revenue_account_statement.csv",["line_item_bm"],"sebenar_rm")
compare("loan_account_stmt_nota6","fact_loan_account_statement.csv",["group_bm","sub_bm","line_item_bm"],"amount_rm")
# revenue: 2010 vol sebenar@2010 vs 2011 vol sebenar_prior@2011
compare("revenue_nota5a","fact_revenue.csv",["item_bm"],"sebenar_rm","sebenar_prior_rm",yA=2010,yB=2011)
# timeseries overlap years 2002-2010
tsA=[f for f in os.listdir(WA) if f.startswith("fact_timeseries_")]
tsB=[f for f in os.listdir(WB) if f.startswith("fact_timeseries_")]
if tsA and tsB:
    dA=pd.read_csv(f"{WA}/{tsA[0]}"); dB=pd.read_csv(f"{WB}/{tsB[0]}")
    dA["section_bm"]=dA["section_bm"].map(norm); dA["line_item_bm"]=dA["line_item_bm"].map(norm)
    dB["section_bm"]=dB["section_bm"].map(norm); dB["line_item_bm"]=dB["line_item_bm"].map(norm)
    a=dA.set_index(["section_bm","line_item_bm","year"])["amount_rm_juta"]
    b=dB.set_index(["section_bm","line_item_bm","year"])["amount_rm_juta"]
    shared=set(a.index)&set(b.index); nd=0
    for k in sorted(shared,key=str):
        if 2002<=k[2]<=2010 and abs(float(a[k])-float(b[k]))>0.5:
            nd+=1; rep("timeseries_overlap_2002_2010",k,float(a[k]),float(b[k]),"RM juta")
    matched["timeseries_overlap_2002_2010"]=(len(shared)-nd,nd)

with open(f"{WA}/_restatements_2010_vs_2011volume.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["table","key","value_2010_volume","value_2011_volume","difference","note"]); w.writerows(findings)
print("per-table (match, diff):")
for t,v in matched.items(): print(f"  {t}: {v}")
print(f"\nTOTAL RESTATEMENT FINDINGS: {len(findings)}")
for t,k,va,vb,d,note in findings[:60]:
    fa=f"{va:,.2f}" if va is not None else "n/a"; fb=f"{vb:,.2f}" if vb is not None else "n/a"
    print(f"  [{t}] {str(k)[:60]}: 2010={fa} 2011={fb} diff={d} {note}")
