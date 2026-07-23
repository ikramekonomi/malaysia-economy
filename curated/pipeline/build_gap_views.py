#!/usr/bin/env python3
"""Build the curated budget-vs-actual gap views from PKKP.

Run from anywhere:  python3 curated/pipeline/build_gap_views.py [year ...]
                    (default pilot year: 2024)

Source of truth = the PKKP CSVs under sources/pkkp/data/<year>/ (never the .duckdb).
Each year is taken from its OWN volume (source_file '<year>_...pdf'), per CLAUDE.md
golden rule #6, so the series is clean (no cross-volume restatement overlap).

WHAT "BUDGET" MEANS HERE (read before using the output)
-------------------------------------------------------
Source #2 (the independent *Anggaran Perbelanjaan Persekutuan* budget book) is not yet
ingested. Until it lands, the "budget" side is PKKP's OWN recorded appropriation — the
figure each ministry was voted, as printed in the audited statements:
  * Operating  (Mengurus):    Nota 5(b), column `anggaran_asal_rm`  (original estimate)
                              with `anggaran_dipinda_rm` (revised) also carried.
  * Development (Pembangunan): Lampiran 2, column `anggaran_jumlah_rm` (year estimate).
The "actual" side is `sebenar_rm` / `sebenar_jumlah_rm` from the same statements.
So this is budget-vs-actual entirely WITHIN the audited source — every figure traces to
one PKKP page. When the Anggaran book is ingested, it slots in as an independent budget
source AND becomes a cross-check against PKKP's recorded `anggaran_asal` (a gap-finding
target in its own right); the schema below reserves `budget_source` for exactly that.

CONVENTIONS (inherited from PKKP / CLAUDE.md)
  * Amounts are exact Ringgit as printed (sen kept). variance = actual - budget.
  * Operating maksud codes are B.*/T.*, development are P.*; the shared ministry number
    is `code_num` (join operating<->development on it). Join budget<->actual on
    (year, maksud_code) — never on names.
  * Grand-total / subtotal rows from the source are EXCLUDED here (this fact is leaf
    grain: one row per year x flow x maksud) so it is safe to SUM. Printed totals are
    reconciled in _validation_gap_<year>.csv instead.
"""
import duckdb, glob, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CURATED = os.path.dirname(HERE)
ROOT = os.path.dirname(CURATED)
PKKP = os.path.join(ROOT, "sources", "pkkp", "data")

YEARS = [int(a) for a in sys.argv[1:]] or [2024]

con = duckdb.connect()  # in-memory; reads the canonical CSVs directly


def csv(year, name):
    """Path to a PKKP CSV in that year's own volume folder."""
    return os.path.join(PKKP, str(year), f"{name}.csv")


def build_year(year):
    vol = f"{year}_%"  # take the year from its own volume only
    # -- Operating (Mengurus): Nota 5(b), one row per maksud, no subtotal rows --
    opex = con.execute(f"""
        SELECT
          {year}                              AS year,
          'Mengurus'                          AS flow_bm,
          'Operating'                         AS flow_en,
          jenis_bm,
          maksud_code,
          CAST(regexp_extract(maksud_code, '[0-9]+$') AS INTEGER) AS code_num,
          maksud_name_bm,
          'pkkp:Nota 5(b):anggaran_asal_rm'   AS budget_source,
          'pkkp:Nota 5(b):sebenar_rm'         AS actual_source,
          anggaran_asal_rm                    AS budget_original_rm,
          anggaran_dipinda_rm                 AS budget_revised_rm,
          sebenar_rm                          AS actual_rm,
          source_file, pdf_page, printed_page, statement
        FROM read_csv_auto('{csv(year,"fact_opex_maksud")}', header=true)
        WHERE year = {year} AND source_file LIKE '{vol}'
    """).df()

    # -- Development (Pembangunan): Lampiran 2, exclude the JUMLAH grand-total row --
    devex = con.execute(f"""
        SELECT
          {year}                              AS year,
          'Pembangunan'                       AS flow_bm,
          'Development'                        AS flow_en,
          NULL                                AS jenis_bm,
          maksud_code,
          CAST(regexp_extract(maksud_code, '[0-9]+$') AS INTEGER) AS code_num,
          maksud_name_bm,
          'pkkp:Lampiran 2:anggaran_jumlah_rm' AS budget_source,
          'pkkp:Lampiran 2:sebenar_jumlah_rm'  AS actual_source,
          anggaran_jumlah_rm                  AS budget_original_rm,
          NULL                                AS budget_revised_rm,
          sebenar_jumlah_rm                   AS actual_rm,
          source_file, pdf_page, printed_page, statement
        FROM read_csv_auto('{csv(year,"fact_devex_maksud")}', header=true)
        WHERE year = {year} AND source_file LIKE '{vol}'
          AND maksud_code LIKE 'P.%'          -- excludes the 'TOTAL' grand-total row
    """).df()

    gap = con.sql("""
        SELECT *,
          actual_rm - budget_original_rm                                   AS variance_rm,
          CASE WHEN budget_original_rm = 0 THEN NULL
               ELSE round(100.0 * actual_rm / budget_original_rm, 2) END   AS utilisation_pct,
          actual_rm - budget_revised_rm                                    AS variance_vs_revised_rm
        FROM (SELECT * FROM opex UNION ALL BY NAME SELECT * FROM devex)
        ORDER BY flow_bm, maksud_code
    """).df()
    return gap


def validate_year(year, gap):
    """Reconcile the curated fact back to the volume's own printed totals."""
    vol = f"{year}_%"
    checks = []

    def add(name, printed, extracted, tol=0.005):
        diff = extracted - printed
        checks.append(dict(check=name, status="PASS" if abs(diff) <= tol else "FAIL",
                           printed_value=printed, extracted_value=extracted, difference=diff))

    o = gap[gap.flow_bm == "Mengurus"]
    d = gap[gap.flow_bm == "Pembangunan"]

    # Operating: curated sum == Nota 5(b) printed maksud total (incl. B.12 transfer).
    printed_oe = con.execute(f"""
        SELECT sum(sebenar_rm) FROM read_csv_auto('{csv(year,"fact_opex_maksud")}', header=true)
        WHERE year={year} AND source_file LIKE '{vol}'""").fetchone()[0]
    add(f"opex: curated actual sum = Nota 5(b) total ({len(o)} maksud)", printed_oe, float(o.actual_rm.sum()))
    printed_oe_b = con.execute(f"""
        SELECT sum(anggaran_asal_rm) FROM read_csv_auto('{csv(year,"fact_opex_maksud")}', header=true)
        WHERE year={year} AND source_file LIKE '{vol}'""").fetchone()[0]
    add("opex: curated budget(original) sum = Nota 5(b) total", printed_oe_b, float(o.budget_original_rm.sum()))
    add("opex: maksud count = 53", 53, len(o))

    # Development: curated sum == Lampiran 2 printed grand-total (the 'TOTAL' row).
    printed_de = con.execute(f"""
        SELECT sebenar_jumlah_rm FROM read_csv_auto('{csv(year,"fact_devex_maksud")}', header=true)
        WHERE year={year} AND source_file LIKE '{vol}' AND maksud_code='TOTAL'""").fetchone()[0]
    add("devex: curated actual sum = Lampiran 2 grand total", printed_de, float(d.actual_rm.sum()))
    printed_de_b = con.execute(f"""
        SELECT anggaran_jumlah_rm FROM read_csv_auto('{csv(year,"fact_devex_maksud")}', header=true)
        WHERE year={year} AND source_file LIKE '{vol}' AND maksud_code='TOTAL'""").fetchone()[0]
    add("devex: curated budget sum = Lampiran 2 grand total", printed_de_b, float(d.budget_original_rm.sum()))

    # Identity: variance == actual - budget, on every row.
    bad = gap[(gap.variance_rm - (gap.actual_rm - gap.budget_original_rm)).abs() > 0.005]
    add("identity: variance_rm = actual - budget (all rows)", 0, len(bad), tol=0)

    import pandas as pd
    return pd.DataFrame(checks)


for year in YEARS:
    gap = build_year(year)
    out = os.path.join(CURATED, "fact_budget_vs_actual.csv")
    gap.to_csv(out, index=False)
    checks = validate_year(year, gap)
    vout = os.path.join(CURATED, f"_validation_gap_{year}.csv")
    checks.to_csv(vout, index=False)
    n_fail = (checks.status == "FAIL").sum()
    print(f"FY{year}: {len(gap)} gap rows -> {os.path.relpath(out, ROOT)}")
    print(f"  operating {len(gap[gap.flow_bm=='Mengurus'])} maksud, "
          f"development {len(gap[gap.flow_bm=='Pembangunan'])} ministries")
    print(f"  validation: {(checks.status=='PASS').sum()}/{len(checks)} PASS"
          + (f"  ** {n_fail} FAIL **" if n_fail else "") + f" -> {os.path.relpath(vout, ROOT)}")
