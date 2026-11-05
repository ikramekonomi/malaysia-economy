#!/usr/bin/env python3
"""Build the conformed core (L2), Phase 1 scope: state level, end to end (docs/DATA_MODEL.md §4-5, §15).

  python3 core/pipeline/build_core.py

Reads L1 (never edits it):
  sources/dosm/data/   population_state, population_district, population_malaysia, hh_income(_state),
                       hh_poverty, hh_inequality, lfs_year (national values),
                       hh_poverty_state, hh_inequality_state, hies_state, lfs_state_sex, cpi_state,
                       gdp_state_real_supply, hh_profile_state  (+ _vintage_log.csv for edition and sha256)
                       cpi_headline, trade_headline (national, monthly)
  sources/bnm/data/    msb_3_1 (federal finance), msb_1_3 (M1-M3), msb_1_18 (loans)  (+ _vintage_log.csv)
  sources/states/data/_national/fact_state_finance_all.csv  (13 states' audited accounts)
  meta/registry_file.csv (sha256 of each state volume), meta/indicator.csv (indicator definitions)
Writes (derived, rebuilt every run, committed so a reviewer can diff them):
  core/dim_geo.csv  core/dim_period.csv  core/dim_indicator.csv  core/dim_breakdown.csv
  core/fact_observation.csv  core/_validation_core.csv

Rules kept here: values in the indicator's base unit (persons, not thousands; RM, not RM juta),
exact decimals; the printed value and unit kept beside it; no uncertainty is invented (DOSM's
state files publish none, so reliability = unknown); names are attributes, geo codes are keys.
"""
import csv
import os
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CORE = os.path.join(REPO, "core")
DOSM = os.path.join(REPO, "sources", "dosm", "data")
STATES = os.path.join(REPO, "sources", "states", "data", "_national", "fact_state_finance_all.csv")
META = os.path.join(REPO, "meta")

STATE_ISO = {  # ISO 3166-2:MY (decision D2)
    "Johor": "MY-01", "Kedah": "MY-02", "Kelantan": "MY-03", "Melaka": "MY-04", "Negeri Sembilan": "MY-05",
    "Pahang": "MY-06", "Pulau Pinang": "MY-07", "Perak": "MY-08", "Perlis": "MY-09", "Selangor": "MY-10",
    "Terengganu": "MY-11", "Sabah": "MY-12", "Sarawak": "MY-13", "W.P. Kuala Lumpur": "MY-14",
    "W.P. Labuan": "MY-15", "W.P. Putrajaya": "MY-16",
}
STATE_EN = {"Pulau Pinang": "Penang", "Melaka": "Malacca", "W.P. Kuala Lumpur": "Federal Territory of Kuala Lumpur",
            "W.P. Labuan": "Federal Territory of Labuan", "W.P. Putrajaya": "Federal Territory of Putrajaya"}
GEO_ALIAS = {"Malaysia": "MY", "Supra": "_unallocated"}
FILE_OF = {"deaths_state": "death_state"}  # catalogue id -> file name, where they differ
DISTRICT_VINTAGE = "dosm_2020"
OBS_FIELDS = ["indicator_code", "geo_code", "period_code", "breakdown_key", "entity_id", "basis", "edition_id",
              "vintage", "value", "value_printed", "unit_printed", "precision_printed", "status", "se", "ci_low",
              "ci_high", "ci_level", "cv", "sample_n", "estimate_method", "reliability", "file_id", "pdf_page",
              "printed_page", "table_ref", "l1_ref"]


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


_BRIDGE = None


def entity(system, code, year, scope=""):
    """The entity_id of a readable code in a year (core/bridge_entity_code.csv, built by build_entities.py); a
    row scoped to the source (e.g. anggaran:2024) wins for that source. Stops when the code resolves to no
    entity or to two: the spine is the only place identity is decided."""
    global _BRIDGE
    if _BRIDGE is None:
        _BRIDGE = rows(os.path.join(REPO, "core", "bridge_entity_code.csv"))
    y = int(str(year)[:4])

    def hits(sc):
        return sorted({c["entity_id"] for c in _BRIDGE if c["code_system"] == system and c["code"] == code
                       and c.get("scope", "") == sc and (not c["valid_from"] or int(c["valid_from"]) <= y)
                       and (not c["valid_to"] or y <= int(c["valid_to"]))})
    hit = (hits(scope) if scope else []) or hits("")
    if len(hit) != 1:
        sys.exit(f"build_core: {system}:{code} in {year} resolves to {hit or 'no entity'} "
                 "(run core/pipeline/build_entities.py; a new code needs a person, rule D26)")
    return hit[0]


def dec(s):
    s = (s or "").strip().replace(",", "")
    if s in ("", "-", "–", "NA", "nan"):
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def fmt(d):
    if d is None:
        return ""
    s = format(d.normalize(), "f")
    return s if "." not in s else s.rstrip("0").rstrip(".")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def geo_of(name):
    return STATE_ISO.get(name) or GEO_ALIAS.get(name)


# ---------------------------------------------------------------- provenance of DOSM files
def dosm_editions():
    """dataset -> (edition_id, vintage, sha256) of the current vintage, from the append-only log."""
    import json
    from email.utils import parsedate_to_datetime
    vin = json.load(open(os.path.join(DOSM, "_vintage.json")))
    out = {}
    for r in rows(os.path.join(DOSM, "_vintage_log.csv")):
        if r["state"] == "current":
            d = (r["last_updated"] or r["data_as_of"] or "")[:10]
            lm = (vin.get(r["dataset"]) or {}).get("storage_last_modified")
            if lm:  # the API's last_updated can lag the file itself (population_state: 2023 vs 2026)
                d = max(d, parsedate_to_datetime(lm).date().isoformat())
            out[r["dataset"]] = (f"dosm:{r['dataset']}@{d}", d, r["sha256"])
    return out


# ---------------------------------------------------------------- the observation builders
class Obs:
    def __init__(self):
        self.rows = []
        self.periods = set()
        self.breakdowns = {"_total": {}}
        self.geos_used = set()
        self.skipped = Counter()

    def add(self, **k):
        r = {f: "" for f in OBS_FIELDS}
        r.update({"breakdown_key": "_total", "entity_id": "_none", "status": "final", "reliability": "unknown"})
        r.update({f: ("" if v is None else v) for f, v in k.items()})
        if isinstance(r["value"], Decimal):
            r["value"] = fmt(r["value"])
        self.rows.append(r)
        self.periods.add(r["period_code"])
        self.geos_used.add(r["geo_code"])


def period_of(date, freq):
    y, m = date[:4], date[5:7]
    if freq == "A":
        return y
    if freq == "Q":
        return f"{y}-Q{(int(m) - 1) // 3 + 1}"
    return f"{y}-{m}"


def dosm_simple(obs, ed, dataset, cols, freq, method, filt=None, geo_col="state", breakdown=None):
    """cols: {source_column: (indicator_code, scale, unit_printed, precision)}"""
    e, vint, sha = ed[dataset]
    fname = FILE_OF.get(dataset, dataset)
    for i, r in enumerate(rows(os.path.join(DOSM, f"{fname}.csv")), start=2):
        if filt and not filt(r):
            continue
        g = "MY" if geo_col is None else geo_of(r[geo_col])
        if not g:
            obs.skipped[f"{dataset}: unknown geo {r[geo_col]}"] += 1
            continue
        bk = breakdown(r) if breakdown else "_total"
        for col, (ind, scale, unit, prec) in cols.items():
            v = dec(r.get(col))
            if v is None:
                continue
            obs.add(indicator_code=ind, geo_code=g, period_code=period_of(r["date"], freq), breakdown_key=bk,
                    basis="statistic", edition_id=e, vintage=vint, value=v * scale, value_printed=r[col],
                    unit_printed=unit, precision_printed=prec, estimate_method=method, file_id=sha,
                    table_ref=dataset, l1_ref=f"sources/dosm/data/{fname}.csv#row{i}")


def build_dosm(obs, ed):
    k = Decimal(1000)
    overall = lambda r: r["age"] == "overall" and r["ethnicity"] == "overall"  # noqa: E731
    sex_bk = lambda r: "_total" if r["sex"] == "both" else f"sex={r['sex']}"  # noqa: E731
    # national population (no state column)
    e, vint, sha = ed["population_malaysia"]
    for i, r in enumerate(rows(os.path.join(DOSM, "population_malaysia.csv")), start=2):
        if overall(r) and dec(r["population"]) is not None:
            obs.add(indicator_code="pop.total", geo_code="MY", period_code=r["date"][:4], breakdown_key=sex_bk(r),
                    basis="statistic", edition_id=e, vintage=vint, value=dec(r["population"]) * k,
                    value_printed=r["population"], unit_printed="'000 persons", precision_printed="100",
                    estimate_method="modelled", file_id=sha, table_ref="population_malaysia",
                    l1_ref=f"sources/dosm/data/population_malaysia.csv#row{i}")
    dosm_simple(obs, ed, "population_state", {"population": ("pop.total", k, "'000 persons", "100")}, "A",
                "modelled", filt=overall, breakdown=sex_bk)
    # districts: DOSM's file names them but carries no code, so the code is minted once from the name,
    # inside its state and boundary set (dim_geo records the proof)
    e, vint, sha = ed["population_district"]
    for i, r in enumerate(rows(os.path.join(DOSM, "population_district.csv")), start=2):
        if overall(r) and r["sex"] == "both" and dec(r["population"]) is not None:
            g = f"{STATE_ISO[r['state']]}/dis:{slug(r['district'])}@{DISTRICT_VINTAGE}"
            obs.add(indicator_code="pop.total", geo_code=g, period_code=r["date"][:4], basis="statistic",
                    edition_id=e, vintage=vint, value=dec(r["population"]) * k, value_printed=r["population"],
                    unit_printed="'000 persons", precision_printed="100", estimate_method="modelled", file_id=sha,
                    table_ref="population_district", l1_ref=f"sources/dosm/data/population_district.csv#row{i}")
            obs.districts[g] = (r["state"], r["district"])
    one = Decimal(1)
    # national values, so every state comparison can show Malaysia beside the states
    dosm_simple(obs, ed, "hh_income", {"income_mean": ("hh_income.gross.mean", one, "RM per month", "1"),
                                       "income_median": ("hh_income.gross.median", one, "RM per month", "1")},
                "A", "direct_survey", geo_col=None)
    dosm_simple(obs, ed, "hh_poverty", {"poverty_absolute": ("poverty.absolute.rate", one, "percent", "0.1"),
                                        "poverty_hardcore": ("poverty.hardcore.rate", one, "percent", "0.1"),
                                        "poverty_relative": ("poverty.relative.rate", one, "percent", "0.1")},
                "A", "direct_survey", geo_col=None)
    dosm_simple(obs, ed, "hh_inequality", {"gini": ("hh_income.gini", one, "ratio", "0.001")}, "A", "direct_survey",
                geo_col=None)
    dosm_simple(obs, ed, "lfs_year", {"lf": ("lfs.labour_force", k, "'000 persons", "100"),
                                      "lf_employed": ("lfs.employed", k, "'000 persons", "100"),
                                      "lf_unemployed": ("lfs.unemployed", k, "'000 persons", "100"),
                                      "p_rate": ("lfs.participation_rate", one, "percent", "0.1"),
                                      "u_rate": ("lfs.unemployment_rate", one, "percent", "0.1")},
                "A", "direct_survey", geo_col=None)
    dosm_simple(obs, ed, "hh_income_state", {"income_mean": ("hh_income.gross.mean", one, "RM per month", "1"),
                                             "income_median": ("hh_income.gross.median", one, "RM per month", "1")},
                "A", "direct_survey")
    dosm_simple(obs, ed, "hh_poverty_state", {"poverty_absolute": ("poverty.absolute.rate", one, "percent", "0.1"),
                                              "poverty_hardcore": ("poverty.hardcore.rate", one, "percent", "0.1"),
                                              "poverty_relative": ("poverty.relative.rate", one, "percent", "0.1")},
                "A", "direct_survey")
    dosm_simple(obs, ed, "hh_inequality_state", {"gini": ("hh_income.gini", one, "ratio", "0.001")}, "A",
                "direct_survey")
    dosm_simple(obs, ed, "hies_state", {"expenditure_mean": ("hh_expenditure.mean", one, "RM per month", "1")},
                "A", "direct_survey")
    dosm_simple(obs, ed, "hh_profile_state", {"households": ("households.total", k, "'000 households", "100")},
                "A", "modelled")
    dosm_simple(obs, ed, "lfs_state_sex", {"lf": ("lfs.labour_force", k, "'000 persons", "100"),
                                           "lf_employed": ("lfs.employed", k, "'000 persons", "100"),
                                           "lf_unemployed": ("lfs.unemployed", k, "'000 persons", "100"),
                                           "p_rate": ("lfs.participation_rate", one, "percent", "0.1"),
                                           "u_rate": ("lfs.unemployment_rate", one, "percent", "0.1")},
                "A", "direct_survey", breakdown=sex_bk)
    dosm_simple(obs, ed, "cpi_state", {"index": ("cpi.index", one, "index 2010=100", "0.1")}, "M", "direct_survey",
                breakdown=lambda r: "_total" if r["division"] == "overall" else f"coicop={r['division']}")
    dosm_simple(obs, ed, "gdp_state_real_supply", {"value": ("gdp.real", Decimal(1000000), "RM million, 2015 prices",
                                                             "1000")},
                "A", "modelled", filt=lambda r: r["series"] == "abs" and r["sector"] == "p0")


def build_services(obs, ed):
    """Phase 2: health, education and services by state (state and national rows; district rows use each
    ministry's own districts, not DOSM's, so they wait for their own boundary sets)."""
    one, alld = Decimal(1), ("All", "All Districts")
    agg = lambda r: r.get("district", "All") in alld  # noqa: E731
    dosm_simple(obs, ed, "hospital_beds", {"beds": ("health.beds", one, "beds", "1")}, "A", "administrative",
                filt=agg, breakdown=lambda r: "_total" if r["type"] == "all" else f"facility_type={r['type']}")
    dosm_simple(obs, ed, "healthcare_staff", {"staff": ("health.staff", one, "persons", "1")}, "A", "administrative",
                breakdown=lambda r: "_total" if r["type"] == "all" else f"staff_type={r['type']}")
    dosm_simple(obs, ed, "schools_district", {"schools": ("edu.schools", one, "institutions", "1")}, "A",
                "administrative", filt=agg,
                breakdown=lambda r: f"stage={r['stage']}|institution_type={slug(r['type'])}")
    for ds, col, ind in (("enrolment_school_district", "students", "edu.enrolment"),
                         ("teachers_district", "teachers", "edu.teachers")):
        dosm_simple(obs, ed, ds, {col: (ind, one, "persons", "1")}, "A", "administrative", filt=agg,
                    breakdown=lambda r: f"stage={r['stage']}" + ("" if r["sex"] == "both" else f"|sex={r['sex']}"))
    dosm_simple(obs, ed, "deaths_state", {"abs": ("deaths.total", one, "persons", "1"),
                                          "rate": ("deaths.crude_rate", one, "per 1,000 population", "0.1")},
                "A", "administrative")
    dosm_simple(obs, ed, "life_expectancy_state", {"life_expectancy": ("life_expectancy", one, "years", "0.1")},
                "A", "modelled", breakdown=lambda r: "_total" if r["sex"] == "both" else f"sex={r['sex']}")
    dosm_simple(obs, ed, "water_access", {"proportion": ("water.access.share", one, "percent", "0.1")}, "A",
                "administrative", breakdown=lambda r: "_total" if r["strata"] == "overall" else f"strata={r['strata']}")
    dosm_simple(obs, ed, "crime_district", {"crimes": ("crime.count", one, "crimes", "1")}, "A", "administrative",
                filt=agg, breakdown=lambda r: f"crime_category={r['category']}"
                + ("" if r["type"] == "all" else f"|crime_type={r['type']}"))


ELECTORAL_VINTAGE = "ge15"


def build_small_areas(obs, ed):
    """Phase 2: district, parlimen and DUN rows from DOSM's HIES and LFS small-area files.

    Districts join the 166 DOSM administrative districts through meta/geo_alias.csv (spellings that
    replace each other between years). Constituencies are coded MY-xx/par:P.001@ge15 and
    MY-xx/dun:N.01@ge15. Every estimate is a survey estimate without published sampling error
    (reliability unknown); LFS constituency rows are survey records aggregated below the survey's
    design domain (district), so reliability = low. compare_geos never ranks any of them."""
    alias = {(r["state"], r["published_name"]): r["canonical_name"]
             for r in rows(os.path.join(META, "geo_alias.csv"))}
    one, k = Decimal(1), Decimal(1000)

    def dis(r):
        if r["district"] in ("All Districts", "All"):
            return STATE_ISO[r["state"]]
        name = alias.get((r["state"], r["district"]), r["district"])
        g = f"{STATE_ISO[r['state']]}/dis:{slug(name)}@{DISTRICT_VINTAGE}"
        obs.districts.setdefault(g, (r["state"], name))
        return g

    def par(r):
        code, _, name = r["parlimen"].partition(" ")
        g = f"{STATE_ISO[r['state']]}/par:{code}@{ELECTORAL_VINTAGE}"
        obs.parlimen.setdefault(g, (r["state"], code, name))
        return g

    def dun(r):
        code, _, name = r["dun"].partition(" ")
        g = f"{STATE_ISO[r['state']]}/dun:{code}@{ELECTORAL_VINTAGE}"
        obs.dun.setdefault(g, (r["state"], code, name, par(r)))
        return g

    def load(dataset, cols, geo, reliability="unknown"):
        e, vint, sha = ed[dataset]
        for i, r in enumerate(rows(os.path.join(DOSM, f"{dataset}.csv")), start=2):
            g = geo(r)
            for col, (ind, scale, unit, prec) in cols.items():
                v = dec(r.get(col))
                if v is None:
                    continue
                obs.add(indicator_code=ind, geo_code=g, period_code=r["date"][:4], basis="statistic",
                        edition_id=e, vintage=vint, value=v * scale, value_printed=r[col], unit_printed=unit,
                        precision_printed=prec, estimate_method="direct_survey", reliability=reliability,
                        file_id=sha, table_ref=dataset, l1_ref=f"sources/dosm/data/{dataset}.csv#row{i}")

    inc = {"income_mean": ("hh_income.gross.mean", one, "RM per month", "1"),
           "income_median": ("hh_income.gross.median", one, "RM per month", "1")}
    lfs = {"lf": ("lfs.labour_force", k, "'000 persons", "100"), "lf_employed": ("lfs.employed", k, "'000 persons", "100"),
           "lf_unemployed": ("lfs.unemployed", k, "'000 persons", "100"),
           "p_rate": ("lfs.participation_rate", one, "percent", "0.1"),
           "u_rate": ("lfs.unemployment_rate", one, "percent", "0.1")}
    gini = {"gini": ("hh_income.gini", one, "ratio", "0.001")}
    for level, geo in (("district", dis), ("parlimen", par), ("dun", dun)):
        load(f"hh_income_{level}", inc, geo)
        load(f"hh_inequality_{level}", gini, geo)
        pov = {"poverty_absolute": ("poverty.absolute.rate", one, "percent", "0.1")}
        if level == "district":
            pov["poverty_relative"] = ("poverty.relative.rate", one, "percent", "0.1")
        load(f"hh_poverty_{level}", pov, geo)
        load(f"lfs_{level}", lfs, geo, reliability="unknown" if level == "district" else "low")
    load("hies_district", {"expenditure_mean": ("hh_expenditure.mean", one, "RM per month", "1")}, dis)
    for level, geo in (("parlimen", par), ("dun", dun)):
        load(f"hh_expenditure_{level}", {"expenditure": ("hh_expenditure.mean", one, "RM per month", "1")}, geo)
    load("hh_access_amenities", {"piped_water": ("amenities.piped_water.share", one, "percent", "0.01"),
                                 "sanitation": ("amenities.sanitation.share", one, "percent", "0.01"),
                                 "electricity": ("amenities.electricity.share", one, "percent", "0.01")}, dis)


NA_INCOME = {"i0": "gdp.nominal", "i1": "na.compensation_of_employees", "i2": "na.gross_operating_surplus",
             "i3": "na.taxes_less_subsidies_production", "i3.1": "na.taxes_on_production",
             "i3.2": "na.subsidies_on_production"}


def build_national_accounts(obs, ed):
    """Phase 2: national accounts, annual, current prices (DOSM gdp_annual_nominal_income, 2010-).

    GDP and its income components, coded by DOSM's own lookup (gdp_lookup.csv: i0..i3.2). GDP here comes
    from the approach tables only: DOSM's long-run gdp_gni_annual_nominal file is a different revision
    vintage for 2022-2025 (RM0.9-2.3 bn lower) and is not mixed in (sources/dosm/README.md)."""
    m = Decimal(1000000)
    e, vint, sha = ed["gdp_annual_nominal_income"]
    for i, r in enumerate(rows(os.path.join(DOSM, "gdp_annual_nominal_income.csv")), start=2):
        v = dec(r["value"])
        if r["series"] != "abs" or v is None or r["component"] not in NA_INCOME:
            continue
        obs.add(indicator_code=NA_INCOME[r["component"]], geo_code="MY", period_code=r["date"][:4],
                basis="statistic", edition_id=e, vintage=vint, value=v * m, value_printed=r["value"],
                unit_printed="RM million", precision_printed="0.001", estimate_method="modelled", file_id=sha,
                table_ref="gdp_annual_nominal_income", l1_ref=f"sources/dosm/data/gdp_annual_nominal_income.csv#row{i}")


BNM = os.path.join(REPO, "sources", "bnm", "data")
TRADE = {"exports": "trade.exports", "imports": "trade.imports", "balance": "trade.balance"}
MONEY = {"m_one_tot": "money.m1", "m_two_tot": "money.m2", "m_thr_tot": "money.m3"}
BANK_TYPE = {"Jumlah/Total": "_total", "Bank-bank Perdagangan / Commercial Banks": "bank_type=commercial",
             "Bank-bank Islam / Islamic Banks": "bank_type=islamic",
             "Bank-bank Pelaburan / Investment Banks": "bank_type=investment"}


def bnm_editions():
    """dataset -> the current row of sources/bnm/data/_vintage_log.csv (data_as_of, sha256)."""
    return {r["dataset"]: r for r in rows(os.path.join(BNM, "_vintage_log.csv")) if r["state"] == "current"}


def build_national_series(obs, ed):
    """Phase 2: national monthly series, as published.

      cpi_headline (DOSM)  CPI for Malaysia, headline and 13 COICOP divisions, 2010=100: the same indicator
                           (cpi.index) and breakdown codes as cpi_state, which is the same DOSM product by state
                           (storage.dosm.gov.my cpi_2d.csv vs cpi_2d_state.csv)
      trade_headline (DOSM) exports, imports and the trade balance of goods, RM, series 'abs' only (DOSM's
                           growth_mom / growth_yoy rows are its own derived transforms and are not loaded)
      BNM MSB 1.3          M1, M2, M3 (RM million)
      BNM MSB 1.18         loans/financing by type: the total of the banking system (the 'Jumlah/Total' row,
                           equal to commercial + Islamic + investment banks, which are kept as a breakdown)
    Blank cells stay blank (no row). Signs are as published (a trade deficit is negative)."""
    one = Decimal(1)
    dosm_simple(obs, ed, "cpi_headline", {"index": ("cpi.index", one, "index 2010=100", "0.1")}, "M", "direct_survey",
                geo_col=None, breakdown=lambda r: "_total" if r["division"] == "overall" else f"coicop={r['division']}")
    dosm_simple(obs, ed, "trade_headline", {c: (ind, one, "RM", "1") for c, ind in TRADE.items()}, "M",
                "administrative", filt=lambda r: r["series"] == "abs", geo_col=None)
    m, vin = Decimal(1000000), bnm_editions()

    def load(dataset, cols, table, breakdown=lambda r: "_total"):
        v = vin[dataset]
        d = v["data_as_of"][:10]
        for i, r in enumerate(rows(os.path.join(BNM, f"{dataset}.csv")), start=2):
            if not r["month_dt"].strip():
                obs.skipped[f"{dataset}: annual row (not loaded; monthly only)"] += 1
                continue
            bk = breakdown(r)
            for col, ind in cols.items():
                val = dec(r[col])
                if val is None:
                    continue
                obs.add(indicator_code=ind, geo_code="MY", period_code=f"{r['year_dt']}-{int(r['month_dt']):02d}",
                        breakdown_key=bk, basis="statistic", edition_id=f"bnm:{dataset}@{d}", vintage=d,
                        value=val * m, value_printed=r[col], unit_printed="RM million",
                        precision_printed="0.000000000001", estimate_method="administrative", file_id=v["sha256"],
                        table_ref=table, l1_ref=f"sources/bnm/data/{dataset}.csv#row{i}")

    def bank_type(r):
        if r["type"] not in BANK_TYPE:
            sys.exit(f"msb_1_18: unknown institution type {r['type']!r}")
        return BANK_TYPE[r["type"]]

    load("msb_1_3", MONEY, "BNM MSB 1.3 Monetary Aggregates M1, M2 and M3")
    load("msb_1_18", {"tot_fin": "credit.loans.banking_system"}, "BNM MSB 1.18 Loans/Financing by Type",
         breakdown=bank_type)


PKKP = os.path.join(REPO, "sources", "pkkp", "data")
ANGGARAN = os.path.join(REPO, "sources", "anggaran", "data")
OPEX_BASIS = {"sebenar_rm": "audited", "anggaran_asal_rm": "budget_estimate", "anggaran_dipinda_rm": "revised_estimate"}


def _vote(code, year, heads, scope=""):
    """(entity_id, breakdown_key) of a printed vote code: its body (rule D26), or the federal government with
    the head as breakdown for Tanggungan (T.xx) and the contingency reserve (P.70)."""
    if code in heads:
        kind = "charged_head" if heads[code]["kind"] == "charged" else "reserve_head"
        return entity("federal_gov", "MY", year), f"{kind}={code}"
    system = {"B": "maksud_bekalan", "P": "maksud_pembangunan"}[code[0]]
    return entity(system, code, year, scope), "_total"


def build_votes(obs):
    """Phase 3: federal spending BY WHO SPENDS IT - each vote's printed total as an entity observation.

      PKKP fact_opex_maksud     every B/T vote's operating total, FY2009-2024: audited (sebenar), and the
                                original and revised estimates printed in the same volume
      PKKP fact_devex_maksud    every P vote's development JUMLAH line, FY2009-2024, audited. Where a vote is
                                printed in blocks (P.63 FY2019-2020: Pendidikan + Pendidikan Tinggi), the vote
                                total is the row equal to the sum of the others (checked; the blocks are not
                                loaded). The grand-total row is not a vote.
      Anggaran Perbelanjaan     each book's vote totals (B/T: mengurus; P: pembangunan): the book year's estimate
                                and the previous year's original estimate (basis budget_estimate), and MOF's
                                actuals for the two years before (basis actual, restated to the book's votes)
    Each year from its own PKKP volume (golden rule 6). Codes resolve through the entity spine at the year of
    the source: the PKKP year, or the book's year (a book prints past years under its own votes)."""
    heads = {r["code"]: r for r in rows(os.path.join(META, "spending_head.csv"))}
    sha = {r["file_name"]: r["sha256"] for r in rows(os.path.join(META, "registry_file.csv"))}
    import glob
    for path in sorted(glob.glob(os.path.join(PKKP, "*", "fact_opex_maksud.csv"))):
        rel = os.path.relpath(path, REPO)
        for i, r in enumerate(rows(path), start=2):
            ent_id, bk = _vote(r["maksud_code"], r["year"], heads)
            for col, basis in OPEX_BASIS.items():
                v = dec(r[col])
                if v is None:
                    continue
                obs.add(indicator_code="federal_gov.vote.opex", geo_code="MY", period_code=r["year"],
                        breakdown_key=bk, entity_id=ent_id, basis=basis, edition_id=f"pkkp:{r['source_file']}",
                        vintage=r["year"], value=v, value_printed=r[col], unit_printed="RM", precision_printed="0.01",
                        estimate_method="accounting", reliability="ok", file_id=sha.get(r["source_file"], ""),
                        pdf_page=r["pdf_page"], printed_page=r["printed_page"], table_ref=r["statement"],
                        l1_ref=f"{rel}#row{i}")
    for path in sorted(glob.glob(os.path.join(PKKP, "*", "fact_devex_maksud.csv"))):
        rel = os.path.relpath(path, REPO)
        by = defaultdict(list)
        for i, r in enumerate(rows(path), start=2):
            if r["maksud_code"].startswith("P."):
                by[(r["maksud_code"], r["year"])].append((i, r))
        for (code, year), lst in by.items():
            if len(lst) > 1:
                vals = [(dec(r["sebenar_jumlah_rm"]) or Decimal(0), i, r) for i, r in lst]
                top = max(vals, key=lambda x: x[0])
                if top[0] != sum(x[0] for x in vals if x is not top):
                    sys.exit(f"build_core: {code} FY{year} printed in {len(lst)} blocks and no row is their total")
                obs.skipped[f"PKKP devex: block rows of a vote printed in blocks ({code} FY{year})"] += len(lst) - 1
                lst = [(top[1], top[2])]
            i, r = lst[0]
            v = dec(r["sebenar_jumlah_rm"])
            if v is None:
                continue
            ent_id, bk = _vote(code, year, heads)
            obs.add(indicator_code="federal_gov.vote.devex", geo_code="MY", period_code=year, breakdown_key=bk,
                    entity_id=ent_id, basis="audited", edition_id=f"pkkp:{r['source_file']}", vintage=year,
                    value=v, value_printed=r["sebenar_jumlah_rm"], unit_printed="RM", precision_printed="0.01",
                    estimate_method="accounting", reliability="ok", file_id=sha.get(r["source_file"], ""),
                    pdf_page=r["pdf_page"], printed_page=r["printed_page"],
                    table_ref=f"{r['statement']} ({r['jumlah_label_bm']})", l1_ref=f"{rel}#row{i}")
            # the same line's allocation column (Lampiran 2 'Anggaran'): the accounts' own year allocation, which
            # is not the Budget book's original estimate (FY2024 RM85.2b against RM92.0b), so its own basis
            a = dec(r["anggaran_jumlah_rm"])
            if a is not None:
                obs.add(indicator_code="federal_gov.vote.devex", geo_code="MY", period_code=year, breakdown_key=bk,
                        entity_id=ent_id, basis="allocation", edition_id=f"pkkp:{r['source_file']}", vintage=year,
                        value=a, value_printed=r["anggaran_jumlah_rm"], unit_printed="RM", precision_printed="0.01",
                        estimate_method="accounting", reliability="ok", file_id=sha.get(r["source_file"], ""),
                        pdf_page=r["pdf_page"], printed_page=r["printed_page"],
                        table_ref=f"{r['statement']} ({r['jumlah_label_bm']}, Anggaran)", l1_ref=f"{rel}#row{i}")
    for path in sorted(glob.glob(os.path.join(ANGGARAN, "*", "fact_anggaran_maksud_*.csv"))):
        rel = os.path.relpath(path, REPO)
        book = int(os.path.basename(path)[-8:-4])
        rs = list(enumerate(rows(path), start=2))
        totals = {(r["maksud_code"], r["measure"], r["component"]) for _, r in rs if r["row_type"] == "total"}
        for i, r in rs:
            code, comp = r["maksud_code"], r["component"]
            want = "mengurus" if code[0] in "BT" else "pembangunan"
            # the 2024 and 2025 books print a Tanggungan head with no mengurus line: its operating total is the
            # head's JUMLAH (= emolumen + lain); the verifier found 112 rows missed without this
            if code[0] in "BT" and comp == "jumlah" and (code, r["measure"], "mengurus") not in totals:
                comp = want
            if comp != want or not (r["row_type"] == "total" or (code, r["measure"], want) not in totals):
                continue
            m = re.fullmatch(r"(anggaran|anggaran_asal|sebenar)_(\d{4})", r["measure"])
            basis = "actual" if m.group(1) == "sebenar" else "budget_estimate"
            v = dec(r["amount_rm"])
            if v is None:
                continue
            ent_id, bk = _vote(code, book, heads, scope=f"anggaran:{book}")
            obs.add(indicator_code="federal_gov.vote.opex" if want == "mengurus" else "federal_gov.vote.devex",
                    geo_code="MY", period_code=m.group(2), breakdown_key=bk, entity_id=ent_id, basis=basis,
                    edition_id=f"anggaran:{r['source_file']}", vintage=str(book), value=v,
                    value_printed=r["amount_rm"], unit_printed="RM", precision_printed="1",
                    estimate_method="accounting", reliability="ok", file_id=sha.get(r["source_file"], ""),
                    pdf_page=r["pdf_page"], printed_page=r["printed_page"],
                    table_ref=f"Anggaran Perbelanjaan Persekutuan {book}, {r['measure']}", l1_ref=f"{rel}#row{i}")


PCTILE_STATS = {"mean": "mean", "median": "median", "minimum": "min", "maximum": "max"}


def build_distribution(obs, ed):
    """Phase 2: HIES household income by percentile group (1 to 100), Malaysia and states, as published.

    Each row of DOSM's file is one percentile group p (the p-th hundredth of households ranked by
    income) and one statistic of the incomes inside it: mean, median, minimum or maximum. The maximum of
    group p is the p-th percentile cut-off. DOSM warns that these carry larger relative standard errors
    than the headline figures and publishes none, so every row is reliability = low (caveat CV13)."""
    for dataset, geo_col in (("hies_malaysia_percentile", None), ("hies_state_percentile", "state")):
        e, vint, sha = ed[dataset]
        for i, r in enumerate(rows(os.path.join(DOSM, f"{dataset}.csv")), start=2):
            v = dec(r["income"])
            if v is None:
                continue
            g = "MY" if geo_col is None else geo_of(r[geo_col])
            obs.add(indicator_code=f"hh_income.gross.pctile_group.{PCTILE_STATS[r['variable']]}", geo_code=g,
                    period_code=r["date"][:4], breakdown_key=f"percentile={int(r['percentile']):03d}",
                    basis="statistic", edition_id=e, vintage=vint, value=v, value_printed=r["income"],
                    unit_printed="RM per month", precision_printed="1", estimate_method="direct_survey",
                    reliability="low", file_id=sha, table_ref=dataset, l1_ref=f"sources/dosm/data/{dataset}.csv#row{i}")


# state accounts: the headline lines only (Phase 1); the line codes are the states pipeline's conformed codes
STATE_LINES = {
    "revenue_total": "state_gov.revenue.total",
    "revenue_tax": "state_gov.revenue.tax",
    "revenue_nontax": "state_gov.revenue.nontax",
    "revenue_nonrevenue_receipts": "state_gov.revenue.nonrevenue_receipts",
    "opex_before_transfer": "state_gov.expenditure.opex",
    "devex_total": "state_gov.expenditure.devex",
    "expenditure_water_supply": "state_gov.expenditure.water_supply",
    "expenditure_total": "state_gov.expenditure.total",
    "surplus_deficit": "state_gov.surplus_deficit",
    "debt_total": "state_gov.debt.total",
    # the federal grants as the state records them (Phase 3, gap_federal_vs_state): printed only in the
    # top-contributor and category tables, so a year without a value is not printed, not zero (CV26)
    "revenue_item_federal_capitation_grant": "state_gov.revenue.federal_capitation_grant",
    "revenue_item_federal_dept_grant": "state_gov.revenue.federal_concurrent_list_grant",
    "revenue_item_federal_grants_total": "state_gov.revenue.federal_grants_total",
}


def sign_rules():
    """(state, year, line_code) -> sign, from meta/sign_convention.csv: a printed figure whose sign the page
    leaves implicit (e.g. a deficit printed unsigned), each with its page proof. value_printed keeps the page."""
    return {(r["state"], r["fiscal_year"], r["line_code"]): r["value_sign"]
            for r in rows(os.path.join(META, "sign_convention.csv"))}


def build_states(obs):
    sha = {r["file_name"]: r["sha256"] for r in rows(os.path.join(META, "registry_file.csv"))}
    signs = sign_rules()
    for i, r in enumerate(rows(STATES), start=2):
        if r["measure"] != "actual" or r["line_code"] not in STATE_LINES:
            continue
        # spending lines are levels (the panel stores them positive even where the statement prints them in
        # parentheses as a deduction); a surplus or deficit keeps the sign printed on the page
        v = dec(r["amount_rm"] if r["line_code"] == "surplus_deficit" else r["amount_rm_conformed"])
        if v is None:
            continue
        if signs.get((r["state"], r["fiscal_year"], r["line_code"])) == "negative":
            v = -abs(v)
        g = STATE_ISO[r["state"]]
        obs.add(indicator_code=STATE_LINES[r["line_code"]], geo_code=g, period_code=r["fiscal_year"],
                entity_id=entity("state_gov", g, r["fiscal_year"]), basis="audited", edition_id=f"states:{r['report']}",
                vintage=r["fiscal_year"], value=v, value_printed=r["amount_printed"], unit_printed=r["unit_printed"],
                precision_printed="10000" if "Juta" in (r["unit_printed"] or "") else "",
                estimate_method="accounting", reliability="ok", file_id=sha.get(r["source_file"], ""),
                pdf_page=r["pdf_page"], printed_page=r["printed_page"], table_ref=f"Jadual {r['jadual']}",
                l1_ref=f"sources/states/data/_national/fact_state_finance_all.csv#row{i}")


def build_federal_loans(obs, checks):
    """What each state government owes the federal government at year-end, by the payer's accounts (Phase 3,
    gap_federal_vs_state transfer `loans`): PKKP Penyata Akaun Memorandum Pinjaman dan Pendahuluan Boleh
    Dituntut, section PINJAMAN, category KERAJAAN NEGERI, one row per state, Baki Belum Selesai (outstanding
    balance), each year from its own volume (golden rule 6). FY2009 prints only the total. Advances
    (PENDAHULUAN) are a separate section and not loaded here. Check C17: the states add up to the printed
    'Jumlah Kerajaan Negeri' to the sen."""
    import glob
    sha = {r["file_name"]: r["sha256"] for r in rows(os.path.join(META, "registry_file.csv"))}
    for path in sorted(glob.glob(os.path.join(PKKP, "*", "fact_loans_receivable.csv"))):
        rel = os.path.relpath(path, REPO)
        yr = os.path.basename(os.path.dirname(path))
        detail, total = Decimal(0), None
        for i, r in enumerate(rows(path), start=2):
            if (r["section_bm"].upper() != "PINJAMAN" or not r["category_bm"].upper().startswith("KERAJAAN NEGERI")
                    or r["year"] != yr or not r["source_file"].startswith(yr)):
                continue
            v = dec(r["baki_belum_selesai_rm"])
            if r["row_type"] == "subtotal":
                total = v
                continue
            g = STATE_ISO.get(r["peminjam_bm"].strip())
            if not g or v is None:
                sys.exit(f"PKKP {yr} loans receivable: unknown state government {r['peminjam_bm']!r}")
            detail += v
            obs.add(indicator_code="federal_gov.loans_receivable.state_government", geo_code=g, period_code=yr,
                    entity_id=entity("federal_gov", "MY", yr), basis="audited", edition_id=f"pkkp:{r['source_file']}",
                    vintage=yr, value=v, value_printed=r["baki_belum_selesai_rm"], unit_printed="RM",
                    precision_printed="0.01", estimate_method="accounting", reliability="ok",
                    file_id=sha.get(r["source_file"], ""), pdf_page=r["pdf_page"], printed_page=r["printed_page"],
                    table_ref="Penyata Akaun Memorandum Pinjaman dan Pendahuluan Boleh Dituntut: Pinjaman, Kerajaan Negeri",
                    l1_ref=f"{rel}#row{i}")
        if total is not None and detail:
            d = detail - total
            checks.append(["C17 federal loans to the states add up to the printed Jumlah Kerajaan Negeri", yr,
                           "PASS" if abs(d) <= Decimal("0.01") else "FAIL", f"states {detail} vs printed {total}"])


# PKKP prints revenue categories by name; the Budget revenue book's section codes (D: gap_revenue method) name them
REV_NAME_TO_KOD = {"HASIL CUKAI": "60000", "JUMLAH HASIL CUKAI": "60000",
                   "HASIL BUKAN CUKAI": "70000", "JUMLAH HASIL BUKAN CUKAI": "70000",
                   "TERIMAAN BUKAN HASIL": "80000", "JUMLAH TERIMAAN BUKAN HASIL": "80000",
                   "HASIL WILAYAH PERSEKUTUAN": "90000", "JUMLAH HASIL WILAYAH PERSEKUTUAN": "90000",
                   "JUMLAH HASIL WILAYAH-WILAYAH PERSEKUTUAN": "90000",
                   "JUMLAH PELBAGAI TERIMAAN": "pelbagai_terimaan_2009", "HASIL": "_total", "JUMLAH HASIL": "_total"}
REV_BASIS = {"anggaran_asal_rm": "budget_estimate", "anggaran_disemak_rm": "revised_estimate", "sebenar_rm": "audited"}


OBLIGATION_LINES = {   # (file, printed label upper-cased) -> instrument; each year from its own volume
    ("fact_memorandum.csv", "HUTANG AWAM"): "debt", ("fact_memorandum.csv", "HUTANG PERSEKUTUAN"): "debt",
    ("fact_memorandum.csv", "LIABILITI INISIATIF PEMBIAYAAN SWASTA"): "pfi",
    ("fact_memorandum.csv", "KOMITMEN KEWANGAN"): "commitments",
    ("fact_guarantees.csv", "JUMLAH KOMITMEN JAMINAN"): "committed_guarantees",
    ("fact_statutory_guarantees.csv", "JUMLAH JAMINAN PINJAMAN"): "loan_guarantees",
    ("fact_statutory_guarantees.csv", "JUMLAH JAMINAN PENCARUM / PENDEPOSIT"): "deposit_guarantees",
}


def build_obligations(obs, checks):
    """Federal obligations (Phase 5, gap_obligations_growth): stocks at 31 December from PKKP's memorandum accounts
    and guarantee registers, FY2009-2024, each year from its own volume (method: core/pipeline/build_gap_obligations.py).
    FY2009-2011 print no deposit-guarantee section: their register total is the loan guarantees. Check C19: one
    figure per instrument and year."""
    import glob
    sha = {r["file_name"]: r["sha256"] for r in rows(os.path.join(META, "registry_file.csv"))}
    seen = defaultdict(list)
    for d in sorted(glob.glob(os.path.join(PKKP, "*"))):
        yr = os.path.basename(d)
        if not yr.isdigit():
            continue
        for fname in ("fact_memorandum.csv", "fact_guarantees.csv", "fact_statutory_guarantees.csv"):
            path = os.path.join(d, fname)
            if not os.path.exists(path):
                continue
            rel = os.path.relpath(path, REPO)
            for i, r in enumerate(rows(path), start=2):
                if r["year"] != yr or not r["source_file"].startswith(yr):
                    continue
                if fname == "fact_memorandum.csv" and "LIABILITI" not in r["section"].upper():
                    continue
                label = (r.get("line_item_bm") or r.get("agensi_bm") or "").strip().upper()
                inst = OBLIGATION_LINES.get((fname, label))
                if fname == "fact_statutory_guarantees.csv" and int(yr) <= 2011 and label in (
                        "JUMLAH JAMINAN", "JUMLAH JAMINAN BERKANUN") and r["row_type"] == "total":
                    inst = "loan_guarantees"
                if not inst:
                    continue
                col = "amount_rm" if fname == "fact_memorandum.csv" else "jumlah_rm"
                v = dec(r[col])
                if v is None:
                    continue
                seen[(inst, yr)].append(v)
                obs.add(indicator_code=f"federal_gov.obligation.{inst}", geo_code="MY", period_code=yr,
                        entity_id=entity("federal_gov", "MY", yr), basis="audited", edition_id=f"pkkp:{r['source_file']}",
                        vintage=yr, value=v, value_printed=r[col], unit_printed="RM", precision_printed="0.01",
                        estimate_method="accounting", reliability="ok", file_id=sha.get(r["source_file"], ""),
                        pdf_page=r["pdf_page"], printed_page=r["printed_page"], table_ref=r["statement"],
                        l1_ref=f"{rel}#row{i}")
    # contributor/depositor guarantees before the register printed them (FY2010-2011): Nota 10(b) 'Simpanan
    # pendeposit di BSN, KWSG, KWSP dan LTH', the same concept (C21: where both are printed, note = register)
    note_dep, agree = {}, []
    for path in sorted(glob.glob(os.path.join(PKKP, "*", "fact_other_notes.csv"))):
        yr = os.path.basename(os.path.dirname(path))
        rel = os.path.relpath(path, REPO)
        for i, r in enumerate(rows(path), start=2):
            if r["year"] == yr and r["source_file"].startswith(yr) and r["nota"].strip() == "10(b)" and \
                    r["line_item_bm"].strip().lower().startswith("simpanan pendeposit") and dec(r["amount_rm"]) is not None:
                note_dep[yr] = (i, rel, r)
    for yr, (i, rel, r) in sorted(note_dep.items()):
        v = dec(r["amount_rm"])
        if ("deposit_guarantees", yr) in seen:
            agree.append((yr, abs(seen[("deposit_guarantees", yr)][0] - v)))
            continue
        seen[("deposit_guarantees", yr)].append(v)
        obs.add(indicator_code="federal_gov.obligation.deposit_guarantees", geo_code="MY", period_code=yr,
                entity_id=entity("federal_gov", "MY", yr), basis="audited", edition_id=f"pkkp:{r['source_file']}",
                vintage=yr, value=v, value_printed=r["amount_rm"], unit_printed="RM", precision_printed="1",
                estimate_method="accounting", reliability="ok", file_id=sha.get(r["source_file"], ""),
                pdf_page=r["pdf_page"], printed_page=r["printed_page"], table_ref=r["statement"] + " 10(b)",
                l1_ref=f"{rel}#row{i}")
    checks.append(["C21 deposit guarantees: Nota 10(b) equals the Jaminan Berkanun register where both are printed",
                   "PKKP", "PASS" if agree and all(d <= 1 for _, d in agree) else "FAIL",
                   ", ".join(f"FY{y} {d}" for y, d in agree) or "none compared"])
    bad = {k: v for k, v in seen.items() if len(v) != 1}
    checks.append(["C19 one printed figure per federal obligation and year (PKKP memorandum, own volume)", "PKKP",
                   "PASS" if not bad else "FAIL", f"{len(seen)} instrument-years" + (f"; {bad}" if bad else "")])


PLAN_STATE = {"Johor": "MY-01", "Kedah": "MY-02", "Kelantan": "MY-03", "Melaka": "MY-04", "Negeri Sembilan": "MY-05",
              "Pahang": "MY-06", "Pulau Pinang": "MY-07", "Perak": "MY-08", "Perlis": "MY-09", "Selangor": "MY-10",
              "Terengganu": "MY-11", "Sabah": "MY-12", "Sarawak": "MY-13", "WP Kuala Lumpur": "MY-14",
              "WP Labuan": "MY-15"}
PLAN_J10 = {"Hasil": "federal_gov.revenue.total", "Perbelanjaan Mengurus": "federal_gov.expenditure.opex",
            "Perbelanjaan Pembangunan Kasar": "federal_gov.expenditure.devex",
            "Tolak: Terimaan Balik Pinjaman": "federal_gov.expenditure.devex_loan_recovery",
            "Perbelanjaan Pembangunan Bersih": "federal_gov.expenditure.devex_net",
            "Baki Keseluruhan": "federal_gov.overall_balance", "Baki Semasa": "federal_gov.current_balance"}
PLAN_J14 = {"Jumlah Guna Tenaga": ("lfs.employed", 1000), "Jumlah Tenaga Buruh": ("lfs.labour_force", 1000),
            "Penganggur": ("lfs.unemployed", 1000), "Kadar Pengangguran, %": ("lfs.unemployment_rate", 1),
            "Kadar Penyertaan Tenaga Buruh, %": ("lfs.participation_rate", 1)}


def build_plan_targets(obs, checks):
    """RMKe-12's 2025 targets (Phase 5, gap_target_vs_outcome; method in core/pipeline/build_gap_target.py), basis
    target, from sources/rmk: GDP by state (level 2025 and the 2021/2025 average growth; the plan's KL row includes
    Putrajaya, so it is MY-14 with breakdown geo_scope=MY-14+MY-16, never the KL total), federal finance and the
    labour market (2025). Lines whose outcome core does not hold stay at L1."""
    man = {r["file_name"]: r for r in rows(os.path.join(REPO, "sources", "rmk", "data", "_documents_manifest.csv"))}
    path = os.path.join(REPO, "sources", "rmk", "data", "rmk12", "fact_rmk12_lampiran.csv")
    rel = os.path.relpath(path, REPO)
    n = 0
    for i, r in enumerate(rows(path), start=2):
        j, line, m = r["jadual"], r["line_bm"], r["measure"]
        ind = per = None
        geo, bk, v = "MY", "_total", dec(r["value"])
        if j == "5" and line == "KDNK" and m in ("sasaran_2025", "sasaran_purata_rmk12_2021_2025"):
            geo = PLAN_STATE[r["section_bm"]]
            bk = "geo_scope=MY-14+MY-16" if geo == "MY-14" else "_total"
            if m == "sasaran_2025":
                ind, per, v = "gdp.real", "2025", v * 1000000
            else:
                ind, per = "gdp.real.avg_growth", "2021/2025"
        elif j == "10" and line in PLAN_J10 and m == "sasaran_2025":
            ind, per, v = PLAN_J10[line], "2025", v * 1000000
        elif j == "10" and line == "% kepada KDNK" and m == "sasaran_2025":
            # a range target: two observations, its lower and upper end as printed ('-3.5 ~ -3.0')
            for b, x in (("bound=lower", r["value"]), ("bound=upper", r["value_hi"])):
                n += 1
                obs.add(indicator_code="federal_gov.overall_balance.pct_gdp", geo_code="MY", period_code="2025",
                        breakdown_key=b, entity_id=entity("federal_gov", "MY", "2025"), basis="target",
                        edition_id="rmk:rmk12.pdf", vintage="2021", value=dec(x), value_printed=r["value_printed"],
                        unit_printed=r["unit_printed"], precision_printed="0.1", estimate_method="plan", reliability="ok",
                        file_id=man["rmk12.pdf"]["sha256"], pdf_page=r["pdf_page"], printed_page=r["printed_page"],
                        table_ref=f"RMKe-12 Lampiran Jadual {j}: {r['table_title_bm']}", l1_ref=f"{rel}#row{i}")
            continue
        elif j == "14" and line in PLAN_J14 and m == "sasaran_2025":
            ind, mult = PLAN_J14[line]
            per, v = "2025", v * mult
        if not ind:
            continue
        n += 1
        obs.add(indicator_code=ind, geo_code=geo, period_code=per, breakdown_key=bk, entity_id=entity(
                    "federal_gov", "MY", per[-4:]) if ind.startswith("federal_gov.") else "_none",
                basis="target", edition_id="rmk:rmk12.pdf", vintage="2021", value=v, value_printed=r["value_printed"],
                unit_printed=r["unit_printed"], precision_printed={"RM juta": "1000000", "'000 orang": "100"}.get(
                    r["unit_printed"], "0.1"),
                estimate_method="plan", reliability="ok", file_id=man["rmk12.pdf"]["sha256"], pdf_page=r["pdf_page"],
                printed_page=r["printed_page"], table_ref=f"RMKe-12 Lampiran Jadual {j}: {r['table_title_bm']}",
                l1_ref=f"{rel}#row{i}")
    checks.append(["C22 RMKe-12 targets loaded (15 state GDP levels and growth, 7 federal + the %-of-GDP range, 5 "
                   "labour)", "rmk", "PASS" if n == 44 else "FAIL", f"{n} targets"])


def build_revenue_by_type(obs, checks):
    """Federal revenue by type (Phase 5, gap_revenue_estimate_vs_collected): PKKP Nota 5(a) levels 0 and 1, FY2009-
    2024 own volume, original and revised estimates and actual; the Budget revenue books' (Anggaran Hasil 2025-
    2026) section and total rows: actual, revised estimate, estimate. Breakdown hasil_kod = the book's section
    code (REV_NAME_TO_KOD maps PKKP's printed names). Check C18: PKKP's level-1 rows add up to its level 0."""
    import glob
    sha = {r["file_name"]: r["sha256"] for r in rows(os.path.join(META, "registry_file.csv"))}
    for path in sorted(glob.glob(os.path.join(PKKP, "*", "fact_revenue.csv"))):
        rel = os.path.relpath(path, REPO)
        yr = os.path.basename(os.path.dirname(path))
        sums = defaultdict(Decimal)
        tot = {}
        for i, r in enumerate(rows(path), start=2):
            if r["level"] not in ("0", "1") or r["year"] != yr or not r["source_file"].startswith(yr):
                continue
            name = r["item_bm"].strip().upper()
            kod = REV_NAME_TO_KOD.get(name)
            if kod is None:
                sys.exit(f"PKKP {yr} revenue: no hasil_kod for level-{r['level']} {name!r} (declare it)")
            bk = "_total" if kod == "_total" else f"hasil_kod={kod}"
            for col, basis in REV_BASIS.items():
                v = dec(r[col])
                if v is None:
                    continue
                if kod == "_total":
                    tot[basis] = v
                else:
                    sums[basis] += v
                obs.add(indicator_code="federal_gov.revenue.by_type", geo_code="MY", period_code=yr, breakdown_key=bk,
                        entity_id=entity("federal_gov", "MY", yr), basis=basis, edition_id=f"pkkp:{r['source_file']}",
                        vintage=yr, value=v, value_printed=r[col], unit_printed="RM", precision_printed="0.01",
                        estimate_method="accounting", reliability="ok", file_id=sha.get(r["source_file"], ""),
                        pdf_page=r["pdf_page"], printed_page=r["printed_page"], table_ref=r["statement"],
                        l1_ref=f"{rel}#row{i}")
        for basis, t in tot.items():
            d = sums[basis] - t
            checks.append(["C18 PKKP revenue types add up to the printed total (Nota 5(a))", f"{yr} {basis}",
                           "PASS" if abs(d) <= Decimal("2") else "FAIL", f"types {sums[basis]} vs total {t}"])
    for path in sorted(glob.glob(os.path.join(REPO, "sources", "anggaran-hasil", "data", "*", "fact_hasil_ringkasan_*.csv"))):
        rel = os.path.relpath(path, REPO)
        book = os.path.basename(os.path.dirname(path))
        for i, r in enumerate(rows(path), start=2):
            if r["level"] not in ("section", "total"):
                continue
            m = re.fullmatch(r"(sebenar|anggaran_disemak|anggaran)_(\d{4})", r["measure"])
            if not m:
                continue
            basis = {"sebenar": "actual", "anggaran_disemak": "revised_estimate", "anggaran": "budget_estimate"}[m.group(1)]
            v = dec(r["amount_rm"])
            if v is None:
                continue
            bk = "_total" if r["level"] == "total" else f"hasil_kod={r['kod']}"
            obs.add(indicator_code="federal_gov.revenue.by_type", geo_code="MY", period_code=m.group(2), breakdown_key=bk,
                    entity_id=entity("federal_gov", "MY", m.group(2)), basis=basis,
                    edition_id=f"anggaran_hasil:{r['source_file']}", vintage=book, value=v,
                    value_printed=r["amount_rm"], unit_printed="RM", precision_printed="1", estimate_method="accounting",
                    reliability="ok", file_id=sha.get(r["source_file"], ""), pdf_page=r["pdf_page"],
                    printed_page=r["printed_page"], table_ref=f"Anggaran Hasil Kerajaan Persekutuan {book}: Ringkasan",
                    l1_ref=f"{rel}#row{i}")


PERF_LINES = {"revenue": "federal_gov.revenue.total", "opex": "federal_gov.expenditure.opex",
              "devex": "federal_gov.expenditure.devex", "covid_fund_exp": "federal_gov.expenditure.covid_fund"}
TRANSFER_LINE = "Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan"


def build_federal(obs):
    """Federal totals, audited, straight from each year's own PKKP volume (Phase 3; until 2026-11-05 they were
    read through curated/fact_fiscal_headline.csv, caveat CV16).

      FY2010-2024  Penyata Prestasi Kewangan (fact_financial_performance, basis sebenar, own volume): revenue,
                   operating expenditure (Belanja Mengurus, before the transfer to the Development Fund),
                   development expenditure (gross) and the COVID-19 Fund; printed in whole ringgit
      FY2009       the older presentation: Akaun Hasil Disatukan (fact_revenue_account_statement) 'Jumlah
                   Hasil' and 'Perbelanjaan Mengurus (Tanpa Pindahan)', and the development grand total
                   (fact_devex_maksud, JUMLAH PERBELANJAAN PEMBANGUNAN)
      every year   the transfer to the Development Fund (Akaun Hasil Disatukan, 'Pindahan Lebihan Hasil ke
                   Kumpulan Wang Pembangunan'), paid under a supply vote, so that votes = opex + transfer (C16)
    Only the own volume's figure for its own year (golden rule 6); comparatives printed in later volumes stay
    in L1."""
    import glob
    sha = {r["file_name"]: r["sha256"] for r in rows(os.path.join(META, "registry_file.csv"))}

    def put(ind, r, col, rel, i, unit_printed, prec, table):
        v = dec(r[col])
        if v is None:
            return
        obs.add(indicator_code=ind, geo_code="MY", period_code=r["year"], entity_id=entity("federal_gov", "MY", r["year"]),
                basis="audited", edition_id=f"pkkp:{r['source_file']}", vintage=r["year"], value=v,
                value_printed=r[col], unit_printed=unit_printed, precision_printed=prec, estimate_method="accounting",
                reliability="ok", file_id=sha.get(r["source_file"], ""), pdf_page=r["pdf_page"],
                printed_page=r["printed_page"], table_ref=table, l1_ref=f"{rel}#row{i}")

    for path in sorted(glob.glob(os.path.join(PKKP, "*", "fact_financial_performance.csv"))):
        rel = os.path.relpath(path, REPO)
        for i, r in enumerate(rows(path), start=2):
            if r["basis"] == "sebenar" and r["line_code"] in PERF_LINES and r["source_file"].startswith(r["year"]):
                put(PERF_LINES[r["line_code"]], r, "amount_rm", rel, i, "RM", "1",
                    f"{r['statement']} ({r['line_item_bm']})")
    for path in sorted(glob.glob(os.path.join(PKKP, "*", "fact_revenue_account_statement.csv"))):
        rel = os.path.relpath(path, REPO)
        for i, r in enumerate(rows(path), start=2):
            if not r["source_file"].startswith(r["year"]):
                continue
            if r["line_item_bm"] == TRANSFER_LINE:
                put("federal_gov.expenditure.transfer_development_fund", r, "sebenar_rm", rel, i, "RM", "0.01",
                    f"{r['statement']} ({r['line_item_bm']})")
            elif r["year"] == "2009" and r["row_type"] == "subtotal" and r["line_item_bm"] in (
                    "Jumlah Hasil", "Perbelanjaan Mengurus (Tanpa Pindahan)"):
                ind = "federal_gov.revenue.total" if r["line_item_bm"] == "Jumlah Hasil" else "federal_gov.expenditure.opex"
                put(ind, r, "sebenar_rm", rel, i, "RM", "0.01", f"{r['statement']} ({r['line_item_bm']})")
    path = os.path.join(PKKP, "2009", "fact_devex_maksud.csv")
    for i, r in enumerate(rows(path), start=2):
        if r["maksud_code"] == "TOTAL" and r["year"] == "2009":
            put("federal_gov.expenditure.devex", r, "sebenar_jumlah_rm", os.path.relpath(path, REPO), i, "RM", "0.01",
                f"{r['statement']} ({r['jumlah_label_bm']})")


BNM_FED = {"cur_bud_rev": "federal_gov.revenue.total", "cur_bud_exp": "federal_gov.expenditure.opex",
           "dev_exp_gro_dev_exp": "federal_gov.expenditure.devex",
           "dev_exp_les_loa_rec": "federal_gov.expenditure.devex_loan_recovery",
           "dev_exp_net_dev_exp": "federal_gov.expenditure.devex_net",
           # BNM's API keys are shifted by one from ov_sur_def onward (sources/bnm/data/_source_anomalies.csv):
           # ov_sur_def holds the COVID-19 Fund (blank before 2020) and sou_fin_dom_bor_gro_dom_bor the overall
           # balance; proved every annual row by check C20 (current balance - net DE - Fund = overall balance)
           "ov_sur_def": "federal_gov.expenditure.covid_fund",
           "sou_fin_dom_bor_gro_dom_bor": "federal_gov.overall_balance"}
MOF_FED = {"revenue": "federal_gov.revenue.total", "operating_expenditure": "federal_gov.expenditure.opex",
           "development_expenditure_gross": "federal_gov.expenditure.devex",
           "development_expenditure_loan_recovery": "federal_gov.expenditure.devex_loan_recovery",
           "development_expenditure_net": "federal_gov.expenditure.devex_net",
           "covid19_fund": "federal_gov.expenditure.covid_fund", "overall_balance": "federal_gov.overall_balance",
           "current_balance": "federal_gov.current_balance", "overall_balance_pct_gdp": "federal_gov.overall_balance.pct_gdp"}


def build_federal_reported(obs):
    """Phase 2: the same federal totals as published by two other institutions, beside PKKP's audited ones.

    BNM Monthly Statistical Bulletin table 3.1 (annual rows; basis actual, reported by BNM) and MOF's
    Tinjauan Fiskal Jadual 1.1 (official actuals; one edition per year by the rule in
    curated/pipeline/mof_editions.py, own volume Y+2; later restatements stay in L1). Where the three
    publishers differ, all three are kept as published: that difference is the reconciliation product."""
    import glob
    sys.path.insert(0, os.path.join(REPO, "curated", "pipeline"))
    import mof_editions
    m = Decimal(1000000)
    bnm_dir = os.path.join(REPO, "sources", "bnm", "data")
    vin = {r["dataset"]: r for r in rows(os.path.join(bnm_dir, "_vintage_log.csv")) if r["state"] == "current"}["msb_3_1"]
    d = vin["data_as_of"][:10]
    worst, n_id = Decimal(0), 0
    for i, r in enumerate(rows(os.path.join(bnm_dir, "msb_3_1.csv")), start=2):
        if r["period"].strip():
            continue  # quarterly rows
        cur, net, ob = dec(r["cur_bud_sur_def"]), dec(r["dev_exp_net_dev_exp"]), dec(r["sou_fin_dom_bor_gro_dom_bor"])
        if None not in (cur, net, ob):
            n_id += 1
            worst = max(worst, abs(cur - net - (dec(r["ov_sur_def"]) or 0) - ob))
        for col, ind in BNM_FED.items():
            v = dec(r[col])
            if v is None:
                continue
            obs.add(indicator_code=ind, geo_code="MY", period_code=r["year_dt"], entity_id=entity("federal_gov", "MY", r["year_dt"]),
                    basis="actual", edition_id=f"bnm:msb_3_1@{d}", vintage=d, value=v * m, value_printed=r[col],
                    unit_printed="RM million", precision_printed="0.000000000001", estimate_method="accounting",
                    reliability="ok", file_id=vin["sha256"], table_ref="BNM MSB 3.1 Federal Government Finance",
                    l1_ref=f"sources/bnm/data/msb_3_1.csv#row{i}")
    obs.extra_checks.append(["C20 BNM MSB 3.1 shifted keys: current balance - net DE - COVID-19 Fund (ov_sur_def) = "
                             "overall balance (sou_fin_dom_bor_gro_dom_bor), every annual row", "BNM",
                             "PASS" if n_id and worst <= Decimal("1.5") else "FAIL",  # four figures, each rounded
                             f"{n_id} annual rows; largest difference RM{worst} million (printed rounding)"])
    reg = {(r["edition"], r["file_name"]): r["sha256"] for r in rows(os.path.join(META, "registry_file.csv"))
           if r["series_id"] == "tinjauan_fiskal"}
    cand = []
    for folder in sorted(glob.glob(os.path.join(REPO, "sources", "mof-fiscal-outlook", "data", "*_public_finance_stats"))):
        rel = os.path.relpath(os.path.join(folder, "fact_headline.csv"), REPO)
        for i, r in enumerate(rows(os.path.join(REPO, rel)), start=2):
            r.update(edition=int(r["edition"]), target_year=int(r["target_year"]), _l1=f"{rel}#row{i}")
            r["line"] = mof_editions.LINE_CROSSWALK.get(r["line"], r["line"])
            cand.append(r)
    for (line, year), r in sorted(mof_editions.choose(cand).items()):
        pct = line.endswith("_pct_gdp")
        v = dec(r["pct_of_gdp"] if pct else r["amount_rm_juta"])
        if line not in MOF_FED or r["basis"] != "official_actual" or v is None:
            continue
        sha = reg.get((str(r["edition"]), r["source_file"]))
        if not sha:
            sys.exit(f"MOF {r['edition']} {r['source_file']}: no sha256 in meta/registry_file.csv")
        obs.add(indicator_code=MOF_FED[line], geo_code="MY", period_code=str(year), entity_id=entity("federal_gov", "MY", year),
                basis="actual", edition_id=f"mof:tinjauan_fiskal@{r['edition']}", vintage=str(r["edition"]),
                value=v if pct else v * m, value_printed=r["pct_of_gdp"] if pct else r["amount_rm_juta"],
                unit_printed="% of GDP" if pct else "RM million", precision_printed="0.1" if pct else "1",
                estimate_method="accounting", reliability="ok", file_id=sha, pdf_page=r["pdf_page"],
                printed_page=r["printed_page"], table_ref=f"Tinjauan Fiskal {r['edition']}, Jadual {r['table_no']}",
                l1_ref=r["_l1"])


def build_flags(obs):
    """Phase 2: flags from L1 carried onto every observation they concern (the verifier's G1, 2026-11-04).

    Three sources, each declared here before use:
      identity_breach  sources/dosm/data/_identity_breaches_realeconomy.csv: the L1 row's own columns do
                       not add up (e.g. labour force != employed + unemployed); every figure from that row
      out_of_bounds    a rate or share outside 0-100 (e.g. Telang Usan 2018, unemployment 293%)
      duplicate_area   two or more areas of one state and year print identical LFS figures (employed,
                       unemployed, outside the labour force, both rates): a copied row, not a measurement
    Nothing is changed or dropped: the figure stays as published and carries caveat CV15."""
    reg = os.path.join(DOSM, "_identity_breaches_realeconomy.csv")
    breach = {}
    for r in rows(reg):
        breach.setdefault((r["dataset"], r["key"]), []).append(f"{r['identity']}: published {r['published']}, implied {r['implied']}")
    keyf = {"lfs_dun": lambda r: f"{r['dun']} {r['parlimen']} {r['state']} {r['date'][:7]}",
            "lfs_parlimen": lambda r: f"{r['parlimen']} {r['state']} {r['date'][:7]}",
            "lfs_district": lambda r: f"{r['district']} {r['state']} {r['date'][:7]}",
            "hies_state_percentile": lambda r: f"{r['state']}/{r['date']}",
            "hies_malaysia_percentile": lambda r: r["date"]}
    out = []
    l1_rows = {}
    for ds, kf in keyf.items():
        for i, r in enumerate(rows(os.path.join(DOSM, f"{ds}.csv")), start=2):
            ref = f"sources/dosm/data/{ds}.csv#row{i}"
            l1_rows[ref] = r
            for note in breach.get((ds, kf(r)), []):
                out.append({"l1_ref": ref, "indicator_code": "", "flag": "identity_breach", "note": note,
                            "register": "sources/dosm/data/_identity_breaches_realeconomy.csv"})
    # duplicate areas: identical LFS figures for two or more areas of one state and year
    for ds in ("lfs_dun", "lfs_parlimen", "lfs_district"):
        groups = defaultdict(list)
        for ref, r in l1_rows.items():
            if ref.startswith(f"sources/dosm/data/{ds}.csv#"):
                sig = tuple(r.get(c, "") for c in ("lf_employed", "lf_unemployed", "lf_outside", "u_rate", "p_rate"))
                if all(sig):
                    groups[(r["state"], r["date"], sig)].append(ref)
        for (st, d, sig), refs in groups.items():
            if len(refs) > 1:
                for ref in refs:
                    out.append({"l1_ref": ref, "indicator_code": "", "flag": "duplicate_area",
                                "note": f"{len(refs)} areas of {st} print identical LFS figures for {d[:4]} "
                                        f"(employed {sig[0]}, unemployed {sig[1]}, rates {sig[3]}/{sig[4]})",
                                "register": "core/pipeline/build_core.py build_flags (declared rule)"})
    for r in obs.rows:
        if (r["unit_printed"] == "percent" and r["value"] and
                not (Decimal(0) <= Decimal(r["value"]) <= Decimal(100))):
            out.append({"l1_ref": r["l1_ref"], "indicator_code": r["indicator_code"], "flag": "out_of_bounds",
                        "note": f"{r['indicator_code']} = {r['value_printed']} percent, outside 0-100",
                        "register": "core/pipeline/build_core.py build_flags (declared rule)"})
    # scope change inside one series (found by the gap_target_vs_outcome verifier, 2026-11-06): DOSM prints WP
    # Putrajaya's GDP separately only from its first year (2023 in gdp_state_real_supply); WP Kuala Lumpur's rows
    # before that include Putrajaya. Proof: RMKe-12 Jadual 5 footnotes its KL row 'Termasuk WP Putrajaya', and
    # DOSM's MY-14 for 2015-2018 equals it to rounding (core/_validation_gap_tvo.csv T7). The figure stays as
    # published; the row carries the flag and CV15.
    first16 = {}
    for r in obs.rows:
        if r["indicator_code"].startswith("gdp.") and r["geo_code"] == "MY-16" and r["edition_id"].startswith("dosm:"):
            first16[r["indicator_code"]] = min(first16.get(r["indicator_code"], "9999"), r["period_code"][:4])
    for r in obs.rows:
        f = first16.get(r["indicator_code"])
        if f and r["geo_code"] == "MY-14" and r["edition_id"].startswith("dosm:") and r["period_code"][:4] < f:
            out.append({"l1_ref": r["l1_ref"], "indicator_code": r["indicator_code"], "flag": "scope_includes_putrajaya",
                        "note": f"WP Kuala Lumpur before {f} includes WP Putrajaya, which DOSM prints separately only from "
                                f"{f}: growth across {f} compares different areas (proof: RMKe-12 Jadual 5 footnote; "
                                "DOSM MY-14 2015-2018 = the plan's KL including Putrajaya, gap_target_vs_outcome T7)",
                        "register": "core/pipeline/build_core.py build_flags (declared rule, 2026-11-06)"})
    # our own known extraction defects that reach core (meta/extraction_defect_flag.csv, each pointing to its
    # state_config.KNOWN_EXTRACTION_DEFECTS entry): the figure is the wrong printed line, caveat CV18
    want = {(d["indicator_code"], d["geo_code"], d["period_code"]): d
            for d in rows(os.path.join(META, "extraction_defect_flag.csv"))}
    for r in obs.rows:
        d = want.get((r["indicator_code"], r["geo_code"], r["period_code"]))
        if d:
            out.append({"l1_ref": r["l1_ref"], "indicator_code": r["indicator_code"], "flag": "our_extraction_defect",
                        "note": d["note"], "register": d["register"]})
    # FY2009 development votes whose printed JUMLAH differs from the sum of their printed project lines,
    # diagnosed in curated/_known_extraction_defects_curated.csv. Flagged on the vote total (caveat CV21)
    # except where the diagnosis proves the gap is a leaf WE failed to capture (the printed total is then right)
    reg = os.path.join(REPO, "curated", "_known_extraction_defects_curated.csv")
    gaps = {}
    for d in rows(reg):
        m = re.fullmatch(r"(P\.\d{2}) devex (\d{4})", d["key"].strip())
        if d["table"] == "fact_ministry_fiscal" and m and d["classification"] != "ours_proven":
            gaps[(m.group(1), m.group(2))] = d
    for r in obs.rows:
        if r["indicator_code"] == "federal_gov.vote.devex" and r["edition_id"].startswith("pkkp:"):
            path, n = r["l1_ref"].split("#row")
            l1 = rows(os.path.join(REPO, path))[int(n) - 2]
            d = gaps.get((l1["maksud_code"], l1["year"]))
            if d:
                if d["classification"] == "ours_suspected":
                    r["reliability"] = "low"  # our extraction of the JUMLAH line is suspected (verifier M2)
                out.append({"l1_ref": r["l1_ref"], "indicator_code": r["indicator_code"], "flag": "leaf_total_mismatch",
                            "note": f"printed JUMLAH {d['printed_rm']} vs project lines {d['computed_rm']} "
                                    f"({d['classification']}): {d['diagnosis'][:300]}",
                            "register": "curated/_known_extraction_defects_curated.csv"})
    seen, uniq = set(), []
    for f in out:
        k = (f["l1_ref"], f["indicator_code"], f["flag"], f["note"])
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    return sorted(uniq, key=lambda f: (f["l1_ref"], f["flag"], f["note"]))


# ---------------------------------------------------------------- dimensions
def dim_geo(obs):
    out = [{"geo_code": "MY", "geo_level": "country", "local_code": "MY", "name_bm": "Malaysia", "name_en": "Malaysia",
            "parent_geo_code": "", "hierarchy": "", "boundary_vintage": "", "boundary_vintage_proof": "stated"},
           {"geo_code": "_unallocated", "geo_level": "unallocated", "local_code": "", "name_bm": "Tidak diagihkan",
            "name_en": "Not allocated to a state (e.g. DOSM 'Supra')", "parent_geo_code": "MY", "hierarchy": "",
            "boundary_vintage": "", "boundary_vintage_proof": "stated"}]
    for name, code in sorted(STATE_ISO.items(), key=lambda x: x[1]):
        out.append({"geo_code": code, "geo_level": "state", "local_code": code[3:], "name_bm": name,
                    "name_en": STATE_EN.get(name, name), "parent_geo_code": "MY", "hierarchy": "administrative",
                    "boundary_vintage": "", "boundary_vintage_proof": "stated (ISO 3166-2:MY)"})
    proof = ("inferred: DOSM's HIES (2019-2024) and LFS (2021-2023) constituency files publish the same 222 parlimen "
             "and 600 DUN labels every year, the seat counts of the GE15 (2022) delineation (600 DUN includes Sabah's 73 "
             "seats from its 2019 redelineation; GE14 had 587). The 2019 figures are therefore tabulated on these later "
             "boundaries; DOSM does not state the boundary set")
    for g, (st, code, name) in sorted(obs.parlimen.items()):
        out.append({"geo_code": g, "geo_level": "parlimen", "local_code": code, "name_bm": name, "name_en": name,
                    "parent_geo_code": STATE_ISO[st], "hierarchy": "electoral",
                    "boundary_vintage": ELECTORAL_VINTAGE, "boundary_vintage_proof": proof})
    for g, (st, code, name, parent) in sorted(obs.dun.items()):
        out.append({"geo_code": g, "geo_level": "dun", "local_code": code, "name_bm": name, "name_en": name,
                    "parent_geo_code": parent, "hierarchy": "electoral",
                    "boundary_vintage": ELECTORAL_VINTAGE, "boundary_vintage_proof": proof})
    for g, (st, d) in sorted(obs.districts.items()):
        out.append({"geo_code": g, "geo_level": "district", "local_code": slug(d), "name_bm": d, "name_en": d,
                    "parent_geo_code": STATE_ISO[st], "hierarchy": "administrative", "boundary_vintage": DISTRICT_VINTAGE,
                    "boundary_vintage_proof": "inferred: sources/dosm/data/population_district.csv publishes the same "
                    "166 districts for every year 2020-2026; DOSM prints names, not codes, so local_code is the "
                    "name slug within its state"})
    return out


def dim_period(obs):
    out = []
    for p in sorted(obs.periods):
        if re.fullmatch(r"\d{4}/\d{4}", p):  # a multi-year period, e.g. a plan's 2021/2025 average growth
            a, b = p.split("/")
            out.append({"period_code": p, "freq": "P", "period_start": f"{a}-01-01", "period_end": f"{b}-12-31",
                        "year": b})
        elif re.fullmatch(r"\d{4}", p):
            out.append({"period_code": p, "freq": "A", "period_start": f"{p}-01-01", "period_end": f"{p}-12-31",
                        "year": p})
        elif "-Q" in p:
            y, q = p.split("-Q")
            m0 = (int(q) - 1) * 3 + 1
            ends = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
            out.append({"period_code": p, "freq": "Q", "period_start": f"{y}-{m0:02d}-01",
                        "period_end": f"{y}-{ends[int(q)]}", "year": y})
        else:
            y, m = p.split("-")
            last = {2: 29 if int(y) % 4 == 0 and (int(y) % 100 or int(y) % 400 == 0) else 28}.get(int(m),
                                                                                          30 if int(m) in (4, 6, 9, 11) else 31)
            out.append({"period_code": p, "freq": "M", "period_start": f"{p}-01", "period_end": f"{p}-{last:02d}",
                        "year": y})
    return out


def dim_breakdown(obs):
    keys = sorted({r["breakdown_key"] for r in obs.rows})
    out = []
    for k in keys:
        if k == "_total":
            out.append({"breakdown_key": k, "label": "no split", "axis": "", "member_code": ""})
            continue
        for part in k.split("|"):
            a, m = part.split("=")
            out.append({"breakdown_key": k, "label": k, "axis": a, "member_code": m})
    return out


# ---------------------------------------------------------------- checks
def checks(obs, geo, per, ind, brk, editions):
    out = []

    def add(check, scope, status, note):
        out.append([check, scope, status, note])

    key = Counter((r["indicator_code"], r["geo_code"], r["period_code"], r["breakdown_key"], r["entity_id"],
                   r["basis"], r["edition_id"], r["vintage"]) for r in obs.rows)
    dups = [k for k, n in key.items() if n > 1]
    add("C1 primary key unique", "fact_observation", "PASS" if not dups else "FAIL",
        f"{len(obs.rows)} rows" if not dups else f"{len(dups)} duplicate keys, e.g. {dups[0]}")
    fk = {"indicator_code": {r["indicator_code"] for r in ind}, "geo_code": {r["geo_code"] for r in geo},
          "period_code": {r["period_code"] for r in per}, "breakdown_key": {r["breakdown_key"] for r in brk}}
    for col, valid in fk.items():
        bad = Counter(r[col] for r in obs.rows if r[col] not in valid)
        add(f"C2 {col} resolves", "fact_observation", "PASS" if not bad else "FAIL",
            "all resolve" if not bad else f"{sum(bad.values())} rows, e.g. {bad.most_common(3)}")
    codes = defaultdict(set)
    for c in rows(os.path.join(META, "code_list.csv")):
        codes[c["code_list"]].add(c["code"])
    for col, lst in (("basis", "basis"), ("status", "status")):
        bad = Counter(r[col] for r in obs.rows if r[col] not in codes[lst])
        add(f"C3 {col} in meta/code_list.csv", "fact_observation", "PASS" if not bad else "FAIL",
            "ok" if not bad else str(bad.most_common(3)))
    # a document registered with no sha256 is one D24 keeps as 'PDF not archived' (CV17): its rows keep their
    # page and L1 row; any other row without a file sha256 is a provenance failure
    unarchived = {r["file_name"] for r in rows(os.path.join(META, "registry_file.csv")) if not r["sha256"]}
    d24 = sum(1 for r in obs.rows if not r["file_id"] and r["edition_id"].split(":", 1)[-1] in unarchived)
    noprov = sum(1 for r in obs.rows if not r["l1_ref"] or (not r["file_id"] and
                                                            r["edition_id"].split(":", 1)[-1] not in unarchived))
    add("C4 every row has provenance (file sha256 + L1 row; D24 volumes: page + L1 row)", "fact_observation",
        "PASS" if not noprov else "FAIL",
        f"{noprov} rows without" + (f"; {d24} rows from D24 volumes (no PDF held, caveat CV17)" if d24 else ""))
    nounc = sum(1 for r in obs.rows if r["basis"] == "statistic" and not r["se"]
                and r["reliability"] not in ("unknown", "low"))
    add("C5 a survey estimate without published uncertainty says so (reliability = unknown)", "fact_observation",
        "PASS" if not nounc else "FAIL", f"{nounc} rows claim reliability without uncertainty")
    # distributions: cut-offs rise with the percentile (get_distribution relies on it); the 50th cut-off
    # against the headline median is reported, not reconciled (both kept as published)
    grp, med = defaultdict(dict), {}
    for r in obs.rows:
        if r["indicator_code"] == "hh_income.gross.pctile_group.max":
            grp[(r["geo_code"], r["period_code"])][int(r["breakdown_key"].split("=")[1])] = Decimal(r["value"])
        elif r["indicator_code"] == "hh_income.gross.median" and r["breakdown_key"] == "_total":
            med[(r["geo_code"], r["period_code"])] = Decimal(r["value"])
    nonmono = [k for k, v in grp.items() if [v[p] for p in sorted(v)] != sorted(v.values())]
    add("C9 percentile cut-offs rise with the percentile", "hh_income.gross.pctile_group.max",
        "PASS" if not nonmono else "FAIL", f"{len(grp)} place-years" + (f"; not rising: {sorted(nonmono)}" if nonmono else ""))
    off = sorted((k, v[50] - med[k]) for k, v in grp.items() if 50 in v and k in med and abs(v[50] - med[k]) > 1)
    add("C10 50th percentile cut-off vs the headline median (DOSM files, kept as published)",
        "hh_income.gross.pctile_group.max", "PASS" if not off else "INFO",
        f"{len(grp)} place-years; within RM1 except " + "; ".join(f"{g} {y}: {fmt(d)}" for (g, y), d in off)
        if off else f"{len(grp)} place-years within RM1")
    # two DOSM files print district Gini: core loads hh_inequality_district; where hies_district differs,
    # say so (both kept as published; the verifier's C2, 2026-11-04)
    a = {(r["state"], r["district"], r["date"][:4]): r["gini"] for r in rows(os.path.join(DOSM, "hies_district.csv"))
         if r.get("gini")}
    b = {(r["state"], r["district"], r["date"][:4]): r["gini"] for r in rows(os.path.join(DOSM, "hh_inequality_district.csv"))
         if r.get("gini")}
    diff = sorted(f"{k[1]} ({k[0]}) {k[2]}: {a[k]} vs {b[k]}" for k in a.keys() & b.keys() if Decimal(a[k]) != Decimal(b[k]))
    add("C11 district Gini: hies_district vs hh_inequality_district (core uses the latter)", "hh_income.gini",
        "PASS" if not diff else "INFO", f"{len(a.keys() & b.keys())} cells in both; " +
        (f"{len(diff)} differ: " + "; ".join(diff) if diff else "all agree"))
    # coverage: every view must be able to run for all 16 states and territories (golden rule 11)
    for i in sorted({r["indicator_code"] for r in obs.rows}):
        g = {r["geo_code"] for r in obs.rows if r["indicator_code"] == i and r["geo_code"].startswith("MY-")
             and "/" not in r["geo_code"]}
        if i.startswith("federal_gov."):  # national totals of the federal government: no state split by design
            continue
        if i.startswith("state_gov."):  # the Federal Territories have no state government: 13 is complete
            miss = sorted(set(STATE_ISO.values()) - set(GEO_ALIAS.values()) - g - {"MY-14", "MY-15", "MY-16"})
            add("C6 state coverage", i, "PASS" if not miss else "INFO",
                f"{len(g)} of 13 state governments" + (f"; never printed or not extracted for {', '.join(miss)}"
                                                        if miss else ""))
        else:
            want = int(next(x for x in ind if x["indicator_code"] == i)["expected_state_count"] or 16)
            note = next(x for x in ind if x["indicator_code"] == i)["coverage_note"]
            add("C6 state coverage", i, "PASS" if len(g) == want else "FAIL",
                f"{len(g)} of 16 states and territories" + (f" (expected {want}: {note})" if want != 16 else ""))
    # population: the parts add up (the L1 verifier does it per file; here on the conformed rows)
    pop = defaultdict(Decimal)
    for r in obs.rows:
        if r["indicator_code"] == "pop.total" and r["breakdown_key"] == "_total" and r["geo_code"].startswith("MY-") \
                and "/" not in r["geo_code"]:
            pop[r["period_code"]] += Decimal(r["value"])
    nat = {r["period_code"]: Decimal(r["value"]) for r in obs.rows
           if r["indicator_code"] == "pop.total" and r["geo_code"] == "MY" and r["breakdown_key"] == "_total"}
    worst = max((abs(pop[p] - nat[p]) for p in nat if p in pop), default=Decimal(0))
    add("C7 states sum to Malaysia (pop.total)", "pop.total", "PASS" if worst <= 800 else "FAIL",
        f"largest gap {fmt(worst)} persons over {len(nat)} years (rounding allowance 16 x 50)")
    bad, n = [], 0
    signed = {(STATE_ISO[s], y, STATE_LINES.get(line)) for (s, y, line) in sign_rules()}
    for r in obs.rows:
        p = (r["value_printed"] or "").replace(",", "").strip()
        neg = p.startswith("(") and p.endswith(")")
        pv = dec(p.strip("()"))
        if pv is None:
            continue
        u = (r["unit_printed"] or "").lower()
        scale = Decimal(1000000) if ("juta" in u or "million" in u) else Decimal(1000) if "'000" in u else Decimal(1)
        want = (-pv if neg else pv) * scale
        got = Decimal(r["value"])
        level = r["indicator_code"].startswith(("state_gov.expenditure.",)) \
            or (r["geo_code"], r["period_code"], r["indicator_code"]) in signed
        n += 1
        if (abs(got) != abs(want)) or (not level and got != want):
            bad.append(f"{r['indicator_code']} {r['geo_code']} {r['period_code']}: value {r['value']} vs printed "
                       f"{r['value_printed']} {r['unit_printed']}")
    # national series (Phase 2): the published identities, re-checked on the conformed rows
    tr, loans = defaultdict(dict), defaultdict(dict)
    for r in obs.rows:
        if r["indicator_code"].startswith("trade."):
            tr[r["period_code"]][r["indicator_code"]] = Decimal(r["value"])
        elif r["indicator_code"] == "credit.loans.banking_system":
            loans[r["period_code"]][r["breakdown_key"]] = Decimal(r["value"])
    off = sorted(p for p, v in tr.items()
                 if len(v) == 3 and v["trade.exports"] - v["trade.imports"] != v["trade.balance"])
    add("C12 trade balance = exports - imports (DOSM trade_headline, to the ringgit)", "trade.balance",
        "PASS" if not off else "INFO", f"{len(tr)} months" + (f"; differ in {off}" if off else ", all exact"))
    tol = Decimal(10000)  # RM0.01 million: BNM serves RM million to 12 places, so parts may round apart
    off = sorted(p for p, v in loans.items() if abs(v["_total"] - sum(x for k, x in v.items() if k != "_total")) > tol)
    add("C13 banking-system loans = commercial + Islamic + investment banks (BNM MSB 1.18)",
        "credit.loans.banking_system", "PASS" if not off else "INFO",
        f"{len(loans)} months" + (f"; differ in {off}" if off else ", within RM0.01 million"))
    import hashlib
    stale, files = [], {(r["edition_id"], r["file_id"]) for r in obs.rows
                      if r["indicator_code"].startswith(("trade.", "money.", "credit."))
                      or (r["indicator_code"] == "cpi.index" and r["geo_code"] == "MY")}
    for e_id, sha in sorted(files):
        pub, ds = e_id.split(":", 1)[0], e_id.split(":", 1)[1].split("@")[0]
        with open(os.path.join(DOSM if pub == "dosm" else BNM, f"{ds}.csv"), "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() != sha:
                stale.append(ds)
    add("C14 the file read is the vintage logged as current (sha256; national series)", "fact_observation",
        "PASS" if not stale else "FAIL", f"{len(files)} files" + (f"; differ: {stale}" if stale else ", all match"))
    ents = {r["entity_id"] for r in rows(os.path.join(REPO, "core", "dim_entity.csv"))} | {"_none"}
    stray = sorted({r["entity_id"] for r in obs.rows} - ents)
    add("C15 every entity_id is a registered entity (core/dim_entity.csv) or _none", "fact_observation",
        "PASS" if not stray else "FAIL", f"{len({r['entity_id'] for r in obs.rows}) - 1} entities used"
        + (f"; unregistered {stray}" if stray else ""))
    # C16 the votes add up to the audited totals printed in the same PKKP volume (operating: supply votes plus
    # charged heads; development: development votes plus the reserve)
    # the printed lines, all in core: operating votes = opex (before the transfer) + the transfer to the
    # Development Fund (itself paid under a vote); development votes = the development total
    aud = {(r["indicator_code"], r["period_code"]): Decimal(r["value"]) for r in obs.rows
           if r["basis"] == "audited" and r["edition_id"].startswith("pkkp:") and r["indicator_code"] in (
               "federal_gov.expenditure.opex", "federal_gov.expenditure.devex",
               "federal_gov.expenditure.transfer_development_fund")}
    tot = {}
    for (ind, y), v in aud.items():
        if ind == "federal_gov.expenditure.opex" and ("federal_gov.expenditure.transfer_development_fund", y) in aud:
            tot[(ind, y)] = v + aud[("federal_gov.expenditure.transfer_development_fund", y)]
        elif ind == "federal_gov.expenditure.devex":
            tot[(ind, y)] = v
    vs = defaultdict(Decimal)
    for r in obs.rows:
        if r["indicator_code"].startswith("federal_gov.vote.") and r["basis"] == "audited":
            vs[(r["indicator_code"].replace(".vote.", ".expenditure."), r["period_code"])] += Decimal(r["value"])
    off = sorted(f"{k[0].split('.')[-1]} {k[1]}: votes {fmt(vs[k])} vs printed {fmt(tot[k])}"
                 for k in vs if k in tot and abs(vs[k] - tot[k]) > 2)
    known = [o for o in off if o.startswith("devex 2009")]
    add("C16 PKKP votes add up to the printed audited totals (opex + transfer, devex; within RM2: the statement prints whole ringgit)", "federal_gov.vote.*",
        "PASS" if not off else "INFO" if off == known else "FAIL",
        f"{len(vs)} year-totals" + (f"; differ: {off}" if off else ", all within RM2")
        + ("; FY2009 devex: printed vote totals vs the printed grand total, diagnosed in "
           "curated/_known_extraction_defects_curated.csv (caveat CV21)" if known else ""))
    add("C8 value = value_printed x unit scale (sign kept, except spending levels and meta/sign_convention.csv)", "fact_observation",
        "PASS" if not bad else "FAIL", f"{n} rows checked" + (f"; {len(bad)} differ, e.g. {bad[:3]}" if bad else ""))
    for c, scope, status, note in getattr(obs, "extra_checks", []):
        add(c, scope, status, note)
    return out


def main():
    os.makedirs(CORE, exist_ok=True)
    ed = dosm_editions()
    obs = Obs()
    obs.districts = {}
    obs.parlimen = {}
    obs.dun = {}
    build_dosm(obs, ed)
    build_services(obs, ed)
    build_small_areas(obs, ed)
    build_distribution(obs, ed)
    build_national_accounts(obs, ed)
    build_states(obs)
    build_federal(obs)
    obs.extra_checks = []
    build_federal_reported(obs)
    build_national_series(obs, ed)
    build_votes(obs)
    build_federal_loans(obs, obs.extra_checks)
    build_revenue_by_type(obs, obs.extra_checks)
    build_obligations(obs, obs.extra_checks)
    build_plan_targets(obs, obs.extra_checks)
    ind = rows(os.path.join(META, "indicator.csv"))
    used = {r["indicator_code"] for r in obs.rows}
    missing = sorted(used - {r["indicator_code"] for r in ind})
    if missing:
        sys.exit(f"indicators used but not defined in meta/indicator.csv: {missing}")
    geo, per, brk = dim_geo(obs), dim_period(obs), dim_breakdown(obs)
    obs.rows.sort(key=lambda r: (r["indicator_code"], r["geo_code"], r["period_code"], r["breakdown_key"],
                                 r["entity_id"], r["basis"], r["edition_id"]))

    def write(name, data, fields):
        with open(os.path.join(CORE, name), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(data)

    write("dim_geo.csv", geo, list(geo[0]))
    hier = [{"hierarchy": g["hierarchy"], "child_geo_code": g["geo_code"], "parent_geo_code": g["parent_geo_code"]}
            for g in geo if g["parent_geo_code"] and g["hierarchy"]]
    hier += [{"hierarchy": "electoral", "child_geo_code": g["geo_code"], "parent_geo_code": "MY"}
             for g in geo if g["geo_level"] == "state"]
    write("geo_hierarchy.csv", sorted(hier, key=lambda h: (h["hierarchy"], h["child_geo_code"])),
          ["hierarchy", "child_geo_code", "parent_geo_code"])
    write("dim_period.csv", per, list(per[0]))
    write("dim_breakdown.csv", brk, list(brk[0]))
    flags = build_flags(obs)
    write("obs_flag.csv", flags, ["l1_ref", "indicator_code", "flag", "note", "register"])
    write("dim_indicator.csv", [r for r in ind if r["indicator_code"] in used], list(ind[0]))
    write("fact_observation.csv", obs.rows, OBS_FIELDS)
    ck = checks(obs, geo, per, [r for r in ind if r["indicator_code"] in used], brk, ed)
    with open(os.path.join(CORE, "_validation_core.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["check", "scope", "status", "note"])
        w.writerows(ck)
    tally = Counter(c[2] for c in ck)
    print(f"core: {len(obs.rows)} observations, {len(used)} indicators, {len(geo)} geos, {len(per)} periods; "
          f"checks: " + ", ".join(f"{v} {k}" for k, v in sorted(tally.items())))
    for c in ck:
        if c[2] == "FAIL":
            print("  FAIL", c)
    for k, n in obs.skipped.items():
        print(f"  skipped {n}: {k}")


if __name__ == "__main__":
    main()
