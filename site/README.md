# Fiskal Malaysia — site

Public front-end for the warehouse in `../curated/warehouse.duckdb`. Scoped to PKKP +
MOF Tinjauan Fiskal for v1, per `docs/SOURCES.md` and the brainstorm plan this was built
from. See the root `CLAUDE.md` for the data warehouse's own rules (never blend bases,
sum only leaf rows, join ministries on the canonical crosswalk).

## Layout

```
site/
  api/    FastAPI backend — constrained query templates + Tanya Fiskal chatbot
  web/    Next.js frontend — Papan Pemuka (dashboard, 3 sub-pages), Tanya Fiskal,
          Eksport Data, Metodologi
```

Papan Pemuka is 3 sub-pages, not one (`/papan-pemuka` redirects to the first):
- **`ringkasan`** — two-year comparative summary: fiscal-flow overview, revenue
  breakdown, OPEX-by-component (Jadual 3.1), DEVEX-by-sector (Jadual 3.3), financing.
- **`perkembangan`** — one named component's value over time (revenue/opex/devex/
  financing line items), full available range per component.
- **`kementerian`** — ministry+year drill-down: top programmes/activities and the
  5-bucket object-class split.

## Run locally

Build the warehouse first if you haven't (from the repo root):
```bash
python3 curated/pipeline/build_warehouse_duckdb.py
```

Backend:
```bash
cd site/api
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...       # required for /api/chat only
python3 -m uvicorn app.main:app --reload --port 8123
```

Frontend:
```bash
cd site/web
npm install
npm run dev
```
Open **http://localhost:3000** — not `127.0.0.1:3000`. Next.js 16 blocks cross-origin
dev resources by default; `next.config.ts` allow-lists both, but `localhost` is the
server's own advertised origin and the safer default while developing.

## What's real vs. stubbed

Implemented and verified end-to-end against real data: all pages (including the 3
Papan Pemuka sub-pages), all 13 query templates (`site/api/app/templates.py`), CSV
export, and the Tanya Fiskal tool-dispatch loop (verified with a mocked Claude response —
no usable `ANTHROPIC_API_KEY` was available in the environment this was built in, so the
live LLM call itself is untested here).

The OPEX-by-component (Jadual 3.1) and DEVEX-by-sector (Jadual 3.3) sections on
`ringkasan`/`perkembangan` are only as complete as the ingested Tinjauan Fiskal editions
— the statistical appendices of the 2019-2027 editions, each year from its own edition, covering FY2015-2027 (actuals to FY2025)
(`sources/mof-fiscal-outlook/README.md`). Any other year shows an explicit "belum
tersedia" state rather than a DOSM-proxied or otherwise degraded figure; ingesting more
editions (2022-2024 and pre-2017) widens this automatically once landed, no code change
needed beyond the ingestion itself.

Explicitly deferred (see the brainstorm plan's "Open items"): production deployment
config (Vercel/Fly.io/Railway), a shared-store rate limiter (`ratelimit.py` is an
in-memory placeholder — fine for one process, not for multiple replicas), the
independent-project disclaimer's final wording (a draft is already in the footer and
`/metodologi`), Excel export, and full leaf-level exports.
