#!/usr/bin/env python3
"""Extract Perangkaan Kewangan Kerajaan Persekutuan 2009-2023 (RM juta), pdf 280-285.

Three two-page spreads. Left pages carry labels + years 2024..2019; right pages
carry 2018..2010 at the same vertical positions. Numeric tokens are mapped to year
columns by X-COORDINATE against the year header row (robust to blank cells).
Sections come from label-only lines; wrap continuations (lowercase/'(' start)
are appended to the previous item's label.
"""
import csv
import re
import pdfplumber

SRC = "2023_Penyata_Kewangan_Kerajaan_Persekutuan.pdf"
OUT = "/home/claude/pkkp/warehouse2023/fact_timeseries_2009_2023.csv"
NUMTOK = re.compile(r"^\(?[\d,]+(?:\.\d+)?\)?$|^[–—-]$")
JUNK = re.compile(r"^(PENYATA KEWANGAN|Perangkaan Kewangan|\(dalam RM juta\)|\( ?s ?ambungan ?\)|WJD25|LAMPIRAN|\d{1,3}$)")


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
            gap_limit = 10.0 if prev["text"] == "(" else 4.0  # lone '(' belongs to next number
            if (wd["x0"] - prev["x1"] < gap_limit and re.match(r"^[\d,().]+$", prev["text"])
                    and re.match(r"^[\d,().]+$", wd["text"])
                    and not prev["text"].endswith(")") and not wd["text"].startswith("(")):
                prev["text"] += wd["text"]
                prev["x1"] = wd["x1"]
                continue
        out.append(dict(wd))
    return out


def lines_of(page_obj):
    words = sorted(page_obj.extract_words(x_tolerance=1.5, y_tolerance=2,
                                          extra_attrs=["fontname"]), key=lambda w: w["top"])
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
    return [(sorted(ws, key=lambda x: x["x0"])[0]["top"], merge_split_numbers(sorted(ws, key=lambda x: x["x0"]))) for ws in rows_]


def year_columns(lns):
    """Find the year header row; return {year: x_center}."""
    for top, ws in lns:
        texts = [w["text"] for w in ws]
        yrs = [t for t in texts if re.match(r"^20\d\d$", t)]
        if len(yrs) >= 4 and len(yrs) == len(texts):
            return {int(w["text"]): (w["x0"] + w["x1"]) / 2 for w in ws}
    return None


def items_from_page(lns, ycols):
    """Yield (top, kind, payload). kind: 'item' -> (label, {year: value}),
    'section' -> label (bold), 'text' -> label (regular, i.e. wrap candidate).
    A numeric token counts as a VALUE only if it sits within 40pt of a year-column
    centre AND right of the label area — digits inside labels ('Baki pada 1 Januari')
    stay in the label."""
    col_min_x = min(ycols.values()) - 55
    for top, ws in lns:
        texts = [w["text"] for w in ws]
        line = " ".join(texts).strip()
        if JUNK.match(line) or (len(texts) >= 4 and all(re.match(r"^20\d\d$", t) for t in texts)):
            continue
        if re.match(r"^\(?\s*(Nota|Tidak termasuk|Termasuk)\b", line):
            continue  # footnote text under the table
        if "PENYATA KEWANGAN KERAJAAN PERSEKUTUAN" in line:
            continue
        # repair double-printed (overlapping) glyph tokens, e.g. '(55,,550000))' -> '(5,500)'
        fixed = []
        for w in ws:
            t = w["text"]
            if not NUMTOK.match(t) and re.match(r"^[\d,().]+$", t):
                c = re.sub(r"(.)\1", r"\1", t)
                if NUMTOK.match(c):
                    w = dict(w)
                    w["text"] = c
            fixed.append(w)
        # drop overprint duplicates: a token whose x-range overlaps the previous kept token
        # and whose text is contained in it (doubled-glyph printing), or a stray lone '('
        ws = []
        for i, w in enumerate(fixed):
            if (w["text"] == "(" and i + 1 < len(fixed)
                    and fixed[i + 1]["x0"] <= w["x0"] + 1.5
                    and fixed[i + 1]["text"].startswith("(")):
                continue
            if ws:
                prev = ws[-1]
                if (w["x0"] < prev["x1"] - 1.5
                        and (w["text"] in prev["text"] or prev["text"] in w["text"])):
                    # keep the longer (more complete) rendering
                    if len(w["text"]) > len(prev["text"]):
                        ws[-1] = w
                    continue
            ws.append(w)
        valws, labws = [], []
        for w in ws:
            xc = (w["x0"] + w["x1"]) / 2
            if NUMTOK.match(w["text"]) and xc > col_min_x and min(abs(c - xc) for c in ycols.values()) <= 40:
                valws.append(w)
            else:
                labws.append(w)
        label = " ".join(w["text"] for w in sorted(labws, key=lambda x: x["x0"])).strip()
        label = re.sub(r"\s*\(disambung…?\)\s*$", "", label)
        label = re.sub(r"\s+\d$", "", label)  # trailing footnote superscript
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


out_rows = []
section = None
with pdfplumber.open("/home/claude/pkkp/work/2023/2023.pdf") as pdf:
    for left_no in (274, 276, 278):
        lp, rp = pdf.pages[left_no - 1], pdf.pages[left_no]
        llns, rlns = lines_of(lp), lines_of(rp)
        lyc, ryc = year_columns(llns), year_columns(rlns)
        assert lyc and ryc, f"year header not found on {left_no}/{left_no+1}"
        # right page: numeric rows by y
        right_rows = [(top, payload[1]) for top, kind, payload in items_from_page(rlns, ryc) if kind == "item"]
        batch = []  # (section, label, {year: val}, top, x0)
        for top, kind, payload in items_from_page(llns, lyc):
            if kind == "text":
                lbl, x0 = payload
                # wrap = deeper-indented or lowercase-starting continuation right under an item
                if batch and top - batch[-1][3] < 16 and (x0 > batch[-1][4] + 4 or lbl[0].islower() or lbl[0] == "("):
                    b = batch[-1]
                    batch[-1] = (b[0], b[1] + " " + lbl, b[2], b[3], b[4])
                else:
                    base = section.split(" / ")[0] if section else ""
                    if lbl in ("Penerimaan", "Pembayaran", "Perbelanjaan Pembangunan") and base.startswith("Kumpulan Wang"):
                        section = f"{base} / {lbl}"
                    else:
                        section = lbl
                continue
            label, vals, x0 = payload
            if not label and batch:
                batch[-1][2].update(vals)
                continue
            # a fund sub-block header printed on the same baseline as an item row merges
            # into its label (e.g. 'Baki pada 1 Januari Penerimaan'); split it back out
            SUBHDRS = ("Penerimaan", "Pembayaran", "Perbelanjaan Pembangunan")
            KNOWN = ("Baki pada 1 Januari", "Jumlah Penerimaan", "Jumlah Pembayaran")
            for sh in SUBHDRS:
                if label.endswith(" " + sh) and label[: -len(sh) - 1].strip() in KNOWN:
                    label = label[: -len(sh) - 1].strip()
                    batch.append((section, label, vals, top, x0))
                    base = (section or "").split(" / ")[0]
                    section = f"{base} / {sh}" if base else sh
                    break
            else:
                batch.append((section, label, vals, top, x0))
            continue
        # attach right-page year values by y
        for section, label, vals, top, _x0 in batch:
            best, bestd = None, 4.0
            for rtop, rvals in right_rows:
                d = abs(rtop - top)
                if d < bestd:
                    best, bestd = rvals, d
            allvals = dict(vals)
            if best:
                allvals.update(best)
            for yr in sorted(allvals, reverse=True):
                src_page = left_no if yr >= 2018 else left_no + 1
                out_rows.append([section, label, yr, allvals[yr], "RM juta",
                                 SRC, src_page, src_page - 12,
                                 "Perangkaan Kewangan Kerajaan Persekutuan 2009-2023"])

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["section_bm", "line_item_bm", "year", "amount_rm_juta", "unit",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(out_rows)

items = []
for r in out_rows:
    if (r[0], r[1]) not in items:
        items.append((r[0], r[1]))
print(f"fact_timeseries_2009_2023.csv: {len(out_rows)} rows, {len(items)} line items")
from collections import Counter
yc = Counter(r[2] for r in out_rows)
print("rows per year:", dict(sorted(yc.items(), reverse=True)))
#控 control: 2024 headline values
ctrl = {("Hasil", "Jumlah Hasil", 2024): 324618, ("Wang Awam", "Wang Tunai", 2024): 28196}
for r in out_rows:
    if r[1] == "Jumlah Hasil" and r[2] == 2024:
        print("Jumlah Hasil 2024 =", r[3])
    if r[1] == "Wang Tunai" and r[2] == 2024 and r[0] == "Wang Awam":
        print("Wang Tunai 2024 =", r[3])
EOF = None
