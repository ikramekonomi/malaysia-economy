# Source: Laporan Ketua Audit Negara (Auditor-General's Report) — SCAFFOLD, acquisition blocked

Audit findings, wastage, non-compliance and project overruns, federal and state — the
Tier-2 source that most directly serves "find gaps in fiscal behaviour"
(docs/SOURCES.md). Published on **www.audit.gov.my** (LKAN series, per year, federal +
per-state volumes).

## Status: egress open, but the portal blocks non-browser clients (2026-07-31)

The environment's network policy now allows `audit.gov.my` and the host resolves and
answers — but its F5 WAF rejects every non-browser TLS fingerprint ("Request
Rejected", regardless of headers), and real-browser traffic cannot traverse this
environment's egress proxy (Chromium CONNECTs are reset; verified against
known-good hosts, and the proxy log shows no policy denial for this host — it is a
client-fingerprint block at the site, not a policy block).

## Ways in (either works)

1. **Supply the PDFs via the repo** (the proven pattern): download the LKAN volumes
   from audit.gov.my in a normal browser → commit them to any GitHub repo you own →
   attach it to a session. Ingestion then follows the standard discipline (extract →
   reconcile to the report's own tables → adversarial verifier).
2. Retry from an environment whose egress path carries browser traffic.

## Planned first extraction (when documents arrive)

The LKAN federal volume's summary tables: findings per ministry with amounts
(kelemahan/teguran), project-audit verdicts, and the follow-up status tables —
keyed to `maksud` where the report names votes, joining PKKP for the
"planned vs delivered vs audited-verdict" pairing in docs/SOURCES.md.
