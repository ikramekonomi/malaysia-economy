# LKAN Aktiviti volumes — structural map for finding-register extraction

Derived 2026-07-31 by a dedicated scoping pass over the five Aktiviti-bearing
volumes (text layers verified page-aligned: 0-based `\f`-split chunk i ==
pdf_page i+1). Used by `extract_lkan_findings.py`; kept as provenance for how
the parser's markers were chosen.

## Global text-layer hazards (all volumes)

1. Duplicated slightly-offset text layers — footers/headers print twice,
   sometimes character-interleaved (`22--11` for printed page "2-1";
   `M a s s R aMass Rapid…` interleavings).
2. InDesign slug lines (printer's marks): `^<jobname>.indd <N> <date> <time>$`
   — reliable per-chapter anchors in CMD.8.2024 / CMD.9.2024 / CMD.5.2025;
   strip from content, use for chapter attribution.
3. Stray editorial marks in the text layer (`VERSI KABINET`, `Terkini
   10.5.2024`, `SEMAKAN KAN_21.4.2025`, `\x03`) — filter.
4. Anonymised parties are source-intended (`Syarikat 1`, `Syarikat 465005-P`,
   `Premis A (premis Kerajaan)`) — keep verbatim.
5. No image-only body pages in any volume.

## Chapter architecture by volume

- **CMD.8.2024** (LKAN 2/2024 Aktiviti, 436 pp): 9 chapters, printed pages
  `N-M`, slug `Teks <N> Persekutuan.indd`. Skeleton per chapter:
  `1. LATAR BELAKANG → 2. OBJEKTIF → 3. SKOP → 4. METODOLOGI →
  5. PENEMUAN TERPERINCI AUDIT → 6. SYOR AUDIT` (no RUMUSAN section).
  Findings `5.x.` / `5.x.y.` / `a.` / `i.`; response marker
  `Maklum Balas <ENTITI> yang diterima pada <tarikh>` (capital B, 166×);
  closing two-line `Pendapat` / `Audit` boxes. Ringkasan part pdf 350–436.
- **CMD.9.2024** (LKAN 2/2024 Syarikat, 362 pp): margin-label layout with
  continuous paragraph numbering per audit (1..~91). Per-audit `FAKTA AUDIT`
  cover page (Skop / Kenapa Perlu Diaudit / Rumusan / Penemuan / Syor Audit)
  = best uniform per-audit record. Margin labels: LATAR BELAKANG, PENEMUAN
  AUDIT, PRESTASI AKTIVITI, TADBIR URUS KORPORAT, KEDUDUKAN KEWANGAN,
  RUMUSAN KESELURUHAN, SYOR AUDIT, `Pendapat Audit` (92×), `Maklum balas` +
  entity on next line (lowercase b, no date in margin form). Slugs absent pdf
  119–230 (chapters 3–5). Ringkasan pdf 295–362.
- **CMD.5.2025** (LKAN 2/2025 Aktiviti, 244 pp): 5 chapters + status; slug
  `WJD25-0234 teks <n>.indd`. Skeleton adds `6. RUMUSAN KESELURUHAN AUDIT`,
  `7. SYOR AUDIT`. Response marker lowercase: `Maklum balas <ENTITI> yang
  diterima pada <tarikh>` (55×). NO Pendapat boxes. Ringkasan pdf 199–242.
- **CMD.2.2026** (LKAN 1/2026 vol 2, 192 pp): continuous printed pagination,
  pdf = printed + 8. Chapters I.1 (R&D&C&I), I.2 (MyDigital ID / MIMOS),
  II.3 (e-SelfAudit census of 852 entities — register-style, not
  per-finding), III.4 (PHB), IV status. Both response variants present —
  master regex needed. Two-line Pendapat boxes in I.1/I.2. Infografik digest
  pdf 15–24.
- **CMD.14.2025** (LKAN 3/2025, 264 pp): pdf = printed + 5. Aktiviti chapters
  IV.1–VI (KAA chapters use short skeleton `1. LATAR BELAKANG → 2. PENEMUAN
  AUDIT → 3. RUMUSAN → 4. SYOR AUDIT`; findings `2.x.` / `2.x.y.`); response
  `Maklum balas <ENTITI> diterima pada <tarikh>` (no "yang"; capitalisation
  wobble `Diterima` exists). Bahagian II (pdf 30–81, JADUAL 1–33) is the
  federal-finance analysis — separate extraction target pairing with PKKP
  FY2024. Lampiran 2 (pdf 238–264) reprints the condensed Penyata Kewangan.

## Master response-marker regex

`Maklum\s+[Bb]alas\s+(?P<entity>[A-Za-z0-9 .,&()/-]+?)\s+(?:[Yy]ang\s+)?[Dd]iterima\s+pada\s+(?P<dates>.+)`
(entity may be compound "KPKT dan JBPM"; dates "X dan Y" / "X, Y dan Z";
whitespace runs inside the phrase are common.)

## RM amounts

Not a fielded value: harvest `RM[\d.,]+\s*(juta|bilion)?` from finding
paragraphs. Systematic in the KAA/2026 chapters, frequent elsewhere. The
Ringkasan/Infografik parts carry quantified per-chapter digests usable to
cross-check register totals.
