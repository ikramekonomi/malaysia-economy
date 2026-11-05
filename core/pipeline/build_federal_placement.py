#!/usr/bin/env python3
"""Where federal spending lands, by state (Phase 3, DATA_MODEL §10 and §13 track A): what can be placed, and how much.

  python3 core/pipeline/build_federal_placement.py
    -> core/fact_placement.csv            one row per audited development project per year, with its place
    -> core/gap_federal_placement.csv     state x year: federal money placed in the state, and the year's placed_share
    -> core/_validation_placement.csv     checks P1-P6

Method (declared 2026-11-05, before any result by state was computed; committed on its own before the code. Only
the national share of development spending whose project name contains a state name, by year, was looked at
while scoping: 3-15%):

* Scope: federal spending as audited in PKKP, each year from its own volume (golden rule 6), FY2009-2024 except
  FY2015 (an image-only scan: its project leaves are OCR-provisional; CLAUDE.md). The denominator is the year's
  federal total spending as gap_need_vs_money uses it: opex + gross devex + the COVID-19 Fund (2020-2022).
* What is placed, and how (geo_method), in this order; nothing else:
  1. `stated_state`: a development project (PKKP Penyata Perbelanjaan Pembangunan, project leaf rows, its actual
     spending `sebenar_jumlah_rm`) whose printed name names exactly one state or Federal Territory.
  2. `parsed_district`: a project whose name names no state but exactly one district of one state (DOSM 2020
     districts in core/dim_geo.csv), matched as whole words; district names that are also common words or
     compass phrases are not used (STOP_DISTRICTS, declared below), nor a district inside a regional name
     (Lembah Klang).
  3. `grant_by_name`: a federal grant whose recipient is a named state government or territory administration
     (core/fact_money_flow.csv, geo_method `stated`); the class grants (all states, all local authorities)
     are never split (D27).
  A project naming two or more states (or a state and another state's district) is `multiple_states` and is not
  placed; a project naming none is `none`. Both stay `_unallocated` with their totals shown.
* Not used, by design: an agency's seat (it would put ministries' headquarters spending in Putrajaya), any
  allocation key (population, staff counts, need): placing money by formula makes a map look more complete than
  the accounts are (D27, DATA_MODEL §13). Operating spending (salaries in schools and clinics, subsidies, cash
  transfers: most of the money) has no place in the federal accounts and is not placed here; the sources that
  could place it (KKM/KPM by state, STR/JKM by state, registry `social_transfers_by_state`) are not held.
* A place in a project name says where the project is, not who benefits; a statewide or cross-border project is
  placed in the state it names. geo_confidence: `medium` for stated_state and grant_by_name, `low` for
  parsed_district.
* Output: every state and Federal Territory (all 16, golden rule 11) x every year, plus an `_unallocated` row and
  an `MY` row per year. placed_share = placed RM in all states / federal total RM, reported on every row; the
  per-state amounts are published only where placed_share is at least 60% (DATA_MODEL §10 guard), otherwise the
  row says why. No ranking.
* Checks: P1 project leaves add up to each volume's printed development total; P2 every project row is placed by
  exactly one method and the methods add up to the leaf total; P3 a stated or parsed place cites the words
  matched; P4 grants by name equal fact_money_flow's stated flows; P5 the 16 places + `_unallocated` = the MY
  row; P6 placed_share in [0, 1].
"""
