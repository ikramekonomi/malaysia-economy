#!/usr/bin/env python3
"""Extract Lampiran 1: Penyata Perbelanjaan Mengurus detail (PKKP 2015,
pdf pages 80-241, printed 66-227) -> warehouse2015/fact_opex_detail.csv.

Adapts the proven 2020 architecture (OCR + column-x mapping + constraint-
solver repair) to a much harder source: the 2015 volume is a 144-dpi JPEG
scan with NO text layer, OCR'd at 400 dpi (ocrlib artifacts).  Page-level
tesseract (psm 6) garbles a large share of numeric cells, so every valued
row's value band is ALSO re-OCR'd as a single line (3x upscale, psm 7,
digit whitelist) and the two independent readings feed a per-cell candidate
pool.  The volume's own printed arithmetic (pct identity, aktiviti/program/
maksud/jenis column sums) plus the eye-verified Nota 5(b) oracle
(warehouse2015/fact_opex_maksud.csv) then arbitrates:  a cell is auto-fixed
only when it is the unique unconfirmed cell of a failing constraint AND the
solved value is a near-digit variant of an OCR reading (or an independent
re-read agrees).  Contested cells are eye-verified from zoomed crops and
hardcoded as MANUAL_OVERRIDES.  Print-side inconsistencies stay as printed
and are logged FAIL.

2015 layout: FOUR value columns -- Anggaran Asal | Anggaran Dipinda |
Sebenar Amaun | Sebenar %Anggaran.  As in 2014/2020, Dipinda is stored in
anggaran_jumlah_rm; anggaran_tambahan_rm / viremen_rm / varian_rm stay empty.
Hierarchy: Maksud (T.xx/B.xx) > Program (XX0000, ALL-CAPS) > Aktiviti
(XXYY00) > object rows (10000..50000); 'Jumlah XXYY00' aktiviti totals;
italic per-program class rows + 'Jumlah XX0000'; maksud-level italic
'Jumlah <class>' rows + 'JUMLAH <MAKSUD NAME>'; jenis class totals +
'JUMLAH PERBELANJAAN TANGGUNGAN/BEKALAN'; grand class totals +
'JUMLAH PERBELANJAAN MENGURUS'.
"""
import csv
import difflib
import os
import re
import subprocess
import sys
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "/home/claude/pkkp/work/2015/pipeline")
import ocrlib
from ocrlib import NUMRE, DASHRE

from PIL import Image

WORK = ocrlib.WORK
SRC = ocrlib.SRC
OUT = "/home/claude/pkkp/warehouse2015/fact_opex_detail.csv"
STMT = "Lampiran 1 Penyata Perbelanjaan Mengurus"
PAGE_LO = int(os.environ.get("L1_LO", 80))
PAGE_HI = int(os.environ.get("L1_HI", 241))
DEV = os.environ.get("L1_DEV") == "1"    # dev subrange: skip oracle ties/output guards

# column x-anchors (right edges, 400-dpi px), calibrated from 2015 pages
TEMPLATE = {"asal": 1930.0, "dipinda": 2272.0, "sebenar": 2614.0, "pct": 2958.0}
COLS = ["asal", "dipinda", "sebenar", "pct"]
VAL_X_MIN = 1620          # value zone starts right of this
LABEL_X_MAX = 3020        # ignore sideways-margin junk right of this
CODE_LEFT_MAX = 430       # rows whose first word starts left of this carry a code
CUR_SHIFT = 0             # per-page x shift (set in the page loop)
COL_TOL = 70

OBJ_CLASSES = {
    "10000": "Emolumen", "20000": "Perkhidmatan dan Bekalan", "30000": "Aset",
    "40000": "Pemberian dan Kenaan Bayaran Tetap",
    "50000": "Perbelanjaan-perbelanjaan Lain",
}
CLASS_CODE = {v: k for k, v in OBJ_CLASSES.items()}
CLASS_NAMES = list(OBJ_CLASSES.values())

FMT = {
    "asal": re.compile(r"^\(?\d{1,3}(?:,\d{3})*\)?$"),
    "dipinda": re.compile(r"^\(?\d{1,3}(?:,\d{3})*\)?$"),
    "sebenar": re.compile(r"^\(?\d{1,3}(?:,\d{3})*\.\d{2}\)?$"),
    "pct": re.compile(r"^\d{1,3}(?:,\d{3})?\.\d{2}$"),
}

FMT_ANY = re.compile(r"^\*?\(?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?\)?$")

# ---------------------------------------------------------------- caches
def _open_cache(path):
    d = {}
    if os.path.exists(path):
        for r in csv.reader(open(path)):
            d[(r[0], r[1])] = r[2]
    f = open(path, "a", newline="")
    return d, f, csv.writer(f)

cell_cache, _cf, _cw = _open_cache(f"{WORK}/l1cells.csv")
row_cache, _rf, _rw = _open_cache(f"{WORK}/l1rows.csv")
rawrow_cache, _rrf, _rrw = _open_cache(f"{WORK}/l1rawrows.csv")
code_cache, _kf, _kw = _open_cache(f"{WORK}/l1codes.csv")
_cache_lock = threading.Lock()
_tls = threading.local()


def _tmpname(tag):
    tid = getattr(_tls, "tid", None)
    if tid is None:
        _tls.tid = tid = threading.get_ident() % 100000
    return f"/tmp/l1_{tag}_{tid}.png"


_img_lock = threading.Lock()
def get_img(pno, clean=True):
    with _img_lock:
        return ocrlib.get_img(pno, clean=clean)


def tess(img, psm=7, whitelist="0123456789,.()-*", tag="c", tsv=False):
    tmp = _tmpname(tag)
    img.save(tmp)
    args = ["tesseract", tmp, "stdout", "--psm", str(psm)]
    if tsv:
        args.append("tsv")
    if whitelist:
        args += ["-c", f"tessedit_char_whitelist={whitelist}"]
    return subprocess.run(args, capture_output=True, text=True).stdout


def cell_ocr(pno, box, clean=True, scale=3, wide_x0=None):
    """Targeted single-cell re-OCR.  Dash/empty dark-pixel test runs on `box`
    (the column band proper); the OCR crop extends left to `wide_x0` so long
    right-aligned numbers keep their leading digits -- the value is then the
    RIGHTMOST token, so a neighbour column's tail entering the crop is
    harmless."""
    key = (f"{pno}{'e' if clean else 'r'}w",
           ",".join(f"{v:.0f}" for v in box) + (f"|{wide_x0:.0f}" if wide_x0 else ""))
    if key in cell_cache:
        return cell_cache[key]
    img = get_img(pno, clean=clean)
    x0, y0, x1, y1 = [int(v) for v in box]
    crop = img.crop((max(0, x0 - 2), max(0, y0 - 3),
                     min(img.width, x1 + 3), min(img.height, y1 + 3)))
    px = crop.load()
    xs, ys, dark = [], [], 0
    for yy in range(crop.height):
        for xx in range(crop.width):
            if px[xx, yy] < 128:
                dark += 1
                xs.append(xx)
                ys.append(yy)
    if dark < 25:
        res = ""
    elif ys and (max(ys) - min(ys)) <= 14 and (max(xs) - min(xs)) <= 60:
        res = "–"
    else:
        wx0 = int(wide_x0) if wide_x0 is not None else x0
        crop2 = img.crop((max(0, wx0), max(0, y0 - 3),
                          min(img.width, x1 + 3), min(img.height, y1 + 3)))
        big = crop2.resize((crop2.width * scale, crop2.height * scale), Image.LANCZOS)
        out = tess(big, psm=7, tag="c").strip()
        toks = [t for t in out.split() if re.search(r"\d", t)]
        joined = out.replace(" ", "").strip("-–—")
        res = ""
        if toks:
            # rightmost numeric token; but if the whole line parses as one
            # number (spaces are mid-number artifacts), prefer that
            tail = toks[-1]
            if FMT_ANY.match(joined):
                res = joined
            elif len(toks) >= 2 and FMT_ANY.match((toks[-2] + tail).strip("-–—")):
                res = (toks[-2] + tail).strip("-–—")
            else:
                res = tail.strip("-–—")
        if res == "" or re.fullmatch(r"[-,.]*", res):
            res = "–" if dark >= 25 else ""
    with _cache_lock:
        cell_cache[key] = res
        _cw.writerow([key[0], key[1], res])
    return res



def rowband_ocr(pno, top, bot, shift, clean=True):
    """Re-OCR one row's whole value band as a single line; return list of
    (token, right_x_page_px)."""
    cache, w = (row_cache, _rw) if clean else (rawrow_cache, _rrw)
    key = (str(pno), f"{top},{bot},{shift}")
    if key in cache:
        raw = cache[key]
    else:
        img = get_img(pno, clean=clean)
        x0 = int(VAL_X_MIN + shift - 40)
        x1 = int(min(TEMPLATE["pct"] + shift + 45, img.width))
        crop = img.crop((x0, max(0, top - 4), x1, min(img.height, bot + 4)))
        big = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
        out = tess(big, psm=7, tag="rb" if clean else "rr", tsv=True)
        toks = []
        for ln in out.splitlines()[1:]:
            f = ln.split("\t")
            if len(f) >= 12 and f[11].strip():
                left = int(f[6]); ww = int(f[8])
                toks.append((f[11].strip(), x0 + (left + ww) / 3.0))
        # merge adjacent numeric fragments
        merged = []
        for t, r in toks:
            if merged:
                pt, pr = merged[-1]
                if (r - pr < 70 and re.match(r"^[\d,().*]+$", pt)
                        and re.match(r"^[\d,().]+$", t)
                        and not (NUMRE.match(pt) and NUMRE.match(t)
                                 and len(pt) > 4 and len(t) > 4)):
                    merged[-1] = (pt + t, r)
                    continue
            merged.append((t, r))
        raw = "|".join(f"{t}@{r:.0f}" for t, r in merged)
        with _cache_lock:
            cache[key] = raw
            w.writerow([key[0], key[1], raw])
    toks = []
    for part in raw.split("|"):
        if part:
            t, r = part.rsplit("@", 1)
            toks.append((t, float(r)))
    return toks


# ------------------------------------------------------- token utilities
def parse_amount(tok):
    return ocrlib.parse_amount(tok)


def cands_from_token(col, tok):
    """Return list of (value, strict) candidate parses of an OCR token."""
    out = []
    t = tok.replace("*", "").replace(" ", "").strip()
    if not t:
        return out
    if t in {"–", "-", "—", "_"} or DASHRE.match(t):
        out.append((0.0 if col != "pct" else None, True))
        return out
    if FMT[col].match(t):
        out.append((parse_amount(t), True))
        return out
    digits = re.sub(r"[^\d]", "", t)
    if not digits:
        return out
    if col in ("sebenar", "pct"):
        if len(digits) >= 3:
            v = float(digits) / 100.0
            if col == "pct":
                if v <= 2000:
                    out.append((v, False))
            else:
                out.append((v, False))
        if col == "pct" and len(digits) <= 3 and "." not in t:
            out.append((float(digits), False))
    else:
        out.append((float(digits), False))
    # a NUMRE-matching token with unexpected decimals: e.g. asal '9.179.000'
    if col in ("asal", "dipinda") and re.fullmatch(r"[\d.,]+", t):
        v2 = float(re.sub(r"[^\d]", "", t))
        if (v2, False) not in out and (v2, True) not in out:
            out.append((v2, False))
    return out


def norm_digits(tok):
    """Map letter confusions to digits."""
    m = {"O": "0", "o": "0", "Q": "0", "D": "0", "U": "0", "C": "0", "c": "0",
         "l": "1", "I": "1", "i": "1", "!": "1", "|": "1", "t": "1", "L": "1",
         "Z": "2", "z": "2", "e": "2", "E": "8", "A": "4", "S": "5", "s": "5",
         "$": "5", "G": "6", "b": "6", "B": "8", "R": "8", "g": "9", "q": "9",
         "K": "4", "V": "0", "v": "0", "d": "0", "a": "0", "&": "8"}
    return "".join(m.get(ch, ch) for ch in tok if ch.isalnum() or ch in "$&!|")


def ratio(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def best_class(s):
    """Fuzzy-match s against the 5 object classes; return (name, ratio)."""
    s = s.strip()
    best, br = None, 0.0
    for cn in CLASS_NAMES:
        r = ratio(s, cn)
        if r > br:
            best, br = cn, r
    return best, br


def is_jumlah_word(w):
    wl = re.sub(r"[^a-z]", "", w.lower())
    if not wl:
        return False
    return ratio(wl[:8], "jumlah") >= 0.6 and wl[0] in "jdvu"


def is_caps(s):
    alpha = [c for c in s if c.isalpha()]
    if not alpha:
        return False
    return sum(1 for c in alpha if c.isupper()) / len(alpha) >= 0.6


# ------------------------------------------------------------ oracle / priors
ORACLE = []      # [(code, jenis, name, asal, dipinda, sebenar)]
with open("/home/claude/pkkp/warehouse2015/fact_opex_maksud.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        ORACLE.append((r["maksud_code"], r["jenis_bm"], r["maksud_name_bm"],
                       float(r["anggaran_asal_rm"]), float(r["anggaran_dipinda_rm"]),
                       float(r["sebenar_rm"])))
ORACLE_BY_CODE = {o[0]: o for o in ORACLE}

PRIOR_PROG = defaultdict(dict)   # maksud -> {prog_code: name}
PRIOR_AKT = defaultdict(dict)    # (maksud, prog) -> {akt_code: name}
for yr in ("2014", "2016"):
    p = f"/home/claude/pkkp/warehouse{yr}/fact_opex_detail.csv"
    if not os.path.exists(p):
        continue
    for r in csv.DictReader(open(p, encoding="utf-8")):
        mk = r["maksud_code"]
        if r["program_code"] and r["program_name_bm"]:
            PRIOR_PROG[mk].setdefault(r["program_code"], r["program_name_bm"])
        if r["aktiviti_code"] and r["aktiviti_name_bm"]:
            PRIOR_AKT[(mk, r["program_code"])].setdefault(
                r["aktiviti_code"], r["aktiviti_name_bm"])


# ------------------------------------------------------------ page parsing
def page_shift(lines):
    rights = []
    for _t, _b, ws in lines:
        for w in ws:
            if NUMRE.match(w["text"]) and len(w["text"]) > 4 and w["right"] > 1500:
                rights.append(w["right"])
    best, best_n = 0, -1
    for cand in range(-90, 91, 2):
        n = sum(1 for r in rights
                if any(abs(r - (a + cand)) <= 16 for a in TEMPLATE.values()))
        if n > best_n:
            best, best_n = cand, n
    return best


JUNK_LINE = re.compile(
    r"(PENYATA KEWANGAN|bagi tahun berakhir|sambung|saqnug|sarn[bs]|samenanjungan|"
    r"Maksud Perb|Anggaran\s+Se[bh]en|LAMPIRAN)", re.I)


def load_lines(pno):
    words = [w for w in ocrlib.load_words(pno)
             if w["left"] < LABEL_X_MAX and w["right"] > 300 and w["conf"] > -1]
    lines = ocrlib.cluster_lines(words, ytol=16)
    out = []
    for top, bot, ws in lines:
        ws = ocrlib.merge_number_fragments(ws, maxgap=28)
        out.append((top, bot, ws))
    # re-attach orphan lower-baseline pct of boxed rows
    merged = []
    for top, bot, ws in out:
        if (merged and len(ws) == 1 and top - merged[-1][0] < 36
                and ws[0]["right"] > VAL_X_MIN + 900
                and (NUMRE.match(ws[0]["text"]) or DASHRE.match(ws[0]["text"]))):
            pt, pb, pws = merged[-1]
            merged[-1] = (pt, max(pb, bot), pws + ws)
        else:
            merged.append((top, bot, list(ws)))
    return merged


def find_data_band(lines, pno):
    data_top = 940
    data_bot = 4560
    for top, bot, ws in lines:
        raw = " ".join(w["text"] for w in ws)
        if top < 1250 and re.search(r"(Se[bh]e[nm][aes]r|Anggar|A[SN]GG|AGRA|ANITA)", raw):
            data_top = max(data_top, bot + 6)
        if top < 1250:
            vs = [w for w in ws if w["right"] > VAL_X_MIN]
            if len(vs) >= 2 and all(re.fullmatch(r"[RFAP][MmuAaltj!i'\",.]{0,4}[,.!'\"]?|%|o\S{0,2}", w["text"]) for w in vs):
                data_top = max(data_top, bot + 6)
        # footnote zone: 'Nota'-ish start at bottom of page
        if top > 4050:
            w0 = ws[0]["text"] if ws else ""
            if (w0[:4] in ("Nota", "Hala", "Wala", "Mata", "Nofa", "Note", "Kata")
                    or re.match(r"^\(?[a-z]\)?$", w0)) and len(ws) > 3:
                data_bot = min(data_bot, top - 5)
    return data_top, data_bot


# ------------------------------------------------------------- code resolve
def code_reocr(pno, ws_code):
    """Targeted digit re-OCR of a code token bbox."""
    x0 = min(w["left"] for w in ws_code) - 4
    x1 = max(w["right"] for w in ws_code) + 4
    y0 = min(w["top"] for w in ws_code) - 3
    y1 = max(w["bottom"] for w in ws_code) + 3
    key = (f"{pno}k", f"{x0},{y0},{x1},{y1}")
    if key in code_cache:
        return code_cache[key]
    img = get_img(pno)
    crop = img.crop((max(0, x0), max(0, y0), min(img.width, x1), min(img.height, y1)))
    big = crop.resize((crop.width * 4, crop.height * 4), Image.LANCZOS)
    out = tess(big, psm=7, whitelist="0123456789", tag="k").strip().replace(" ", "")
    with _cache_lock:
        code_cache[key] = out
        _kw.writerow([key[0], key[1], out])
    return out


CONF_PAIRS = {("0", "6"), ("0", "9"), ("0", "8"), ("2", "8"), ("3", "8"),
              ("5", "6"), ("5", "9"), ("1", "7"), ("4", "9"), ("1", "4"),
              ("0", "5"), ("2", "3"), ("6", "8"), ("9", "8"), ("3", "5"),
              ("0", "2"), ("1", "2")}


def digit_variants_ok(a, b):
    """True if codes a,b differ only at confusable digit positions."""
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x != y and (x, y) not in CONF_PAIRS and (y, x) not in CONF_PAIRS:
            return False
    return True


# =====================================================================
# PASS 1: structural parse of all pages
# =====================================================================
rows = []          # output rows, 2020-style list layout + meta
cands = []         # per row: {col: set(values), 'strict': {col: set}}
salvage = []
checks = []        # buffered validation rows
pending_pages = [p for p in range(PAGE_LO, PAGE_HI + 1)
                 if not os.path.exists(f"{WORK}/tsv/p-{p:03d}.tsv")]
if pending_pages:
    import time
    print(f"waiting for OCR of pages: {pending_pages}")
    for _ in range(40):
        time.sleep(60)
        pending_pages = [p for p in pending_pages
                         if not os.path.exists(f"{WORK}/tsv/p-{p:03d}.tsv")]
        if not pending_pages:
            break
        print(f"  still waiting: {pending_pages}")
    if pending_pages:
        sys.exit(f"OCR never finished for {pending_pages}")

CLASS_ORDER = {c: i for i, c in enumerate(CLASS_NAMES)}

state = dict(jenis=None, mk_i=-1, maksud=None, maksud_name=None,
             prog=None, prog_name=None, akt=None, akt_name=None, akt_foot=False,
             last_header=None, last_rt=None,
             akt_classes=[], prog_classes=set(), mk_classes=set(),
             jenis_classes={"Tanggungan": set(), "Bekalan": set()},
             run=None, run_type=None, page_valued=False)


def next_maksud():
    return ORACLE[state["mk_i"] + 1] if state["mk_i"] + 1 < len(ORACLE) else None


def class_run_list(scope):
    if scope == "prog":
        cls = state["prog_classes"]
    elif scope == "mk":
        cls = state["mk_classes"]
    elif scope == "jenis":
        cls = state["jenis_classes"][state["jenis"]]
    else:
        cls = state["jenis_classes"]["Tanggungan"] | state["jenis_classes"]["Bekalan"]
    return sorted(cls, key=lambda c: CLASS_ORDER[c])


def start_maksud(nxt):
    state["mk_i"] += 1
    state["maksud"], state["jenis"], state["maksud_name"] = nxt[0], nxt[1], nxt[2]
    state["prog"] = state["prog_name"] = None
    state["akt"] = state["akt_name"] = None
    state["akt_foot"] = False
    state["akt_classes"] = []
    state["prog_classes"] = set()
    state["mk_classes"] = set()
    state["run"] = state["run_type"] = None
    state["last_header"] = "maksud"


def classify_header(label, ws_lab, pno, top, hdr_foot=False):
    """Handle a no-value line; update state."""
    s = label.strip()
    if not s:
        return
    # jenis header
    if re.match(r"^P[EF3]R[BS8][EF3]LAN", s) and ratio(s[:24], "PERBELANJAAN TANGGUNGAN") > 0.55:
        if "TANG" in s.upper().replace("7", "T") or ratio(s, "PERBELANJAAN TANGGUNGAN") > ratio(s, "PERBELANJAAN BEKALAN"):
            state["jenis"] = "Tanggungan"
        else:
            state["jenis"] = "Bekalan"
        return
    # maksud header: T./B. + 2 digits, or fuzzy-name of current/next maksud
    m = re.match(r"^[\"'*]?\s*([TB8E7F])\s*[.,;:_]?\s*['`]?(\d{1,2})\b[.,]?\s*(.*)$", s)
    if m and len(m.group(3)) >= 3:
        num = int(m.group(2))
        cur = ORACLE[state["mk_i"]] if state["mk_i"] >= 0 else None
        nxt = next_maksud()
        name_part = m.group(3)
        if cur and int(cur[0][2:]) == num and cur[0][0] == ("T" if m.group(1) in "TF7" else "B") \
                and ratio(name_part[:len(cur[2]) + 4], cur[2]) > 0.35:
            state["last_header"] = "maksud"
            return     # (SAMB.) repeat of current maksud
        if nxt:
            exp_num = int(nxt[0][2:])
            r_nxt = ratio(name_part[: len(nxt[2]) + 4], nxt[2])
            r_cur = ratio(name_part[: len(cur[2]) + 4], cur[2]) if cur else 0
            if (num == exp_num and r_nxt >= 0.3) or (r_nxt >= 0.55 and r_nxt > r_cur):
                start_maksud(nxt)
                if num != exp_num:
                    salvage.append(f"maksud header p{pno} read '{s[:40]}' -> {nxt[0]} (name match {r_nxt:.2f})")
                return
        if cur and ratio(name_part[: len(cur[2]) + 4], cur[2]) >= 0.4:
            state["last_header"] = "maksud"
            return
        salvage.append(f"UNMATCHED maksud-like header p{pno} y{top}: '{s[:60]}'")
        return
    # program / aktiviti header: code region = words starting left of 470+shift
    code_ws = [w for w in ws_lab if w["left"] < CODE_LEFT_MAX + 20 + CUR_SHIFT]
    name_ws = [w for w in ws_lab if w["left"] >= CODE_LEFT_MAX + 20 + CUR_SHIFT]
    code_tok = "".join(w["text"] for w in code_ws)
    name = " ".join(w["text"] for w in name_ws).strip()
    foot = hdr_foot or bool(re.match(r"^[\"'*™«+]", code_tok))
    code_tok = re.sub(r"[\"'*™«+()\[\]{}.,]", "", code_tok)
    nd = norm_digits(code_tok)
    if code_ws and name and 3 <= len(code_tok) <= 9:
        caps = is_caps(name)
        code_read = code_tok if re.fullmatch(r"\d{6}", code_tok) else code_reocr(pno, code_ws)
        if not re.fullmatch(r"\d{6}", code_read):
            code_read = nd[:6].ljust(6, "0") if nd else ""
        if caps or (code_read.endswith("0000") and not re.search(r"[a-z]{3}", name)):
            resolve_program(code_read, name, pno, foot)
        else:
            resolve_aktiviti(code_read, name, pno, foot)
        return
    # wrapped header continuation
    if state["last_header"] and len(s) < 80 and not re.search(r"[\d,]{6,}", s):
        key = {"maksud": "maksud_name", "program": "prog_name",
               "aktiviti": "akt_name"}.get(state["last_header"])
        if key and key != "maksud_name" and state.get(key) is not None:
            state[key] = (state[key] + " " + s).strip()
    return


def resolve_program(code_read, name, pno, foot):
    mk = state["maksud"]
    prior = PRIOR_PROG.get(mk, {})
    prev = state["prog"]
    # repeat of current program header ((SAMB.) in the page-top block only)
    if prev and not state["page_valued"] and (
            (state["prog_name"] and ratio(name, state["prog_name"]) >= 0.45)
            or (re.fullmatch(r"\d{6}", code_read) and code_read == prev)):
        state["last_header"] = "program"
        return
    if prev and re.fullmatch(r"\d{6}", code_read) and code_read == prev \
            and state["prog_name"] and ratio(name, state["prog_name"]) >= 0.6:
        state["last_header"] = "program"
        return
    cand = None
    if re.fullmatch(r"\d{6}", code_read) and code_read.endswith("0000") \
            and 1 <= int(code_read[:2]) <= 45 \
            and (prev is None or int(code_read[:2]) > int(prev[:2])):
        cand = code_read
    best_p, best_r = None, 0.0
    for pc, pn in prior.items():
        r = ratio(name, pn)
        if r > best_r:
            best_p, best_r = pc, r
    if best_r >= 0.62 and (prev is None or int(best_p[:2]) > int(prev[:2])) \
            and (cand is None or digit_variants_ok(cand, best_p) or cand == best_p):
        if cand is not None and cand != best_p:
            salvage.append(f"program code p{pno}: read {cand} -> {best_p} (prior-year name match '{name[:30]}' {best_r:.2f})")
        cand = best_p
        name = prior[best_p]
    if cand is None:
        nd = norm_digits(code_read)[:2]
        if nd.isdigit() and (prev is None or 0 < int(nd) - int(prev[:2]) <= 12) and int(nd) >= 1:
            cand = nd + "0000"
        else:
            cand = (f"{int(prev[:2])+1:02d}0000" if prev else "010000")
            salvage.append(f"program code p{pno} unreadable ('{code_read}') -> inferred {cand} (seq)")
    state["prog"], state["prog_name"] = cand, name
    state["akt"] = state["akt_name"] = None
    state["akt_foot"] = False
    state["akt_classes"] = []
    state["prog_classes"] = set()
    state["run"] = state["run_type"] = None
    state["last_header"] = "program"


def resolve_aktiviti(code_read, name, pno, foot):
    mk, prog = state["maksud"], state["prog"]
    if prog is None:
        nd = norm_digits(code_read)
        prog = (nd[:2] if len(nd) >= 2 and nd[:2].isdigit() and nd[:2] != "00" else "01") + "0000"
        salvage.append(f"missing program header before aktiviti p{pno} '{name[:30]}': program {prog} inferred")
        state["prog"], state["prog_name"] = prog, None
        state["prog_classes"] = set()
    # repeat of current aktiviti ((SAMB.) in the page-top block only)
    prev = state["akt"]
    if prev and not state["page_valued"] and state["akt_name"] \
            and ratio(name, state["akt_name"]) >= 0.45:
        state["last_header"] = "aktiviti"
        state["akt_foot"] = state["akt_foot"] or foot
        return
    prior = PRIOR_AKT.get((mk, prog), {})
    cand = None
    if re.fullmatch(r"\d{6}", code_read) and code_read[:2] == prog[:2] and code_read.endswith("00") \
            and code_read[2:4] != "00" \
            and (prev is None or prev[:2] != prog[:2] or int(code_read[2:4]) > int(prev[2:4])):
        cand = code_read
    best_p, best_r, second_r = None, 0.0, 0.0
    for pc, pn in prior.items():
        r = ratio(name, pn)
        if r > best_r:
            best_p, best_r, second_r = pc, r, best_r
        elif r > second_r:
            second_r = r
    if best_r >= 0.62 and best_r - second_r >= 0.05 \
            and (prev is None or prev[:2] != prog[:2] or int(best_p[2:4]) > int(prev[2:4])) \
            and (cand is None or cand == best_p or digit_variants_ok(cand, best_p)):
        if cand is not None and cand != best_p:
            salvage.append(f"aktiviti code p{pno}: read {cand} -> {best_p} (prior-year name match '{name[:30]}' {best_r:.2f})")
        cand = best_p
        name = prior[best_p]
    if cand is None:
        nd = norm_digits(code_read)
        yy_prev = int(prev[2:4]) if prev and prev[:2] == prog[:2] else 0
        if len(nd) >= 4 and nd[:2] == prog[:2] and nd[2:4].isdigit() \
                and yy_prev < int(nd[2:4]) <= yy_prev + 12 and nd[2:4] != "00":
            cand = nd[:4] + "00"
        else:
            cand = f"{prog[:2]}{yy_prev + 1:02d}00"
            salvage.append(f"aktiviti code p{pno} unreadable ('{code_read}') -> inferred {cand} (seq)")
    state["akt"], state["akt_name"], state["akt_foot"] = cand, name, foot
    state["akt_classes"] = []
    state["run"] = state["run_type"] = None
    state["last_header"] = "aktiviti"


def scrub_samb(label):
    label = re.sub(r"\s*[-–—~=_]{0,3}\s*[({\[][^)}\]]{0,9}[)}\]!.,_]{0,3}\s*$", "", label)
    label = re.sub(r"\s*[-–—~=_]{1,3}\s*\(?\s*S[AV]?[MN][BE8][^)]{0,4}$", "", label, flags=re.I)
    return label.strip()


all_pages = list(range(PAGE_LO, PAGE_HI + 1))
for pno in all_pages:
    lines = load_lines(pno)
    joined = " ".join(w["text"] for _t, _b, ws in lines for w in ws)
    shift = page_shift(lines)
    CUR_SHIFT = shift
    state["page_valued"] = False
    anchors = {c: TEMPLATE[c] + shift for c in COLS}
    val_x_min = VAL_X_MIN + shift
    data_top, data_bot = find_data_band(lines, pno)
    printed = pno - ocrlib.PAGE_OFFSET
    for top, bot, ws in lines:
        if top < data_top or top > data_bot:
            continue
        raw_line = " ".join(w["text"] for w in ws)
        if JUNK_LINE.search(raw_line) and not any(
                NUMRE.match(w["text"]) and len(w["text"]) > 6 for w in ws):
            continue
        labws = [w for w in ws if w["right"] < val_x_min]
        valws = [w for w in ws if w["right"] >= val_x_min]
        label = " ".join(w["text"] for w in labws).strip()
        hdr_foot = bool(re.search(r"[({\[]\s*[a-h]\s*[)}\]]\s*$", label))
        label = scrub_samb(label)
        label = re.sub(r"^[.,'`~\-–—°·]+\s*", "", label).strip()
        # value tokens near anchors
        vals = {}          # col -> raw token (page TSV reading)
        foot = False
        garbled = False
        leftover_alpha = []
        for w in valws:
            t = w["text"]
            if t.startswith("*") or t.startswith('"'):
                foot = True
            tt = t.replace("*", "")
            ci = min(COLS, key=lambda c: abs(anchors[c] - w["right"]))
            near = abs(anchors[ci] - w["right"]) <= COL_TOL
            if NUMRE.match(tt):
                if near and ci not in vals:
                    vals[ci] = tt
                elif not near:
                    garbled = True
            elif DASHRE.match(tt):
                if near:
                    vals.setdefault(ci, "–")
            elif re.fullmatch(r"[A-Za-z()&.,'\-]{2,}", t):
                leftover_alpha.append(t)
            else:
                garbled = True
        has_vals = bool(vals) or any(
            NUMRE.match(w["text"].replace("*", "")) or DASHRE.match(w["text"])
            for w in valws)
        if leftover_alpha and not has_vals:
            label = (label + " " + " ".join(leftover_alpha)).strip()
            label = scrub_samb(label)
        if len(ws) <= 2 and re.fullmatch(r"[\d ]{1,4}", raw_line.strip()):
            continue        # printed page number
        if not has_vals:
            # header/continuation; but check for object-like rows whose values
            # OCR missed entirely (ink test)
            first_left = labws[0]["left"] if labws else 9999
            bc, br = best_class(re.sub(r"^\S+\s+", "", label) if first_left < CODE_LEFT_MAX else label)
            looks_obj = br >= 0.62 or (is_jumlah_word(label.split()[0]) if label.split() else False)
            if looks_obj:
                dk, wi, hi = ocrlib.dark_stats(pno, (val_x_min, top - 2, anchors["pct"] + 40, bot + 2))
                if dk > 400:
                    has_vals = True       # fall through to valued-row handling
            if not has_vals:
                classify_header(label, labws, pno, top, hdr_foot)
                continue
        if not label:
            # label OCR failed: re-OCR label band
            img = get_img(pno)
            crop = img.crop((330, max(0, top - 3), int(val_x_min) - 10, min(img.height, bot + 3)))
            big = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
            lab_txt = tess(big, psm=7, whitelist=None, tag="lab").strip()
            lab_txt = re.sub(r"\s+", " ", lab_txt).strip()
            if lab_txt:
                salvage.append(f"label re-OCR p{pno} y{top}: -> '{lab_txt[:50]}'")
                label = scrub_samb(lab_txt)
            else:
                continue
        state["last_header"] = None
        # ------------- classify valued row -------------
        def classify_valued(s, labws, foot):
            """Return (rt, obj_class, obj_code, lab_out, foot)."""
            code_ws = [w for w in labws if w["left"] < CODE_LEFT_MAX + 20 + CUR_SHIFT]
            name_str = " ".join(w["text"] for w in labws
                                if w["left"] >= CODE_LEFT_MAX + 20 + CUR_SHIFT).strip()
            code_tok = "".join(w["text"] for w in code_ws)
            if re.match(r"^[\"'*™«+]", code_tok):
                foot = True
            toks = s.split()
            # --- object row: leading code region + class name ---
            if code_ws and name_str:
                bc, br = best_class(scrub_samb(name_str))
                nd = norm_digits(re.sub(r"[\"'*™«+()\[\]{}.,]", "", code_tok))
                if br >= 0.45 or (len(nd) == 5 and nd in OBJ_CLASSES and br >= 0.3):
                    if br < 0.45:
                        bc = OBJ_CLASSES[nd]
                    return "object_aktiviti", bc, CLASS_CODE[bc], f"{CLASS_CODE[bc]} {bc}", foot
                return None, None, None, s, foot
            # --- no code region ---
            w1 = toks[0] if toks else ""
            wl = re.sub(r"[^A-Za-z]", "", w1).lower()
            jum_r = ratio(wl[:8], "jumlah")
            jumish = (jum_r >= 0.45 and wl[:1] in "jdvu") or wl[:3] == "jum" or jum_r >= 0.6
            rest = " ".join(toks[1:]) if jumish else s
            rest_nd = norm_digits(re.sub(r"[\s()\[\]{}.,'\"]", "", rest))
            # drop numeric-ish trailing tokens for class matching
            rtoks = rest.split()
            while rtoks and (sum(ch.isdigit() for ch in rtoks[-1]) >= 1
                             or len(re.sub(r"[^A-Za-z]", "", rtoks[-1])) <= 1):
                rtoks.pop()
            rest_alpha = " ".join(rtoks)
            _nd_dig = sum(ch.isdigit() for ch in rest_nd)
            digitish = (4 <= len(rest_nd) <= 8 and not re.search(r"\d,\d{3}", rest)
                        and _nd_dig >= 0.7 * max(len(rest_nd), 1) and _nd_dig >= 3)
            capsline = is_caps(rest) if rest else False
            # grand / jenis / maksud totals (ALL CAPS)
            if jumish and rest and capsline and not digitish:
                r_tang = ratio(rest, "PERBELANJAAN TANGGUNGAN")
                r_bek = ratio(rest, "PERBELANJAAN BEKALAN")
                r_men = ratio(rest, "PERBELANJAAN MENGURUS")
                r_mk = ratio(rest, (state["maksud_name"] or "").upper())
                bestr = max(r_tang, r_bek, r_men, r_mk)
                if bestr >= 0.4 and bestr in (r_tang, r_bek) and re.search(r"PERB|PERS|PER8|FERB", rest.upper()):
                    jn = "TANGGUNGAN" if r_tang >= r_bek else "BEKALAN"
                    # MENGURUS beats jenis when it matches the tail
                    if r_men >= bestr and re.search(r"MENG|MEHG|MFNG|WENG", rest.upper()):
                        return "jumlah_besar", None, None, "JUMLAH PERBELANJAAN MENGURUS", foot
                    return "jumlah_jenis", None, None, f"JUMLAH PERBELANJAAN {jn}", foot
                if bestr >= 0.4 and bestr == r_men and re.search(r"MENG|MEHG|MFNG|WENG", rest.upper()):
                    return "jumlah_besar", None, None, "JUMLAH PERBELANJAAN MENGURUS", foot
                if r_mk >= 0.35:
                    return "jumlah_maksud", None, None, state["maksud_name"], foot
            # class-total rows: 'Jumlah <class>'
            if jumish and rest_alpha and not digitish:
                bc, br = best_class(scrub_samb(rest_alpha))
                if br >= 0.45:
                    return "jumlah_objek_maksud", bc, None, f"Jumlah {bc}", foot
            # jumlah aktiviti / program (code after Jumlah, or garbled code)
            if (jumish and (digitish or not rest)) or (not jumish and digitish and len(wl) <= 8):
                if state["run_type"] == "prog" or state["last_rt"] == "object_program":
                    rt = "jumlah_program"
                    lab = f"Jumlah {state['prog']}"
                    want = state["prog"]
                else:
                    rt = "jumlah_aktiviti"
                    lab = f"Jumlah {state['akt']}"
                    want = state["akt"]
                if re.fullmatch(r"\d{6}", rest_nd or "") and want and rest_nd != want \
                        and not digit_variants_ok(rest_nd, want):
                    salvage.append(f"NOTE jumlah code mismatch p{pno}: read '{rest[:16]}'({rest_nd}) "
                                   f"vs context {want} [{rt}]")
                return rt, None, None, lab, foot
            # bare italic class row
            bc, br = best_class(scrub_samb(s))
            if br >= 0.5:
                return "object_program", bc, None, bc, foot
            # caps maksud total without recognizable JUMLAH word
            if is_caps(s) and ratio(s, "JUMLAH " + (state["maksud_name"] or "").upper()) >= 0.5:
                return "jumlah_maksud", None, None, state["maksud_name"], foot
            return None, None, None, s, foot

        rt, obj_class, obj_code, lab_out, foot = classify_valued(label, labws, foot)
        if rt is None:
            # retry with a targeted label re-OCR
            img = get_img(pno)
            crop = img.crop((330, max(0, top - 3), int(val_x_min) - 10, min(img.height, bot + 3)))
            big = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
            lab2 = tess(big, psm=7, whitelist=None, tag="lab").strip()
            lab2 = scrub_samb(re.sub(r"\s+", " ", lab2).strip())
            if lab2 and lab2 != label:
                # rebuild pseudo word-list with x from proportional split
                pseudo = []
                # estimate: single word occupies label band; give left from crop OCR? keep simple:
                # treat as no-code-region unless original had words left of threshold
                rt, obj_class, obj_code, lab_out, foot = classify_valued(
                    lab2, labws if labws else [], foot)
                if rt:
                    salvage.append(f"label re-OCR reclass p{pno} y{top}: '{label[:30]}' -> '{lab2[:40]}' [{rt}]")
                    label = lab2
        if rt is None:
            # context expectation fallback
            if state["run"] is not None and state["run"]:
                bc = state["run"][0]
                if state["run_type"] == "prog":
                    rt, obj_class, lab_out = "object_program", bc, bc
                else:
                    rt, obj_class, lab_out = "jumlah_objek_maksud", bc, f"Jumlah {bc}"
                salvage.append(f"context-inferred class row p{pno} y{top}: '{label[:30]}' -> {rt} {bc}")
            elif state["last_rt"] == "jumlah_aktiviti" and state["prog_classes"]:
                bc = class_run_list("prog")[0]
                rt, obj_class, lab_out = "object_program", bc, bc
                salvage.append(f"context-inferred first program-class row p{pno} y{top}: '{label[:30]}' -> {bc}")
        if rt is None:
            # run-start context inference
            lr = state["last_rt"]
            if lr == "jumlah_program" and state["mk_classes"]:
                state["run_type"], state["run"] = "mk", class_run_list("mk")
                bc = state["run"][0]
                rt, obj_class, lab_out = "jumlah_objek_maksud", bc, f"Jumlah {bc}"
                salvage.append(f"context-inferred maksud class row p{pno} y{top}: '{label[:30]}' -> {bc}")
            elif lr == "jumlah_maksud" and state["jenis"] in state["jenis_classes"]:
                state["run_type"], state["run"] = "jenis", class_run_list("jenis")
                bc = state["run"][0]
                rt, obj_class, lab_out = "jumlah_objek_maksud", bc, f"Jumlah {bc}"
                salvage.append(f"context-inferred jenis class row p{pno} y{top}: '{label[:30]}' -> {bc}")
            elif lr == "jumlah_jenis":
                state["run_type"], state["run"] = "kes", class_run_list("kes")
                bc = state["run"][0]
                rt, obj_class, lab_out = "jumlah_objek_maksud", bc, f"Jumlah {bc}"
                salvage.append(f"context-inferred keseluruhan class row p{pno} y{top}: '{label[:30]}' -> {bc}")
        if rt is None:
            rt = "unclassified"
        # ------------- run bookkeeping -------------
        if rt == "object_aktiviti" and state["akt"] is None:
            # aktiviti header line missing/unreadable in OCR
            prog = state["prog"] or "010000"
            prior = PRIOR_AKT.get((state["maksud"], prog), {})
            if len(prior) == 1:
                (ac, an), = prior.items()
                state["akt"], state["akt_name"] = ac, an
                salvage.append(f"aktiviti header missing p{pno} ({state['maksud']}): "
                               f"inferred {ac} '{str(an)[:30]}' from prior year")
            else:
                state["akt"] = prog[:2] + "0100"
                state["akt_name"] = None
                salvage.append(f"aktiviti header missing p{pno} ({state['maksud']}): "
                               f"inferred {state['akt']} (seq)")
            state["akt_classes"] = []
        if rt == "object_aktiviti":
            state["akt_classes"].append(obj_class)
            state["prog_classes"].add(obj_class)
            state["mk_classes"].add(obj_class)
            if state["jenis"] in state["jenis_classes"]:
                state["jenis_classes"][state["jenis"]].add(obj_class)
            state["run"] = state["run_type"] = None
        elif rt == "object_program":
            if state["run_type"] != "prog":
                state["run"] = class_run_list("prog")
                state["run_type"] = "prog"
            if obj_class in state["run"]:
                while state["run"] and state["run"][0] != obj_class:
                    state["run"].pop(0)
                if state["run"]:
                    state["run"].pop(0)
        elif rt == "jumlah_objek_maksud":
            if state["run_type"] not in ("mk", "jenis", "kes"):
                if state["last_rt"] == "jumlah_jenis":
                    state["run_type"] = "kes"
                    state["run"] = class_run_list("kes")
                elif state["last_rt"] == "jumlah_maksud":
                    state["run_type"] = "jenis"
                    state["run"] = class_run_list("jenis")
                else:
                    state["run_type"] = "mk"
                    state["run"] = class_run_list("mk")
            if obj_class in (state["run"] or []):
                while state["run"] and state["run"][0] != obj_class:
                    state["run"].pop(0)
                if state["run"]:
                    state["run"].pop(0)
        elif rt in ("jumlah_program", "jumlah_maksud", "jumlah_jenis", "jumlah_besar", "jumlah_aktiviti"):
            state["run"] = state["run_type"] = None
        state["last_rt"] = rt
        if rt in ("object_aktiviti", "jumlah_aktiviti") and state["akt_foot"]:
            foot = True
        state["page_valued"] = True
        rows.append([
            state["jenis"], state["maksud"], state["maksud_name"],
            state["prog"], state["prog_name"], state["akt"], state["akt_name"],
            obj_code, obj_class, rt, lab_out, ocrlib.YEAR,
            None, None, None, None, None, None, None, foot,
            SRC, pno, printed, STMT, garbled,
            dict(pno=pno, top=top, bot=bot, shift=shift, tsv=dict(vals)),
        ])
        cands.append({c: {} for c in COLS})

print(f"pass1: {len(rows)} valued rows")

# =====================================================================
# PASS 2: value resolution -- row-band re-OCR of every row + candidates
# =====================================================================
IDX = dict(asal=12, dipinda=15, sebenar=16, pct=17)


def add_cand(i, col, val, strict, src):
    if val is None and col != "pct":
        return
    d = cands[i][col]
    key = round(val, 2) if val is not None else None
    if key not in d:
        d[key] = dict(strict=strict, srcs=set())
    d[key]["strict"] = d[key]["strict"] or strict
    d[key]["srcs"].add(src)


def prefetch_rowbands(idxs, clean=True):
    def work(i):
        m = rows[i][25]
        rowband_ocr(m["pno"], m["top"], m["bot"], m["shift"], clean=clean)
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(work, idxs))


print("row-band OCR (clean + raw render) of all rows...")
prefetch_rowbands(range(len(rows)), clean=True)
prefetch_rowbands(range(len(rows)), clean=False)

for i, r in enumerate(rows):
    m = r[25]
    anchors = {c: TEMPLATE[c] + m["shift"] for c in COLS}
    # source 1: page TSV
    for c, tok in m["tsv"].items():
        for v, strict in cands_from_token(c, tok):
            add_cand(i, c, v, strict, "tsv")
    # sources 2+3: row-band re-OCR of the rule-stripped AND the raw render
    # (rule-stripping damages digits crossing the box rules of subtotal rows,
    #  so the raw render is the better read there)
    for src_name, cl in (("rb", True), ("raw", False)):
        for tok, rx in rowband_ocr(m["pno"], m["top"], m["bot"], m["shift"], clean=cl):
            ci = min(COLS, key=lambda c: abs(anchors[c] - rx))
            if abs(anchors[ci] - rx) > COL_TOL + 10:
                continue
            for v, strict in cands_from_token(ci, tok):
                add_cand(i, ci, v, strict, src_name)


def filt_vals(d):
    """Filter a cell's candidate dict: drop values whose digit string is a
    proper prefix/suffix (>=2 digits shorter) of another candidate's -- these
    are truncated reads (crop cut / box-rule damage), never real analogues."""
    keys = [v for v in d if v is not None]
    digs = {}
    for v in keys:
        digs[v] = re.sub(r"[^\d]", "", f"{v:.2f}").lstrip("0")
    drop = set()
    for v in keys:
        for w in keys:
            if v == w or w in drop:
                continue
            dv, dw = digs[v], digs[w]
            if dv and len(dw) >= len(dv) + 3 and (dw.endswith(dv) or dw.startswith(dv)):
                drop.add(v)
                break
    return {v: i for v, i in d.items() if v not in drop}


# initial settle: strict two-source agreement > strict raw > strict tsv > weak
missing_cells = []
for i, r in enumerate(rows):
    for c in COLS:
        d = filt_vals(cands[i][c]) if c != "pct" else cands[i][c]
        pick = None
        stricts = [(v, info) for v, info in d.items() if info["strict"]]
        if stricts:
            both = [v for v, info in stricts if len(info["srcs"]) >= 2]
            if both:
                pick = both[0]
            else:
                raws = [v for v, info in stricts if "raw" in info["srcs"]]
                tsvs = [v for v, info in stricts if "tsv" in info["srcs"]]
                pick = raws[0] if raws else (tsvs[0] if tsvs else stricts[0][0])
        elif d:
            pick = max(d.items(), key=lambda kv: len(kv[1]["srcs"]))[0]
        else:
            missing_cells.append((i, c))
        r[IDX[c]] = pick if not (c == "pct" and pick is None) else None
        if c == "pct" and pick is not None and pick == 0.0 and not d:
            r[IDX[c]] = None

print(f"cells with no candidate at all: {len(missing_cells)}; filling via cell_ocr")


PREV_COL = {"asal": None, "dipinda": "asal", "sebenar": "dipinda", "pct": "sebenar"}


def cell_boxes(m, c):
    x1 = TEMPLATE[c] + m["shift"] + 8
    x0 = x1 - (290 if c != "pct" else 210)
    pc = PREV_COL[c]
    wide = (TEMPLATE[pc] + m["shift"] + 12) if pc else (VAL_X_MIN + m["shift"] - 60)
    return (x0, m["top"], x1, m["bot"]), wide


def fill_cell(i, c):
    m = rows[i][25]
    box, wide = cell_boxes(m, c)
    tok = cell_ocr(m["pno"], box, wide_x0=wide)
    if tok in ("",) or not FMT[c].match(tok.replace("*", "").replace(" ", "").strip()):
        tok2 = cell_ocr(m["pno"], box, clean=False, wide_x0=wide)
        if tok2 and (tok in ("", "–") or FMT[c].match(tok2.replace("*", "").strip())):
            return tok2
    return tok


def apply_fill(i, c, tok):
    r = rows[i]
    if tok == "":
        r[IDX[c]] = None if c == "pct" else 0.0
        return
    if tok == "–":
        r[IDX[c]] = None if c == "pct" else 0.0
        add_cand(i, c, 0.0 if c != "pct" else None, True, "cell")
        return
    got = cands_from_token(c, tok)
    for v, strict in got:
        add_cand(i, c, v, strict, "cell")
    stricts = [v for v, s in got if s]
    if stricts:
        r[IDX[c]] = stricts[0]
    elif got:
        r[IDX[c]] = got[0][0]
    else:
        r[IDX[c]] = None if c == "pct" else 0.0


with ThreadPoolExecutor(max_workers=3) as ex:
    toks = list(ex.map(lambda ic: fill_cell(*ic), missing_cells))
for (i, c), tok in zip(missing_cells, toks):
    apply_fill(i, c, tok)

# =====================================================================
# PASS 3: pct identity per row -- candidate-combination arbitration
# =====================================================================
def pct_bad(r):
    d, s, p = r[IDX["dipinda"]], r[IDX["sebenar"]], r[IDX["pct"]]
    if p is None or not d:
        return False
    return abs(s / d * 100 - p) > 0.6


def identity_settle(i):
    """Try candidate combos for (dipinda, sebenar, pct) to satisfy identity."""
    r = rows[i]
    dset = list(filt_vals(cands[i]["dipinda"]))[:5] or [r[IDX["dipinda"]]]
    sset = list(filt_vals(cands[i]["sebenar"]))[:5] or [r[IDX["sebenar"]]]
    pset = list(cands[i]["pct"].keys())[:5] or [r[IDX["pct"]]]
    good = []
    for d in dset:
        for sv in sset:
            for p in pset:
                if d is None or sv is None or p is None or not d:
                    continue
                if abs(sv / d * 100 - p) <= 0.6:
                    good.append((d, sv, p))
    if not good:
        return False
    dv = {g[0] for g in good}
    svv = {g[1] for g in good}
    pv = {g[2] for g in good}
    changed = False
    if len(dv) == 1 and next(iter(dv)) != r[IDX["dipinda"]]:
        r[IDX["dipinda"]] = next(iter(dv)); changed = True
    if len(svv) == 1 and next(iter(svv)) != r[IDX["sebenar"]]:
        r[IDX["sebenar"]] = next(iter(svv)); changed = True
    if len(pv) == 1 and next(iter(pv)) != r[IDX["pct"]]:
        r[IDX["pct"]] = next(iter(pv)); changed = True
    return changed


n_id_fix = 0
for i, r in enumerate(rows):
    if pct_bad(r):
        if identity_settle(i):
            n_id_fix += 1
print(f"identity-based candidate settles: {n_id_fix}; rows still failing pct: "
      f"{sum(1 for r in rows if pct_bad(r))}")

# rows still failing: re-OCR each cell individually (clean + raw render)
still = [i for i, r in enumerate(rows) if pct_bad(r)]
print(f"targeted cell re-OCR for {len(still)} pct-failing rows")


def deep_reocr_row(i):
    m = rows[i][25]
    for c in COLS:
        box, wide = cell_boxes(m, c)
        for cl, srcn in ((True, "cell"), (False, "cellraw")):
            tok = cell_ocr(m["pno"], box, clean=cl, wide_x0=wide)
            for v, strict in cands_from_token(c, tok):
                add_cand(i, c, v, strict, srcn)


with ThreadPoolExecutor(max_workers=2) as ex:
    list(ex.map(deep_reocr_row, still))
n2 = 0
for i in still:
    if pct_bad(rows[i]) and identity_settle(i):
        n2 += 1
print(f"after deep re-OCR: {n2} more settles; rows failing pct: "
      f"{sum(1 for r in rows if pct_bad(r))}")

# =====================================================================
# post-classification fixups (as 2020)
# =====================================================================
# 'Jumlah <class>' runs immediately before jumlah_program are program-level
run_start = None
for i in range(len(rows) + 1):
    if i < len(rows) and rows[i][9] == "jumlah_objek_maksud":
        if run_start is None:
            run_start = i
        continue
    if run_start is not None:
        if i < len(rows) and rows[i][9] == "jumlah_program":
            for j in range(run_start, i):
                rows[j][9] = "object_program"
        run_start = None

# jenis/keseluruhan class-total relabel (tolerate members misread as
# object_program when the italic 'Jumlah' word garbled away)
for i, r in enumerate(rows):
    if r[9] in ("jumlah_jenis", "jumlah_besar"):
        newrt = "jumlah_objek_jenis" if r[9] == "jumlah_jenis" else "jumlah_objek_keseluruhan"
        j = i - 1
        n = 0
        while j >= 0 and rows[j][9] in ("jumlah_objek_maksud", "object_program") and n < 5:
            rows[j][9] = newrt
            rows[j][10] = f"Jumlah {rows[j][8]}"
            j -= 1
            n += 1

# =====================================================================
# PASS 4: constraint solver (2020-style) with candidate arbitration
# =====================================================================
NOTA5B = {o[0]: (o[3], o[4], o[5]) for o in ORACLE}


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
    return f"{v:,.2f}" if v is not None else "nil"


def build_constraints():
    cons = []
    ag = defaultdict(lambda: defaultdict(list))
    for j, r in enumerate(rows):
        rt, mk, pg, ak, cls = r[9], r[1], r[3], r[5], (r[8] or "").strip()
        jn = r[0]
        if rt == "object_aktiviti":
            ag[("akt", mk, pg, ak)]["m"].append(j)
            ag[("pobj", mk, pg, cls)]["m"].append(j)
            ag[("omaks", mk, cls)]["m"].append(j)
            ag[("ojenis", jn, cls)]["m"].append(j)
            ag[("okes", cls)]["m"].append(j)
        elif rt == "jumlah_aktiviti":
            ag[("akt", mk, pg, ak)]["t"].append(j)
            ag[("prog", mk, pg)]["m"].append(j)
        elif rt == "jumlah_program":
            ag[("prog", mk, pg)]["t"].append(j)
            ag[("maks", mk)]["m"].append(j)
        elif rt == "object_program":
            ag[("pobj", mk, pg, cls)]["t"].append(j)
        elif rt == "jumlah_objek_maksud":
            ag[("omaks", mk, cls)]["t"].append(j)
        elif rt == "jumlah_maksud":
            ag[("maks", mk)]["t"].append(j)
            ag[("jenis", jn)]["m"].append(j)
        elif rt == "jumlah_objek_jenis":
            ag[("ojenis", jn, cls)]["t"].append(j)
        elif rt == "jumlah_jenis":
            ag[("jenis", jn)]["t"].append(j)
            ag[("besar",)]["m"].append(j)
        elif rt == "jumlah_objek_keseluruhan":
            ag[("okes", cls)]["t"].append(j)
        elif rt == "jumlah_besar":
            ag[("besar",)]["t"].append(j)
    for key, d in ag.items():
        if d["t"] and d["m"]:
            for c in ("asal", "dipinda", "sebenar"):
                cons.append((f"{key}", [(j, c, 1) for j in d["m"]]
                             + [(j, c, -1) for j in d["t"]], 0.0, c))
    for j, r in enumerate(rows):
        if r[9] == "jumlah_maksud" and r[1] in NOTA5B:
            a5, d5, s5 = NOTA5B[r[1]]
            cons.append((f"nota5b:{r[1]}", [(j, "asal", 1)], a5, "asal"))
            cons.append((f"nota5b:{r[1]}", [(j, "dipinda", 1)], d5, "dipinda"))
            cons.append((f"nota5b:{r[1]}s", [(j, "sebenar", 1)], s5, "sebenar"))
    if DEV:   # drop groups touching the (possibly truncated) range edges
        edge = {j for j, r in enumerate(rows) if r[21] in (PAGE_LO, PAGE_HI)}
        cons = [c for c in cons if not (set(j for j, _c, _s in c[1]) & edge)
                and not c[0].startswith(("('jenis", "('besar", "('ojenis", "('okes", "nota5b"))]
    return cons


# eye-verified fixes for cells the constraints contest beyond digit variants:
# (pdf_page, label, col, aktiviti_code) -> (value, note)
MANUAL_OVERRIDES = {
}
contested_seen = set()
contested_list = []
auto_fixes = 0
manual_fixes = 0


def soft_confirmed():
    """Cells corroborated by the row's own printed pct identity."""
    soft = set()
    for j, r in enumerate(rows):
        if r[IDX["pct"]] is not None and r[IDX["dipinda"]] and not pct_bad(r):
            soft.add((j, "dipinda"))
            soft.add((j, "sebenar"))
    return soft


def fam(name):
    m = re.match(r"\(?'?(\w+)", name)
    return m.group(1) if m else name


def solve_round(final=False):
    global auto_fixes, manual_fixes
    cons = build_constraints()
    stat = []
    for name, cells, const, col in cons:
        tol = _tol_of(name)
        s = sum(sign * (rows[j][IDX[c]] or 0.0) for j, c, sign in cells) - const
        stat.append((abs(s) <= tol, s))
    confirmed = set()
    for (ok, _s), (name, cells, const, col) in zip(stat, cons):
        if ok:
            for j, c, sign in cells:
                confirmed.add((j, c))
    # phase A: collect implied values from constraints with a unique
    # unconfirmed cell
    implied = defaultdict(list)     # (j, c) -> [(name, value)]
    for (ok, s), (name, cells, const, col) in zip(stat, cons):
        if ok:
            continue
        unconf = [(j, c, sign) for j, c, sign in cells if (j, c) not in confirmed]
        if len(unconf) != 1:
            continue
        j, c, sign = unconf[0]
        old = rows[j][IDX[c]] or 0.0
        new = old - s / sign
        if abs(new - old) < 1 or new < -0.005:
            continue
        implied[(j, c)].append((name, round(new, 2)))
    # phase B: adoption
    fixed = 0
    for (j, c), imps in implied.items():
        old = rows[j][IDX[c]] or 0.0
        name, new = imps[0]
        # cross-constraint agreement from different constraint families
        fams = {fam(n) for n, v in imps if abs(v - new) <= 0.5}
        cross = len(fams) >= 2
        # candidate agreement: an independent OCR read produced this value
        pool = filt_vals(cands[j][c]) if c != "pct" else cands[j][c]
        cand_hit = any(v is not None and abs(v - new) <= 0.5 for v in pool)
        # never break a previously-consistent printed pct identity
        if c in ("dipinda", "sebenar") and rows[j][IDX["pct"]] is not None and any(
                info["strict"] and abs((v if v is not None else -1) - rows[j][IDX["pct"]]) <= 0.005
                for v, info in cands[j]["pct"].items()):
            d0, s0, p0 = rows[j][IDX["dipinda"]], rows[j][IDX["sebenar"]], rows[j][IDX["pct"]]
            if d0 and s0 is not None and abs(s0 / d0 * 100 - p0) <= 0.6:
                d1 = new if c == "dipinda" else d0
                s1 = new if c == "sebenar" else s0
                if d1 and abs(s1 / d1 * 100 - p0) > 0.8:
                    continue
        # printed pct identity corroborates the implied value
        ident_ok = False
        if c in ("dipinda", "sebenar") and rows[j][IDX["pct"]] is not None:
            d = new if c == "dipinda" else rows[j][IDX["dipinda"]]
            sv = new if c == "sebenar" else rows[j][IDX["sebenar"]]
            if d and sv is not None and abs(sv / d * 100 - rows[j][IDX["pct"]]) <= 0.6:
                ident_ok = True
        ed = edit_dist(f"{old:.2f}", f"{new:.2f}")
        dr, di = re.sub(r"[^\d]", "", f"{old:.2f}"), re.sub(r"[^\d]", "", f"{new:.2f}")
        dr0, di0 = dr.strip("0"), di.strip("0")
        decshift = dr0 == di0 and dr0 != ""
        trunc = len(dr) >= 5 and (di.endswith(dr) or di.startswith(dr))
        if cand_hit or decshift or trunc or ed <= 2 or ident_ok or cross:
            why = ("independent OCR read agrees" if cand_hit else
                   "decimal/comma slip" if decshift else
                   "truncation" if trunc else
                   f"edit-dist {ed}" if ed <= 2 else
                   "printed pct identity corroborates" if ident_ok else
                   f"agreeing independent constraints {sorted(fams)}")
            salvage.append(
                f"arithmetic salvage p{rows[j][21]} '{str(rows[j][10])[:40]}' {c} "
                f"{fmt(old)} -> {fmt(new)} [constraint {name}; {why}]")
            rows[j][IDX[c]] = new
            fixed += 1
            auto_fixes += 1
            continue
        if not final:
            continue
        mo_key = (rows[j][21], str(rows[j][10]), c, rows[j][5])
        if mo_key in MANUAL_OVERRIDES:
            val, note = MANUAL_OVERRIDES[mo_key]
            salvage.append(f"MANUAL_OVERRIDE p{rows[j][21]} '{str(rows[j][10])[:40]}' {c} "
                           f"{fmt(old)} -> {fmt(val)} ({note})")
            rows[j][IDX[c]] = val
            fixed += 1
            manual_fixes += 1
            continue
        if (j, c) not in contested_seen:
            contested_seen.add((j, c))
            contested_list.append((j, c, old, new, name))
            salvage.append(
                f"CONTESTED cell p{rows[j][21]} '{str(rows[j][10])[:40]}' {c}: "
                f"read {fmt(old)}, constraint {name} implies {fmt(new)} (left as read)")
    return fixed


def _tol_of(name):
    return 0.55 if not name.startswith("nota5b") else (0.55 if not name.endswith("s") else 0.75)


def csp_round():
    """Group repair: choose per-cell values from the OCR candidate pools so a
    failing printed sum holds.  Only actual OCR readings (page TSV / row-band /
    cell / raw-render) are adoptable -- i.e. an independent read that agrees
    with the volume's own arithmetic -- and only cells on which every minimal-
    change solution agrees are changed."""
    global auto_fixes
    import itertools
    cons = build_constraints()
    stat = []
    for name, cells, const, col in cons:
        s = sum(sign * (rows[j][IDX[c]] or 0.0) for j, c, sign in cells) - const
        stat.append((abs(s) <= _tol_of(name), s))
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
        if not unconf or len(unconf) > 7:
            continue
        total_confirmed = sum(sign * (rows[j][IDX[c]] or 0.0)
                              for j, c, sign in cells if (j, c) in confirmed)
        pools = []
        for j, c, sign in unconf:
            cur = rows[j][IDX[c]] or 0.0
            pool = [cur]
            for v, info in sorted(filt_vals(cands[j][c]).items(),
                                  key=lambda kv: not kv[1]["strict"]):
                if v is not None and all(abs(v - x) > 0.005 for x in pool):
                    pool.append(v)
            pools.append(pool[:6])
        n_comb = 1
        for p in pools:
            n_comb *= len(p)
        if n_comb > 5000:
            continue
        tol = _tol_of(name)

        def identity_ok_after(combo):
            byrow = {}
            for (j, c, sign), v in zip(unconf, combo):
                byrow.setdefault(j, {})[c] = v
            for j, ch in byrow.items():
                p = rows[j][IDX["pct"]]
                if p is None or not any(
                        info["strict"] and abs((v if v is not None else -1) - p) <= 0.005
                        for v, info in cands[j]["pct"].items()):
                    continue
                d = ch.get("dipinda", rows[j][IDX["dipinda"]])
                sv = ch.get("sebenar", rows[j][IDX["sebenar"]])
                if not d or sv is None:
                    continue
                if abs(sv / d * 100 - p) > 0.8:
                    return False
            return True

        sols_all, sols_id = [], []
        for combo in itertools.product(*pools):
            tot = total_confirmed + sum(sign * v for (jc, v) in zip(unconf, combo)
                                        for j, c, sign in [jc])
            if abs(tot - const) <= tol:
                sols_all.append(combo)
                if identity_ok_after(combo):
                    sols_id.append(combo)
                if len(sols_all) > 60:
                    break
        sols = sols_id if sols_id else sols_all
        if not sols:
            continue
        def n_changes(combo):
            return sum(1 for (j, c, sign), v in zip(unconf, combo)
                       if abs(v - (rows[j][IDX[c]] or 0.0)) > 0.005)
        minch = min(n_changes(cb) for cb in sols)
        sols = [cb for cb in sols if n_changes(cb) == minch]
        for k, (j, c, sign) in enumerate(unconf):
            vals = {round(cb[k], 2) for cb in sols}
            if len(vals) == 1:
                v = vals.pop()
                old = rows[j][IDX[c]] or 0.0
                if abs(v - old) > 0.005:
                    salvage.append(
                        f"csp salvage p{rows[j][21]} '{str(rows[j][10])[:40]}' {c} "
                        f"{fmt(old)} -> {fmt(v)} [constraint {name}; independent OCR "
                        f"read agrees with printed sum]")
                    rows[j][IDX[c]] = v
                    fixed += 1
                    auto_fixes += 1
    return fixed


_enriched = set(still)


def enrich_failing():
    cons = build_constraints()
    bad = set()
    for name, cells, const, col in cons:
        s = sum(sign * (rows[j][IDX[c]] or 0.0) for j, c, sign in cells) - const
        if abs(s) > _tol_of(name):
            bad.update(j for j, c, sign in cells)
    todo = [j for j in bad if j not in _enriched]
    _enriched.update(todo)
    if todo:
        with ThreadPoolExecutor(max_workers=2) as ex:
            list(ex.map(deep_reocr_row, todo))
    return len(todo)


for rnd in range(10):
    n_en = enrich_failing() if rnd < 2 else 0
    f1 = csp_round()
    f2 = solve_round()
    print(f"repair round {rnd}: enriched {n_en} rows, csp fixes {f1}, solver fixes {f2}")
    if not (f1 or f2 or n_en):
        break
solve_round(final=True)

# pct final salvage
n_pct_fix = 0
for ridx, r in enumerate(rows):
    if not pct_bad(r):
        continue
    exp = round(r[IDX["sebenar"]] / r[IDX["dipinda"]] * 100, 2)
    old_p = r[IDX["pct"]]
    hit = [v for v in cands[ridx]["pct"] if v is not None and abs(v - exp) <= 0.6]
    if hit:
        salvage.append(f"pct salvage p{r[21]} '{str(r[10])[:40]}' pct {old_p} -> {hit[0]} "
                       f"(candidate read agrees with identity; RM columns constraint-checked)")
        r[IDX["pct"]] = hit[0]
        n_pct_fix += 1
    elif old_p is not None and old_p >= 1000 and abs(old_p / 100.0 - exp) < 0.7:
        salvage.append(f"pct salvage p{r[21]} '{str(r[10])[:40]}' pct {old_p} -> {old_p/100.0} "
                       f"(decimal point dropped by OCR)")
        r[IDX["pct"]] = old_p / 100.0
        n_pct_fix += 1
    else:
        mo_key = (r[21], str(r[10]), "pct", r[5])
        if mo_key in MANUAL_OVERRIDES:
            val, note = MANUAL_OVERRIDES[mo_key]
            salvage.append(f"MANUAL_OVERRIDE p{r[21]} '{str(r[10])[:40]}' pct {old_p} -> {val} ({note})")
            r[IDX["pct"]] = val
            manual_fixes += 1
        else:
            contested_list.append((ridx, "pct", old_p, exp, "pct-identity"))
            salvage.append(f"CONTESTED pct p{r[21]} '{str(r[10])[:40]}': read {old_p}, "
                           f"identity implies {exp} (left as read)")
print(f"pct salvages: {n_pct_fix}")

# =====================================================================
# final tidy + write + validation log
# =====================================================================
before = len(rows)
keep = []
kept_cands = []
for r, cd in zip(rows, cands):
    if r[9] == "unclassified":
        nstrict = sum(1 for c in COLS if any(i["strict"] for i in cd[c].values()))
        if nstrict < 2:
            salvage.append(f"dropped noise line p{r[21]} '{str(r[10])[:50]}' "
                           f"({nstrict} format-valid cells)")
            continue
    if r[9] in ("object_program", "jumlah_objek_maksud") \
            and not r[12] and not r[15] and not r[16] \
            and not any(i["strict"] for c in COLS for i in cd[c].values()):
        salvage.append(f"dropped all-empty noise row p{r[21]} '{str(r[10])[:50]}'")
        continue
    keep.append(r)
    kept_cands.append(cd)
rows, cands = keep, kept_cands
print(f"dropped {before - len(rows)} junk rows")

# canonical maksud names, clear hierarchy fields on summary rows (2014 style)
for r in rows:
    if r[1] in ORACLE_BY_CODE:
        r[2] = ORACLE_BY_CODE[r[1]][2]
        if r[9] == "jumlah_maksud":
            r[10] = ORACLE_BY_CODE[r[1]][2]
for r in rows:
    rt = r[9]
    if rt in ("object_program", "jumlah_program"):
        r[5] = r[6] = None
    elif rt in ("jumlah_objek_maksud", "jumlah_maksud"):
        r[3] = r[4] = r[5] = r[6] = None
    elif rt in ("jumlah_objek_jenis", "jumlah_jenis"):
        r[1] = r[2] = r[3] = r[4] = r[5] = r[6] = None
    elif rt in ("jumlah_objek_keseluruhan", "jumlah_besar"):
        r[0] = None
        r[1] = r[2] = r[3] = r[4] = r[5] = r[6] = None

# back-fill program names
_pnames = {}
for r in rows:
    if r[3] and r[4]:
        _pnames.setdefault((r[1], r[3]), r[4])
for r in rows:
    if r[3] and not r[4] and (r[1], r[3]) in _pnames:
        r[4] = _pnames[(r[1], r[3])]

cons = build_constraints()
n_pass = n_fail = 0
fail_rows = []
for name, cells, const, col in cons:
    tol = 0.55 if not name.startswith("nota5b") else (0.55 if not name.endswith("s") else 0.75)
    s = sum(sign * (rows[j][IDX[c]] or 0.0) for j, c, sign in cells) - const
    ok = abs(s) <= tol
    n_pass += ok
    n_fail += not ok
    status = "PASS" if ok else "FAIL"
    got = sum(sign * (rows[j][IDX[c]] or 0.0) for j, c, sign in cells if sign > 0)
    want = got - s
    checks.append((status, f"lampiran1: {name} {col} sum", f"{got:.2f}", f"{want:.2f}", f"{s:.2f}"))
    if not ok:
        fail_rows.append((name, col, s))
print(f"constraints: {n_pass} PASS / {n_fail} FAIL")
for fr in fail_rows[:40]:
    print("  FAIL", fr)

badpct = sum(1 for r in rows if pct_bad(r))
checks.append(("PASS" if badpct == 0 else "FAIL",
               f"lampiran1: rows failing pct≈sebenar/dipinda*100 (tol 0.6)", str(badpct), "0", str(badpct)))

if DEV:
    OUT = "/tmp/dev_fact_opex_detail.csv"
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
        out = list(r[:24])
        for k in (13, 14, 18):
            out[k] = ""
        out[17] = "" if out[17] is None else out[17]
        cw.writerow(out)

c = Counter(r[9] for r in rows)
print(f"\nfact_opex_detail.csv: {len(rows)} rows")
for k, v in c.most_common():
    print(f"  {k}: {v}")
for n in salvage:
    print("!!", n)
print(f"auto arithmetic fixes: {auto_fixes}; manual overrides applied: {manual_fixes}; "
      f"contested left as read: {len(contested_list)}")
un = [r for r in rows if r[9] == "unclassified"]
print(f"unclassified: {len(un)}")
for r in un[:30]:
    print("   ?", str(r[10])[:70], "p", r[21])
gt = {c: sum(r[IDX[c]] or 0 for r in rows if r[9] == "jumlah_maksud") for c in ("asal", "dipinda", "sebenar")}
print("sum jumlah_maksud:", {k: f"{v:,.2f}" for k, v in gt.items()})
for r in rows:
    if r[9] == "jumlah_besar":
        print("grand:", fmt(r[12]), fmt(r[15]), fmt(r[16]), r[17])

# salvage/override notes -> validation csv
for n in salvage:
    tag = ("FAIL" if n.startswith(("CONTESTED", "UNMATCHED", "NOTE")) else "INFO")
    checks.append((tag, f"lampiran1: {n[:220]}", "", "", ""))

# de-dup our prefix rows then append (idempotent reruns)
VPATH = "/home/claude/pkkp/warehouse2015/_validation_checks_2015.csv"
if DEV:
    VPATH = "/tmp/dev_checks.csv"
if os.path.exists(VPATH):
    kept = []
    with open(VPATH, newline="", encoding="utf-8") as f:
        rd = list(csv.reader(f))
    hdr, body = rd[0], rd[1:]
    body = [x for x in body if not (len(x) > 1 and x[1].startswith("lampiran1:"))]
    with open(VPATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(hdr)
        w.writerows(body)
ocrlib.append_checks(checks, path=VPATH)
print(f"appended {len(checks)} validation rows")

# dump contested crops for eye-verification
os.makedirs("/tmp/contested", exist_ok=True)
for k, (j, c, old, new, name) in enumerate(contested_list[:80]):
    m = rows[j][25] if j < len(rows) and len(rows[j]) > 25 else None
    if not m:
        continue
    x1 = TEMPLATE[c] + m["shift"] + 20 if c != "pct" else TEMPLATE["pct"] + m["shift"] + 30
    x0 = TEMPLATE[c] + m["shift"] - 330
    ocrlib.save_crop(m["pno"], (x0, m["top"] - 8, x1, m["bot"] + 8),
                     f"/tmp/contested/c{k:02d}_p{m['pno']}_{c}.png", scale=4)
    print(f"contested crop c{k:02d}: p{m['pno']} '{str(rows[j][10])[:40]}' {c} "
          f"read {fmt(old)} implied {fmt(new)} [{name}]")
_cf.flush(); _rf.flush(); _rrf.flush(); _kf.flush()
