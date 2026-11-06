# sources/state-budgets — the 13 states' own budget documents

Each state government tables its budget in its state assembly as two documents:
* an estimates book (Anggaran Hasil dan Perbelanjaan / Buku Anggaran Belanjawan): revenue by head and spending
  by department and programme, beside the year before's actual and revised estimate;
* a budget speech (Ucapan Belanjawan).

The estimates book is the plan side of the states' own budget-versus-actual. The actual side is the states'
audited statements, held in `sources/states`.

## Held (2026-11-06)

`data/_documents_manifest.csv` gives each document's URL, landing page, sha256, pages and whether it has a text
layer (all 16 do). The PDFs are in `raw/`, which is gitignored; they go to the private L0 archive
(`meta/l0_candidates.csv`).

| state | estimates book | speeches |
|---|---|---|
| Selangor | **2022** (274 pp) | 2024; 2025 infographic |
| Johor | — | 2024, 2025, 2026 |
| Pulau Pinang | — | 2024, 2025, 2026, 2027 |
| Sabah | — | 2025, 2026 (Malay and English) |
| Negeri Sembilan | — | 2025 |
| Perlis | — | 2024 |

Nothing is extracted yet. The Selangor 2022 book comes first: its revenue heads against Selangor's audited
statements.

## Not reachable from here

`data/_locations_checked.csv` lists every document located but not downloaded, with the reason. In summary:
* **Hosts that reset every TLS handshake** from the warehouse's network, probably a geo or IP block:
  * pwn.selangor.gov.my: the Selangor books 2018-2022 and 2026;
  * jkpnm.melaka.gov.my: Melaka's 2025 estimates and the 2026 'Buku Bajet';
  * kewangan.perak.gov.my;
  * treasury.sarawak.gov.my and sfs.sarawak.gov.my;
  * www.terengganu.gov.my.
* **Hosts not allowed** in this environment's network policy: mmk.kedah.gov.my (Kedah's speeches and assembly
  Hansard) and sabah.gov.my (Sabah's speech archive).
* **Nothing published on the reachable sites:** Johor, Pulau Pinang, Sabah, Negeri Sembilan, Perlis, Kelantan
  and Pahang publish no estimates book there.

Routes left:
* a fetch from a Malaysian network;
* the Wayback Machine (not allowed here);
* a written request to each state treasury.

## Terms

No site states an open licence. Every site checked prints 'Hak Cipta Terpelihara' (all rights reserved).
Pulau Pinang JKN's copyright notice asks written permission before copying or redistribution. Licence is
`to_confirm` in the registry: the documents are held in the private archive and cited, never republished.
The Selangor 2024 speech's cover carries the embargo line '25 NOVEMBER 2022' although it is titled Belanjawan
2024; this is kept as printed.
