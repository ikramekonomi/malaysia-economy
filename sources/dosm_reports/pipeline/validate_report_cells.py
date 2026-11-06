#!/usr/bin/env python3
"""Check the DOSM report tables (cells.csv) against themselves and against the DOSM open-data files already held.

  python3 sources/dosm_reports/pipeline/validate_report_cells.py -> sources/dosm_reports/data/_validation_report_cells.csv

Declared before the results were looked at (2026-11-06). Runs offline on the committed CSVs.
  R1 coverage     every numeric cell of every sheet is a captured cell, sits in a header row, or is a label printed as
                  a number (an income class's bounds, a year column)
                  (data/_extraction_coverage.csv, written by the extractor from the workbook itself)
  R2 display      value_printed is value rounded to the decimals value_printed shows (half away from zero)
  R3 open data    the same figure in the report and in the open-data file DOSM publishes for it, exact: the open-data
                  figure equals the number the workbook stores or the figure it prints (amended after the first run,
                  which compared the stored number only: the Salaries & Wages workbook stores the 2018 means unrounded,
                  3227.807..., prints 3,228, and the open data carry 3228; the poverty workbook stores hardcore
                  incidence 0.08, prints 0.1, and the open data carry 0.08):
                    poverty_2024 Jadual 2.1 / 3.1 / 4.0 (hardcore / absolute / relative incidence by state, 2022 and
                      2024, column 'Jumlah')                        vs sources/dosm/data/hh_poverty_state.csv
                    household_income_2024 Jadual 2.7 (median and mean by state, 2022 and 2024)
                                                                    vs sources/dosm/data/hh_income_state.csv
                    labour_annual_2025 Jadual A1.1 (participation rate, total, 2025) vs lfs_year.csv
                    salaries_wages_2025 Jadual A8 / A9 (recipients, median, mean by state and sex, 2010-2025)
                                                                    vs sources/dosm/data/wages_state.csv
                  A row whose report figure and open-data figure differ is a FAIL here unless it is registered, with its
                  proof, in data/_source_divergences.csv (status SOURCE_DIVERGENCE): a divergence between two DOSM
                  releases, kept as each prints it (golden rule 2), never a correction.
  R5 one report   (added after the blind verifier, 2026-11-06) a figure the poverty report prints twice is printed the
                  same: Jadual 5.4 (state rows: absolute and relative poverty, median and mean income, 2022 and 2024)
                  against Jadual 3.1 / 4.0 and household_income Jadual 2.7; Jadual 5.1 / 5.3 (Malaysia and state rows,
                  2022 and 2024) against Jadual 2.1 / 3.1. Exact on the printed figure; a registered difference reads
                  SOURCE_DIVERGENCE.
  R4 identity     household_income_2024 Jadual 2.7: the households of the 16 states add to Malaysia's, to the
                  rounding of 17 printed figures (8.5 thousand households at one decimal: 17 x 0.05)
"""
import csv
import os
import re
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(SRC))
DOSM = os.path.join(REPO, "sources", "dosm", "data")
OUT = os.path.join(SRC, "data", "_validation_report_cells.csv")
FIELDS = ["check", "publication", "table_no", "key", "report_value", "other_value", "status", "note"]
PUBS = ["household_income_2024", "household_expenditure_2024", "poverty_2024", "income_inequality_2024",
        "labour_annual_2025", "salaries_wages_2025"]


def cells(pub):
    return list(csv.DictReader(open(os.path.join(SRC, "data", pub, "cells.csv"), encoding="utf-8")))


def norm_state(s):
    s = re.sub(r"[^a-z]", "", s.lower())
    return {"wpkualalumpur": "wpkualalumpur", "kualalumpur": "wpkualalumpur", "wplabuan": "wplabuan",
            "wpputrajaya": "wpputrajaya"}.get(s, s)


def eq(a, b):
    try:
        return Decimal(a) == Decimal(b)
    except Exception:
        return False


def printed(r):
    return r["value_printed"].replace(",", "")


def same(r, other):
    return eq(r["value"], other) or eq(printed(r), other)


def main():
    out = []

    reg = {(d["publication"], d["sheet"], d["cell"]): d
           for d in csv.DictReader(open(os.path.join(SRC, "data", "_source_divergences.csv"), encoding="utf-8"))}

    def add(check, pub, tab, key, rv, ov, ok, note="", cell=None):
        st = "PASS" if ok else "FAIL"
        d = reg.get((pub, cell[0], cell[1])) if cell else None
        if not ok and d and d["report_value"] == rv and d["other_value"] == ov:
            st, note = "SOURCE_DIVERGENCE", f"{d['id']} (data/_source_divergences.csv); {note}"
        out.append(dict(check=check, publication=pub, table_no=tab, key=key, report_value=rv, other_value=ov,
                        status=st, note=note))

    # R1
    for r in csv.DictReader(open(os.path.join(SRC, "data", "_extraction_coverage.csv"), encoding="utf-8")):
        add("R1", r["publication"], "", r["sheet"], r["captured"], r["numeric_cells"], int(r["not_captured"]) == 0,
            f"{r['in_header_rows']} in header rows, {r['in_note_rows']} in notes, {r['in_label_columns']} printed as "
            f"labels (class bounds, years); not captured: "
            f"{r['not_captured_cells'] or 'none'}")
    data = {p: cells(p) for p in PUBS}
    # R2
    for p, rows in data.items():
        bad = []
        for r in rows:
            if not r["value"]:
                continue
            shown = r["value_printed"].replace(",", "").rstrip("%")
            dp = len(shown.split(".")[1]) if "." in shown else 0
            v = Decimal(r["value"]) * (100 if r["value_printed"].endswith("%") else 1)
            if "e" in shown.lower() or "E" in r["value"]:
                ok = Decimal(shown) == Decimal(r["value"]) if "e" in shown.lower() else True
            else:
                ok = v.quantize(Decimal(1).scaleb(-dp), rounding=ROUND_HALF_UP) == Decimal(shown)
            if not ok:
                bad.append(f"{r['sheet']}!{r['cell']}")
        add("R2", p, "", "all cells", str(sum(1 for r in rows if r["value"])), str(len(bad)), not bad,
            " ".join(bad[:20]))
    # R3 poverty
    pov = {}
    for r in csv.DictReader(open(os.path.join(DOSM, "hh_poverty_state.csv"), encoding="utf-8")):
        pov[(norm_state(r["state"]), r["date"][:4])] = r
    col = {"2.1": "poverty_hardcore", "3.1": "poverty_absolute", "4.0": "poverty_relative"}
    for r in data["poverty_2024"]:
        if r["table_no"] not in col or not r["col_header"].endswith("Jumlah | Total") or r["row_label"] == "Malaysia":
            continue
        yr = r["col_header"][:4]
        api = pov.get((norm_state(r["row_label"]), yr))
        if api is None:
            add("R3", "poverty_2024", r["table_no"], f"{r['row_label']} {yr} {r['cell']}", r["value"], "", False,
                "no open-data row")
            continue
        add("R3", "poverty_2024", r["table_no"], f"{r['row_label']} {yr} {r['cell']}", printed(r),
            api[col[r["table_no"]]], same(r, api[col[r["table_no"]]]), "hh_poverty_state.csv",
            (r["sheet"], r["cell"]))
    # R3 income
    inc = {(norm_state(r["state"]), r["date"][:4]): r
           for r in csv.DictReader(open(os.path.join(DOSM, "hh_income_state.csv"), encoding="utf-8"))}
    for r in data["household_income_2024"]:
        if r["table_no"] != "2.7" or not re.search(r"\(RM\) \| 20\d\d$", r["col_header"]):
            continue
        yr = r["col_header"][-4:]
        measure = "income_median" if r["col_header"].startswith("Penengah") else "income_mean"
        api = inc.get((norm_state(r["row_label"]), yr))
        if r["row_label"] == "Malaysia":
            continue
        if api is None:
            add("R3", "household_income_2024", "2.7", f"{r['row_label']} {yr} {measure}", r["value"], "", False,
                "no open-data row")
            continue
        add("R3", "household_income_2024", "2.7", f"{r['row_label']} {yr} {measure} {r['cell']}", printed(r),
            api[measure], same(r, api[measure]), "hh_income_state.csv", (r["sheet"], r["cell"]))
    # R3 labour force
    lfs = {r["date"][:4]: r for r in csv.DictReader(open(os.path.join(DOSM, "lfs_year.csv"), encoding="utf-8"))}
    for r in data["labour_annual_2025"]:
        if r["table_no"] == "A1.1" and r["row_label"] == "Jumlah (%) Total" and \
                r["col_header"] == "Jumlah | Total | Jumlah | Total":
            add("R3", "labour_annual_2025", "A1.1", f"participation rate 2025 {r['cell']}", printed(r),
                lfs["2025"]["p_rate"], same(r, lfs["2025"]["p_rate"]), "lfs_year.csv p_rate")
    # R3 wages: sheet -> (sex, measure); the Malaysia row of the A9 sheets is printed as the measure's own label
    wag = {(norm_state(r["state"]), r["date"][:4], r["sex"]): r
           for r in csv.DictReader(open(os.path.join(DOSM, "wages_state.csv"), encoding="utf-8"))}
    sheets = {}
    for sh in {r["sheet"] for r in data["salaries_wages_2025"] if r["table_no"] in ("A8", "A9")}:
        sex = "both" if sh.startswith("JADUAL A8") else "female" if "Prmpuan" in sh else "male"
        meas = "recipients" if "Penerima" in sh else "wages_median" if "Penengah" in sh else "wages_mean"
        sheets[sh] = (sex, meas)
    n_ok = n_bad = 0
    for r in data["salaries_wages_2025"]:
        if r["sheet"] not in sheets or not re.fullmatch(r"20\d\d", r["col_header"]):
            continue
        sex, meas = sheets[r["sheet"]]
        st = "malaysia" if re.match(r"(Penengah|Purata|Bil\. Penerima)", r["row_label"]) else norm_state(
            re.sub(r"\s*\d$", "", r["row_label"]))
        api = wag.get((st, r["col_header"], sex))
        if api is None:
            add("R3", "salaries_wages_2025", r["table_no"], f"{r['row_label']} {r['col_header']} {sex} {meas}",
                r["value"], "", False, "no open-data row")
            continue
        if same(r, api[meas]):
            n_ok += 1
        else:
            n_bad += 1
            add("R3", "salaries_wages_2025", r["table_no"],
                f"{r['row_label']} {r['col_header']} {sex} {meas} {r['sheet']}!{r['cell']}", printed(r), api[meas],
                False, "wages_state.csv", (r["sheet"], r["cell"]))
    add("R3", "salaries_wages_2025", "A8/A9", "state x year x sex x measure, equal", str(n_ok), str(n_ok + n_bad),
        n_ok > 0 and n_bad == 0, "wages_state.csv; any differing cell is listed on its own row")
    # R5
    pv = data["poverty_2024"]
    inc27 = {}
    for r in data["household_income_2024"]:
        m = re.search(r"\(RM\) \| (20\d\d)$", r["col_header"])
        if r["table_no"] == "2.7" and m:
            inc27[(norm_state(r["row_label"]), "median" if r["col_header"].startswith("Penengah") else "mean",
                   m.group(1))] = r
    t31 = {(norm_state(r["row_label"]), r["col_header"][:4]): r for r in pv if r["table_no"] == "3.1"
           and r["col_header"].endswith("Jumlah | Total")}
    t21 = {(norm_state(r["row_label"]), r["col_header"][:4]): r for r in pv if r["table_no"] == "2.1"
           and r["col_header"].endswith("Jumlah | Total")}
    t40 = {(norm_state(r["row_label"]), r["col_header"][:4]): r for r in pv if r["table_no"] == "4.0"
           and r["col_header"].endswith("Jumlah | Total")}
    states = {k[0] for k in t31}
    pairs = []
    for r in pv:
        st, yr = norm_state(r["row_label"]), r["col_header"][-4:]
        if st not in states or yr not in ("2022", "2024"):
            continue
        if r["table_no"] == "5.4":
            h = r["col_header"]
            ref = t31 if "Mutlak" in h else t40 if "Relatif" in h else None
            if ref is not None:
                pairs.append((r, ref.get((st, yr))))
            elif "Penengah" in h or "Purata" in h:
                pairs.append((r, inc27.get((st, "median" if "Penengah" in h else "mean", yr))))
        elif r["table_no"] in ("5.1", "5.3") and (r["section"] == "Negeri/State" or st == "malaysia") \
                and r["col_header"] in ("2022", "2024"):
            pairs.append((r, (t21 if r["table_no"] == "5.1" else t31).get((st, yr))))
    n_ok = 0
    for a, b in pairs:
        if b is None:
            add("R5", a["publication"], a["table_no"], f"{a['row_label']} {a['col_header'][-4:]} {a['sheet']}!{a['cell']}",
                printed(a), "", False, "no counterpart found in the declared chapter table")
        elif printed(a) == printed(b) or eq(a["value"], b["value"]):
            n_ok += 1
        else:
            add("R5", a["publication"], a["table_no"],
                f"{a['row_label']} {a['col_header'][-4:]}: {a['sheet']}!{a['cell']} vs {b['publication']} "
                f"Jadual {b['table_no']} {b['sheet']}!{b['cell']}", printed(a), printed(b), False,
                "the same figure printed twice in one release", (a["sheet"], a["cell"]))
    add("R5", "poverty_2024", "5.1/5.3/5.4", "figures printed twice, equal", str(n_ok), str(len(pairs)), n_ok > 0,
        "any unequal pair is listed on its own row")
    # R4
    t = [r for r in data["household_income_2024"] if r["table_no"] == "2.7" and "households" in r["col_header"]]
    for yr in ("2022", "2024"):
        rows = [r for r in t if r["col_header"].endswith(yr)]
        my = [Decimal(r["value_printed"].replace(",", "")) for r in rows if r["row_label"] == "Malaysia"]
        st = [Decimal(r["value_printed"].replace(",", "")) for r in rows if r["row_label"] != "Malaysia"]
        if len(my) == 1 and len(st) == 16:
            add("R4", "household_income_2024", "2.7", f"households, 16 states = Malaysia, {yr}", str(sum(st)),
                str(my[0]), abs(sum(st) - my[0]) <= Decimal("0.85"), "printed figures, '000; tolerance 17 x 0.05")
        else:
            add("R4", "household_income_2024", "2.7", f"households {yr}", str(len(st)), str(len(my)), False,
                "expected 16 states and one Malaysia row")
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    from collections import Counter
    print("report cells:", dict(Counter((r["check"], r["status"]) for r in out)))


if __name__ == "__main__":
    main()
