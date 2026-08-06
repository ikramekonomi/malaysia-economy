#!/usr/bin/env python3
"""Ingest the DOSM **real-economy set** — the outcome measures an economic agenda is
judged on (docs/SOURCES.md, Tier 1b + the Agenda Ekonomi Negara roadmap).

The warehouse's fiscal side is audited and reconcilable to the ringgit. The economy
side is not: it is survey-based, revised, and vintaged. So this ingest follows the
same discipline as `ingest_expansion.py` — values verbatim, provenance on every row,
vintage recorded, verified through a second independent door — and adds one thing the
fiscal sources never needed: a **series-break register** (`series_breaks.py` ->
data/_series_breaks_dosm.csv), because HIES is a periodic survey whose definitions,
geographic coverage and poverty lines have all changed inside the published series.

Five blocks, in the priority order of the brief:

  1. National accounts detail  — GDP by sector AND by expenditure, annual + quarterly,
     real + nominal + seasonally adjusted, headline + subsector/subtype "granular"
     tiers, the income approach (the only published labour-share aggregate), real
     GDP & GNI, and the external balance (BOP) + FDI flows, which is as close as the
     catalogue gets to a savings/investment balance.
  2. Household income & expenditure (HIES) — income mean/median, Gini, poverty
     (absolute / hardcore / relative), by state, district, parliament and DUN, plus
     the full percentile distribution nationally and by state. This is the block
     without which the agenda's core outcomes are unmeasurable.
  3. Wages, productivity, labour depth — labour productivity (annual, quarterly,
     priority subsectors), the LFS at every published grain, and both published
     underemployment measures (skills-related and time-related).
  4. Industrial production, wholesale & retail, services — the monthly/quarterly
     activity and producer-price indices.
  5. Trade depth — retained imports by BEC/end-use, plus the SITC and BEC dictionaries.

Retrieval path is the catalogue's own storage links (byte-stable, unpaginated); each
file is written to data/<dataset_id>.csv with the source values verbatim plus the two
appended provenance columns retrieved_from + retrieved_date.

Route notes
-----------
Seven of these datasets carry `exclude_openapi: true` in the catalogue metadata, so
api.data.gov.my does not serve them. They are marked route "meta" here: their vintage
metadata comes from the catalogue repo (raw.githubusercontent.com/data-gov-my/
datagovmy-meta) and their independent verification door is the **parquet mirror** of
the same publication (the pattern verify_against_api.py already uses for the original
three denominators), not the API. Nothing is left unverified.

Catalogue absences found while building this list (2026-08-03) — recorded in README.md
because an absence is a finding: there is **no salaries & wages dataset** (DOSM's
formal-sector wages figures are dashboard-only), **no manufacturing sales-value
dataset**, **no index of services production**, **no nominal state GDP**, **no
household expenditure dataset at national or state grain** (only DUN/parliament, plus
the hies_state/hies_district income-and-expenditure pair), and **no trade below SITC
1-digit and none by partner country**.
"""
import csv
import io
import json
import os
import urllib.request

from ingest_expansion import download_with_provenance  # provenance-appending writer

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
VINTAGE = os.path.join(DATA, "_vintage.json")
RETRIEVED_DATE = "2026-08-03"

META_REPO = ("https://raw.githubusercontent.com/data-gov-my/datagovmy-meta/main/"
             "data-catalogue/{}.json")

S_GDP = "https://storage.dosm.gov.my/gdp/"
S_BOP = "https://storage.dosm.gov.my/bop/"
S_HIES = "https://storage.dosm.gov.my/hies/"
S_DEMO = "https://storage.dosm.gov.my/demography/"
S_LAB = "https://storage.dosm.gov.my/labour/"
S_IPI = "https://storage.dosm.gov.my/ipi/"
S_IOW = "https://storage.dosm.gov.my/iowrt/"
S_PPI = "https://storage.dosm.gov.my/ppi/"
S_MEI = "https://storage.dosm.gov.my/mei/"
S_TRADE = "https://storage.dosm.gov.my/trade/"
S_DICT = "https://storage.dosm.gov.my/dictionaries/"

# dataset id -> (storage csv url, verification route)
#   "opendosm"  -> api.data.gov.my/opendosm serves it (second door = the API)
#   "meta"      -> exclude_openapi in the catalogue; vintage from datagovmy-meta,
#                  second door = the parquet mirror of the same file
REALECONOMY = {
    # ---- 1. National accounts detail -------------------------------------------
    "gdp_gni_annual_real": (S_GDP + "gdp_gni_annual_real.csv", "opendosm"),
    "gdp_annual_nominal_supply": (S_GDP + "gdp_annual_nominal_supply.csv", "opendosm"),
    "gdp_annual_real_supply": (S_GDP + "gdp_annual_real_supply.csv", "opendosm"),
    "gdp_annual_nominal_demand": (S_GDP + "gdp_annual_nominal_demand.csv", "opendosm"),
    "gdp_annual_real_demand": (S_GDP + "gdp_annual_real_demand.csv", "opendosm"),
    "gdp_annual_nominal_income": (S_GDP + "gdp_annual_nominal_income.csv", "opendosm"),
    "gdp_annual_nominal_supply_granular": (S_GDP + "gdp_annual_nominal_supply_sub.csv", "opendosm"),
    "gdp_annual_real_supply_granular": (S_GDP + "gdp_annual_real_supply_sub.csv", "opendosm"),
    "gdp_annual_nominal_demand_granular": (S_GDP + "gdp_annual_nominal_demand_sub.csv", "opendosm"),
    "gdp_annual_real_demand_granular": (S_GDP + "gdp_annual_real_demand_sub.csv", "meta"),
    "gdp_qtr_nominal": (S_GDP + "gdp_qtr_nominal.csv", "opendosm"),
    "gdp_qtr_real": (S_GDP + "gdp_qtr_real.csv", "opendosm"),
    "gdp_qtr_nominal_supply": (S_GDP + "gdp_qtr_nominal_supply.csv", "opendosm"),
    "gdp_qtr_real_supply": (S_GDP + "gdp_qtr_real_supply.csv", "opendosm"),
    "gdp_qtr_nominal_demand": (S_GDP + "gdp_qtr_nominal_demand.csv", "opendosm"),
    "gdp_qtr_real_demand": (S_GDP + "gdp_qtr_real_demand.csv", "opendosm"),
    "gdp_qtr_real_sa": (S_GDP + "gdp_qtr_real_sa.csv", "opendosm"),
    "gdp_qtr_real_sa_supply": (S_GDP + "gdp_qtr_real_sa_supply.csv", "opendosm"),
    "gdp_qtr_real_sa_demand": (S_GDP + "gdp_qtr_real_sa_demand.csv", "opendosm"),
    "gdp_qtr_nominal_supply_granular": (S_GDP + "gdp_qtr_nominal_supply_sub.csv", "meta"),
    "gdp_qtr_real_supply_granular": (S_GDP + "gdp_qtr_real_supply_sub.csv", "meta"),
    "gdp_qtr_nominal_demand_granular": (S_GDP + "gdp_qtr_nominal_demand_sub.csv", "meta"),
    "gdp_qtr_real_demand_granular": (S_GDP + "gdp_qtr_real_demand_sub.csv", "meta"),
    "gdp_lookup": (S_GDP + "gdp_lookup.csv", "opendosm"),
    "bop_balance": (S_BOP + "bop_balance.csv", "opendosm"),
    "fdi_flows": (S_BOP + "fdi_flows.csv", "opendosm"),
    # ---- 2. Household income & expenditure (HIES) -------------------------------
    "hh_income": (S_HIES + "hh_income.csv", "opendosm"),
    "hh_income_state": (S_HIES + "hh_income_state.csv", "opendosm"),
    "hh_income_district": (S_HIES + "hh_income_district.csv", "opendosm"),
    "hh_income_parlimen": (S_HIES + "hh_income_parlimen.csv", "opendosm"),
    "hh_income_dun": (S_HIES + "hh_income_dun.csv", "opendosm"),
    "hh_inequality": (S_HIES + "hh_inequality.csv", "opendosm"),
    "hh_inequality_state": (S_HIES + "hh_inequality_state.csv", "opendosm"),
    "hh_inequality_district": (S_HIES + "hh_inequality_district.csv", "opendosm"),
    "hh_inequality_parlimen": (S_HIES + "hh_inequality_parlimen.csv", "opendosm"),
    "hh_inequality_dun": (S_HIES + "hh_inequality_dun.csv", "opendosm"),
    "hh_poverty": (S_HIES + "hh_poverty.csv", "opendosm"),
    "hh_poverty_state": (S_HIES + "hh_poverty_state.csv", "opendosm"),
    "hh_poverty_district": (S_HIES + "hh_poverty_district.csv", "opendosm"),
    "hh_poverty_parlimen": (S_HIES + "hh_poverty_parlimen.csv", "opendosm"),
    "hh_poverty_dun": (S_HIES + "hh_poverty_dun.csv", "opendosm"),
    "hies_malaysia_percentile": (S_HIES + "hies_malaysia_percentile.csv", "opendosm"),
    "hies_state_percentile": (S_HIES + "hies_state_percentile.csv", "opendosm"),
    "hies_state": (S_HIES + "hies_state.csv", "opendosm"),
    "hies_district": (S_HIES + "hies_district.csv", "opendosm"),
    "hh_expenditure_parlimen": (S_HIES + "hh_expenditure_parlimen.csv", "opendosm"),
    "hh_expenditure_dun": (S_HIES + "hh_expenditure_dun.csv", "opendosm"),
    "hh_access_amenities": (S_HIES + "hh_access_amenities.csv", "opendosm"),
    "hh_profile_state": (S_DEMO + "hh_lq_state.csv", "opendosm"),
    # ---- 3. Wages, productivity, labour depth -----------------------------------
    "productivity_annual": (S_LAB + "productivity_annual.csv", "opendosm"),
    "productivity_annual_priority": (S_LAB + "productivity_annual_p14.csv", "opendosm"),
    "productivity_qtr": (S_LAB + "productivity_qtr.csv", "opendosm"),
    "productivity_lookup": (S_LAB + "productivity_lookup.csv", "opendosm"),
    "lfs_month_sa": (S_LAB + "lfs_month_sa.csv", "opendosm"),
    "lfs_month_status": (S_LAB + "lfs_month_status.csv", "opendosm"),
    "lfs_month_duration": (S_LAB + "lfs_month_duration.csv", "opendosm"),
    "lfs_month_youth": (S_LAB + "lfs_month_youth.csv", "opendosm"),
    "lfs_qtr": (S_LAB + "lfs_qtr.csv", "opendosm"),
    "lfs_qtr_state": (S_LAB + "lfs_qtr_state.csv", "opendosm"),
    "lfs_qtr_sru_age": (S_LAB + "lfs_qtr_sru_age.csv", "opendosm"),
    "lfs_qtr_sru_sex": (S_LAB + "lfs_qtr_sru_sex.csv", "opendosm"),
    "lfs_qtr_tru_age": (S_LAB + "lfs_qtr_tru_age.csv", "opendosm"),
    "lfs_qtr_tru_sex": (S_LAB + "lfs_qtr_tru_sex.csv", "opendosm"),
    "lfs_year": (S_LAB + "lfs_year.csv", "opendosm"),
    "lfs_year_sex": (S_LAB + "lfs_year_sex.csv", "opendosm"),
    "lfs_state_sex": (S_LAB + "lfs_state_sex.csv", "opendosm"),
    "lfs_district": (S_LAB + "lfs_district.csv", "opendosm"),
    "lfs_parlimen": (S_LAB + "lfs_parlimen.csv", "opendosm"),
    "lfs_dun": (S_LAB + "lfs_dun.csv", "opendosm"),
    "employment_sector": (S_LAB + "employment_sector.csv", "opendosm"),
    # ---- 4. Industrial production, wholesale & retail, services ------------------
    "ipi": (S_IPI + "ipi.csv", "opendosm"),
    "ipi_1d": (S_IPI + "ipi_1d.csv", "opendosm"),
    "ipi_2d": (S_IPI + "ipi_2d.csv", "meta"),
    "ipi_domestic": (S_IPI + "ipi_domestic.csv", "meta"),
    "ipi_export": (S_IPI + "ipi_export.csv", "meta"),
    "iowrt": (S_IOW + "iowrt.csv", "opendosm"),
    "iowrt_2d": (S_IOW + "iowrt_2d.csv", "opendosm"),
    "iowrt_3d": (S_IOW + "iowrt_3d.csv", "meta"),
    "sppi": (S_PPI + "sppi.csv", "opendosm"),
    "sppi_1d": (S_PPI + "sppi_1d.csv", "opendosm"),
    "sppi_2d": (S_PPI + "sppi_2d.csv", "opendosm"),
    "sppi_3d": (S_PPI + "sppi_3d.csv", "meta"),
    "ppi": (S_PPI + "ppi.csv", "opendosm"),
    "ppi_1d": (S_PPI + "ppi_1d.csv", "opendosm"),
    # producer prices on the SAME SITC classification as trade_sitc_1d — the pairing
    # that makes a terms-of-trade read possible without a mapping table
    "ppi_sitc": (S_PPI + "ppi_sitc.csv", "opendosm"),
    "economic_indicators": (S_MEI + "mei.csv", "opendosm"),
    # ---- 5. Trade depth ---------------------------------------------------------
    "trade_enduse_bec": (S_TRADE + "trade_enduse_bec.csv", "opendosm"),
    "sitc": (S_DICT + "sitc.csv", "opendosm"),
    "bec": (S_DICT + "bec.csv", "opendosm"),
    "mcoicop": (S_DICT + "mcoicop.csv", "opendosm"),
}


def catalogue_meta(ds):
    """Vintage metadata from the catalogue repo — works for exclude_openapi datasets too."""
    with urllib.request.urlopen(META_REPO.format(ds), timeout=60) as r:
        return json.loads(r.read())


def api_meta(ds, route):
    url = f"https://api.data.gov.my/{route}?id={ds}&meta=true&limit=1"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())["meta"]


def meta_for(ds, route):
    """Uniform vintage dict regardless of whether the API serves the dataset."""
    if route == "meta":
        m = catalogue_meta(ds)
        return {"data_as_of": m.get("data_as_of"), "last_updated": m.get("last_updated"),
                "next_update": m.get("next_update"), "api_total_rows": None}
    m = api_meta(ds, route)
    return {"data_as_of": m.get("data_as_of"), "last_updated": m.get("last_updated"),
            "next_update": m.get("next_update"), "api_total_rows": m.get("total")}


def storage_etag(url):
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.headers.get("ETag", "").strip('"'), r.headers.get("Last-Modified", "")


def main():
    os.makedirs(DATA, exist_ok=True)
    vintage = json.load(open(VINTAGE)) if os.path.exists(VINTAGE) else {}
    total = 0
    for ds, (url, route) in REALECONOMY.items():
        dest = os.path.join(DATA, f"{ds}.csv")
        n = download_with_provenance(url, dest, retrieved_date=RETRIEVED_DATE)
        total += n
        m = meta_for(ds, route)
        etag, lastmod = storage_etag(url)
        vintage[ds] = {"file": f"{ds}.csv", "data_as_of": m["data_as_of"],
                       "last_updated": m["last_updated"], "next_update": m["next_update"],
                       "api_total_rows": m["api_total_rows"], "storage_etag": etag,
                       "storage_last_modified": lastmod, "api_route": route,
                       "provenance_columns": True, "block": "realeconomy"}
        print(f"{ds}: {n} rows (data_as_of {m['data_as_of']}) -> {dest}")
    json.dump(vintage, open(VINTAGE, "w"), indent=2)
    print(f"total {total} rows across {len(REALECONOMY)} datasets; vintage recorded in {VINTAGE}")
    print("next: python3 sources/dosm/pipeline/series_breaks.py")
    print("      python3 sources/dosm/pipeline/verify_realeconomy.py")


if __name__ == "__main__":
    main()
