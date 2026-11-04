# Document registry

**Status: DRAFT for review. Nothing built yet.** Seed rows: `docs/registry/series_seed.csv`.

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
| `series` | `series_id`, publisher, title_bm/en, theme(s), frequency, geo_depth, priority, money-trail track, route, alternate_routes |
| `edition` | `edition_id`, series, period covered, geo covered, release date, **status**, status_reason, status_evidence, expected_release |
| `file` | `file_id`, edition, url, sha256, pages, size, retrieved_date, text layer (`text` / `scan`) |
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

---

## 3. Seed: what the first rows say

60 series across all 8 themes (`docs/registry/series_seed.csv`). The plan behind them, theme by
theme, is `docs/SOURCES.md`. Each row also says how it is reached (`access`: `api`, `bulk_file`,
`pdf`, `web_table`, `paid`, `none`).

| Status | Series |
|---|---|
| verified / extracted | 16: PKKP, Anggaran (operating), Anggaran Hasil, Tinjauan Fiskal, BNM MSB, state statements, LKAN federal, AG sijil, HIES, LFS, productivity, CPI, national accounts, state GDP, industry and trade, amenities |
| held, not extracted | 1: LKAN state volumes (findings) |
| located | 7: state budget estimates, speeches, enacted budgets and year-end reports; DUN hansards and questions; MyOBI |
| expected | 33 |
| restricted | 2: SSM company register, PADU/eKasih |
| not_published | 1: state Supply Bills (no state published one for 2026, per MyOBI 2026) |

State document statuses cite IDEAS' MyOBI 2026 as their evidence.

**The P1 gaps** (priority 1 and not yet held):

| Series | Theme | Why it matters |
|---|---|---|
| Development estimates (project-level budget) | 5 | the missing half of budget-vs-actual per project (Track 0) |
| Population by state / district | 1 | every per-capita comparison depends on it |
| State budget estimates (*Buku Belanjawan*) | 5 | state budget vs state actual; 7 of 13 states publish (MyOBI 2026) |
| Federal development allocation by state | 5 | the most direct source for placing money (Track A); existence to confirm |
| Procurement awards | 7 | project → contractor (Track B) |
| Salaries and wages survey | 2 | median wage by state |
| Health facts | 6 | doctors and beds per capita by state |
| Education statistics | 6 | school outcomes by district |
| Malaysia Plan targets (RMK-12 MTR, RMK-13) | cross | the spine of target vs outcome |

---

## 4. What exists today and gets unified

| Today | Rows | Becomes |
|---|---|---|
| `sources/audit-negara/data/lkan_reports_backfill.csv` | 402 volumes, sha256 | edition + file rows |
| `sources/audit-negara/data/lkan_reports.csv` | federal 2024–26 | edition + file rows |
| `sources/mof-fiscal-outlook/data/_editions_manifest.csv` | 17 files | edition + file rows |
| `sources/dosm/data/_vintage.json` | per dataset | edition rows (one per vintage) |
| `sources/states/data/<state>/state_reports_<state>.csv` | per state volume | edition + file rows |
| PKKP, Anggaran, Anggaran Hasil, BNM | **no manifest** | to be written (Phase 0) |

---

## 5. Rules for adding a row

1. Never invent a URL. If the route is unknown, write `to locate`.
2. One series per publication, not per table. Tables go in `extract`.
3. Use the publisher's own title in Malay first (`title_bm`), English second.
4. Every series has a theme, a priority (P1–P3) and a money-trail track (`0`, `A`, `B` or `-`).
5. When a status changes, keep the old evidence. The history is part of the record.
