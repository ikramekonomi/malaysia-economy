# Document registry

**Status: agreed design, revision 2 (2026-11-04).** Seed rows: `docs/registry/series_seed.csv`.

The registry is the index of **every document the warehouse needs**: the ones we hold, and
also the ones we do not have yet, cannot get, or that are not published. It answers three
questions for a person or an AI agent:

1. Does the warehouse know about this document?
2. Do we hold it, and how far has it been processed?
3. If not, why not, and is there another way to get it?

A gap in the data is only useful to IKRAM if it is a *known* gap. The registry makes it known.

---

## 1. Structure

```
publisher ──< series ──< edition ──< file ──< extract
  MOF        Tinjauan    2027 ed.    st_kewangan.pdf   Jadual 1.1 → sources/mof-fiscal-outlook/data/2027_…
             Fiskal      (period × geo)  (url, sha256,     (used_by: fact_observation)
                                          pages, retrieved)
```

| Level | Key fields |
|---|---|
| `publisher` | `publisher_id`, name_bm, name_en, type (`ministry`, `agency`, `statutory_body`, `state_gov`, `parliament`, `company`) |
| `series` | `series_id`, publisher, title_bm/en, theme(s), frequency, geo_depth, priority, money-trail track, route, access, alternate_routes, **licence, redistribution, contains_personal_data** |
| `edition` | `edition_id`, series, period covered, geo covered, release date, **status**, status_reason, status_evidence, expected_release |
| `file` | `file_id`, edition, url, sha256, pages, size, retrieved_date, text layer (`text` / `scan`), **archive_url** (the public archive copy, where the licence allows) |
| `extract` | `extract_id`, file, table/page range, L1 output file, verifier result, used_by |

`dim_source` in the data model (`docs/DATA_MODEL.md` §4.6) is this registry. Every fact row
points to an `edition_id` and `file_id`.

---

## 2. Status lifecycle

```
expected ──> located ──> held ──> extracted ──> verified
   │            │
   └──> not_published · restricted · unobtainable          (terminal, each with reason + evidence + date)
                                                  superseded (a newer edition replaces it; kept)
```

| Status | Meaning | Evidence required |
|---|---|---|
| `expected` | we believe it exists or should exist | why we believe it (cited mention, prior edition) |
| `located` | URL or physical location known, not downloaded | URL + date checked |
| `held` | file in L0 with sha256 | manifest row |
| `extracted` | L1 tables produced | extract rows + own-total reconciliation |
| `verified` | independent adversarial verifier passed | verifier report path |
| `not_published` | publisher does not release it | dated check (site, enquiry, parliamentary answer) |
| `restricted` | exists, access limited (paid, request-only, confidential) | access terms |
| `unobtainable` | tried every route and failed | each attempt, dated |
| `superseded` | replaced by a later edition; kept for vintages | the replacing edition |

Rules:

* A status changes only with dated evidence. "We think it isn't published" stays `expected`.
* `restricted` and `not_published` are findings in themselves. They are reported in
  `list_documents` and can be cited in advocacy ("this is not public").
* A series status is the weakest status among its required editions.
* **Lawful sources only.** A document is registered only if its owner published it, it was released
  under the law, or it came through an official data request. No leaked or OSA-classified documents.

**Governance fields** (docs/DATA_MODEL.md §12):

| Field | Values | Effect |
|---|---|---|
| `licence` | the licence as stated by the publisher, or `to_confirm` | recorded on every answer that uses the series |
| `redistribution` | `open` · `attribution` · `no_redistribution` · `to_confirm` | `no_redistribution` never leaves the warehouse; `to_confirm` may be published with full citation (G1, as decided 2026-11-04) |
| `contains_personal_data` | `no` · `public_figures` · `possible` · `yes` | `possible`/`yes` series pass through the personal-data rule before any output |

Only licences stated somewhere we can cite are filled in: DOSM (CC BY 4.0, per its catalogue
pages) and World Bank WDI (CC BY 4.0). Everything else is `to_confirm` until checked.

---

## 3. Seed: what the first rows say

104 series across all 9 themes (`docs/registry/series_seed.csv`). The plan behind them, theme by
theme, is `docs/SOURCES.md`. Each row also says how it is reached (`access`: `api`, `bulk_file`,
`pdf`, `web_table`, `paid`, `none`). Revision 2 added 28 series from the two reviews (household-coverage
check and plan review) and deferred 12 low-value global series (`priority = deferred`). Phase 0
registered two DOSM series already held but not yet listed: population (`dosm_population`) and
government finance statistics (`dosm_gfs`).

| Status | Series |
|---|---|
| verified / extracted | 18: PKKP, Anggaran (operating), Anggaran Hasil, Tinjauan Fiskal, BNM MSB, state statements, LKAN federal, AG sijil, HIES, LFS, productivity, CPI, national accounts, state GDP, industry and trade, amenities, DOSM population (national), DOSM government finance |
| held, not extracted | 1: LKAN state volumes (findings) |
| expected | 81 (34 of all 104 series are reachable by API), including every state budget document: whether each state publishes it is to be checked state by state |
| restricted | 4: SSM company register, PADU/eKasih, DOSM and KPM data requests |

**The P1 gaps** (priority 1 and not yet held):

| Series | Theme | Why it matters |
|---|---|---|
| Development estimates (project-level budget) | 5 | the missing half of budget-vs-actual per project (Track 0) |
| Population by state / district | 1 | every per-capita comparison depends on it |
| State budget estimates (*Buku Belanjawan*) | 5 | state budget vs state actual |
| Federal development allocation by state | 5 | the most direct source for placing money (Track A); existence to confirm |
| Procurement awards | 7 | project → contractor (Track B) |
| Salaries and wages survey | 2 | median wage by state |
| Health facts | 6 | doctors and beds per capita by state |
| Education statistics | 6 | school outcomes by district |
| Malaysia Plan targets (RMK-12 MTR, RMK-13) | cross | the spine of target vs outcome |
| DOSM survey report tables (HIS, HES, LFS annual) | 1, 3, 2 | strata, ethnicity, income source, spending by item and decile, labour detail: published, but not in the API |
| National Health and Morbidity Survey | 6 | health outcomes, not only facilities |
| Cash transfer and welfare recipients by state | 5 | places operating spending by area, so need vs money is not built on projects alone |

---

## 4. What exists today and gets unified

Phase 0 unifies them: `python3 meta/build_registry.py` reads every manifest below and writes one
row per file to **`meta/registry_file.csv`** (series, edition, file, URL, sha256, size, pages,
retrieved date, manifest), then checks the registry into `meta/_validation_registry.csv`:
vocabulary, unique ids, every held series has files, every file has a sha256 and every held series
a confirmed licence. A missing sha256 or an unconfirmed licence is `OPEN` (a Phase 0 criterion not
yet met), not `FAIL`. Code lists are `meta/code_list.csv`; decisions D1–D23 and G1–G7 are
`meta/decision.csv`. All of it loads into the warehouse as `meta.*`.

| Today | Rows | Becomes |
|---|---|---|
| `sources/audit-negara/data/lkan_reports_backfill.csv` | 402 volumes, sha256 | edition + file rows |
| `sources/audit-negara/data/lkan_reports.csv` | federal 2024–26 | edition + file rows |
| `sources/mof-fiscal-outlook/data/_editions_manifest.csv` | 17 files | edition + file rows |
| `sources/dosm/data/_vintage.json` + `_vintage_log.csv` | 110 datasets; 173 vintages logged (2026-11-04) | edition + file rows (one per vintage, with sha256) |
| `sources/states/data/<state>/state_reports_<state>.csv` | per state volume | edition + file rows |
| `sources/bnm/data/_vintage_log.csv` | 32 datasets (seeded 2026-11-04) | edition + file rows, with sha256 |
| PKKP, Anggaran, Anggaran Hasil | **no manifest**: file names from row provenance, no sha256 | sha256 when the L0 archive holds the PDFs |

---

## 5. Rules for adding a row

1. Never invent a URL. If the route is unknown, write `to locate`.
2. One series per publication, not per table. Tables go in `extract`.
3. Use the publisher's own title in Malay first (`title_bm`), English second.
4. Every series has a theme, a priority (P1–P3, or `deferred`) and a money-trail track (`0`, `A`, `B` or `-`).
5. Every series has a `licence`, `redistribution` and `contains_personal_data` value, `to_confirm` if unknown. Never guess a licence.
6. When a status changes, keep the old evidence. The history is part of the record.
