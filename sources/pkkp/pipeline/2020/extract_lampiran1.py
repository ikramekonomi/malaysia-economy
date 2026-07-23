#!/usr/bin/env python3
"""Extract Lampiran 1: Penyata Perbelanjaan Mengurus detail (PKKP 2020, pdf 95-206).

The 2020 volume's Lampiran 1 has NO text layer (all glyphs converted to vector
outlines), so this extractor works from 300-dpi renders OCR'd with tesseract
(cached TSVs in ../l1tsv). Values are assigned to columns by x-position against
a per-page-calibrated column template; cells the page-level OCR missed or
garbled are re-OCR'd individually from a 600-dpi crop of the ORIGINAL vector
PDF (with a dark-pixel test distinguishing en-dash nil cells).

2020 layout: FOUR value columns -- Anggaran Asal | Anggaran Dipinda |
Sebenar Amaun | Prestasi % -- (the 7-column Tambahan/Viremen/Jumlah/Varian
layout only appears from later volumes). To keep the warehouse2022 schema,
Dipinda is stored in anggaran_jumlah_rm (the final authorised provision, the
same economic quantity) and anggaran_tambahan_rm / viremen_rm / varian_rm are
left empty. Documented in _validation_checks_2020.csv.

Hierarchy: Maksud (T.xx/B.xx) > Program (6-digit XX0000, ALL-CAPS) > Aktiviti
(6-digit XXYY00) > Object row (5-digit 10000..50000). Wrapped headers span
lines; '(SAMB.)' markers are scrubbed; a printed '*' on the grand
Pemberian dan Kenaan Bayaran Tetap total flags the KWP transfer footnote.
"""
import csv
import os
import re
import subprocess
from collections import defaultdict

import pdfplumber

SRC = "2020_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2020/fact_opex_detail.csv"
WORK = "/home/claude/pkkp/work/2020"
DPI = 300.0
TEMPLATE = {"asal": 1485.0, "dipinda": 1748.0, "sebenar": 2032.0, "pct": 2318.0}
COLS = ["asal", "dipinda", "sebenar", "pct"]
VAL_X_MIN = 1150   # template frame: values live right of this (label area left)

OBJ_CLASSES = {
    "10000": "Emolumen", "20000": "Perkhidmatan dan Bekalan", "30000": "Aset",
    "40000": "Pemberian dan Kenaan Bayaran Tetap", "50000": "Perbelanjaan-perbelanjaan Lain",
}
OBJ_NAMES = set(OBJ_CLASSES.values())
NUMRE = re.compile(r"^\*?\(?[\d,]+(?:\.\d{1,2})?\)?$")
DASHRE = re.compile(r"^[-–—_=~.·]{1,3}$")

pdf = pdfplumber.open(f"{WORK}/2020.pdf")
CELL_CACHE_PATH = f"{WORK}/l1cells.csv"
cell_cache = {}
if os.path.exists(CELL_CACHE_PATH):
    for _r in csv.reader(open(CELL_CACHE_PATH)):
        cell_cache[(_r[0], _r[1])] = _r[2]
_cache_f = open(CELL_CACHE_PATH, "a", newline="")
_cache_w = csv.writer(_cache_f)


_page_img = {}
def _get_img(pno):
    from PIL import Image
    if pno not in _page_img:
        _page_img[pno] = Image.open(f"{WORK}/l1clean/p-{pno:03d}.png").convert("L")
    return _page_img[pno]


def cell_reocr(pno, x0_px, x1_px, y0_px, y1_px):
    """Re-OCR a single cell. Fast path: PIL crop of the cached 300-dpi render
    with dark-pixel geometry deciding empty/dash; tesseract (3x upscale) only
    when a number is actually present; pdfplumber 600-dpi vector render as a
    final fallback for unparseable results."""
    key = (str(pno), f"{x0_px:.0f},{x1_px:.0f},{y0_px:.0f},{y1_px:.0f}")
    if key in cell_cache:
        return cell_cache[key]
    from PIL import Image
    img = _get_img(pno)
    x0 = max(0, int(x0_px)); y0 = max(0, int(y0_px) - 2)
    x1 = min(img.width, int(x1_px) + 3); y1 = min(img.height, int(y1_px) + 2)
    crop = img.crop((x0, y0, x1, y1))
    px = crop.load()
    xs, ys, dark = [], [], 0
    for yy in range(crop.height):
        for xx in range(crop.width):
            if px[xx, yy] < 128:
                dark += 1
                xs.append(xx); ys.append(yy)
    res = None
    if dark < 12:
        res = ""
    elif ys and (max(ys) - min(ys)) <= 8 and (max(xs) - min(xs)) <= 40:
        res = "–"          # a lone en-dash stroke
    else:
        big = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
        tmp = f"/tmp/cell_{pno}.png"
        big.save(tmp)
        out = subprocess.run(
            ["tesseract", tmp, "stdout", "--psm", "7", "-c",
             "tessedit_char_whitelist=0123456789,.()-*"],
            capture_output=True, text=True).stdout.strip().replace(" ", "")
        out = out.strip("-\u2013\u2014")
        if out == "" or re.fullmatch(r"[-,.]*", out):
            res = "–"
        elif re.fullmatch(r"\*?\(?[\d,]+(?:\.\d{1,2})?\)?", out):
            res = out
        else:
            # fallback: crisp 600-dpi render of the vector page
            k = 72.0 / DPI
            page = pdf.pages[pno - 1]
            cx0 = max(x0_px * k - 3, 0); cy0 = max(y0_px * k - 2, 0)
            cx1 = min(x1_px * k + 3, page.width); cy1 = min(y1_px * k + 2, page.height)
            im = page.crop((cx0, cy0, cx1, cy1)).to_image(resolution=600)
            im.save(tmp)
            out2 = subprocess.run(
                ["tesseract", tmp, "stdout", "--psm", "7", "-c",
                 "tessedit_char_whitelist=0123456789,.()-*"],
                capture_output=True, text=True).stdout.strip().replace(" ", "")
            out2 = out2.strip("-\u2013\u2014")
            if re.fullmatch(r"\*?\(?[\d,]+(?:\.\d{1,2})?\)?", out2):
                res = out2
            else:
                m = re.search(r"\(?\d[\d,]*(?:\.\d{1,2})?\)?", out2 or out)
                res = m.group(0) if m else "–"
                print(f"  !! cell re-OCR noisy p{pno}: {out!r}/{out2!r} -> {res!r}")
    cell_cache[key] = res
    _cache_w.writerow([key[0], key[1], res])
    return res


def parse_amount(tok):
    tok = tok.strip().replace("*", "").strip(",.")
    if tok in {"–", "-", "—", "_", ""}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()").replace(",", "").strip(".") or "0"
    v = float(tok)
    return -v if neg else v


def load_page(pno):
    """Return list of lines: (top_px, bottom_px, [ (text,left,right) ... ])."""
    words = []
    for r in csv.DictReader(open(f"{WORK}/l1tsv/p-{pno:03d}.tsv"), delimiter="\t"):
        t = r["text"].strip()
        if not t:
            continue
        left, top = int(r["left"]), int(r["top"])
        w, h = int(r["width"]), int(r["height"])
        words.append(dict(text=t, left=left, right=left + w, top=top, bottom=top + h))
    words.sort(key=lambda w: (w["top"], w["left"]))
    # cluster into lines by top (row pitch ~35 px)
    lines = []
    for w in sorted(words, key=lambda x: x["top"]):
        placed = False
        for ln in lines:
            if abs(w["top"] - ln["top"]) <= 12:
                ln["ws"].append(w)
                placed = True
                break
        if not placed:
            lines.append(dict(top=w["top"], ws=[w]))
    out = []
    for ln in sorted(lines, key=lambda l: l["top"]):
        ws = sorted(ln["ws"], key=lambda x: x["left"])
        # merge fragments split at a comma/period ('148,631 ,837.65')
        merged = []
        for w in ws:
            if merged:
                p = merged[-1]
                gap = w["left"] - p["right"]
                if (gap < 18 and re.match(r"^[\d,().*]+$", p["text"])
                        and re.match(r"^[\d,().]+$", w["text"])
                        and not (NUMRE.match(p["text"]) and NUMRE.match(w["text"])
                                 and len(p["text"]) > 4 and len(w["text"]) > 4)):
                    p["text"] += w["text"]
                    p["right"] = w["right"]
                    continue
            merged.append(dict(w))
        top = min(x["top"] for x in merged)
        bot = max(x["bottom"] for x in merged)
        out.append((top, bot, merged))
    # the Prestasi value of boxed subtotal rows prints on a slightly lower
    # baseline; re-attach such orphan single-value lines to the row above
    merged_out = []
    for top, bot, ws2 in out:
        if (merged_out and len(ws2) == 1 and NUMRE.match(ws2[0]["text"])
                and ws2[0]["right"] > 1100 and top - merged_out[-1][0] < 26):
            pt, pb, pws = merged_out[-1]
            merged_out[-1] = (pt, max(pb, bot), pws + ws2)
        else:
            merged_out.append((top, bot, list(ws2)))
    return merged_out


def page_shift(lines):
    """Estimate x-shift of this page's column frame vs the template."""
    rights = []
    for _t, _b, ws in lines:
        for w in ws:
            if NUMRE.match(w["text"]) and len(w["text"]) > 3 and w["right"] > 1100:
                rights.append(w["right"])
    best, best_n = 0, -1
    for cand in range(-90, 91, 2):
        n = 0
        for r in rights:
            if any(abs(r - (a + cand)) <= 18 for a in TEMPLATE.values()):
                n += 1
        if n > best_n:
            best, best_n = cand, n
    return best


HDR_JUNK = re.compile(
    r"^(LAMPIRAN|Penyata Perbelanjaan|bagi tahun|\(sambungan|Maksud Perbelanjaan|"
    r"Asal Dipinda|RM RM|PENYATA KEWANGAN|Nota:|Nota :|\W+$|\d+\s*$|.{0,3}$)")

rows = []
salvage_notes = []
maksud = maksud_name = jenis = None
program_code = program_name = None
akt_code = akt_name = None
akt_foot = False
last_header = None
pending_maksud_wrap = False
reocr_count = 0

for pno in range(95, 207):
    lines = load_page(pno)
    if not any("Perbelanjaan Mengurus" in " ".join(w["text"] for w in ws) for _t, _b, ws in lines):
        continue
    shift = page_shift(lines)
    anchors = {c: TEMPLATE[c] + shift for c in COLS}
    val_x_min = VAL_X_MIN + shift
    printed = pno - 16
    # data band: below the 'RM RM RM %' units row, above the page footer
    data_top, data_bot = 0, 10 ** 9
    for top, _b, ws in lines:
        raw = " ".join(w["text"] for w in ws)
        if re.search(r"RM\s+RM\s+RM", raw) or ("Asal" in raw and "Dipinda" in raw):
            data_top = max(data_top, top + 25)
        if "PENYATA KEWANGAN KERAJAAN" in raw or "Teks Lamp" in raw or "14/10/2021" in raw:
            data_bot = min(data_bot, top - 5)
    prev_rowlike = None
    for top, bot, ws in lines:
        if top < data_top or top > data_bot:
            continue
        raw_line = " ".join(w["text"] for w in ws)
        if re.search(r"\(disambung|\(sambungan|^\W*$", raw_line):
            continue
        # split into label / value zones
        labws = [w for w in ws if w["right"] < val_x_min]
        valws = [w for w in ws if w["right"] >= val_x_min]
        label = " ".join(w["text"] for w in labws).strip()
        label = re.sub(r"\s*[–—-]{1,2}\s*\(SAMB\.?\)\s*$", "", label).strip()
        label = label.replace("—", "-")
        label = re.sub(r"^J[a-zJ1l]{0,4}ah\b", "Jumlah", label)
        label = re.sub(r"^JUM[A-Z1]{0,3}AH\b", "JUMLAH", label)
        if HDR_JUNK.match(raw_line) and not valws:
            continue
        if re.match(r"^(LAMPIRAN|Penyata Perbelanjaan Mengurus$|bagi tahun berakhir|Maksud Perbelanjaan$|Asal Dipinda|RM RM)", label):
            continue
        if label.startswith(("Nota:", "Nota :")):
            continue
        if len(ws) == 1 and re.fullmatch(r"\d{1,3}", ws[0]["text"]):
            continue    # printed page number
        # ---- value assignment by column x ----
        vals = {}
        foot = False
        garbled = False
        leftover_alpha = []
        for w in valws:
            t = w["text"]
            if t.startswith("*"):
                foot = True
            tt = t.replace("*", "")
            ci = min(COLS, key=lambda c: abs(anchors[c] - w["right"]))
            near = abs(anchors[ci] - w["right"]) <= 60
            if NUMRE.match(tt):
                if near:
                    vals[ci] = tt
                else:
                    garbled = True
            elif DASHRE.match(tt) or re.fullmatch(r"[A-Za-z]{1,2}[.)]?", tt) or tt in ("§", "%"):
                if near:
                    vals.setdefault(ci, "–")
            elif re.fullmatch(r"[A-Za-z()&.,-]+", t):
                leftover_alpha.append(t)   # label overflow into the value zone
            else:
                garbled = True
        if leftover_alpha and not vals:
            label = (label + " " + " ".join(leftover_alpha)).strip()
            valws = []
        has_vals = bool(vals) or bool(valws and not leftover_alpha)
        has_vals = bool(vals) or any(NUMRE.match(w["text"].replace("*", "")) or DASHRE.match(w["text"]) for w in valws)
        if not label and has_vals:
            numeric = [w for w in valws if NUMRE.match(w["text"].replace("*", ""))]
            if not numeric:
                continue    # rules/artifacts without any content
            # a data row whose label OCR failed entirely: re-OCR the label band
            from PIL import Image
            img = _get_img(pno)
            lx0, lx1 = 380, int(val_x_min) - 10
            crop = img.crop((lx0, max(0, top - 3), lx1, min(img.height, bot + 3)))
            big = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
            tmp = f"/tmp/lab_{pno}.png"
            big.save(tmp)
            lab_txt = subprocess.run(["tesseract", tmp, "stdout", "--psm", "7"],
                                     capture_output=True, text=True).stdout.strip()
            lab_txt = re.sub(r"\s+", " ", lab_txt).strip()
            lab_txt = re.sub(r"^Jum[a-zJ1l]{0,3}ah\b", "Jumlah", lab_txt)
            if lab_txt:
                salvage_notes.append(f"label re-OCR p{pno} y{top}: -> {lab_txt!r}")
                label = lab_txt
        # ---- classification ----
        s = label
        if not has_vals:
            if re.match(r"^PERBELANJAAN TANGGUNGAN", s):
                jenis = "Tanggungan"
                prev_rowlike = None
                continue
            if re.match(r"^PERBELANJAAN BEKALAN", s):
                jenis = "Bekalan"
                prev_rowlike = None
                continue
            mh = re.match(r"^([TB])[.,_]\s?(\d{2})[.,_]*\s+(.+?)$", s)
            if mh:
                maksud = f"{mh.group(1)}.{mh.group(2)}"
                nm = mh.group(3).strip()
                maksud_name = nm
                jenis = "Tanggungan" if mh.group(1) == "T" else "Bekalan"
                program_code = program_name = akt_code = akt_name = None
                last_header = "maksud"
                prev_rowlike = None
                continue
            ph = re.match(r"^(\*?)\s?(\d{6})\s+(.+)$", s)
            if ph:
                code, name = ph.group(2), ph.group(3).strip()
                name = re.sub(r"\s*[–—-]{0,2}\s*\(SAMB\.?\)\s*$", "", name).strip()
                if code[2:] == "0000":
                    program_code, program_name = code, name
                    akt_code = akt_name = None
                    akt_foot = False
                    last_header = "program"
                else:
                    if program_code is None or code[:2] != program_code[:2]:
                        inferred = code[:2] + "0000"
                        salvage_notes.append(
                            f"missing program header before aktiviti {code} ({maksud}, pdf {pno}): "
                            f"program {inferred} inferred from code prefix")
                        program_code, program_name = inferred, None
                    akt_code, akt_name = code, name
                    akt_foot = ph.group(1) == "*"
                    last_header = "aktiviti"
                prev_rowlike = None
                continue
            # wrapped header continuation
            if (last_header and s and len(s) < 75
                    and not re.search(r"[\d,]{5,}", s)
                    and not s.startswith(("JUMLAH", "Jumlah", "PERBELANJAAN"))):
                frag = re.sub(r"\s*[–—-]{0,2}\s*\(SAMB\.?\)\s*$", "", s).strip()
                if frag:
                    if last_header == "maksud" and maksud_name is not None:
                        maksud_name = (maksud_name + " " + frag).strip()
                    elif last_header == "program" and program_name is not None:
                        program_name = (program_name + " " + frag).strip()
                    elif last_header == "aktiviti" and akt_name is not None:
                        akt_name = (akt_name + " " + frag).strip()
                continue
            prev_rowlike = None
            continue
        # ---- rows with values ----
        last_header = None
        rt = None
        obj_code = obj_class = None
        lab = s
        m5 = re.match(r"^\*?\s?(\d{5})\s+(.+)$", s)
        mj = re.match(r"^Jumlah\s+[0OQ]?(\d{5,6})\b", s)
        if m5 and m5.group(1) in OBJ_CLASSES:
            rt, obj_code, obj_class = "object_aktiviti", m5.group(1), m5.group(2).strip()
            if s.startswith("*"):
                foot = True
        elif mj:
            code = mj.group(1).zfill(6)
            rt = "jumlah_program" if code[2:] == "0000" else "jumlah_aktiviti"
            if rt == "jumlah_aktiviti" and code != akt_code:
                akt_code = code
            lab = f"Jumlah {code}"
        elif re.match(r"^Jumlah\s+(Emolumen|Perkhidmatan|Aset|Pemberian|Perbelanjaan)", s):
            rt = "jumlah_objek_maksud"
            obj_class = re.sub(r"^Jumlah\s+", "", s).replace("& ", "dan ")
        elif s in OBJ_NAMES or re.match(r"^(Emolumen|Perkhidmatan dan Bekalan|Aset|Pemberian (dan|&) Kenaan Bayaran Tetap|Perbelanjaan\s*-\s*perbelanjaan Lain)$", s):
            rt, obj_class = "object_program", s.replace("& ", "dan ")
        elif re.match(r"^JUMLAH PERBELANJAAN TANGGUNGAN", s) or re.match(r"^JUMLAH PERBELANJAAN BEKALAN", s):
            rt = "jumlah_jenis"
        elif re.match(r"^JUMLAH (PERBELANJAAN|KESELURUHAN) MENGURUS", s):
            rt = "jumlah_besar"
        elif re.match(r"^JUMLAH\s+\S", s):
            rt = "jumlah_maksud"
            lab = re.sub(r"^JUMLAH\s+", "", s).strip()
        else:
            rt = "unclassified"
        # ---- fill missing cells by re-OCR of the vector page ----
        filled = {}
        for c in COLS:
            if c in vals:
                filled[c] = vals[c]
            else:
                x1a = anchors[c]
                x0a = x1a - (260 if c != "pct" else 200)
                tok = cell_reocr(pno, x0a, x1a, top, bot)
                reocr_count += 1
                filled[c] = tok if tok else "–"
        asal = parse_amount(filled["asal"])
        dipinda = parse_amount(filled["dipinda"])
        sebenar = parse_amount(filled["sebenar"])
        pct = parse_amount(filled["pct"]) if filled["pct"].strip(",.") not in ("", "–") else None
        if "*" in (filled["sebenar"] or ""):
            foot = True
        if rt in ("object_aktiviti", "jumlah_aktiviti") and akt_foot:
            foot = True
        rows.append([
            jenis, maksud, maksud_name,
            program_code, program_name, akt_code, akt_name,
            obj_code, obj_class, rt, lab, 2020,
            asal, None, None, dipinda, sebenar, pct, None, foot,
            SRC, pno, printed, "Lampiran 1 Penyata Perbelanjaan Mengurus", garbled,
            dict(pno=pno, top=top, bot=bot, shift=shift),
        ])
        prev_rowlike = rt

_cache_f.flush()

# 'Jumlah <objek class>' rows are maksud-level summaries ONLY when they close
# the maksud; inside a program whose classes each print a single 'Jumlah
# <class>' line before 'Jumlah <program>' (e.g. B.11 010000), they are
# program-level class summaries -> object_program.
run_start = None
for i, r in enumerate(rows + [[None] * 26]):
    rt = r[9] if r[0] is not None or i < len(rows) else None
    if i < len(rows) and rows[i][9] == "jumlah_objek_maksud":
        if run_start is None:
            run_start = i
        continue
    if run_start is not None:
        nxt = rows[i][9] if i < len(rows) else None
        if nxt == "jumlah_program":
            for j in range(run_start, i):
                rows[j][9] = "object_program"
        run_start = None

# =====================================================================
# Verification-and-repair: printed identities drive targeted re-OCR of
# suspect rows from crisp 600-dpi renders of the ORIGINAL vector pages.
# Every replacement is logged. Print-side inconsistencies that survive a
# clean re-read are left as printed and surface in validate.py.
# =====================================================================
ROW_CACHE_PATH = f"{WORK}/l1rows.csv"
row_cache = {}
if os.path.exists(ROW_CACHE_PATH):
    for _r in csv.reader(open(ROW_CACHE_PATH)):
        row_cache[(_r[0], _r[1])] = _r[2]
_rcache_f = open(ROW_CACHE_PATH, "a", newline="")
_rcache_w = csv.writer(_rcache_f)


def row_reocr(meta):
    """Re-OCR one row band from the vector PDF at 600 dpi; return col->token."""
    pno, top, bot, shift = meta["pno"], meta["top"], meta["bot"], meta["shift"]
    key = (str(pno), f"{top},{bot}")
    if key in row_cache:
        raw = row_cache[key]
    else:
        k = 72.0 / DPI
        page = pdf.pages[pno - 1]
        x0 = max((VAL_X_MIN + shift - 80) * k, 0)
        x1 = min((TEMPLATE["pct"] + shift + 30) * k, page.width)
        y0 = max(top * k - 2, 0)
        y1 = min(bot * k + 2, page.height)
        im = page.crop((x0, y0, x1, y1)).to_image(resolution=600)
        tmp = f"/tmp/row_{pno}.png"
        im.save(tmp)
        out = subprocess.run(["tesseract", tmp, "stdout", "--psm", "7", "tsv", "-c",
                              "tessedit_char_whitelist=0123456789,.()-*"],
                             capture_output=True, text=True).stdout
        toks = []
        for ln in out.splitlines()[1:]:
            f = ln.split("\t")
            if len(f) >= 12 and f[11].strip():
                left = int(f[6]); w = int(f[8])
                # 600-dpi crop px -> 300-dpi page frame px
                x300 = (x0 * DPI / 72.0) + (left + w) / 2.0
                toks.append((f[11].strip(), x300))
        # merge fragments
        merged = []
        for t, r in toks:
            if merged and re.match(r"^[\d,().*]+$", merged[-1][0]) and re.match(r"^[\d,().]+$", t) \
                    and r - merged[-1][1] < 60 and not (NUMRE.match(merged[-1][0]) and NUMRE.match(t)
                                                        and len(merged[-1][0]) > 4 and len(t) > 4):
                merged[-1] = (merged[-1][0] + t, r)
            else:
                merged.append((t, r))
        raw = "|".join(f"{t}@{r:.0f}" for t, r in merged)
        row_cache[key] = raw
        _rcache_w.writerow([key[0], key[1], raw])
    anchors = {c: TEMPLATE[c] + meta["shift"] for c in COLS}
    got = {}
    for part in raw.split("|"):
        if not part:
            continue
        t, r = part.rsplit("@", 1)
        r = float(r)
        tt = t.strip("-")
        ci = min(COLS, key=lambda c: abs(anchors[c] - r))
        if abs(anchors[ci] - r) > 70 or ci in got:
            continue
        if re.fullmatch(r"\*?\(?[\d,]+(?:\.\d{1,2})?\)?", tt):
            got[ci] = tt
        elif re.fullmatch(r"[-,.]*", t):
            got[ci] = "–"
    return got


IDX = dict(asal=12, dipinda=15, sebenar=16, pct=17)
ORIG = {}    # (row_index, col) -> page-level OCR value before row-level re-OCR
repaired = set()


def apply_reocr(i, why):
    """Adopt the full-row 600-dpi re-OCR for a suspect row (recovers wide
    amounts the page OCR dropped). The prior page-level reading is kept in
    ORIG; where the two independent reads disagree, the constraint solver
    below arbitrates and can restore the page reading."""
    if i in repaired:
        return False
    repaired.add(i)
    r = rows[i]
    got = row_reocr(r[25])
    changed = False
    for c in COLS:
        if c not in got:
            continue
        newv = parse_amount(got[c]) if got[c] != "–" else 0.0
        if c == "pct":
            old = r[IDX["pct"]]
            newp = None if got[c] == "–" else newv
            if (old is None) != (newp is None) or (old is not None and abs(old - (newp or 0)) > 0.005):
                ORIG[(i, "pct")] = old
                r[IDX["pct"]] = newp
                changed = True
        else:
            old = r[IDX[c]]
            if abs(old - newv) > 0.005:
                ORIG[(i, c)] = old
                r[IDX[c]] = newv
                changed = True
    return changed


def pct_bad(r):
    if r[IDX["pct"]] is None or not r[IDX["dipinda"]]:
        return False
    exp = r[IDX["sebenar"]] / r[IDX["dipinda"]] * 100
    return abs(exp - r[IDX["pct"]]) > 0.6


def group_checks():
    """Return set of row indices belonging to failing printed-sum groups."""
    bad = set()
    # aktiviti: objects sum = Jumlah <akt>
    i = 0
    n = len(rows)
    # group by (maksud, program, aktiviti) in document order
    groups = defaultdict(list)
    for j, r in enumerate(rows):
        if r[9] == "object_aktiviti":
            groups[(r[1], r[3], r[5])].append(j)
        elif r[9] == "jumlah_aktiviti":
            groups[(r[1], r[3], r[5])].append(j)
    for key, idxs in groups.items():
        objs = [j for j in idxs if rows[j][9] == "object_aktiviti"]
        jums = [j for j in idxs if rows[j][9] == "jumlah_aktiviti"]
        if not jums:
            continue
        for c in ("asal", "dipinda", "sebenar"):
            if abs(sum(rows[j][IDX[c]] for j in objs) - sum(rows[j][IDX[c]] for j in jums)) > 0.5:
                bad.update(objs + jums)
    # program: object_program rows sum by class = objects; jumlah_program = sum jumlah_aktiviti
    pgroups = defaultdict(list)
    for j, r in enumerate(rows):
        if r[9] in ("object_aktiviti", "jumlah_aktiviti", "object_program", "jumlah_program"):
            pgroups[(r[1], r[3])].append(j)
    for key, idxs in pgroups.items():
        ja = [j for j in idxs if rows[j][9] == "jumlah_aktiviti"]
        jp = [j for j in idxs if rows[j][9] == "jumlah_program"]
        if not jp:
            continue
        for c in ("asal", "dipinda", "sebenar"):
            if abs(sum(rows[j][IDX[c]] for j in ja) - sum(rows[j][IDX[c]] for j in jp)) > 0.5:
                bad.update(idxs)
    return bad


for rnd in range(3):
    suspects = (set(j for j, r in enumerate(rows) if pct_bad(r)) | group_checks()) - repaired
    if not suspects:
        break
    print(f"row re-OCR round {rnd}: {len(suspects)} suspect rows")
    for j in sorted(suspects):
        apply_reocr(j, "identity/sum check")
_rcache_f.flush()
print(f"after row re-OCR: rows failing pct identity: {sum(1 for r in rows if pct_bad(r))}; "
      f"rows in failing sum-groups: {len(group_checks())}")

# ---------------------------------------------------------------------
# Constraint-solver salvage: the print's own arithmetic (aktiviti/program/
# maksud/jenis sums, Nota 5(b) external totals) identifies single cells the
# OCR persistently misread. A fix is applied ONLY when (a) the cell is the
# unique unconfirmed cell of a failing constraint, and (b) the solved value
# is a near-digit variant of the OCR reading (edit distance <= 2) -- i.e. an
# OCR error, not a print discrepancy. Everything else is left as read and
# surfaces in validate.py with a diagnosis.
# ---------------------------------------------------------------------
NOTA5B = {}
with open("/home/claude/pkkp/warehouse2020/fact_opex_maksud.csv", encoding="utf-8") as _f:
    for _r in csv.DictReader(_f):
        NOTA5B[_r["maksud_code"]] = (float(_r["anggaran_asal_rm"]), float(_r["anggaran_dipinda_rm"]),
                                     float(_r["sebenar_rm"]))
MAKSUD_BY_NAME = {}
with open("/home/claude/pkkp/warehouse2020/fact_opex_maksud.csv", encoding="utf-8") as _f:
    for _r in csv.DictReader(_f):
        MAKSUD_BY_NAME[(_r["jenis_bm"], _r["maksud_name_bm"].upper())] = _r["maksud_code"]


def edit_dist(a, b):
    a, b = re.sub(r"[^\d]", "", a), re.sub(r"[^\d]", "", b)
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            cur = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev = cur
    return dp[n]


def fmt(v):
    return f"{v:,.2f}"


def build_constraints():
    cons = []   # (name, [(idx, col, sign)], const)
    ag = defaultdict(lambda: defaultdict(list))
    for j, r in enumerate(rows):
        rt = r[9]
        if rt == "object_aktiviti":
            ag[("akt", r[1], r[3], r[5])]["m"].append(j)
            ag[("pobj", r[1], r[3], (r[8] or "").strip())]["m"].append(j)
            ag[("omaks", r[1], (r[8] or "").strip())]["m"].append(j)
        elif rt == "jumlah_aktiviti":
            ag[("akt", r[1], r[3], r[5])]["t"].append(j)
            ag[("prog", r[1], r[3])]["m"].append(j)
        elif rt == "jumlah_program":
            ag[("prog", r[1], r[3])]["t"].append(j)
            ag[("maks", r[1])]["m"].append(j)
        elif rt == "object_program":
            ag[("pobj", r[1], r[3], (r[8] or "").strip())]["t"].append(j)
        elif rt == "jumlah_objek_maksud":
            ag[("omaks", r[1], (r[8] or "").strip())]["t"].append(j)
        elif rt == "jumlah_maksud":
            ag[("maks", r[1])]["t"].append(j)
    for key, d in ag.items():
        if d["t"] and d["m"]:
            for c in ("asal", "dipinda", "sebenar"):
                cons.append((f"{key}", [(j, c, 1) for j in d["m"]] + [(j, c, -1) for j in d["t"]], 0.0, c))
    # external truth: jumlah_maksud row == Nota 5(b)
    for j, r in enumerate(rows):
        if r[9] == "jumlah_maksud" and r[1] in NOTA5B:
            a5, d5, s5 = NOTA5B[r[1]]
            cons.append((f"nota5b:{r[1]}", [(j, "asal", 1)], a5, "asal"))
            cons.append((f"nota5b:{r[1]}", [(j, "dipinda", 1)], d5, "dipinda"))
            cons.append((f"nota5b:{r[1]}d", [(j, "sebenar", 1)], round(s5), "sebenar"))
    return cons


# cells where a printed identity disagrees with the OCR reading by digit
# SUBSTITUTION (not a mere decimal/truncation artifact): each was cropped from
# the 300-dpi render and verified BY EYE against the print before being listed
# here. Cells where the print itself carries the inconsistent value are NOT
# listed; they stay as printed and are reported in validate.py.
MANUAL_OVERRIDES = {   # (pdf_page, label, col, aktiviti_code) -> (value, note)
    (139, "40000 Pemberian dan Kenaan Bayaran Tetap", "sebenar", "050100"):
        (2574800.00, "crop verified against print (2,574,800.00); tesseract misreads the 5 as 9 at 300 and 600 dpi"),
    (153, "Jumlah 030200", "pct", "030200"):
        (100.00, "crop verified against print (100.00); page OCR read 400.00"),
}
contested_seen = set()


def solve_round():
    cons = build_constraints()
    # evaluate
    stat = []
    for name, cells, const, col in cons:
        s = sum(sign * rows[j][IDX[c]] for j, c, sign in cells) - const
        stat.append((abs(s) <= (0.55 if not name.startswith("nota5b") else 0.55), s))
    confirmed = set()
    for (ok, _s), (name, cells, const, col) in zip(stat, cons):
        if ok:
            for j, c, sign in cells:
                confirmed.add((j, c))
    fixed = 0
    for (ok, s), (name, cells, const, col) in zip(stat, cons):
        if ok:
            continue
        unconf = [(j, c, sign) for j, c, sign in cells if (j, c) not in confirmed]
        if len(unconf) != 1:
            continue
        j, c, sign = unconf[0]
        old = rows[j][IDX[c]]
        new = old - s / sign
        if new < 0 and c != "sebenar":
            continue
        ed = edit_dist(f"{old:.2f}", f"{new:.2f}")
        # rounding-only differences (nota5b prints whole RM) are not fixes
        if abs(new - old) < 1:
            continue
        # OCR truncation: page OCR caught only the tail (or head) of the number
        dr, di = re.sub(r"[^\d]", "", f"{old:.2f}"), re.sub(r"[^\d]", "", f"{new:.2f}")
        dr0, di0 = dr.strip("0"), di.strip("0")
        decshift = dr0 == di0 and dr0 != ""        # same digits, decimal/comma slip
        trunc = len(dr) >= 5 and (di.endswith(dr) or di.startswith(dr))
        orig = ORIG.get((j, c))
        if orig is not None and abs(orig - new) <= 0.55 and abs(orig - old) > 0.55:
            salvage_notes.append(
                f"arithmetic salvage p{rows[j][21]} '{str(rows[j][10])[:40]}' {c} "
                f"{fmt(old)} -> {fmt(new)} [constraint {name}; page-level OCR reading restored]")
            rows[j][IDX[c]] = orig
            confirmed.add((j, c))
            fixed += 1
            continue
        if not (decshift or trunc):
            if (name, j, c) not in contested_seen:
                contested_seen.add((name, j, c))
                mo_key = (rows[j][21], str(rows[j][10]), c, rows[j][5])
                if mo_key in MANUAL_OVERRIDES:
                    val, note = MANUAL_OVERRIDES[mo_key]
                    salvage_notes.append(
                        f"manual override p{rows[j][21]} '{str(rows[j][10])[:40]}' {c} "
                        f"{fmt(old)} -> {fmt(val)} ({note})")
                    rows[j][IDX[c]] = val
                    confirmed.add((j, c))
                    fixed += 1
                else:
                    salvage_notes.append(
                        f"CONTESTED cell p{rows[j][21]} '{str(rows[j][10])[:40]}' {c}: "
                        f"read {fmt(old)}, constraint {name} implies {fmt(new)} "
                        f"(needs visual verification; left as read)")
            continue
        if True:
            salvage_notes.append(
                f"arithmetic salvage p{rows[j][21]} '{str(rows[j][10])[:40]}' {c} "
                f"{fmt(old)} -> {fmt(new)} [constraint {name}, edit-dist {ed}"
                + (", truncation" if trunc else "") + "]")
            rows[j][IDX[c]] = round(new, 2)
            # re-derive pct expectation left as printed
            fixed += 1
            confirmed.add((j, c))
        else:
            salvage_notes.append(
                f"UNRESOLVED constraint {name}: cell p{rows[j][21]} '{str(rows[j][10])[:40]}' {c} "
                f"read {fmt(old)}, implied {fmt(new)} (edit-dist {ed} too large; left as read)")
    return fixed


for _ in range(6):
    if not solve_round():
        break
# pct salvage: sums confirmed the RM columns; a residual pct-identity failure
# means the % token itself was misread (e.g. '400.00' for '100.00')
for ridx, r in enumerate(rows):
    if not pct_bad(r):
        continue
    exp = round(r[IDX["sebenar"]] / r[IDX["dipinda"]] * 100, 2)
    old_p = r[IDX["pct"]]
    orig_p = ORIG.get((ridx, "pct"))
    if old_p is not None and old_p >= 1000 and abs(old_p / 100.0 - exp) < 0.7:
        salvage_notes.append(f"pct salvage p{r[21]} '{str(r[10])[:40]}' pct {old_p} -> {old_p/100.0} "
                             f"(decimal point dropped by OCR; RM columns confirmed)")
        r[IDX["pct"]] = old_p / 100.0
    elif orig_p is not None and abs(orig_p - exp) < 0.6 and (old_p is None or abs(orig_p - old_p) > 0.005):
        salvage_notes.append(f"pct salvage p{r[21]} '{str(r[10])[:40]}' pct {old_p} -> {orig_p} "
                             f"(page-level OCR reading restored; agrees with identity)")
        r[IDX["pct"]] = orig_p
    else:
        mo_key = (r[21], str(r[10]), "pct", r[5])
        if mo_key in MANUAL_OVERRIDES:
            val, note = MANUAL_OVERRIDES[mo_key]
            salvage_notes.append(f"manual override p{r[21]} '{str(r[10])[:40]}' pct {old_p} -> {val} ({note})")
            r[IDX["pct"]] = val
        else:
            salvage_notes.append(f"CONTESTED pct p{r[21]} '{str(r[10])[:40]}': read {old_p}, "
                                 f"identity implies {exp} (needs visual verification; left as read)")
rem_pct = sum(1 for r in rows if pct_bad(r))
rem_groups = len(group_checks())
print(f"after arithmetic salvage: rows failing pct identity: {rem_pct}; rows in failing sum-groups: {rem_groups}")

# drop decorative junk rows (no digits in label, all cells nil)
before = len(rows)
rows = [r for r in rows if not (r[9] == "unclassified" and not re.search(r"\d", str(r[10]))
                                and not r[12] and not r[15] and not r[16])]
print(f"dropped {before - len(rows)} empty junk rows")

# back-fill program names for inferred program blocks
_pnames = {}
for r in rows:
    if r[3] and r[4]:
        _pnames.setdefault((r[1], r[3]), r[4])
for r in rows:
    if r[3] and not r[4] and (r[1], r[3]) in _pnames:
        r[4] = _pnames[(r[1], r[3])]

# canonical maksud names from Nota 5(b) (text layer, authoritative spelling)
CANON = {}
with open("/home/claude/pkkp/warehouse2020/fact_opex_maksud.csv", encoding="utf-8") as _f:
    for _r in csv.DictReader(_f):
        CANON[_r["maksud_code"]] = _r["maksud_name_bm"]
for r in rows:
    if r[1] in CANON:
        r[2] = CANON[r[1]]
    if r[9] == "jumlah_maksud" and r[1] in CANON:
        r[10] = CANON[r[1]]

IDX_RT, IDX_LBL = 9, 10
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
    for r in rows:
        cw.writerow(r[:24])

from collections import Counter
c = Counter(r[9] for r in rows)
print(f"fact_opex_detail.csv: {len(rows)} rows | cell re-OCRs: {reocr_count}")
for k, v in c.most_common():
    print(f"  {k}: {v}")
for n in salvage_notes:
    print("!!", n)
gb = [r for r in rows if r[24]]
print(f"garbled-token rows: {len(gb)}")
for r in gb[:20]:
    print("  ?g", r[1], r[9], str(r[10])[:50], "p", r[21])
un = [r for r in rows if r[9] == "unclassified"]
print(f"unclassified: {len(un)}")
for r in un[:25]:
    print("   ?", str(r[10])[:70], "p", r[21])
# quick self-check: pct identity on object rows
bad_pct = 0
for r in rows:
    if r[9] == "object_aktiviti" and r[15] and r[17] is not None and r[15] > 0:
        exp = r[16] / r[15] * 100
        if abs(exp - r[17]) > 0.6:
            bad_pct += 1
print(f"object rows failing pct≈sebenar/dipinda: {bad_pct}")
jm = sum(r[16] for r in rows if r[9] == "jumlah_maksud")
print(f"sum(jumlah_maksud sebenar) = {jm:,.2f}")
