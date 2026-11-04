#!/usr/bin/env python3
"""FY2025 expected-actual nowcast: Budget 2025 as tabled x utilisation signatures.

Run:  python3 apps/models/build_nowcast_2025.py
Reads : sources/anggaran/data/2025/fact_anggaran_maksud_2025.csv   (verified budget)
        sources/anggaran/data/2025/_crosswalk_pkkp_2025.csv         (code crosswalk)
        apps/models/fact_utilisation_signatures.csv            (actual/budget history)
Writes: apps/models/fact_nowcast_2025.csv

Method (basis=model_projection, never an audited figure): for every operating vote
(T jumlah + B mengurus), expected FY2025 actual = anggaran_2025 x the vote's own
historical utilisation quantiles (p25 / median / p75 of actual-vs-original-budget,
FY2010-FY2024). Votes with no usable signature (no PKKP history, e.g. created after
2024) fall back to ratio 1.0 and are flagged fallback_no_history — reported, not hidden.
Development votes are excluded: DE utilisation signatures are not built yet (devex
volatility makes per-vote OE-style ratios misleading).
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
AP = os.path.join(ROOT, "sources", "anggaran", "data", "2025")

sig = {}
for r in csv.DictReader(open(os.path.join(HERE, "fact_utilisation_signatures.csv"))):
    if not (r["util_p25"] and r["util_median"] and r["util_p75"]):
        continue  # signature exists but quantiles unpublishable (too few years)
    sig[r["maksud_code"]] = (float(r["util_p25"]), float(r["util_median"]), float(r["util_p75"]),
                             int(r["n_years"]))

xwalk = {}
for r in csv.DictReader(open(os.path.join(AP, "_crosswalk_pkkp_2025.csv"))):
    xwalk[r["maksud_code"]] = r["status"]

budget = {}   # code -> (name, anggaran_2025 total for the operating side)
for r in csv.DictReader(open(os.path.join(AP, "fact_anggaran_maksud_2025.csv"))):
    if r["measure"] != "anggaran_2025":
        continue
    c = r["maksud_code"]
    if (c.startswith("T.") and r["component"] == "jumlah") or \
       (c.startswith("B.") and r["component"] == "mengurus"):
        budget[c] = (r["maksud_name_bm"], int(r["amount_rm"]))

dest = os.path.join(HERE, "fact_nowcast_2025.csv")
with open(dest, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["year", "maksud_code", "name_bm", "budget_2025_rm", "signature",
                "expected_lo_rm", "expected_mid_rm", "expected_hi_rm",
                "basis", "method", "data_through", "note"])
    tot_b = tot_lo = tot_mid = tot_hi = 0
    n_fallback = 0
    for c in sorted(budget):
        name, b = budget[c]
        if c in sig and xwalk.get(c, "").startswith("matched"):
            p25, med, p75, n = sig[c]
            lo, mid, hi = round(b * p25), round(b * med), round(b * p75)
            signature, note = f"own history (n={n})", ""
        else:
            lo = mid = hi = b
            signature, note = "fallback_no_history", "no usable PKKP utilisation history; ratio 1.0"
            n_fallback += 1
        tot_b += b; tot_lo += lo; tot_mid += mid; tot_hi += hi
        w.writerow([2025, c, name, b, signature, lo, mid, hi, "model_projection",
                    "budget x per-vote actual/original-budget quantiles (p25/med/p75), FY2010-FY2024",
                    2024, note])
    w.writerow([2025, "TOTAL_OE", "Jumlah Perbelanjaan Mengurus (expected)", tot_b, "sum of votes",
                tot_lo, tot_mid, tot_hi, "model_projection",
                "sum of per-vote expected actuals (quantile sums, not a joint distribution)",
                2024, "official OE budget 2025: 335,000,000,000; official revised (Budget 2026 ed.): 332,150,000,000"])
print(f"wrote {dest}: {len(budget)} votes ({n_fallback} fallback), "
      f"OE budget {tot_b:,} -> expected mid {tot_mid:,} (lo {tot_lo:,} / hi {tot_hi:,})")
