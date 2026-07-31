# Source: DOSM (Department of Statistics Malaysia) — national denominators

Macro denominators for the warehouse: **annual nominal GDP**, **population**, and
**number of households**. Used by `curated/dashboard/` to express audited PKKP figures
per-GDP / per-capita / per-household. These are *external context* series — never blended
into the audited fiscal tables.

## Datasets (CSVs in `data/` are the canonical, as-published files)

| file | dataset (data.gov.my / OpenDOSM) | units | coverage | data vintage |
|---|---|---|---|---|
| `gdp_gni_annual_nominal.csv` | Annual Nominal GDP & GNI: 1947 to Present (`gdp_gni_annual_nominal`) | RM million (`abs` rows); `growth_yoy` rows = % | 1947–2025 | "Data as of 2025" per catalogue page |
| `population_malaysia.csv` | Population — Malaysia (`population_malaysia`) | '000 persons, by sex × age × ethnicity | 1970–2026 | "Data as of 2025" per catalogue page |
| `hh_lq.csv` | Number of Households and Living Quarters (`hh_profile`) | count | 1970–2024 (annual from 2010) | "Data as of 2024" per catalogue page |

## Provenance

- Retrieved **2026-07-31** from DOSM's own object storage (the catalogue pages' download links):
  - https://storage.dosm.gov.my/gdp/gdp_gni_annual_nominal.csv
  - https://storage.dosm.gov.my/population/population_malaysia.csv
  - https://storage.dosm.gov.my/demography/hh_lq.csv
- Catalogue pages: https://open.dosm.gov.my/data-catalogue/gdp_gni_annual_nominal ,
  https://open.dosm.gov.my/data-catalogue/population_malaysia ,
  https://open.dosm.gov.my/data-catalogue/hh_profile
- License: Creative Commons Attribution 4.0 (per catalogue pages).
- The CSVs are byte-for-byte as downloaded — **never edit them**; re-download to refresh
  (that is a new vintage: update this README's retrieval date and vintages).

## Keeping it fresh (updates are pulled, never silent)

The warehouse pins a retrieval vintage on purpose — an upstream revision changing every
%GDP ratio silently would break provenance. To detect and apply DOSM updates:

- `python3 sources/dosm/pipeline/refresh.py` — **check** (safe): compares the OpenDOSM
  static API metadata (`data_as_of`, `last_updated` via
  `api.data.gov.my/opendosm?id=…&meta=true`) and the storage ETag against the recorded
  baseline in `data/_vintage.json`; exits non-zero if a new vintage exists.
- `python3 sources/dosm/pipeline/refresh.py --apply` — pulls the new vintage with a
  row-level diff report, updates `_vintage.json`, rebuilds the derived denominators and
  re-runs the API cross-check. Then update the vintage table above, rebuild the
  dashboard, and commit the refresh as its own change.
- `python3 sources/dosm/pipeline/verify_against_api.py` — independent value-level
  cross-check of the canonical CSVs against the API (same publication, second door).

Per the API, the next scheduled DOSM releases are recorded in `data/_vintage.json`
(`next_update` per dataset).

## Derived output

`pipeline/build_denominators.py` regenerates `curated/dashboard/external_denominators.csv`
(unit conversions only: RM mil → RM bil, '000 → mil, count → mil; GDP total = `sector p0`
equivalent headline `gdp` column, population = `both`/`overall`/`overall` rows). Households
are absent after 2024 in the source and are left blank, never interpolated.

## Validation (2026-07-31 ingest)

- CSV downloads match the parquet mirrors of the same datasets (date-key join: 0 mismatches).
- Internal cross-check: `gdp_capita` as printed vs `gdp ÷ population` recomputed from the
  population dataset agrees to ≤0.03 % (rounding) for 2009–2025 — the two datasets are
  mutually consistent.
- vs the retired provisional numbers (`external_denominators.csv` before this ingest):
  GDP differences ≤ 0.28 % (vintage revisions, e.g. 2023 1819.0 → 1824.0,
  2022 1791.1 → 1793.9); population ≤ 0.98 % (largest at 2013); households up to
  **5.9 %** higher across 2020–2024 (the provisional series had not applied the 2020
  Census rebase). The provisional values were replaced wholesale, not merged.

## Known caveats

- GDP & population 2025 values and population 2026 are DOSM current estimates/projections
  (vintage above), subject to revision at the next annual release.
- `gdp_annual_nominal_supply` (sectoral dataset) carries slightly different totals for the
  same years (e.g. 2024: 1,933,209.415 vs 1,932,291.49 RM mil here) — different revision
  vintages between catalogue datasets. This source uses `gdp_gni_annual_nominal` throughout;
  do not mix the two.
- Households series is census-benchmarked at 1970/1980/1991/2000/2010/2020; intervening
  years are DOSM intercensal estimates (their methodology note, not ours).
