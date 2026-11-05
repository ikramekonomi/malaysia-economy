"""Per-state volume manifest and per-state source knowledge.  THE ONLY
state-specific file in this pipeline.

To add a 14th jurisdiction, add a key to `VOLUMES` with its Command Papers (and,
if it levies a revenue head no other state levies, a rule in
`STATE_REVENUE_CLASSES`).  Nothing else changes.

`fiscal_year` is the state financial year the volume AUDITS.  It is read from
each volume's OWN front matter - the section heading `PENYATA KEWANGAN KERAJAAN
NEGERI <state> BAGI TAHUN BERAKHIR 31 DISEMBER <year>` and the cover's `TAHUN
<year>` - never inferred from the Command-Paper year.  `pipeline/verify_covers.py`
re-derives every value here from the PDFs and fails on any mismatch.

`agency_fiscal_year` is the year of the AGENCY statements the volume's
*penyerahan* (submission) register covers: the same year as the state statements
in eras 1-3, one year behind from era 4.  It is a MANIFEST convenience only -
`fact_state_agency_sijil_*.fiscal_year_agency` is read from each register's own
printed heading, because the *sijil* (opinion) register in the same volume
usually covers a different year again.

Era map (identical in all 13 states - the Jabatan Audit Negara re-templated the
whole series at once, verified by the JADUAL numbering in every volume):

  e1_jadual_4x_titlecase  tabled 2015-2016  FY2014-FY2015  `Jadual 4.1` title case
  e2_jadual_4x_caps       tabled 2017-2018  FY2016-FY2017  `JADUAL 4.1` all caps
  e3_jadual_serial        tabled 2019-2023  FY2018-FY2022  `JADUAL 1` serial
  e4_lkan_serial          tabled 2024-2025  FY2023-FY2024  `JADUAL 1`, LKAN n/YYYY
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# volume manifest
# ---------------------------------------------------------------------------
# file_name, fiscal_year, agency_fiscal_year, report, command_paper, era, scope

VOLUMES: dict[str, list[dict]] = {
    "Johor": [
        dict(file="CMD.51.2015.pdf", fiscal_year=2014, agency_fiscal_year=2014,
             report="LKAN Negeri Johor 2014", command_paper="CMD.51.2015",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.35.2016.pdf", fiscal_year=2015, agency_fiscal_year=2015,
             report="LKAN Negeri Johor 2015", command_paper="CMD.35.2016",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.33.2017.pdf", fiscal_year=2016, agency_fiscal_year=2016,
             report="LKAN Negeri Johor 2016", command_paper="CMD.33.2017",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.33.2018.pdf", fiscal_year=2017, agency_fiscal_year=2017,
             report="LKAN Negeri Johor 2017", command_paper="CMD.33.2018",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.30.2019.pdf", fiscal_year=2018, agency_fiscal_year=2018,
             report="LKAN Negeri Johor 2018", command_paper="CMD.30.2019",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.29.2020.pdf", fiscal_year=2019, agency_fiscal_year=2019,
             report="LKAN Negeri Johor 2019", command_paper="CMD.29.2020",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.39.2021.pdf", fiscal_year=2020, agency_fiscal_year=2020,
             report="LKAN Negeri Johor 2020", command_paper="CMD.39.2021",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.41.2022.pdf", fiscal_year=2021, agency_fiscal_year=2021,
             report="LKAN Negeri Johor 2021", command_paper="CMD.41.2022",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.38.2023.pdf", fiscal_year=2022, agency_fiscal_year=2022,
             report="LKAN Negeri Johor 2022", command_paper="CMD.38.2023",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.19.2024.pdf", fiscal_year=2023, agency_fiscal_year=2022,
             report="LKAN 3/2024", command_paper="CMD.19.2024",
             era="e4_lkan_serial", scope="state_financial_statements"),
        dict(file="CMD.15.2025.pdf", fiscal_year=2024, agency_fiscal_year=2023,
             report="LKAN 3/2025", command_paper="CMD.15.2025",
             era="e4_lkan_serial", scope="state_financial_statements"),
    ],
    "Kedah": [
        dict(file="CMD.50.2015.pdf", fiscal_year=2014, agency_fiscal_year=2014,
             report="LKAN Negeri Kedah 2014", command_paper="CMD.50.2015",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.34.2016.pdf", fiscal_year=2015, agency_fiscal_year=2015,
             report="LKAN Negeri Kedah 2015", command_paper="CMD.34.2016",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.34.2017.pdf", fiscal_year=2016, agency_fiscal_year=2016,
             report="LKAN Negeri Kedah 2016", command_paper="CMD.34.2017",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.34.2018.pdf", fiscal_year=2017, agency_fiscal_year=2017,
             report="LKAN Negeri Kedah 2017", command_paper="CMD.34.2018",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.47.2018.pdf", fiscal_year=None, agency_fiscal_year=None,
             report="LKAN 2017 Siri 2", command_paper="CMD.47.2018",
             era="e2_jadual_4x_caps", scope="state_activity_management"),
        dict(file="CMD.31.2019.pdf", fiscal_year=2018, agency_fiscal_year=2018,
             report="LKAN Negeri Kedah 2018", command_paper="CMD.31.2019",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.30.2020.pdf", fiscal_year=2019, agency_fiscal_year=2019,
             report="LKAN Negeri Kedah 2019", command_paper="CMD.30.2020",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.40.2021.pdf", fiscal_year=2020, agency_fiscal_year=2020,
             report="LKAN Negeri Kedah 2020", command_paper="CMD.40.2021",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.42.2022.pdf", fiscal_year=2021, agency_fiscal_year=2021,
             report="LKAN Negeri Kedah 2021", command_paper="CMD.42.2022",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.39.2023.pdf", fiscal_year=2022, agency_fiscal_year=2022,
             report="LKAN Negeri Kedah 2022", command_paper="CMD.39.2023",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.20.2024.pdf", fiscal_year=2023, agency_fiscal_year=2022,
             report="LKAN 3/2024", command_paper="CMD.20.2024",
             era="e4_lkan_serial", scope="state_financial_statements"),
        dict(file="CMD.16.2025.pdf", fiscal_year=2024, agency_fiscal_year=2023,
             report="LKAN 3/2025", command_paper="CMD.16.2025",
             era="e4_lkan_serial", scope="state_financial_statements"),
    ],
    "Kelantan": [
        dict(file="CMD.52.2015.pdf", fiscal_year=2014, agency_fiscal_year=2014,
             report="LKAN Negeri Kelantan 2014", command_paper="CMD.52.2015",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.36.2016.pdf", fiscal_year=2015, agency_fiscal_year=2015,
             report="LKAN Negeri Kelantan 2015", command_paper="CMD.36.2016",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.32.2017.pdf", fiscal_year=2016, agency_fiscal_year=2016,
             report="LKAN Negeri Kelantan 2016", command_paper="CMD.32.2017",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.35.2018.pdf", fiscal_year=2017, agency_fiscal_year=2017,
             report="LKAN Negeri Kelantan 2017", command_paper="CMD.35.2018",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.32.2019.pdf", fiscal_year=2018, agency_fiscal_year=2018,
             report="LKAN Negeri Kelantan 2018", command_paper="CMD.32.2019",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.31.2020.pdf", fiscal_year=2019, agency_fiscal_year=2019,
             report="LKAN Negeri Kelantan 2019", command_paper="CMD.31.2020",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.41.2021.pdf", fiscal_year=2020, agency_fiscal_year=2020,
             report="LKAN Negeri Kelantan 2020", command_paper="CMD.41.2021",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.43.2022.pdf", fiscal_year=2021, agency_fiscal_year=2021,
             report="LKAN Negeri Kelantan 2021", command_paper="CMD.43.2022",
             era="e3_jadual_serial", scope="state_financial_statements"),
        # Kelantan FY2022 IS this volume - its cover reads "PENYATA KEWANGAN
        # KERAJAAN NEGERI DAN AGENSI NEGERI ... KELANTAN TAHUN 2O22" - but the
        # whole 210-page body is an IMAGE-ONLY scan: `pdftotext -layout`
        # returns 3 characters per page and zero JADUAL headings.  Nothing can
        # be extracted from the text layer, so it is declared here and logged in
        # `_unparsed_tables_kelantan.csv` rather than silently omitted.
        dict(file="CMD.40.2023.pdf", fiscal_year=2022, agency_fiscal_year=2022,
             report="LKAN Negeri Kelantan 2022", command_paper="CMD.40.2023",
             era="e3_jadual_serial", scope="state_financial_statements",
             text_layer="image_only"),
        dict(file="CMD.21.2024.pdf", fiscal_year=2023, agency_fiscal_year=2022,
             report="LKAN 3/2024", command_paper="CMD.21.2024",
             era="e4_lkan_serial", scope="state_financial_statements"),
        dict(file="CMD.17.2025.pdf", fiscal_year=2024, agency_fiscal_year=2023,
             report="LKAN 3/2025", command_paper="CMD.17.2025",
             era="e4_lkan_serial", scope="state_financial_statements"),
    ],
    "Melaka": [
        dict(file="CMD.53.2015.pdf", fiscal_year=2014, agency_fiscal_year=2014,
             report="LKAN Negeri Melaka 2014", command_paper="CMD.53.2015",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.37.2016.pdf", fiscal_year=2015, agency_fiscal_year=2015,
             report="LKAN Negeri Melaka 2015", command_paper="CMD.37.2016",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.35.2017.pdf", fiscal_year=2016, agency_fiscal_year=2016,
             report="LKAN Negeri Melaka 2016", command_paper="CMD.35.2017",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.36.2018.pdf", fiscal_year=2017, agency_fiscal_year=2017,
             report="LKAN Negeri Melaka 2017", command_paper="CMD.36.2018",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.33.2019.pdf", fiscal_year=2018, agency_fiscal_year=2018,
             report="LKAN Negeri Melaka 2018", command_paper="CMD.33.2019",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.32.2020.pdf", fiscal_year=2019, agency_fiscal_year=2019,
             report="LKAN Negeri Melaka 2019", command_paper="CMD.32.2020",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.42.2021.pdf", fiscal_year=2020, agency_fiscal_year=2020,
             report="LKAN Negeri Melaka 2020", command_paper="CMD.42.2021",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.44.2022.pdf", fiscal_year=2021, agency_fiscal_year=2021,
             report="LKAN Negeri Melaka 2021", command_paper="CMD.44.2022",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.41.2023.pdf", fiscal_year=2022, agency_fiscal_year=2022,
             report="LKAN Negeri Melaka 2022", command_paper="CMD.41.2023",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.22.2024.pdf", fiscal_year=2023, agency_fiscal_year=2022,
             report="LKAN 3/2024", command_paper="CMD.22.2024",
             era="e4_lkan_serial", scope="state_financial_statements"),
        dict(file="CMD.18.2025.pdf", fiscal_year=2024, agency_fiscal_year=2023,
             report="LKAN 3/2025", command_paper="CMD.18.2025",
             era="e4_lkan_serial", scope="state_financial_statements"),
    ],
    "Negeri Sembilan": [
        dict(file="CMD.54.2015.pdf", fiscal_year=2014, agency_fiscal_year=2014,
             report="LKAN Negeri Negeri Sembilan 2014", command_paper="CMD.54.2015",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.36.2017.pdf", fiscal_year=2016, agency_fiscal_year=2016,
             report="LKAN Negeri Negeri Sembilan 2016", command_paper="CMD.36.2017",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.37.2018.pdf", fiscal_year=2017, agency_fiscal_year=2017,
             report="LKAN Negeri Negeri Sembilan 2017", command_paper="CMD.37.2018",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.34.2019.pdf", fiscal_year=2018, agency_fiscal_year=2018,
             report="LKAN Negeri Negeri Sembilan 2018", command_paper="CMD.34.2019",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.33.2020.pdf", fiscal_year=2019, agency_fiscal_year=2019,
             report="LKAN Negeri Negeri Sembilan 2019", command_paper="CMD.33.2020",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.43.2021.pdf", fiscal_year=2020, agency_fiscal_year=2020,
             report="LKAN Negeri Negeri Sembilan 2020", command_paper="CMD.43.2021",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.45.2022.pdf", fiscal_year=2021, agency_fiscal_year=2021,
             report="LKAN Negeri Negeri Sembilan 2021", command_paper="CMD.45.2022",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.42.2023.pdf", fiscal_year=2022, agency_fiscal_year=2022,
             report="LKAN Negeri Negeri Sembilan 2022", command_paper="CMD.42.2023",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.23.2024.pdf", fiscal_year=2023, agency_fiscal_year=2022,
             report="LKAN 3/2024", command_paper="CMD.23.2024",
             era="e4_lkan_serial", scope="state_financial_statements"),
        dict(file="CMD.19.2025.pdf", fiscal_year=2024, agency_fiscal_year=2023,
             report="LKAN 3/2025", command_paper="CMD.19.2025",
             era="e4_lkan_serial", scope="state_financial_statements"),
    ],
    "Pahang": [
        dict(file="CMD.55.2015.pdf", fiscal_year=2014, agency_fiscal_year=2014,
             report="LKAN Negeri Pahang 2014", command_paper="CMD.55.2015",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.39.2016.pdf", fiscal_year=2015, agency_fiscal_year=2015,
             report="LKAN Negeri Pahang 2015", command_paper="CMD.39.2016",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.37.2017.pdf", fiscal_year=2016, agency_fiscal_year=2016,
             report="LKAN Negeri Pahang 2016", command_paper="CMD.37.2017",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.38.2018.pdf", fiscal_year=2017, agency_fiscal_year=2017,
             report="LKAN Negeri Pahang 2017", command_paper="CMD.38.2018",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.35.2019.pdf", fiscal_year=2018, agency_fiscal_year=2018,
             report="LKAN Negeri Pahang 2018", command_paper="CMD.35.2019",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.35.2020.pdf", fiscal_year=2019, agency_fiscal_year=2019,
             report="LKAN Negeri Pahang 2019", command_paper="CMD.35.2020",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.44.2021.pdf", fiscal_year=2020, agency_fiscal_year=2020,
             report="LKAN Negeri Pahang 2020", command_paper="CMD.44.2021",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.46.2022.pdf", fiscal_year=2021, agency_fiscal_year=2021,
             report="LKAN Negeri Pahang 2021", command_paper="CMD.46.2022",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.43.2023.pdf", fiscal_year=2022, agency_fiscal_year=2022,
             report="LKAN Negeri Pahang 2022", command_paper="CMD.43.2023",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.24.2024.pdf", fiscal_year=2023, agency_fiscal_year=2022,
             report="LKAN 3/2024", command_paper="CMD.24.2024",
             era="e4_lkan_serial", scope="state_financial_statements"),
        dict(file="CMD.20.2025.pdf", fiscal_year=2024, agency_fiscal_year=2023,
             report="LKAN 3/2025", command_paper="CMD.20.2025",
             era="e4_lkan_serial", scope="state_financial_statements"),
    ],
    "Perak": [
        dict(file="CMD.56.2015.pdf", fiscal_year=2014, agency_fiscal_year=2014,
             report="LKAN Negeri Perak 2014", command_paper="CMD.56.2015",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.38.2017.pdf", fiscal_year=2016, agency_fiscal_year=2016,
             report="LKAN Negeri Perak 2016", command_paper="CMD.38.2017",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.39.2018.pdf", fiscal_year=2017, agency_fiscal_year=2017,
             report="LKAN Negeri Perak 2017", command_paper="CMD.39.2018",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.52.2018.pdf", fiscal_year=None, agency_fiscal_year=None,
             report="LKAN 2017 Siri 2", command_paper="CMD.52.2018",
             era="e2_jadual_4x_caps", scope="state_activity_management"),
        dict(file="CMD.36.2019.pdf", fiscal_year=2018, agency_fiscal_year=2018,
             report="LKAN Negeri Perak 2018", command_paper="CMD.36.2019",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.36.2020.pdf", fiscal_year=2019, agency_fiscal_year=2019,
             report="LKAN Negeri Perak 2019", command_paper="CMD.36.2020",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.45.2021.pdf", fiscal_year=2020, agency_fiscal_year=2020,
             report="LKAN Negeri Perak 2020", command_paper="CMD.45.2021",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.47.2022.pdf", fiscal_year=2021, agency_fiscal_year=2021,
             report="LKAN Negeri Perak 2021", command_paper="CMD.47.2022",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.44.2023.pdf", fiscal_year=2022, agency_fiscal_year=2022,
             report="LKAN Negeri Perak 2022", command_paper="CMD.44.2023",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.25.2024.pdf", fiscal_year=2023, agency_fiscal_year=2022,
             report="LKAN 3/2024", command_paper="CMD.25.2024",
             era="e4_lkan_serial", scope="state_financial_statements"),
        dict(file="CMD.21.2025.pdf", fiscal_year=2024, agency_fiscal_year=2023,
             report="LKAN 3/2025", command_paper="CMD.21.2025",
             era="e4_lkan_serial", scope="state_financial_statements"),
    ],
    "Perlis": [
        dict(file="CMD.57.2015.pdf", fiscal_year=2014, agency_fiscal_year=2014,
             report="LKAN Negeri Perlis 2014", command_paper="CMD.57.2015",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.41.2016.pdf", fiscal_year=2015, agency_fiscal_year=2015,
             report="LKAN Negeri Perlis 2015", command_paper="CMD.41.2016",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.39.2017.pdf", fiscal_year=2016, agency_fiscal_year=2016,
             report="LKAN Negeri Perlis 2016", command_paper="CMD.39.2017",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.40.2018.pdf", fiscal_year=2017, agency_fiscal_year=2017,
             report="LKAN Negeri Perlis 2017", command_paper="CMD.40.2018",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.37.2019.pdf", fiscal_year=2018, agency_fiscal_year=2018,
             report="LKAN Negeri Perlis 2018", command_paper="CMD.37.2019",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.37.2020.pdf", fiscal_year=2019, agency_fiscal_year=2019,
             report="LKAN Negeri Perlis 2019", command_paper="CMD.37.2020",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.46.2021.pdf", fiscal_year=2020, agency_fiscal_year=2020,
             report="LKAN Negeri Perlis 2020", command_paper="CMD.46.2021",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.48.2022.pdf", fiscal_year=2021, agency_fiscal_year=2021,
             report="LKAN Negeri Perlis 2021", command_paper="CMD.48.2022",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.45.2023.pdf", fiscal_year=2022, agency_fiscal_year=2022,
             report="LKAN Negeri Perlis 2022", command_paper="CMD.45.2023",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.26.2024.pdf", fiscal_year=2023, agency_fiscal_year=2022,
             report="LKAN 3/2024", command_paper="CMD.26.2024",
             era="e4_lkan_serial", scope="state_financial_statements"),
        dict(file="CMD.22.2025.pdf", fiscal_year=2024, agency_fiscal_year=2023,
             report="LKAN 3/2025", command_paper="CMD.22.2025",
             era="e4_lkan_serial", scope="state_financial_statements"),
    ],
    "Pulau Pinang": [
        dict(file="CMD.58.2015.pdf", fiscal_year=2014, agency_fiscal_year=2014,
             report="LKAN Negeri Pulau Pinang 2014", command_paper="CMD.58.2015",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.40.2017.pdf", fiscal_year=2016, agency_fiscal_year=2016,
             report="LKAN Negeri Pulau Pinang 2016", command_paper="CMD.40.2017",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.41.2018.pdf", fiscal_year=2017, agency_fiscal_year=2017,
             report="LKAN Negeri Pulau Pinang 2017", command_paper="CMD.41.2018",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.53.2018.pdf", fiscal_year=None, agency_fiscal_year=None,
             report="LKAN 2017 Siri 2", command_paper="CMD.53.2018",
             era="e2_jadual_4x_caps", scope="state_activity_management"),
        dict(file="CMD.38.2019.pdf", fiscal_year=2018, agency_fiscal_year=2018,
             report="LKAN Negeri Pulau Pinang 2018", command_paper="CMD.38.2019",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.34.2020.pdf", fiscal_year=2019, agency_fiscal_year=2019,
             report="LKAN Negeri Pulau Pinang 2019", command_paper="CMD.34.2020",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.47.2021.pdf", fiscal_year=2020, agency_fiscal_year=2020,
             report="LKAN Negeri Pulau Pinang 2020", command_paper="CMD.47.2021",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.49.2022.pdf", fiscal_year=2021, agency_fiscal_year=2021,
             report="LKAN Negeri Pulau Pinang 2021", command_paper="CMD.49.2022",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.46.2023.pdf", fiscal_year=2022, agency_fiscal_year=2022,
             report="LKAN Negeri Pulau Pinang 2022", command_paper="CMD.46.2023",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.27.2024.pdf", fiscal_year=2023, agency_fiscal_year=2022,
             report="LKAN 3/2024", command_paper="CMD.27.2024",
             era="e4_lkan_serial", scope="state_financial_statements"),
        dict(file="CMD.23.2025.pdf", fiscal_year=2024, agency_fiscal_year=2023,
             report="LKAN 3/2025", command_paper="CMD.23.2025",
             era="e4_lkan_serial", scope="state_financial_statements"),
    ],
    "Sabah": [
        dict(file="CMD.59.2015.pdf", fiscal_year=2014, agency_fiscal_year=2014,
             report="LKAN Negeri Sabah 2014", command_paper="CMD.59.2015",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.43.2016.pdf", fiscal_year=2015, agency_fiscal_year=2015,
             report="LKAN Negeri Sabah 2015", command_paper="CMD.43.2016",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.41.2017.pdf", fiscal_year=2016, agency_fiscal_year=2016,
             report="LKAN Negeri Sabah 2016", command_paper="CMD.41.2017",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.42.2018.pdf", fiscal_year=2017, agency_fiscal_year=2017,
             report="LKAN Negeri Sabah 2017", command_paper="CMD.42.2018",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.39.2019.pdf", fiscal_year=2018, agency_fiscal_year=2018,
             report="LKAN Negeri Sabah 2018", command_paper="CMD.39.2019",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.38.2020.pdf", fiscal_year=2019, agency_fiscal_year=2019,
             report="LKAN Negeri Sabah 2019", command_paper="CMD.38.2020",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.48.2021.pdf", fiscal_year=2020, agency_fiscal_year=2020,
             report="LKAN Negeri Sabah 2020", command_paper="CMD.48.2021",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.50.2022.pdf", fiscal_year=2021, agency_fiscal_year=2021,
             report="LKAN Negeri Sabah 2021", command_paper="CMD.50.2022",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.47.2023.pdf", fiscal_year=2022, agency_fiscal_year=2022,
             report="LKAN Negeri Sabah 2022", command_paper="CMD.47.2023",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.28.2024.pdf", fiscal_year=2023, agency_fiscal_year=2022,
             report="LKAN 3/2024", command_paper="CMD.28.2024",
             era="e4_lkan_serial", scope="state_financial_statements"),
        dict(file="CMD.24.2025.pdf", fiscal_year=2024, agency_fiscal_year=2023,
             report="LKAN 3/2025", command_paper="CMD.24.2025",
             era="e4_lkan_serial", scope="state_financial_statements"),
    ],
    "Sarawak": [
        dict(file="CMD.60.2015.pdf", fiscal_year=2014, agency_fiscal_year=2014,
             report="LKAN Negeri Sarawak 2014", command_paper="CMD.60.2015",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.44.2016.pdf", fiscal_year=2015, agency_fiscal_year=2015,
             report="LKAN Negeri Sarawak 2015", command_paper="CMD.44.2016",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.43.2018.pdf", fiscal_year=2017, agency_fiscal_year=2017,
             report="LKAN Negeri Sarawak 2017", command_paper="CMD.43.2018",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.40.2019.pdf", fiscal_year=2018, agency_fiscal_year=2018,
             report="LKAN Negeri Sarawak 2018", command_paper="CMD.40.2019",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.39.2020.pdf", fiscal_year=2019, agency_fiscal_year=2019,
             report="LKAN Negeri Sarawak 2019", command_paper="CMD.39.2020",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.49.2021.pdf", fiscal_year=2020, agency_fiscal_year=2020,
             report="LKAN Negeri Sarawak 2020", command_paper="CMD.49.2021",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.51.2022.pdf", fiscal_year=2021, agency_fiscal_year=2021,
             report="LKAN Negeri Sarawak 2021", command_paper="CMD.51.2022",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.48.2023.pdf", fiscal_year=2022, agency_fiscal_year=2022,
             report="LKAN Negeri Sarawak 2022", command_paper="CMD.48.2023",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.29.2024.pdf", fiscal_year=2023, agency_fiscal_year=2022,
             report="LKAN 3/2024", command_paper="CMD.29.2024",
             era="e4_lkan_serial", scope="state_financial_statements"),
        # Sarawak FY2024.  Its cover carries no `TAHUN BERAKHIR 31 DISEMBER`
        # line and its text layer is PARTIAL (183 pp at ~240 characters a page,
        # 10 JADUAL blocks against 50-120 in a fully-typeset volume), so it was
        # missed by the Penyata-Kewangan title filter.  What the text layer
        # does give is extracted; the rest is image-only and declared.
        dict(file="CMD.25.2025.pdf", fiscal_year=2024, agency_fiscal_year=2023,
             report="LKAN 3/2025", command_paper="CMD.25.2025",
             era="e4_lkan_serial", scope="state_financial_statements",
             text_layer="partial"),
    ],
    "Selangor": [
        dict(file="CMD.61.2015.pdf", fiscal_year=2014, agency_fiscal_year=2014,
             report="LKAN Negeri Selangor 2014", command_paper="CMD.61.2015",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.45.2016.pdf", fiscal_year=2015, agency_fiscal_year=2015,
             report="LKAN Negeri Selangor 2015", command_paper="CMD.45.2016",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.43.2017.pdf", fiscal_year=2016, agency_fiscal_year=2016,
             report="LKAN Negeri Selangor 2016", command_paper="CMD.43.2017",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.44.2018.pdf", fiscal_year=2017, agency_fiscal_year=2017,
             report="LKAN Negeri Selangor 2017", command_paper="CMD.44.2018",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.56.2018.pdf", fiscal_year=None, agency_fiscal_year=None,
             report="LKAN 2017 Siri 2", command_paper="CMD.56.2018",
             era="e2_jadual_4x_caps", scope="state_activity_management"),
        dict(file="CMD.41.2019.pdf", fiscal_year=2018, agency_fiscal_year=2018,
             report="LKAN Negeri Selangor 2018", command_paper="CMD.41.2019",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.40.2020.pdf", fiscal_year=2019, agency_fiscal_year=2019,
             report="LKAN Negeri Selangor 2019", command_paper="CMD.40.2020",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.50.2021.pdf", fiscal_year=2020, agency_fiscal_year=2020,
             report="LKAN Negeri Selangor 2020", command_paper="CMD.50.2021",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.52.2022.pdf", fiscal_year=2021, agency_fiscal_year=2021,
             report="LKAN Negeri Selangor 2021", command_paper="CMD.52.2022",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.49.2023.pdf", fiscal_year=2022, agency_fiscal_year=2022,
             report="LKAN Negeri Selangor 2022", command_paper="CMD.49.2023",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.30.2024.pdf", fiscal_year=2023, agency_fiscal_year=2022,
             report="LKAN 3/2024", command_paper="CMD.30.2024",
             era="e4_lkan_serial", scope="state_financial_statements"),
        dict(file="CMD.26.2025.pdf", fiscal_year=2024, agency_fiscal_year=2023,
             report="LKAN 3/2025", command_paper="CMD.26.2025",
             era="e4_lkan_serial", scope="state_financial_statements"),
        # Carries Selangor state audit work but NO state financial statements:
        # LKAN 1/2026 is the company-management / e-SelfAudit volume.
        dict(file="CMD.14.2026.pdf", fiscal_year=None, agency_fiscal_year=None,
             report="LKAN 1/2026", command_paper="CMD.14.2026",
             era="e4_lkan_serial", scope="state_company_management"),
    ],
    "Terengganu": [
        dict(file="CMD.46.2016.pdf", fiscal_year=2015, agency_fiscal_year=2015,
             report="LKAN Negeri Terengganu 2015", command_paper="CMD.46.2016",
             era="e1_jadual_4x_titlecase", scope="state_financial_statements"),
        dict(file="CMD.44.2017.pdf", fiscal_year=2016, agency_fiscal_year=2016,
             report="LKAN Negeri Terengganu 2016", command_paper="CMD.44.2017",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.45.2018.pdf", fiscal_year=2017, agency_fiscal_year=2017,
             report="LKAN Negeri Terengganu 2017", command_paper="CMD.45.2018",
             era="e2_jadual_4x_caps", scope="state_financial_statements"),
        dict(file="CMD.42.2019.pdf", fiscal_year=2018, agency_fiscal_year=2018,
             report="LKAN Negeri Terengganu 2018", command_paper="CMD.42.2019",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.41.2020.pdf", fiscal_year=2019, agency_fiscal_year=2019,
             report="LKAN Negeri Terengganu 2019", command_paper="CMD.41.2020",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.51.2021.pdf", fiscal_year=2020, agency_fiscal_year=2020,
             report="LKAN Negeri Terengganu 2020", command_paper="CMD.51.2021",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.53.2022.pdf", fiscal_year=2021, agency_fiscal_year=2021,
             report="LKAN Negeri Terengganu 2021", command_paper="CMD.53.2022",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.50.2023.pdf", fiscal_year=2022, agency_fiscal_year=2022,
             report="LKAN Negeri Terengganu 2022", command_paper="CMD.50.2023",
             era="e3_jadual_serial", scope="state_financial_statements"),
        dict(file="CMD.31.2024.pdf", fiscal_year=2023, agency_fiscal_year=2022,
             report="LKAN 3/2024", command_paper="CMD.31.2024",
             era="e4_lkan_serial", scope="state_financial_statements"),
        dict(file="CMD.27.2025.pdf", fiscal_year=2024, agency_fiscal_year=2023,
             report="LKAN 3/2025", command_paper="CMD.27.2025",
             era="e4_lkan_serial", scope="state_financial_statements"),
    ],
}


STATES: list[str] = list(VOLUMES)


def slug(state: str) -> str:
    return state.lower().replace(" ", "_")


# ---------------------------------------------------------------------------
# per-state revenue heads
# ---------------------------------------------------------------------------
# The Akta Tatacara Kewangan 1957 gives every state the same FUND structure, but
# NOT the same revenue heads.  Anything a state levies that no other state
# levies belongs here, not in `table_catalog.REVENUE_CLASSES`, so that a
# Peninsular state can never acquire a Borneo revenue class by accident.
#
# `NATIONAL_REVENUE_CLASSES` are label-driven and safe everywhere (a state that
# does not levy the head simply never prints the label); `STATE_REVENUE_CLASSES`
# is checked FIRST and only for that state.
#
# Sources for the substantive claims below: Perjanjian Malaysia 1963 art. VIII
# + Perlembagaan Persekutuan Jadual Kesepuluh Bhg. III/V (Sabah & Sarawak's
# additional sources, incl. the 5% petroleum cash payment under the Petroleum
# Development Act 1974 agreements), and each state's own printed revenue tables.

NATIONAL_REVENUE_CLASSES: list[tuple[str, str]] = [
    # Petroleum: the 5% cash payment / royalty under the PDA 1974 agreements.
    # Printed by Terengganu, Kelantan (as `Wang Ihsan`/`Royalti Petroleum`),
    # Sabah and Sarawak.  Never printed by a non-producing state.
    (r"royalti petroleum|petroleum.{0,12}royalti|wang ihsan|"
     r"royalti minyak|hasil petroleum|bayaran tunai petroleum",
     "petroleum_royalty"),
    # Timber / forest produce: Sabah, Sarawak, Pahang, Perak, Kelantan,
    # Terengganu and Kedah all print a Hasil Hutan head at scale.
    (r"hasil hutan|royalti (kayu|balak|hutan)|premium hutan|"
     r"cukai hutan|hasil kayu|silvi(kultur|culture)|timber",
     "forest_produce"),
    # Cukai Jualan Negeri - a STATE sales tax.  Only Sabah and Sarawak levy one
    # (Sales Tax Ordinance 1998 / Sarawak State Sales Tax Ordinance 1998);
    # no Peninsular state may, so this class doubles as a Borneo marker.
    (r"cukai jualan negeri|state sales tax|cukai jualan (?!dan perkhidmatan)",
     "state_sales_tax"),
    # Mineral / quarry royalties printed as their own head by the Borneo and
    # the tin/bauxite states.
    (r"royalti (galian|mineral|bijih|kuari)|hasil kuari", "mineral_royalty"),
]

STATE_REVENUE_CLASSES: dict[str, list[tuple[str, str]]] = {
    # Sarawak prints several of its trust-fund and revenue heads in ENGLISH
    # inside an otherwise Malay volume (`The State Road Maintenance Fund`,
    # `Government Contributions Towards Approved Agencies Trust Fund`).
    "Sarawak": [
        (r"state sales tax|sales tax|cukai jualan", "state_sales_tax"),
        # Sarawak does not print a "royalti petroleum" head: the PDA 1974
        # payment appears as `Pampasan Gantian Hak Ke Atas Minyak` and
        # `... Ke Atas Gas` (compensation in lieu of rights over oil / gas).
        (r"petroleum|pampasan gantian hak ke atas (minyak|gas)|"
         r"hak ke atas (minyak|gas)", "petroleum_royalty"),
        (r"royalti hutan|premium (tanah|perhutanan)", "forest_produce"),
    ],
    "Sabah": [
        (r"cukai jualan", "state_sales_tax"),
        (r"petroleum|minyak mentah", "petroleum_royalty"),
    ],
    # Terengganu's and Kelantan's share of the PDA 1974 payment is printed as
    # `Wang Ihsan` / `Dana Khas`, paid by the FEDERAL government - the volumes
    # name the payer, so those rows also carry `federal_transfer` semantics.
    # `Dana Khas` is deliberately NOT mapped to petroleum_royalty: the volumes
    # never say what the special fund is for.
    "Terengganu": [(r"wang ihsan|royalti petroleum|petroleum", "petroleum_royalty")],
    "Kelantan": [(r"wang ihsan|royalti petroleum|petroleum", "petroleum_royalty"),
                 (r"royalti kayu kayan|premium perhutanan", "forest_produce")],
}

# Trust funds that are NOT one of the four statutory funds every state keeps
# (Kumpulan Wang Pembangunan / Pembangunan Hutan / Pinjaman Perumahan /
# Amanah Awam) must fall through to an UNCONFORMED `<spec_id>.<slug>` code, so
# that one state's `Kumpulan Wang Bekalan Air` can never collide with another
# state's fund.  That is the default behaviour of `table_catalog.line_code`;
# this list only documents the ones seen, for the README.
STATE_SPECIFIC_TRUST_FUNDS: dict[str, list[str]] = {
    "Johor": ["Kumpulan Wang Bekalan Air"],
    "Kedah": ["Kumpulan Wang Amanah Penyelenggaraan Jalan Negeri"],
    "Sarawak": ["The State Road Maintenance Fund", "The State Disaster Relief Fund",
                "Government Contributions Towards Approved Agencies Trust Fund",
                "The Ketua Masyarakat (Ketua Kaum) Trust Fund",
                "The Forest Concession Area (Rehabilitation and Development) Trust Fund"],
    "Sabah": ["Kumpulan Wang Amanah Bencana Alam"],
}

# ---------------------------------------------------------------------------
# agency-register name prefixes
# ---------------------------------------------------------------------------
# The submission / opinion registers list agencies by name; a row is only
# accepted when the name opens with an institutional noun.  The Borneo states
# add a few of their own (Sarawak's `Majlis Islam Sarawak`, Sabah's
# `Jabatan ...`, `Lembaga ...`), so the prefix set is configuration.

AGENCY_NAME_PREFIXES: list[str] = [
    "Kumpulan Wang", "Tabung", "Perbadanan", "Lembaga", "Majlis", "Yayasan",
    "Institut", "Suruhanjaya", "Pihak Berkuasa", "Pusat", "Badan", "Agensi",
    "Setiausaha", "Jabatan", "Kolej", "Universiti", "Dewan", "Amanah",
    "Koperasi", "Syarikat Air", "Unit", "Bahagian",
    # `Korporasi ...` is the Sabah statutory-body form (Korporasi Pembangunan
    # Desa Sabah, Korporasi Kemajuan Perikanan Dan Nelayan Sabah); without it
    # those two registered agencies were refused as unreadable names.
    "Korporasi",
]

AGENCY_NAME_PREFIXES_EXTRA: dict[str, list[str]] = {
    "Sarawak": ["Sarawak", "The ", "Kuching", "Miri", "Sibu", "Bintulu", "Padawan"],
    "Sabah": ["Sabah", "Kota Kinabalu", "Tawau", "Sandakan", "Lembaga Sukan"],
    "Pulau Pinang": ["Perbadanan Bekalan Air"],
}


def agency_name_re(state: str) -> re.Pattern:
    names = AGENCY_NAME_PREFIXES + AGENCY_NAME_PREFIXES_EXTRA.get(state, [])
    return re.compile(r"^(" + "|".join(re.escape(n) for n in names) + r")\b")


# ---------------------------------------------------------------------------
# section boundary
# ---------------------------------------------------------------------------
# Section dividers - identical wording in every state's volume.

AGENCY_SECTION = re.compile(
    r"PENYERAHAN,?\s+PENGESAHAN|PENYATA KEWANGAN AGENSI NEGERI|"
    r"PENGESAHAN DAN PEMBENTANGAN PENYATA KEWANGAN AGENSI", re.I)

STATE_SECTION_HINT = re.compile(
    r"ANALISIS KEWANGAN KERAJAAN NEGERI|PENYATA PRESTASI KEWANGAN|"
    r"KUMPULAN WANG DISATUKAN", re.I)


def state_section_end(pages: list[str], first_table_page: int) -> int:
    """pdf page (1-based, exclusive) at which the agency half of the volume
    starts.  Contents pages repeat the wording, so only look past the first
    analysis table."""
    for i in range(max(first_table_page, 20), len(pages)):
        txt = pages[i]
        for line in txt.split("\n"):
            s = line.strip()
            if len(s) < 120 and AGENCY_SECTION.search(s) and not STATE_SECTION_HINT.search(s):
                return i + 1
    return len(pages) + 1


# ---------------------------------------------------------------------------
# known extraction defects
# ---------------------------------------------------------------------------
# Defects THIS PIPELINE is responsible for, which have been diagnosed against
# the printed page but not yet fixed.
#
# They are listed here, and never in `_source_anomalies_<slug>.csv`.  That file
# asserts that the Auditor-General's own printed figures do not add up; filing
# a defect of ours in it is a false accusation against the source, which is
# exactly what golden rule 2 forbids.  Being unfixed is honest; being mis-filed
# is not.
#
# Each entry drives three things:
#   * `_known_extraction_defects_<slug>.csv` (+ the national roll-up);
#   * `data_quality='suspect'` on the affected rows of the fact files, so a
#     consumer cannot use them unaware;
#   * suppression of the matching V1 failure from `_source_anomalies` - the
#     failure itself stays in `_validation_<slug>.csv`, because it IS a
#     failure; only the claim "the source misprinted this" is withdrawn.
#
# `match` selects the affected fact rows and the V1 failures to divert.  An
# entry with no `match` is a standing limitation with no single page to point
# at; it is reported in the file only.

# Auditor-General misprints PROVED ON THE ARCHIVED PAGE (qa/evidence/). Only these turn a FAIL into
# SOURCE_ANOMALY in _validation_<slug>.csv (golden rule 2). Every other unexplained V1 failure is still
# listed in _source_anomalies_<slug>.csv, but marked page_proved=no, and stays a FAIL.
PAGE_PROVED_ANOMALIES: list[dict] = [
    dict(
        state="Kedah", fiscal_year="2016", source_file="CMD.34.2018.pdf", checks=("V1_intra_volume_contradiction",),
        evidence="qa/evidence/CMD.34.2018.pdf/p031.txt (J4.9), p030.txt (J4.8)",
        proof="J4.9 prints a '2016 DINYATAKAN SEMULA' (restated) column in which the three revenue categories are "
              "reprinted, reclassified (222.75 + 213.62 + 165.26 = 601.63, the same total as J4.8), but the HASIL line "
              "itself is printed nil (-). The nil is how the restated column is printed, not a second revenue figure.",
    ),
    dict(
        state="Johor", fiscal_year="2019", source_file="CMD.38.2023.pdf", checks=("V1_revenue_categories",),
        evidence="qa/evidence/CMD.38.2023.pdf/p037.txt (5-year Penyata Prestasi Kewangan, 2018-2022)",
        proof="FY2019 prints Hasil Cukai 533.15 + Hasil Bukan Cukai 874.80 + Terimaan Bukan Hasil 337.77 = 1,745.72 "
              "against JUMLAH HASIL 1,745.32 (0.40 less). Every other year of the same table adds up exactly "
              "(2018 1,543.03; 2020 1,674.29; 2021 1,428.14; 2022 1,630.64).",
    ),
    dict(
        state="Kelantan", fiscal_year="2018", source_file="CMD.43.2022.pdf", checks=("V1_cra_surplus",),
        evidence="qa/evidence/CMD.43.2022.pdf/p042.txt (Kedudukan Akaun Hasil Disatukan 2017-2021)",
        proof="FY2018 prints Hasil 586.94 and Perbelanjaan Mengurus 546.49, whose difference is 40.45, and "
              "Lebihan/Defisit 40.46 with footnote (2): 'Jumlah lebihan/defisit hasil adalah perbezaan keseluruhan "
              "yang telah dibundarkan' - the surplus is the rounded difference of the unrounded totals. The publisher's "
              "declared rounding (0.01).",
    ),
    dict(
        state="Perlis", fiscal_year="2024", source_file="CMD.22.2025.pdf", checks=("V1_continuity_cross_volume",),
        evidence="qa/evidence/CMD.26.2024.pdf/p041.txt; qa/evidence/CMD.22.2025.pdf/p036.txt",
        proof="A restatement, not a misprint: CMD.26.2024 closes FY2023 at (523.53) (= (501.14) + 140.54 - 162.93); "
              "CMD.22.2025 opens FY2024 at (523.50) and reprints FY2023 as (501.11) + 140.54 - 162.93 = (523.50). "
              "Each volume adds up; the later one restates the earlier year by 0.03. Each year is taken from its "
              "own volume (golden rule 6).",
    ),
    dict(
        state="Selangor", fiscal_year="2019", source_file="CMD.50.2021.pdf",
        checks=("V1_govt_trust_fund_composition", "V1_trust_account_composition", "V1_intra_volume_contradiction"),
        evidence="qa/evidence/CMD.50.2021.pdf/p029.txt (Jadual 2), p030.txt (Jadual 3)",
        proof="The FY2019 subtotal 'Kumpulan Wang Amanah Kerajaan' is printed 1,114.60 in Jadual 2 and Jadual 3, but "
              "its own four printed components sum to 50.00 + 6.31 + 987.41 + 27.15 = 1,070.87, and only 1,070.87 "
              "reconciles upward: 1,070.87 + 376.26 + 427.34 = 1,874.47 (printed Akaun Amanah Disatukan) and "
              "267.29 + 0.00 + 1,874.47 = 2,141.76 (printed BAKI PADA 31 DISEMBER). Jadual 24 prints 1,070.87.",
    ),
]


def page_proved(state: str, c: dict):
    for d in PAGE_PROVED_ANOMALIES:
        if (d["state"] == state and c["check"] in d["checks"] and str(c.get("fiscal_year")) == d["fiscal_year"]
                and c.get("source_file") == d["source_file"]):
            return d
    return None


KNOWN_EXTRACTION_DEFECTS: list[dict] = [
    # Johor CMD.35.2016 J4.20 (FY2015 trust total read as 2014's) and Selangor CMD.61.2015 J4.21 (FY2014 loan-account
    # receipts/payments read as 2013's) were registered here 2026-11-04 and are FIXED by the parser's shifted-block rule
    # (lkan_state_parser.parse_rows, 2026-11-05); see qa/audits/2026-11-05_state_column_shift.md.
    # Located by the blind verifier of 2026-11-05 (qa/audits/2026-11-05_state_column_shift.md); all pre-date it.
    dict(
        state="Sarawak",
        source_file="CMD.44.2016.pdf", pdf_page="48", printed_page="", jadual="4.30",
        match=dict(target="finance", jadual="4.30", checks=()),
        affected_rows="CMD.44.2016 J4.30 (Akaun Deposit by type), every row",
        defect="The table prints a block of depositor COUNTS (Bilangan Pendeposit 2015 / 2014) then the amounts "
               "(RM Juta 2015 / 2014) under a two-tier header; the columns are read off by one block, so the 2014 "
               "counts ship as RM Juta for FY2015 (11,988 / 3,106 / 15,094) and the FY2014 Jumlah carries the 2015 "
               "total (613.08 for 461.03); the FY2014 Deposit Am 64.88 and Deposit Khas 396.15 are right.",
        diagnosis="Page-proved (CMD.44.2016.pdf p48): printed 2015 RM 73.49 / 539.59 / 613.08, 2014 RM 64.88 / "
                  "396.15 / 461.03. Not an AG misprint.",
        why_unfixed="A two-tier header with a non-money block needs the header tiers read as such; one table.",
        impact_on_data="Unconformed codes, not in the national panel or core. Do not use this table's rows.",
    ),
    dict(
        state="Kedah",
        source_file="CMD.34.2018.pdf", pdf_page="", printed_page="", jadual="",
        match=dict(target="finance", jadual="4.8", fiscal_year=("2016",), checks=()),
        affected_rows="CMD.34.2018 J4.8 (and J4.9, next entry), the FY2016 comparatives",
        defect="FY2016 is printed twice, as originally reported and 'Dinyatakan Semula' (restated); the extractor "
               "reads the restated column, where '-' means 'not restated', and ships 0.00 (e.g. Baki 1 Januari "
               "-497.93 -> 0; Perbelanjaan 545.91 / 660.91 -> 0).",
        diagnosis="Page-proved by the verifier (CMD.34.2018.pdf p30-31).",
        why_unfixed="Needs the 'Dinyatakan Semula' column recognised as a restatement basis, not the year column.",
        impact_on_data="The national panel takes Kedah FY2016 from its own volume (CMD.34.2017), so core is "
                       "unaffected; do not use these comparatives.",
    ),
    dict(
        state="Kedah",
        source_file="CMD.34.2018.pdf", pdf_page="", printed_page="", jadual="",
        match=dict(target="finance", jadual="4.9", fiscal_year=("2016",), checks=()),
        affected_rows="CMD.34.2018 J4.9 (and J4.8, previous entry), the FY2016 comparatives",
        defect="FY2016 is printed twice, as originally reported and 'Dinyatakan Semula' (restated); the extractor "
               "reads the restated column, where '-' means 'not restated', and ships 0.00 (e.g. Baki 1 Januari "
               "-497.93 -> 0; Perbelanjaan 545.91 / 660.91 -> 0).",
        diagnosis="Page-proved by the verifier (CMD.34.2018.pdf p30-31).",
        why_unfixed="Needs the 'Dinyatakan Semula' column recognised as a restatement basis, not the year column.",
        impact_on_data="The national panel takes Kedah FY2016 from its own volume (CMD.34.2017), so core is "
                       "unaffected; do not use these comparatives.",
    ),
    dict(
        state="Melaka",
        source_file="CMD.35.2017.pdf", pdf_page="64", printed_page="", jadual="4.49",
        match=dict(target="finance", jadual="4.49", checks=()),
        affected_rows="CMD.35.2017 J4.49 (Pelaburan), the rows read as FY2015",
        defect="The column header is misprinted '2015 2015' (the title says 2016 berbanding 2015); the 2016 column "
               "is read as FY2015 (Hartanah 69.93, JUMLAH 143.37) and the real FY2015 dropped.",
        diagnosis="The FY2015 volume prints 69.05 / 142.49. The header misprint is the source's; reading the column "
                  "as FY2015 is ours.",
        why_unfixed="One table; a header-year override needs its own page-proved rule.",
        impact_on_data="Some rows are conformed (Saham Tidak Tersiar Harga) or canonical (Hartanah); all are "
                       "flagged suspect. Do not use this table's FY2015 figures.",
    ),
    dict(
        state="Sabah",
        source_file="CMD.43.2016.pdf", pdf_page="48", printed_page="", jadual="4.31",
        match=dict(target="finance", jadual="4.31", checks=()),
        affected_rows="CMD.43.2016 J4.31, the row labelled 'Corporation Sdn. Bhd. Jumlah'",
        defect="The last item's wrapped name is welded to the Jumlah line, which is then typed a leaf component "
               "(358.03): summing leaf rows counts the total twice.",
        diagnosis="Verifier 2026-11-05 (CMD.43.2016.pdf p48).",
        why_unfixed="Label-join case not resolved by the glyph-position tie-break (not an exact tie).",
        impact_on_data="Unconformed code. Do not sum this table's leaf rows.",
    ),
    dict(
        state="Sarawak",
        source_file="CMD.49.2021.pdf", pdf_page="", printed_page="",
        jadual="8",
        match=dict(target="finance", jadual="8",
                   line_code=("revenue_total",),
                   is_canonical=("yes",),
                   checks=()),
        affected_rows="0 rows carry a wrong figure; 1 printed row per Sarawak "
                      "year is MISSING (the head itself)",
        defect="Sarawak prints a FOURTH revenue head, `Pemberian Kerajaan "
               "Persekutuan dan Bayaran Balik` (FY2020: 248.34), which is not "
               "emitted as a row. `revenue_total` (10,646.69) is correct, but "
               "tax + nontax + nonrevenue = 10,398.35 falls short by that head, "
               "so Sarawak's revenue components do not sum to its total.",
        diagnosis="Surfaced by the DOSM cross-check "
                  "(sources/dosm/data/_crosscheck_state_finance_vs_audited.csv): "
                  "DOSM reports Sarawak non-revenue receipts as 279.09, and "
                  "30.75 + 248.34 = 279.09 exactly - DOSM folds the head into "
                  "non-revenue receipts, proving the printed head exists and "
                  "our figure for it is right. The validator already uses it "
                  "in the four-head reconciliation proof, so the head is "
                  "recognised during checking but never written to the fact file.",
        why_unfixed="Needs a revenue-head row emitted under a conformed code "
                    "(e.g. revenue_federal_grants) plus a decision on whether "
                    "other states' equivalent heads conform to the same code - "
                    "a dictionary change, not taken unilaterally. "
                    "sources/dosm/pipeline/crosscheck_state_finance.py already "
                    "carries the COMBINES entry that will re-adjudicate the "
                    "DOSM comparison to DEFINITIONAL once the code exists.",
        impact_on_data="No figure in the panel is wrong. Do not derive Sarawak "
                       "revenue by summing components; use revenue_total.",
    ),
    dict(
        state="Perak",
        source_file="CMD.44.2023.pdf", pdf_page="98", printed_page="90",
        jadual="5",
        match=dict(target="agency", pdf_page="98"),
        affected_rows="8 register rows (`sijil_pendapat`)",
        defect="Agency names weld across the three-line centred layout "
               "(`Majlis Bandaraya Ipoh Kumpulan Wang Biasiswa Bukan Melayu "
               "Perak`), one printed bil is absorbed into its neighbour, and "
               "EVERY row on the page reads `opinion=Tanpa Teguran`.",
        diagnosis="Two causes.  (a) The name cell is printed on the lines "
                  "either side of its Bil., and where the Bil. line itself "
                  "carries a name the per-column tie-break cannot separate "
                  "them.  (b) `_OPGROUPS` has no pattern for this volume's "
                  "captions `PENDAPAT TANPA TEGURAN DENGAN OM` / `... DENGAN "
                  "EOM DAN OM`, so the opening `PENDAPAT TANPA TEGURAN` "
                  "section heading is never superseded.",
        why_unfixed="(b) is a one-line addition but changes the opinion "
                    "taxonomy for every state, which needs its own verified "
                    "pass against the printed opinion captions; shipping it "
                    "untested would silently re-tag opinions elsewhere.",
        impact_on_data="`opinion` and `opinion_qualifier` on this page are not "
                       "trustworthy; `agency_name_bm` on this page is partly "
                       "welded.  No other page of any state is affected.",
    ),
    dict(
        state="Pulau Pinang",
        source_file="CMD.46.2023.pdf", pdf_page="96", printed_page="88",
        jadual="5",
        match=dict(target="agency", pdf_page="96"),
        affected_rows="1 emitted (of 2 printed); 1 agency lost",
        defect="`Majlis Agama Islam Negeri Pulau Pinang` is not emitted.  The "
               "page prints two rows, each numbered `1.`, under two different "
               "opinion captions.",
        diagnosis="The second caption is typeset with wide inter-word gaps and "
                  "wraps (`PENDAPAT TANPA   TEGURAN   DENGAN   PERENGGAN "
                  "PENEGASAN PERKARA DAN PERENGGAN` / `HAL-HAL LAIN`), so its "
                  "tail is not recognised as a heading and the two `1.` "
                  "anchors collapse into one row.",
        why_unfixed="Recognising a heading that wraps across two lines needs "
                    "the caption matcher to join header lines before testing, "
                    "which risks swallowing genuine agency rows printed in "
                    "capitals; not attempted without a verified sweep.",
        impact_on_data="One agency is missing from the FY2021 sijil register "
                       "for Pulau Pinang.  The surviving row is correct.",
    ),
    dict(
        state="(all)",
        source_file="", pdf_page="", printed_page="", jadual="",
        affected_rows="unknown - a latent tokeniser defect, not a located row set",
        defect="A figure printed EXACTLY ONE SPACE after the previous figure "
               "is dropped by `lkan_state_parser._value_tokens`.",
        diagnosis="`_NUM_RE` allows one optional space after the sign, so when "
                  "two figures are one space apart the scanner starts the "
                  "second match ON that space; its preceding character is then "
                  "the last digit of the first figure and the date / "
                  "section-number guard discards it.  Seen on Sarawak "
                  "CMD.43.2018 J4.14, where every row lost `27.5 25.8 35.2`.",
        why_unfixed="A global fix (trim leading white space before applying "
                    "the guard) moved roughly 2,000 rows and broke column "
                    "geometry (Pahang lost 63 rows), so it is applied only at "
                    "ROW level (2026-11-05): column building keeps the "
                    "historical tokeniser, and a row whose historical tokens do "
                    "not fit the columns falls back to the exact ones (one per "
                    "column, one per money-year column, or amount/share pairs "
                    "in a `(RM Juta)`/`(%)` matrix).  That cleared every "
                    "top-contributor JUMLAH defect (Selangor CMD.41.2019 J11 "
                    "and CMD.50.2021 J13, Negeri Sembilan CMD.37.2018 J4.10); "
                    "rows that still fit the columns with a value missing are "
                    "not re-tokenised.",
        impact_on_data="Mostly percentage and PERUBAHAN columns, which are not "
                       "extracted anyway.  Where it hits a money column the row "
                       "is marked `column_geometry=incomplete_row`, so no "
                       "figure is wrong - some are absent.",
    ),
    dict(
        state="(all)",
        source_file="", pdf_page="", printed_page="", jadual="",
        affected_rows="labels only, in analysis tables, under UNCONFORMED line codes; located by the blind "
                      "verifier of the 2026-11-05 parser pass (qa/audits/2026-11-05_state_parser_verifier.md)",
        defect="Some printed labels are stitched wrongly; every amount and year on these rows is right. "
               "(a) A label wrapped BELOW its line joins the NEXT row in the line-at-a-time parser: Sarawak "
               "CMD.60.2015 / CMD.44.2016 J4.2 ship `Kumpulan Wang Amanah i. Kumpulan Wang` (printed: `i. Kumpulan "
               "Wang Pembangunan`), `Pembangunan ii. Kumpulan Wang Amanah` (printed: `ii. Kumpulan Wang Amanah "
               "Kerajaan`), `Awam b. Deposit`; Johor CMD.35.2016 J4.2 `Amanah Kerajaan b) Kumpulan Wang Amanah "
               "Awam`; the by-Bil. parser does the same in Sarawak CMD.44.2016 J4.13 (`Kewangan Pampasan Gantian "
               "Hak Ke Atas` = printed `Pampasan Gantian Hak Ke Atas Minyak`; `Minyak Royalti Hutan` = `Royalti "
               "Hutan`). (b) FIXED 2026-11-05: a label line exactly between two rows is now placed by its glyph "
               "position (pdftotext -bbox-layout) in both parsers, never onto a closed total/balance line - labels "
               "in 12 states moved to their own row (Kedah CMD.42.2022 J10 `Lain-Lain "
               "Levi` / the Concurrent List grant, the many `<name tail> Jumlah` totals; "
               "qa/audits/2026-11-05_state_column_shift.md). (c) The running "
               "footer `Penyata Kewangan` survives on some JUMLAH labels (Melaka CMD.33.2019 J15, Perlis "
               "CMD.37.2019 J5, Kedah, Perak, Pahang `JUMLAH Pahang Tahun`). (d) Five label-only footer lines "
               "become nil (`-`) phantom rows: Melaka CMD.33.2019 p39 J15, Perak CMD.36.2019 p29 J3, Sarawak "
               "CMD.40.2019 p31 J3 and p35 J8, Terengganu CMD.41.2020 p35 J7.",
        diagnosis="All pre-date the 2026-11-05 pass (the same labels are on main for the other years of each "
                  "line). A rule sending a label-only line to the row ABOVE whenever every Bil. line carries label "
                  "text fixed Sarawak J4.13 and Kedah J4.14 but broke Johor CMD.39.2021 J9, Kedah CMD.40.2021 "
                  "J10 and stitched prose into two new Sabah CMD.41.2017 J4.9 rows, so it was reverted: the text "
                  "layer alone does not say whether a wrapped line continues the row above or opens the row "
                  "below.",
        why_unfixed="(a) is the line-at-a-time parser and a by-Bil. case that is not an exact tie; the glyph "
                    "positions now used for (b) could place them too, a further change to every state's tables "
                    "that needs its own verified pass; the phantoms and footer residue need the footer filter to recognise "
                    "single footer words without eating real labels.",
        impact_on_data="No amount is wrong. The affected rows carry unconformed codes (not read by core or the "
                       "gap view) except Johor J4.2 `public_trust_funds`, whose code is right. Do not quote "
                       "these labels; the nil phantoms are 0.00 rows with no printed item.",
    ),
]


def defect_entries(state: str) -> list[dict]:
    return [d for d in KNOWN_EXTRACTION_DEFECTS
            if d["state"] in (state, "(all)")]


def _matches(d: dict, target: str, row: dict) -> bool:
    m = d.get("match")
    if not m or m.get("target") != target:
        return False
    if d["state"] != row.get("state"):
        return False
    if d["source_file"] and row.get("source_file") != d["source_file"]:
        return False
    for fld in ("jadual", "pdf_page"):
        if fld in m and str(row.get(fld, "")) != str(m[fld]):
            return False
    if "line_code" in m and row.get("line_code") not in m["line_code"]:
        return False
    if "fiscal_year" in m and row.get("fiscal_year") not in m["fiscal_year"]:
        return False
    if "is_canonical" in m and row.get("is_canonical") not in m["is_canonical"]:
        return False
    return True


def is_known_defect_row(target: str, row: dict) -> bool:
    """True when this fact row is covered by a KNOWN_EXTRACTION_DEFECTS entry."""
    return any(_matches(d, target, row) for d in KNOWN_EXTRACTION_DEFECTS)


def is_known_defect_check(state: str, check: dict) -> bool:
    """True when this V1 failure is a defect of OURS, already diagnosed, and
    must therefore not be asserted as a misprint in `_source_anomalies`."""
    for d in KNOWN_EXTRACTION_DEFECTS:
        m = d.get("match")
        if not m or d["state"] != state:
            continue
        if check["check"] not in m.get("checks", ()):
            continue
        if d["source_file"] and check.get("source_file") != d["source_file"]:
            continue
        if "jadual" in m and str(check.get("jadual", "")) != str(m["jadual"]):
            continue
        if "fiscal_year" in m and check.get("fiscal_year") not in m["fiscal_year"]:
            continue
        return True
    return False


DEFECT_FIELDS = ["state", "source_file", "pdf_page", "printed_page", "jadual",
                 "affected_rows", "defect", "diagnosis", "why_unfixed",
                 "impact_on_data"]
