#!/usr/bin/env python3
"""gap_reported_vs_audited (docs/DATA_MODEL.md §10, Phase 5): do MOF, BNM and PKKP agree?

  python3 core/pipeline/build_gap_reported_vs_audited.py -> core/gap_reported_vs_audited.csv, core/_validation_gap_rva.csv

Method (declared 2026-11-06 00:55 MYT, committed before the view was built. While checking units I saw the
three printings of federal operating expenditure for 2019, 2022 and 2024, and no other result):
* Grain: federal headline indicator x year. Each publisher's figure as core holds it (built by build_core
  build_federal_reported), never mixed or corrected:
    pkkp_audited   PKKP, the Auditor-General's certified accounts, that year's own volume (basis audited)
    bnm_actual     BNM Monthly Statistical Bulletin table 3.1, the annual row (basis actual, current vintage)
    mof_actual     MOF Tinjauan Fiskal Jadual 1.1, the edition chosen by curated/pipeline/mof_editions.py (own
                   volume Y+2); what later editions print differently is kept in mof_restated_in
  Indicators: federal_gov.revenue.total, .expenditure.opex (before the transfer to the Development Fund),
  .expenditure.devex (gross), .expenditure.covid_fund, .expenditure.devex_loan_recovery, .expenditure.devex_net.
  A row exists where at least two publishers print the indicator for the year; an indicator printed by only one
  publisher (the overall balance, MOF only in core) is not a row (listed in check G4).
* Three pairs: bnm - pkkp, mof - pkkp, mof - bnm (RM, signed). Status of each pair:
    agree          |difference| <= half the printed unit of the coarser of the two printings (MOF prints whole
                   RM juta: RM500,000; BNM prints RM million to the decimals in its value; PKKP prints sen)
    differ_minor   beyond that, but |difference| <= 0.1% of the larger of the two figures
    differ         beyond 0.1%
    not_held       one side missing
  Thresholds declared here, before results. A difference is reported, never resolved: which publisher is right
  is not decided by this view (PKKP is the anchor of last resort, CLAUDE.md, but a reported figure may use another
  scope or a later revision).
* Checks: G1 every value equals its observation; G2 every row traces to observation ids; G3 every indicator and
  year present once; G4 coverage (INFO): years per publisher and the indicators left out; G5 status counts (INFO).
"""
import csv
import os
import sys
from collections import Counter, defaultdict
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "curated", "pipeline"))
from warehouse import CORE, Warehouse, fmt  # noqa: E402
from build_core import MOF_FED  # noqa: E402
import mof_editions  # noqa: E402

INDICATORS = ["federal_gov.revenue.total", "federal_gov.expenditure.opex", "federal_gov.expenditure.devex",
              "federal_gov.expenditure.covid_fund", "federal_gov.expenditure.devex_loan_recovery",
              "federal_gov.expenditure.devex_net"]
PUB = {"pkkp": "pkkp_audited", "bnm": "bnm_actual", "mof": "mof_actual"}
BASIS = {"pkkp": "audited", "bnm": "actual", "mof": "actual"}
PAIRS = [("bnm", "pkkp"), ("mof", "pkkp"), ("mof", "bnm")]
MINOR = Decimal("0.001")
FIELDS = ["geo_code", "indicator_code", "indicator", "year", "pkkp_audited", "bnm_actual", "mof_actual", "mof_edition",
          "bnm_vintage"] + [f"{a}_minus_{b}_rm" for a, b in PAIRS] + [f"{a}_vs_{b}_status" for a, b in PAIRS] + \
         ["mof_restated_in", "source_obs_ids", "note", "caveats", "release_id"]


def half_unit(pub, r):
    """Half the printed unit of one printing, in RM."""
    if pub == "pkkp":
        return Decimal("0.005")
    if pub == "mof":
        return Decimal("500000")
    p = (r.get("value_printed") or "").strip()
    dp = len(p.split(".")[1].rstrip("0")) if "." in p else 0
    return Decimal(1000000) * Decimal(5) / Decimal(10) ** (dp + 1)


def main():
    w = Warehouse()
    cells = defaultdict(dict)
    dup = []
    for r in w.obs:
        if r["indicator_code"] not in INDICATORS or r["geo_code"] != "MY" or r["breakdown_key"] != "_total":
            continue
        pub = r["edition_id"].split(":")[0]
        if pub not in PUB or r["basis"] != BASIS[pub]:
            continue
        k = (r["indicator_code"], r["period_code"])
        if pub in cells[k]:
            dup.append((k, pub))
        cells[k][pub] = r
    restated = {}
    for (line, year), r in mof_editions.choose(mof_editions.load_all("fact_headline")).items():
        if line in MOF_FED and r.get("restated_in"):
            restated[(MOF_FED[line], str(year))] = r["restated_in"].replace("prints", "prints RM juta")
    out, checks, single = [], [], Counter()
    for (ind, y), d in sorted(cells.items(), key=lambda x: (INDICATORS.index(x[0][0]), x[0][1])):
        if len(d) < 2:
            single[(ind, next(iter(d)))] += 1
            continue
        row = {k: "" for k in FIELDS}
        row.update(geo_code="MY", indicator_code=ind, indicator=w.ind.get(ind, {}).get("name_en", ""), year=y,
                   release_id=w.release_id)
        val, notes, cv = {}, [], set()
        for pub, r in d.items():
            val[pub] = Decimal(r["value"])
            row[PUB[pub]] = fmt(val[pub])
            cv |= set(w.caveats_for(r))
        row["mof_edition"] = d["mof"]["vintage"] if "mof" in d else ""
        row["bnm_vintage"] = d["bnm"]["vintage"] if "bnm" in d else ""
        for a, b in PAIRS:
            if a in val and b in val:
                dd = val[a] - val[b]
                tol = max(half_unit(a, d[a]), half_unit(b, d[b]))
                row[f"{a}_minus_{b}_rm"] = fmt(dd)
                row[f"{a}_vs_{b}_status"] = ("agree" if abs(dd) <= tol else
                                             "differ_minor" if abs(dd) <= MINOR * max(abs(val[a]), abs(val[b])) else
                                             "differ")
            else:
                row[f"{a}_vs_{b}_status"] = "not_held"
        row["mof_restated_in"] = restated.get((ind, y), "")
        if "pkkp" not in val:
            notes.append("no audited figure: PKKP does not print this line" if ind.endswith(("loan_recovery", "net"))
                         else "no audited figure held for this year (PKKP is held for FY2009-2024)")
        row["source_obs_ids"] = ";".join(d[p]["obs_id"] for p in ("pkkp", "bnm", "mof") if p in d)
        row["caveats"] = ";".join(sorted(cv))
        row["note"] = "; ".join(notes)
        out.append(row)

    def add(c, st, dt):
        checks.append(dict(check=c, scope="core/gap_reported_vs_audited.csv", status=st, detail=dt))
    bad = [r for r in out for pub, col in PUB.items() if r[col] and not any(
        w.by_id[i]["edition_id"].startswith(pub + ":") and Decimal(w.by_id[i]["value"]) == Decimal(r[col])
        for i in r["source_obs_ids"].split(";"))]
    add("G1 every value equals its observation", "PASS" if not bad else "FAIL", f"{len(out)} rows")
    bad = [r for r in out if any(i not in w.by_id for i in r["source_obs_ids"].split(";"))]
    add("G2 every row traces to observation ids", "PASS" if not bad else "FAIL", f"{len(out)} rows")
    keys = [(r["indicator_code"], r["year"]) for r in out]
    add("G3 every indicator and year present once", "PASS" if len(keys) == len(set(keys)) and not dup else "FAIL",
        f"{len(keys)} rows" + (f"; two observations of one publisher: {dup[:5]}" if dup else ""))
    yrs = defaultdict(list)
    for (ind, y), d in cells.items():
        for p in d:
            yrs[(ind, p)].append(y)
    add("G4 coverage (INFO)", "INFO", "; ".join(f"{i.split('.')[-1]}/{p} {min(v)}-{max(v)}" for (i, p), v in
                                               sorted(yrs.items())) + "; left out (one publisher only): " +
        (", ".join(f"{i} ({p}, {n} years)" for (i, p), n in sorted(single.items())) or "none")
        + "; federal_gov.overall_balance: MOF only in core")
    for a, b in PAIRS:
        c = Counter((r["indicator_code"].split(".")[-1], r[f"{a}_vs_{b}_status"]) for r in out
                    if r[f"{a}_vs_{b}_status"] != "not_held")
        add(f"G5 {a} vs {b} status counts (INFO)", "INFO", ", ".join(f"{i}/{s} {n}" for (i, s), n in sorted(c.items())))
    with open(os.path.join(CORE, "gap_reported_vs_audited.csv"), "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        wr.writeheader()
        wr.writerows(out)
    with open(os.path.join(CORE, "_validation_gap_rva.csv"), "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=["check", "scope", "status", "detail"], lineterminator="\n")
        wr.writeheader()
        wr.writerows(checks)
    print(f"gap_reported_vs_audited: {len(out)} rows; " + "; ".join(f"{c['check'][:2]} {c['status']}" for c in checks))
    if any(c["status"] == "FAIL" for c in checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
