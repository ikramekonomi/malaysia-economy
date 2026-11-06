# The public site

A static site over the warehouse, with no server, no database and no build step for the code. Its pages:
- **About**: the pitch. Every fact on it is computed from the data on load.
- **Explore data**: 125 indicators by place, period and breakdown. Each indicator page has:
  - a one-sentence headline;
  - value / change / index views;
  - an every-state grid of small charts;
  - a state map with a play button;
  - tables you can sort and filter.
- **Policy gaps**: the nine L3 views. Each has a live headline, a rule-based reading, a chart, a drilldown, its rows and its caveats.
- **Bubbles**: any two state indicators, animated through the years, with trails.
- **States**, **Sources & caveats** and **Method & trust**.

```bash
python3 apps/site/build_site_data.py      # core/ -> site/data/*.json (about 33 MB, 5 s; not committed)
python3 -m http.server 8000 -d site       # then open http://localhost:8000
```

It deploys itself to GitHub Pages on every push to `main` that touches `core/`, `meta/` or `site/`
(`.github/workflows/site.yml`; one-time setup: Settings → Pages → Source: GitHub Actions).

| File | What it is |
|---|---|
| `index.html` | the shell: sidebar, top bar, ⌘K palette |
| `app.js` | the whole app: a hash router and one function per view (`viewAbout`, `viewExplore`, `viewIndicator`, `viewGap`, ...) |
| `style.css` | the design system: colour tokens for light and dark, components |
| `vendor/` | d3 7.9.0 and Observable Plot 0.6.16 (ISC licences), pinned and served locally |
| `assets/` | IKRAM's logo (`ikram-logo.png`) |
| `data/` | built by `apps/site/build_site_data.py`; never hand-edit |

## What it will not show (enforced in `build_site_data.py`)
- series whose registry row says `no_redistribution` (golden rule 10);
- the audit inventory and `gap_audit_recurrence` (failed blind verification, 2026-11-06);
- federal amounts by state where a gap view marks them unpublishable (they are blanked; the share placed stays).

## Chart rules (keep them when you change a chart)
- No smoothing, no interpolation. A missing year breaks the line (a step longer than 1.6× the series' usual cadence).
- A series break (`meta/series_break.csv`) is a dashed rule, and the line does not run across it.
- Each basis (estimate, actual, audited, target) and each publisher is its own line. Where two editions print the same
  period differently, the main line uses the period's own volume, else the latest vintage; the other is a hollow point.
- Amounts and counts start at zero. Rates, indices and growth are fitted to the data, and the chart says which.
- Tooltips give the value exactly as printed, with edition, table, page and file.
- States are banded against Malaysia (±1 pp for percentages, else ±5%, or overlapping intervals), never ranked.
  Nothing below state level is coloured or ranked (D10).

## Adding a gap view to the site
Add it to `GAPS` in `apps/site/build_site_data.py`, a question to `QUESTIONS` in `app.js`, and an entry in `G`
(`filters`, `rows`, `read`, `chart`, `table`). The `read` text must be derived by fixed rules from the rows: no
hand-written claims.
