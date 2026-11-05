# Blind verifier: gap_obligations_growth (2026-11-06)

A separate agent was given only the declared method (the docstring), not the build code. It re-derived the 66
rows and 66 observations from PKKP L1 (memorandum, guarantee registers, notes), each year from its own volume.

It confirmed:
- every amount, growth, ratio, index and status, with 0 mismatches;
- O2 and the FY2009-2011 register being loans only;
- the five O3 restatements;
- that Hutang Awam and Hutang Persekutuan are the same scope, and that the memorandum debt equals MOF's federal
  government debt;
- the memorandum identities;
- the tool.

| # | finding | severity | outcome |
|---|---|---|---|
| 1 | Deposit guarantees are printed for FY2010-2011 in Nota 10(b), not only in the register from FY2012 | medium | added to core from Nota 10(b) (C21: the FY2012 note equals the register); the series now starts in FY2010 (68 rows) |
| 2 | PKKP's PFI line is two vehicles; MOF's PPP and PFI obligations are about 4.5 times larger and growing; the decline is real repayment | medium | note on every PFI row, indicator definition, README |
| 3 | Committed guarantees overlap the statutory loan guarantees (RM210.9b of RM236.2b in 2024); no caveat said so | medium | CV30, notes, README |
| 4 | Deposit guarantees are mostly EPF members' savings; "overlaps deposit insurance" was the wrong wording | medium | reworded in the notes, CV30, the indicator and curated/OBLIGATIONS.md (whether any of these bodies is a PIDM member was not checked) |
| 5 | The FY2017 deposit "restatement" is a change of scope (SSPN-i added) | low | named in the FY2018 row's note (like-for-like growth 9.03%); the generic note now says "restatement or change of scope" |
| 6 | O3 did not say which years it cannot test | low | it now does (57 of 62) |
| 7 | CV17 was not carried to rows whose growth uses an unarchived prior year | low | each row carries the caveats of every observation it uses |
| 8 | The FY2018 volume prints 2017 comparatives that the method leaves out | info | stated in the README (golden rule 6) |
| 9 | The docstring said 'the benchmark'; the data say `the_benchmark` | info | docstring fixed |

Outside this view, found in passing: `sources/pkkp/data/2019-2024/fact_commitment_detail.csv` lacks the KOMITMEN
PAMPASAN rows. They are present in fact_debt, and this view is not affected. This is left for a separate fix.
