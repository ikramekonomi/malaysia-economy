#!/usr/bin/env python3
"""Derive curated/dashboard/external_denominators.csv from the DOSM source CSVs.

Inputs (canonical, in sources/dosm/data/ — see sources/dosm/README.md for provenance):
  gdp_gni_annual_nominal.csv   annual nominal GDP, RM million  (series='abs' rows)
  population_malaysia.csv      population '000                 (both/overall/overall rows)
  hh_lq.csv                    number of households (count)

Output (derived, rebuildable):
  curated/dashboard/external_denominators.csv
    year, gdp_rm_bil, population_mil, households_mil, source, note

Rules: no figure is altered — only unit conversions (RM mil -> RM bil, '000 -> mil,
count -> mil). Years emitted: 2009 onward, wherever GDP and population both exist;
households left blank for years DOSM has not published (never interpolated).
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(HERE, "..", "..", "..", "curated", "dashboard", "external_denominators.csv")

SOURCE = "DOSM via sources/dosm (data.gov.my/OpenDOSM)"
NOTE = ("EXTERNAL — DOSM national accounts & demography, not part of the audited PKKP "
        "warehouse; provenance in sources/dosm/README.md")


def year(datestr):
    return int(datestr[:4])


def read_gdp():
    out = {}
    with open(os.path.join(DATA, "gdp_gni_annual_nominal.csv")) as f:
        for row in csv.DictReader(f):
            if row["series"] == "abs" and row["gdp"] != "":
                out[year(row["date"])] = float(row["gdp"]) / 1000.0  # RM mil -> RM bil
    return out


def read_pop():
    out = {}
    with open(os.path.join(DATA, "population_malaysia.csv")) as f:
        for row in csv.DictReader(f):
            if row["sex"] == "both" and row["age"] == "overall" and row["ethnicity"] == "overall":
                out[year(row["date"])] = float(row["population"]) / 1000.0  # '000 -> mil
    return out


def read_hh():
    out = {}
    with open(os.path.join(DATA, "hh_lq.csv")) as f:
        for row in csv.DictReader(f):
            out[year(row["date"])] = float(row["households"]) / 1e6  # count -> mil
    return out


def main():
    gdp, pop, hh = read_gdp(), read_pop(), read_hh()
    years = sorted(y for y in gdp if y >= 2009 and y in pop)
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "gdp_rm_bil", "population_mil", "households_mil", "source", "note"])
        for y in years:
            w.writerow([y, f"{gdp[y]:.3f}", f"{pop[y]:.4f}",
                        f"{hh[y]:.4f}" if y in hh else "", SOURCE, NOTE])
    print(f"wrote {OUT}: {len(years)} years ({years[0]}-{years[-1]}), "
          f"households present for {sum(1 for y in years if y in hh)} of them")


if __name__ == "__main__":
    main()
