# Blind verifiers: DOSM report tables and the development project lists (2026-11-06)

Two independent agents checked the work. Neither saw the extraction, validation or mapping code; each re-derived
everything from the original files with its own scripts.

## DOSM survey-report tables (`sources/dosm_reports`, core rows under `dosm:report.*`)

The verifier checked every one of the 1,059 core rows, and all 75,794 L1 cells against the workbooks.

**Core: no errors.** Every row's indicator, place, year, breakdown members and printed figure match the printed
headers. The declared tables give 1,229 keys, which split as:
* 1,059 loaded once;
* 170 already held from the open data with equal figures.

None is missing, none is loaded twice, and none differs between two tables of one report.

**Findings and what was done:**
1. **SD1 was incomplete.** The poverty report itself prints Terengganu's 2024 absolute poverty as 5.8 in its
   district table (Jadual 5.4, I100, PDF p. 72). It prints 4.8 in Jadual 3.1 and 5.3. Done:
   * the SD1 proof is rewritten, and SD1b is registered;
   * a new check, R5, compares the figures the report prints twice: 203 of 204 equal, and the exception is
     SD1b;
   * the README caveats are corrected.

   The strata imply 4.7-4.8.
2. **The income-class tables (2.13, 2.14, 3.11, 3.12) had no row labels**, because their bounds were read as
   data. Range bounds (`2,000 – 2,999`) are now labels; the coverage file counts them under `in_label_columns`.
3. **Text rows were glued onto the label above:** section headers, all-`n.a` rows and footnotes. Now:
   * `n.a` (without the dot) counts as a marker;
   * a text-only line is a continuation (or the English half, `Total` under `Jumlah`) unless it is a heading or
     a state;
   * the notes rule also matches `Bermula tahun` / `Data merujuk`.
4. **Stacked blocks lost their block.** Headings now nest in `section` (`Lelaki | Penengah (RM)`), and a
   measure's total row heads its block. The HES 2.1 and 2.2 Tahun column is a label, and the state is carried
   down to its 2024 row.
5. **Header rows were captured as data:** the years of a second block (household_income 6.4, 6.5) and percentile
   rows. A header row inside a table now heads the rows below it.
6. **Sheet names had been trimmed.** They are now kept exactly.
7. **Mixed precision** between report rows (printed figure) and open-data rows (stored figure): this is
   documented and unchanged.
8. **Markers handled inconsistently.** Markers are kept as cells with an empty value. Core skips them (12 cells
   in the declared tables, `marker_at_l1`).

After the fixes core is unchanged: the same 1,059 rows, with only their `l1_ref` row numbers moved.

## Development project lists (`fact_anggaran_projek_<year>`) and `gap_project_budget_vs_actual`

**Extraction: no errors.** The verifier used two parsers (pdftotext lines, and pdfplumber words by column) over
every vote of the three books. Codes, all five columns, titles, programmes and pages all match. The 12 rounding
anomalies, and no others, reproduce. Every vote total equals the books' summary pages.

**Findings and what was done:**
1. **P.70, the contingency reserve, was inside the FY2024 headline.** Its RM447.8m actual is offset in the
   accounts by P.70 00200. P.70 rows now read `reserve` and are left out of every total. The headline is
   corrected:

   | | First count (reserve inside) | Corrected (697 projects) |
   |---|---|---|
   | Tabled | RM91.99b | RM89.99b |
   | Allocation (PKKP) | RM80.03b | RM78.03b |
   | Actual (PKKP) | RM79.37b | RM78.93b |

   Spending is 101.1% of the allocation.
2. **A negative actual was labelled `overspent`.** It now reads `offset_entry`.
3. **Six of the eight `different` pairs were one line renamed** (MDAG / Schoolnet Fasa 2 at the same
   RM217,249,700). Two different names with the same total project cost to within 5% are now `renamed` and
   joined: 5 pairs. P.23 41000 (BES / SESB) stays `different` under the rule.
4. **Two of the four 'revised figure not used' cases were renames.** The cost rule now joins them.
5. **Two doubtful `similar` joins** (P.06 00119, P.43 00900) matched only on generic words. Generic words are
   now ignored, so both read `different`.
6. **PKKP names with doubled glyphs** ('PPrroojjeekk JJaalluurr LLeebbaarr', 11 years). This is an L1 extraction
   bug in sources/pkkp. It needs the PDFs on Actions, so it is left for a separate fix.
7. **`printed_page` is blank on a page that prints no folio** (2025 p303). Left as printed.
8. **Column (4) at project level:** the README caveat now gives project counts per book.
