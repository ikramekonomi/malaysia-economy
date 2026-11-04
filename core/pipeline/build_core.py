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
    for i, r in enumerate(rows(os.path.join(DOSM, f"{dataset}.csv")), start=2):
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
                    table_ref=dataset, l1_ref=f"sources/dosm/data/{dataset}.csv#row{i}")


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


def build_states(obs):
    sha = {r["file_name"]: r["sha256"] for r in rows(os.path.join(META, "registry_file.csv"))}
    for i, r in enumerate(rows(STATES), start=2):
        if r["measure"] != "actual" or r["line_code"] not in STATE_LINES:
            continue
        # spending lines are levels (the panel stores them positive even where the statement prints them in
        # parentheses as a deduction); a surplus or deficit keeps the sign printed on the page
        v = dec(r["amount_rm"] if r["line_code"] == "surplus_deficit" else r["amount_rm_conformed"])
        if v is None:
            continue
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
    nounc = sum(1 for r in obs.rows if r["basis"] == "statistic" and not r["se"] and r["reliability"] != "unknown")
    add("C5 a survey estimate without published uncertainty says so (reliability = unknown)", "fact_observation",
        "PASS" if not nounc else "FAIL", f"{nounc} rows claim reliability without uncertainty")
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
            add("C6 state coverage", i, "PASS" if len(g) == 16 else "FAIL", f"{len(g)} of 16 states and territories")
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
        level = r["indicator_code"].startswith(("state_gov.expenditure.",))
        n += 1
        if (abs(got) != abs(want)) or (not level and got != want):
            bad.append(f"{r['indicator_code']} {r['geo_code']} {r['period_code']}: value {r['value']} vs printed "
                       f"{r['value_printed']} {r['unit_printed']}")
    add("C8 value = value_printed x unit scale (sign kept, except spending levels)", "fact_observation",
        "PASS" if not bad else "FAIL", f"{n} rows checked" + (f"; {len(bad)} differ, e.g. {bad[:3]}" if bad else ""))
    return out


def main():
    os.makedirs(CORE, exist_ok=True)
    ed = dosm_editions()
    obs = Obs()
    obs.districts = {}
    build_dosm(obs, ed)
    build_states(obs)
    build_federal(obs)
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
