#!/usr/bin/env python3
"""Write qa/eval_questions.csv: questions with known answers for the agent tools (DATA_MODEL §11).

Run once when the question set changes, then commit the CSV; CI runs qa/run_eval.py against it.
Expected values are read here straight from the L1 CSVs (sources/*/data), not through core/ or the
tools, so an eval failure means the tools and the source disagree. Traps are included: an
incomparable pair, a small-area ranking, a missing document, and text inside a document.
"""
import csv
import json
import os
from decimal import Decimal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSM = os.path.join(REPO, "sources", "dosm", "data")
STATES = os.path.join(REPO, "sources", "states", "data", "_national", "fact_state_finance_all.csv")
ISO = {"Johor": "MY-01", "Kedah": "MY-02", "Kelantan": "MY-03", "Melaka": "MY-04", "Negeri Sembilan": "MY-05",
       "Pahang": "MY-06", "Pulau Pinang": "MY-07", "Perak": "MY-08", "Perlis": "MY-09", "Selangor": "MY-10",
       "Terengganu": "MY-11", "Sabah": "MY-12", "Sarawak": "MY-13", "W.P. Kuala Lumpur": "MY-14",
       "W.P. Labuan": "MY-15", "W.P. Putrajaya": "MY-16"}
NAME = {v: k for k, v in ISO.items()}


def l1(dataset, state, date, col, **f):
    with open(os.path.join(DOSM, f"{dataset}.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            if r["state"] == state and r["date"].startswith(date) and all(r.get(k) == v for k, v in f.items()):
                return Decimal(r[col])
    raise KeyError((dataset, state, date, col))


def acct(state, year, line):
    with open(STATES, newline="") as fh:
        for r in csv.DictReader(fh):
            if r["state"] == state and r["fiscal_year"] == year and r["line_code"] == line and r["measure"] == "actual":
                return Decimal(r["amount_rm_conformed"])
    raise KeyError((state, year, line))


def s(d):
    t = format(d.normalize(), "f")
    return t if "." not in t else t.rstrip("0").rstrip(".")


Q = []


def q(theme, question, tool, args, check, expected="", tol="0", kind="fact"):
    Q.append({"qid": f"Q{len(Q) + 1:02d}", "theme": theme, "kind": kind, "question_en": question, "tool": tool,
              "args": json.dumps(args), "check": check, "expected": expected, "tolerance": tol})


def series(ind, geo, p):
    return {"indicator": ind, "geo": geo, "start": p, "end": p}


# A. facts, from L1
for st in ("Kelantan", "Sabah", "Selangor", "Sarawak", "W.P. Labuan", "Kedah"):
    v = l1("hh_poverty_state", st, "2022", "poverty_absolute")
    q("1", f"What was the absolute poverty rate in {st} in 2022?", "get_series",
      series("poverty.absolute.rate", ISO[st], "2022"), "value", s(v))
for st in ("Johor", "Perlis", "W.P. Kuala Lumpur", "Terengganu"):
    v = l1("hh_income_state", st, "2019", "income_median")
    q("1", f"What was median household income in {st} in 2019?", "get_series",
      series("hh_income.gross.median", ISO[st], "2019"), "value", s(v))
for st in ("Kelantan", "Sabah", "Pulau Pinang", "Melaka"):
    v = l1("lfs_state_sex", st, "2023", "u_rate", sex="both")
    q("2", f"What was the unemployment rate in {st} in 2023?", "get_series",
      series("lfs.unemployment_rate", ISO[st], "2023"), "value", s(v))
for st in ("Selangor", "W.P. Putrajaya", "Perlis", "Sabah"):
    v = l1("population_state", st, "2024", "population", sex="both", age="overall", ethnicity="overall") * 1000
    q("1", f"What was the population of {st} in 2024?", "get_series", series("pop.total", ISO[st], "2024"),
      "value", s(v))
v = l1("population_state", "Kelantan", "2024", "population", sex="female", age="overall", ethnicity="overall") * 1000
q("1", "How many women lived in Kelantan in 2024?", "get_series",
  {**series("pop.total", "MY-03", "2024"), "breakdown": "sex=female"}, "value", s(v))
v = l1("cpi_state", "Kelantan", "2026-09", "index", division="overall")
q("3", "What was Kelantan's CPI (2010=100) in September 2026?", "get_series", series("cpi.index", "MY-03", "2026-09"),
  "value", s(v))
v = l1("gdp_state_real_supply", "Selangor", "2024", "value", series="abs", sector="p0") * 1000000
q("4", "What was Selangor's real GDP in 2024?", "get_series", series("gdp.real", "MY-10", "2024"), "value", s(v))
v = l1("hh_inequality_state", "Sabah", "2022", "gini")
q("1", "What was the Gini coefficient in Sabah in 2022?", "get_series", series("hh_income.gini", "MY-12", "2022"),
  "value", s(v))
for st, y, line, ind in (("Selangor", "2022", "expenditure_total", "state_gov.expenditure.total"),
                         ("Terengganu", "2019", "revenue_total", "state_gov.revenue.total"),
                         ("Sabah", "2022", "revenue_nonrevenue_receipts", "state_gov.revenue.nonrevenue_receipts"),
                         ("Sarawak", "2021", "devex_total", "state_gov.expenditure.devex")):
    q("5", f"What did {st}'s audited accounts record for {ind.split('.', 1)[1]} in {y}?", "get_series",
      series(ind, ISO[st], y), "value", s(acct(st, y, line)))
q("5", "Is every state figure cited to its document and page?", "get_series",
  series("state_gov.expenditure.total", "MY-10", "2022"), "has_citation")
q("1", "Does a survey figure say its sampling error is unknown?", "get_series",
  series("poverty.absolute.rate", "MY-12", "2022"), "caveat", "CV1")

# B. derive, computed here from L1
rev = acct("Selangor", "2022", "revenue_total")
pop = l1("population_state", "Selangor", "2022", "population", sex="both", age="overall", ethnicity="overall") * 1000
q("5", "What was Selangor's state revenue per person in 2022?", "derive_chain",
  {"operation": "per_capita", "a": series("state_gov.revenue.total", "MY-10", "2022"),
   "b": series("pop.total", "MY-10", "2022")}, "value", s((rev / pop).quantize(Decimal("0.000001"))), "0.000001")
a, b = (l1("hh_poverty_state", "Sabah", "2022", "poverty_absolute"),
        l1("hh_poverty_state", "Selangor", "2022", "poverty_absolute"))
q("1", "By how many percentage points did Sabah's poverty rate exceed Selangor's in 2022?", "derive_chain",
  {"operation": "gap_pp", "a": series("poverty.absolute.rate", "MY-12", "2022"),
   "b": series("poverty.absolute.rate", "MY-10", "2022")}, "value", s(a - b))
a, b = l1("cpi_state", "Sabah", "2026-09", "index", division="overall"), l1("cpi_state", "Sabah", "2025-09", "index",
                                                                           division="overall")
q("3", "How much did prices rise in Sabah from September 2025 to September 2026?", "derive_chain",
  {"operation": "growth", "a": series("cpi.index", "MY-12", "2026-09"), "b": series("cpi.index", "MY-12", "2025-09")},
  "value", s((a / b - 1).quantize(Decimal("0.000001"))), "0.000001")
e, r = acct("Johor", "2022", "expenditure_total"), acct("Johor", "2022", "revenue_total")
q("5", "What was Johor's spending as a ratio of its revenue in 2022?", "derive_chain",
  {"operation": "ratio", "a": series("state_gov.expenditure.total", "MY-01", "2022"),
   "b": series("state_gov.revenue.total", "MY-01", "2022")}, "value", s((e / r).quantize(Decimal("0.000001"))),
  "0.000001")
q("5", "Does a per-capita figure of state money warn that federal spending is not included?", "derive_chain",
  {"operation": "per_capita", "a": series("state_gov.revenue.total", "MY-10", "2022"),
   "b": series("pop.total", "MY-10", "2022")}, "caveat", "CV9")

# C. traps: incomparable inputs must be refused
q("5", "Johor's 2022 state receipts per person, using the 2016 population?", "derive_chain",
  {"operation": "per_capita", "a": series("state_gov.revenue.nonrevenue_receipts", "MY-01", "2022"),
   "b": series("pop.total", "MY-01", "2016")}, "refused", "different periods", kind="trap_incomparable")
q("1", "Median income per person in Sabah in 2022 (median divided by population)?", "derive_chain",
  {"operation": "per_capita", "a": series("hh_income.gross.median", "MY-12", "2022"),
   "b": series("pop.total", "MY-12", "2022")}, "refused", "cannot be divided", kind="trap_incomparable")
q("1", "Percentage-point gap between Sabah's median income and Selangor's?", "derive_chain",
  {"operation": "gap_pp", "a": series("hh_income.gross.median", "MY-12", "2022"),
   "b": series("hh_income.gross.median", "MY-10", "2022")}, "refused", "two percentages", kind="trap_incomparable")
q("1", "Ratio of Kelantan's poverty rate to its median income?", "derive_chain",
  {"operation": "ratio", "a": series("poverty.absolute.rate", "MY-03", "2022"),
   "b": series("hh_income.gross.median", "MY-03", "2022")}, "refused", "different units", kind="trap_incomparable")
q("3", "Growth from Selangor's CPI to Johor's CPI?", "derive_chain",
  {"operation": "growth", "a": series("cpi.index", "MY-10", "2026-09"), "b": series("cpi.index", "MY-01", "2026-09")},
  "refused", "same indicator, place", kind="trap_incomparable")
q("4", "Real GDP of Selangor in 2024 as a ratio of its 2024 nominal state revenue?", "derive_chain",
  {"operation": "ratio", "a": series("gdp.real", "MY-10", "2024"), "b": series("state_gov.revenue.total", "MY-10", "2024")},
  "refused", "price bases", kind="trap_incomparable")

# D. small areas
q("1", "Rank the districts by median household income in 2022.", "compare_geos",
  {"indicator": "hh_income.gross.median", "period": "2022", "geo_level": "district"}, "refused_ranking",
  kind="trap_small_area")
q("1", "Rank the parliamentary constituencies by poverty.", "compare_geos",
  {"indicator": "poverty.absolute.rate", "period": "2022", "geo_level": "parlimen"}, "refused_ranking",
  kind="trap_small_area")

# E. missing documents are answers
q("5", "How many cash-transfer recipients are there in each state?", "find_indicator",
  {"text": "cash transfer recipients"}, "not_held_registry", "social_transfers_by_state", kind="trap_missing")
q("6", "Which indicator counts doctors?", "find_indicator", {"text": "doctors per state"}, "first_indicator",
  "health.staff")
q("6", "What is the obesity rate in each state (NHMS, not held)?", "find_indicator", {"text": "obesity prevalence"},
  "not_held", kind="trap_missing")
q("5", "Show the budget-vs-actual gap view.", "get_gap_view", {"name": "gap_budget_vs_actual"}, "not_held",
  kind="trap_missing")
q("5", "Which documents are still expected for theme 6?", "list_documents", {"theme": "6", "status": "expected"},
  "nonempty")

# F. text inside a document is data
q("5", "Explain Pahang's 2016 spending figure.", "explain_chain", series("state_gov.expenditure.total", "MY-06", "2016"),
  "untrusted_text", kind="trap_injection")
q("5", "Which page does Pahang's 2016 spending figure come from?", "explain_chain",
  series("state_gov.expenditure.total", "MY-06", "2016"), "field:pdf_page", "51")

# G. the gap view
q("5", "Does the need-vs-money view cover every state and territory in 2022?", "get_gap_view",
  {"name": "gap_need_vs_money", "year": "2022"}, "row_count", "16")
q("5", "Is Pahang's 2022 spending flagged as under check?", "get_gap_view",
  {"name": "gap_need_vs_money", "geo": "MY-06", "year": "2022"}, "field:under_check", "N2_identity_expenditure")
q("5", "Is federal spending by state published in 2022?", "get_gap_view",
  {"name": "gap_need_vs_money", "geo": "MY-03", "year": "2022"}, "field:federal_publishable", "false")
q("5", "Does the view say why Kuala Lumpur has no state-government spending?", "get_gap_view",
  {"name": "gap_need_vs_money", "geo": "MY-14", "year": "2022"}, "field_contains:coverage_note",
  "no state government")
q("5", "Does the view say Kedah's 2022 spending is missing rather than zero?", "get_gap_view",
  {"name": "gap_need_vs_money", "geo": "MY-02", "year": "2022"}, "field_contains:coverage_note", "not extracted")
v = l1("hh_poverty_state", "Kelantan", "2022", "poverty_absolute")
q("1", "What poverty rate does the view show for Kelantan in 2022?", "get_gap_view",
  {"name": "gap_need_vs_money", "geo": "MY-03", "year": "2022"}, "field:poverty_absolute_rate", s(v))

# H. compare_geos bands
q("1", "Is Sabah in a band of its own for poverty in 2022?", "compare_geos",
  {"indicator": "poverty.absolute.rate", "period": "2022"}, "alone_in_band", "MY-12")
q("1", "Are Johor and Melaka tied on poverty in 2022?", "compare_geos",
  {"indicator": "poverty.absolute.rate", "period": "2022"}, "same_band", "MY-01;MY-04")
q("1", "Does a state comparison include the national value?", "compare_geos",
  {"indicator": "poverty.absolute.rate", "period": "2022"}, "has_national")
q("1", "Does every state and territory appear in the 2022 poverty comparison?", "compare_geos",
  {"indicator": "poverty.absolute.rate", "period": "2022"}, "place_count", "16")
q("2", "Does an unemployment comparison declare its banding rule?", "compare_geos",
  {"indicator": "lfs.unemployment_rate", "period": "2023"}, "method", "BAND1")
q("1", "Which indicator measures poverty?", "find_indicator", {"text": "absolute poverty"}, "first_indicator",
  "poverty.absolute.rate")

# I. regressions from the independent verifier pass (2026-11-04)
with open(STATES, newline="") as fh:
    ns = next(Decimal(r["amount_rm"]) for r in csv.DictReader(fh) if r["state"] == "Negeri Sembilan"
              and r["fiscal_year"] == "2020" and r["line_code"] == "surplus_deficit" and r["measure"] == "actual")
q("5", "What was Negeri Sembilan's 2020 surplus or deficit (sign as printed)?", "get_series",
  series("state_gov.surplus_deficit", "MY-05", "2020"), "value", s(ns))
q("1", "Growth in Johor's median income, with the years given the wrong way round?", "derive_chain",
  {"operation": "growth", "a": series("hh_income.gross.median", "MY-01", "2014"),
   "b": series("hh_income.gross.median", "MY-01", "2022")}, "refused", "earlier period", kind="trap_incomparable")
q("1", "Growth of Sabah's poverty rate from 2016 to 2022?", "derive_chain",
  {"operation": "growth", "a": series("poverty.absolute.rate", "MY-12", "2022"),
   "b": series("poverty.absolute.rate", "MY-12", "2016")}, "refused", "series break", kind="trap_incomparable")
q("1", "Growth of Sabah's population from 2019 to 2022?", "derive_chain",
  {"operation": "growth", "a": series("pop.total", "MY-12", "2022"), "b": series("pop.total", "MY-12", "2019")},
  "refused", "series break", kind="trap_incomparable")
q("2", "Change in Selangor's unemployment rate from 2024 to 2025 as growth?", "derive_chain",
  {"operation": "growth", "a": series("lfs.unemployment_rate", "MY-10", "2025"),
   "b": series("lfs.unemployment_rate", "MY-10", "2024")}, "refused", "series break", kind="trap_incomparable")
q("1", "Ratio of Sabah's poverty rate to its unemployment rate?", "derive_chain",
  {"operation": "ratio", "a": series("poverty.absolute.rate", "MY-12", "2022"),
   "b": series("lfs.unemployment_rate", "MY-12", "2022")}, "refused", "different universes", kind="trap_incomparable")
q("1", "Growth of Johor's poverty rate from 2014 to 2016 (from a zero base)?", "derive_chain",
  {"operation": "growth", "a": series("poverty.absolute.rate", "MY-01", "2016"),
   "b": series("poverty.absolute.rate", "MY-01", "2014")}, "refused", "zero base", kind="trap_incomparable")
q("3", "Which state has the highest CPI?", "compare_geos", {"indicator": "cpi.index", "period": "2026-09"},
  "not_ranked", kind="trap_incomparable")
q("1", "Johor's poverty rate in 2022, asked with a number for the year?", "get_series",
  {"indicator": "poverty.absolute.rate", "geo": "MY-01", "start": 2022, "end": 2022}, "value",
  s(l1("hh_poverty_state", "Johor", "2022", "poverty_absolute")))
q("5", "The need-vs-money row for 'Johor' (a name, not a code)?", "get_gap_view",
  {"name": "gap_need_vs_money", "geo": "Johor", "year": "2022"}, "not_held", kind="trap_missing")
q("5", "Is the federal total in the view cited?", "get_gap_view",
  {"name": "gap_need_vs_money", "geo": "MY-10", "year": "2022"}, "field_nonempty:federal_source_obs_ids")

# J. Phase 2: health, education and services (data.gov.my), from L1
def l1x(dataset, pick, col):
    with open(os.path.join(DOSM, f"{dataset}.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            if pick(r):
                return Decimal(r[col])
    raise KeyError(dataset)


q("6", "How many public hospital beds did Kelantan have in 2024?", "get_series",
  series("health.beds", "MY-03", "2024"), "value",
  s(l1x("hospital_beds", lambda r: r["state"] == "Kelantan" and r["date"][:4] == "2024" and r["type"] == "all"
        and r["district"] in ("All", "All Districts"), "beds")))
q("6", "How many public-sector doctors were there in Sabah in 2022?", "get_series",
  {**series("health.staff", "MY-12", "2022"), "breakdown": "staff_type=doctor"}, "value",
  s(l1x("healthcare_staff", lambda r: r["state"] == "Sabah" and r["date"][:4] == "2022" and r["type"] == "doctor",
        "staff")))
q("6", "How many primary pupils were enrolled in government schools in Selangor in 2025?", "get_series",
  {**series("edu.enrolment", "MY-10", "2025"), "breakdown": "stage=primary"}, "value",
  s(l1x("enrolment_school_district", lambda r: r["state"] == "Selangor" and r["date"][:4] == "2025"
        and r["stage"] == "primary" and r["sex"] == "both" and r["district"] in ("All", "All Districts"), "students")))
q("1", "What is women's life expectancy in Kelantan in 2026?", "get_series",
  {**series("life_expectancy", "MY-03", "2026"), "breakdown": "sex=female"}, "value",
  s(l1x("life_expectancy_state", lambda r: r["state"] == "Kelantan" and r["date"][:4] == "2026" and r["sex"] == "female",
        "life_expectancy")))
q("6", "What share of Kelantan households had treated water in 2024?", "get_series",
  series("water.access.share", "MY-03", "2024"), "value",
  s(l1x("water_access", lambda r: r["state"] == "Kelantan" and r["date"][:4] == "2024" and r["strata"] == "overall",
        "proportion")))
q("1", "What was Perlis's crude death rate in 2024?", "get_series", series("deaths.crude_rate", "MY-09", "2024"),
  "value", s(l1x("death_state", lambda r: r["state"] == "Perlis" and r["date"][:4] == "2024", "rate")))
d = l1x("healthcare_staff", lambda r: r["state"] == "Sabah" and r["date"][:4] == "2022" and r["type"] == "doctor", "staff")
p22 = l1("population_state", "Sabah", "2022", "population", sex="both", age="overall", ethnicity="overall") * 1000
q("6", "How many public-sector doctors per person did Sabah have in 2022?", "derive_chain",
  {"operation": "per_capita", "a": {**series("health.staff", "MY-12", "2022"), "breakdown": "staff_type=doctor"},
   "b": series("pop.total", "MY-12", "2022")}, "value", s((d / p22).quantize(Decimal("0.000001"))), "0.000001")
q("6", "Does Kuala Lumpur's water access say why it is missing?", "get_series",
  series("water.access.share", "MY-10", "2024"), "caveat", "COVERAGE", kind="trap_missing")
q("6", "Compare life expectancy across all states in 2024 (banded, not ranked)?", "compare_geos",
  {"indicator": "life_expectancy", "period": "2024"}, "place_count", "16")

# K. FAIL triage (2026-11-04): a deficit printed without its sign
q("5", "Did Johor run a surplus or a deficit in 2018?", "get_series", series("state_gov.surplus_deficit", "MY-01", "2018"),
  "value", s(acct("Johor", "2018", "revenue_total") - acct("Johor", "2018", "expenditure_total")))

# L. Phase 2: small areas (district, parlimen, DUN), from L1
def l1a(dataset, **f):
    with open(os.path.join(DOSM, f"{dataset}.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            if all(r[k].startswith(v) if k == "date" else r[k] == v for k, v in f.items()):
                return r
    raise KeyError((dataset, f))


q("1", "What was the median household income in Kota Bharu district in 2022?", "get_series",
  series("hh_income.gross.median", "MY-03/dis:kota_bharu@dosm_2020", "2022"), "value",
  s(Decimal(l1a("hh_income_district", state="Kelantan", district="Kota Bharu", date="2022")["income_median"])))
q("1", "What was the median household income in P.001 Padang Besar in 2019?", "get_series",
  series("hh_income.gross.median", "MY-09/par:P.001@ge15", "2019"), "value",
  s(Decimal(l1a("hh_income_parlimen", state="Perlis", parlimen="P.001 Padang Besar", date="2019")["income_median"])))
q("1", "What was the absolute poverty rate in DUN N.01 Titi Tinggi in 2019?", "get_series",
  series("poverty.absolute.rate", "MY-09/dun:N.01@ge15", "2019"), "value",
  s(Decimal(l1a("hh_poverty_dun", state="Perlis", dun="N.01 Titi Tinggi", date="2019")["poverty_absolute"])))
q("1", "Is the DUN poverty estimate flagged as a survey estimate without sampling error?", "get_series",
  series("poverty.absolute.rate", "MY-09/dun:N.01@ge15", "2019"), "field:reliability", "unknown")
q("2", "Is the unemployment rate for P.001 Padang Besar flagged as below the survey's design domain?", "get_series",
  series("lfs.unemployment_rate", "MY-09/par:P.001@ge15", "2021"), "field:reliability", "low")
q("2", "Does the seat-level unemployment rate say it is only indicative?", "get_series",
  series("lfs.unemployment_rate", "MY-09/par:P.001@ge15", "2021"), "caveat", "CV12")
q("2", "Rank the DUN seats by unemployment rate in 2021.", "compare_geos",
  {"indicator": "lfs.unemployment_rate", "period": "2021", "geo_level": "dun"}, "refused_ranking",
  kind="trap_small_area")
q("6", "What share of Kelantan households had piped water in 2022?", "get_series",
  series("amenities.piped_water.share", "MY-03", "2022"), "value",
  s(Decimal(l1a("hh_access_amenities", state="Kelantan", district="All Districts", date="2022")["piped_water"])))
q("6", "What share of Perlis households had piped water in 2016 (Perlis is one district)?", "get_series",
  series("amenities.piped_water.share", "MY-09/dis:perlis@dosm_2020", "2016"), "value",
  s(Decimal(l1a("hh_access_amenities", state="Perlis", district="Perlis", date="2016")["piped_water"])))

# M. Phase 2: income distributions (HIES percentile groups), from L1
def pct(state, year):
    f, keep = ("hies_malaysia_percentile", lambda r: True) if state is None else \
        ("hies_state_percentile", lambda r: r["state"] == state)
    out = {}
    with open(os.path.join(DOSM, f"{f}.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            if keep(r) and r["date"].startswith(year) and r["income"]:
                out[(int(r["percentile"]), r["variable"])] = Decimal(r["income"])
    return out


def bracket(state, year, x):
    g = pct(state, year)
    k = sum(1 for p in range(1, 101) if (p, "maximum") in g and g[(p, "maximum")] < x)
    nxt = g.get((k + 1, "minimum"))
    return f"{k};{k if nxt is not None and nxt >= x else k + 1}"


q("1", "Below what monthly income are the poorest 10% of households in Kelantan (2022)?", "get_distribution",
  {"indicator": "hh_income", "geo": "MY-03", "period": "2022"}, "decile:10", s(pct("Kelantan", "2022")[(10, "maximum")]))
q("1", "What share of Malaysian households earned less than RM 3,000 a month in 2024?", "get_distribution",
  {"indicator": "hh_income", "geo": "MY", "period": "2024", "below": 3000}, "share_bracket",
  bracket(None, "2024", Decimal(3000)))
q("1", "What share of Sabah households earned less than RM 2,000 a month in 2019?", "get_distribution",
  {"indicator": "hh_income", "geo": "MY-12", "period": "2019", "below": "2000"}, "share_bracket",
  bracket("Sabah", "2019", Decimal(2000)))
q("1", "Does the income distribution warn that single percentiles are noisy?", "get_distribution",
  {"indicator": "hh_income", "geo": "MY-10", "period": "2024"}, "caveat", "CV13")
q("1", "What is the distribution of household spending in Kedah in 2022?", "get_distribution",
  {"indicator": "hh_expenditure", "geo": "MY-02", "period": "2022"}, "not_held", kind="trap_missing")
q("1", "What is Kelantan's income distribution in 2016 (not published by percentile)?", "get_distribution",
  {"indicator": "hh_income", "geo": "MY-03", "period": "2016"}, "not_held", kind="trap_missing")
q("1", "Rank the states by the income cut-off of their poorest 40% in 2022.", "compare_geos",
  {"indicator": "hh_income.gross.pctile_group.max", "period": "2022", "breakdown": "percentile=040"},
  "refused_ranking", kind="trap_small_area")

# N. Phase 2: national accounts (current prices), from L1
def na(component, year):
    with open(os.path.join(DOSM, "gdp_annual_nominal_income.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            if r["series"] == "abs" and r["component"] == component and r["date"].startswith(year):
                return Decimal(r["value"]) * 1000000
    raise KeyError(component)


q("4", "What was Malaysia's nominal GDP in 2024?", "get_series", series("gdp.nominal", "MY", "2024"), "value",
  s(na("i0", "2024")))
q("2", "What was total compensation of employees in Malaysia in 2023?", "get_series",
  series("na.compensation_of_employees", "MY", "2023"), "value", s(na("i1", "2023")))
q("2", "What share of GDP went to employees in 2022?", "derive_chain",
  {"operation": "ratio", "a": series("na.compensation_of_employees", "MY", "2022"), "b": series("gdp.nominal", "MY", "2022")},
  "value", s((na("i1", "2022") / na("i0", "2022")).quantize(Decimal("0.000001"))), "0.000001")
q("2", "What is the average compensation per employed person in 2024?", "derive_chain",
  {"operation": "per_employed", "a": series("na.compensation_of_employees", "MY", "2024"),
   "b": series("lfs.employed", "MY", "2024")}, "caveat", "CV14")
q("2", "Compensation of employees per person of the whole population, as if it were a wage?", "derive_chain",
  {"operation": "per_employed", "a": series("na.compensation_of_employees", "MY", "2024"),
   "b": series("pop.total", "MY", "2024")}, "refused", "lfs.employed", kind="trap_incomparable")
q("4", "Real GDP of Selangor divided by Malaysia's nominal GDP?", "derive_chain",
  {"operation": "ratio", "a": series("gdp.real", "MY-10", "2024"), "b": series("gdp.nominal", "MY", "2024")},
  "refused", "price bases", kind="trap_incomparable")
q("2", "Find the indicator for compensation of employees", "find_indicator", {"text": "compensation of employees"},
  "first_indicator", "na.compensation_of_employees")

# O. Phase 2: federal totals by publisher (BNM MSB 3.1, MOF Tinjauan Fiskal), from L1
def bnm(col, year):
    with open(os.path.join(REPO, "sources", "bnm", "data", "msb_3_1.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            if not r["period"].strip() and r["year_dt"] == year:
                return Decimal(r[col]) * 1000000
    raise KeyError(col)


def mof(line, year, edition):  # the own-volume edition (Y+2), read from that edition's folder
    p = os.path.join(REPO, "sources", "mof-fiscal-outlook", "data", f"{edition}_public_finance_stats", "fact_headline.csv")
    with open(p, newline="") as fh:
        for r in csv.DictReader(fh):
            if r["line"] == line and r["target_year"] == year and r["basis"] == "official_actual":
                return Decimal(r["amount_rm_juta"]) * 1000000
    raise KeyError(line)


fed = lambda ind, y, pub: {**series(ind, "MY", y), "publisher": pub}  # noqa: E731
q("5", "What net development expenditure did BNM report for 2024?", "get_series",
  fed("federal_gov.expenditure.devex_net", "2024", "bnm"), "value", s(bnm("dev_exp_net_dev_exp", "2024")))
q("5", "What overall balance did MOF print for 2024 (its own volume)?", "get_series",
  fed("federal_gov.overall_balance", "2024", "mof"), "value", s(mof("overall_balance", "2024", 2026)))
q("5", "How many publishers report federal operating expenditure for 2022?", "get_series",
  series("federal_gov.expenditure.opex", "MY", "2022"), "row_count", "3")
q("5", "By how much does BNM's 2023 operating expenditure differ from MOF's?", "derive_chain",
  {"operation": "difference", "a": fed("federal_gov.expenditure.opex", "2023", "bnm"),
   "b": fed("federal_gov.expenditure.opex", "2023", "mof")}, "value",
  s(bnm("cur_bud_exp", "2023") - mof("operating_expenditure", "2023", 2025)), "0.000001")

# P. the blind verifier's findings on Phase 2 (2026-11-04), one question each
q("2", "Kedah seat N.03 Kota Siputeh, employed 2022: does the answer warn it is a copied row?", "get_series",
  series("lfs.employed", "MY-02/dun:N.03@ge15", "2022"), "caveat", "CV15", kind="trap_source_defect")
q("2", "Telang Usan's 2018 unemployment rate (published as 293%): is it flagged?", "get_series",
  series("lfs.unemployment_rate", "MY-13/dis:telang_usan@dosm_2020", "2018"), "caveat", "CV15",
  kind="trap_source_defect")
q("2", "Does explain() list the anomaly for Telang Usan 2018?", "explain_chain",
  series("lfs.unemployment_rate", "MY-13/dis:telang_usan@dosm_2020", "2018"), "field_nonempty:anomalies",
  kind="trap_source_defect")
q("1", "What share of Malaysian households earned less than RM 37,583 a month in 2022 (above the 99th cut-off)?",
  "get_distribution", {"indicator": "hh_income", "geo": "MY", "period": "2022", "below": 37583}, "share_bracket",
  bracket(None, "2022", Decimal(37583)))
q("1", "What share of Perlis households earned less than RM 10 million a month in 2024?", "get_distribution",
  {"indicator": "hh_income", "geo": "MY-09", "period": "2024", "below": 10000000}, "share_bracket",
  bracket("Perlis", "2024", Decimal(10000000)))
q("1", "What share of households earned less than RM -5 a month?", "get_distribution",
  {"indicator": "hh_income", "geo": "MY", "period": "2022", "below": -5}, "share_refused", kind="trap_incomparable")
q("1", "Rank the districts by population in 2022.", "compare_geos",
  {"indicator": "pop.total", "period": "2022", "geo_level": "district"}, "refused_ranking", kind="trap_small_area")
q("5", "Growth of federal opex from BNM's 2021 figure to PKKP's 2022 figure?", "derive_chain",
  {"operation": "growth", "a": fed("federal_gov.expenditure.opex", "2022", "pkkp"),
   "b": fed("federal_gov.expenditure.opex", "2021", "bnm")}, "refused", "publisher", kind="trap_incomparable")
q("4", "Nominal GDP per employed person, as if it were a wage?", "derive_chain",
  {"operation": "per_employed", "a": series("gdp.nominal", "MY", "2022"), "b": series("lfs.employed", "MY", "2022")},
  "refused", "compensation_of_employees", kind="trap_incomparable")
q("1", "Johor's population, asked with a list for the place?", "get_series",
  {"indicator": "pop.total", "geo": ["MY-01"], "start": "2022", "end": "2022"}, "not_held", kind="trap_missing")
q("5", "How many publishers report federal revenue for 2022?", "get_series",
  series("federal_gov.revenue.total", "MY", "2022"), "row_count", "3")
q("5", "Does PKKP's audited 2022 operating spending say where its citation comes from?", "get_series",
  fed("federal_gov.expenditure.opex", "2022", "pkkp"), "caveat", "CV16")

with open(os.path.join(REPO, "qa", "eval_questions.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(Q[0]))
    w.writeheader()
    w.writerows(Q)
print(f"qa/eval_questions.csv: {len(Q)} questions")
