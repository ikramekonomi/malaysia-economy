# PKKP Data Warehouse — Analyst Quickstart

Malaysia's audited Federal Government Financial Statements (Penyata Kewangan Kerajaan Persekutuan), extracted to full detail — **all 16 volumes FY2009–FY2024 complete** (~580k numeric data points; 76,320 object-level operating-expenditure rows alone). Every figure carries provenance (source PDF, page) and reconciles to the printed totals — see `VALIDATION_REPORT.md` for the verification methodology and `DATA_DICTIONARY.md` for every table. One exception: the FY2015 volume is an image-only scan whose object-leaf/project-leaf amounts are OCR-provisional (its statement/register/panel/ministry-level tables are fully verified) — details in `VALIDATION_REPORT.md`.

## Open it (pick one)

**DuckDB CLI** (https://duckdb.org/docs/installation — single binary):
```
duckdb pkkp.duckdb
SHOW TABLES;
```

**Python:**
```python
import duckdb
con = duckdb.connect("pkkp.duckdb", read_only=True)
con.sql("SHOW TABLES").show()
```

**R:** `library(duckdb); con <- dbConnect(duckdb(), "pkkp.duckdb", read_only=TRUE)`

**No DuckDB?** The CSVs are the canonical layer — open any of them directly; the .duckdb file is just the same data pre-loaded with convenience views. Rebuild it anytime: `python3 pipeline/build_duckdb_multi.py`.

## Things to know before querying

1. **row_type discipline.** Detail tables keep printed subtotal rows on purpose. SUM only leaf rows: `row_type='object_aktiviti'` (opex detail), `'project'` (devex), `'detail'` (most others) — or you will double count.
2. **Two volumes can report the same year.** Each volume carries its own year plus prior-year comparatives, and governments restate. Filter `source_file` (or take each year from its own volume) for clean time series. Known restatements are catalogued: `2023/_restatements_2023_vs_2024volume.csv` (82) and `2022/_restatements_2022_vs_2023volume.csv` (152, incl. three declared restatements localized to exact rows).
3. **Units.** `*_rm` columns are exact Ringgit as printed (sen where printed). The `fact_timeseries_*` panels are RM juta (millions), rounded by the source.
4. **Labels are Malay (canonical).** `dim_maksud.name_en` has English glosses for ministries. Join on codes (`maksud_code`, `projek_code`), never on names — the source has renames and even typos (preserved faithfully).

## Starter queries

```sql
-- Ministry operating spend, both years (actual vs budget)
SELECT year, maksud_code, maksud_name_bm,
       anggaran_asal_rm/1e9 AS budget_bil, sebenar_rm/1e9 AS actual_bil
FROM fact_opex_maksud ORDER BY year, sebenar_rm DESC;

-- Biggest development projects of 2024
SELECT maksud_code, projek_code, name_bm,
       sebenar_jumlah_rm/1e6 AS spent_2024_mil, kos_keseluruhan_rm/1e6 AS approved_cost_mil
FROM v_devex_projects WHERE year = 2024 ORDER BY sebenar_jumlah_rm DESC LIMIT 25;

-- Where did KKM's money go, object by object (leaf grain)
SELECT program_name_bm, aktiviti_name_bm, objek_class_bm, sebenar_rm
FROM v_opex_leaf WHERE maksud_code = 'B.42' AND year = 2024 ORDER BY sebenar_rm DESC;

-- Full 25-year revenue picture: chain each volume's own year (exact, no restatement overlap)
SELECT year, sum(sebenar_rm)/1e9 AS revenue_bil
FROM fact_revenue WHERE row_type='detail'
GROUP BY year ORDER BY year;   -- spans 2009–2024 from 16 volumes

-- 15-year fiscal picture (RM juta, from the 2024 volume's panel)
SELECT year, amount_rm_juta FROM fact_timeseries_2010_2024
WHERE line_item_bm = 'Jumlah Hasil' ORDER BY year;

-- Federal debt by individual issue, with maturity
SELECT instrument_bm, perihal_bm, kadar_faedah, tarikh_tebusan, amaun_belum_selesai_rm/1e9 AS outstanding_bil
FROM fact_debt_issues WHERE row_type='detail' AND year=2024 ORDER BY outstanding_bil DESC;

-- Audit trail for any number: where does it come from?
SELECT * FROM fact_revenue WHERE item_bm LIKE '%Petroleum%' OR item_bm LIKE '%Pendapatan%';
-- → source_file + pdf_page point to the exact page of the audited statement.
```

## Integrity self-check

The reconciliation checks ship inside the database:
```sql
SELECT status, count(*) FROM meta_validation_checks GROUP BY status;          -- 2024 volume
SELECT status, count(*) FROM meta_validation_checks_2023 GROUP BY status;     -- 2023 volume
SELECT status, count(*) FROM meta_validation_checks_2022 GROUP BY status;     -- 2022 volume
SELECT status, count(*) FROM meta_validation_checks_2021 GROUP BY status;     -- 2021 volume
SELECT status, count(*) FROM meta_validation_checks_2020 GROUP BY status;     -- 2020 volume
SELECT status, count(*) FROM meta_validation_checks_2019 GROUP BY status;     -- 2019 volume
SELECT status, count(*) FROM meta_validation_checks_2018 GROUP BY status;     -- 2018 volume
SELECT status, count(*) FROM meta_validation_checks_2017 GROUP BY status;     -- 2017 volume
SELECT status, count(*) FROM meta_validation_checks_2016 GROUP BY status;     -- 2016 volume
SELECT status, count(*) FROM meta_validation_checks_2014 GROUP BY status;     -- 2014 volume
-- 2015 is the OCR volume; see meta_validation_checks_2015 + meta_unresolved_ocr_cells_2015
```
Every FAIL row is a proven misprint in the government's own volume (documented with proofs in the check files); everything else passes to the sen.
