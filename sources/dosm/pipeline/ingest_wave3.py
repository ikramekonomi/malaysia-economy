#!/usr/bin/env python3
"""Ingest the DOSM / data.gov.my **wave 3** datasets (2026-11-06): what the catalogue added since the
real-economy ingest, and what the build order's steps 1 and 5 need.

  python3 sources/dosm/pipeline/ingest_wave3.py   -> data/<dataset_id>.csv + _vintage.json + _vintage_log.csv

Three blocks:
  1. Wages and productivity: the Salaries & Wages Survey tables (wages_*: median and mean monthly wages and
     recipients by state, strata, sector, industry, education, age, ethnicity, occupation, skill, certificate,
     non-citizens, and real wages by state), formal-sector wages from administrative records (formal_wages_*,
     monthly), and labour productivity by state. The real-economy ingest (2026-08-03) found no wages dataset in
     the catalogue; these were published since.
  2. Prices, output, people, services: CPI detail (core, low-income households, urban/rural, inflation by state,
     annual), GDP by district (constant 2015 prices), life expectancy (national, state x ethnicity, district),
     births, fertility, maternal and early-childhood deaths by state, school completion (state, district) and
     household internet access.
  3. Environment, energy, water, agriculture (theme 9 and 4): air pollution, greenhouse-gas emissions, river
     basin water quality, forest reserves, electricity and energy balance, water consumption and production,
     mineral extraction, timber, crops and fish landings.
Left out on purpose (size; not needed yet): cpi_3d/4d/5d, population_dun/parlimen (age x ethnicity grain).

Same discipline as ingest_expansion.py and ingest_realeconomy.py: the catalogue's storage file, values
verbatim, two appended provenance columns (retrieved_from, retrieved_date), the vintage recorded in
_vintage.json and appended to _vintage_log.csv. The second door is verify_wave3.py (the parquet mirror of
the same publication). Routes: "opendosm" / "data-catalogue" = served by api.data.gov.my; "meta" = excluded
from the API, vintage from the catalogue repo.
"""
import json
import os
import sys
import urllib.request
from datetime import date

from ingest_expansion import download_with_provenance

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
VINTAGE = os.path.join(DATA, "_vintage.json")
META_REPO = "https://raw.githubusercontent.com/data-gov-my/datagovmy-meta/main/data-catalogue/{}.json"

WAVE3 = {
    # ---- 1. wages and productivity
    "wages_state": ("https://storage.dosm.gov.my/labour/wages_state.csv", "opendosm"),
    "wages_strata": ("https://storage.dosm.gov.my/labour/wages_strata.csv", "opendosm"),
    "wages_sector": ("https://storage.dosm.gov.my/labour/wages_sector.csv", "opendosm"),
    "wages_industry": ("https://storage.dosm.gov.my/labour/wages_industry.csv", "opendosm"),
    "wages_education": ("https://storage.dosm.gov.my/labour/wages_education.csv", "opendosm"),
    "wages_age": ("https://storage.dosm.gov.my/labour/wages_age.csv", "opendosm"),
    "wages_ethnicity": ("https://storage.dosm.gov.my/labour/wages_ethnicity.csv", "opendosm"),
    "wages_occupation": ("https://storage.dosm.gov.my/labour/wages_occupation.csv", "opendosm"),
    "wages_skill": ("https://storage.dosm.gov.my/labour/wages_skill.csv", "opendosm"),
    "wages_certificate": ("https://storage.dosm.gov.my/labour/wages_certificate.csv", "opendosm"),
    "wages_noncitizen": ("https://storage.dosm.gov.my/labour/wages_noncitizen.csv", "opendosm"),
    "wages_noncitizen_education": ("https://storage.dosm.gov.my/labour/wages_noncitizen_education.csv", "opendosm"),
    "wages_real_state": ("https://storage.dosm.gov.my/labour/wages_real_state.csv", "opendosm"),
    "wages_real_state_citizen": ("https://storage.dosm.gov.my/labour/wages_real_state_citizen.csv", "opendosm"),
    "formal_wages": ("https://storage.dosm.gov.my/labour/formal_wages.csv", "opendosm"),
    "formal_wages_state": ("https://storage.dosm.gov.my/labour/formal_wages_state.csv", "opendosm"),
    "formal_wages_msic": ("https://storage.dosm.gov.my/labour/formal_wages_msic.csv", "opendosm"),
    "formal_wages_band": ("https://storage.dosm.gov.my/labour/formal_wages_band.csv", "opendosm"),
    "formal_wages_percentile": ("https://storage.dosm.gov.my/labour/formal_wages_percentile.csv", "opendosm"),
    "formal_wages_msic_age": ("https://storage.dosm.gov.my/labour/formal_wages_msic_age.csv", "opendosm"),
    "productivity_state": ("https://storage.dosm.gov.my/labour/productivity_state.csv", "opendosm"),
    # ---- 2. prices, output, people, services
    "cpi_core": ("https://storage.dosm.gov.my/cpi/cpi_2d_core.csv", "opendosm"),
    "cpi_core_inflation": ("https://storage.dosm.gov.my/cpi/cpi_2d_core_inflation.csv", "opendosm"),
    "cpi_lowincome": ("https://storage.dosm.gov.my/cpi/cpi_2d_lowincome.csv", "opendosm"),
    "cpi_strata": ("https://storage.dosm.gov.my/cpi/cpi_2d_strata.csv", "opendosm"),
    "cpi_state_inflation": ("https://storage.dosm.gov.my/cpi/cpi_2d_state_inflation.csv", "opendosm"),
    "cpi_headline_inflation": ("https://storage.dosm.gov.my/cpi/cpi_2d_inflation.csv", "opendosm"),
    "cpi_annual": ("https://storage.dosm.gov.my/cpi/cpi_2d_annual.csv", "opendosm"),
    "cpi_annual_inflation": ("https://storage.dosm.gov.my/cpi/cpi_2d_annual_inflation.csv", "opendosm"),
    "gdp_district_real_supply": ("https://storage.dosm.gov.my/gdp/gdp_district_real_supply.csv", "opendosm"),
    "life_expectancy": ("https://storage.dosm.gov.my/demography/life_expectancy.csv", "opendosm"),
    "life_expectancy_state_ethnic": ("https://storage.dosm.gov.my/demography/life_expectancy_state_ethnic.csv", "opendosm"),
    "life_expectancy_district": ("https://storage.dosm.gov.my/demography/life_expectancy_district.csv", "opendosm"),
    "births_annual_state": ("https://storage.dosm.gov.my/demography/birth_state.csv", "opendosm"),
    "fertility_state": ("https://storage.dosm.gov.my/demography/fertility_state.csv", "opendosm"),
    "deaths_maternal_state": ("https://storage.dosm.gov.my/demography/death_maternal_state.csv", "opendosm"),
    "deaths_early_childhood_state": ("https://storage.dosm.gov.my/demography/deaths_early_childhood_state.csv", "opendosm"),
    "completion_school_state": ("https://storage.data.gov.my/education/completion_school_state.csv", "data-catalogue"),
    "completion_school_district": ("https://storage.data.gov.my/education/completion_school_district.csv", "data-catalogue"),
    "hh_access_internet": ("https://storage.dosm.gov.my/icths/hh_access_internet.csv", "opendosm"),
    # ---- 3. environment, energy, water, agriculture
    "air_pollution": ("https://storage.data.gov.my/environment/air_pollution.csv", "data-catalogue"),
    "ghg_emissions": ("https://storage.data.gov.my/environment/ghg_emissions.csv", "data-catalogue"),
    "water_pollution_basin": ("https://storage.data.gov.my/environment/water_pollution_basin.csv", "data-catalogue"),
    "forest_reserve": ("https://storage.data.gov.my/environment/forest_reserve.csv", "data-catalogue"),
    "forest_reserve_state": ("https://storage.data.gov.my/environment/forest_reserve_state.csv", "data-catalogue"),
    "electricity_consumption": ("https://storage.data.gov.my/energy/electricity_consumption.csv", "data-catalogue"),
    "electricity_supply": ("https://storage.data.gov.my/energy/electricity_supply.csv", "data-catalogue"),
    "energy_consumption_sector": ("https://storage.data.gov.my/energy/energy_consumption_sector.csv", "data-catalogue"),
    "energy_supply_commodity": ("https://storage.data.gov.my/energy/energy_supply_commodity.csv", "data-catalogue"),
    "water_consumption": ("https://storage.data.gov.my/water/water_consumption.csv", "data-catalogue"),
    "water_production": ("https://storage.data.gov.my/water/water_production.csv", "data-catalogue"),
    "mineral_extraction": ("https://storage.data.gov.my/mining/mineral_extraction.csv", "data-catalogue"),
    "timber_production": ("https://storage.data.gov.my/agriculture/timber_products.csv", "data-catalogue"),
    "crops_state": ("https://storage.data.gov.my/agriculture/crops_state.csv", "data-catalogue"),
    "fish_landings": ("https://storage.data.gov.my/agriculture/fish_landings.csv", "data-catalogue"),
}


def meta_for(ds, route):
    if route == "meta":
        with urllib.request.urlopen(META_REPO.format(ds), timeout=60) as r:
            m = json.loads(r.read())
        return {k: m.get(k) for k in ("data_as_of", "last_updated", "next_update")}
    with urllib.request.urlopen(f"https://api.data.gov.my/{route}?id={ds}&meta=true&limit=1", timeout=60) as r:
        return json.loads(r.read())["meta"]


def main():
    sys.path.insert(0, HERE)
    from refresh import log_vintage, storage_etag  # noqa: E402  (refresh imports this module)
    only = set(sys.argv[1:])
    vintage = json.load(open(VINTAGE))
    today = date.today().isoformat()
    for ds, (url, route) in WAVE3.items():
        if only and ds not in only:
            continue
        dest = os.path.join(DATA, f"{ds}.csv")
        n = download_with_provenance(url, dest, retrieved_date=today)
        m = meta_for(ds, route)
        etag, lastmod = storage_etag(url)
        vintage[ds] = {"file": f"{ds}.csv", "data_as_of": m.get("data_as_of"), "last_updated": m.get("last_updated"),
                       "next_update": m.get("next_update"), "api_total_rows": m.get("total"), "storage_etag": etag,
                       "storage_last_modified": lastmod, "api_route": route, "provenance_columns": True,
                       "block": "wave3"}
        log_vintage(ds, f"{ds}.csv", vintage[ds], dest, "current")
        print(f"{ds}: {n} rows (data_as_of {m.get('data_as_of')})")
    json.dump(vintage, open(VINTAGE, "w"), indent=2)


if __name__ == "__main__":
    main()
