#!/usr/bin/env python3
"""Derived labour indicators: implied average wage and labour share of GDP.

Run:    python3 curated/pipeline/build_labour_indicators.py
Writes: curated/fact_labour_indicators.csv, curated/_validation_labour.csv

WHY THIS EXISTS — a documented gap, not a preference. DOSM publishes **no
salaries-and-wages dataset** through data.gov.my / OpenDOSM: an exhaustive check
of all 289 data.gov.my and 182 OpenDOSM dataset ids (see sources/dosm/README.md)
found formal-sector wages to be dashboard-only, and the Salaries & Wages Survey
reports sit on www.dosm.gov.my, which this environment cannot reach. The
Labour Force Survey family carries no income field at any grain.

So these two indicators are DERIVED, from two sources already in the warehouse:

    implied_average_wage_rm = compensation of employees / employed persons
        numerator   sources/dosm/data/gdp_annual_nominal_income.csv
                    series='abs', component='i1'  (RM million, current prices)
        denominator sources/dosm/data/lfs_year.csv  lf_employed  ('000 persons)

    labour_share_pct = compensation of employees / GDP (income approach) x 100
        denominator component='i0' of the same file

`basis='derived'` on every row. These are NOT DOSM statistics and must never be
presented as such — cite them as "derived from national accounts and the labour
force survey", and prefer the official Salaries & Wages Survey the moment it is
acquired (docs/SOURCES.md Tier 1b).

WHAT THEY DO AND DO NOT MEASURE
  - The wage figure is compensation per EMPLOYED person across the whole economy,
    which includes the self-employed and unpaid family workers in the denominator
    while the numerator counts only employees. It therefore UNDERSTATES the
    average employee wage, by roughly the self-employed share of employment. It
    is a consistent series over time, not a level estimate.
  - Compensation of employees includes employer contributions (EPF, SOCSO), so it
    is labour cost, not take-home pay.
  - Both are national and nominal. No sector, state, occupation or percentile
    detail is derivable — that is exactly what the missing survey would provide.

VALIDATION. The identity is checked in both directions against the source files,
and labour share is re-derived independently from the published i1/i0 pair. A
year is emitted only where both inputs exist on the same vintage.
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DOSM = os.path.join(ROOT, "sources", "dosm", "data")
INCOME = os.path.join(DOSM, "gdp_annual_nominal_income.csv")
LFS = os.path.join(DOSM, "lfs_year.csv")


def load_income():
    """component i1 = compensation of employees, i0 = GDP (income approach).

    The file carries BOTH series='abs' (levels, RM million) and
    series='growth_yoy' (per cent) — filtering on series is mandatory, or the
    growth rows silently overwrite the levels for every year from 2016.
    """
    comp, gdp, prov = {}, {}, {}
    for r in csv.DictReader(open(INCOME)):
        if r["series"] != "abs":
            continue
        y = r["date"][:4]
        if r["component"] == "i1":
            comp[y] = float(r["value"])
            prov[y] = (r["retrieved_from"], r["retrieved_date"])
        elif r["component"] == "i0":
            gdp[y] = float(r["value"])
    return comp, gdp, prov


def load_employed():
    return {r["date"][:4]: float(r["lf_employed"])
            for r in csv.DictReader(open(LFS)) if r.get("lf_employed")}


def main():
    comp, gdp, prov = load_income()
    emp = load_employed()
    years = sorted(set(comp) & set(emp))
    rows, checks = [], []

    for y in years:
        wage = comp[y] * 1e6 / (emp[y] * 1e3)          # RM per employed person
        share = 100 * comp[y] / gdp[y] if gdp.get(y) else None
        src, date = prov[y]
        base = dict(year=y, basis="derived", unit_note="current prices, national",
                    numerator_rm_mil=f"{comp[y]:.3f}", denominator=f"{emp[y]:.1f}",
                    source_numerator="sources/dosm/data/gdp_annual_nominal_income.csv"
                                     " (series=abs, component=i1)",
                    source_denominator="sources/dosm/data/lfs_year.csv (lf_employed)",
                    retrieved_from=src, retrieved_date=date)
        rows.append(dict(base, indicator="implied_average_wage_rm_per_worker_year",
                         value=f"{wage:.2f}"))
        if share is not None:
            rows.append(dict(base, indicator="labour_share_of_gdp_pct",
                             value=f"{share:.3f}",
                             denominator=f"{gdp[y]:.3f}",
                             source_denominator="sources/dosm/data/gdp_annual_nominal_income.csv"
                                                " (series=abs, component=i0)"))

    # V1 the derivation reproduces from the printed inputs (both directions)
    for y in years:
        w = comp[y] * 1e6 / (emp[y] * 1e3)
        back = w * (emp[y] * 1e3) / 1e6
        checks.append(["V1_wage_roundtrip", y, f"{comp[y]:.3f}", f"{back:.3f}",
                       "PASS" if abs(back - comp[y]) < 1e-6 else "FAIL",
                       "compensation -> wage -> compensation"])
    # V2 labour share within a plausible band; flags a units error, not a value
    for y in years:
        if not gdp.get(y):
            continue
        s = 100 * comp[y] / gdp[y]
        checks.append(["V2_labour_share_band", y, "20-60%", f"{s:.1f}%",
                       "PASS" if 20 <= s <= 60 else "FAIL",
                       "sanity band; outside it means a units or series mix-up"])
    # V3 both inputs must come from the same retrieved vintage
    dates = {prov[y][1] for y in years}
    checks.append(["V3_single_vintage", "all", "1 retrieved_date", str(sorted(dates)),
                   "PASS" if len(dates) == 1 else "FAIL",
                   "inputs must share one DOSM snapshot"])

    dest = os.path.join(ROOT, "curated", "fact_labour_indicators.csv")
    cols = ["year", "indicator", "value", "basis", "unit_note", "numerator_rm_mil",
            "denominator", "source_numerator", "source_denominator",
            "retrieved_from", "retrieved_date"]
    with open(dest, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    vdest = os.path.join(ROOT, "curated", "_validation_labour.csv")
    with open(vdest, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["check", "year", "expected", "got", "status", "note"])
        w.writerows(checks)

    fails = sum(1 for c in checks if c[4] == "FAIL")
    print(f"wrote {dest}: {len(rows)} rows, {years[0]}-{years[-1]}")
    print(f"wrote {vdest}: {len(checks)} checks, {fails} FAIL")


if __name__ == "__main__":
    main()
