"""DOSM survey-report tables (sources/dosm_reports, L1 cells as printed) into fact_observation, table by table.

The mapping is declared here, one entry per table, before the loaded rows were looked at (2026-11-06):
which indicator, what the row labels and the column headers mean (geo, period, breakdown), and which columns are
left at L1. Decision D35: a report figure joins the core only when the open data held do not already carry the
same figure for the same key (indicator, place, period, breakdown); where the two DOSM releases print different
figures for one key (sources/dosm_reports/data/_source_divergences.csv), both are kept, each under its own
edition. Growth rates (compounded annual growth, derivable from two held levels) stay at L1 (D34).

The value loaded is the figure the report prints (value_printed: the workbook's stored number under its own number
format, which the PDF twin prints); the workbook stores more digits behind some figures (hardcore poverty 0.03
printed 0.0; RM 4,920.0000001 printed 4,920), kept at L1 in cells.csv 'value'. A figure printed in more than one
table of a report (Malaysia's median in the state table and as the total of the ethnicity table) is loaded once,
from the first table declared below, and the copies are checked equal (an unequal copy stops the build).

Breakdown axes of a household's head are their own axes (hoh_ethnicity, hoh_sex, hoh_age), not the person axes
(ethnicity, sex, age): a household headed by a woman is not a woman. hh_size is the household's size.
"""
import csv
import os
import re
from decimal import Decimal

CORE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(CORE)
SRC = os.path.join(REPO, "sources", "dosm_reports", "data")
STATES = {"johor": "MY-01", "kedah": "MY-02", "kelantan": "MY-03", "melaka": "MY-04", "negerisembilan": "MY-05",
          "pahang": "MY-06", "pulaupinang": "MY-07", "perak": "MY-08", "perlis": "MY-09", "selangor": "MY-10",
          "terengganu": "MY-11", "sabah": "MY-12", "sarawak": "MY-13", "wpkualalumpur": "MY-14",
          "wplabuan": "MY-15", "wpputrajaya": "MY-16", "malaysia": "MY"}
ETH = [(r"^Jumlah", None), (r"^Bumiputera", "bumi"), (r"^Cina", "chinese"), (r"^India", "indian"),
       (r"^Lain", "other")]
SIZE = {"Satu/One": "1", "Dua/Two": "2", "Tiga/Three": "3", "Empat/Four": "4", "Lima/Five": "5",
        "Enam dan ke atas Six and above": "6_above"}


def state(label):
    return STATES.get(re.sub(r"[^a-z]", "", label.lower()))


def ethnicity(label):
    for pat, code in ETH:
        if re.match(pat, label):
            return ("total",) if code is None else ("hoh_ethnicity", code)
    return None


def age_group(label):
    if re.match(r"^Jumlah", label):
        return ("total",)
    m = re.match(r"^(\d+)\s*[-–−]\s*(\d+)$", label)
    if m:
        return ("hoh_age", f"{m.group(1)}_{m.group(2)}")
    if re.match(r"^65\b", label):
        return ("hoh_age", "65_above")
    return None


def person_age(label):
    if re.match(r"^Jumlah", label):
        return ("total",)
    m = re.match(r"^(\d+)\s*[-–−]\s*(\d+)$", label)
    return ("age", f"{m.group(1)}_{m.group(2)}") if m else None


def hh_size(label):
    if re.match(r"^Jumlah", label):
        return ("total",)
    return ("hh_size", SIZE[label]) if label in SIZE else None


def year_of(col, title):
    m = re.search(r"\b(20\d\d)\b(?!\s*[–-])", col)
    if m:
        return m.group(1)
    return re.findall(r"\b(20\d\d)\b", title)[-1]


def strata_of(col):
    return "rural" if re.search(r"\bRural\b", col) else "urban" if re.search(r"\bUrban\b", col) else None


def sex_of(col):
    return "female" if re.search(r"\bFemale\b", col) else "male" if re.search(r"\bMale\b", col) else None


def mean_or_median(col):
    return "median" if "Median" in col else "mean" if "Mean" in col else None


# table -> (row parser: label -> geo or breakdown part, column parser: header -> (indicator suffix | None, parts))
# indicator: a fixed code, or a format with {m} (median / mean) taken from the column
TABLES = {
    "poverty_2024": {
        "1.1": ("poverty.pli.mean", "state", "plain"),
        "1.2": ("poverty.pli.mean", "state", "strata"),
        "1.3": ("poverty.pli.mean", "ethnicity", "strata"),
        "1.4": ("poverty.pli.mean", "state", "component"),
        "2.1": ("poverty.hardcore.rate", "state", "strata"),
        "2.2": ("poverty.hardcore.rate", "ethnicity", "strata"),
        "2.3": ("poverty.hardcore.rate", "ethnicity", "hoh_sex"),
        "2.4": ("poverty.hardcore.rate", "hoh_age", "plain"),
        "2.5": ("poverty.hardcore.rate", "hh_size", "plain"),
        "3.1": ("poverty.absolute.rate", "state", "strata"),
        "3.2": ("poverty.absolute.rate", "ethnicity", "strata"),
        "3.3": ("poverty.absolute.rate", "ethnicity", "hoh_sex"),
        "3.4": ("poverty.absolute.rate", "hoh_age", "plain"),
        "3.5": ("poverty.absolute.rate", "hh_size", "plain"),
        "4.0": ("poverty.relative.rate", "state", "strata"),
    },
    "household_income_2024": {
        "2.7": ("hh_income.gross.{m}", "state", "measure"),
        "2.8": ("hh_income.gross_per_capita.{m}", "state", "measure"),
        "2.9": ("hh_income.gross.median", "ethnicity", "strata_hoh_sex"),
        "2.10": ("hh_income.gross.mean", "ethnicity", "strata_hoh_sex"),
        "2.11": ("hh_income.gross.{m}", "state", "measure_hoh_sex"),
        "2.12": ("hh_income.gross.{m}", "hoh_age", "measure"),
        "3.5": ("hh_income.disposable.{m}", "state", "measure"),
        "3.6": ("hh_income.disposable_per_capita.{m}", "state", "measure"),
        "3.7": ("hh_income.disposable.median", "ethnicity", "strata_hoh_sex"),
        "3.8": ("hh_income.disposable.mean", "ethnicity", "strata_hoh_sex"),
        "3.9": ("hh_income.disposable.{m}", "state", "measure_hoh_sex"),
        "3.10": ("hh_income.disposable.{m}", "hoh_age", "measure"),
    },
    "labour_annual_2025": {
        "A1.1": ("lfs.participation_rate", "person_age", "strata_sex"),
    },
}
UNIT = {"poverty.hardcore.rate": "percent", "poverty.absolute.rate": "percent", "poverty.relative.rate": "percent",
        "lfs.participation_rate": "percent"}  # everything else: RM per month


def precision(printed):
    """'0.01' for a figure printed to two decimals, '1' for a whole number: the precision the report prints."""
    s = printed.replace(",", "")
    dp = len(s.split(".")[1]) if "." in s else 0
    return "1" if dp == 0 else "0." + "0" * (dp - 1) + "1"


def parse_row(kind, label):
    """-> ('geo', code) | ('total',) | (axis, member) | None"""
    if kind == "state":
        g = state(label)
        return ("geo", g) if g else None
    return {"ethnicity": ethnicity, "hoh_age": age_group, "hh_size": hh_size, "person_age": person_age}[kind](label)


def parse_col(kind, col, title):
    """-> (measure or None, {axis: member}) | None to leave the column at L1"""
    if "growth rate" in col or "households" in col:
        return None  # growth rates are derivable (D34); household counts are loaded from hh_profile_state
    parts = {}
    if kind in ("strata", "strata_hoh_sex", "strata_sex"):
        s = strata_of(col)
        if s:
            parts["strata"] = s
    if kind in ("hoh_sex", "strata_hoh_sex", "measure_hoh_sex"):
        s = sex_of(col)
        if s:
            parts["hoh_sex"] = s
    if kind == "strata_sex":
        s = sex_of(col)
        if s:
            parts["sex"] = s
    if kind == "component":
        parts["pli_component"] = "non_food" if "Non-food" in col else "food"
    m = mean_or_median(col) if kind.startswith("measure") else None
    if kind.startswith("measure") and m is None:
        return None
    return m, parts


def manifest():
    return {r["publication"]: r for r in csv.DictReader(open(os.path.join(SRC, "_documents_manifest.csv"),
                                                             encoding="utf-8"))}


def load(obs):
    """Add the declared report tables to obs (build_core.Obs), after the open data. Returns counts for the log."""
    man = manifest()
    held = {}
    for r in obs.rows:
        held.setdefault((r["indicator_code"], r["geo_code"], r["period_code"], r["breakdown_key"]), []).append(r)
    divergent = {(d["publication"], d["sheet"], d["cell"]) for d in
                 csv.DictReader(open(os.path.join(SRC, "_source_divergences.csv"), encoding="utf-8"))}
    counts = {"loaded": 0, "same_as_open_data": 0, "repeated_in_report": 0, "divergent_kept": 0, "left_at_l1": 0,
              "marker_at_l1": 0, "unparsed": 0}
    first = {}
    unparsed = []
    for pub, tables in TABLES.items():
        m = man[pub]
        edition = f"dosm:report.{pub}@{m['release_date']}"
        for i, c in enumerate(csv.DictReader(open(os.path.join(SRC, pub, "cells.csv"), encoding="utf-8")), start=2):
            spec = tables.get(c["table_no"])
            if not spec:
                continue
            ind_fmt, rkind, ckind = spec
            if not c["value"]:
                counts["marker_at_l1"] += 1  # 'n.a' / '-' as printed: no figure to load
                continue
            row = parse_row(rkind, c["row_label"])
            col = parse_col(ckind, c["col_header"], c["title_en"])
            if col is None:
                counts["left_at_l1"] += 1
                continue
            if row is None:
                counts["unparsed"] += 1
                unparsed.append(f"{pub} {c['sheet']}!{c['cell']} {c['row_label']!r}")
                continue
            measure, parts = col
            geo = row[1] if row[0] == "geo" else "MY"
            if row[0] not in ("geo", "total"):
                parts[row[0]] = row[1]
            ind = ind_fmt.format(m=measure)
            period = year_of(c["col_header"], c["title_en"])
            bk = "|".join(f"{a}={v}" for a, v in sorted(parts.items())) or "_total"
            v = Decimal(c["value_printed"].replace(",", ""))
            k4 = (ind, geo, period, bk)
            if (edition, k4) in first:
                pv, ref = first[(edition, k4)]
                if pv != v:
                    unparsed.append(f"{pub} {c['sheet']}!{c['cell']} prints {v}, {ref} prints {pv} for {k4}")
                counts["repeated_in_report"] += 1
                continue
            first[(edition, k4)] = (v, f"{c['sheet']}!{c['cell']}")
            same = [h for h in held.get(k4, []) if Decimal(h["value"]) in (v, Decimal(c["value"]))]
            key = (pub, c["sheet"], c["cell"])
            if same and key not in divergent:
                counts["same_as_open_data"] += 1
                continue
            if held.get((ind, geo, period, bk)) and key not in divergent:
                counts["unparsed"] += 1
                unparsed.append(f"{pub} {c['sheet']}!{c['cell']}: differs from open data and is not registered")
                continue
            if key in divergent:
                counts["divergent_kept"] += 1
            obs.add(indicator_code=ind, geo_code=geo, period_code=period, breakdown_key=bk, basis="statistic",
                    edition_id=edition, vintage=m["release_date"], value=v, value_printed=c["value_printed"],
                    unit_printed=UNIT.get(ind, "RM per month"), precision_printed=precision(c["value_printed"]),
                    estimate_method="direct_survey", reliability="unknown", file_id=m["sha256"],
                    table_ref=f"{pub} Jadual {c['table_no']} ({c['sheet']}!{c['cell']})",
                    l1_ref=f"sources/dosm_reports/data/{pub}/cells.csv#row{i}")
            counts["loaded"] += 1
    return counts, unparsed
