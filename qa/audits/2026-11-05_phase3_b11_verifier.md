# Blind verifier pass: Phase 3.5 B.11 grant flows (2026-11-05)

A separate agent, blind to the flow builder and the warehouse code (it disclosed that a docstring grep printed
part of `get_flows`' body, which it did not use), re-derived every B.11 flow from PKKP's operating detail and
attacked `get_flows` (about 50 calls).

**Result: 94 of 94 B.11 flows re-derived exactly** (the 40000 line, period, recipient, L1 line, page, own
volume); B.11 programme 020000's leaf lines equal its printed total in all 14 years; the FY2017 services lines
are rightly left out; group membership correct for all 16 places; no crash. Recipients confirmed: the
Concurrent List grants are booked as revenue by the states (Kedah, Terengganu, Selangor: the federal 50% of
state departments' operating cost); the joint Sabah-Sarawak payments cannot be split from either state's books.

| # | Finding | Severity | Fixed by | Eval |
|---|---|---|---|---|
| 1 | The FY2024 Federal Territory grants moved to B.06 programme 080000 (Anggaran 2024 shows the move), not "not printed" | high | name rules for B.06 080000; 2 flows loaded | FT special grant 2024 |
| 2 | FY2018 Federal Territory grants not under B.11; B.32 040400 prints RM65,000,000.00 that year only, about their combined size, but its name does not say so | medium-high | not loaded (inference, not proof); F10/F11 and the coverage text say "not found under B.11 or B.06" and name the candidate | — |
| 3 | Payments by name to Perbadanan Putrajaya, Perbadanan Labuan, DBKL (B.32, later B.06) and B.43's local-government lines neither loaded nor declared | medium | declared in F11 and `coverage`; next slice (they need those bodies as entities) | — |
| 4 | The territories inherited the T.12 local-authority grant through group membership, without evidence | medium-low | the territories are not members of E000061; their answer says why | Putrajaya excludes it |
| 5 | Group queries had no answer text; Sabah/Sarawak's note omitted the joint grants | low | group answers say no amount is one body's money; note reworded | group answer |
| 6 | Selangor FY2014 (CMD.61.2015 p33) splits the Concurrent List label over two rows; the second carries the table total 1,676.81 flagged as a leaf component | low, outside this slice | follow-up: states parser or `KNOWN_EXTRACTION_DEFECTS` with page proof, before any state-side reconciliation | — |
