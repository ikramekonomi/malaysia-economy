# Handover

The warehouse is a gift to IKRAM from its first builder, Ammar Roslizar, handed over on 2026-11-06. This page covers what
is built, what is checked, what is open and how to keep it running. Read it with [`README.md`](README.md), which
says what the warehouse is, and [`CLAUDE.md`](CLAUDE.md), which gives the rules for working in it.

---

## 1. On day one

The repository was **copied**, not transferred: `ikramekonomi/malaysia-economy` (the account of
ammar.roslizar@ikram.org.my) is IKRAM's own, and the original `ammarroslizar/malaysia-economy` is archived as a
read-only record. Old links to the original do not redirect here.

1. **Check the copy is whole.**
   - **Code:** the code and its full history are here.
   - **Archive:** the `l0-archive` release (the raw PDFs, by sha256) holds
     470 files. Check with `gh release view l0-archive --json assets --jq '.assets | length'`.
     The index is `meta/l0_archive.csv`.
2. **Allow the workflows to write.** Settings → Actions → General → Workflow permissions:
   - choose *Read and write permissions*;
   - tick *Allow GitHub Actions to create and approve pull requests*.

   The daily DOSM refresh and the archive workflows need both. Enable workflows in the Actions tab if GitHub paused
   them.
3. **Turn on the site.** Settings → Pages → Source: **GitHub Actions**, then Actions → *Site* → *Run workflow*. The site
   goes to **https://ikramekonomi.github.io/malaysia-economy/** and redeploys on every push to `main`.
   - **Private repo:** Pages needs a paid plan (GitHub Pro or Team). This is the recommended setup, because it keeps
     the raw archive private.
   - **Public repo:** the `l0-archive` release becomes public too.
4. **Check the checks.** Actions → *Validate* → *Run workflow*. It must be green.
5. **Check the daily refresh.** Actions → *DOSM refresh* runs every day at 14:17 MYT. It opens a PR, which merges
   itself only when every verifier is clean. If it has failed several days running, open its log.
6. **Nothing else depends on the previous owner.** No secrets are used; the workflows use GitHub's built-in token.
   The old Claude scheduled task that refreshed DOSM lived on the previous owner's account and stopped with it;
   `dosm-refresh.yml` does the same job here.

## 2. What is built

| Layer | What | Where | State |
|---|---|---|---|
| L0 | raw PDFs and files, by sha256 | release `l0-archive`; index `meta/l0_archive.csv` | 470 files (13.4 GB) |
| L1 | source tables as printed: pkkp, anggaran, anggaran-hasil, mof-fiscal-outlook, bnm, dosm, dosm_reports, audit-negara, states, rmk, parliament, state-budgets | `sources/<name>/` | verified per source (each has `_validation*.csv`) |
| L2 | conformed core: 6 dimensions, `fact_observation` (223,090 rows, 125 indicators), money flows, records | `core/` | built; machine-checked; blind-verified source by source |
| L3 | 9 gap views (below) | `core/gap_*.csv` | built and blind-verified, except `gap_audit_recurrence` (draft) |
| L4 | agent tools; models; the site | `apps/tools/`, `apps/models/`, `site/` | tools have 270 eval questions in CI; the site is new (2026-11-06) |

**Gap views on the site:**
* `gap_budget_vs_actual`
* `gap_project_budget_vs_actual`
* `gap_revenue_estimate_vs_collected`
* `gap_reported_vs_audited`
* `gap_obligations_growth`
* `gap_target_vs_outcome`
* `gap_need_vs_money`
* `gap_federal_vs_state`
* `gap_federal_placement`

**Not on the site:**
* `gap_audit_recurrence` and the audit links: they failed blind verification (section 4).
* Every `no_redistribution` series.
* Federal amounts by state below the 60% placement guard.

**Before IKRAM publishes any figure,** it needs a human spot-check (`qa/spot_check/`, `docs/DATA_MODEL.md` §7.4).
The views are `machine_checked` or `verifier_agent` tier today. None is `human_spot_checked` yet.

## 3. How to run it

```bash
pip install -r requirements.txt                       # plus poppler-utils and tesseract-ocr for extraction
python3 qa/run_offline_suite.py                       # the CI suite: run before every push (about 10 min)
python3 apps/site/build_site_data.py                  # core/ -> site/data (5 s)
python3 -m http.server 8000 -d site                   # the site, locally
python3 curated/pipeline/build_warehouse_duckdb.py    # curated/warehouse.duckdb for SQL (analysts only)
```

**Workflows** (`.github/workflows/`):

| Workflow | What it does | Trigger |
|---|---|---|
| `validate.yml` | the offline suite | every PR and push to main |
| `site.yml` | builds and deploys the site | push to main touching core/meta/site; manual |
| `dosm-refresh.yml` | refreshes the 121 DOSM datasets and keeps every vintage | daily 14:17 MYT |
| `l0-archive.yml` | archives raw files to the release by sha256 | manual |
| `l0-pages.yml` | writes text of chosen archived pages to `qa/evidence/` | manual / request file |
| `lkan-extract.yml` | fetches LKAN PDFs from the archive and runs the contents-page and OCR extraction | manual; commits only with `Commit-Extraction: yes` |
| `states-extract.yml` | state statements extraction | manual |

**Working rules, in short:**
* Work on a branch and open a PR. Never push data straight to `main`.
* Keep figures as printed.
* For every new or changed source, a blind verifier agent re-derives a sample from the original.
* A CI failure is fixed or explained; never added to `qa/known_fails.csv` without a reason.

## 4. What is open, in priority order

### 4.1 Audit inventory (Phase 4): failed verification, fix then verify again
Every link and recurrence row is `publishable=false` / `draft` until a new blind verification passes. The full
findings are in `qa/audits/2026-11-06_lkan_inventory_verifier.md`. Fix them in this order, in
`sources/audit-negara/pipeline/lkan_inventory.py` (and `core/pipeline/build_records.py`):
1. Read the TW and bare-page contents layouts so that each body stays with its own entry.
2. Drop non-audit rows: the financial-statement chapters, digest and infographic entries, PENUTUP, the
   e-SelfAudit sub-sections and Tindakan Susulan.
3. Strip page footers from topics.
4. OCR the contents pages of the 9 LKAN 2021 Siri 2 state volumes (broken font encoding) and of the 2014–2016
   volumes (image only). `lkan-extract.yml` has tesseract.
5. Correct the year of the LKAN 1/2026 state volumes. Their manifest titles say 2022; their covers do not.
6. Classify topic families on the title alone, as `meta/audit_topic_taxonomy.csv` declares, and fix the
   'kumpanan wang' typo.
7. Add Kementerian Kewangan to `core/entity_name.csv`, and merge the higher-education ministry's three entity ids.
8. Re-run the blind verifier. Only then set `PUBLISHABLE` back in `build_records.py`.

The owner's 60 signatures in `meta/link_signoff.csv` are kept and apply again once the fixes are in. **7 links are
held unsigned.** In each, the entity had no name in the audit's year. A new owner of the warehouse should decide
them: sign them in that file, or leave them.

### 4.2 Step 4: social transfers, health survey, procurement (not started; leads found)
Leads are in `docs/leads/2026-11-06_step4_leads.csv`. Register each in `docs/registry/series_seed.csv` before
extraction. Never guess a licence.

* **NHMS 2019** (health survey, state tables with 95% intervals): `storage.data.gov.my/healthcare/nhms_2019.pdf`.
  The licence is ©IKU, so `to_confirm`.
* **MyProcurement** (MOF tender and quotation results, about 24,564 archived tender results and 131,146 quotation
  results): the endpoint is `/procurements/fetch`, plus the page's own `/generate-xls` export. Results can name
  sole proprietors and give addresses. **Personal data:** the companies must be kept and individuals dropped
  before anything leaves (golden rule 10).
* **Welfare (JKM) by state:** DOSM's *My Local Stats* "Perkhidmatan Kebajikan" tables. JKM's own datasets on
  archive.data.gov.my were down on 2026-11-06.
* These hosts were blocked from the build environment: iku.moh.gov.my, eperolehan, kpwkm, hasil, web.archive.org.
  Try them from a normal network.

### 4.3 Step 5: environment theme (not started)
Air quality, emissions, forest, water and disasters beyond what DOSM already gives. See `docs/SOURCES.md`, theme 9.

### 4.4 State budgets (Step 2, paused)
Only Selangor's 2022 estimates book and 15 budget speeches are held (`sources/state-budgets/`). Where the other
states' books were looked for is in `_locations_checked.csv`. Most are not online and need a request to each
state's treasury.

### 4.5 Smaller known issues
* **PKKP doubled glyphs.** Some PKKP project names extract with every letter doubled (e.g. "PPrroojjeekk JJaalluurr
  LLeebbaarr"). This is an extraction bug, not the source. Fix it in the PKKP extractor (collapse doubled
  characters only where the PDF draws them twice), and keep the name check in `build_gap_project_budget.py` green.
* **PKKP FY2015** is an image scan: its leaf amounts are OCR-provisional (`sources/pkkp/data/2015/_unresolved_ocr_cells_2015.csv`).
* **FY2025 audited accounts** (PKKP) are not loaded yet. Several views use MOF's FY2025 actuals until they are.
* **Baseline FAILs:** 22 known rows (`qa/known_fails.csv`), mostly Pahang and Perlis state statements that do not
  add up as printed. Each needs a proof page in `_source_anomalies*.csv`, or a fix.
* **Federal spending by place** is under 4% placeable, so federal amounts by state stay withheld. Raising it needs
  project locations, which the Development Estimates book (`sources/anggaran`) partly gives.
* **PKKP memorandum checks for FY2009–2013.** The validators in those year folders were copies of the 2014
  script (they re-checked 2014 five times) and were removed on 2026-11-06. Their `_validation_checks_memoranda_<year>.csv`
  files are kept as last written but are no longer re-run. Each year needs its own `validate_memoranda_<year>.py`.
* **Retire `curated/` in stages.** It is the older layer. The site no longer reads it, but CI still runs six of its
  builders, `qa/reproduce_curated.py` checks the core against it, and `core/pipeline` imports
  `curated/pipeline/mof_editions.py`. The order:
  1. Move `mof_editions.py` and `_known_extraction_defects_curated.csv` into `core/`.
  2. Drop `fact_budget_vs_actual` and `build_gap_views.py`, which `core/gap_budget_vs_actual.csv` supersedes.
  3. Retire the MOF breakdown tables once the owner confirms no one uses them.
  4. Keep `fact_obligations`, `fact_ministry_fiscal`, `fact_fiscal_headline` and `fact_labour_indicators` until
     the core has views that reproduce them to the ringgit.
  5. Move `build_warehouse_duckdb.py` (the SQL entry point for analysts) out of `curated/`.
* **PKKP per-year extraction scripts** (`sources/pkkp/pipeline/<year>/`) are a frozen record of how each volume
  was read. They hard-code the original work paths and need the PDFs; keep them as provenance, and do not delete them.

## 5. Decisions you will meet

Decisions are numbered D1–D35 in `docs/DATA_MODEL.md` §16 and in `meta/decision.csv`. The ones that come up most:

| Decision | Rule |
|---|---|
| **D10** | Nothing below state level is ranked or coloured. |
| **D23** | The L0 archive is on GitHub. |
| **D33** | An audit link is either `name_exact_official` or `human_signed`; nothing else publishes. |
| **D34** | `fact_observation` is sharded. |
| **D35** | Report figures enter only where the open data lack them or diverge from them. |
| **G1** | Publishing an official figure with its citation is not blocked by a licence still `to_confirm`. |

## 6. Where things are

| You want to | Look in |
|---|---|
| understand the model | `docs/DATA_MODEL.md` |
| avoid silent wrong numbers | `docs/ANALYST_GUIDE.md` |
| see what is held and what is needed | `docs/registry/series_seed.csv`, `docs/SOURCES.md` |
| check a source | `sources/<name>/README.md` and its `_validation*.csv`, `_source_anomalies*.csv` |
| see the verifier reports | `qa/audits/` |
| answer questions as an agent | `apps/tools/warehouse_tools.py` (typed tools, every number cited) |
| change the site | `site/README.md` |
