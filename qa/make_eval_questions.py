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
  {"indicator": "hh_income.gross.median", "period": "2022", "geo_level": "district"}, "not_ranked",
  kind="trap_small_area")
q("1", "Rank the parliamentary constituencies by poverty.", "compare_geos",
  {"indicator": "poverty.absolute.rate", "period": "2022", "geo_level": "parlimen"}, "not_ranked",
  kind="trap_small_area")

# E. missing documents are answers
q("5", "How many cash-transfer recipients are there in each state?", "find_indicator",
  {"text": "cash transfer recipients"}, "not_held_registry", "social_transfers_by_state", kind="trap_missing")
q("6", "How many doctors per person does each state have?", "find_indicator", {"text": "doctors per state"},
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

with open(os.path.join(REPO, "qa", "eval_questions.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(Q[0]))
    w.writeheader()
    w.writerows(Q)
print(f"qa/eval_questions.csv: {len(Q)} questions")
