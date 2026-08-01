#!/usr/bin/env python3
"""Extract the Auditor-General's federal fiscal tables (LKAN 3/2025 Bahagian II).

CMD.14.2025.pdf, Analisis Kewangan Kerajaan Persekutuan: Bahagian II (pdf
30-67, JADUAL 1-33), II.a Pengurusan Hutang Persekutuan (pdf 68-73, JADUAL
1-4) and II.b Pengurusan Pelbagai ABT Hasil (pdf 74-81, JADUAL 1-11). One
long-format row per printed cell -> data/fact_lkan_fiscal_tables_2024.csv.
This is the third independent restatement of the federal accounts, for
triangulation against PKKP (audited) and BNM (reported).

Layout logic (pdftotext -layout, page-aligned cache raw/_text/CMD.14.2025.txt):
- a table runs from its centred `JADUAL n` line to the `Sumber:` citation;
  the CAPS title lines follow the JADUAL line, then a header block, then data.
- data lines are recognised by punctuated numeric segments (decimals, commas,
  parentheses-negatives, en-dash nil); value columns are clustered on the
  right-aligned end column of those segments; a leading `N.` column is BIL.
- row labels wrap above/below their value line and may be interrupted by the
  table grid: label-only lines attach to the nearest value line; lines ending
  with ':' or starting left of the modal label column are group headers
  (row_level 0); JUMLAH markers drive row_type (total when KESELURUHAN or a
  bare JUMLAH, else subtotal).
- column headers are assigned by x-overlap with the value clusters; segments
  spanning several clusters (TAHUN, PERUBAHAN, 2024 over RM BILION/%) become
  prefixes when a column's own heading is only a unit; `(RM JUTA)`-style
  fragments set `unit` and are kept out of col_label_bm.
Charts (CARTA) are skipped: parsing stops at Sumber:/next JADUAL/CARTA.
Values are kept exactly as printed (parentheses, en-dash nil, footnote `*`).
"""
import csv
import os
import re
from collections import Counter

from extract_lkan_findings import volume_pages, noisy

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

SOURCE_FILE = "CMD.14.2025.pdf"
REPORT = "LKAN 3/2025"
BAHAGIAN = [("II", 30, 67, 33), ("II.a", 68, 73, 4), ("II.b", 74, 81, 11)]

# Bahagian II running footers name the section, not the LKAN (which the
# shared NOISE list catches) — including their doubled/interleaved layers
SECTION_FOOTER = re.compile(
    r"^\s*(\d{1,3}\s+)?(Analisis\s*Kewangan|Pengurusan\s*(Hutang|Pelbagai))"
    r"[A-Za-z ]*(\d{1,3})?\s*$")
# repeated column-header fragments on continuation pages
HDRISH = re.compile(r"^(\(?RM( (JUTA|BILION|TRILION))?\)?|\(RM[^)]*\)|%|"
                    r"\d{4}|TAHUN|PERUBAHAN|PENINGKATAN|"
                    r"BIL\.?|BUTIRAN|AGENSI|KOMITMEN|JAMINAN)$")

VALUE = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?%?\*{0,2}\)?$|^[-–]$")
# gridless II.a JADUAL 3 (pdf 71) wraps two row labels symmetrically around
# label-less value lines — geometrically ambiguous for the generic fold; the
# printed readings below are confirmed against the page itself (same
# discipline as LAYOUT_REPAIRS in extract_agensi_sijil.py)
LABEL_REPAIRS = {
    ("II.a", 3): {
        "Jumlah Statutori Hutang Nisbah Statutori": "Jumlah Statutori Hutang",
        "Hutang Kepada KDNK (%)":
            "Nisbah Statutori Hutang Kepada KDNK (%)",
    },
}
PUNCT_VALUE = re.compile(r"[.,()]|^[-–]$")
UNIT = re.compile(r"^\(?RM(?:\s+(JUTA|BILION|TRILION))?\)?$", re.I)
BIL_SEG = re.compile(r"^\d{1,3}\.$")
YEAR = re.compile(r"^\d{4}$")


def segments(line):
    """[(text, start, end)] split on runs of 2+ spaces."""
    return [(m.group(0), m.start(), m.end())
            for m in re.finditer(r"\S(?:\S| (?! ))*", line)]


def is_value(text):
    return bool(VALUE.match(text))


def norm_unit(text):
    m = UNIT.match(text.strip("()"))
    if m:
        return "RM " + m.group(1).title() if m.group(1) else "RM"
    if text.strip("()") == "%":
        return "%"
    return None


def cluster_columns(data_lines):
    """Value columns: cluster the right-aligned ends of numeric cells, then
    merge overlapping clusters only when they never share a line — the
    centred %/nisbah cells of a money column overlap it but never co-occur
    with it, while tightly-packed neighbouring year columns always do.
    Nil dashes are centred, not right-aligned: they are placed by nearest
    column afterwards (col_of) instead of minting phantom columns here."""
    segs = [(k, s, e) for k, segs_ in enumerate(data_lines)
            for t, s, e in segs_ if is_value(t) and t not in "-–"]
    clusters = []                     # [ [min_s, max_e, set(lines)] ]
    for k, s, e in sorted(segs, key=lambda x: x[2]):
        if clusters and abs(e - clusters[-1][1]) <= 3:
            c = clusters[-1]
            c[0], c[1] = min(c[0], s), max(c[1], e)
            c[2].add(k)
        else:
            clusters.append([s, e, {k}])
    changed = True
    while changed:
        changed = False
        for i in range(len(clusters) - 1):
            a, b = clusters[i], clusters[i + 1]
            if min(a[1], b[1]) - max(a[0], b[0]) > 0 and not (a[2] & b[2]):
                clusters[i] = [min(a[0], b[0]), max(a[1], b[1]), a[2] | b[2]]
                del clusters[i + 1]
                clusters.sort()
                changed = True
                break
    clusters.sort()
    return [(c[0], c[1]) for c in clusters]


def col_of(seg, cols):
    t, s, e = seg
    best, bi = 0, None
    for i, (cs, ce) in enumerate(cols):
        ov = min(e, ce) - max(s, cs)
        if ov > best:
            best, bi = ov, i
    if bi is None and t in "-–" and cols:
        centre = (s + e) / 2
        bi = min(range(len(cols)),
                 key=lambda i: abs((cols[i][0] + cols[i][1]) / 2 - centre))
    return bi


def split_header_units(segs):
    """Break "(RM BILION) (RM BILION)"-style glued header runs apart."""
    out = []
    for t, s, e in segs:
        if t.count("(RM") >= 2:
            pos = s
            for part in re.finditer(r"\(RM[^)]*\)", t):
                out.append((part.group(0), s + part.start(), s + part.end()))
        else:
            out.append((t, s, e))
    return out


def parse_table(body, bahagian, jadual_no):
    """body: [(page, line)] between the JADUAL line and Sumber:. -> rows."""
    seglines = [(page, segments(ln)) for page, ln in body]
    if bahagian in ("II.a", "II.b"):
        # these sections use the margin-label narrative layout: the label
        # column (x ~22, wrapping to ~40) runs alongside the tables and must
        # not leak into titles or row labels
        seglines = [(page, [seg for seg in segs if seg[2] >= 45])
                    for page, segs in seglines]
    # title: leading single-segment CAPS lines with no value tokens (spanning
    # header words like TAHUN/PERUBAHAN end the title, they are column heads)
    HDR_WORD = re.compile(r"^(TAHUN|PERUBAHAN|PENINGKATAN.*|BERBANDING|"
                          r"TEMPOH MATANG)$")
    title, i = [], 0
    while i < len(seglines):
        page, segs = seglines[i]
        if len(segs) == 1 and not is_value(segs[0][0]) \
                and segs[0][0].upper() == segs[0][0] \
                and not HDR_WORD.match(segs[0][0]):
            title.append(segs[0][0])
            i += 1
        else:
            break
    body_segs = seglines[i:]

    data_idx = [k for k, (page, segs) in enumerate(body_segs)
                if any(is_value(t) and PUNCT_VALUE.search(t)
                       for t, s, e in segs)]
    if not data_idx:
        return " ".join(title), []
    # a table continuing onto the next page can shift horizontally: align
    # every page on the leftmost value-line segment of the table's first page
    page_left = {}
    for k in data_idx:
        page, segs = body_segs[k]
        left = min(s for t, s, e in segs)
        page_left[page] = min(page_left.get(page, 10 ** 9), left)
    base = page_left[body_segs[data_idx[0]][0]]
    if any(abs(v - base) > 2 for v in page_left.values()):
        shifted = []
        for page, segs in body_segs:
            d = page_left.get(page, base) - base
            shifted.append((page, [(t, s - d, e - d) for t, s, e in segs]))
        body_segs = shifted
    def cols_for(idx):
        cc = cluster_columns([body_segs[k][1] for k in idx])
        drop = set()                # leading `N.` running numbers are BIL
        for ci in range(len(cc)):
            vals = [t for k in idx for t, s, e in body_segs[k][1]
                    if is_value(t) and col_of((t, s, e), cc) == ci]
            if vals and all(BIL_SEG.match(v) for v in vals):
                drop.add(ci)
        return [c for ci, c in enumerate(cc) if ci not in drop]

    # a continuation page can change its column spacing (not only a uniform
    # shift): cluster each page separately, then map every page's columns
    # onto the reference page's by right-edge-aligned centres — the last
    # column (%) is always present, so aligning the right edges is stable
    by_page = {}
    for k in data_idx:
        by_page.setdefault(body_segs[k][0], []).append(k)
    page_cols_raw = {p: cols_for(idx) for p, idx in by_page.items()}
    first_page = body_segs[data_idx[0]][0]
    max_n = max(len(c) for c in page_cols_raw.values())
    ref_p = first_page if len(page_cols_raw[first_page]) == max_n else \
        min(p for p in page_cols_raw if len(page_cols_raw[p]) == max_n)
    cols = page_cols_raw[ref_p]
    page_map = {}
    for p, pc in page_cols_raw.items():
        shift = cols[-1][1] - pc[-1][1]
        idx_map = [min(range(len(cols)),
                       key=lambda i: abs((cols[i][0] + cols[i][1]) / 2
                                         - ((cs + ce) / 2 + shift)))
                   for cs, ce in pc]
        page_map[p] = (pc, idx_map)
    first_col_start = min(cs for cs, ce in cols)

    # gridless tables (II.a J3) centre every row independently: cells stop
    # aligning (far more right-edge chains than columns) or two cells of one
    # line collide on a cluster. Fall back to ordinal left-to-right
    # assignment against the widest line's cell count.
    ends = sorted(e for k in data_idx for t, s, e in body_segs[k][1]
                  if is_value(t) and t not in "-–" and not BIL_SEG.match(t))
    chains = sum(1 for i, e in enumerate(ends)
                 if i == 0 or e - ends[i - 1] > 3)
    ordinal = chains > len(cols) + 3
    for k in data_idx:
        page, segs = body_segs[k]
        pcols, idx_map = page_map[page]
        seen = set()
        for t, s, e in segs:
            if is_value(t) and t not in "-–":
                ci = col_of((t, s, e), pcols)
                if ci is not None:
                    if idx_map[ci] in seen:
                        ordinal = True
                    seen.add(idx_map[ci])
    if ordinal:
        n_ord = max(sum(1 for t, s, e in body_segs[k][1]
                        if is_value(t) and not BIL_SEG.match(t))
                    for k in data_idx)
        first_col_start = min(s for k in data_idx
                              for t, s, e in body_segs[k][1]
                              if is_value(t) and not BIL_SEG.match(t))

    # header block: lines before the first data line; trailing lines whose
    # single segment sits wholly left of the value columns are group rows
    hdr_end = data_idx[0]
    header_lines = []
    for k in range(hdr_end):
        page, segs = body_segs[k]
        segs = split_header_units(segs)
        whole_left = segs and all(e < first_col_start + 2 for _, _, e in segs)
        no_units = not any(norm_unit(t) for t, _, _ in segs)
        mixed = any(t.upper() != t for t, _, _ in segs)
        if len(segs) == 1 and whole_left and no_units:
            body_segs[k] = (page, segs)        # group header: leave for rows
        elif whole_left and no_units and mixed:
            body_segs[k] = (page, segs)        # "A. Syarikat" group before
        else:                                  # the first data row
            header_lines.append(segs)
            body_segs[k] = (page, [])          # consumed

    # column labels and units: each header line is partitioned at the
    # midpoints between its segments (a single spanning word like TAHUN or
    # PERUBAHAN covers the whole width); a column is labelled by every
    # non-unit segment whose partition covers its centre, top line first,
    # and takes its unit from covering (RM ...)/% fragments
    table_left_x = min(cs for cs, ce in cols) - 40
    table_right_x = max(ce for cs, ce in cols) + 4
    spans_by_line = []
    for segs in header_lines:
        # a header fragment wholly left of the value region belongs to the
        # label column's own heading (BUTIRAN / JENIS PRODUK ...): drop it
        segs = [x for x in segs if x[2] >= first_col_start - 2]
        spans = []
        for i, (t, s, e) in enumerate(segs):
            if len(segs) == 1:
                left, right = table_left_x, table_right_x
            else:
                left = s - 6 if i == 0 else (segs[i - 1][2] + s) // 2
                if i == len(segs) - 1:
                    # a trailing % head governs everything to its right
                    # (the narrow glyph sits left of its wide cells)
                    right = table_right_x if t.strip("()") == "%" else e + 6
                else:
                    right = (e + segs[i + 1][1]) // 2
            spans.append((t, left, right))
        spans_by_line.append(spans)
    col_meta = []
    for ci, (cs, ce) in enumerate(cols):
        centre = (cs + ce) / 2
        labels, unit, unit_text = [], None, ""
        for spans in spans_by_line:
            for t, left, right in spans:
                if left <= centre < right and norm_unit(t) is None:
                    labels.append(t)
        # units bottom-up: the unit line closest to the data governs (a
        # group-wide "(RM JUTA)" above must not shadow a per-column % head)
        for spans in reversed(spans_by_line):
            for t, left, right in spans:
                u = norm_unit(t)
                if u and left <= centre < right:
                    unit = unit or u
                    unit_text = unit_text or t.strip("()")
        # spanning single-word tiers (TAHUN over both years, PERUBAHAN over
        # its pair) are dropped once a more specific heading is present
        if len(labels) > 1:
            labels = [t for t in labels if t not in ("TAHUN", "BERBANDING")] \
                or labels
        if any(re.fullmatch(r"\d{4}", t) for t in labels):
            labels = [t for t in labels
                      if t not in ("PERUBAHAN", "PENINGKATAN")]
        if unit is None and any("%" in t for t in labels):
            unit = "%"
        label = squish(" ".join(labels)) or unit_text
        col_meta.append({"label": label, "unit": unit or ""})
    if ordinal:
        # ordinal fallback: labels from the widest header line and units from
        # the unit fragments, both in x-position order over the value region
        widest = max(header_lines, key=len, default=[])
        labs = [t for t, s, e in sorted(widest, key=lambda x: x[1])
                if not norm_unit(t) and e >= first_col_start - 2]
        units = [t for s, t in sorted((s, t) for segs in header_lines
                                      for t, s, e in segs if norm_unit(t))]
        col_meta = []
        for i in range(n_ord):
            lab = labs[i] if i < len(labs) else ""
            u = (norm_unit(units[i]) if i < len(units) else None) or \
                ("%" if "%" in lab else "")
            col_meta.append({"label": lab or (units[i].strip("()")
                                              if i < len(units) else
                                              "lajur %d" % (i + 1)),
                             "unit": u})

    # trust check: multi-row stacked/wrapped headers can compose garbled
    # labels even though the VALUES are positionally correct. A consumer must
    # never get a wrong label silently, so any garble sign downgrades the
    # whole table to explicit positional labels.
    seen_lu = Counter((m["label"], m["unit"]) for m in col_meta)
    UNIT_LABELS = {"RM JUTA", "RM BILION", "RM", "%", "PERATUS"}

    def garble_sign(m):
        toks = m["label"].split()
        if not toks:
            return True
        if m["label"] in UNIT_LABELS:          # unit-headed columns are fine
            return False
        if seen_lu[(m["label"], m["unit"])] > 1:
            return True                        # two columns compose the same
        if len(set(toks)) != len(toks):
            return True                        # doubled fragment ("ABT ABT")
        if len(toks) > 1 and any(re.fullmatch(r"\d{4}", t) for t in toks):
            return True                        # year glued to stray words
        if any(t in ("RM", "JUTA", "BILION", "TRILION") for t in toks):
            return True                        # unit remnant in a label
        if "JUMLAH" in toks[:-1]:
            return True                        # JUMLAH fused into a bucket
        return False

    if any(garble_sign(m) for m in col_meta):
        for i, m in enumerate(col_meta):
            m["label"] = "lajur %d (kepala tidak boleh dibina semula)" % (i + 1)
        print("  ! %s JADUAL %s: header not reconstructable, positional "
              "column labels" % (bahagian, jadual_no))

    # the containing narrative's own margin labels (II.a/II.b margin layout)
    # were already cut at x=45 above, so everything left in the body belongs
    # to the table itself
    table_left = 0

    # rows: value lines anchor; label-only lines attach or become groups
    anchors = []              # [{k, page, bil, label_segs, cells}]
    floats = []               # (k, text, start) label fragments
    label_starts = []
    for k, (page, segs) in enumerate(body_segs):
        if not segs:
            continue
        pcols, idx_map = page_map.get(page, (cols, list(range(len(cols)))))
        pfirst = first_col_start if ordinal else min(cs for cs, ce in pcols)
        vals = {}
        labels = []
        for t, s, e in segs:
            if s < table_left:
                continue                       # narrative margin label
            if ordinal:
                ci = len(vals) if is_value(t) and not BIL_SEG.match(t) \
                    else None
            else:
                ci = col_of((t, s, e), pcols) if is_value(t) else None
                ci = idx_map[ci] if ci is not None else None
            if ci is not None:
                vals[ci] = t
            elif is_value(t) and BIL_SEG.match(t):
                pass
            elif e < pfirst + 2 or not is_value(t):
                if not HDRISH.match(t):        # reprinted header fragments
                    labels.append((t, s))
        # bare-year-only lines are reprinted column headers, not data
        if vals and not all(YEAR.match(v) for v in vals.values()):
            inline = [(k, t, s) for t, s in labels if not BIL_SEG.match(t)]
            anchors.append({"k": k, "page": page, "cells": vals,
                            "labels": inline, "inline": bool(inline)})
            if labels:
                label_starts.append(min(s for t, s in labels
                                        if not BIL_SEG.match(t))
                                    if [1 for t, s in labels
                                        if not BIL_SEG.match(t)] else None)
        elif labels:
            keep = [(t, s) for t, s in labels if not BIL_SEG.match(t)]
            if keep:
                floats.append((k, " ".join(t for t, s in keep),
                               min(s for t, s in keep)))
    # the label column's modal x comes from inline labels AND wrapped
    # fragments — tables whose labels wrap around label-less value lines
    # (II.a J3) have almost no inline labels to calibrate on
    label_starts = [s for s in label_starts if s is not None] + \
        [s for _, _, s in floats]
    modal_start = Counter(label_starts).most_common(1)[0][0] \
        if label_starts else 0

    rows = []                 # ordered: {kind, k, ...}
    for a in anchors:
        rows.append({"kind": "data", **a})
    for k, text, s in floats:
        # centred subtotal labels start left of the label column but are
        # wrapped row labels, never group headers
        jumlah = bool(re.match(r"(?i)jumlah", text))
        if text.endswith(":") or (s < modal_start - 3 and not jumlah):
            rows.append({"kind": "group", "k": k, "label": text, "start": s})
        else:                                  # wrapped label fragment
            # a value line with no inline label of its own (label entirely
            # wrapped) attracts fragments across one extra line of distance —
            # "Nisbah Hutang / Persekutuan / <values> / Kepada KDNK" wraps
            # around the label-less line, not onto the labelled row above
            near = min(anchors,
                       key=lambda a: (abs(a["k"] - k)
                                      + (1 if a["inline"] else 0),
                                      1 if a["inline"] else 0),
                       default=None)
            if near is not None and abs(near["k"] - k) <= 3:
                near["labels"].append((k, text, s))
            else:
                rows.append({"kind": "group", "k": k, "label": text,
                             "start": s})
    rows.sort(key=lambda r: r["k"])

    # levels from label start positions (clustered to +-2)
    starts = sorted({r.get("start",
                           min((s for _, t, s in r.get("labels", [])),
                               default=modal_start))
                     for r in rows})
    lvl_of = {}
    for s in starts:
        for seen in lvl_of:
            if abs(seen - s) <= 2:
                lvl_of[s] = lvl_of[seen]
                break
        else:
            lvl_of[s] = len(set(lvl_of.values()))

    out = []
    for r in rows:
        if r["kind"] == "group":
            out.append({"row_label_bm": squish(r["label"]),
                        "row_level": lvl_of[r["start"]], "row_type": "line",
                        "cells": {}, "page": body[0][0] if not out else
                        out[-1]["page"]})
            continue
        frags = sorted(r["labels"], key=lambda f: f[0])
        label = squish(" ".join(t for _, t, s in frags))
        start = min((s for _, t, s in frags), default=modal_start)
        up = label.upper()
        if up.startswith("JUMLAH KESELURUHAN") or up == "JUMLAH":
            rtype = "total"
        elif up.startswith("JUMLAH"):
            rtype = "subtotal"
        else:
            rtype = "line"
        out.append({"row_label_bm": label, "row_level": lvl_of[start],
                    "row_type": rtype, "cells": r["cells"], "page": r["page"]})
    return " ".join(title), [(o, col_meta) for o in out]


def squish(text):
    return re.sub(r"\s+", " ", text).strip()


def main():
    pages = volume_pages(SOURCE_FILE)
    recs, table_log = [], []
    for bah, lo, hi, expect in BAHAGIAN:
        lines = []
        for p in range(lo, hi + 1):
            for ln in pages[p - 1].split("\n"):
                # keep Sumber: citations even when they cite the LKAN itself
                # (the running-footer noise pattern would otherwise eat them)
                if ln.strip() and (noisy(ln) or SECTION_FOOTER.match(ln)) \
                        and not ln.strip().startswith("Sumber:"):
                    continue
                lines.append((p, ln))
        k, seen = 0, []
        while k < len(lines):
            # the JADUAL head can share its line with a narrative margin
            # label (II.b J9), so it only needs to END the line
            m = re.match(r"^(?:\s*|.*\s)JADUAL\s+(\d+)\s*$", lines[k][1])
            if not m:
                k += 1
                continue
            jn = int(m.group(1))
            stop = None
            for j in range(k + 1, len(lines)):
                s = lines[j][1].strip()
                if s.startswith("Sumber:") \
                        or re.match(r"^(JADUAL|CARTA)\s+\d+$", s):
                    stop = j
                    break
            stop = stop if stop is not None else len(lines)
            if not lines[stop][1].strip().startswith("Sumber:"):
                print("  ! %s JADUAL %d has no Sumber: line, stopping at %s"
                      % (bah, jn, lines[stop][1].strip()[:30]))
            body = [(p, ln) for p, ln in lines[k + 1:stop] if ln.strip()]
            title, rows = parse_table(body, bah, jn)
            repairs = LABEL_REPAIRS.get((bah, jn), {})
            for o, _ in rows:
                o["row_label_bm"] = repairs.get(o["row_label_bm"],
                                                o["row_label_bm"])
            n = 0
            for o, col_meta in rows:
                if not o["cells"]:
                    recs.append({
                        "bahagian": bah, "jadual_no": jn,
                        "jadual_title_bm": title,
                        "row_label_bm": o["row_label_bm"],
                        "row_level": o["row_level"], "row_type": o["row_type"],
                        "col_label_bm": "", "value_verbatim": "", "unit": "",
                        "pdf_page": o["page"]})
                    continue
                ratio_row = o["row_label_bm"].lower().startswith(
                    ("nisbah", "peratus"))
                for ci in sorted(o["cells"]):
                    meta = col_meta[ci]
                    val = o["cells"][ci]
                    # ratio rows inside RM tables print percentages: their
                    # cells are %, whatever the column's money unit says
                    unit = "%" if ("%" in val or ratio_row) else meta["unit"]
                    recs.append({
                        "bahagian": bah, "jadual_no": jn,
                        "jadual_title_bm": title,
                        "row_label_bm": o["row_label_bm"],
                        "row_level": o["row_level"], "row_type": o["row_type"],
                        "col_label_bm": meta["label"],
                        "value_verbatim": val,
                        "unit": unit, "pdf_page": o["page"]})
                    n += 1
            seen.append(jn)
            table_log.append((bah, jn, title, n))
            k = stop
        missing = sorted(set(range(1, expect + 1)) - set(seen))
        print("%-5s %2d/%2d tables%s" % (bah, len(seen), expect,
                                         ", missing " + str(missing)
                                         if missing else ""))
    cols = ["report", "source_file", "bahagian", "jadual_no",
            "jadual_title_bm", "row_label_bm", "row_level", "row_type",
            "col_label_bm", "value_verbatim", "unit", "pdf_page"]
    dest = os.path.join(DATA, "fact_lkan_fiscal_tables_2024.csv")
    with open(dest, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in recs:
            r["report"] = REPORT
            r["source_file"] = SOURCE_FILE
        w.writerows([{c: r[c] for c in cols} for r in recs])
    print("%d cell rows -> %s" % (len(recs), dest))
    for bah, jn, title, n in table_log:
        print("  %-5s J%-2d %-58s %3d cells" % (bah, jn, title[:58], n))


if __name__ == "__main__":
    main()
