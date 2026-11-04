#!/usr/bin/env python3
"""Build the conformed core (L2), Phase 1 scope: state level, end to end (docs/DATA_MODEL.md §4-5, §15).

  python3 core/pipeline/build_core.py

Reads L1 (never edits it):
  sources/dosm/data/   population_state, population_district, population_malaysia, hh_income(_state),
                       hh_poverty, hh_inequality, lfs_year (national values),
                       hh_poverty_state, hh_inequality_state, hies_state, lfs_state_sex, cpi_state,
                       gdp_state_real_supply, hh_profile_state  (+ _vintage_log.csv for edition and sha256)
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
    "expenditure_total": "state_gov.expenditure.total",
    "surplus_deficit": "state_gov.surplus_deficit",
    "debt_total": "state_gov.debt.total",
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
                entity_id=f"state_gov:{g}", basis="audited", edition_id=f"states:{r['report']}",
                vintage=r["fiscal_year"], value=v, value_printed=r["amount_printed"], unit_printed=r["unit_printed"],
                precision_printed="10000" if "Juta" in (r["unit_printed"] or "") else "",
                estimate_method="accounting", reliability="ok", file_id=sha.get(r["source_file"], ""),
                pdf_page=r["pdf_page"], printed_page=r["printed_page"], table_ref=f"Jadual {r['jadual']}",
                l1_ref=f"sources/states/data/_national/fact_state_finance_all.csv#row{i}")


FEDERAL = {"opex_net_rm": ("federal_gov.expenditure.opex", "opex_source_file", "opex_pdf_page", "opex_printed_page"),
           "devex_gross_rm": ("federal_gov.expenditure.devex", None, None, None),
           "covid_fund_rm": ("federal_gov.expenditure.covid_fund", "covid_fund_source_file", "covid_fund_pdf_page",
                             "covid_fund_printed_page")}


def build_federal(obs):
    """Federal spending totals, audited (PKKP). Phase 1 reads them from curated/fact_fiscal_headline.csv, which
    cites the PKKP volume and page; Phase 3 moves them to PKKP entity observations."""
    import hashlib
    path = os.path.join(REPO, "curated", "fact_fiscal_headline.csv")
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    for i, r in enumerate(rows(path), start=2):
        for col, (ind, f_col, p_col, pp_col) in FEDERAL.items():
            v = dec(r.get(col))
            if v is None:
                continue
            src = r.get(f_col, "") if f_col else ""
            obs.add(indicator_code=ind, geo_code="MY", period_code=r["year"], entity_id="federal_gov:MY",
                    basis="audited", edition_id=f"pkkp:{src or 'FY' + r['year']}", vintage=r["year"], value=v,
                    value_printed=r[col], unit_printed="RM", estimate_method="accounting", reliability="ok",
                    file_id=sha, pdf_page=r.get(p_col, "") if p_col else "",
                    printed_page=r.get(pp_col, "") if pp_col else "",
                    table_ref=(src + (f" ({r.get(col.replace('_rm', '_basis'), '')})" if not f_col else "")),
                    l1_ref=f"curated/fact_fiscal_headline.csv#row{i}")


BNM_FED = {"cur_bud_rev": "federal_gov.revenue.total", "cur_bud_exp": "federal_gov.expenditure.opex",
           "dev_exp_gro_dev_exp": "federal_gov.expenditure.devex",
           "dev_exp_les_loa_rec": "federal_gov.expenditure.devex_loan_recovery",
           "dev_exp_net_dev_exp": "federal_gov.expenditure.devex_net"}
MOF_FED = {"revenue": "federal_gov.revenue.total", "operating_expenditure": "federal_gov.expenditure.opex",
           "development_expenditure_gross": "federal_gov.expenditure.devex",
           "development_expenditure_loan_recovery": "federal_gov.expenditure.devex_loan_recovery",
           "development_expenditure_net": "federal_gov.expenditure.devex_net",
           "covid19_fund": "federal_gov.expenditure.covid_fund", "overall_balance": "federal_gov.overall_balance"}


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
    for i, r in enumerate(rows(os.path.join(bnm_dir, "msb_3_1.csv")), start=2):
        if r["period"].strip():
            continue  # quarterly rows
        for col, ind in BNM_FED.items():
            v = dec(r[col])
            if v is None:
                continue
            obs.add(indicator_code=ind, geo_code="MY", period_code=r["year_dt"], entity_id="federal_gov:MY",
                    basis="actual", edition_id=f"bnm:msb_3_1@{d}", vintage=d, value=v * m, value_printed=r[col],
                    unit_printed="RM million", precision_printed="0.000000000001", estimate_method="accounting",
                    reliability="ok", file_id=vin["sha256"], table_ref="BNM MSB 3.1 Federal Government Finance",
                    l1_ref=f"sources/bnm/data/msb_3_1.csv#row{i}")
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
        v = dec(r["amount_rm_juta"])
        if line not in MOF_FED or r["basis"] != "official_actual" or v is None:
            continue
        sha = reg.get((str(r["edition"]), r["source_file"]))
        if not sha:
            sys.exit(f"MOF {r['edition']} {r['source_file']}: no sha256 in meta/registry_file.csv")
        obs.add(indicator_code=MOF_FED[line], geo_code="MY", period_code=str(year), entity_id="federal_gov:MY",
                basis="actual", edition_id=f"mof:tinjauan_fiskal@{r['edition']}", vintage=str(r["edition"]),
                value=v * m, value_printed=r["amount_rm_juta"], unit_printed="RM million", precision_printed="1",
                estimate_method="accounting", reliability="ok", file_id=sha, pdf_page=r["pdf_page"],
                printed_page=r["printed_page"], table_ref=f"Tinjauan Fiskal {r['edition']}, Jadual {r['table_no']}",
                l1_ref=r["_l1"])


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
             "and 600 DUN labels every year, the seat counts of the delineations used at GE14 (2018) and GE15 (2022); "
             "DOSM does not state the boundary set")
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
        if re.fullmatch(r"\d{4}", p):
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
    noprov = sum(1 for r in obs.rows if not r["file_id"] or not r["l1_ref"])
    add("C4 every row has provenance (file sha256 + L1 row)", "fact_observation", "PASS" if not noprov else "FAIL",
        f"{noprov} rows without")
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
    add("C8 value = value_printed x unit scale (sign kept, except spending levels and meta/sign_convention.csv)", "fact_observation",
        "PASS" if not bad else "FAIL", f"{n} rows checked" + (f"; {len(bad)} differ, e.g. {bad[:3]}" if bad else ""))
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
    build_federal_reported(obs)
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
