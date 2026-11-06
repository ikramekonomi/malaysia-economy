# Malaysia Economy Data Warehouse

*Pangkalan Data Ekonomi Malaysia · an IKRAM initiative*

A consolidated, fully verifiable data warehouse of **the Malaysian economy**, national and state,
built for evidence-based policy advocacy. It brings official documents and statistics (audited
accounts, budgets, Auditor-General reports, DOSM and BNM data) into one place. Every number is
traceable to its page, checked, and carries its uncertainty and caveats.

It is built to find **gaps worth advocating on**: plan vs outcome, budget vs spending, need vs
money, federal vs state, reported vs audited. People query it, and so do AI agents through typed
tools. The public site (`site/`) is one application on top of it.

> **Every number must survive a hostile reader.** If a figure cannot be traced to its source page
> and its checks, it does not leave the warehouse.

### Start here

| You are | Go to |
|---|---|
| **a policy advocate or analyst** | the site: *About*, *Explore data*, *Policy gaps* (`site/`, published by `.github/workflows/site.yml`; run it locally with the two commands in [`site/README.md`](site/README.md)) |
| **taking over the warehouse** | [`HANDOVER.md`](HANDOVER.md): what is built, what is open, how to keep it running |
| **adding or fixing data** | [`CLAUDE.md`](CLAUDE.md) (the rules), then [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) |
| **querying it** | [`docs/ANALYST_GUIDE.md`](docs/ANALYST_GUIDE.md), then the *Quick start* below |

---

## What is inside

| Source | What it is | Coverage | Rows | Checks |
|---|---|---|---|---|
| **pkkp** | Federal Government Financial Statements, audited, to object and project level. **The hub for federal money** | FY2009–2024 | 141,951 | 7,329 |
| **anggaran** | Federal expenditure estimates as tabled (ministry, programme, activity, object, posts) | Budgets 2024–2026 | 29,202 | 12,037 |
| **anggaran-hasil** | Federal revenue estimates, including the effect of tax measures | Budgets 2025–2026 | 496 | 132 |
| **mof-fiscal-outlook** | *Tinjauan Fiskal*: projections, debt, guarantees, contingent liabilities | Editions 2018–2027 | 3,204 | 975 |
| **audit-negara** | Auditor-General's reports: findings, agency certifications, e-SelfAudit, the AG's fiscal tables | LKAN 2015–2026 (402-volume manifest) | 3,285 | 160 |
| **states** | All 13 states' audited financial statements, plus a conformed national panel | FY2014–2024 | 50,053 | 10,224 |
| **bnm** | Monthly Highlights & Statistics (fiscal, debt, monetary, banking, external) | 1996–2026 | 8,106 | 279 |
| **dosm** | 121 datasets (DOSM and data.gov.my): national accounts, population by state and district, HIES, LFS, CPI, trade, GFS; hospital beds, health staff, schools, teachers, deaths, life expectancy, water, crime. **Refreshed daily** | 1947–2026 | 957,708 | 1,473 |

**Totals:** about 1.19 million source rows and 32,609 validation checks. **49 catalogued source
anomalies:** places where a publisher's own figures do not add up, kept exactly as printed with
proof.

**What we hold and what we still need** is one checklist,
[`docs/registry/series_seed.csv`](docs/registry/series_seed.csv): 115 series, 46 held. Each has
its route, licence and priority. The plan, theme by theme, is [`docs/SOURCES.md`](docs/SOURCES.md).

### Nine themes
People & poverty · jobs & wages · prices & cost of living · output & industry · public money &
money trail · health, education & services · accountability · money, credit & financial
wellbeing · environment, climate & disasters.

---

## How it is built

```
L0  raw documents        PDFs and API files, archived by sha256 (private l0-archive release)
L1  sources/<name>/      every table exactly as printed, with source file, page and statement
L2  core/                one conformed model: geo, period, indicator, breakdown, entity, source
                         + fact_observation (exact decimals, printed value, uncertainty, citation)
L3  core/gap_*.csv       named gap views, e.g. gap_need_vs_money (state level)
L4  apps/                agent tools (apps/tools), models (apps/models), the site (site/)
```

The full specification is [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md), and the rules for working
in the repository are in [`CLAUDE.md`](CLAUDE.md). Before your first query, read
[`docs/ANALYST_GUIDE.md`](docs/ANALYST_GUIDE.md): it covers basis blending, leaf rows, sign
conventions and other traps that give a wrong number silently.

### Truth by reconciliation
No single source is "the truth". Each domain has a hub, and the other sources are reconciled
against it. Where independent institutions agree to the ringgit, that is evidence. Where they
diverge, the divergence is kept as published and measured.

| Domain | Hub | Reconciled against it |
|---|---|---|
| Real economy, people, prices | DOSM | BNM, research sources, IMF |
| Federal public money | PKKP (audited) | budgets, BNM fiscal series, AG tables, MOF outlook, DOSM GFS |
| States | each state's audited statements | state budgets, state LKAN, DOSM state finance |
| Agencies & GLCs | AG certifications, company accounts | e-SelfAudit censuses, findings |
| Monetary and financial | BNM | debt issuance, holdings |

---

## How we keep it true

No single safeguard is enough. Each layer below catches what the one before it cannot.

| Layer | What it checks | When | Can it block? |
|---|---|---|---|
| **1. The source's own arithmetic** | Every printed total against the sum of its printed parts. A publisher's misprint becomes a `SOURCE_ANOMALY` with proof, never a silent correction | at extraction | yes |
| **2. CI** (`qa/run_offline_suite.py`) | 53 scripts on every pull request. A PR is blocked if:<br>• a check script fails;<br>• a rebuild changes a committed file;<br>• a new `FAIL` row appears that isn't in `qa/known_fails.csv`;<br>• a stored value differs from its printed value;<br>• an agent tool gives a wrong answer to one of 70 eval questions, or falls for a trap (incomparable figures, small-area rankings, missing documents, instructions hidden in a document) | every PR, automatically | **yes, always** |
| **3. Independent verifier agent** | A separate agent, blind to the extraction code, re-derives figures from the original and tries to break the tools | every new or changed source, and a monthly random audit (the 3rd of each month; reports in `qa/audits/`) | findings become fixes and new eval questions |
| **4. Cross-source reconciliation** | The same concept from independent publishers (e.g. PKKP vs BNM vs MOF) | every build | divergences are published, not hidden |
| **5. Human spot-check** | A person checks a random sample against the archived page (`qa/spot_check/`) | before anything IKRAM publishes | **yes: no publication without it** |
| **6. Archive and vintages** | Every raw document is kept by sha256, every data release is logged, and nothing is overwritten | always | lets anyone re-check any figure later |

**Why both CI and a verifier agent?** They catch different errors.
- **CI** is deterministic and cheap. It never forgets a check, but it only checks what someone
  thought to write.
- **The verifier agent** finds what nobody wrote a check for. Its first pass on Phase 1
  re-derived all 720 cells of the need-vs-money view and found a deficit printed as a surplus,
  plus several ways the tools could be misused.
- **Every verifier finding becomes a permanent CI check**, so it can never come back. That is how
  the checks keep growing.

AI checking AI is still not enough for publication. That is why layer 5 is a person.

**Verification tier.** Every published view carries one: `machine_checked` → `verifier_agent` →
`human_spot_checked` → `externally_reviewed`. IKRAM publishes only from `human_spot_checked` or
above.

---

## Quick start

```bash
pip install -r requirements.txt
python3 pipeline/build_duckdb.py                     # sources/pkkp/pkkp.duckdb (PKKP only)
python3 curated/pipeline/build_warehouse_duckdb.py   # curated/warehouse.duckdb: every source + core + meta
duckdb curated/warehouse.duckdb
```

Each source has its own schema (`pkkp`, `anggaran`, `states`, `dosm`, ...), plus `core` and
`meta`. Sources are namespaced, never merged; comparison happens in `core`.

**For agents and apps**, use the typed tools instead of SQL. Every number they return carries its
citation, uncertainty and caveats, and all arithmetic goes through `derive`, which refuses
figures that cannot be compared:

```python
from apps.tools.warehouse_tools import Tools
t = Tools()
t.compare_geos("poverty.absolute.rate", "2022")     # states in bands, not ranks, with Malaysia's value
t.get_gap_view("gap_need_vs_money", year="2022")    # need vs state-government money, all 16 states and FTs
```

**Run the checks before you push:** `python3 qa/run_offline_suite.py`.

---

## Rules (abridged; the full list is in [`CLAUDE.md`](CLAUDE.md))

1. The source CSVs are the truth. Everything derived is rebuilt, never hand-edited.
2. Never silently correct a figure. A misprint is kept as printed, with proof.
3. Every row keeps its source file, page and statement.
4. Join on codes, never names. Sum only leaf rows. Take each year from its own volume.
5. Keep every vintage. Archive every raw document.
6. A survey estimate carries its uncertainty, or says it is unknown. Small areas are never ranked
   as if exact.
7. Licence and personal data are checked before anything leaves. Individuals are never returned.
8. Neutral by construction: methods are declared before results are seen, and every view covers
   all 13 states and the 3 Federal Territories.
9. Work on a branch and open a PR. CI must pass.

---

## Status

| Phase | What | State |
|---|---|---|
| 0 Foundation | registry as data, CI, archive, vintage logs, governance | **built** |
| 1 First slice | state-level need vs money, end to end, with agent tools and evals | **built**; awaiting a human spot-check before publication |
| 2 Broaden statistics | DOSM, BNM and MOF series, survey report tables, health, education and services, small areas | **built** (125 indicators, 223,090 observations) |
| 3 Money trail | entities, federal→state transfers, placing federal spending by state, development projects | **built**; federal spending by state withheld (under 4% placeable) |
| 4 Records and links | audit findings inventory, audit-to-ministry links, recurrence | **draft**: failed blind verification 2026-11-06; fix list in `HANDOVER.md` |
| 5 Complete | gap views, the site | 9 gap views built and blind-verified; new site 2026-11-06 |

**Known caveats:**
- PKKP FY2015 is an image-only scan, so its leaf amounts are OCR-provisional.
- DOSM small-area estimates carry no published sampling error.
- Federal spending cannot yet be placed by state: only about 1% can be today, so that column is
  withheld.

Each source's README lists its own caveats and anomaly register.
