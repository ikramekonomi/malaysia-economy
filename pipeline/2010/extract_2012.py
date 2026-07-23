#!/usr/bin/env python3
"""Extract Lampiran 1: Penyata Perbelanjaan Mengurus detail (PKKP 2012, pdf 68-207).

4-value-column layout: Anggaran Asal | Anggaran Dipinda | Sebenar Amaun |
Sebenar %Anggaran. Adapted from the 2014 extractor. pdfplumber word
coordinates; words clustered into visual rows by top; value tokens assigned to
the four columns by x-position (right edge) against per-page anchors built from
the page's own complete 4-token rows. 2012 particulars:
 - clean single-up pages; doubled-glyph overprints appear at x0>640 (beyond
   page width 642) and are dropped by the x1<=width+5 filter;
 - header words carry trailing '!' watermark glyphs;
 - grand total prints its VALUES row first with the wrapped label
   'JUMLAH KESELURUHAN MENGURUS' on the FOLLOWING line -> forward adoption;
 - printed = pdf - 22.
Schema columns: Dipinda stored in anggaran_jumlah_rm; anggaran_tambahan_rm /
viremen_rm / varian_rm left empty. No 2012 maksud reference file exists, so
maksud_name_bm is assembled from the printed header (+ wrapped continuation).
Hierarchy: Maksud (T.xx/B.xx) > Program (XX0000) > Aktiviti (XXYY00) > Object
(5-digit). Nothing silently corrected; group sums validated separately.
"""
import csv
import re
import statistics

import pdfplumber

SRC = "2012_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2012/fact_opex_detail.csv"
YEAR = 2012
PDF = "/home/claude/pkkp/work/2012/2012.pdf"
FIRST, LAST = 68, 207
PRINTED_OFFSET = 22

NUMRE = re.compile(r"^\*?\(?[\d,]+(?:\.\d+)?\)?$")
DASHRE = re.compile(r"^\*?[–—-]$")
OBJ_CLASSES = {
    "10000": "Emolumen", "20000": "Perkhidmatan dan Bekalan", "30000": "Aset",
    "40000": "Pemberian dan Kenaan Bayaran Tetap", "50000": "Perbelanjaan-perbelanjaan Lain",
}
OBJ_NAMES = set(OBJ_CLASSES.values())


def parse_amount(tok):
    tok = tok.strip().replace("*", "")
    if tok in {"–", "-", "—", ""}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()").replace(",", "")
    v = float(tok)
    return -v if neg else v


def merge_split_numbers(ws):
    out = []
    for wd in ws:
        if out:
            prev = out[-1]
            if (wd["x0"] - prev["x1"] < 4.0
                    and re.match(r"^[\d,().*]+$", prev["text"])
                    and re.match(r"^[\d,().]+$", wd["text"])):
                prev["text"] += wd["text"]
                prev["x1"] = wd["x1"]
                continue
        out.append(dict(wd))
    return out


def rows_of(pg):
    words = [w for w in pg.extract_words(x_tolerance=1.5, y_tolerance=2)
             if w.get("upright", True)
             and w["x0"] >= 0 and w["x1"] <= pg.width + 5
             and 0 <= w["top"] <= pg.height]
    cleaned = []
    for w in words:
        t = w["text"]
        if t.strip("!") == "":
            continue
        if t.endswith("!") and not re.search(r"[!]{2,}", t):
            w = dict(w)
            w["text"] = t.rstrip("!")
        cleaned.append(w)
    words = cleaned
    ded = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        dup = False
        for p in ded[-6:]:
            if (p["text"] == w["text"] and abs(p["x0"] - w["x0"]) < 1.5
                    and abs(p["top"] - w["top"]) < 1.5):
                dup = True
                break
        if not dup:
            ded.append(w)
    rows_, cur, cur_top = [], [], None
    for wd in sorted(ded, key=lambda w: w["top"]):
        if cur and wd["top"] - cur_top > 3.0:
            rows_.append(cur)
            cur = []
        if not cur:
            cur_top = wd["top"]
        cur.append(wd)
    if cur:
        rows_.append(cur)
    return [merge_split_numbers(sorted(ws, key=lambda x: x["x0"])) for ws in rows_]


def numlike(t):
    return bool(NUMRE.match(t) or DASHRE.match(t))


pdf = pdfplumber.open(PDF)

rows = []
maksud = maksud_name = jenis = None
program_code = program_name = None
akt_code = akt_name = None
akt_foot = False
last_header = None
notes = []
seen_jp = set()

for pno in range(FIRST, LAST + 1):
    pg = pdf.pages[pno - 1]
    prows = rows_of(pg)
    page_text = " ".join(w["text"] for ws in prows for w in ws)
    if "Perbelanjaan Mengurus" not in page_text:
        continue
    printed = pno - PRINTED_OFFSET
    # --- per-page column anchors from complete 4-value rows ---
    cand = []
    for ws in prows:
        vals = [w for w in ws if NUMRE.match(w["text"]) and w["x0"] > 250]
        if len(vals) == 4 and all(len(v["text"]) >= 4 for v in vals[:3]):
            cand.append([v["x1"] for v in vals])
    if len(cand) >= 3:
        anchors = [statistics.median(c[i] for c in cand) for i in range(4)]
        use_center = False
    else:
        hdr = {}
        for ws in prows:
            for w in ws:
                t = w["text"].rstrip("!")
                if t in ("Asal", "Dipinda", "Amaun", "%") and t not in hdr:
                    hdr[t] = (w["x0"] + w["x1"]) / 2
        if len(hdr) < 4:
            print(f"!! no column anchors derivable on pdf {pno}; page skipped")
            continue
        anchors = [hdr["Asal"], hdr["Dipinda"], hdr["Amaun"], hdr["%"]]
        use_center = True
    # --- build (label, toks, has_num) line records ---
    recs = []
    for ws in prows:
        labws, valtok = [], {}
        foot = False
        for w in ws:
            t = w["text"]
            if numlike(t):
                if "*" in t:
                    foot = True
                tt = t.replace("*", "")
                ref = (w["x0"] + w["x1"]) / 2 if use_center else w["x1"]
                di = [abs(anchors[i] - ref) for i in range(4)]
                ci = di.index(min(di))
                lim = (40 if use_center else 30) if NUMRE.match(tt) else 60
                if min(di) <= lim and ci not in valtok:
                    valtok[ci] = tt
                    continue
                if re.fullmatch(r"\d{1,3}", t) and (w["x1"] < 85 or w["x0"] > anchors[3] + 15):
                    continue
                labws.append(w)
            else:
                if re.fullmatch(r"\*+", t):
                    foot = True
                    continue
                labws.append(w)
        labws = [w for w in labws
                 if not (len(w["text"]) <= 2 and w["x0"] > anchors[3] + 1
                         and not numlike(w["text"]))]
        label = " ".join(w["text"] for w in labws).strip()
        recs.append(dict(label=label, valtok=valtok, foot=foot,
                         has_num=any(NUMRE.match(v) for v in valtok.values())))
    # --- re-attach lone dropped-baseline value rows to the previous data row ---
    merged = []
    for rec in recs:
        if (merged and not rec["label"] and rec["valtok"]
                and merged[-1]["valtok"]
                and all(ci not in merged[-1]["valtok"] for ci in rec["valtok"])):
            merged[-1]["valtok"].update(rec["valtok"])
            merged[-1]["has_num"] = merged[-1]["has_num"] or rec["has_num"]
            merged[-1]["foot"] = merged[-1]["foot"] or rec["foot"]
            continue
        merged.append(rec)
    # --- wrapped label rows: values-only row adopts nearest label-only line ---
    for i, rec in enumerate(merged):
        if rec["valtok"] and not rec["label"]:
            for back in range(i - 1, max(i - 4, -1), -1):
                cand_l = merged[back]
                if cand_l["valtok"]:
                    break
                if cand_l["label"] and not re.search(r"\d{4}", cand_l["label"]):
                    rec["label"] = cand_l["label"]
                    cand_l["label"] = ""
                    break
        if rec["valtok"] and not rec["label"]:
            for fwd in range(i + 1, min(i + 3, len(merged))):
                cand_l = merged[fwd]
                if cand_l["valtok"]:
                    break
                if cand_l["label"].startswith("JUMLAH"):
                    rec["label"] = cand_l["label"]
                    cand_l["label"] = ""
                    break
    # --- classify ---
    for rec in merged:
        s = rec["label"].strip()
        valtok = rec["valtok"]
        is_data = bool(valtok) and (rec["has_num"] or len(valtok) >= 2)
        if not is_data:
            if not s:
                continue
            if s.startswith(("Nota:", "Nota :", "(**)", "(*)")):
                continue
            if re.match(r"^(LAMPIRAN|Penyata Perbelanjaan|bagi tahun|\(sambungan|\(disambung|Maksud Perbelanjaan|Anggaran|Sebenar|PENYATA KEWANGAN|RM|%|Asal|Dipinda|Amaun|Prestasi|\$10|\d+\.\s*LAMPIRAN|6\. LAMPIRAN)", s):
                continue
            if re.match(r"^PERBELANJAAN TANGGUNGAN(\s|–|$|-)", s):
                jenis = "Tanggungan"
                last_header = None
                continue
            if re.match(r"^PERBELANJAAN BEKALAN(\s|–|$|-)", s):
                jenis = "Bekalan"
                last_header = None
                continue
            mh = re.match(r"^([TB])\.\s?(\d{2})\s+(.+?)(\s*[–—-]\s*\(SAMB\.\))?$", s)
            if mh:
                maksud = f"{mh.group(1)}.{mh.group(2)}"
                if not mh.group(4):
                    maksud_name = mh.group(3).strip()
                jenis = "Tanggungan" if mh.group(1) == "T" else "Bekalan"
                program_code = program_name = akt_code = akt_name = None
                last_header = "maksud"
                continue
            ph = re.match(r"^(\*?)\s?(\d{6})\s+(.+?)$", s)
            if ph:
                code, name = ph.group(2), ph.group(3).strip()
                name = re.sub(r"\s*\(dis\s?ambung[^)]*\)\s*$", "", name)
                name = re.sub(r"\s*[–—-]?\s*\(SAMB\.\)\s*$", "", name).strip()
                if code[2:] == "0000":
                    program_code, program_name = code, name
                    akt_code = akt_name = None
                    akt_foot = False
                    last_header = "program"
                else:
                    if program_code is None or code[:2] != program_code[:2]:
                        inferred = code[:2] + "0000"
                        notes.append(f"missing program header before aktiviti {code} "
                                     f"({maksud}, pdf {pno}): program {inferred} inferred from code prefix")
                        program_code, program_name = inferred, None
                    akt_code, akt_name = code, name
                    akt_foot = ph.group(1) == "*"
                    last_header = "aktiviti"
                continue
            m5h = re.match(r"^(\d{5})\s+(.+)$", s)
            if m5h and m5h.group(1) not in OBJ_CLASSES:
                code = "0" + m5h.group(1)
                akt_code, akt_name = code, m5h.group(2).strip()
                akt_foot = False
                last_header = "aktiviti"
                notes.append(f"aktiviti header printed with 5-digit code "
                             f"'{m5h.group(1)}' (pdf {pno}, {maksud}): read as {code}")
                continue
            if re.match(r"^\d{5}(\s|$)", s):
                continue
            if (last_header and len(s) < 70
                    and not re.search(r"[\d,]{5,}|\d{2}/\d{2}/\d{4}", s)
                    and "PENYATA KEWANGAN" not in s and "LAMPIRAN" not in s
                    and not s.startswith(("JUMLAH", "Jumlah", "PERBELANJAAN"))):
                frag = re.sub(r"\s*[–—-]?\s*\(SAMB\.\)\s*$", "", s).strip()
                if frag:
                    if last_header == "program" and program_name is not None:
                        program_name = (program_name + " " + frag).strip()
                    elif last_header == "aktiviti" and akt_name is not None:
                        akt_name = (akt_name + " " + frag).strip()
                    elif last_header == "maksud" and maksud_name is not None:
                        maksud_name = (maksud_name + " " + frag).strip()
                continue
            last_header = None
            continue
        # ------- data row -------
        if (re.search(r"\(disambung", s) or s.strip() in ("!", "pendahuluan.", "kira sebagai pendahuluan.", "sebagai pendahuluan.")
                or s.startswith(("Nota:", "Nota :", "telah dimasuk")) or "Program/Aktiviti -" in s
                or "Penyata Kewangan Kerajaan Persekutuan" in s):
            continue
        if re.fullmatch(r"|\d{1,3}", s) and all(re.fullmatch(str(YEAR) + r"|\d{1,3}", t) for t in valtok.values()):
            continue
        last_header = None
        label = s.lstrip("`'’ ").strip()
        foot = rec["foot"]
        if label.startswith("*"):
            foot = True
            label = label.lstrip("*").strip()
        toks = [valtok.get(i, "–") for i in range(4)]
        vals = [parse_amount(t) for t in toks]
        asal, dipinda, sebenar, pct_v = vals
        pct = None if toks[3] in ("–", "-", "—") else pct_v
        rt = None
        obj_code = obj_class = None
        lab = label
        m5 = re.match(r"^(\d{5})\s+(.+)$", label)
        m6h = re.match(r"^\*?\s?(\d{6})\s+(.+)$", label)
        if m5 and m5.group(1) in OBJ_CLASSES:
            rt, obj_code, obj_class = "object_aktiviti", m5.group(1), m5.group(2).strip()
        elif re.fullmatch(r"\d{5}", label) and label in OBJ_CLASSES:
            rt, obj_code, obj_class = "object_aktiviti", label, OBJ_CLASSES[label]
            notes.append(f"object row printed with code only, no class name: '{label}' "
                         f"(pdf {pno}, {maksud}); objek_class taken from the standard chart")
        elif m6h and not label.startswith("Jumlah"):
            code, name = m6h.group(1), m6h.group(2).strip()
            if code[2:] == "0000":
                program_code, program_name = code, name
            else:
                akt_code, akt_name = code, name
            continue
        elif re.match(r"^Jumlah\s+(\d{6})$", label):
            code = re.match(r"^Jumlah\s+(\d{6})$", label).group(1)
            rt = "jumlah_program" if code[2:] == "0000" else "jumlah_aktiviti"
            if rt == "jumlah_aktiviti" and code != akt_code:
                akt_code = code
            if rt == "jumlah_program":
                if code != program_code and (maksud, code) in seen_jp:
                    notes.append(f"duplicate 'Jumlah {code}' in {maksud} (pdf {pno}): "
                                 f"printed program-subtotal code differs from context program "
                                 f"{program_code}; kept printed label but attributed to {program_code} "
                                 f"(likely a mislabelled program subtotal in source)")
                else:
                    program_code = code
                    seen_jp.add((maksud, code))
            lab = f"Jumlah {code}"
        elif re.match(r"^Jumlah\s+(Emolumen|Perkhidmatan|Aset|Pemberian|Perbelanjaan)", label):
            rt = "jumlah_objek_maksud"
            obj_class = re.sub(r"^Jumlah\s+", "", label).replace("& ", "dan ")
        elif label in OBJ_NAMES or re.match(r"^(Emolumen|Perkhidmatan dan Bekalan|Aset|Pemberian (dan|&) Kenaan Bayaran Tetap|Perbelanjaan\s*-?\s*[Pp]erbelanjaan Lain)$", label):
            rt, obj_class = "object_program", label.replace("& ", "dan ")
        elif re.match(r"^JUMLAH PERBELANJAAN TANGGUNGAN", label):
            rt = "jumlah_jenis"
        elif re.match(r"^JUMLAH PERBELANJAAN BEKALAN", label):
            rt = "jumlah_jenis"
        elif re.match(r"^JUMLAH (PERBELANJAAN|KESELURUHAN) MENGURUS", label):
            rt = "jumlah_besar"
        elif re.match(r"^JUMLAH\s+\S", label):
            rt = "jumlah_maksud"
            lab = re.sub(r"^JUMLAH\s+", "", label).strip()
        else:
            rt = "unclassified"
        if rt in ("object_aktiviti", "jumlah_aktiviti") and akt_foot:
            foot = True
        rows.append([
            jenis, maksud, maksud_name,
            program_code, program_name, akt_code, akt_name,
            obj_code, obj_class, rt, lab, YEAR,
            asal, None, None, dipinda, sebenar, pct, None, foot,
            SRC, pno, printed, "Lampiran 1 Penyata Perbelanjaan Mengurus",
        ])

# back-fill program names for inferred program blocks
_pnames = {}
for r in rows:
    if r[3] and r[4]:
        _pnames.setdefault((r[1], r[3]), r[4])
for r in rows:
    if r[3] and not r[4] and (r[1], r[3]) in _pnames:
        r[4] = _pnames[(r[1], r[3])]

# fix A: page-break artifact — program-level class subtotals (object_program)
# printed at the TOP of a continuation page, BEFORE the 'Jumlah <program>' that
# names their program, carry no program_code. Forward-fill from that Jumlah.
for i, r in enumerate(rows):
    if r[9] == "object_program" and not r[3]:
        for j in range(i + 1, min(i + 9, len(rows))):
            if rows[j][9] == "jumlah_program" and rows[j][1] == r[1]:
                r[3], r[4] = rows[j][3], rows[j][4]
                notes.append(f"object_program class '{r[8]}' ({r[1]}, pdf {r[21]}) at page top "
                             f"attributed to program {r[3]} from following Jumlah")
                break
            if rows[j][9] in ("jumlah_objek_maksud", "jumlah_maksud", "object_aktiviti"):
                break

# fix B: source dropped the 'Jumlah' prefix on a maksud-level class subtotal, so
# it printed as a bare class name inside the maksud recap block -> reclassify the
# object_program to jumlah_objek_maksud (it sits between jumlah_objek_maksud rows
# and/or immediately before the JUMLAH <maksud> total, never before a Jumlah
# <program>).
for i, r in enumerate(rows):
    if r[9] == "object_program":
        prev = rows[i - 1] if i > 0 else None
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        prev_recap = prev is not None and prev[9] == "jumlah_objek_maksud" and prev[1] == r[1]
        next_maksud = nxt is not None and nxt[9] in ("jumlah_maksud", "jumlah_objek_maksud") and nxt[1] == r[1]
        if prev_recap or next_maksud:
            r[9] = "jumlah_objek_maksud"
            notes.append(f"maksud class subtotal '{r[8]}' ({r[1]}, pdf {r[21]}) printed without "
                         f"'Jumlah' prefix -> reclassified object_program to jumlah_objek_maksud")

# assemble canonical maksud names from first-seen header (fullest name)
CANON = {}
for r in rows:
    if r[1] and r[2] and r[1] not in CANON:
        CANON[r[1]] = r[2]
for r in rows:
    if r[1] in CANON:
        r[2] = CANON[r[1]]
    if r[9] == "jumlah_maksud" and r[1] in CANON:
        r[10] = CANON[r[1]]

IDX_RT = 9
for i, r in enumerate(rows):
    if r[IDX_RT] in ("jumlah_jenis", "jumlah_besar"):
        newrt = "jumlah_objek_jenis" if r[IDX_RT] == "jumlah_jenis" else "jumlah_objek_keseluruhan"
        j = i - 1
        while j >= 0 and rows[j][IDX_RT] == "jumlah_objek_maksud":
            rows[j][IDX_RT] = newrt
            j -= 1

for r in rows:
    rt = r[9]
    if rt in ("object_program", "jumlah_program"):
        r[5] = r[6] = None
    elif rt in ("jumlah_objek_maksud", "jumlah_maksud"):
        r[3] = r[4] = r[5] = r[6] = None
    elif rt in ("jumlah_objek_jenis", "jumlah_jenis", "jumlah_objek_keseluruhan", "jumlah_besar"):
        r[1] = r[2] = r[3] = r[4] = r[5] = r[6] = None

import os
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow([
        "jenis_bm", "maksud_code", "maksud_name_bm",
        "program_code", "program_name_bm", "aktiviti_code", "aktiviti_name_bm",
        "objek_code", "objek_class_bm", "row_type", "label_bm", "year",
        "anggaran_asal_rm", "anggaran_tambahan_rm", "viremen_rm", "anggaran_jumlah_rm",
        "sebenar_rm", "prestasi_pct", "varian_rm", "has_footnote",
        "source_file", "pdf_page", "printed_page", "statement",
    ])
    cw.writerows(rows)

from collections import Counter
c = Counter(r[9] for r in rows)
print(f"fact_opex_detail.csv: {len(rows)} rows")
for k, v in c.most_common():
    print(f"  {k}: {v}")
for n in notes:
    print("!!", n)
un = [r for r in rows if r[9] == "unclassified"]
print(f"unclassified: {len(un)}")
for r in un[:20]:
    print("   ?", str(r[10])[:70], "p", r[21])
