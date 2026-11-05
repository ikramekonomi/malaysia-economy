# Blind verifier pass: grants by name to the territories' administrations (2026-11-05)

A separate agent with no access to `core/pipeline/`, `apps/tools/*.py` (beyond docstrings), the eval and
reproduction scripts or git history re-derived the 40 `fact_money_flow` rows paid to Perbadanan Putrajaya
(E000064), Perbadanan Labuan (E000065) and Dewan Bandaraya Kuala Lumpur (E000066) from L1 (PKKP
`fact_opex_detail.csv`, each year from its own volume): vote B.32 (from FY2023 B.06), a block whose printed name
starts with the body's name, the block's object 40000 line.

**Result: 40 of 40 re-derived exactly** (amount, period, from/to entity, geo, geo method, PDF and printed page,
edition, `l1_ref` = the CSV's physical line with the header as line 1, file sha256 = `meta/l0_archive.csv` for
13 of 14 volumes; FY2020 is the unarchived volume and carries CV17). No missing or extra rows, at most one
block per body per year, every matched block holds only its 40000 line (nothing understated within a block).
19 of the 40 checked on the printed page (FY2010, 2011, 2014, 2017, 2019, 2021, 2024; archive sha256 matched):
all agree. `get_flows` for the three bodies and MY-14/15/16 answers correctly; no L1 line is used twice among
the 276 flows; the class grants (E000063) appear only under `not_split_by_state`.

| # | Finding | Severity | Done |
|---|---|---|---|
| 1 | FY2010 B.32 070500 'Kos Operasi & Penyelenggaraan ITIS-DBKL' RM38m and 070600 'Penyelenggaraan Harta Bukan Milik DBKL' RM10m (p136): tagged DBKL, not stated as a grant to it | medium | declared not loaded in F11 and `FLOW_COVERAGE` |
| 2 | FY2014 lines tagged `(DBKL)` / `(PL)`: duty and licence collection RM2m, Bukit Tagar tipping fee RM18.43m, BIMP-EAGA games RM2.28m, ferry fare discount RM11m (p186-187) | medium | declared in F11 (possibly paid through the administration; loaded only when a page says so) |
| 3 | FY2013 090400 Borneo Games `- PL` RM1.5m | low | declared in F11 |
| 4 | Lines naming a territory with no recipient (Putrajaya infrastructure, PICC, buses, lake desilting, ferry discount after 2016) | low | listed in F11 as services, recipient not stated |
| 5 | DBKL has no grant by name in FY2019: genuine (programme 020000's 40000 total equals its four printed lines) | none | — |
| 6 | FY2009 prints programme-level grants (Putrajaya RM101m, Labuan RM36.36m) as `object_program` rows; FY2009 is skipped by design | low | named in F11 |
| 7 | CV25 and the `core/README.md` table still said "T.12 and B.11" | low | both updated |
| 8 | FY2020's three rows rest on L1 only (no archived PDF) | low | CV17 already says so |
| 9 | FY2014 PDF prints Putrajaya's programme header as 040100; L1 has 040000 with a blank programme name (already in that year's validation) | info | — |
