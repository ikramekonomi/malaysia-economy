# Federal spending placed by state: blind verifier pass (2026-11-05)

Decision D29: federal spending is placed in a state only where the federal accounts name the place (method
declared and committed before any result by state, commit 5642f89; `core/pipeline/build_federal_placement.py`).

**Result.** The verifier wrote its own matcher from the declared method and compared all 14,112 project leaves
of all 15 years row by row (L1 joins 1:1, amounts and names identical); re-derived the view for 7 years
(per-state amounts, federal totals from the cited observations, placed_share, states + not placed = MY = leaves
+ grants + not itemised); checked 21 placed rows on sha256-verified PDFs (FY2009, 2016, 2019, 2024); confirmed
the FY2009 shortfall (49,515,355,570.54 printed vs 49,104,778,320.66 in leaves) and every prose claim; the tool
withholds state amounts and says why.

| # | Finding | Severity | Done |
|---|---|---|---|
| 1 | Iskandar projects (P.06 00107 and others) left unplaced under that name: RM803.1m missed (FY2009 624.4m) | high | `meta/place_gazetteer.csv` (each place with its proof): Iskandar placed in Johor |
| 2 | IADA Pekan never placed ('pekan' is a stop word): RM99.7m | medium | the phrase `iada pekan` is listed (Pahang) |
| 3 | towns and islands outside the district list missed (Cyberjaya, Ipoh, Kangar, Taiping, Shah Alam, Bangi, Sungai Petani, Layang-layang, Sipadan, 'P.Pinang'): about RM56m | medium | listed with proofs (`parsed_place`); 'P.Pinang' and 'KL' as state aliases |
| 4 | misplaced: '(di Luar Kuala Lumpur)' placed in KL; a road through Perak, Kelantan and Terengganu placed in Kelantan; a 'Jalan Duta / Nusajaya, Johor' line placed in Johor: RM43.0m | medium | 'di luar Kuala Lumpur' / 'di luar KL' removed before matching; Simpang Pulai, Kuala Berang and Jalan Duta listed, so those lines are `multiple_states` |
| 5 | Peninsula lines (RM4.24b) can never be placed while the Sabah and Sarawak lines are: Sabah and Sarawak hold 54% of placed money partly by layout; not disclosed | medium | new method `peninsula` with its own column; disclosed in CV27, README and the tool's reading note |
| 6 | FY2009 grants by name shown as 0 (no flows held) | low-medium | blank (not held) and a note |
| 7 | code placed 'districts of one state' while the docstring said 'exactly one district' | low | docstring and D29 say what the code does |
| 8 | the CSV carries state amounts the note called 'not published' | low-medium | note: kept for verification, withheld by the tools and from publication; a floor, not what the state received |
| 9 | placed lines include loans, equity and regional agencies (KEDA serves Perlis too) | low | CV27 says so |
| 10 | pdf_page cites the name page; the amount is on the facing page | low | stated in the README |

After the fixes: stated_state 2,205, parsed_district 263, parsed_place 75, multiple_states 104, peninsula 136,
none 11,329; placed_share 0.6-3.9% (FY2009 3.2%); P1-P6 as before (P1 WARN for FY2009); 241 eval questions pass.
