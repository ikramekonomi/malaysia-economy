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
q("5", "How much did Pahang spend on water supply in 2022 (its third spending head)?", "get_series",
  series("state_gov.expenditure.water_supply", "MY-06", "2022"), "value", s(acct("Pahang", "2022", "expenditure_water_supply")))
q("5", "Is Pahang's 2022 spending still under check now that its water-supply head is extracted?", "get_gap_view",
  {"name": "gap_need_vs_money", "geo": "MY-06", "year": "2022"}, "field:under_check", "")
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
def perf(year, line, col):
    for r in csv.DictReader(open(os.path.join(REPO, "sources", "pkkp", "data", str(year),
                                              "fact_financial_performance.csv"))):
        if r["line_code"] == line and r["basis"] == "sebenar" and r["source_file"].startswith(str(year)):
            return r[col]
    raise LookupError(f"fact_financial_performance {year} {line}")


q("5", "On which PDF page of its own volume is PKKP's audited 2022 operating spending printed?", "get_series",
  fed("federal_gov.expenditure.opex", "2022", "pkkp"), "field:pdf_page", perf(2022, "opex", "pdf_page"))
q("5", "What was PKKP's audited 2022 operating spending (Penyata Prestasi Kewangan, own volume)?", "get_series",
  fed("federal_gov.expenditure.opex", "2022", "pkkp"), "value", s(Decimal(perf(2022, "opex", "amount_rm"))))
q("5", "How much revenue surplus was transferred to the Development Fund in 2024?", "get_series",
  {**series("federal_gov.expenditure.transfer_development_fund", "MY", "2024"), "publisher": "pkkp"}, "value",
  s(Decimal(next(r["sebenar_rm"] for r in csv.DictReader(open(os.path.join(REPO, "sources", "pkkp", "data", "2024",
     "fact_revenue_account_statement.csv"))) if r["line_item_bm"] == "Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan"
     and r["source_file"].startswith("2024")))))

q("5", "Does PKKP's 2020 revenue say its PDF is not archived (decision D24)?", "get_series",
  fed("federal_gov.revenue.total", "2020", "pkkp"), "caveat", "CV17", kind="trap_missing")

q("5", "What was Pahang's total public debt at the end of 2020 (JUMLAH HUTANG AWAM, not the federal-loan subtotal)?",
  "get_series", series("state_gov.debt.total", "MY-06", "2020"), "value", s(acct("Pahang", "2020", "debt_total")))

# Q. Phase 2: national monthly series (DOSM CPI and trade; BNM money and credit), from L1
def cpi_my(date, division="overall"):
    return l1x("cpi_headline", lambda r: r["date"].startswith(date) and r["division"] == division, "index")


def trade(date, col):
    return l1x("trade_headline", lambda r: r["series"] == "abs" and r["date"].startswith(date), col)


def msb(table, year, month, col, **f):
    with open(os.path.join(REPO, "sources", "bnm", "data", f"{table}.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            if r["year_dt"] == year and r["month_dt"] == month and all(r[k] == v for k, v in f.items()):
                return Decimal(r[col]) * 1000000
    raise KeyError((table, year, month, col))


q("3", "What was Malaysia's CPI (2010=100) in September 2026?", "get_series", series("cpi.index", "MY", "2026-09"),
  "value", s(cpi_my("2026-09")))
q("3", "What was Malaysia's food and non-alcoholic beverages CPI (COICOP 01) in September 2026?", "get_series",
  {**series("cpi.index", "MY", "2026-09"), "breakdown": "coicop=01"}, "value", s(cpi_my("2026-09", "01")))
q("3", "What was Malaysia's CPI in January 1980 (the start of DOSM's national series)?", "get_series",
  series("cpi.index", "MY", "1980-01"), "value", s(cpi_my("1980-01")))
a, b = cpi_my("2026-09"), cpi_my("2025-09")
q("3", "How much did prices rise in Malaysia from September 2025 to September 2026?", "derive_chain",
  {"operation": "growth", "a": series("cpi.index", "MY", "2026-09"), "b": series("cpi.index", "MY", "2025-09")},
  "value", s((a / b - 1).quantize(Decimal("0.000001"))), "0.000001")
q("3", "Is Malaysia's CPI for COICOP 12 held for 2005 (DOSM prints that division from 2010 only)?", "get_series",
  {**series("cpi.index", "MY", "2005-06"), "breakdown": "coicop=12"}, "not_held", kind="trap_missing")
q("3", "Does the national CPI warn that its level does not compare places?", "get_series",
  series("cpi.index", "MY", "2026-09"), "caveat", "CV8")
q("4", "What were Malaysia's exports of goods in September 2026?", "get_series", series("trade.exports", "MY", "2026-09"),
  "value", s(trade("2026-09", "exports")))
q("4", "What were Malaysia's imports of goods in September 2026?", "get_series", series("trade.imports", "MY", "2026-09"),
  "value", s(trade("2026-09", "imports")))
q("4", "What was Malaysia's trade balance in April 1991 (a deficit, sign as published)?", "get_series",
  series("trade.balance", "MY", "1991-04"), "value", s(trade("1991-04", "balance")))
q("4", "Does a trade figure warn that recent months are revised?", "get_series",
  series("trade.exports", "MY", "2026-09"), "caveat", "CV19")
q("8", "What was M1 in May 2026?", "get_series", series("money.m1", "MY", "2026-05"), "value",
  s(msb("msb_1_3", "2026", "5", "m_one_tot")))
q("8", "What was M2 in December 2019?", "get_series", series("money.m2", "MY", "2019-12"), "value",
  s(msb("msb_1_3", "2019", "12", "m_two_tot")))
q("8", "What was broad money M3 in January 2013?", "get_series", series("money.m3", "MY", "2013-01"), "value",
  s(msb("msb_1_3", "2013", "1", "m_thr_tot")))
a, b = msb("msb_1_3", "2026", "5", "m_thr_tot"), msb("msb_1_3", "2025", "5", "m_thr_tot")
q("8", "How fast did M3 grow from May 2025 to May 2026?", "derive_chain",
  {"operation": "growth", "a": series("money.m3", "MY", "2026-05"), "b": series("money.m3", "MY", "2025-05")},
  "value", s((a / b - 1).quantize(Decimal("0.000001"))), "0.000001")
q("8", "What were total banking-system loans/financing in May 2026?", "get_series",
  series("credit.loans.banking_system", "MY", "2026-05"), "value",
  s(msb("msb_1_18", "2026", "5", "tot_fin", type="Jumlah/Total")))
q("8", "What were Islamic banks' loans/financing in December 2025?", "get_series",
  {**series("credit.loans.banking_system", "MY", "2025-12"), "breakdown": "bank_type=islamic"}, "value",
  s(msb("msb_1_18", "2025", "12", "tot_fin", type="Bank-bank Islam / Islamic Banks")))
q("8", "Does the loans figure warn that it is not BNM's balance-sheet loans and advances?", "get_series",
  series("credit.loans.banking_system", "MY", "2026-05"), "caveat", "CV20")
q("8", "What was the overnight policy rate in 2024 (BNM MSB 2.3 not loaded)?", "find_indicator",
  {"text": "overnight policy rate"}, "not_held", kind="trap_missing")
# traps: a CPI level is not a price level, so it compares no places; a month is not a year
q("3", "Is Selangor dearer than Malaysia (Selangor's CPI divided by Malaysia's)?", "derive_chain",
  {"operation": "ratio", "a": series("cpi.index", "MY-10", "2026-09"), "b": series("cpi.index", "MY", "2026-09")},
  "refused", "do not compare places", kind="trap_incomparable")
q("3", "By how many index points is Kuala Lumpur's CPI above Sabah's?", "derive_chain",
  {"operation": "difference", "a": series("cpi.index", "MY-14", "2026-09"), "b": series("cpi.index", "MY-12", "2026-09")},
  "refused", "do not compare places", kind="trap_incomparable")
q("3", "Growth from Malaysia's CPI in 2025-09 to Selangor's in 2026-09?", "derive_chain",
  {"operation": "growth", "a": series("cpi.index", "MY-10", "2026-09"), "b": series("cpi.index", "MY", "2025-09")},
  "refused", "same indicator, place", kind="trap_incomparable")
q("4", "Exports as a share of GDP, using December 2025 exports and 2025 GDP?", "derive_chain",
  {"operation": "ratio", "a": series("trade.exports", "MY", "2025-12"), "b": series("gdp.nominal", "MY", "2025")},
  "refused", "different periods", kind="trap_incomparable")
q("8", "M3 growth from 2026-05 back to 2025-05, with the months given the wrong way round?", "derive_chain",
  {"operation": "growth", "a": series("money.m3", "MY", "2025-05"), "b": series("money.m3", "MY", "2026-05")},
  "refused", "earlier period", kind="trap_incomparable")

# ---------------------------------------------------------------- Phase 3: the entity spine
# expected names come from PKKP's own dim_maksud (L1), never from meta/entity_register.csv
def pkkp_name(code, year):
    for r in csv.DictReader(open(os.path.join(REPO, "sources", "pkkp", "data", str(year), "dim_maksud.csv"))):
        if r["maksud_code"] == code:
            return r["name_bm"]
    raise LookupError(f"{code} not printed in PKKP FY{year}")


def ent(code, year=None):
    return {"code": code, "year": year} if year is not None else {"code": code}


q("5", "Which body was supply vote B.45 in 2024?", "get_entity", ent("B.45", 2024), "printed_name",
  pkkp_name("B.45", 2024))
q("5", "Which ministry held vote B.23 in 2019 (portfolio reshuffled since 2009)?", "get_entity", ent("B.23", 2019),
  "printed_name", pkkp_name("B.23", 2019))
q("5", "Is vote B.41 in 2013 the same body as vote B.63 in 2020 (Education renumbered)?", "entity_same",
  {"a": ent("B.41", 2013), "b": ent("B.63", 2020)}, "same_entity", "same")
q("5", "Is vote B.49 in 2012 the same body as B.64 in 2021 (Higher Education renumbered)?", "entity_same",
  {"a": ent("B.49", 2012), "b": ent("B.64", 2021)}, "same_entity", "same")
q("5", "Is development vote P.29 in 2020 (after B.29 ended in 2018) the same body as B.29 in 2017?", "entity_same",
  {"a": ent("P.29", 2020), "b": ent("B.29", 2017)}, "same_entity", "same")
q("5", "Is B.15 in 2019 the same body as B.15 in 2024?", "entity_same",
  {"a": ent("B.15", 2019), "b": ent("B.15", 2024)}, "same_entity", "different", kind="trap_identity")
q("5", "Does the answer say the B.15 split is not yet confirmed by a person?", "entity_same",
  {"a": ent("B.15", 2019), "b": ent("B.15", 2024)}, "entity_caveat", "rule D26", kind="trap_identity")
q("5", "Is B.26 in 2009 the same body as B.26 in 2020?", "entity_same",
  {"a": ent("B.26", 2009), "b": ent("B.26", 2020)}, "same_entity", "different", kind="trap_identity")
q("5", "Who is B.15, with no year given?", "get_entity", ent("B.15"), "entity_count", "2", kind="trap_identity")
q("5", "Which body is T.13 (debt service charges)?", "get_entity", ent("T.13"), "not_held", kind="trap_identity")
q("5", "Which body held vote B.99 in 2020?", "get_entity", ent("B.99", 2020), "not_held", kind="trap_missing")
q("5", "Is MY-03 the Kelantan state government (not the place)?", "get_entity", ent("MY-03"),
  "entity_field:gfs_sector", "state_gov")
q("5", "Does a state-government figure name the government it belongs to?", "get_series",
  series("state_gov.revenue.total", "MY-03", "2023"), "field_contains:entity_name", "Kelantan")

# ---------------------------------------------------------------- Phase 3.2: spending by vote (L1 directly)
def pk(table, code, year, col, **f):
    for r in csv.DictReader(open(os.path.join(REPO, "sources", "pkkp", "data", str(year), f"{table}.csv"))):
        if r["maksud_code"] == code and all(r[k] == v for k, v in f.items()):
            return Decimal(r[col])
    raise LookupError(f"{table} {code} {year} {col} {f}")


def ag(book, code, measure, comp):
    for r in csv.DictReader(open(os.path.join(REPO, "sources", "anggaran", "data", str(book),
                                              f"fact_anggaran_maksud_{book}.csv"))):
        if r["maksud_code"] == code and r["measure"] == measure and r["component"] == comp and r["row_type"] == "total":
            return Decimal(r["amount_rm"])
    raise LookupError(f"anggaran {book} {code} {measure} {comp}")


def vote(ind, y, entity=None, basis="audited", publisher="pkkp", breakdown="_total"):
    d = {"indicator": f"federal_gov.vote.{ind}", "geo": "MY", "start": str(y), "end": str(y), "basis": basis,
         "publisher": publisher, "breakdown": breakdown}
    if entity:
        d["entity"] = entity
    return d


q("5", "How much did the Ministry of Health (B.42) spend on operations in 2024, audited?", "get_series",
  vote("opex", 2024, "B.42"), "value", s(pk("fact_opex_maksud", "B.42", 2024, "sebenar_rm")))
q("5", "What was the Ministry of Health's revised operating estimate for 2024?", "get_series",
  vote("opex", 2024, "B.42", basis="revised_estimate"), "value", s(pk("fact_opex_maksud", "B.42", 2024, "anggaran_dipinda_rm")))
q("5", "What was Education's (B.41) audited operating spending in 2013?", "get_series",
  vote("opex", 2013, "B.41"), "value", s(pk("fact_opex_maksud", "B.41", 2013, "sebenar_rm")))
q("5", "How much was paid in debt service charges (T.13) in 2024?", "get_series",
  vote("opex", 2024, breakdown="charged_head=T.13"), "value", s(pk("fact_opex_maksud", "T.13", 2024, "sebenar_rm")))
q("5", "What did Education (P.63) spend on development in 2019 (printed in two blocks)?", "get_series",
  vote("devex", 2019, "P.63"), "value",
  s(pk("fact_devex_maksud", "P.63", 2019, "sebenar_jumlah_rm", jumlah_label_bm="KEMENTERIAN PENDIDIKAN")))
q("5", "What is the Ministry of Health's operating budget for 2026 (Anggaran 2026)?", "get_series",
  vote("opex", 2026, "B.42", basis="budget_estimate", publisher="anggaran"), "value",
  s(ag(2026, "B.42", "anggaran_2026", "mengurus")))
q("5", "Does MOF's 2024 actual for Health, as printed in the 2026 budget book, say it is not the audited figure?",
  "get_series", {**vote("opex", 2024, "B.42", basis="actual", publisher="anggaran")}, "caveat", "CV22")
q("5", "Does a vote's spending say it is gross and not placed?", "get_series", vote("opex", 2024, "B.42"), "caveat", "CV23")
q("5", "Does P.47's FY2009 development total warn that it disagrees with its own project lines?", "get_series",
  vote("devex", 2009, "P.47"), "caveat", "CV21")
q("5", "Does Health's FY2015 spending say the PKKP volume is not archived?", "get_series",
  vote("opex", 2015, "B.42"), "caveat", "CV17")
a, b = pk("fact_opex_maksud", "B.42", 2024, "sebenar_rm"), pk("fact_opex_maksud", "B.42", 2024, "anggaran_asal_rm")
q("5", "By how much did Health's audited 2024 operating spending differ from its original estimate?", "derive_chain",
  {"operation": "difference", "a": vote("opex", 2024, "B.42"), "b": vote("opex", 2024, "B.42", basis="budget_estimate")},
  "value", s(a - b))
q("5", "Who spent T.13 (as an entity)?", "get_series", vote("opex", 2024, "T.13"), "not_held", kind="trap_identity")
q("5", "Growth of B.15's spending from 2019 to 2024 (two different bodies under one code)?", "derive_chain",
  {"operation": "growth", "a": vote("opex", 2024, "B.15"), "b": vote("opex", 2019, "B.15")},
  "refused", "one body with itself", kind="trap_identity")
q("5", "Growth of Health's actuals 2021->2024 taken from two budget books (2024 and 2026)?", "derive_chain",
  {"operation": "growth", "a": vote("opex", 2024, "B.42", basis="actual", publisher="anggaran"),
   "b": vote("opex", 2021, "B.42", basis="actual", publisher="anggaran")},
  "refused", "same book", kind="trap_incomparable")

# regressions from the blind verifier of Phase 3.2 (2026-11-05)
q("5", "Who spent B.33's 2021 operating actual as printed in the 2024 budget book (the lapsed KASA vote)?",
  "get_series", vote("opex", 2021, "E000045", basis="actual", publisher="anggaran"), "value",
  s(ag(2024, "B.33", "sebenar_2021", "mengurus")), kind="trap_identity")
q("5", "Did any body hold B.64 in 2019 (Higher Education folded into Education)?", "get_entity", ent("B.64", 2019),
  "not_held", kind="trap_identity")
q("5", "Did any body hold B.32 in 2024 (the 2024 book only reprints the lapsed vote)?", "get_entity", ent("B.32", 2024),
  "not_held", kind="trap_identity")
q("5", "What was debt service (T.13) budgeted at in the 2025 budget book?", "get_series",
  vote("opex", 2025, breakdown="charged_head=T.13", basis="budget_estimate", publisher="anggaran"), "value",
  s(ag(2025, "T.13", "anggaran_2025", "jumlah")))
q("5", "Does Health's FY2015 original estimate say the PKKP volume is not archived?", "get_series",
  vote("opex", 2015, "B.42", basis="budget_estimate"), "caveat", "CV17")
q("5", "Is P.47's FY2009 development total (our extraction suspected) marked low reliability?", "get_series",
  vote("devex", 2009, "P.47"), "field:reliability", "low", kind="trap_source_defect")
q("5", "Does growth of Education's spending 2014->2015 warn that its scope changed?", "derive_chain",
  {"operation": "growth", "a": vote("opex", 2015, "E000048"), "b": vote("opex", 2014, "E000048")}, "caveat", "CV24")
q("5", "Growth from Health's 2024 original estimate to its 2024 audited spending?", "derive_chain",
  {"operation": "growth", "a": vote("opex", 2024, "B.42"), "b": vote("opex", 2024, "B.42", basis="budget_estimate")},
  "refused", "one basis", kind="trap_incomparable")
q("5", "Health's audited 2024 operating spending, asked with basis in capitals?", "get_series",
  {**vote("opex", 2024, "B.42"), "basis": "AUDITED"}, "value", s(pk("fact_opex_maksud", "B.42", 2024, "sebenar_rm")))

# ---------------------------------------------------------------- Phase 3.4: money flows (PKKP T.12, from L1)
def t12(year, aktiviti):
    for r in csv.DictReader(open(os.path.join(REPO, "sources", "pkkp", "data", str(year), "fact_opex_detail.csv"))):
        if (r["maksud_code"] == "T.12" and r["program_code"] == "010000" and r["aktiviti_code"] == aktiviti
                and r["row_type"] == "jumlah_aktiviti" and r["source_file"].startswith(str(year))):
            return Decimal(r["sebenar_rm"])
    raise LookupError(f"T.12 {year} {aktiviti}")


q("5", "How much did the federal government pay Sabah as its special annual grant in 2024?", "get_flows",
  {"to": "MY-12", "start": "2024", "end": "2024"}, "flow_value", s(t12(2024, "010600")))
q("5", "How much did Sarawak receive as its special annual grant in 2022 (federal accounts)?", "get_flows",
  {"to": "MY-13", "start": "2022", "end": "2022"}, "flow_value", s(t12(2022, "010500")))
q("5", "What was the federal annual grant to local authorities in 2023?", "get_flows",
  {"to": "local_authorities", "start": "2023", "end": "2023"}, "flow_purpose_value:annual grant to local authorities",
  s(t12(2023, "010800")))
q("5", "Is the local-authority grant placed in any state?", "get_flows",
  {"to": "local_authorities", "start": "2023", "end": "2023"}, "flow_geo", "_unallocated", kind="trap_placement")
q("5", "How much capitation grant did Johor receive in 2020, by the federal accounts?", "get_flows",
  {"to": "MY-01", "start": "2020", "end": "2020"}, "flow_count", "0", kind="trap_placement")
q("5", "Does Johor's answer show the class grants the federal accounts do not split by state?", "get_flows",
  {"to": "MY-01", "start": "2020", "end": "2020"}, "class_flow_count", "9", kind="trap_placement")
def b11(year, pattern):
    import re
    hits = [r for r in csv.DictReader(open(os.path.join(REPO, "sources", "pkkp", "data", str(year), "fact_opex_detail.csv")))
            if r["maksud_code"] == "B.11" and r["program_code"] == "020000" and r["row_type"] == "object_aktiviti"
            and r["objek_code"] == "40000" and re.search(pattern, r["aktiviti_name_bm"], re.I)
            and r["source_file"].startswith(str(year))]
    assert len(hits) == 1, (year, pattern, len(hits))
    return Decimal(hits[0]["sebenar_rm"])


def flow_by(to, year, purpose_prefix):
    return {"to": to, "start": str(year), "end": str(year), "_pick": purpose_prefix}


q("5", "How much did the federal government pay Sabah and Sarawak in 2024 for abolishing petroleum duties?", "get_flows",
  {"to": "sabah_sarawak", "start": "2024", "end": "2024"}, "flow_purpose_value:compensation to Sabah and Sarawak",
  s(b11(2024, r"petroleum.*sabah dan sarawak")))
q("5", "What were the federal grants under the Concurrent List in 2024?", "get_flows",
  {"to": "state_governments", "start": "2024", "end": "2024"}, "flow_purpose_value:grants under the Concurrent List",
  s(b11(2024, r"senarai bersama")))
q("5", "Concurrent List grants in 2017 (the printed activity total leaves out a services line; the grant is the 40000 line)?",
  "get_flows", {"to": "state_governments", "start": "2017", "end": "2017"},
  "flow_purpose_value:grants under the Concurrent List", s(b11(2017, r"senarai bersama")))
q("5", "Does Johor's answer leave out the grants paid to Sabah and Sarawak together?", "get_flows",
  {"to": "MY-01", "start": "2024", "end": "2024"}, "class_excludes", "Kerajaan Negeri Sabah dan Sarawak",
  kind="trap_placement")
q("5", "Does Sarawak's answer include the grants paid to Sabah and Sarawak together?", "get_flows",
  {"to": "MY-13", "start": "2024", "end": "2024"}, "class_includes", "Kerajaan Negeri Sabah dan Sarawak",
  kind="trap_placement")
q("5", "Federal special grant to the Federal Territories in 2023?", "get_flows",
  {"to": "federal_territories", "start": "2023", "end": "2023"}, "flow_purpose_value:special grant to the Federal Territories",
  s(b11(2023, r"pemberian khas kepada wilayah persekutuan")))
def vote_grant(year, maksud, pattern):
    import re
    hits = [r for r in csv.DictReader(open(os.path.join(REPO, "sources", "pkkp", "data", str(year), "fact_opex_detail.csv")))
            if r["maksud_code"] == maksud and r["row_type"] == "object_aktiviti" and r["objek_code"] == "40000"
            and re.search(pattern, r["aktiviti_name_bm"], re.I) and r["source_file"].startswith(str(year))]
    assert len(hits) == 1, (year, maksud, pattern, len(hits))
    return Decimal(hits[0]["sebenar_rm"])


q("5", "Federal special grant to the Federal Territories in 2024 (moved from B.11 to the Prime Minister's Department)?",
  "get_flows", {"to": "federal_territories", "start": "2024", "end": "2024"},
  "flow_purpose_value:special grant to the Federal Territories",
  s(vote_grant(2024, "B.06", r"pemberian khas kepada wilayah persekutuan")))
def named_grant(year, maksud, pattern):
    import re
    hits = [r for r in csv.DictReader(open(os.path.join(REPO, "sources", "pkkp", "data", str(year), "fact_opex_detail.csv")))
            if r["maksud_code"] == maksud and r["row_type"] == "object_aktiviti" and r["objek_code"] == "40000"
            and re.search(pattern, (r["aktiviti_name_bm"].strip() or r["program_name_bm"]), re.I)
            and r["source_file"].startswith(str(year))]
    assert len(hits) == 1, (year, maksud, pattern, len(hits))
    return Decimal(hits[0]["sebenar_rm"])


q("5", "How much did the federal government pay Perbadanan Putrajaya in 2011 (a whole programme in B.32)?", "get_flows",
  {"to": "perbadanan_putrajaya", "start": "2011", "end": "2011"}, "flow_value",
  s(named_grant(2011, "B.32", r"^\s*perbadanan putrajaya")))
q("5", "What did Labuan's administration receive by name from the federal government in 2024?", "get_flows",
  {"to": "MY-15", "start": "2024", "end": "2024"}, "flow_value", s(named_grant(2024, "B.06", r"^\s*perbadanan labuan")))
q("5", "Did Kuala Lumpur City Hall receive a federal grant by name in 2019?", "get_flows",
  {"to": "dbkl", "start": "2019", "end": "2019"}, "not_held", kind="trap_missing")
q("5", "Is Putrajaya shown the local-authority grants paid to the states' local authorities?", "get_flows",
  {"to": "MY-16", "start": "2024", "end": "2024"}, "class_excludes", "Pihak Berkuasa Tempatan", kind="trap_placement")
q("5", "Does a group answer say no amount is one body's money?", "get_flows",
  {"to": "state_governments", "start": "2024", "end": "2024"}, "field_contains:answer", "no amount here is one body",
  kind="trap_placement")
q("5", "Sabah's federal grants 2014-2016: does the answer say FY2015 is not held?", "get_flows",
  {"to": "MY-12", "start": "2014", "end": "2016"}, "field_contains:years_not_held", "2015", kind="trap_missing")
q("5", "Does Sabah's answer warn not to add up its named grants as what it received?", "get_flows",
  {"to": "MY-12", "start": "2024", "end": "2024"}, "field_contains:answer", "do not add up", kind="trap_placement")
q("5", "Does the flow answer say the B.11 grants are not loaded?", "get_flows",
  {"to": "MY-13", "start": "2024", "end": "2024"}, "field_contains:coverage", "B.11", kind="trap_missing")
q("5", "Federal grants to Kuala Lumpur in 2024 (a Federal Territory)?", "get_flows",
  {"to": "MY-14", "start": "2024", "end": "2024"}, "field_contains:answer", "Federal Territory", kind="trap_identity")
q("5", "Sabah's grants from the first quarter of 2020?", "get_flows", {"to": "MY-12", "start": "2020Q1"},
  "not_held", kind="trap_incomparable")
q("5", "Federal grants to the states in 2015 (the image-only volume)?", "get_flows",
  {"to": "state_governments", "start": "2015", "end": "2015"}, "not_held", kind="trap_missing")
q("5", "Does a flow say what it can and cannot place?", "get_flows", {"to": "MY-12", "start": "2024", "end": "2024"},
  "caveat", "CV25")

def st_rev(state, year, pattern, own=True):
    """A state's printed revenue line from L1 (its own-year volume unless own=False: every printing)."""
    import re
    slug = state.lower().replace(" ", "_")
    hits = [r for r in csv.DictReader(open(os.path.join(REPO, "sources", "states", "data", slug,
                                                         f"fact_state_revenue_{slug}.csv")))
            if r["fiscal_year"] == year and r["measure"] == "actual" and re.search(pattern, r["line_label_bm"], re.I)
            and (r["column_role"] == "own_year") == own]
    vals = {Decimal(r["amount_rm_conformed"]) for r in hits}
    assert vals and (len(vals) == 1 or not own), (state, year, pattern, vals)
    return vals


# J. gap_federal_vs_state: federal paid (PKKP) vs state recorded (state accounts)
q("5", "What did Kedah record receiving as the Concurrent List grant in 2020 (its own report)?", "get_gap_view",
  {"name": "gap_federal_vs_state", "geo": "MY-02", "year": "2020", "transfer": "concurrent_list"},
  "field:state_recorded_rm", s(next(iter(st_rev("Kedah", "2020", r"senarai bersama")))))
q("5", "Do Kedah's own reports agree on its 2020 Concurrent List grant?", "get_gap_view",
  {"name": "gap_federal_vs_state", "geo": "MY-02", "year": "2020", "transfer": "concurrent_list"},
  "field:printings_agree", "true" if len(st_rev("Kedah", "2020", r"senarai bersama", own=False)
                                         | st_rev("Kedah", "2020", r"senarai bersama")) == 1 else "false",
  kind="trap_restatement")
q("5", "What does the view give as the federal Concurrent List grants to all states in 2020?", "get_gap_view",
  {"name": "gap_federal_vs_state", "geo": "_states", "year": "2020", "transfer": "concurrent_list"},
  "field:federal_paid_rm", s(b11(2020, r"senarai bersama")))
q("5", "Can a state's Concurrent List receipt 'agree' with the federal accounts?", "get_gap_view",
  {"name": "gap_federal_vs_state", "geo": "MY-10", "year": "2022", "transfer": "concurrent_list"},
  "field:comparison", "share_of_class_total", kind="trap_placement")
q("5", "Did Johor print its capitation grant in 2020 (or is it zero)?", "get_gap_view",
  {"name": "gap_federal_vs_state", "geo": "MY-01", "year": "2020", "transfer": "capitation"},
  "field:status", "state_not_printed", kind="trap_missing")
q("5", "Is Sarawak's 2023 record of its federal grants at least its special grant?", "get_gap_view",
  {"name": "gap_federal_vs_state", "geo": "MY-13", "year": "2023", "transfer": "named"}, "field:status",
  "consistent" if next(iter(st_rev("Sarawak", "2023", r"^pemberian kerajaan persekutuan"))) >= t12(2023, "010500")
  else "inconsistent")
q("5", "Capitation grant to Kuala Lumpur in 2022, federal vs state?", "get_gap_view",
  {"name": "gap_federal_vs_state", "geo": "MY-14", "year": "2022", "transfer": "capitation"},
  "field:status", "no_state_government", kind="trap_identity")
q("5", "Federal vs state Concurrent List grants in 2015?", "get_gap_view",
  {"name": "gap_federal_vs_state", "geo": "_states", "year": "2015", "transfer": "concurrent_list"},
  "field:status", "federal_not_held", kind="trap_missing")
q("5", "Federal vs state road grants?", "get_gap_view",
  {"name": "gap_federal_vs_state", "transfer": "roads"}, "not_held", kind="trap_incomparable")
q("5", "Does the federal-vs-state view say a missing state figure is not zero?", "get_gap_view",
  {"name": "gap_federal_vs_state", "geo": "MY-01", "year": "2020", "transfer": "capitation"},
  "field_contains:how_to_read", "is not zero", kind="trap_missing")

with open(os.path.join(REPO, "qa", "eval_questions.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(Q[0]))
    w.writeheader()
    w.writerows(Q)
print(f"qa/eval_questions.csv: {len(Q)} questions")
