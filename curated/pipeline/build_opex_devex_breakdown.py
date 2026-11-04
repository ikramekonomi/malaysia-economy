#!/usr/bin/env python3
"""OPEX-by-component, OPEX-by-sector, DEVEX-by-sector -- curated from MOF Tinjauan
Fiskal's own Jadual 3.1/3.2/3.3 (7.1-7.3 in the 2023 edition): finer than anything
derivable from PKKP or DOSM alone.

Run:  python3 curated/pipeline/build_opex_devex_breakdown.py
Reads : sources/mof-fiscal-outlook/data/<edition>_public_finance_stats/*.csv, editions
        2019-2027 (the source CSVs directly -- golden rule 1)
Writes: curated/fact_opex_by_component.csv
        curated/fact_opex_by_sector.csv
        curated/fact_devex_by_sector.csv
        curated/_validation_breakdowns.csv -- every curated year foots on its own

ONE YEAR, ONE EDITION
---------------------
Each edition prints five years, so most actual years appear in three editions, and the
editions sometimes disagree. Which edition supplies each year is decided by the shared
rule in mof_editions.py -- strongest basis first, then the year's own edition (the one in
which it is the newest actual) -- and `restated_in` on each row lists what later editions
print instead. Years with no actual yet (FY2026 revised estimate, FY2027 budget estimate)
come from the newest edition and say so in `basis`: filter on basis before building a
series of outturns.

KNOWN BREAKS -- READ BEFORE PLOTTING A SECTOR SERIES
----------------------------------------------------
* "Pertanian dan pembangunan luar bandar" (editions 2019-2021) became "Pertanian" (2022
  onward). A RENAME, proven: the overlap years print identically under both labels in three
  editions. Conformed to one line, economic_agriculture, by mof_editions.LINE_CROSSWALK;
  line_bm keeps the label each row was printed under, and its note says so.
* The 2024 edition reclassified about RM1.1-1.2 bil a year of FY2020-21 operating
  expenditure from general administration to housing. Under the own-edition rule FY2020
  and FY2021 carry the OLD classification and FY2022 onward the new one, so housing
  steps from ~RM0.01 bil to ~RM1.2 bil at FY2022 by reclassification, not by spending.
  The rows for FY2020-21 say so in `restated_in`.
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CURATED = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import mof_editions  # noqa: E402

OUT = {
    "fact_opex_by_component": os.path.join(CURATED, "fact_opex_by_component.csv"),
    "fact_opex_by_sector": os.path.join(CURATED, "fact_opex_by_sector.csv"),
    "fact_devex_by_sector": os.path.join(CURATED, "fact_devex_by_sector.csv"),
}

FIELDS = ["year", "line", "line_bm", "line_en", "level", "parent_line", "amount_rm",
          "pct_share", "basis", "source_edition", "source_table", "source_file",
          "pdf_page", "printed_page", "restated_in", "note"]


def source_anomaly_lines(edition, year):
    """Lines of one edition-year that its own validation proved do not foot AS PRINTED
    (SOURCE_ANOMALY). The parent named in the check and its sub-items get a note, so the
    curated row says its components do not add up -- not only the source folder."""
    path = os.path.join(mof_editions.MOF_DATA, f"{edition}_public_finance_stats", "_validation.csv")
    if not os.path.exists(path):
        return {}
    out = {}
    for v in csv.DictReader(open(path)):
        if v["result"] == "SOURCE_ANOMALY" and int(v["target_year"]) == year:
            parent = v["check"].split()[1]            # "3.1 debt_service = domestic + external"
            out[parent] = v["note"]
    return out


def build(table):
    chosen = mof_editions.choose(mof_editions.load_all(table))
    out = []
    anomalies = {}
    for (line, year), r in sorted(chosen.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        amt = r["amount_rm_juta"]
        key = (r["edition"], year)
        if key not in anomalies:
            anomalies[key] = source_anomaly_lines(*key)
        note = r["note"]
        for parent, why in anomalies[key].items():
            if line == parent or line.startswith(parent + "_"):
                flag = (f"SOURCE ANOMALY in this edition: {parent} and its sub-items do not "
                        f"foot as printed -- {why} (sources/mof-fiscal-outlook/data/_source_anomalies.csv)")
                note = f"{note}; {flag}" if note else flag
        out.append({
            "year": year, "line": line, "line_bm": r["line_bm"], "line_en": r["line_en"],
            "level": int(r["level"]), "parent_line": r["parent_line"],
            "amount_rm": round(float(amt) * 1e6, 2) if amt not in ("", None) else None,
            "pct_share": r["pct_share"] or None, "basis": r["basis"],
            "source_edition": f"tinjauan_fiskal_{r['edition']}",
            "source_table": r["table_no"],
            "source_file": f"{r['edition']}/{r['source_file']}",
            "pdf_page": r["pdf_page"], "printed_page": r["printed_page"] or None,
            "restated_in": r["restated_in"], "note": note,
        })
    out.sort(key=lambda r: (r["year"], r["level"], r["line"]))
    return out


# A year is one edition's printed column, so it must foot. Rounding bound: each printed
# figure is rounded to the nearest RM juta, so a sum of n may miss by 0.5 x (n + 1) juta.
L1 = {"fact_opex_by_component": ["emoluments", "retirement_charges", "debt_service",
                                 "grants_state_govts", "supplies_services",
                                 "subsidies_social_assistance", "asset_acquisition",
                                 "refunds_writeoffs", "grants_statutory_bodies", "other"],
      "fact_opex_by_sector": ["economic", "social", "security", "general_admin", "other"],
      "fact_devex_by_sector": ["economic", "social", "security", "general_admin"]}
TOTAL_IN_HEADLINE = {"fact_opex_by_component": "operating_expenditure",
                     "fact_opex_by_sector": "operating_expenditure",
                     "fact_devex_by_sector": "development_expenditure_gross"}


def validate(table, rows, checks):
    by_year = {}
    for r in rows:
        if r["amount_rm"] is not None:
            by_year.setdefault(r["year"], {})[r["line"]] = r["amount_rm"] / 1e6
    hl = mof_editions.choose(mof_editions.load_all("fact_headline"))

    edition_of = {r["year"]: int(r["source_edition"][-4:]) for r in rows}

    def source_verdict(year, line):
        """A failure the SOURCE's own validation already proved printed (SOURCE_ANOMALY,
        confirmed on a page render) is inherited, not re-reported as a new failure."""
        ed = edition_of.get(year)
        path = os.path.join(mof_editions.MOF_DATA, f"{ed}_public_finance_stats", "_validation.csv")
        if ed is None or not os.path.exists(path):
            return None
        for v in csv.DictReader(open(path)):
            if v["result"] == "SOURCE_ANOMALY" and int(v["target_year"]) == year and line in v["check"]:
                return v["note"]
        return None

    def check(name, year, total, parts, line=None):
        diff = sum(parts) - total
        band = 0.5 * (len(parts) + 1)
        status = "PASS" if abs(diff) < 1e-6 else "PASS_ROUNDING" if abs(diff) <= band + 1e-6 else "FAIL"
        note = ""
        if status == "FAIL" and line:
            inherited = source_verdict(year, line)
            if inherited:
                status, note = "SOURCE_ANOMALY", inherited
        checks.append([table, name, year, round(total, 3), round(sum(parts), 3), round(diff, 3),
                       band, status, note])

    for year, g in sorted(by_year.items()):
        check("sum(level-1 lines) = total", year, g["total"], [g[k] for k in L1[table] if k in g])
        parents = {"debt_service": ["debt_service_domestic", "debt_service_external"],
                   "grants_state_govts": ["grants_constitutional", "grants_other"]} \
            if table == "fact_opex_by_component" else \
            {s: [k for k in g if k.startswith(s + "_")] for s in ("economic", "social", "security")}
        for parent, kids in parents.items():
            if parent in g and kids:
                check(f"{parent} = sum(sub-items)", year, g[parent], [g[k] for k in kids if k in g],
                      line=parent)
        h = hl.get((TOTAL_IN_HEADLINE[table], year))
        if h is not None:
            # the same year's headline may come from the same edition by the same rule
            check(f"total = Jadual 1.1 {TOTAL_IN_HEADLINE[table]}", year,
                  float(h["amount_rm_juta"]), [g["total"]])


def main():
    checks = []
    for table, path in OUT.items():
        rows = build(table)
        validate(table, rows, checks)
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
        years = sorted({r["year"] for r in rows})
        eds = sorted({r["source_edition"][-4:] for r in rows})
        print(f"{path}: {len(rows)} rows, FY{years[0]}-{years[-1]}, from editions {', '.join(eds)}")
    dest = os.path.join(CURATED, "_validation_breakdowns.csv")
    with open(dest, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["table", "check", "year", "printed_total_juta", "sum_of_parts_juta",
                    "diff_juta", "band_juta", "status", "note"])
        w.writerows(checks)
    from collections import Counter
    tally = Counter(c[7] for c in checks)
    print(f"{dest}: {len(checks)} checks -- " + ", ".join(f"{v} {k}" for k, v in sorted(tally.items())))
    for c in checks:
        if c[7] in ("FAIL", "SOURCE_ANOMALY"):
            print(f"  {c[7]}", c[:7])


if __name__ == "__main__":
    main()
