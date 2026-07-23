# Sources

Every figure traces to an audited source PDF: *Penyata Kewangan Kerajaan Persekutuan*
(Federal Government Financial Statements), FY2009–FY2024, published by Jabatan Akauntan
Negara Malaysia (JANM). Each warehouse row carries `source_file`, `pdf_page`,
`printed_page`, and `statement` so any number can be checked against the exact page.

The 16 source PDFs are not committed here (they are the government's published documents;
keep a local copy alongside the repo if you need to re-run extraction from scratch). The
per-year extraction scripts under `pipeline/<year>/` expect a volume PDF for that year.
