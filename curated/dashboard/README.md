# Malaysia Federal Finances — dashboard

An interactive, self-contained dashboard built **from the warehouse**: audited federal
actuals FY2010–FY2024, reconciled to the government's own printed totals. It is the public,
explorable face of the curated layer.

## Reproducible build

```
python3 pipeline/build_duckdb.py                 # 1. (re)build the PKKP cache from the CSVs
python3 curated/dashboard/build_dashboard.py     # 2. warehouse -> data.json -> index.html
```

`build_dashboard.py` reads `sources/pkkp/pkkp.duckdb` (each year from its own audited volume)
plus `external_denominators.csv`, emits `data.json`, and injects it into `template.html` to
produce the self-contained **`index.html`** (no runtime network calls; safe to open, host, or
publish as an artifact). Re-run it whenever the warehouse changes and the dashboard stays in sync.

## Files

| file | role |
| --- | --- |
| `build_dashboard.py` | the pipeline (DuckDB + external CSV → `data.json` → `index.html`) |
| `template.html` | the UI (HTML/CSS/JS) with a `__DATA__` placeholder; **edit this**, not `index.html` |
| `external_denominators.csv` | GDP & population (DOSM) — **external, provisional** (see caveat) |
| `external_peers.csv` | regional debt/deficit benchmarks (IMF/national) — **external, indicative** |
| `data.json` | built payload (gitignored; embedded into `index.html`) |
| `index.html` | built, self-contained dashboard (the deliverable) |

## What it shows

Overview KPIs (RM / % of revenue / % of GDP, with per-household context) · revenue vs
expenditure · revenue mix & the petroleum swing · operating spend by object class and by
function · ministry winners & losers vs revenue growth · the development pipeline (approved vs
delivered) · fiscal rigidity with the 15%-of-revenue debt-service guardrail · budget vs actual
by vote · the pension timebomb with an interactive **reform simulator** (retirement age /
indexation / DC-switch) · debt vs the 60/65%-of-GDP ceiling · the refinancing wall & instrument
mix · contingent exposure (additive waterfall, with statutory guarantees shown separately as
non-additive) · the COVID-19 Fund · regional peer benchmarks (debt & deficit vs
Thailand/Indonesia/Philippines/Vietnam, indicative). Controls: fiscal-year slider (with play),
unit toggle, section nav, deep-linkable URL (`#y=2020&u=gdp`), light/dark, per-card data tables,
page-level source provenance, keyboard-accessible chart tooltips, and shareable stat cards.

**Embed mode:** append `#embed=<id>` to render one card chrome-free for an iframe —
ids: `revenue, debt, rigidity, gap, pension, covid, contingent, compare` (combine with
`y=`/`u=`, e.g. `#y=2022&u=gdp&embed=pension`).

## ⚠️ On the external denominators

GDP and population come from **DOSM** and are **external to the audited warehouse and
provisional** (`external_denominators.csv`). They are used only for ratios (% of GDP,
per-household) and are namespaced/flagged so they are never blended into the audited PKKP
tables — consistent with the golden rules. Replace them when the DOSM source is ingested
(`docs/SOURCES.md`). The pension projection and reform simulator are **illustrative** models,
labelled as such in the UI. Everything else traces to an audited PKKP source page.
