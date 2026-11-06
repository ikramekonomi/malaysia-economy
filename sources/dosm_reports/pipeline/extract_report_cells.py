#!/usr/bin/env python3
"""Extract DOSM survey-report tables (OpenDOSM publications' Excel files) as printed, one row per number.

  python3 sources/dosm_reports/pipeline/extract_report_cells.py -> sources/dosm_reports/data/<publication>/cells.csv
                                                                  + tables.csv (one row per table, its notes)
                                                                  + data/_extraction_coverage.csv (every numeric
                                                                    cell of every sheet: captured, or why not)
Labels printed as numbers are labels: an income class's bounds ('2,000 – 2,999') and a Tahun/Year column (the state
printed once for its 2022 and 2024 rows is carried down). Headings nest (Lelaki > Penengah (RM) > Bandar): a heading
replaces its own level and those opened after it; a measure's total row ('Penengah (RM)' with numbers) heads its
block. A text-only line is a continuation of the label above (or its English half, 'Total' under 'Jumlah') unless
it is a heading or a state. A header row inside a table ('D5 - D8' / years; a percentile row) heads the rows
below it. Sheet names are kept exactly, trailing spaces included.

Each report's workbook (raw/<publication>.xlsx; sha256 and link in data/_documents_manifest.csv) prints its
tables as a person reads them: several tables to a sheet, a Malay title row then an English one ('Jadual 2.3:' /
'Table 2.3:'), a header block of up to several rows (merged cells, two languages), row labels that can run over
two lines, and section rows (e.g. 'Bandar / Urban') that carry their own numbers. Nothing is reshaped here. For
every numeric cell the row keeps:
  table_no, title_bm, title_en       the table the cell is in (a sheet can hold several)
  sheet, cell                         where it is (A1 reference): the cell is the citation
  row_label                           the printed text of the row's label cells (a label continued on the next,
                                      number-less line is joined), section = the last row above it whose label
                                      cells carry no number in this column block
  col_header                          the printed header texts above it, top to bottom, each carried right across
                                      its merged span
  value_printed, value                as displayed (the cell's stored number formatted by its own number format,
                                      Excel rounding half away from zero: what the PDF twin prints), and the stored
                                      number in full (no rounding); a '-' or '..' is kept as printed, value empty
  number_format                       the cell's Excel number format, so value_printed can be re-derived
A table starts at a 'Jadual X:' row, or, in workbooks whose titles carry no 'Jadual' (the Salaries & Wages
report: 'A8 : Bilangan ...'), at a first-row 'X : ' title. Leading rows whose numbers are all whole years
(1900-2100) are header rows, not data.
Semantic mapping (which indicator, which breakdown) is done table by table in core, never here.
"""
import csv
import hashlib
from collections import Counter
import os
import re
import sys

import openpyxl
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
TITLE_BM = re.compile(r"^\s*Jadual\s+([A-Z]?\d+(?:\.\d+)*[A-Z]?)\s*:?", re.I)
TITLE_EN = re.compile(r"^\s*Table\s+([A-Z]?\d+(?:\.\d+)*[A-Z]?)\s*:?", re.I)
NOTE = re.compile(r"^\s*(\d+\s|\*|Nota|Note|Sumber|Source|Catatan|Bermula tahun|Data merujuk|Data refer)", re.I)
TITLE_BARE = re.compile(r"^\s*([A-Z]\d+(?:\.\d+)*)\s*:\s*\S")
FIELDS = ["publication", "sheet", "table_no", "title_bm", "title_en", "cell", "row", "col", "section", "row_label",
          "col_header", "value_printed", "value", "number_format", "source_file"]

TABLE_FIELDS = ["publication", "sheet", "table_no", "title_bm", "title_en", "first_row", "last_row", "n_cells", "notes",
                "source_file"]

COVERAGE_FIELDS = ["publication", "sheet", "numeric_cells", "captured", "in_header_rows", "in_note_rows",
                   "in_label_columns", "not_captured", "not_captured_cells"]


def txt(v):
    return "" if v is None else re.sub(r"\s+", " ", str(v)).strip()


def is_num(v):
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    return False


MARKS = ("-", "..", "–", "n.a.", "n.a", "na", "N/A", "NA", "N.A.")
STATE_LIKE = re.compile(r"^(Malaysia|MALAYSIA|Johor|Kedah|Kelantan|Melaka|Negeri Sembilan|Pahang|Pulau Pinang|Perak|"
                        r"Perlis|Selangor|Terengganu|Sabah|Sarawak|W\.?\s?P\.?\s|Wilayah Persekutuan)")
SECTIONS = [("sex", r"^(Jumlah|Total|Lelaki|Male|Perempuan|Female)\b"),
            ("measure", r"^(Bil\.? Penerima|Bilangan penerima|Number of recipients|Penengah|Median|Purata|Mean)\b"),
            ("group", r"^(Kumpulan etnik|Ethnic|Strata|Negeri|State|Daerah|District|Warganegara|Bukan Warganegara|"
                      r"Citizen|Non-citizen)\b")]


def sec_class(text):
    for k, pat in SECTIONS:
        if re.match(pat, text, re.I):
            return k
    return None


def set_level(levels, cls, text):
    """Sections nest: a new heading replaces its own level and every level opened after it."""
    for i, (c, _) in enumerate(levels):
        if c == cls:
            del levels[i:]
            break
    levels.append((cls, text))


TRANSLATION = {"jumlah": "total", "lelaki": "male", "perempuan": "female", "bandar": "urban", "luar bandar": "rural",
               "penengah": "median", "purata": "mean"}


def is_translation(label, text):
    """'Total' printed under 'Jumlah': the English half of a bilingual label, not a heading."""
    a, b = label.strip().lower(), text.strip().lower()
    return any(a.endswith(bm) and b.startswith(en) for bm, en in TRANSLATION.items())


def is_fraction_row(row):
    nums = [v for v in row if is_num(v)]
    return len(nums) >= 2 and all(0 < v <= 1 for v in nums) and nums == sorted(nums)


def is_year_row(row):
    nums = [v for v in row if is_num(v)]
    return len(nums) >= 1 and all(float(v).is_integer() and 1900 <= v <= 2100 for v in nums)


def display(v, fmt):
    """The number as Excel shows it under its number format (the common formats in these workbooks)."""
    from decimal import Decimal, ROUND_HALF_UP
    if fmt in (None, "", "General"):
        return format(v, ".10g") if isinstance(v, float) else str(v)
    sec = fmt.split(";")[0]
    sec = re.sub(r'"[^"]*"|\\.|_.|\*.|\[[^\]]*\]', "", sec)
    pct = "%" in sec
    m = re.search(r"\.([0#?]+)", sec)
    dp = len(m.group(1)) if m else 0
    x = Decimal(repr(v)) * (100 if pct else 1)
    q = x.quantize(Decimal(1).scaleb(-dp), rounding=ROUND_HALF_UP)
    out = f"{q:,.{dp}f}" if "," in sec else f"{q:.{dp}f}"
    return out + ("%" if pct else "")


def merged_value_map(ws):
    """(row, col) -> the merged range's top-left value, for header carry-across."""
    out = {}
    for rng in ws.merged_cells.ranges:
        v = ws.cell(rng.min_row, rng.min_col).value
        for r in range(rng.min_row, rng.max_row + 1):
            for c in range(rng.min_col, rng.max_col + 1):
                out[(r, c)] = v
    return out


def tables_in(grid):
    """Split a sheet into tables at each Malay title row; yields (start_row, end_row, no, title_bm, title_en)."""
    starts = []
    for r, row in enumerate(grid):
        for v in row[:4]:
            m = TITLE_BM.match(txt(v))
            if m:
                starts.append((r, m.group(1)))
                break
    if not starts:
        for r, row in enumerate(grid[:3]):
            m = TITLE_BARE.match(txt(row[0]) if row else "")
            if m:
                starts.append((r, m.group(1)))
                break
    if not starts:
        return [(0, len(grid), "", "", "")]
    out = []
    for i, (r, no) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(grid)
        bm = " ".join(txt(v) for v in grid[r] if txt(v))
        en = ""
        for rr in range(r + 1, min(r + 4, end)):
            line = " ".join(txt(v) for v in grid[rr] if txt(v))
            if TITLE_EN.match(line) or (TITLE_BARE.match(line) and TITLE_BARE.match(line).group(1) == no):
                en = line
                break
        out.append((r, end, no, bm, en))
    return out


def extract(path, publication):
    """(cells, tables): one row per numeric cell, and one per table with its notes as printed."""
    wb = openpyxl.load_workbook(path, data_only=True)
    out, tables, coverage = [], [], []
    for ws in wb.worksheets:
        role = {}  # row index -> 'header' / 'note' for the rows whose numbers are not data
        label_cells = set()  # (row, col) of numbers printed as labels: an income class's bounds, a year column
        mv = merged_value_map(ws)
        cells = [list(row) for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=ws.max_column)]
        raw = [[c.value for c in row] for row in cells]
        fmts = [[c.number_format for c in row] for row in cells]
        grid = [[mv.get((r + 1, c + 1), v) for c, v in enumerate(row)] for r, row in enumerate(raw)]
        for start, end, no, bm, en in tables_in(raw):
            body = range(start, end)
            numeric_rows = [r for r in body if any(is_num(v) for v in raw[r][1:]) and not TITLE_BM.match(txt(raw[r][0]) or txt(raw[r][1] if len(raw[r]) > 1 else ""))]
            if not numeric_rows:
                continue
            # a year printed in the header block is a number too: leading rows whose numbers are all whole years
            # are header rows; the data start at the first row after them whose numbers sit beside a text label
            lead = [r for r in numeric_rows]
            while lead and is_year_row(raw[lead[0]][1:]):
                lead.pop(0)
            first = lead[0] if lead else numeric_rows[0]
            for r in lead:
                lab = [txt(v) for v in raw[r] if txt(v) and not is_num(v)]
                if lab:
                    first = r
                    break
            ncol = max(len(x) for x in raw[start:end])
            hdr_rows = [r for r in range(start + 1, first)
                        if not any(p.match(" ".join(txt(v) for v in raw[r] if txt(v))) for p in (TITLE_EN, TITLE_BM, TITLE_BARE))]
            # label columns printed as numbers: an income class's bounds ('2,000 – 2,999') and a Tahun/Year column
            # (a range: whole-number bounds either side of a dash, the upper above the lower, in 3 rows or more, and
            # nothing but whole numbers in the lower bound's column; a nil '–' between two figures is not a range)
            label_num, seen = set(), Counter()
            for r in range(first, end):
                row = raw[r]
                for k in range(1, len(row) - 1):
                    lo, hi = row[k - 1], row[k + 1]
                    if txt(row[k]) in ("–", "-") and is_num(lo) and is_num(hi) and float(lo).is_integer() and \
                            float(hi).is_integer() and hi > lo:
                        seen[k] += 1
            for k, n in seen.items():
                lows = [raw[r][k - 1] for r in range(first, end) if k - 1 < len(raw[r]) and is_num(raw[r][k - 1])]
                if n >= 3 and all(float(v).is_integer() for v in lows):
                    label_num |= {k - 1, k + 1}
            year_cols = set()
            for c in range(ncol):
                head = " ".join(txt(grid[h][c]) for h in hdr_rows if c < len(grid[h]))
                vals = [raw[r][c] for r in range(first, end) if c < len(raw[r]) and is_num(raw[r][c])]
                if re.search(r"\b(Tahun|Year)\b", head) and vals and all(is_year_row([v]) for v in vals):
                    year_cols.add(c)
            label_num |= year_cols
            # the label columns: those left of the first numeric column in the data rows
            numcols = sorted({c for r in range(first, end) for c, v in enumerate(raw[r]) if is_num(v)} - label_num)
            first_num_col = numcols[0] if numcols else ncol
            for r in range(start, first):
                role[r] = "header"
            levels, notes, n0 = [], [], len(out)
            local_hdr, prev_data = None, True
            last_label, last_label_row, last_count, carried = "", -9, 0, ""
            for r in range(first, end):
                row = raw[r]
                parts = [display(v, fmts[r][c]) if is_num(v) else txt(v) for c, v in enumerate(row[:first_num_col])
                         if c not in year_cols and txt(v)]
                text = " ".join(parts)
                year = " ".join(str(row[c]) for c in sorted(year_cols) if c < len(row) and is_num(row[c]))
                nums = [(c, v) for c, v in enumerate(row) if c >= first_num_col and (is_num(v) or txt(v) in MARKS)]
                if notes or (not nums and NOTE.match(text)):
                    role[r] = "note"
                    # the notes under a table ('1 Data merujuk ...', 'Nota/Note:', 'Sumber/Source:') end its body
                    whole = " ".join(txt(v) for v in row if txt(v))
                    if whole:
                        notes.append(whole)
                    continue
                beyond = [txt(v) for c, v in enumerate(row) if c >= first_num_col and txt(v) and txt(v) not in MARKS]
                if not text and not year and (
                        (not nums and beyond) or
                        (nums and (is_year_row(row[first_num_col:]) or is_fraction_row(row[first_num_col:])))):
                    # a header row inside the table ('D5 - D8' / '1970* 1974* 1976 ...'; a percentile row):
                    # it heads the rows below it
                    if prev_data or local_hdr is None:
                        local_hdr, levels = [r], []  # a new block: its own header, its own sections
                    else:
                        local_hdr = local_hdr + [r]
                    prev_data = False
                    role[r] = "header"
                    continue
                if not nums:
                    if not text:
                        continue
                    cls = sec_class(text)
                    if last_label and r == last_label_row + 1 and (is_translation(last_label, text) or (
                            cls is None and not STATE_LIKE.match(text))):
                        # a label continued on its own line: join it to the row above's cells already written
                        for o in out[-last_count:] if last_count else []:
                            o["row_label"] = f"{o['row_label']} {text}".strip()
                        last_label_row = r
                    else:
                        set_level(levels, cls or "other", text)
                        last_label = ""
                    continue
                if year and not text:
                    text = carried  # the state printed once for its 2022 and 2024 rows
                elif text:
                    carried = text
                label = f"{text} {year}".strip()
                label_cells |= {(r, c) for c in label_num if c < len(row) and is_num(row[c])}
                section = " | ".join(t for _, t in levels)
                last_label, last_label_row, last_count = label, r, len(nums)
                prev_data = True
                for c, v in nums:
                    heads = []
                    for h in (local_hdr if local_hdr else hdr_rows):
                        t = txt(grid[h][c]) if c < len(grid[h]) else ""
                        if t and (not heads or heads[-1] != t):
                            heads.append(t)
                    out.append(dict(publication=publication, sheet=ws.title, table_no=no, title_bm=bm, title_en=en,
                                    cell=f"{get_column_letter(c + 1)}{r + 1}", row=r + 1, col=c + 1,
                                    section=section, row_label=label, col_header=" | ".join(heads),
                                    value_printed=txt(v) if not is_num(v) else display(v, fmts[r][c]),
                                    value="" if not is_num(v) else (repr(v) if isinstance(v, float) else str(v)),
                                    number_format=fmts[r][c],
                                    source_file=os.path.basename(path)))
                if sec_class(text) == "measure":
                    set_level(levels, "measure", text)  # a measure's total row heads its block ('Penengah (RM)')
            if len(out) > n0:
                tables.append(dict(publication=publication, sheet=ws.title, table_no=no, title_bm=bm,
                                   title_en=en, first_row=start + 1, last_row=end, n_cells=len(out) - n0,
                                   notes=" || ".join(notes), source_file=os.path.basename(path)))
        got = {(o["row"] - 1, o["col"] - 1) for o in out if o["sheet"] == ws.title}
        cnt = {"captured": 0, "header": 0, "note": 0, "label": 0, "other": 0}
        other = []
        for r, row in enumerate(raw):
            for c, v in enumerate(row):
                if not is_num(v):
                    continue
                k = "captured" if (r, c) in got else "label" if (r, c) in label_cells else role.get(r, "other")
                cnt[k] += 1
                if k == "other":
                    other.append(f"{get_column_letter(c + 1)}{r + 1}")
        coverage.append(dict(publication=publication, sheet=ws.title, numeric_cells=sum(cnt.values()),
                             captured=cnt["captured"], in_header_rows=cnt["header"], in_note_rows=cnt["note"],
                             in_label_columns=cnt["label"],
                             not_captured=cnt["other"], not_captured_cells=" ".join(other[:50])))
    return out, tables, coverage


def main():
    man = list(csv.DictReader(open(os.path.join(SRC, "data", "_documents_manifest.csv"))))
    only = set(sys.argv[1:])
    coverage = []
    for m in man:
        pub = m["publication"]
        if only and pub not in only:
            continue
        path = os.path.join(SRC, "raw", m["file_name"])
        h = hashlib.sha256(open(path, "rb").read()).hexdigest()
        if h != m["sha256"]:
            sys.exit(f"{m['file_name']}: sha256 {h} is not the manifest's {m['sha256']}")
        rows, tables, cov = extract(path, pub)
        coverage += cov
        d = os.path.join(SRC, "data", pub)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "cells.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        with open(os.path.join(d, "tables.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=TABLE_FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(tables)
        print(f"{pub}: {len(rows)} cells in {len({(r['sheet'], r['table_no']) for r in rows})} tables")
    if not only:
        with open(os.path.join(SRC, "data", "_extraction_coverage.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COVERAGE_FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(coverage)


if __name__ == "__main__":
    main()
