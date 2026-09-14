# CLAUDE.md — Fiskal Malaysia site

Operating manual for anyone (human or AI) working in `site/`. Read the root `CLAUDE.md`
first — this file only adds rules specific to the public front-end; it never overrides
the warehouse's golden rules (raw CSVs are truth, never silently correct a figure, join
on codes, sum only leaf rows).

## What this is

Public front-end for `../curated/warehouse.duckdb`. Scoped to **PKKP + MOF Tinjauan
Fiskal** for v1 (per `../docs/SOURCES.md`). Three surfaces plus a trust page:

```
site/
  api/    FastAPI backend — constrained query templates + Tanya Fiskal chatbot
  web/    Next.js frontend — Papan Pemuka (dashboard), Tanya Fiskal, Eksport Data, Metodologi
```

The full brainstorm/scope plan (product surface, data contracts, chatbot design, tech
stack) lives at the session's plan file and `site/README.md`; this file is the
day-to-day ruleset, not the rationale.

## Golden rules for this layer

1. **Never generate free-form SQL for Tanya Fiskal.** Every question the chatbot answers
   must map to one of `site/api/app/templates.py`'s functions. A new capability means a
   new template (parameterized, read-only, returns `{"rows": [...], "citations": [...]}`)
   — never a prompt tweak that lets the model write its own query.
2. **Gross vs net is national-level only.** `curated.fact_fiscal_headline` has both
   bases; `curated.fact_ministry_fiscal` is gross-only. Never expose a fake "net" figure
   for a ministry, and never let a UI toggle silently no-op when a ministry filter is
   active — disable it and say why.
3. **Ministry filters resolve through the canonical crosswalk**
   (`curated.dim_maksud_canonical`), never raw `maksud_code`. Otherwise a ministry's time
   series shows fake breaks across renumbering years (Education, Higher Education).
4. **Every number needs a citation.** Every chart and every chatbot answer carries its
   source page/table back to `SourceCitation` / the template's `citations` field. No
   figure without a traceable source — this is the whole reason the site exists instead
   of a generic dashboard.
5. **Known caveats stay visible in the UI, not just in docs.** FY2015 (OCR-provisional
   leaf tier), FY2019 (print-anomaly page gap), and FY2014/2019 Higher-Ed-folded-into-
   Education must surface inline (footnote/info icon) wherever the affected year appears,
   with a link to `/metodologi`.
6. **A template/endpoint that can't cover a requested year must say so explicitly**
   (an `not_available`/reason flag), never return an empty array or a silent
   approximation from a different, incompatible classification.
7. **The warehouse is read-only from here.** `site/api` opens `curated/warehouse.duckdb`
   read-only; rebuilding it is the root pipeline's job (`pipeline/build_duckdb.py`,
   `curated/pipeline/*.py`), never something the site does at request time.

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

See `site/README.md` for the current, maintained list — it's updated as pages/templates
land. As of the last update: all 4 pages, the query templates in
`site/api/app/templates.py`, CSV export, and the Tanya Fiskal tool-dispatch loop are
implemented; production deployment config, a shared-store rate limiter, final disclaimer
wording, Excel export, and full leaf-level export are explicitly deferred. Don't assume a
stubbed piece is production-ready just because it runs locally.
