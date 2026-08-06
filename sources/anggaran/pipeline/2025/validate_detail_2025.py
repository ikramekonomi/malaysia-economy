#!/usr/bin/env python3
"""Validate fact_anggaran_detail_2025.csv (see ../detail_common.py):
V1 internal sums (butiran = its objek-am lines; program = its aktiviti; vote
JUMLAH = its programs), V2 anchor (vote total == the adversarially verified
fact_anggaran_maksud_2025.csv figure), V3 coverage, V4 Bil. Jawatan totals.

Output: sources/anggaran/data/2025/_validation_detail_2025.csv
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import detail_common

if __name__ == "__main__":
    detail_common.validate_book(2025)
