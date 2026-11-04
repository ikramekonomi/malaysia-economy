"""One rule for choosing which Tinjauan Fiskal edition supplies each year.

Every edition prints five years: three actuals, a revised estimate and a budget estimate.
So most actual years are printed by three editions, and the editions do not always agree
(sources/mof-fiscal-outlook/data/_restatements_editions.csv: 30 of 588 line-years move,
mostly by RM1 juta, a few by reclassification). Taking "whatever row comes first" would
blend editions silently. This module is the single place that decides, and every curated
table that reads MOF's tables goes through it.

THE RULE (golden rule 6 -- each year from its own volume)
  0. The choice is made per YEAR (per table): every line of a year comes from the same
     edition, because only one edition's column is guaranteed to add up.
  1. Strongest basis wins: official_actual > official_preliminary > official_revised >
     official_projection.
  2. Among editions printing the same basis -- in practice, the actuals -- take the
     earliest edition at or after Y+2. Edition Y+2 is the one in which year Y is the
     newest actual: its own volume. If the warehouse holds no edition Y+2 (FY2015-2016 are
     first printed as actuals by the 2019 edition), the earliest edition that prints Y as
     actual is used.
  3. Whatever a later edition prints differently is not lost: the chosen row says so in
     `restated_in`, value by edition, so a series break caused by reclassification
     (FY2020-21 general administration -> housing in the 2024 edition) is visible on the
     row rather than discovered by surprise.

Reads the source CSVs directly -- the raw data is the source of truth (golden rule 1).
"""
import csv
import glob
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
MOF_DATA = os.path.join(ROOT, "sources", "mof-fiscal-outlook", "data")

BASIS_RANK = {"official_actual": 0, "official_preliminary": 1, "official_revised": 2,
              "official_projection": 3}


def load_all(table):
    """Every row of <table>.csv across all *_public_finance_stats edition folders."""
    rows = []
    for folder in sorted(glob.glob(os.path.join(MOF_DATA, "*_public_finance_stats"))):
        path = os.path.join(folder, f"{table}.csv")
        if not os.path.exists(path):
            continue
        for r in csv.DictReader(open(path, newline="")):
            r["edition"] = int(r.get("edition") or os.path.basename(folder)[:4])
            r["target_year"] = int(r["target_year"])
            rows.append(r)
    return rows


def _value(r):
    v = r.get("amount_rm_juta")
    if v in ("", None):
        v = r.get("pct_of_gdp")
    return None if v in ("", None) else float(v)


def choose(rows):
    """{(line, year): chosen row}, each with `restated_in` describing later disagreement.

    The edition is chosen per YEAR, not per line: a year's table is one printed column,
    and only lines taken together from the same edition are guaranteed to add up. Choosing
    line by line would let a renamed line ("Pertanian dan pembangunan luar bandar" ->
    "Pertanian") arrive twice from two editions and be double-counted in its sector.
    """
    by_year = {}
    for r in rows:
        if _value(r) is None:
            continue
        by_year.setdefault(r["target_year"], []).append(r)
    out = {}
    for year, cands in by_year.items():
        # basis is a property of the printed column, so it is the same for every line of
        # one edition-year; rank editions by it, then by the own-edition rule
        eds = {}
        for c in cands:
            eds.setdefault(c["edition"], c["basis"])
        best_rank = min(BASIS_RANK[b] for b in eds.values())
        same = sorted(e for e, b in eds.items() if BASIS_RANK[b] == best_rank)
        own = [e for e in same if e >= year + 2]
        edition = own[0] if own else same[0]
        others = [e for e in same if e != edition]
        mine = [c for c in cands if c["edition"] == edition]
        if len({c["basis"] for c in mine}) != 1:
            raise SystemExit(f"FY{year} edition {edition}: mixed basis within one column")
        alt = {(c["line"], c["edition"]): _value(c) for c in cands if c["edition"] in others}
        for c in mine:
            pick = dict(c)
            pick["restated_in"] = "; ".join(
                f"edition {e} prints {alt[(c['line'], e)]:g}" for e in others
                if (c["line"], e) in alt and alt[(c["line"], e)] != _value(c))
            out[(c["line"], year)] = pick
    return out


def headline(line):
    """{year: chosen row} for one Jadual 1.1 line."""
    chosen = choose(load_all("fact_headline"))
    return {y: r for (l, y), r in chosen.items() if l == line}
