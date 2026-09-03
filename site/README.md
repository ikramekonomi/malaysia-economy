# Fiskal Malaysia — site

Public front-end for the warehouse in `../curated/warehouse.duckdb`. Scoped to PKKP +
MOF Tinjauan Fiskal for v1, per `docs/SOURCES.md` and the brainstorm plan this was built
from. See the root `CLAUDE.md` for the data warehouse's own rules (never blend bases,
sum only leaf rows, join ministries on the canonical crosswalk).

## Layout

```
site/
  api/    FastAPI backend — constrained query templates + Tanya Fiskal chatbot
  web/    Next.js frontend — Papan Pemuka (dashboard), Tanya Fiskal, Eksport Data, Metodologi
```

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

Implemented and verified end-to-end against real data: all 4 pages, the 6 query
templates (`site/api/app/templates.py`), CSV export, and the Tanya Fiskal tool-dispatch
loop (verified with a mocked Claude response — no usable `ANTHROPIC_API_KEY` was
available in the environment this was built in, so the live LLM call itself is untested
here).

Explicitly deferred (see the brainstorm plan's "Open items"): production deployment
config (Vercel/Fly.io/Railway), a shared-store rate limiter (`ratelimit.py` is an
in-memory placeholder — fine for one process, not for multiple replicas), the
independent-project disclaimer's final wording (a draft is already in the footer and
`/metodologi`), Excel export, and full leaf-level exports.
