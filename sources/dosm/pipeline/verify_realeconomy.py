#!/usr/bin/env python3
"""Verify the real-economy CSVs (ingest_realeconomy.py) — second door + internal identities.

Same discipline as verify_expansion.py, extended for a survey-based domain where a
row-count match is not enough: an economic series can be internally *incoherent*
(components that do not add to their own total, a labour force that is not employed +
unemployed, a decile distribution that does not average to the published mean) while
every row matches its source byte-for-byte. Both classes of check run here.

A. Two independent doors onto the same publication, per dataset

   A1 parquet mirror (storage.dosm.gov.my/<domain>/<file>.parquet) — the SAME vintage
      of the same publication in a different serialisation. This is the arbiter: it is
      what decides whether the canonical CSV's numbers are right.
   A2 static API (api.data.gov.my) — an independent serving path, available for 80 of
      the 90 datasets (the other 10 carry exclude_openapi: true in the catalogue).

   Each door is checked for row_count and for a full field-by-field comparison of every
   row at the latest period both it and the CSV publish (lookup tables: full content).
   Values compared as a multiset of (column, normalised value) pairs — exact for
   strings, 1e-6 for numerics.

   Ruling: a value disagreement is a FAIL only if the **parquet arbiter** disagrees with
   the canonical CSV. An API-only disagreement is recorded as INFO with the arbiter's
   verdict attached, because it means the API mirror — not this warehouse's file — is
   the one out of step. Three such divergences exist in this vintage and are named in
   the output: a stale API vintage for the granular GDP files, a stale ep_ratio column
   in the API's lfs_district, and lag of one to two periods in the API's ipi/ipi_1d.
   Separately, hh_access_amenities is the one dataset where the storage CSV itself is
   behind its own mirrors (2024 wave present in parquet+API, absent from the CSV) —
   recorded, not silently swapped.

B. Internal identities — the accounting the source implies about itself
   gdp_expenditure   e0 == e1 + e2 + e3 + e4 + e5 - e6   (annual, quarterly, SA)
   gdp_supply        p0 == p1 + ... + p6
   gdp_income        i0 == i1 + i2 + i3   and   i3 == i3.1 - i3.2
   gdp_three_ways    production == expenditure == income total, same year (SNA 2008
                     requires the three approaches to agree)
   labour_force      lf == lf_employed + lf_unemployed, and u_rate == unemployed/lf,
                     across every LFS grain (month, quarter, year, state, district,
                     parliament, DUN, by sex)
   productivity      output_employment == gdp/employment, output_hour == gdp/hours
   percentile_mean   the 100 percentile means average to the published overall mean
                     (nationally and per state) — the decile/percentile distribution
                     against hh_income / hh_income_state
   poverty_nesting   hardcore poverty <= absolute poverty (the source defines hardcore
                     as a subset)
   hies_crosscheck   hies_state's income_mean / gini / poverty vs the same year in
                     hh_income_state / hh_inequality_state / hh_poverty_state
   employment_shares employment_sector proportions sum to 100 per date x sex

Tolerances are stated per check and are rounding-scale only: the published files carry
1-3 decimal places and DOSM's own caveat says "the sum of each category may not always
equal the totals ... because of independent rounding". Anything beyond rounding scale is
reported, never corrected.

Writes data/_validation_realeconomy.csv. Exits non-zero on any FAIL.
"""
import csv
import io
import json
import os
import sys
import urllib.request
from collections import Counter, defaultdict

from ingest_realeconomy import REALECONOMY

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
PROV = ("retrieved_from", "retrieved_date")

out = []


def add(ds, check, expected, got, status, note=""):
    out.append([ds, check, expected, got, status, note])


# ---------------------------------------------------------------- helpers
def load(ds):
    with open(os.path.join(DATA, f"{ds}.csv")) as f:
        return list(csv.DictReader(f))


def num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def norm(v):
    """Normalise a cell from either door to a comparable scalar."""
    if v is None or v == "" or (isinstance(v, float) and v != v):
        return None
    if hasattr(v, "isoformat"):          # parquet date/datetime
        return v.isoformat()[:10]
    if isinstance(v, bool):
        return str(v)
    try:
        return round(float(v), 6)
    except (TypeError, ValueError):
        s = str(v).strip()
        return s[:10] if len(s) == 19 and s[4] == "-" and s[10] == " " else s


def rowkey(r, cols):
    return tuple(sorted((c, norm(r.get(c))) for c in cols))


def _get(url, tries=4):
    """Fetch with retries — the public endpoints reset connections under bulk reads."""
    import time
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=240) as r:
                return r.read()
        except Exception:                                      # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def fetch_api(ds, route="opendosm"):
    d = json.loads(_get(f"https://api.data.gov.my/{route}?id={ds}&limit=1000000"))
    return d["data"] if isinstance(d, dict) else d


def fetch_parquet(csv_url):
    import pyarrow.parquet as pq
    t = pq.read_table(io.BytesIO(_get(csv_url.replace(".csv", ".parquet"))))
    return t.to_pylist()


def date_span(rows, key="date"):
    ds_ = sorted({norm(r.get(key)) for r in rows if r.get(key) not in (None, "")})
    return (ds_[0], ds_[-1]) if ds_ else (None, None)


# Divergences between the doors found on 2026-08-01 with every door fetched fresh, and
# kept exactly as published (CLAUDE.md rule 2). Each names the arbiter's verdict.
DOOR_NOTES = {
    "lfs_district": "the API mirror's ep_ratio column is ~19pp below the CSV's "
                    "throughout; the CSV (and the parquet arbiter) reproduce "
                    "100*lf_employed/(lf+lf_outside) exactly, the API does not.",
    "gdp_annual_nominal_supply_granular": "the API mirror is a stale VINTAGE, not just "
                    "short: it ends 2023 and its 2023 values are pre-revision.",
    "gdp_annual_real_supply_granular": "stale API vintage — ends 2023, pre-revision values.",
    "gdp_annual_nominal_demand_granular": "stale API vintage — ends 2023, pre-revision values.",
}


def compare(ds, rows, ref, door, arbiter):
    """Row-count + value comparison of the canonical CSV against one door.

    arbiter=True  -> a disagreement is a FAIL (the canonical file would be wrong)
    arbiter=False -> a disagreement is INFO (the mirror is the one out of step; the
                     arbiter has already ruled on the numbers)
    """
    hard = "FAIL" if arbiter else "INFO"
    cols = [c for c in rows[0] if c not in PROV] if rows else []
    dated = bool(rows) and "date" in cols
    _, c_hi = date_span(rows) if dated else (None, None)
    _, r_hi = date_span(ref) if dated else (None, None)

    if len(rows) == len(ref):
        add(ds, f"row_count (vs {door})", len(ref), len(rows), "PASS")
    elif dated and r_hi and r_hi < c_hi:
        add(ds, f"row_count (vs {door})", len(ref), len(rows), "INFO",
            f"{door} lags: it ends {r_hi}, the canonical CSV ends {c_hi} "
            f"(+{len(rows) - len(ref)} rows here). " + DOOR_NOTES.get(ds, ""))
    elif dated and r_hi and r_hi > c_hi:
        add(ds, f"row_count (vs {door})", len(ref), len(rows), "INFO",
            f"{door} is AHEAD of the canonical CSV: it ends {r_hi}, the CSV ends "
            f"{c_hi} ({len(ref) - len(rows)} rows not in the download-button file). "
            "The CSV is kept as published; the newer wave is a future vintage pull.")
    else:
        add(ds, f"row_count (vs {door})", len(ref), len(rows), hard)

    if not dated:                                  # lookup / dictionary tables
        c_ms, r_ms = Counter(rowkey(r, cols) for r in rows), Counter(rowkey(r, cols) for r in ref)
        mism = sum(((c_ms - r_ms) + (r_ms - c_ms)).values())
        add(ds, f"full_content vs {door} ({len(rows)} rows x {len(cols)} cols)", 0, mism,
            "PASS" if mism == 0 else hard)
        return

    latest = min(x for x in (c_hi, r_hi) if x)     # latest period BOTH doors publish
    c_ms = Counter(rowkey(r, cols) for r in rows if norm(r["date"]) == latest)
    r_ms = Counter(rowkey(r, cols) for r in ref if norm(r.get("date")) == latest)
    n = sum(c_ms.values())
    only_csv, only_ref = c_ms - r_ms, r_ms - c_ms
    mism = sum(only_csv.values()) + sum(only_ref.values())
    label = f"period_values vs {door} ({latest}, {n} rows x {len(cols)} cols)"
    if mism == 0 and n > 0:
        add(ds, label, 0, mism, "PASS",
            f"compared at {latest}; canonical CSV runs to {c_hi}" if latest != c_hi else "")
        return
    diffcols = sorted({c for k in list(only_csv) + list(only_ref) for c, _ in k})
    status, note = hard, "differing columns: " + ",".join(diffcols)
    if not arbiter:
        note = (DOOR_NOTES.get(ds) or "differs from the canonical CSV; the parquet "
                "arbiter has ruled in favour of the CSV.") + " " + note
    elif r_hi and c_hi and r_hi > c_hi:
        # The arbiter is AHEAD of the canonical file in time, so a disagreement at an
        # overlapping period is a revision between two vintages of the same publication,
        # not an extraction error. Recorded; the CSV is kept exactly as published.
        status = "INFO"
        note = (f"the parquet mirror is a NEWER VINTAGE (runs to {r_hi}, the "
                f"download-button CSV to {c_hi}) and has also revised the overlapping "
                f"{latest} values. The canonical CSV is kept as published; pulling the "
                "newer wave is an explicit vintage decision (refresh.py --apply). "
                + note)
    add(ds, label, 0, mism, status, note)
    if arbiter and status == "FAIL":
        for k in list(only_csv)[:3]:
            print(f"  MISMATCH {ds} csv-only {dict(k)}")


print("A. two-door checks (parquet arbiter + static API)")
for ds, (url, route) in REALECONOMY.items():
    rows = load(ds)
    try:
        compare(ds, rows, fetch_parquet(url), "parquet mirror", arbiter=True)
    except Exception as e:                                     # noqa: BLE001
        add(ds, "parquet_arbiter_fetch", "reachable", str(e)[:90], "FAIL")
    if route != "meta":
        try:
            compare(ds, rows, fetch_api(ds, route), f"api/{route}", arbiter=False)
        except Exception as e:                                 # noqa: BLE001
            add(ds, "api_door_fetch", "reachable", str(e)[:90], "INFO",
                "API door unreachable on this run; the parquet arbiter still verified "
                "the numbers.")
print(f"   {len(out)} checks so far")




# ---------------------------------------------------------------- B. identities
# Status convention, following verify_expansion.py:
#   PASS  the identity holds to the published rounding scale
#   INFO  it does not, and the cause is upstream — the values are verbatim from a
#         second-door-verified file, so a breach is a property of the source. Recorded
#         with a proof and the offending rows; NEVER corrected (CLAUDE.md rule 2).
#   FAIL  reserved for anything this pipeline could have caused.
# Every breaching row is also written out in full to data/_identity_breaches_realeconomy.csv
print("B. internal identities")

breaches = []          # dataset, check, key, published, implied, note


def log_breach(ds, check, key, published, implied, note=""):
    breaches.append([ds, check, key, published, implied, note])


def decimals(vals, cap=6):
    """The decimal step the given values are *published* to.

    Computed per comparison group rather than per file, because DOSM mixes precisions
    inside one file (lfs_state_sex is 1 dp except 2000-2003 which is 3 dp; the quarterly
    GDP files are whole RM million for some periods and 3 dp for others) — a single
    file-wide step would be wrong for most rows either way. Capped at 1e-6 so the
    occasional binary-float artefact (e.g. -702.8113124800198 in bop_balance) cannot
    collapse the tolerance to nothing.
    """
    d = 0
    for v in vals:
        s = str(v)
        if "." in s:
            d = max(d, min(cap, len(s.split(".")[1].rstrip("0"))))
    return 10 ** -d


def component_identity(ds, keycol, total, plus, minus=(), status_on_break="INFO"):
    """total == sum(plus) - sum(minus) per date, abs series only.

    Tolerance is the half-unit rounding bound: 0.5 * step * (number of terms), where
    step is the decimal precision the file itself is published to. DOSM's own caveat:
    "the sum of each category may not always equal to the totals ... because of
    independent rounding".
    """
    rows = [r for r in load(ds) if r.get("series", "abs") == "abs"]
    valcol = "value" if "value" in rows[0] else "index"
    terms = 1 + len(plus) + len(minus)
    by = defaultdict(dict)
    for r in rows:
        by[r["date"]][r[keycol]] = r[valcol]      # keep the printed string for precision
    bad, n, steps = [], 0, set()
    expr = total + " == " + "+".join(plus) + ("-" + "-".join(minus) if minus else "")
    need = [total] + list(plus) + list(minus)
    for d, m in sorted(by.items()):
        if any(num(m.get(c)) is None for c in need):
            continue                      # component genuinely absent for this period
        n += 1
        # half-unit bound on each independently-rounded term at THIS period's printed
        # precision, floored at one full unit so "agrees to the last printed digit"
        # always counts as agreement
        step = decimals([m[c] for c in need])
        steps.add(step)
        tol = max(0.5 * step * terms, step)
        lhs = num(m[total])
        rhs = sum(num(m[c]) for c in plus) - sum(num(m[c]) for c in minus)
        if abs(lhs - rhs) > tol:
            bad.append(f"{d[:7]}: {lhs} vs {rhs:.3f}")
            log_breach(ds, expr, d, lhs, round(rhs, 6), f"tol {tol:g}")
    add(ds, f"identity {expr} ({n} periods, per-period half-unit rounding bound on "
        f"{terms} terms; printed step {'/'.join(f'{s:g}' for s in sorted(steps))})",
        0, len(bad), "PASS" if not bad else status_on_break, "; ".join(bad[:3]))


EXP, SUP = ["e1", "e2", "e3", "e4", "e5"], ["p1", "p2", "p3", "p4", "p5", "p6"]
for ds in ("gdp_annual_nominal_demand", "gdp_annual_real_demand", "gdp_qtr_nominal_demand",
           "gdp_qtr_real_demand", "gdp_qtr_real_sa_demand",
           "gdp_annual_nominal_demand_granular", "gdp_annual_real_demand_granular",
           "gdp_qtr_nominal_demand_granular", "gdp_qtr_real_demand_granular"):
    component_identity(ds, "type", "e0", EXP, ["e6"])
for ds in ("gdp_annual_nominal_supply", "gdp_annual_real_supply", "gdp_qtr_nominal_supply",
           "gdp_qtr_real_supply", "gdp_qtr_real_sa_supply",
           "gdp_annual_nominal_supply_granular", "gdp_annual_real_supply_granular",
           "gdp_qtr_nominal_supply_granular", "gdp_qtr_real_supply_granular"):
    component_identity(ds, "sector", "p0", SUP)
component_identity("gdp_annual_nominal_income", "component", "i0", ["i1", "i2", "i3"])
component_identity("gdp_annual_nominal_income", "component", "i3", ["i3.1"], ["i3.2"])

# --- the three approaches to GDP must agree (SNA 2008 double entry)
sup = {r["date"]: num(r["value"]) for r in load("gdp_annual_nominal_supply")
       if r["series"] == "abs" and r["sector"] == "p0"}
dem = {r["date"]: num(r["value"]) for r in load("gdp_annual_nominal_demand")
       if r["series"] == "abs" and r["type"] == "e0"}
inc = {r["date"]: num(r["value"]) for r in load("gdp_annual_nominal_income")
       if r["series"] == "abs" and r["component"] == "i0"}
common = sorted(set(sup) & set(dem) & set(inc))
bad = []
for d in common:
    if max(abs(sup[d] - dem[d]), abs(sup[d] - inc[d])) > 0.001:
        bad.append(f"{d[:4]}: sup={sup[d]} dem={dem[d]} inc={inc[d]}")
        log_breach("gdp_annual_nominal_*", "production == expenditure == income", d,
                   sup[d], f"dem={dem[d]} inc={inc[d]}")
add("gdp_annual_nominal_*", "identity production == expenditure == income "
    f"({len(common)} years, tol RM 0.001 mil)", 0, len(bad),
    "PASS" if not bad else "INFO", "; ".join(bad[:3]))

# --- labour force accounting, at every published grain -----------------------------
# Rates are checked against a propagated rounding bound, not a flat tolerance: at DUN
# and district grain the levels are small ('000 persons, 1 dp), so the same absolute
# rounding produces a much larger percentage-point uncertainty.
AREA = ("dun", "parlimen", "district", "state", "sex")


def who(r):
    return " ".join(str(r[c]) for c in AREA if c in r) + " " + str(r.get("date", ""))[:7]


LFS = ("lfs_month", "lfs_qtr", "lfs_year", "lfs_qtr_state", "lfs_year_sex",
       "lfs_state_sex", "lfs_district", "lfs_parlimen", "lfs_dun")
for ds in LFS:
    rows = load(ds)
    lvl = [r for r in rows if num(r.get("lf")) and num(r.get("lf_employed")) is not None
           and num(r.get("lf_unemployed")) is not None]
    bad, steps = [], set()
    for r in lvl:
        step = decimals([r["lf"], r["lf_employed"], r["lf_unemployed"]])
        steps.add(step)
        implied = num(r["lf_employed"]) + num(r["lf_unemployed"])
        if abs(num(r["lf"]) - implied) > 1.5 * step:
            bad.append(who(r))
            log_breach(ds, "lf == lf_employed + lf_unemployed", who(r), num(r["lf"]),
                       round(implied, 4), f"tol {1.5 * step:g}")
    add(ds, f"identity lf == employed + unemployed ({len(lvl)} rows, per-row half-unit "
        f"bound on 3 terms; printed step {'/'.join(f'{s:g}' for s in sorted(steps))})",
        0, len(bad), "PASS" if not bad else "INFO", "; ".join(bad[:3]))

    for rate, numer, base_cols in (("u_rate", "lf_unemployed", ("lf",)),
                                   ("p_rate", "lf", ("lf", "lf_outside")),
                                   ("ep_ratio", "lf_employed", ("lf", "lf_outside"))):
        sel = [r for r in rows if num(r.get(rate)) is not None
               and all(num(r.get(c)) is not None for c in base_cols)
               and num(r.get(numer)) is not None and sum(num(r[c]) for c in base_cols)]
        if not sel:
            continue
        bad = []
        for r in sel:
            b = sum(num(r[c]) for c in base_cols)
            implied = 100 * num(r[numer]) / b
            rstep = decimals([r[rate]])
            step = decimals([r[numer]] + [r[c] for c in base_cols])
            # half-unit on the published rate + propagated half-unit on numerator/base,
            # floored at one full unit of the rate's own printed step so "agrees to the
            # last printed digit" counts as agreement (same rule as component_identity)
            tol = max(rstep,
                      0.5 * rstep + 100 * (0.5 * step / b + implied / 100
                                           * len(base_cols) * 0.5 * step / b))
            if abs(num(r[rate]) - implied) > tol:
                bad.append(f"{who(r)} {r[rate]} vs {implied:.2f}")
                log_breach(ds, f"{rate} == 100*{numer}/{'+'.join(base_cols)}", who(r),
                           num(r[rate]), round(implied, 3), f"tol {tol:.3f}")
        note = ""
        if bad and rate == "ep_ratio" and ds.endswith("_sex"):
            note = ("cross-dataset proof: for the same years lfs_year's ep_ratio "
                    "reproduces 100*employed/(lf+outside) exactly while lfs_year_sex's "
                    "'both' rows do not — the two DOSM datasets publish different "
                    "ep_ratio values for identical labour-force levels. ")
        add(ds, f"identity {rate} == 100*{numer}/({'+'.join(base_cols)}) ({len(sel)} rows, "
            "propagated rounding tol)", 0, len(bad),
            "PASS" if not bad else "INFO", note + "; ".join(bad[:3]))

# lfs_month_sa is deliberately NOT in the list above: each seasonally adjusted series is
# adjusted independently, so the components are not required to add to the total.
sa = load("lfs_month_sa")
dev = sorted(abs(num(r["lf"]) - num(r["lf_employed"]) - num(r["lf_unemployed"]))
             for r in sa if num(r.get("lf")) and num(r.get("lf_unemployed")) is not None)
add("lfs_month_sa", f"diagnostic |lf - (employed+unemployed)| ({len(dev)} months)", "n/a",
    f"median {dev[len(dev)//2]:.1f}k, max {dev[-1]:.1f}k", "INFO",
    "expected: X-12-ARIMA/SEAM adjusts each series independently, so the seasonally "
    "adjusted components are not additive. No identity asserted; use lfs_month for levels.")

# --- productivity is a derived ratio: it must reproduce from its own inputs ----------
for ds in ("productivity_annual", "productivity_qtr", "productivity_annual_priority"):
    rows = [r for r in load(ds) if r.get("series", "abs") == "abs"]
    for label, numer, den, scale in (("output_employment", "gdp", "employment", 1000.0),
                                     ("output_hour", "gdp", "hours", 1.0)):
        sel = [r for r in rows if num(r.get(den)) and num(r.get(label)) is not None]
        if not sel:
            continue
        rstep = decimals([r[label] for r in sel])
        bad = []
        for r in sel:
            implied = num(r[numer]) * scale / num(r[den])
            gstep, dstep = decimals([r[numer]]), decimals([r[den]])
            tol = 0.5 * rstep + implied * (0.5 * gstep / num(r[numer])
                                           + 0.5 * dstep / num(r[den]))
            if abs(num(r[label]) - implied) > tol:
                bad.append(f"{r['date'][:7]} {r.get('sector', '')}")
                log_breach(ds, f"{label} == {numer}/{den}",
                           f"{r['date']} {r.get('sector', '')}", num(r[label]),
                           round(implied, 4), f"tol {tol:.4f}")
        add(ds, f"identity {label} == {numer}/{den} ({len(sel)} abs rows, propagated "
            "rounding tol)", 0, len(bad), "PASS" if not bad else "INFO",
            "; ".join(bad[:3]))

# --- the income distribution must average back to the published mean ----------------
def percentile_vs_mean(pct_ds, mean_ds, keys):
    got = defaultdict(list)
    for r in load(pct_ds):
        if r["variable"] == "mean" and num(r["income"]) is not None:
            got[tuple(r[k] for k in keys)].append(num(r["income"]))
    pub = {tuple(r[k] for k in keys): num(r["income_mean"]) for r in load(mean_ds)}
    bad, n = [], 0
    for k, v in sorted(got.items()):
        if len(v) != 100 or pub.get(k) is None:
            continue
        n += 1
        avg = sum(v) / 100
        if abs(avg - pub[k]) > max(2.0, 0.002 * pub[k]):    # RM2 or 0.2%
            bad.append(f"{'/'.join(x[:7] for x in k)}: {avg:.1f} vs {pub[k]} "
                       f"({(avg - pub[k]) / pub[k] * 100:+.2f}%)")
            log_breach(pct_ds, f"mean(100 percentile means) == {mean_ds}.income_mean",
                       "/".join(k), pub[k], round(avg, 1),
                       f"{(avg - pub[k]) / pub[k] * 100:+.2f}%")
    add(pct_ds, f"identity mean(100 percentile means) == {mean_ds} income_mean "
        f"({n} groups, tol max(RM2, 0.2%))", 0, len(bad),
        "PASS" if not bad else "INFO", "; ".join(bad[:4]))


percentile_vs_mean("hies_malaysia_percentile", "hh_income", ["date"])
percentile_vs_mean("hies_state_percentile", "hh_income_state", ["state", "date"])

# --- poverty definitions nest -------------------------------------------------------
for ds in ("hh_poverty", "hh_poverty_state", "hh_poverty_district",
           "hh_poverty_parlimen", "hh_poverty_dun"):
    rows = [r for r in load(ds) if num(r.get("poverty_hardcore")) is not None
            and num(r.get("poverty_absolute")) is not None]
    bad = []
    for r in rows:
        if num(r["poverty_hardcore"]) > num(r["poverty_absolute"]) + 1e-9:
            bad.append(who(r))
            log_breach(ds, "hardcore <= absolute poverty", who(r),
                       num(r["poverty_absolute"]), num(r["poverty_hardcore"]))
    add(ds, f"identity hardcore <= absolute poverty ({len(rows)} rows)", 0, len(bad),
        "PASS" if not bad else "INFO", "; ".join(bad[:3]))

# --- hies_state vs the three single-indicator state datasets, same year -------------
gs = {(r["state"], r["date"]): num(r["gini"]) for r in load("hh_inequality_state")}
ps = {(r["state"], r["date"]): num(r["poverty_absolute"]) for r in load("hh_poverty_state")}
ms = {(r["state"], r["date"]): (num(r["income_mean"]), num(r["income_median"]))
      for r in load("hh_income_state")}
bad, n = [], 0
for r in load("hies_state"):
    k = (r["state"], r["date"])
    if k not in ms:
        continue
    n += 1
    for label, a, b, tol in (("income_mean", num(r["income_mean"]), ms[k][0], 0.5),
                             ("income_median", num(r["income_median"]), ms[k][1], 0.5),
                             ("gini", num(r["gini"]), gs.get(k), 5e-4),
                             ("poverty", num(r["poverty"]), ps.get(k), 0.05)):
        if b is not None and a is not None and abs(a - b) > tol:
            bad.append(f"{k[0]} {k[1][:4]} {label}: {a} vs {b}")
            log_breach("hies_state", f"{label} vs single-indicator state dataset",
                       f"{k[0]} {k[1]}", a, b)
add("hies_state", "crosscheck vs hh_income_state / hh_inequality_state / hh_poverty_state "
    f"({n} state-years x 4 indicators)", 0, len(bad),
    "PASS" if not bad else "INFO", "; ".join(bad[:3]))

# --- employment shares --------------------------------------------------------------
shares = defaultdict(float)
for r in load("employment_sector"):
    shares[(r["date"], r["sex"])] += num(r["proportion"]) or 0.0
bad = []
for k, v in sorted(shares.items()):
    if abs(v - 100.0) > 0.35:
        bad.append(f"{k[0][:4]} {k[1]}: {v:.1f}")
        log_breach("employment_sector", "sector proportions sum to 100", " ".join(k),
                   100.0, round(v, 2))
add("employment_sector", f"identity sector proportions sum to 100 ({len(shares)} date-sex "
    "groups, tol 0.35pp — source caveat: 'proportions may not sum to 100% due to "
    "rounding')", 0, len(bad), "PASS" if not bad else "INFO", "; ".join(bad[:3]))

# --- BOP: the financial-account sign convention is not published with the dataset, so
#     the residual is REPORTED as a diagnostic, not asserted as an identity.
bop = defaultdict(dict)
for r in load("bop_balance"):
    bop[r["date"]][r["account"]] = num(r["balance"])
res = sorted(abs(v["ca"] + v["ka"] + v["neo"] - v["fa"])
             for v in bop.values() if {"ca", "ka", "neo", "fa"} <= set(v))
add("bop_balance", f"diagnostic residual |ca+ka+neo-fa| ({len(res)} quarters)", "n/a",
    f"median RM {res[len(res)//2]:,.0f} mil, max RM {res[-1]:,.0f} mil", "INFO",
    "the financial-account sign convention is not published in the dataset; residual "
    "recorded for the analyst, no identity asserted")

# ---------------------------------------------------------------- write
dest = os.path.join(DATA, "_validation_realeconomy.csv")
with open(dest, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["dataset", "check", "expected", "got", "status", "note"])
    w.writerows(out)
bdest = os.path.join(DATA, "_identity_breaches_realeconomy.csv")
with open(bdest, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["dataset", "identity", "key", "published", "implied", "note"])
    w.writerows(breaches)

fails = [r for r in out if r[4] == "FAIL"]
infos = [r for r in out if r[4] == "INFO"]
print(f"\n{len(out)} checks: {len(out) - len(fails) - len(infos)} PASS, {len(infos)} INFO, "
      f"{len(fails)} FAIL -> {dest}")
print(f"{len(breaches)} individual identity breaches -> {bdest}")
for r in fails:
    print("FAIL:", r[0], "|", r[1], "| got", r[3], "|", r[5])
for r in infos:
    print("INFO:", r[0], "|", r[1][:70], "| got", r[3])
sys.exit(1 if fails else 0)
