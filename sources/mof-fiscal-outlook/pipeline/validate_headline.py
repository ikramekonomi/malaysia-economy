#!/usr/bin/env python3
"""Reconcile data/fiscal_outlook_headline.csv against the documents' own printed totals.

Checks (all against figures printed in the PDFs themselves, no external numbers):
  A. current-balance identity:  revenue - operating_expenditure = printed current balance
  B. net-DE identity:           gross DE - printed loan recovery = printed net DE
     (net + loan recovery figures are carried in the row notes, read off the same table)
  C. overall-balance identity:  current balance - net DE = overall_deficit row
  D. %GDP rows:                 amount / printed nominal_gdp (same edition & target year)
                                rounds at 1 dp to the printed pct row
Writes data/_validation_headline.csv (check, edition, target, expected, got, status).
"""
import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

# printed current balance (Jadual 1.1 "Baki semasa"), RM bil — provenance same page as
# the revenue/opex rows of that edition/target in the headline CSV
PRINTED_CURRENT_BALANCE = {
    (2025, 2024): 0.550, (2025, 2025): 4.706,
    (2026, 2024): 3.109, (2026, 2025): 1.965, (2026, 2026): 4.922,
}

rows = list(csv.DictReader(open(os.path.join(DATA, "fiscal_outlook_headline.csv"))))
val = {(int(r["edition_year"]), int(r["target_year"]), r["line"]): float(r["amount_rm_bil"]) for r in rows}
note = {(int(r["edition_year"]), int(r["target_year"]), r["line"]): r["note"] for r in rows}

out = []


def check(name, ed, ty, expected, got, tol=5e-4):
    ok = abs(expected - got) <= tol
    out.append([name, ed, ty, f"{expected:.3f}", f"{got:.3f}", "PASS" if ok else "FAIL"])


for (ed, ty), cb in sorted(PRINTED_CURRENT_BALANCE.items()):
    rev, oe = val[(ed, ty, "revenue")], val[(ed, ty, "operating_expenditure")]
    check("A_current_balance", ed, ty, cb, rev - oe)

    gross = val[(ed, ty, "development_expenditure")]
    m = re.search(r"net printed ([\d.]+) after loan recovery ([\d.]+)", note[(ed, ty, "development_expenditure")])
    if m:
        net, rec = float(m.group(1)), float(m.group(2))
        check("B_net_de", ed, ty, net, gross - rec)
    else:
        net = None
        out.append(["B_net_de", ed, ty, "no net/recovery in note", "", "SKIP"])

    if net is not None and (ed, ty, "overall_deficit") in val:
        check("C_overall_balance", ed, ty, val[(ed, ty, "overall_deficit")], cb - net)

for (ed, ty, line), pct in sorted(val.items()):
    if line in ("deficit_pct_gdp", "debt_pct_gdp"):
        amt_line = "overall_deficit" if line == "deficit_pct_gdp" else "federal_debt"
        gdp = val.get((ed, ty, "nominal_gdp"))
        amt = val.get((ed, ty, amt_line))
        if gdp is None or amt is None:
            out.append([f"D_{line}", ed, ty, "missing gdp or amount", "", "SKIP"])
            continue
        derived = round(amt / gdp * 100, 1)
        out.append([f"D_{line}", ed, ty, f"{pct:.1f}", f"{derived:.1f}",
                    "PASS" if abs(derived - pct) < 1e-9 else "FAIL"])

dest = os.path.join(DATA, "_validation_headline.csv")
with open(dest, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["check", "edition_year", "target_year", "expected_printed", "derived", "status"])
    w.writerows(out)

fails = [r for r in out if r[-1] == "FAIL"]
print(f"{len(out)} checks, {len(fails)} FAIL -> {dest}")
for r in fails:
    print("FAIL:", r)
