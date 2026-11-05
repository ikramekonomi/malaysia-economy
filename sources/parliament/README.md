# sources/parliament — Dewan Rakyat answers (figures published nowhere else)

Ministers' written answers often print figures that appear in no other publication, such as allocations by
state. Each answer is kept as printed, with its date, question number and page. Personal names are not kept:
a question is identified by its date and number.

| held | what | pages |
|---|---|---|
| `raw/JBL12122024.pdf`: written answers of 12 Dec 2024 (sha256 in `data/_documents_manifest.csv`; parlimen.gov.my re-issues these collections, so the hash names the copy held) | Q243: federal development allocation, spending, % spent and project count by state, for RMKe-12's Rolling Plans RP1-RP4 (2021-2024). Source line: Sistem MyProjek, as at 4 Nov 2024 | 701-704 |

* `data/fact_dr_devex_by_state.csv`: 224 cells (14 rows × 4 rolling plans × 4 measures).
  'Wilayah Persekutuan' is the three Federal Territories together. There is no multi-state row.
* `pipeline/extract_dr_devex_by_state.py` extracts the table. `pipeline/validate_dr_devex_by_state.py` checks it:
  * D1: % spent = spending / allocation;
  * D2: coverage;
  * D3 (INFO): the rows' spending against PKKP's audited gross development spending of the same year.

  Results are in `data/_validation_dr_devex_by_state.csv`.

How to read it:
* **The figures come from MyProjek** (the project-monitoring system), not the audited accounts. In D3 the 14
  rows' spending is 59% of PKKP's development spending in 2021 and 2022, 68% in 2023, and 45% in 2024. RP4 is
  as at 4 Nov 2024, part of the year.
* **The Federal Territories row spends 131% of its allocation in RP1.** It likely carries national projects run
  from Putrajaya and Kuala Lumpur.
* **RP3 is misprinted for 7 states.** Their spending and % columns repeat the allocation
  (`data/_source_anomalies.csv`). Their RP3 spending is not usable.
* **Not used for placement.** These figures do not reconcile to the accounts (D29, D30), so
  `gap_federal_placement` does not use them.

Not yet extracted, all located by the 2026-11-05 search (paths and sha256s in the session notes):
* 26 May 2016 oral Q12: 2011-2015 spending by state, yearly; OCR text;
* Mar 2025 Q248: RMK9-RMK11 allocation and spending by state;
* Mar 2024 Q380: 2022-2024 allocation to the sen;
* Dec 2025 Q715: RMK10-RMK12 allocation.
