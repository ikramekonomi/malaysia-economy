#!/usr/bin/env python3
"""Reconcile every parsed Tinjauan Fiskal edition to its own printed identities, then
catalogue how each year's figures move between editions.

Run after extract_public_finance_stats.py and extract_breakdowns.py.
Writes: data/<edition>_public_finance_stats/_validation.csv   (2019-2027, not 2021,
                                                                which keeps its own)
        data/_validation_editions_summary.csv
        data/_restatements_editions.csv

ROUNDING, STATED RATHER THAN HIDDEN
-----------------------------------
Every figure in these tables is printed rounded to the nearest RM juta. A sum of n printed
figures can therefore differ from a printed total by up to 0.5 x (n + 1) juta -- half a
juta on each component and on the total -- with nothing wrong anywhere. Each check
carries that bound in `band_juta`, and the status says which case it is:
    PASS           exact
    PASS_ROUNDING  within the rounding bound of its own printed figures
    FOOTNOTED      fails, and a term in it carries a printed footnote that explains the
                   gap (2019 edition: FY2018 net domestic borrowing "excludes net issuance
                   of Treasury bills of RM2 bilion" -- the financing falls short of the
                   deficit by exactly RM2,000 juta)
    SOURCE_ANOMALY fails as PRINTED, confirmed on a page render; listed one by one in
                   KNOWN_SOURCE_ANOMALIES below and in data/_source_anomalies.csv
    FAIL           anything else beyond the bound -- stops nothing, but is investigated
A FAIL is investigated, never widened away.
"""
import csv
import glob
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

# (edition, check, year) -> the anomaly, confirmed against a 150-dpi render of the page
KNOWN_SOURCE_ANOMALIES = {
    (2024, "3.1 debt_service = domestic + external", 2022):
        "both the 2024 and 2025 editions print domestic debt service 40,533 + external 716 "
        "= 41,249 under a printed total of 41,269; the 2026 edition restates domestic to "
        "40,553, which foots",
    (2025, "3.1 debt_service = domestic + external", 2022):
        "as the 2024 edition: 40,533 printed, restated to 40,553 in the 2026 edition",
}

COMPONENT_L1 = ["emoluments", "retirement_charges", "debt_service", "grants_state_govts",
                "supplies_services", "subsidies_social_assistance", "asset_acquisition",
                "refunds_writeoffs", "grants_statutory_bodies", "other"]
SECTOR_L1_OPEX = ["economic", "social", "security", "general_admin", "other"]
SECTOR_L1_DEVEX = ["economic", "social", "security", "general_admin"]


def load(path):
    if not os.path.exists(path):
        return []
    return list(csv.DictReader(open(path)))


def grid(rows, field="amount_rm_juta"):
    g = defaultdict(dict)
    for r in rows:
        v = r.get(field)
        if v not in ("", None):
            g[r["line"]][int(r["target_year"])] = float(v)
    return g


def validate(edition):
    folder = os.path.join(DATA, f"{edition}_public_finance_stats")
    hl_rows = load(os.path.join(folder, "fact_headline.csv"))
    hl, pct = grid(hl_rows), grid(hl_rows, "pct_of_gdp")
    oc = grid(load(os.path.join(folder, "fact_opex_by_component.csv")))
    os_ = grid(load(os.path.join(folder, "fact_opex_by_sector.csv")))
    ds = grid(load(os.path.join(folder, "fact_devex_by_sector.csv")))
    ds_share = grid(load(os.path.join(folder, "fact_devex_by_sector.csv")), "pct_share")
    oc_share = grid(load(os.path.join(folder, "fact_opex_by_component.csv")), "pct_share")
    years = sorted(hl["revenue"])
    checks = []

    footnotes = {(r["line"], int(r["target_year"])): r["note"] for r in hl_rows
                 if "printed with footnote" in r.get("note", "")}

    def check(name, year, expected, parts, unit="juta", lines=()):
        """expected: printed total; parts: list of printed figures (signed) that sum to it;
        lines: the line keys behind parts, so a footnoted term can be named."""
        if expected is None or any(p is None for p in parts):
            checks.append([name, year, expected, None, None, "", "SKIP", "a term is not printed"])
            return
        got = sum(parts)
        diff = got - expected
        band = 0.5 * (len(parts) + 1) if unit == "juta" else 0.05 * (len(parts) + 1)
        status = "PASS" if abs(diff) < 1e-9 else ("PASS_ROUNDING" if abs(diff) <= band + 1e-9 else "FAIL")
        note = ""
        if status == "FAIL":
            fn = [footnotes[(l, year)] for l in lines if (l, year) in footnotes]
            if fn:
                status, note = "FOOTNOTED", fn[0]
            elif (edition, name, year) in KNOWN_SOURCE_ANOMALIES:
                status, note = "SOURCE_ANOMALY", KNOWN_SOURCE_ANOMALIES[(edition, name, year)]
        checks.append([name, year, expected, round(got, 4), round(diff, 4), band, status, note])

    g = lambda d, k, y: d.get(k, {}).get(y)
    for y in years:
        # ---- 1.1 -----------------------------------------------------------------
        check("1.1 current_balance = revenue - opex", y, g(hl, "current_balance", y),
              [g(hl, "revenue", y), -g(hl, "operating_expenditure", y)
               if g(hl, "operating_expenditure", y) is not None else None])
        check("1.1 devex_gross = direct + gross_lending", y, g(hl, "development_expenditure_gross", y),
              [g(hl, "development_expenditure_direct", y), g(hl, "development_expenditure_gross_lending", y)])
        lr = g(hl, "development_expenditure_loan_recovery", y)
        check("1.1 devex_net = gross - loan_recovery", y, g(hl, "development_expenditure_net", y),
              [g(hl, "development_expenditure_gross", y), -lr if lr is not None else None])
        covid = g(hl, "covid19_fund", y)
        parts = [g(hl, "current_balance", y), -(g(hl, "development_expenditure_net", y) or 0)]
        if covid is not None:
            parts.append(-covid)
        check("1.1 overall_balance = current_balance - devex_net - covid_fund", y,
              g(hl, "overall_balance", y), parts)
        fin = [g(hl, k, y) for k in ("net_offshore_borrowings", "net_domestic_borrowings",
                                      "change_in_assets")]
        if all(f is not None for f in fin):
            ob = g(hl, "overall_balance", y)
            check("1.1 financing sources sum to the deficit", y, -ob if ob is not None else None, fin,
                  lines=("net_offshore_borrowings", "net_domestic_borrowings", "change_in_assets"))

        # ---- 3.1 -----------------------------------------------------------------
        if oc:
            check("3.1 debt_service = domestic + external", y, g(oc, "debt_service", y),
                  [g(oc, "debt_service_domestic", y), g(oc, "debt_service_external", y)])
            check("3.1 grants_state_govts = constitutional + other", y, g(oc, "grants_state_govts", y),
                  [g(oc, "grants_constitutional", y), g(oc, "grants_other", y)])
            check("3.1 sum(level-1 lines) = total", y, g(oc, "total", y),
                  [g(oc, k, y) for k in COMPONENT_L1])
            check("3.1 total = 1.1 operating_expenditure", y, g(hl, "operating_expenditure", y),
                  [g(oc, "total", y)])
            check("3.1 level-1 shares sum to 100", y, 100.0,
                  [g(oc_share, k, y) for k in COMPONENT_L1], unit="pct")
        # ---- 3.2 / 3.3 -----------------------------------------------------------
        for tag, d, l1, total_line in (("3.2", os_, SECTOR_L1_OPEX, "operating_expenditure"),
                                       ("3.3", ds, SECTOR_L1_DEVEX, "development_expenditure_gross")):
            if not d:
                continue
            for sector in ("economic", "social", "security"):
                subs = sorted(k for k in d if k.startswith(sector + "_"))
                check(f"{tag} {sector} = sum(sub-items)", y, g(d, sector, y), [g(d, k, y) for k in subs])
            check(f"{tag} sum(level-1 lines) = total", y, g(d, "total", y), [g(d, k, y) for k in l1])
            check(f"{tag} total = 1.1 {total_line}", y, g(hl, total_line, y), [g(d, "total", y)])
        if ds_share:
            check("3.3 level-1 shares sum to 100", y, 100.0,
                  [g(ds_share, k, y) for k in SECTOR_L1_DEVEX], unit="pct")

    with open(os.path.join(folder, "_validation.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["check", "target_year", "printed", "computed", "diff", "band_juta",
                    "result", "note"])
        w.writerows(checks)
    return checks


def restatements():
    """Every (table, line, year) printed as official_actual by more than one edition."""
    seen = defaultdict(dict)    # (file, line, year) -> {edition: value}
    for folder in sorted(glob.glob(os.path.join(DATA, "*_public_finance_stats"))):
        edition = int(os.path.basename(folder)[:4])
        for fn in ("fact_headline", "fact_opex_by_component", "fact_opex_by_sector",
                   "fact_devex_by_sector"):
            for r in load(os.path.join(folder, f"{fn}.csv")):
                if r["basis"] != "official_actual" or r["amount_rm_juta"] in ("", None):
                    continue
                seen[(fn, r["line"], int(r["target_year"]))][edition] = float(r["amount_rm_juta"])
    rows = []
    for (fn, line, year), by_ed in sorted(seen.items()):
        if len(by_ed) < 2:
            continue
        eds = sorted(by_ed)
        first = by_ed[eds[0]]
        moves = [by_ed[e] - first for e in eds]
        rows.append([fn, line, year, ";".join(f"{e}={by_ed[e]:g}" for e in eds),
                     round(max(moves, key=abs), 3),
                     "restated" if any(abs(m) > 0 for m in moves) else "stable"])
    with open(os.path.join(DATA, "_restatements_editions.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["table", "line", "target_year", "value_by_edition_rm_juta",
                    "largest_move_vs_first_rm_juta", "status"])
        w.writerows(rows)
    return rows


def main():
    summary = []
    for folder in sorted(glob.glob(os.path.join(DATA, "*_public_finance_stats"))):
        edition = int(os.path.basename(folder)[:4])
        if edition == 2021:
            continue          # validated by its own extractor (80/80) and by the parser check
        checks = validate(edition)
        tally = defaultdict(int)
        for c in checks:
            tally[c[6]] += 1
        summary.append([edition, len(checks), tally["PASS"], tally["PASS_ROUNDING"],
                        tally["FOOTNOTED"], tally["SOURCE_ANOMALY"], tally["FAIL"], tally["SKIP"]])
        print(f"{edition}: {len(checks)} checks  PASS={tally['PASS']}  "
              f"PASS_ROUNDING={tally['PASS_ROUNDING']}  FOOTNOTED={tally['FOOTNOTED']}  "
              f"SOURCE_ANOMALY={tally['SOURCE_ANOMALY']}  FAIL={tally['FAIL']}  SKIP={tally['SKIP']}")
        for c in checks:
            if c[6] in ("FAIL", "FOOTNOTED", "SOURCE_ANOMALY"):
                print(f"    {c[6]} {c[0]} {c[1]}: printed {c[2]} computed {c[3]} diff {c[4]} (band {c[5]})")
    with open(os.path.join(DATA, "_validation_editions_summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["edition", "checks", "pass", "pass_rounding", "footnoted", "source_anomaly",
                    "fail", "skip"])
        w.writerows(summary)
    rs = restatements()
    moved = [r for r in rs if r[5] == "restated"]
    print(f"restatements: {len(rs)} (line, year) pairs printed as actual by 2+ editions, "
          f"{len(moved)} differ between editions")


if __name__ == "__main__":
    main()
