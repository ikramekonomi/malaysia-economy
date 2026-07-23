#!/usr/bin/env python3
"""Cross-year restatement audit: 2015 volume (year=2015 current) vs the 2016
volume's printed 2015 comparatives. Emits _restatements_2015_vs_2016volume.csv
(table,key,value_2015_volume,value_2016_volume,difference,note). Every non-zero
difference is a candidate: genuine restatement OR residual OCR error -> noted.
Doubles as an independent OCR check on the core statements (which the 2016
volume reprints verbatim as its comparative column).
"""
import csv
import pandas as pd

W15 = "/home/claude/pkkp/warehouse2015"
W16 = "/home/claude/pkkp/warehouse2016"
OUT = f"{W15}/_restatements_2015_vs_2016volume.csv"
TOL = 0.5

rows = []


def keyed(df, keycols, valcol, year=2015):
    d = df[df.year == year] if "year" in df.columns else df
    out = {}
    for _, r in d.iterrows():
        k = " | ".join(str(r[c]).strip() for c in keycols if c in df.columns and pd.notna(r[c]))
        v = r[valcol]
        if pd.notna(v):
            out[k] = float(v)
    return out


def audit(table, keycols, valcol15, valcol16=None, year16=2015, note_hint=""):
    valcol16 = valcol16 or valcol15
    d15 = pd.read_csv(f"{W15}/{table}.csv")
    d16 = pd.read_csv(f"{W16}/{table}.csv")
    a = keyed(d15, keycols, valcol15, 2015)
    b = keyed(d16, keycols, valcol16, year16)
    keys = list(dict.fromkeys(list(a) + list(b)))
    n_match = n_diff = n_only = 0
    for k in keys:
        v15, v16 = a.get(k), b.get(k)
        if v15 is None or v16 is None:
            n_only += 1
            rows.append((table, k, v15 if v15 is not None else "",
                         v16 if v16 is not None else "", "",
                         "row present in only one volume (structure/label diff)"))
            continue
        diff = round(v15 - v16, 2)
        if abs(diff) < TOL:
            n_match += 1
        else:
            n_diff += 1
            # relative size to hint at OCR (order-of-magnitude) vs restatement
            rel = abs(diff) / max(abs(v16), 1)
            hint = ("likely OCR (order-of-magnitude/digit)" if rel > 0.25
                    else "small delta: genuine restatement or sen-level OCR")
            rows.append((table, k, v15, v16, diff, f"{note_hint}{hint}"))
    print(f"{table:34} match={n_match:4} diff={n_diff:3} single={n_only:3}")
    return n_match, n_diff, n_only


audit("fact_financial_position", ["section", "line_item_bm"], "amount_rm")
audit("fact_financial_performance", ["line_item_bm", "basis"], "amount_rm")
audit("fact_cash_statement", ["flow", "category_bm", "item_bm"], "amount_rm")
audit("fact_memorandum", ["section", "line_item_bm"], "amount_rm")
# revenue: 2015-vol current sebenar vs 2016-vol sebenar_prior (its 2015 column)
audit("fact_revenue", ["level", "category_l1_bm", "category_l2_bm", "item_bm"],
      "sebenar_rm", "sebenar_prior_rm", year16=2016,
      note_hint="revenue 2015 sebenar vs 2016-vol prior col; ")

with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["table", "key", "value_2015_volume", "value_2016_volume", "difference", "note"])
    w.writerows(rows)
print(f"\nwrote {OUT}: {len(rows)} rows")
diffs = [r for r in rows if r[4] != "" and abs(float(r[4])) >= TOL]
print(f"non-zero numeric differences: {len(diffs)}")
