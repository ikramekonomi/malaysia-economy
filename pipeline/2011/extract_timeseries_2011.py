#!/usr/bin/env python3
"""Extract Perangkaan Kewangan Kerajaan Persekutuan 2002-2011 (RM juta), pdf 320-322.

The 2011 volume prints ALL 10 year columns (2011..2002) on every page; the
three pages (pdf 320,321,322) are vertical continuations of one long panel.
Numeric tokens are mapped to year columns by X-COORDINATE against each page's
year header row. Sections come from label-only lines; wrap continuations are
appended to the previous item's label. printed = pdf - 18.

Adapted from the 2012 volume's extract_timeseries.py (X-coordinate mapping).
"""
import csv
import re
import pdfplumber

PDF = "/home/claude/pkkp/work/2011/2011.pdf"
SRC = "2011_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2011/fact_timeseries_2002_2011.csv"
STATEMENT = "Perangkaan Kewangan Kerajaan Persekutuan"
UNIT = "juta"  # matches warehouse2012 CSV exactly (see note in report)
PAGES = (320, 321, 322)
PRINTED_OFFSET = 18

NUMTOK = re.compile(r"^\(?[\d,]+(?:\.\d+)?\)?$|^[–—-]$")
JUNK = re.compile(
    r"^(PENYATA KEWANGAN|Perangkaan Kewangan|Lampiran|LAMPIRAN|\(dalam RM juta\)|"
    r"\( ?s ?ambungan ?[.…]*\)|Federal Government|Appendix|\(in RM million\)|"
    r"Nota|Teks \d|\d{1,3}$|\($)", re.IGNORECASE)


def parse_amount(tok):
    tok = tok.strip()
    if tok in {"–", "-", "—"}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    v = float(tok.strip("()").replace(",", ""))
    return -v if neg else v


def merge_split_numbers(ws):
    out = []
    for wd in ws:
        if out:
            prev = out[-1]
            gap_limit = 10.0 if prev["text"] == "(" else 4.0
            if (wd["x0"] - prev["x1"] < gap_limit and re.match(r"^[\d,().]+$", prev["text"])
                    and re.match(r"^[\d,().]+$", wd["text"])
                    and not prev["text"].endswith(")") and not wd["text"].startswith("(")):
                prev["text"] += wd["text"]
                prev["x1"] = wd["x1"]
                continue
        out.append(dict(wd))
    return out


def lines_of(page_obj):
    raw = [w for w in page_obj.extract_words(x_tolerance=1.5, y_tolerance=2)
           if w.get("upright", True) and w["x0"] >= 0 and w["x1"] <= page_obj.width + 5]
    cleaned = []
    for w in raw:
        t = w["text"]
        if t.strip("!") == "":
            continue
        if t.endswith("!"):
            w = dict(w)
            w["text"] = t.rstrip("!")
        cleaned.append(w)
    words = sorted(cleaned, key=lambda w: w["top"])
    rows_, cur, cur_top = [], [], None
    for wd in words:
        if cur and wd["top"] - cur_top > 2.5:
            rows_.append(cur)
            cur = []
        if not cur:
            cur_top = wd["top"]
        cur.append(wd)
    if cur:
        rows_.append(cur)
    return [(sorted(ws, key=lambda x: x["x0"])[0]["top"],
             merge_split_numbers(sorted(ws, key=lambda x: x["x0"]))) for ws in rows_]


def year_columns(lns):
    for top, ws in lns:
        texts = [w["text"] for w in ws]
        yrs = [t for t in texts if re.match(r"^20\d\d$", t)]
        if len(yrs) >= 4 and len(yrs) == len(texts):
            return {int(w["text"]): (w["x0"] + w["x1"]) / 2 for w in ws}
    return None


def is_junk_line(line):
    if JUNK.match(line):
        return True
    if ".indd" in line or "Apendices" in line or "Appendices" in line:
        return True
    if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", line):        # timestamp
        return True
    if re.match(r"^\(\s*\d\s*\)", line):                    # footnote "(1) - ..."
        return True
    return False


def items_from_page(lns, ycols):
    col_min_x = min(ycols.values()) - 55
    for top, ws in lns:
        texts = [w["text"] for w in ws]
        line = " ".join(texts).strip()
        if is_junk_line(line) or (len(texts) >= 4 and all(re.match(r"^20\d\d$", t) for t in texts)):
            continue
        if re.match(r"^\(?\s*(Nota|Tidak termasuk|Termasuk)", line):
            continue
        valws, labws = [], []
        for w in ws:
            xc = (w["x0"] + w["x1"]) / 2
            if NUMTOK.match(w["text"]) and xc > col_min_x and min(abs(c - xc) for c in ycols.values()) <= 40:
                valws.append(w)
            else:
                labws.append(w)
        label = " ".join(w["text"] for w in sorted(labws, key=lambda x: x["x0"])).strip()
        label = re.sub(r"\s*\(disambung[.…]*\)\s*$", "", label)
        label = re.sub(r"\s*\(\s*$", "", label)
        label = re.sub(r"\s+\d$", "", label)      # trailing footnote superscript (single digit)
        label = label.strip()
        x0 = min((w["x0"] for w in labws), default=0)
        if not valws:
            if label:
                yield top, "text", (label, x0)
            continue
        vals = {}
        for w in valws:
            xc = (w["x0"] + w["x1"]) / 2
            yr = min(ycols, key=lambda y: abs(ycols[y] - xc))
            vals[yr] = parse_amount(w["text"])
        yield top, "item", (label, vals, x0)


# ---- top-level umbrella headers that are NOT sections (2012 convention) ----
DROP_HEADERS = {
    "Penyata Kedudukan Kewangan",
    "Perubahan Dalam Kedudukan Kewangan",
    "Pinjaman",
    "Hutang Awam",
}
PEMB_SUBHDRS = ("Penerimaan", "Pembayaran", "Perbelanjaan Pembangunan")

batch = []
section = None
seen_kwd = 0  # count of 'Kumpulan Wang Disatukan' umbrella occurrences
with pdfplumber.open(PDF) as pdf:
    for pno in PAGES:
        pg = pdf.pages[pno - 1]
        lns = lines_of(pg)
        ycols = year_columns(lns)
        assert ycols, f"year header not found on {pno}"
        assert len(ycols) == 10, f"expected 10 year cols on {pno}, got {sorted(ycols)}"
        for top, kind, payload in items_from_page(lns, ycols):
            if kind == "text":
                lbl, x0 = payload
                lbl = re.sub(r"\s*-\s*\(Samb\.\)\s*$", "", lbl)
                lbl = re.sub(r"\s*–?\s*\(SAMB\.?\)\s*$", "", lbl, flags=re.IGNORECASE).strip()
                if not lbl:
                    continue
                if lbl == "Kumpulan Wang Pembangunan - (Samb.)":
                    section = "Kumpulan Wang Pembangunan"
                    continue
                if lbl == "Kumpulan Wang Pembangunan":
                    section = "Kumpulan Wang Pembangunan"
                    continue
                if lbl in DROP_HEADERS:
                    continue
                # wrap continuation appended to previous item's label
                if batch and batch[-1][5] == pno and top - batch[-1][3] < 16 and (
                        x0 > batch[-1][4] + 4 or lbl[0].islower() or lbl[0] == "("):
                    b = batch[-1]
                    batch[-1] = (b[0], (b[1] + " " + lbl).strip(), b[2], b[3], b[4], b[5])
                    continue
                if lbl == "Kumpulan Wang Disatukan":
                    seen_kwd += 1
                    if seen_kwd == 1:
                        section = "Kumpulan Wang Disatukan"   # totals block
                    # 2nd occurrence: umbrella dropped; next sub-header sets section
                    continue
                base = section.split(" / ")[0] if section else ""
                if lbl in PEMB_SUBHDRS and base.startswith("Kumpulan Wang"):
                    section = f"{base} / {lbl}"
                else:
                    section = lbl
                continue
            label, vals, x0 = payload
            if not label and batch:
                batch[-1][2].update(vals)
                continue
            batch.append((section, label, vals, top, x0, pno))

out_rows = []
for section, label, vals, top, _x0, pno in batch:
    for yr in sorted(vals, reverse=True):
        out_rows.append([section, label, yr, vals[yr], UNIT, SRC, pno, pno - PRINTED_OFFSET, STATEMENT])

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["section_bm", "line_item_bm", "year", "amount_rm_juta", "unit",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(out_rows)

items = []
for r in out_rows:
    if (r[0], r[1]) not in items:
        items.append((r[0], r[1]))
print(f"{OUT}: {len(out_rows)} rows, {len(items)} line items, "
      f"{len(set(r[0] for r in out_rows))} sections")
from collections import Counter
print("rows/year:", dict(sorted(Counter(r[2] for r in out_rows).items(), reverse=True)))
