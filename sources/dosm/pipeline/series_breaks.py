#!/usr/bin/env python3
"""Build data/_series_breaks_dosm.csv — the register of discontinuities inside the
DOSM series this warehouse holds.

Why this file exists
--------------------
The fiscal sources in this warehouse are audited and reconcilable to the ringgit. The
real-economy sources are not: they are survey estimates whose *definitions* changed
inside the published series. HIES has run since 1970 and in that time changed its
geographic coverage, its population base, the number of states it can resolve, and —
twice — the poverty line itself. A chart of "poverty since 1970" drawn straight from
`hh_poverty.csv` is therefore not one series; it is several, drawn on one axis. The
same is true of the LFS across the 2020 Census rebase, and of the national accounts
across the 2015 base year.

So rather than silently presenting a continuous line (or, worse, "fixing" it — barred by
CLAUDE.md rule 2), every break is recorded here with the period it occurs at, what
changed, and the **source's own words**. Two kinds of row:

  source_caveat   lifted verbatim from the catalogue metadata (caveat_en /
                  methodology_en at github.com/data-gov-my/datagovmy-meta), one row per
                  distinct break the source itself declares. `source_note` is the
                  quoted text — nothing paraphrased into a number.
  observed        a discontinuity this pipeline observed in the data and could not
                  attribute to a caveat: the first/last period a series actually
                  carries, or a divergence between two DOSM datasets covering the same
                  concept. Flagged so it is not mistaken for a real economic movement.

The 2019 PLI revision is the case that matters most for the Agenda Ekonomi Negara: the
absolute-poverty rate for 2019 was republished at 5.6% on the new PLI against 0.4% on
the old one — a fourteen-fold difference that is entirely definitional. Both numbers
were official. Any "poverty fell/rose" claim spanning 2016->2019 is measuring the
methodology unless it says otherwise.

Run:  python3 sources/dosm/pipeline/series_breaks.py
"""
import csv
import json
import os
import re
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
META = ("https://raw.githubusercontent.com/data-gov-my/datagovmy-meta/main/"
        "data-catalogue/{}.json")

# Families of datasets that share a caveat, so the register says which files are affected
FAMILIES = {
    "hies_income": ["hh_income", "hh_income_state", "hh_income_district",
                    "hh_income_parlimen", "hh_income_dun", "hies_state", "hies_district",
                    "hies_malaysia_percentile", "hies_state_percentile"],
    "hies_inequality": ["hh_inequality", "hh_inequality_state", "hh_inequality_district",
                        "hh_inequality_parlimen", "hh_inequality_dun"],
    "hies_poverty": ["hh_poverty", "hh_poverty_state", "hh_poverty_district",
                     "hh_poverty_parlimen", "hh_poverty_dun"],
    "lfs": ["lfs_month", "lfs_month_sa", "lfs_month_status", "lfs_month_duration",
            "lfs_month_youth", "lfs_qtr", "lfs_qtr_state", "lfs_qtr_sru_age",
            "lfs_qtr_sru_sex", "lfs_qtr_tru_age", "lfs_qtr_tru_sex", "lfs_year",
            "lfs_year_sex", "lfs_state_sex", "lfs_district", "lfs_parlimen", "lfs_dun",
            "employment_sector"],
    "national_accounts": ["gdp_gni_annual_real", "gdp_annual_nominal_supply",
                          "gdp_annual_real_supply", "gdp_annual_nominal_demand",
                          "gdp_annual_real_demand", "gdp_annual_nominal_income",
                          "gdp_qtr_real", "gdp_qtr_nominal", "gdp_qtr_real_sa",
                          "gdp_state_real_supply", "productivity_annual",
                          "productivity_qtr"],
}
# One representative dataset per family whose catalogue caveat is quoted
CAVEAT_SOURCE = {"hies_income": "hh_income_state", "hies_inequality": "hh_inequality_state",
                 "hies_poverty": "hh_poverty_state", "lfs": "lfs_month",
                 "national_accounts": "gdp_annual_real_supply"}

# Breaks the register asserts, each anchored to the period it happens at and to the
# text the source publishes. `match` picks the caveat bullet that documents it.
BREAKS = [
    # series family, break period, what changed, caveat-bullet matcher
    ("hies_income", "1976", "geographic coverage: 1970 and 1974 cover Peninsular "
     "Malaysia only; Sabah and Sarawak enter the survey in 1976. Levels before and "
     "after 1976 are not the same population.", r"Peninsular Malaysia only"),
    ("hies_income", "1989", "population base: from 1989 the published statistics cover "
     "Malaysian citizens only, though non-citizens are surveyed.", r"citizens only"),
    ("hies_income", "1976", "state panel: W.P. Kuala Lumpur appears only from 1976 "
     "(gazetted 1974); before that its residents are inside Selangor.",
     r"Kuala Lumpur was gazzeted"),
    ("hies_income", "2007", "state panel: W.P. Labuan and W.P. Putrajaya appear only "
     "from 2007 in the income series; earlier residents sit inside Sabah and Selangor "
     "respectively. NOTE the poverty file dates Labuan from 2004, not 2007 — the two "
     "DOSM caveats disagree; both are recorded, neither is corrected.",
     r"Labuan was gazetted"),
    ("hies_poverty", "2007", "state panel: hh_poverty_state's caveat dates W.P. Labuan "
     "from 2004, while hh_income_state's dates it from 2007 for the same survey. "
     "Recorded as published.", r"Labuan was gazetted"),
    ("hies_income", "2019", "grain: district / parliament / DUN resolution begins in "
     "2019 — earlier HIES samples could not support it. There is no district series "
     "before 2019 to compare against.", r"district-level data is only published from 2019"),
    ("lfs", "2025", "population benchmark: LFS data before 2025 is compiled against the "
     "2010 Census, and from 2025 against the 2020 Census. The source states a trend "
     "break follows.", r"2010 Census"),
    ("national_accounts", "2015", "base year: constant-price series are on 2015=100. "
     "The catalogue's real GDP files start in 2015 for that reason; the long real "
     "GDP & GNI series (gdp_gni_annual_real, from 1970) is spliced across earlier "
     "base years by the source.", None),
]

# Breaks the source does not state as a caveat but which are load-bearing for any
# outcome measure. Each carries its own citation.
ASSERTED = [
    ("hies_poverty", "hh_poverty, hh_poverty_state, hh_poverty_district, "
     "hh_poverty_parlimen, hh_poverty_dun", "2019",
     "poverty line redefined (PLI revised with the 2019 HIES). The absolute-poverty "
     "headcount steps from {p_prev}% in {y_prev} to {p_new}% in {y_new} and hardcore "
     "poverty from {h_prev}% to {h_new}%, while median household income ROSE {inc:+.1f}% "
     "over the same interval — the step is the poverty line moving, not household "
     "welfare. Pre-2019 and 2019-onward absolute and hardcore poverty are NOT one series "
     "and must not be differenced. Relative poverty (below half the national median) is "
     "defined independently of the PLI and runs from 1995.",
     "DOSM, hh_poverty methodology_en: 'For full details on the methodology, especially "
     "the computation of the PLI and its evolution and nuances, please refer to the "
     "technical notes' — https://open.dosm.gov.my/publications/technical-notes/hies-technotes. "
     "Step sizes above are computed from the ingested hh_poverty.csv / hh_income.csv.",
     "source_caveat+observed"),
    ("hies_income", "hh_income, hh_income_state, hies_*", "all",
     "nominal, not real: every HIES income figure is in current prices and is NOT "
     "deflated. Comparing 1970 to 2024 income without applying cpi_headline measures "
     "inflation, not welfare.",
     "DOSM, hh_income caveat_en: 'This data presents nominal values, i.e. they have not "
     "been adjusted for inflation.'", "source_caveat"),
    ("hies_income", "hies_malaysia_percentile, hies_state_percentile", "all",
     "the percentile files carry materially larger relative standard errors than the "
     "headline mean/median, by construction. Treat single-percentile movements as "
     "noise unless corroborated.",
     "DOSM, hies_malaysia_percentile caveat_en: 'This data should be used with caution "
     "as the relative standard errors are larger due to the higher resolution.'",
     "source_caveat"),
    ("lfs", "lfs_year, lfs_year_sex, lfs_state_sex", "1991, 1994",
     "missing years: 1991 and 1994 are absent from the annual LFS series entirely "
     "(sample limitations), so an unbroken annual line through those years is "
     "interpolation, not data.",
     "DOSM, lfs_year caveat_en: 'Data for 1991 and 1994 are not available due to "
     "limitations in the sample data from those years.'", "source_caveat"),
    ("lfs", "lfs_month_sa, gdp_qtr_real_sa*", "all",
     "seasonally adjusted series are adjusted series-by-series (X-12-ARIMA + SEAM), so "
     "their components do NOT add to their totals. Verified: median |lf - (employed + "
     "unemployed)| in lfs_month_sa is 4.5 thousand. Use the unadjusted files for levels "
     "and any accounting identity.",
     "DOSM, gdp_qtr_real_sa methodology_en: 'Seasonal adjustment was conducted using "
     "X-12-ARIMA, augmented with the Seasonal Adjustment for Malaysia (SEAM) procedure'; "
     "verified in data/_validation_realeconomy.csv", "observed"),
    ("national_accounts", "gdp_annual_*, gdp_qtr_*, productivity_*", "rolling",
     "open vintages: the most recent years are provisional and are revised at the next "
     "release — GDP states 2024 and 2025 may be revised, the SA series names 2022-2024, "
     "productivity names the most recent 3 years, IPI the most recent 1 year, BOP and "
     "FDI the most recent 8 quarters, and trade the most recent 2 months. Any level "
     "taken from those windows is a moving target; _vintage.json pins which one we hold.",
     "DOSM, gdp_annual_nominal_supply caveat_en: 'Values for 2024 and 2025 may be "
     "revised in future releases.'", "source_caveat"),
    ("hies_income", "hh_access_amenities", "2024",
     "the 2024 wave was published mid-ingest and revised 2022 as well as adding 2024: "
     "the file first retrieved ended at 2022, and within the same session the storage "
     "CSV moved to the 2024 wave with the overlapping 2022 values changed. The warehouse "
     "holds the 2024-wave file. Anyone holding an earlier copy of this dataset has "
     "different 2022 numbers — the reason every DOSM file here is vintage-pinned in "
     "data/_vintage.json rather than assumed stable.",
     "observed 2026-08-01 by pipeline/verify_realeconomy.py (parquet and API mirrors "
     "carried 2024 before the CSV did) and confirmed by pipeline/refresh.py detecting "
     "the new vintage (data_as_of 2022 -> 2024)", "observed"),
    ("lfs", "lfs_year_sex, lfs_state_sex", "all",
     "ep_ratio is not comparable across LFS datasets: lfs_year's ep_ratio reproduces "
     "100*employed/(lf+outside) exactly, but lfs_year_sex and lfs_state_sex publish a "
     "different ep_ratio for identical labour-force levels in the same year (e.g. 1982: "
     "62.7 vs 62.5; 2008: 60.6 vs 58.1). Join ep_ratio from one dataset only.",
     "observed 2026-08-01 by pipeline/verify_realeconomy.py; 1,464 of 1,732 lfs_state_sex "
     "rows breach the identity, median 1.38pp, max 45pp — see "
     "data/_identity_breaches_realeconomy.csv", "observed"),
    ("lfs", "lfs_district, lfs_parlimen, lfs_dun", "2020-2023",
     "small-area cells that do not add up: at district/parliament/DUN grain some "
     "published rows have lf != employed + unemployed by far more than rounding "
     "(lfs_dun max 109.7 thousand at Johor N.49 Kota Iskandar 2023; lfs_district "
     "Sabah/Tongod 2020 prints lf=83.0 between 22.8 in 2019 and 14.9 in 2021, and its "
     "p_rate/ep_ratio are computed from that outlier). Kept as published; do not "
     "aggregate small-area LFS cells to a state or national total.",
     "observed 2026-08-01 by pipeline/verify_realeconomy.py; every breaching row listed "
     "in data/_identity_breaches_realeconomy.csv", "observed"),
    ("hies_income", "hies_malaysia_percentile", "2022",
     "the 2022 percentile distribution does not average back to the published 2022 "
     "mean: mean of the 100 percentile means is RM 8,359.7 against a published mean of "
     "RM 8,479 (-1.4%). The 2019 and 2024 waves reconcile to within 0.03%. Use the "
     "headline mean for 2022 levels and the percentile file for shape only.",
     "observed 2026-08-01 by pipeline/verify_realeconomy.py", "observed"),
]


def fetch_meta(ids):
    def one(i):
        try:
            with urllib.request.urlopen(META.format(i), timeout=60) as r:
                return i, json.loads(r.read())
        except Exception as e:                                 # noqa: BLE001
            return i, {"_error": str(e)}
    with ThreadPoolExecutor(max_workers=8) as ex:
        return dict(ex.map(one, ids))


def bullet(text, pattern):
    """The single caveat sentence/bullet documenting a break — quoted, never rewritten."""
    if not text or not pattern:
        return ""
    for part in re.split(r"\n\s*-\s*|\n\n", text):
        if re.search(pattern, part):
            return " ".join(part.split()).strip(" -")
    return ""


def pli_step():
    """Measure the 2019 poverty-line break from the ingested files, don't assert it."""
    def rows_of(f):
        with open(os.path.join(DATA, f)) as fh:
            return list(csv.DictReader(fh))
    pov = {r["date"][:4]: r for r in rows_of("hh_poverty.csv")}
    inc = {r["date"][:4]: r for r in rows_of("hh_income.csv")}
    years = sorted(pov)
    y_new = "2019"
    y_prev = years[years.index(y_new) - 1]
    a, b = pov[y_prev], pov[y_new]
    i0, i1 = float(inc[y_prev]["income_median"]), float(inc[y_new]["income_median"])
    return {"y_prev": y_prev, "y_new": y_new,
            "p_prev": a["poverty_absolute"], "p_new": b["poverty_absolute"],
            "h_prev": a["poverty_hardcore"], "h_new": b["poverty_hardcore"],
            "inc": (i1 / i0 - 1) * 100}


def main():
    meta = fetch_meta(sorted(set(CAVEAT_SOURCE.values())))
    measured = pli_step()
    rows = []
    for fam, period, what, pattern in BREAKS:
        src = CAVEAT_SOURCE[fam]
        m = meta.get(src, {})
        quote = bullet(m.get("caveat_en", ""), pattern) or bullet(m.get("methodology_en", ""), pattern)
        rows.append([fam, ", ".join(FAMILIES[fam]), period, what,
                     (f"DOSM, {src} caveat_en: \"{quote}\"" if quote else
                      f"DOSM, {src} catalogue entry (no single bullet; see methodology_en)"),
                     "source_caveat" if quote else "observed",
                     f"https://open.dosm.gov.my/data-catalogue/{src}"])
    for fam, files, period, what, note, kind in ASSERTED:
        rows.append([fam, files, period, what.format(**measured), note, kind,
                     f"https://open.dosm.gov.my/data-catalogue/{CAVEAT_SOURCE[fam]}"])

    dest = os.path.join(DATA, "_series_breaks_dosm.csv")
    with open(dest, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series_family", "datasets_affected", "break_period", "what_changed",
                    "source_note", "evidence_type", "catalogue_url"])
        w.writerows(rows)
    kinds = defaultdict(int)
    for r in rows:
        kinds[r[5]] += 1
    print(f"{len(rows)} series breaks -> {dest}")
    for k, v in sorted(kinds.items()):
        print(f"  {k}: {v}")
    for r in rows:
        print(f"  [{r[0]}] {r[2]}: {r[3][:88]}")


if __name__ == "__main__":
    main()
