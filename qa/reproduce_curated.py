#!/usr/bin/env python3
"""Phase 2 'done when': the core reproduces today's curated tables to the last printed digit.

Each curated row is rebuilt from core observations through the agent tools (get_series + derive), never
from the curated file or the L1 CSV, and compared at the curated table's own printed precision.
Writes qa/_validation_reproduce.csv (one row per curated cell; FAIL blocks the PR like any other).

    python3 qa/reproduce_curated.py

Covered so far: curated/fact_labour_indicators.csv (labour share of GDP, implied average wage), and the
BNM and MOF columns of curated/fact_fiscal_headline.csv (compared to the sen). Its PKKP columns are not
covered: core still reads them from that same table (Phase 3 moves them to PKKP observations), so a
comparison would be circular, and it is not claimed.
"""
import csv
import os
import sys
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from apps.tools.warehouse_tools import Tools  # noqa: E402


def places(printed):
    return len(printed.split(".")[1]) if "." in printed else 0


def at(value, printed):
    """value rounded to the printed precision; the same answer under half-up and half-even, or flagged."""
    q = Decimal(1).scaleb(-places(printed))
    up, even = value.quantize(q, ROUND_HALF_UP), value.quantize(q, ROUND_HALF_EVEN)
    return up, up != even


def obs(t, ind, year):
    r = t.get_series(ind, "MY", year, year)
    return r["rows"][0]["obs_id"] if r.get("held") and len(r["rows"]) == 1 else None


def labour(t, out):
    path = os.path.join(REPO, "curated", "fact_labour_indicators.csv")
    for r in csv.DictReader(open(path, newline="")):
        y, ind = r["year"], r["indicator"]
        comp = obs(t, "na.compensation_of_employees", y)
        if ind == "implied_average_wage_rm_per_worker_year":
            op, other, scale = "per_employed", obs(t, "lfs.employed", y), Decimal(1)
        elif ind == "labour_share_of_gdp_pct":
            op, other, scale = "ratio", obs(t, "gdp.nominal", y), Decimal(100)
        else:
            out.append(["fact_labour_indicators", f"{y} {ind}", r["value"], "", "FAIL", "no rule to reproduce it"])
            continue
        if not comp or not other:
            out.append(["fact_labour_indicators", f"{y} {ind}", r["value"], "", "FAIL", "input not held in core"])
            continue
        d = t.derive(op, comp, other)
        if not d.get("ok"):
            out.append(["fact_labour_indicators", f"{y} {ind}", r["value"], "", "FAIL", d.get("refused")])
            continue
        got, tie = at(Decimal(d["value"]) * scale, r["value"])
        ok = got == Decimal(r["value"])
        out.append(["fact_labour_indicators", f"{y} {ind}", r["value"], str(got), "PASS" if ok else "FAIL",
                    f"core: derive('{op}') {d['derivation_id']}" + (" (rounding tie)" if tie else "")])


FISCAL = {  # curated column -> (core indicator, publisher)
    "revenue_bnm_rm": ("federal_gov.revenue.total", "bnm"), "opex_bnm_rm": ("federal_gov.expenditure.opex", "bnm"),
    "devex_gross_bnm_rm": ("federal_gov.expenditure.devex", "bnm"),
    "devex_loan_recovery_bnm_rm": ("federal_gov.expenditure.devex_loan_recovery", "bnm"),
    "devex_net_bnm_rm": ("federal_gov.expenditure.devex_net", "bnm"),
    "revenue_mof_rm": ("federal_gov.revenue.total", "mof"), "opex_mof_rm": ("federal_gov.expenditure.opex", "mof"),
    "devex_gross_mof_rm": ("federal_gov.expenditure.devex", "mof"),
    "devex_loan_recovery_mof_rm": ("federal_gov.expenditure.devex_loan_recovery", "mof"),
    "covid_fund_mof_rm": ("federal_gov.expenditure.covid_fund", "mof"),
    "overall_balance_mof_rm": ("federal_gov.overall_balance", "mof"),
}
SEN = Decimal("0.01")


def fiscal(t, out):
    path = os.path.join(REPO, "curated", "fact_fiscal_headline.csv")
    for r in csv.DictReader(open(path, newline="")):
        y = r["year"]
        cols = dict(FISCAL)
        if "MOF" in r["devex_net_basis"]:
            cols["devex_net_rm"] = ("federal_gov.expenditure.devex_net", "mof")
        for col, (ind, pub) in cols.items():
            res = t.get_series(ind, "MY", y, y, publisher=pub)
            got = res["rows"] if res.get("held") else []
            cell = f"{y} {col}"
            if not r[col]:
                out.append(["fact_fiscal_headline", cell, "", got[0]["value"] if got else "",
                            "PASS" if not got else "FAIL", "empty in both" if not got else "core holds a value curated lacks"])
                continue
            if len(got) != 1:
                out.append(["fact_fiscal_headline", cell, r[col], "", "FAIL", f"{len(got)} core rows for {pub}"])
                continue
            a, b = Decimal(r[col]).quantize(SEN), Decimal(got[0]["value"]).quantize(SEN)
            out.append(["fact_fiscal_headline", cell, str(a), str(b), "PASS" if a == b else "FAIL",
                        f"core {got[0]['citation']['edition_id']}, to the sen"])


def main():
    t = Tools()
    out = []
    labour(t, out)
    fiscal(t, out)
    with open(os.path.join(REPO, "qa", "_validation_reproduce.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["table", "cell", "curated", "core", "status", "note"])
        w.writerows(out)
    bad = [r for r in out if r[4] != "PASS"]
    print(f"reproduce: {len(out) - len(bad)} of {len(out)} curated cells reproduced from core "
          f"(release {t.w.release_id})")
    for r in bad[:10]:
        print("  FAIL", r)


if __name__ == "__main__":
    main()
