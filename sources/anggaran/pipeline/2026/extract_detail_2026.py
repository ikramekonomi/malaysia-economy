#!/usr/bin/env python3
"""Extract the per-vote detail sections (program/aktiviti x objek-am + Bil.
Jawatan) of Anggaran Perbelanjaan Persekutuan 2026.

All parsing logic and the era-quirk catalogue live in ../detail_common.py
(shared by the 2024/2025/2026 books - same layout family, per-era differences
handled by config + documented in the module docstring).

Output: sources/anggaran/data/2026/fact_anggaran_detail_2026.csv
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import detail_common


def main():
    votes, problems = detail_common.extract_book(2026)
    dest, n = detail_common.write_csv(2026, votes)
    nb = sum(len(v["butiran"]) for v in votes)
    no = sum(len(b["objek"]) for v in votes for b in v["butiran"])
    print(f"wrote {dest}: {n} rows - {len(votes)} votes, {nb} butiran, {no} objek lines")
    for p in problems:
        print(f"  note pdf_page {p['pdf_page']} [{p['kind']}]: {p['line'][:100]}")


if __name__ == "__main__":
    main()
