"""Extract Jadual 1.1, 3.1, 3.2, 3.3 from the Tinjauan Fiskal 2021 "Statistik Kewangan
Awam / Public Finance Statistics" appendix (now cited as the official st_kewangan.pdf;
see SOURCE_FILE below. PDFs are not committed -- this script is the provenance trail).

Every value below was read directly off the named pdf_page/printed_page via
`pdftotext -layout` on that PDF (verify with `pdftotext -layout -f <pdf_page> -l <pdf_page>
raw/2021/st_kewangan.pdf -`) — none is recomputed or estimated. Basis per the source's own
footnotes: 2017-2019 = official_actual (unlabelled in source), 2020 = official_revised
("Anggaran disemak"), 2021 = official_projection ("Anggaran belanjawan tidak termasuk
langkah Belanjawan 2021" -- i.e. excludes 2021 Budget measures).

Run: python3 sources/mof-fiscal-outlook/pipeline/extract_2021_public_finance_stats.py
Writes: sources/mof-fiscal-outlook/data/2021_public_finance_stats/fact_headline.csv
        sources/mof-fiscal-outlook/data/2021_public_finance_stats/fact_opex_by_component.csv
        sources/mof-fiscal-outlook/data/2021_public_finance_stats/fact_opex_by_sector.csv
        sources/mof-fiscal-outlook/data/2021_public_finance_stats/fact_devex_by_sector.csv
        sources/mof-fiscal-outlook/data/2021_public_finance_stats/_validation.csv
"""
import csv
import os

# The figures were first transcribed (2026-09-04) from a user-uploaded copy of this
# 20-page appendix, filed then as "tinjauan_fiskal_2021.pdf" under a URL that no longer
# resolves. The appendix is now held as the official st_kewangan.pdf
# (data/_editions_manifest.csv), and it is cited directly: its pdf pages 5/7/8/9 and
# printed pages 173/175-177 are the ones recorded below, and the generic parser re-reads
# every one of the folder's 334 cells from it identically (data/_parser_check_2021*.csv).
SOURCE_FILE = "st_kewangan.pdf"
RETRIEVED_FROM = ("https://belanjawan.mof.gov.my/pdf/2021/hasil/st_kewangan.pdf "
                  "(first transcribed 2026-09-04 from a user-uploaded copy of the same appendix)")
RETRIEVED_DATE = "2026-11-04"
YEARS = [2017, 2018, 2019, 2020, 2021]
BASIS = {2017: "official_actual", 2018: "official_actual", 2019: "official_actual",
         2020: "official_revised", 2021: "official_projection"}

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "2021_public_finance_stats")


def row_common(pdf_page, printed_page, note=""):
    return dict(edition=2021, source_file=SOURCE_FILE, pdf_page=pdf_page, printed_page=printed_page,
                retrieved_from=RETRIEVED_FROM, retrieved_date=RETRIEVED_DATE, note=note)


# ---------------------------------------------------------------------------
# Jadual 1.1 -- Kewangan Kerajaan Persekutuan / Federal Government Finance
# pdf_page 5, printed_page 173
# ---------------------------------------------------------------------------
HEADLINE = {
    "revenue":                    [220406, 232882, 264415, 227270, 236900],
    "operating_expenditure":      [217695, 230960, 263343, 226720, 236540],
    "current_balance":            [2711, 1922, 1072, 550, 360],
    "development_expenditure_gross": [44884, 56095, 54173, 50000, 69000],
    "development_expenditure_direct": [42277, 54405, 52058, 47468, 67300],
    "development_expenditure_gross_lending": [2607, 1690, 2115, 2532, 1700],
    "development_expenditure_loan_recovery": [1852, 788, 1603, 1000, 800],
    "development_expenditure_net": [43032, 55307, 52570, 49000, 68200],
    "covid19_fund":               [None, None, None, 38000, 17000],
    "overall_balance":            [-40321, -53385, -51498, -86450, -84840],
    "overall_balance_pct_gdp":    [-2.9, -3.7, -3.4, -6.0, -5.4],
    "primary_balance":            [-12458, -22838, -18565, -51505, -45840],
    "primary_balance_pct_gdp":    [-0.9, -1.6, -1.2, -3.6, -2.9],
    "net_offshore_borrowings":    [-342, -320, 6977, -303, None],
    "net_domestic_borrowings":    [40732, 54427, 44755, 87051, None],
    "change_in_assets":           [-69, -722, -234, -298, None],
}
HEADLINE_NOTE = {
    "development_expenditure_gross": "printed as 'Perbelanjaan pembangunan kasar'",
    "development_expenditure_net": "printed as 'Perbelanjaan pembangunan bersih' = gross - loan_recovery",
    "primary_balance": "excludes debt service charges, per source footnote 2",
    "net_offshore_borrowings": "financing breakdown not printed for 2021 budget estimate (dash in source)",
    "net_domestic_borrowings": "financing breakdown not printed for 2021 budget estimate (dash in source)",
    "change_in_assets": "financing breakdown not printed for 2021 budget estimate (dash in source); (+) drawdown, (-) accumulation",
}


def build_headline():
    rows = []
    for line, values in HEADLINE.items():
        for year, val in zip(YEARS, values):
            if val is None:
                continue
            is_pct = line.endswith("_pct_gdp")
            r = dict(table_no="1.1", line=line, target_year=year,
                     amount_rm_juta=None if is_pct else val,
                     pct_of_gdp=val if is_pct else None,
                     basis=BASIS[year])
            r.update(row_common(5, 173, HEADLINE_NOTE.get(line, "")))
            rows.append(r)
    return rows


# ---------------------------------------------------------------------------
# Jadual 3.1 -- Perbelanjaan Mengurus mengikut Komponen / Operating Expenditure
# by Component. pdf_page 7, printed_page 175
# level 1 = top-level component; level 2 = sub-split of a level-1 line
# ---------------------------------------------------------------------------
OPEX_COMPONENT = [
    # (line_key, line_bm, line_en, level, parent, [2017,2018,2019,2020,2021] amounts, [pct shares]
    ("emoluments", "Emolumen", "Emoluments", 1, None,
     [77036, 79989, 80534, 82611, 84532], [35.4, 34.6, 30.6, 36.4, 35.7]),
    ("retirement_charges", "Bayaran persaraan", "Retirement charges", 1, None,
     [22800, 25177, 25894, 27055, 27583], [10.5, 10.9, 9.8, 11.9, 11.7]),
    ("debt_service", "Bayaran khidmat hutang", "Debt service charges", 1, None,
     [27863, 30547, 32933, 34945, 39000], [12.8, 13.2, 12.5, 15.4, 16.5]),
    ("debt_service_domestic", "Dalam negeri", "Domestic", 2, "debt_service",
     [27159, 29891, 32239, 34147, 38104], [12.5, 12.9, 12.2, 15.1, 16.1]),
    ("debt_service_external", "Luar negeri", "External", 2, "debt_service",
     [704, 656, 694, 798, 896], [0.3, 0.3, 0.3, 0.4, 0.4]),
    ("grants_state_govts", "Pemberian dan serahan kepada kerajaan negeri",
     "Grants and transfers to state governments", 1, None,
     [7109, 7605, 7574, 7749, 7745], [3.3, 3.3, 2.9, 3.4, 3.3]),
    ("grants_constitutional", "Pemberian di bawah Perlembagaan", "Constitutional grants", 2,
     "grants_state_govts", [5101, 5495, 5619, 5659, 5705], [2.3, 2.4, 2.1, 2.5, 2.4]),
    ("grants_other", "Pemberian/pindahan lain", "Other grants/transfers", 2,
     "grants_state_govts", [2008, 2110, 1955, 2090, 2040], [1.0, 0.9, 0.7, 0.9, 0.9]),
    ("supplies_services", "Perkhidmatan dan bekalan", "Supplies and services", 1, None,
     [34738, 35283, 31507, 30101, 32770], [16.0, 15.3, 12.0, 13.3, 13.9]),
    ("subsidies_social_assistance", "Subsidi dan bantuan sosial", "Subsidies and social assistance", 1, None,
     [22354, 27516, 23901, 20145, 18853], [10.3, 11.9, 9.1, 8.9, 8.0]),
    ("asset_acquisition", "Pembelian aset", "Asset acquisition", 1, None,
     [516, 447, 770, 650, 542], [0.2, 0.2, 0.3, 0.3, 0.2]),
    ("refunds_writeoffs", "Bayaran balik dan hapus kira", "Refunds and write-offs", 1, None,
     [973, 883, 893, 987, 511], [0.4, 0.4, 0.3, 0.4, 0.2]),
    ("grants_statutory_bodies", "Pemberian kepada badan berkanun", "Grants to statutory bodies", 1, None,
     [14044, 13763, 13780, 14040, 15430], [6.5, 6.0, 5.2, 6.2, 6.5]),
    ("other", "Lain-lain", "Others", 1, None,
     [10262, 9750, 45557, 8437, 9574], [4.6, 4.2, 17.3, 3.8, 4.0]),
    ("total", "Jumlah", "Total", 1, None,
     [217695, 230960, 263343, 226720, 236540], [100.0, 100.0, 100.0, 100.0, 100.0]),
]
OPEX_COMPONENT_NOTE = {
    "other": "footnote: includes grants to Statutory Funds, public corporations, "
             "international organisations, insurance claims and gratuities and others; "
             "the 2019 spike (45,557) is as printed in the source, not a transcription error",
}


def build_opex_component():
    rows = []
    for key, bm, en, level, parent, amounts, shares in OPEX_COMPONENT:
        for year, amt, pct in zip(YEARS, amounts, shares):
            r = dict(table_no="3.1", line=key, line_bm=bm, line_en=en, level=level,
                      parent_line=parent, target_year=year, amount_rm_juta=amt,
                      pct_share=pct, basis=BASIS[year])
            r.update(row_common(7, 175, OPEX_COMPONENT_NOTE.get(key, "")))
            rows.append(r)
    return rows


# ---------------------------------------------------------------------------
# Jadual 3.2 -- Perbelanjaan Mengurus mengikut Sektor / Operating Expenditure by
# Sector. pdf_page 8, printed_page 176. (No % share printed in this table.)
# ---------------------------------------------------------------------------
OPEX_SECTOR = [
    ("economic", "Ekonomi", "Economic", 1, None,
     [16878, 14064, 15605, 16209, 17057]),
    ("economic_agri_rural", "Pertanian dan pembangunan luar bandar",
     "Agriculture and rural development", 2, "economic", [4480, 4618, 3457, 1818, 1863]),
    ("economic_energy_utilities", "Tenaga dan kemudahan awam", "Energy and public utilities",
     2, "economic", [96, 297, 243, 369, 406]),
    ("economic_trade_industry", "Perdagangan dan perindustrian", "Trade and industry",
     2, "economic", [3156, 2703, 2936, 3078, 3495]),
    ("economic_transport", "Pengangkutan", "Transport", 2, "economic",
     [6146, 3448, 5638, 6076, 6294]),
    ("economic_communications", "Perhubungan", "Communications", 2, "economic",
     [96, 96, 87, 94, 89]),
    ("economic_environment", "Alam sekitar", "Environment", 2, "economic",
     [99, 70, 135, 126, 140]),
    ("economic_other", "Lain-lain", "Others", 2, "economic", [2805, 2832, 3109, 4648, 4770]),
    ("social", "Sosial", "Social", 1, None, [87409, 90968, 93494, 91933, 96942]),
    ("social_education", "Pendidikan dan latihan", "Education and training", 2, "social",
     [54227, 56233, 56546, 56321, 59139]),
    ("social_health", "Kesihatan", "Health", 2, "social", [24054, 26435, 27873, 26123, 27504]),
    ("social_housing", "Perumahan", "Housing", 2, "social", [715, 13, 10, 0, 0]),
    ("social_other", "Lain-lain", "Others", 2, "social", [8413, 8287, 9065, 9489, 10299]),
    ("security", "Keselamatan", "Security", 1, None, [26006, 27229, 23429, 24654, 25834]),
    ("security_defence", "Pertahanan", "Defence", 2, "security", [11683, 16283, 10633, 10681, 11355]),
    ("security_internal", "Keselamatan dalam negeri", "Internal security", 2, "security",
     [14323, 10946, 12796, 13973, 14479]),
    ("general_admin", "Pentadbiran am", "General administration", 1, None,
     [12048, 17597, 16901, 17194, 19323]),
    ("other", "Lain-lain", "Others", 1, None, [75354, 81102, 113914, 76730, 77384]),
    ("total", "Jumlah", "Total", 1, None, [217695, 230960, 263343, 226720, 236540]),
]
OPEX_SECTOR_NOTE = {
    "social_housing": "printed as '-' (nil) for 2020 and 2021, kept as 0 per this warehouse's "
                      "en-dash-equals-nil convention",
    "general_admin": "footnote: includes general services, refund and reimbursement, and "
                     "foreign affairs services",
    "other": "footnote: includes debt service charges, retirement charges and transfer payments "
             "(i.e. the components of Jadual 3.1 with no sector classification)",
}


def build_opex_sector():
    rows = []
    for key, bm, en, level, parent, amounts in OPEX_SECTOR:
        for year, amt in zip(YEARS, amounts):
            r = dict(table_no="3.2", line=key, line_bm=bm, line_en=en, level=level,
                      parent_line=parent, target_year=year, amount_rm_juta=amt,
                      pct_share=None, basis=BASIS[year])
            r.update(row_common(8, 176, OPEX_SECTOR_NOTE.get(key, "")))
            rows.append(r)
    return rows


# ---------------------------------------------------------------------------
# Jadual 3.3 -- Perbelanjaan Pembangunan mengikut Sektor / Development
# Expenditure by Sector. pdf_page 9, printed_page 177.
# ---------------------------------------------------------------------------
DEVEX_SECTOR = [
    ("economic", "Ekonomi", "Economic", 1, None,
     [24186, 36103, 31300, 28525, 38887], [53.9, 64.4, 57.8, 57.1, 56.4]),
    ("economic_agri_rural", "Pertanian dan pembangunan luar bandar",
     "Agriculture and rural development", 2, "economic",
     [2219, 2133, 2314, 3016, 2894], [4.9, 3.8, 4.3, 6.0, 4.2]),
    ("economic_energy_utilities", "Tenaga dan kemudahan awam", "Energy and public utilities",
     2, "economic", [2475, 2254, 2760, 3586, 3330], [5.5, 4.0, 5.1, 7.2, 4.8]),
    ("economic_trade_industry", "Perdagangan dan perindustrian", "Trade and industry",
     2, "economic", [3800, 2512, 3054, 2438, 3121], [8.5, 4.5, 5.6, 4.9, 4.5]),
    ("economic_transport", "Pengangkutan", "Transport", 2, "economic",
     [10429, 17004, 13750, 10195, 15036], [23.2, 30.3, 25.4, 20.4, 21.8]),
    ("economic_communications", "Perhubungan", "Communications", 2, "economic",
     [126, 68, 71, 347, 600], [0.3, 0.1, 0.1, 0.7, 0.9]),
    ("economic_environment", "Alam sekitar", "Environment", 2, "economic",
     [2061, 1665, 1723, 1734, 1891], [4.6, 3.0, 3.2, 3.5, 2.7]),
    ("economic_other", "Lain-lain", "Others", 2, "economic",
     [3076, 10467, 7628, 7209, 12015], [6.9, 18.7, 14.1, 14.4, 17.5]),
    ("social", "Sosial", "Social", 1, None,
     [12425, 12873, 14484, 13058, 18369], [27.7, 22.9, 26.7, 26.1, 26.7]),
    ("social_education", "Pendidikan dan latihan", "Education and training", 2, "social",
     [6306, 6505, 7629, 5871, 8873], [14.0, 11.6, 14.1, 11.7, 12.9]),
    ("social_health", "Kesihatan", "Health", 2, "social",
     [1470, 1773, 1827, 2883, 4726], [3.3, 3.2, 3.4, 5.8, 6.8]),
    ("social_housing", "Perumahan", "Housing", 2, "social",
     [785, 1285, 2126, 1491, 1834], [1.7, 2.3, 3.9, 3.0, 2.7]),
    ("social_other", "Lain-lain", "Others", 2, "social",
     [3864, 3310, 2902, 2813, 2936], [8.7, 5.8, 5.3, 5.6, 4.3]),
    ("security", "Keselamatan", "Security", 1, None,
     [5334, 4929, 5614, 5557, 7780], [11.9, 8.8, 10.4, 11.1, 11.2]),
    ("security_defence", "Pertahanan", "Defence", 2, "security",
     [4315, 3262, 2931, 2665, 4860], [9.6, 5.8, 5.4, 5.3, 7.0]),
    ("security_internal", "Keselamatan dalam negeri", "Internal security", 2, "security",
     [1019, 1667, 2683, 2892, 2920], [2.3, 3.0, 5.0, 5.8, 4.2]),
    ("general_admin", "Pentadbiran am", "General administration", 1, None,
     [2939, 2190, 2775, 2860, 3964], [6.5, 3.9, 5.1, 5.7, 5.7]),
    ("total", "Jumlah", "Total", 1, None,
     [44884, 56095, 54173, 50000, 69000], [100.0, 100.0, 100.0, 100.0, 100.0]),
]
DEVEX_SECTOR_NOTE = {
    "economic_energy_utilities": "footnote: mainly electricity and water supply",
    "general_admin": "footnote: includes general services, maintenance and renovations",
}


def build_devex_sector():
    rows = []
    for key, bm, en, level, parent, amounts, shares in DEVEX_SECTOR:
        for year, amt, pct in zip(YEARS, amounts, shares):
            r = dict(table_no="3.3", line=key, line_bm=bm, line_en=en, level=level,
                      parent_line=parent, target_year=year, amount_rm_juta=amt,
                      pct_share=pct, basis=BASIS[year])
            r.update(row_common(9, 177, DEVEX_SECTOR_NOTE.get(key, "")))
            rows.append(r)
    return rows


# ---------------------------------------------------------------------------
# Validation -- reconcile every table's own leaf rows to its own printed subtotals
# and totals. Never corrects a figure; only flags PASS/FAIL against what's printed.
# ---------------------------------------------------------------------------
def validate(opex_component, opex_sector, devex_sector, headline):
    checks = []

    def check(name, year, expected, actual, tol=1.0):
        ok = expected is not None and actual is not None and abs(expected - actual) <= tol
        checks.append(dict(check=name, target_year=year, expected=expected, actual=actual,
                            result="PASS" if ok else "FAIL"))

    def by(rows, table_no):
        d = {}
        for r in rows:
            if r["table_no"] != table_no:
                continue
            d.setdefault(r["line"], {})[r["target_year"]] = r["amount_rm_juta"]
        return d

    oc = by(opex_component, "3.1")
    os_ = by(opex_sector, "3.2")
    ds = by(devex_sector, "3.3")
    hl = by(headline, "1.1")

    for y in YEARS:
        # 3.1: debt service domestic+external == debt_service
        check("3.1 debt_service = domestic+external", y, oc["debt_service"][y],
              oc["debt_service_domestic"][y] + oc["debt_service_external"][y])
        # 3.1: constitutional+other == grants_state_govts
        check("3.1 grants_state_govts = constitutional+other", y, oc["grants_state_govts"][y],
              oc["grants_constitutional"][y] + oc["grants_other"][y])
        # 3.1: all top-level (level 1) lines sum to total
        top_level_sum = sum(oc[k][y] for k, *_ in
                             [(k,) for k, bm, en, lvl, p, *_ in OPEX_COMPONENT if lvl == 1 and k != "total"])
        check("3.1 sum(level-1 lines) = total", y, oc["total"][y], top_level_sum)
        # 3.1 total == 1.1 operating_expenditure
        check("3.1 total = 1.1 operating_expenditure", y, hl.get("operating_expenditure", {}).get(y),
              oc["total"][y])

        # 3.2: each sector's sub-items sum to the sector
        for sector in ["economic", "social", "security"]:
            subs = [k for k, bm, en, lvl, p, *_ in OPEX_SECTOR if p == sector]
            check(f"3.2 {sector} = sum(sub-items)", y, os_[sector][y],
                  sum(os_[k][y] for k in subs))
        top_level_sum = sum(os_[k][y] for k, bm, en, lvl, p, *_ in OPEX_SECTOR if lvl == 1 and k != "total")
        check("3.2 sum(level-1 lines) = total", y, os_["total"][y], top_level_sum)
        check("3.2 total = 1.1 operating_expenditure", y, hl.get("operating_expenditure", {}).get(y),
              os_["total"][y])

        # 3.3: each sector's sub-items sum to the sector
        for sector in ["economic", "social", "security"]:
            subs = [k for k, bm, en, lvl, p, *_ in DEVEX_SECTOR if p == sector]
            check(f"3.3 {sector} = sum(sub-items)", y, ds[sector][y],
                  sum(ds[k][y] for k in subs))
        top_level_sum = sum(ds[k][y] for k, bm, en, lvl, p, *_ in DEVEX_SECTOR if lvl == 1 and k != "total")
        check("3.3 sum(level-1 lines) = total", y, ds["total"][y], top_level_sum)
        check("3.3 total = 1.1 development_expenditure_gross", y,
              hl.get("development_expenditure_gross", {}).get(y), ds["total"][y])

        # 1.1: net devex = gross - loan_recovery
        check("1.1 devex_net = gross - loan_recovery", y,
              hl["development_expenditure_net"][y],
              hl["development_expenditure_gross"][y] - hl["development_expenditure_loan_recovery"][y])
        # 1.1: overall balance = revenue - opex - devex_net (+ covid fund where printed)
        covid = hl.get("covid19_fund", {}).get(y) or 0
        check("1.1 overall_balance = revenue - opex - devex_net - covid_fund", y,
              hl["overall_balance"][y],
              hl["revenue"][y] - hl["operating_expenditure"][y] - hl["development_expenditure_net"][y] - covid,
              tol=2.0)

    return checks


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    headline = build_headline()
    opex_component = build_opex_component()
    opex_sector = build_opex_sector()
    devex_sector = build_devex_sector()

    write_csv(os.path.join(OUT_DIR, "fact_headline.csv"), headline,
              ["edition", "table_no", "line", "target_year", "amount_rm_juta", "pct_of_gdp", "basis",
               "source_file", "pdf_page", "printed_page", "retrieved_from", "retrieved_date", "note"])
    write_csv(os.path.join(OUT_DIR, "fact_opex_by_component.csv"), opex_component,
              ["edition", "table_no", "line", "line_bm", "line_en", "level", "parent_line", "target_year",
               "amount_rm_juta", "pct_share", "basis", "source_file", "pdf_page", "printed_page",
               "retrieved_from", "retrieved_date", "note"])
    write_csv(os.path.join(OUT_DIR, "fact_opex_by_sector.csv"), opex_sector,
              ["edition", "table_no", "line", "line_bm", "line_en", "level", "parent_line", "target_year",
               "amount_rm_juta", "pct_share", "basis", "source_file", "pdf_page", "printed_page",
               "retrieved_from", "retrieved_date", "note"])
    write_csv(os.path.join(OUT_DIR, "fact_devex_by_sector.csv"), devex_sector,
              ["edition", "table_no", "line", "line_bm", "line_en", "level", "parent_line", "target_year",
               "amount_rm_juta", "pct_share", "basis", "source_file", "pdf_page", "printed_page",
               "retrieved_from", "retrieved_date", "note"])

    checks = validate(opex_component, opex_sector, devex_sector, headline)
    write_csv(os.path.join(OUT_DIR, "_validation.csv"), checks,
              ["check", "target_year", "expected", "actual", "result"])

    n_fail = sum(1 for c in checks if c["result"] == "FAIL")
    print(f"Wrote {len(headline)} headline rows, {len(opex_component)} opex-by-component rows, "
          f"{len(opex_sector)} opex-by-sector rows, {len(devex_sector)} devex-by-sector rows.")
    print(f"Validation: {len(checks) - n_fail}/{len(checks)} PASS")
    if n_fail:
        for c in checks:
            if c["result"] == "FAIL":
                print("FAIL:", c)


if __name__ == "__main__":
    main()
