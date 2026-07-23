#!/usr/bin/env python3
"""Extract Perangkaan Kewangan Kerajaan Persekutuan 2010-2019 (RM juta), pdf 254-256.

2019 volume prints a TEN-year panel (2010-2019) on three standalone full-width
pages (no left/right spreads as in later volumes). Numeric tokens are mapped to
year columns by X-COORDINATE against each page's year header row. Sections come
from label-only lines; wrap continuations (lowercase/'(' start, or deeper
indent) are appended to the previous item's label. Footnote superscripts print
as isolated single digits and are dropped."""
import csv
import re
import pdfplumber

SRC = "2019_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2019/fact_timeseries_2010_2019.csv"
NUMTOK = re.compile(r"^\(?[\d,]+(?:\.\d+)?\)?$|^[–—-]$")
JUNK = re.compile(r"^(PENYATA KEWANGAN|PERANGKAAN KEWANGAN|Perangkaan Kewangan|\(dalam RM juta\)|\( ?s ?ambungan ?\)|\(s amb|\(dis a|LAMPIRAN|Teks \d|\d+\. (Teks|lampiran)|14/10/2021|\d{1,3}$)")


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
    raw = page_obj.extract_words(x_tolerance=1.5, y_tolerance=2)
    words = []
    for w in raw:
        if w["x0"] < 0 or w["x1"] > page_obj.width or not w.get("upright", True):
            continue    # off-page spread ghosts / rotated sidebar
        if w["text"].endswith("!"):
            w = dict(w, text=w["text"].rstrip("!"))
            if not w["text"]:
                continue
        words.append(w)
    words = sorted(words, key=lambda w: w["top"])
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
    for top, ws in lns:
        texts = [w["text"] for w in ws]
        yrs = [t for t in texts if re.match(r"^20\d\d$", t)]
        if len(yrs) >= 4 and len(yrs) == len(texts):
            return {int(w["text"]): (w["x0"] + w["x1"]) / 2 for w in ws}
    return None


def items_from_page(lns, ycols):
    col_min_x = min(ycols.values()) - 55
    for top, ws in lns:
        texts = [w["text"] for w in ws]
        line = " ".join(texts).strip()
        if JUNK.match(line) or (len(texts) >= 4 and all(re.match(r"^20\d\d$", t) for t in texts)):
            continue
        if re.match(r"^\(?\s*(Nota|Tidak termasuk|Termasuk)\b", line):
            continue
        if "PENYATA KEWANGAN KERAJAAN PERSEKUTUAN" in line:
            continue
        # repair double-printed (overlapping) glyph tokens
        fixed = []
        for w in ws:
            t = w["text"]
            if not NUMTOK.match(t) and re.match(r"^[\d,().]+$", t):
                c = re.sub(r"(.)\1", r"\1", t)
                if NUMTOK.match(c):
                    w = dict(w)
                    w["text"] = c
            fixed.append(w)
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
        # drop isolated footnote superscripts (single digit, no other label text)
        labws = [w for w in labws if not (re.fullmatch(r"\d", w["text"]) and len(labws) == 1)]
        label = " ".join(w["text"] for w in sorted(labws, key=lambda x: x["x0"])).strip()
        label = re.sub(r"\s*\(disambung[^)]*\)\s*$", "", label)
        label = re.sub(r"\s*[–-]\s*\(Samb\.?\)\s*$", "", label)
        label = re.sub(r"\s+\d$", "", label)
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
with pdfplumber.open("/home/claude/pkkp/work/2019/2019.pdf") as pdf:
    for pno in (254, 255, 256):
        lns = lines_of(pdf.pages[pno - 1])
        ycols = year_columns(lns)
        assert ycols, f"year header not found on {pno}"
        seq = list(items_from_page(lns, ycols))
        # pre-pass: an item whose label prints on its own line (a footnote
        # superscript separates label from values, e.g. 'Pemberian dan Kenaan
        # Bayaran Tetap 4' / 'Pinjaman Bersih Dalam Negeri 3') appears as an
        # empty-label ITEM next to a label-only TEXT line -- either just above
        # or just below. Attach the nearest such TEXT as the item's label.
        for i, (top, kind, payload) in enumerate(seq):
            if kind != "item" or payload[0]:
                continue
            cands = []
            if i > 0 and seq[i - 1][1] == "text" and 0 <= top - seq[i - 1][0] < 14:
                cands.append((top - seq[i - 1][0], i - 1))
            if i + 1 < len(seq) and seq[i + 1][1] == "text" and 0 <= seq[i + 1][0] - top < 8:
                cands.append((seq[i + 1][0] - top, i + 1))
            if not cands:
                continue
            _, j = min(cands)
            lbl, lx0 = seq[j][2]
            seq[i] = (top, "item", (lbl, payload[1], lx0))
            seq[j] = (seq[j][0], "consumed", None)
        seq = [s for s in seq if s[1] != "consumed"]
        batch = []  # (section, label, {year: val}, top, x0)
        for top, kind, payload in seq:
            if kind == "text":
                lbl, x0 = payload
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
        for section_, label, vals, top, _x0 in batch:
            for yr in sorted(vals, reverse=True):
                out_rows.append([section_, label, yr, vals[yr], "RM juta",
                                 SRC, pno, pno - 12,
                                 "Perangkaan Kewangan Kerajaan Persekutuan 2010-2019"])

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["section_bm", "line_item_bm", "year", "amount_rm_juta", "unit",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(out_rows)

items = []
for r in out_rows:
    if (r[0], r[1]) not in items:
        items.append((r[0], r[1]))
print(f"fact_timeseries_2010_2019.csv: {len(out_rows)} rows, {len(items)} line items")
from collections import Counter
yc = Counter(r[2] for r in out_rows)
print("rows per year:", dict(sorted(yc.items(), reverse=True)))
for r in out_rows:
    if r[1] == "Jumlah Hasil" and r[2] == 2019:
        print("Jumlah Hasil 2019 =", r[3])
    if r[1] == "Wang Tunai" and r[2] == 2019 and r[0] == "Wang Awam":
        print("Wang Tunai 2019 =", r[3])
