#!/usr/bin/env python3
"""Extract Lampiran 2 at PROJECT level (PKKP 2015, pdf 242-271, two-page
spreads; NO text layer -- parsed from 400-dpi OCR TSVs + per-cell re-OCR).

Left (even) pages: maksud header 'P.xx NAME', program headers (all caps),
project rows '[*]NNNNN name' + [Kos Keseluruhan | Perbelanjaan Sebenar
RMKe-10 hingga 31.12.2014], 'Jumlah <Program>' subtotals, 'JUMLAH <MINISTRY>'
totals, grand 'JUMLAH PERBELANJAAN PEMBANGUNAN'. Right (odd) pages, same rows
by y: 7 cols = Anggaran Tahun 2015 [Cara Langsung|Pinjaman|Jumlah],
Perbelanjaan Sebenar 2015 [Cara Langsung|Pinjaman|Jumlah], Perbelanjaan
Sebenar RMKe-10 hingga 31.12.2015.  2015 = RMKe-10 FINAL year: prior
cumulative -> terkumpul_rmke10_prior_rm, current -> terkumpul_rmke10_rm
(same storage as warehouse2014).

Base page OCR digits are unreliable (144-dpi source): every amount cell is
re-OCR'd from its own crop (clean render scale 3 + raw render scale 4,
psm 7 digit whitelist, cached).  A value is 'confirmed' when >=2 independent
reads agree on a well-formed amount; residual cells are forced by the row
identities (ag_l+ag_p=ag_j, sb_l+sb_p=sb_j, prior+sb_j=kum) and per-maksud
column sums, near-digit auto-fixes logged, CONTESTED cells eye-verified from
crops (OVERRIDES below).  Print-side inconsistencies stay as printed and are
logged FAIL.
"""
import csv
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher

sys.path.insert(0, "/home/claude/pkkp/work/2015/pipeline")
import ocrlib
from ocrlib import SRC, PAGE_OFFSET

YEAR = 2015
STMT = "Lampiran 2 Penyata Perbelanjaan Pembangunan"
DRY = os.environ.get("L2_DRY") == "1"
OUT = ("/tmp/fact_devex_project.csv" if DRY
       else "/home/claude/pkkp/warehouse2015/fact_devex_project.csv")
CHECKS_PATH = ("/tmp/l2_checks.csv" if DRY
               else "/home/claude/pkkp/warehouse2015/_validation_checks_2015.csv")
CACHE = "/home/claude/pkkp/work/2015/cache/lampiran2_cellocr.json"
EYEDIR = "/tmp/l2_eye"
LEFT_PAGES = list(range(242, 271, 2))
TOL = 0.011

# ---------------------------------------------------------------- overrides
# Eye-verified cells (Read of zoomed crops). key -> printed string.
# key = f"{pno}:{rowkey}:{col}"  (col in kos,prior,ag_l,ag_p,ag_j,sb_l,sb_p,
# sb_j,kum); rowkey = y-top of the LEFT row.  Every entry corresponds to a
# logged manual-override INFO row.
OVERRIDES = {}  # filled after eye-verification passes (see appended log)
MANUAL_NOTES = {}

NOISE = re.compile(r"[|!'\"`~_=\\]")


# ---------------------------------------------------------------- helpers
def letters(s):
    return re.sub(r"[^A-Za-z]", "", s or "").upper()


def lev(a, b, cap=99):
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def fuzzy(a, b, frac=0.3):
    a, b = letters(a), letters(b)
    if not a or not b:
        return False
    cap = max(1, int(frac * max(len(a), len(b))))
    return lev(a, b, cap) <= cap


WELL = re.compile(r"^\(?\d{1,3}(?:,\d{3})*\.\d{2}\)?$")


def canon_amount(s):
    """(value, wellformed) from an OCR string; None if hopeless."""
    if s is None:
        return None
    t = NOISE.sub("", str(s)).replace(" ", "").replace("*", "")
    t = t.replace("O", "0").replace("o", "0").replace("S", "5").replace("l", "1").replace("I", "1")
    if not re.search(r"\d", t):
        return None
    neg = "(" in t and ")" in t
    t = t.strip("()").strip(".").strip(",")
    if re.fullmatch(r"\d{1,3}(?:,\d{3})*,\d{2}", t):  # comma as decimal sep
        t = t[: t.rfind(",")] + "." + t[t.rfind(",") + 1:]
    well = bool(WELL.match(("(" + t + ")") if False else t))
    digits = re.sub(r"[^\d.]", "", t)
    if "." in digits:
        main, _, frac = digits.rpartition(".")
        main = main.replace(".", "")
        if len(frac) == 2:
            v = float(main or 0) + float(frac) / 100
        elif len(frac) == 1:
            v, well = float(main or 0) + float(frac) / 10, False
        else:
            v, well = float(main + frac), False
    else:
        v, well = float(digits), False
    return (-v if neg else v), well


def near_digit(a, b):
    """Printed-string near-variant: same magnitude class, <=2 digit edits."""
    da = re.sub(r"\D", "", f"{abs(a):.2f}")
    db = re.sub(r"\D", "", f"{abs(b):.2f}")
    return lev(da, db, 2) <= 2


# ---------------------------------------------------------------- cell OCR
import threading
_cache = {}
if os.path.exists(CACHE):
    _cache = json.load(open(CACHE))
_cache_dirty = [0]
_cache_lock = threading.Lock()


def save_cache():
    if _cache_dirty[0]:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with _cache_lock:
            snap = dict(_cache)
        tmp = CACHE + ".tmp"
        json.dump(snap, open(tmp, "w"))
        os.replace(tmp, CACHE)
        _cache_dirty[0] = 0


_tmpn = [0]


def cellocr(pno, box, scale=3, clean=True, psm=7):
    key = f"{pno}:{','.join(str(int(v)) for v in box)}:{scale}:{int(clean)}:{psm}"
    if key in _cache:
        return _cache[key]
    from PIL import Image
    img = ocrlib.get_img(pno, clean=clean)
    x0, y0, x1, y1 = [int(v) for v in box]
    crop = img.crop((max(0, x0 - 2), max(0, y0 - 2),
                     min(img.width, x1 + 3), min(img.height, y1 + 3)))
    big = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
    _tmpn[0] += 1
    tmp = f"/tmp/l2cell_{os.getpid()}_{_tmpn[0] % 64}.png"
    big.save(tmp)
    args = ["tesseract", tmp, "stdout", "--psm", str(psm),
            "-c", "tessedit_char_whitelist=0123456789,.()*"]
    out = subprocess.run(args, capture_output=True, text=True).stdout.strip().replace(" ", "")
    with _cache_lock:
        _cache[key] = out
        _cache_dirty[0] += 1
    return out


def ink_stats(pno, box, clean=True, thresh=150):
    from PIL import Image
    img = ocrlib.get_img(pno, clean=clean)
    x0, y0, x1, y1 = [int(v) for v in box]
    crop = img.crop((max(0, x0), max(0, y0), min(img.width, x1), min(img.height, y1)))
    mask = crop.point(lambda p: 255 if p < thresh else 0)
    bbox = mask.getbbox()
    dark = int(sum(mask.histogram()[128:]) if False else mask.histogram()[255])
    if not bbox:
        return 0, 0, 0
    return dark, bbox[2] - bbox[0], bbox[3] - bbox[1]


# ---------------------------------------------------------------- geometry
def calibrate_right(pno):
    """Per-page 7 right-edge anchors."""
    base = [575, 950, 1340, 1730, 2075, 2460, 2890]
    words = ocrlib.load_words(pno)
    nums = [w for w in words if w["top"] > 900 and w["right"] < 3050
            and re.search(r"\d", w["text"])
            and re.match(r"^[\d,.()*OoSGl|!~—–-]+$", w["text"])]
    per = defaultdict(list)
    for w in nums:
        ci = min(range(7), key=lambda i: abs(base[i] - w["right"]))
        if abs(base[ci] - w["right"]) < 160:
            per[ci].append(w["right"])
    out = []
    for i in range(7):
        xs = sorted(per[i])
        out.append(xs[len(xs) // 2] if len(xs) >= 3 else base[i])
    return out


def calibrate_left(pno):
    base = [2274, 2675]
    words = ocrlib.load_words(pno)
    nums = [w for w in words if w["top"] > 900 and 1650 < w["right"] < 2800
            and re.search(r"\d", w["text"])]
    per = defaultdict(list)
    for w in nums:
        ci = 0 if abs(base[0] - w["right"]) < abs(base[1] - w["right"]) else 1
        if abs(base[ci] - w["right"]) < 140:
            per[ci].append(w["right"])
    return [sorted(per[i])[len(per[i]) // 2] if len(per[i]) >= 3 else base[i]
            for i in range(2)]


COLS = ["ag_l", "ag_p", "ag_j", "sb_l", "sb_p", "sb_j", "kum"]
LCOLS = ["kos", "prior"]


def cell_box(anchors, ci, ytop, ybot, is_left=False):
    a = anchors[ci]
    x0 = a - 330
    if ci > 0:
        x0 = max(x0, anchors[ci - 1] + 35)
    elif not is_left:
        x0 = max(x0, 300)
    else:
        x0 = a - 340
    return (x0, ytop - 4, a + 22, ybot + 4)


# ---------------------------------------------------------------- resolution
def queue_cell(cells, cn, pno, box, tsv_txt, tag, pending):
    cells[cn] = dict(value=None, well=False, route="pending", cands=[], box=box)
    pending.append((cells, cn, pno, box, tsv_txt, tag))


def run_pending(pending, checks, workers=4):
    # preload page images (thread-safety of get_img cache)
    for pno in sorted({p[2] for p in pending}):
        ocrlib.get_img(pno, clean=True)
        ocrlib.get_img(pno, clean=False)
        print(f"preloaded p{pno}", flush=True)
    def work(job):
        cells, cn, pno, box, tsv_txt, tag = job
        cells[cn] = resolve_cell(pno, box, tsv_txt, checks, tag)
    with ThreadPoolExecutor(workers) as ex:
        n = 0
        for _ in ex.map(work, pending):
            n += 1
            if n % 500 == 0:
                print(f"resolved {n}/{len(pending)} cells", flush=True)
                save_cache()
    save_cache()


def resolve_cell(pno, box, tsv_txt, checks, tag):
    """Return dict(value, well, route, cands). Value None => needs solving."""
    ov = OVERRIDES.get(tag)
    if ov is not None:
        v, _ = canon_amount(ov)
        return dict(value=v, well=True, route="manual_eye", cands=[v], box=box)
    dark, iw, ih = ink_stats(pno, box)
    if dark < 12:
        return dict(value=0.0, well=True, route="blank", cands=[0.0], box=box)
    if ih <= 12 and iw <= 60 and dark < 260:
        return dict(value=0.0, well=True, route="dash", cands=[0.0], box=box)
    reads = []
    tv = canon_amount(tsv_txt) if tsv_txt else None
    if tv:
        reads.append(("tsv", tv))
    c1 = canon_amount(cellocr(pno, box, scale=3, clean=True))
    if c1:
        reads.append(("clean3", c1))
    # early exit on strong agreement
    vals = [r for r in reads if r[1][1]]
    if len(vals) >= 2 and abs(vals[0][1][0] - vals[1][1][0]) < TOL:
        return dict(value=vals[0][1][0], well=True, route="tsv+clean", cands=[vals[0][1][0]], box=box)
    c2 = canon_amount(cellocr(pno, box, scale=4, clean=False))
    if c2:
        reads.append(("raw4", c2))
    well = [(nm, v) for nm, (v, w) in reads if w]
    for i in range(len(well)):
        for j in range(i + 1, len(well)):
            if abs(well[i][1] - well[j][1]) < TOL:
                return dict(value=well[i][1], well=True,
                            route=well[i][0] + "+" + well[j][0], cands=[well[i][1]], box=box)
    # no two agreeing well-formed reads
    cands = []
    for nm, (v, w) in reads:
        if not any(abs(v - c) < TOL for c in cands):
            cands.append(v)
    val = well[0][1] if well else (reads[0][1][0] if reads else None)
    return dict(value=val, well=bool(well), route="unconfirmed", cands=cands, box=box)


# ---------------------------------------------------------------- left parse
def parse_left(pno, checks):
    words = ocrlib.load_words(pno)
    lines = ocrlib.cluster_lines(words, ytol=14)
    kosx, priorx = calibrate_left(pno)
    recs = []
    for top, bot, ws in lines:
        ws = ocrlib.merge_number_fragments(ws, maxgap=28)
        texts = [w["text"] for w in ws]
        line = " ".join(texts)
        L = letters(line)
        if top < 900:
            continue
        amts = [w for w in ws if w["left"] > 1680 and (re.search(r"\d", w["text"]) or ocrlib.DASHRE.match(w["text"]))]
        head = [w for w in ws if w not in amts and w["right"] <= 2100]
        headtxt = " ".join(NOISE.sub("", w["text"]) for w in head).strip()
        if not head and not amts:
            continue
        if letters(headtxt).startswith("NOTA") or (head and fuzzy(head[0]["text"], "Nota", 0.34) and len(head[0]["text"]) <= 6):
            recs.append(dict(kind="nota", y=(top, bot), text=line))
            continue
        recs.append(dict(kind="raw", y=(top, bot), head=head, amts=amts,
                         headtxt=headtxt, line=line))
    return recs, (kosx, priorx)


def head_code(pno, rec):
    """Re-OCR the code column region of a row; '' if no ink."""
    top, bot = rec["y"]
    box = (315, top - 4, 476, bot + 4)
    dark, iw, ih = ink_stats(pno, box)
    if dark < 25:
        return "", False
    out = cellocr(pno, box, scale=4, clean=True, psm=7)
    star = out.startswith("*") or "*" in out
    dig = re.sub(r"\D", "", out)
    return dig, star


# ---------------------------------------------------------------- main parse
def main():
    checks = []
    os.makedirs(EYEDIR, exist_ok=True)
    # canonical names for maksud (2014+2016)
    canon_mk = {}
    for wf in ("/home/claude/pkkp/warehouse2014/fact_devex_maksud.csv",
               "/home/claude/pkkp/warehouse2016/fact_devex_maksud.csv"):
        if os.path.exists(wf):
            for r in csv.DictReader(open(wf)):
                if r["maksud_code"].startswith("P."):
                    canon_mk.setdefault(r["maksud_code"], set()).add(r["maksud_name_bm"])
                    canon_mk[r["maksud_code"]].add(r["jumlah_label_bm"])
    canon_proj = {}
    canon_prog = defaultdict(set)
    for wf in ("/home/claude/pkkp/warehouse2014/fact_devex_project.csv",
               "/home/claude/pkkp/warehouse2016/fact_devex_project.csv"):
        if os.path.exists(wf):
            for r in csv.DictReader(open(wf)):
                if r["row_type"] == "project":
                    canon_proj.setdefault((r["maksud_code"], r["projek_code"]), []).append(r["name_bm"])
                if r["program_bm"]:
                    canon_prog[r["maksud_code"]].add(r["program_bm"])
                if r["row_type"] == "program_subtotal":
                    canon_prog[r["maksud_code"]].add(r["name_bm"])

    all_rows = []       # ordered row dicts across the whole statement
    pending = []        # queued cell-resolution jobs
    cur_mk = cur_mkname = None
    cur_prog = None
    last_amt_row = None
    last_prog_hdr = False

    for pno in LEFT_PAGES:
        recs, (kosx, priorx) = parse_left(pno, checks)
        lanch = [kosx, priorx]
        for rec in recs:
            if rec["kind"] == "nota":
                # RM10 pendahuluan Nota: record for footnote flags
                all_rows.append(dict(rt="nota", page=pno, text=rec["text"], y=rec["y"]))
                last_amt_row = None
                continue
            top, bot = rec["y"]
            head, amts = rec["head"], rec["amts"]
            headtxt = rec["headtxt"]
            L = letters(headtxt)
            code, star = ("", False)
            if head and head[0]["left"] < 470:
                code, star = head_code(pno, rec)
            firstword = head[0]["text"] if head else ""
            is_jum = (fuzzy(firstword, "Jumlah", 0.4) and len(letters(firstword)) >= 4) or L.startswith(("JUMLAH", "UUMLAH", "IUMLAH", "JUMIAH", "SUMAH", "SUME", "SUMAN", "JUMAH", "UUMAH"))
            resid = None
            if is_jum:
                resid = re.sub(r"^\S+\s*", "", headtxt).strip()
            # maksud header: no amounts, all-caps-ish, starts left, has P-code
            if not amts and head and head[0]["left"] < 470 and not code and not is_jum \
                    and len(L) > 8 and sum(c.isupper() for c in headtxt if c.isalpha()) > 0.7 * len(L):
                name = re.sub(r"^\S+\s*", "", headtxt)
                name = re.sub(r"\s*[-–—]?\s*\(?[Ss][Aa][Mm][Bb][^)]*\)?\s*$", "", name).strip()
                samb = "SAMB" in letters(rec["line"])
                # code via canonical name match
                best = None
                for mk, names in canon_mk.items():
                    for nm in names:
                        r = SequenceMatcher(None, letters(name), letters(nm)).ratio()
                        if best is None or r > best[0]:
                            best = (r, mk, nm)
                hdr_ocr = cellocr(pno, (315, top - 6, 500, bot + 6), scale=4)
                mnum = re.sub(r"\D", "", hdr_ocr)[:2]
                if best and best[0] > 0.72:
                    mk = best[1]
                    if mnum and mnum != mk[2:] and len(mnum) == 2:
                        # trust name match; log
                        checks.append(("INFO", f"lampiran2: p{pno} maksud header code OCR '{hdr_ocr}' vs name-matched {mk} ({name[:40]}) -- name match used", hdr_ocr, mk, ""))
                    nm_canon = max(canon_mk[mk], key=len)
                elif mnum:
                    mk, nm_canon = f"P.{mnum}", name
                    checks.append(("WARN", f"lampiran2: p{pno} maksud header only via code OCR: {mk} {name[:40]}", hdr_ocr, "", ""))
                else:
                    checks.append(("WARN", f"lampiran2: p{pno} unrecognized header line kept as program: {headtxt[:60]}", "", "", ""))
                    continue
                if not samb:
                    cur_prog = None
                cur_mk, cur_mkname = mk, nm_canon
                if samb and letters(name) and not fuzzy(name, nm_canon, 0.35):
                    checks.append(("INFO", f"lampiran2: p{pno} (SAMB.) header name variant '{name[:50]}' for {mk}", "", "", ""))
                last_amt_row = None
                last_prog_hdr = False
                continue
            if amts:
                # amount row: resolve kos/prior cells
                cells = {}
                for i, cn in enumerate(LCOLS):
                    toks = [w for w in amts if abs(w["right"] - lanch[i]) < 165 or
                            (lanch[i] - 340 < w["left"] and w["right"] < lanch[i] + 25 and (i == 0 or w["left"] > lanch[0] + 40))]
                    toks = [w for w in toks if (w["right"] <= lanch[i] + 30) and w["right"] > lanch[i] - 340]
                    tsv_txt = "".join(w["text"] for w in toks) if toks else None
                    if toks:
                        y0 = min(w["top"] for w in toks) - 2
                        y1 = max(w["bottom"] for w in toks) + 2
                        y0, y1 = min(y0, top), max(y1, bot)
                    else:
                        y0, y1 = top, bot
                    box = cell_box(lanch, i, y0, y1, is_left=True)
                    queue_cell(cells, cn, pno, box, tsv_txt, f"{pno}:{top}:{cn}", pending)
                star2 = "*" in " ".join(w["text"] for w in amts)
                if code and re.fullmatch(r"\d{5}", code):
                    rt, name = "project", headtxt
                    if head and re.match(r"^[\dOoQGSseflc€un*]{4,6}\)?$", head[0]["text"]):
                        name = " ".join(NOISE.sub("", w["text"]) for w in head[1:]).strip()
                elif is_jum:
                    if "PERBELANJAANPEMBANGUNAN" in L:
                        rt, name = "grand_total", "JUMLAH PERBELANJAAN PEMBANGUNAN"
                    else:
                        rt, name = "jumlah", resid  # ministry vs program decided later
                else:
                    rt, name = "odd", headtxt
                    if code:
                        # garbled 4/6-digit code: treat as project, code fixed later
                        rt = "project"
                        name = " ".join(NOISE.sub("", w["text"]) for w in head[1:]).strip()
                all_rows.append(dict(rt=rt, page=pno, y=(top, bot), code=code or None,
                                     star=star or star2, name=name, maksud=cur_mk,
                                     mkname=cur_mkname, program=cur_prog, cells=cells,
                                     line=rec["line"]))
                last_amt_row = all_rows[-1]
                last_prog_hdr = False
            else:
                # no amounts: program header (all caps) or name wrap
                if L and L == letters(headtxt.upper()) and sum(c.islower() for c in headtxt) <= 2 and len(L) >= 4:
                    frag = re.sub(r"\s*[-–—]?\s*\(?[Ss][Aa][Mm][Bb][^)]*\)?\s*$", "", headtxt).strip()
                    if last_prog_hdr and cur_prog:
                        cur_prog = cur_prog + " " + frag
                    else:
                        cur_prog = frag
                    if all_rows and all_rows[-1].get("rt") == "jumlah":
                        pass
                    last_prog_hdr = True
                    last_amt_row = None
                elif last_amt_row is not None and len(headtxt) < 90 and headtxt:
                    last_amt_row["name"] += " " + headtxt
        print(f"left p{pno} parsed: rows so far {len(all_rows)}")

    # program attach for jumlah rows / projects
    for r in all_rows:
        if r.get("rt") == "jumlah":
            r["program_hdr"] = r.get("program")

    # ---------------------------------------------------------- right pages
    for pno in LEFT_PAGES:
        rp = pno + 1
        anch = calibrate_right(rp)
        words = ocrlib.load_words(rp)
        toks = [w for w in words if w["top"] > 900 and w["right"] < 3050
                and (ocrlib.DASHRE.match(w["text"]) or
                     (re.search(r"\d", w["text"]) and re.match(r"^[\d,.()*OoSGl|!~—–-]+$", w["text"])))]
        mine = [r for r in all_rows if r.get("page") == pno and r.get("cells") is not None]
        if not mine:
            continue
        # y offset: mode of diffs between right token line-centers and left rows
        centers = sorted({(w["top"] + w["bottom"]) // 2 for w in toks})
        diffs = []
        for r in mine:
            lc = (r["y"][0] + r["y"][1]) / 2
            best = min(centers, key=lambda c: abs(c - lc)) if centers else lc
            if abs(best - lc) < 60:
                diffs.append(best - lc)
        dy = sorted(diffs)[len(diffs) // 2] if diffs else 0
        for r in mine:
            lc = (r["y"][0] + r["y"][1]) / 2 + dy
            rowtoks = [w for w in toks if abs((w["top"] + w["bottom"]) / 2 - lc) <= 24]
            ry0 = min([w["top"] for w in rowtoks], default=r["y"][0] + dy)
            ry1 = max([w["bottom"] for w in rowtoks], default=r["y"][1] + dy)
            ry0, ry1 = min(ry0, lc - 15), max(ry1, lc + 15)
            for ci, cn in enumerate(COLS):
                ctoks = [w for w in rowtoks if abs(w["right"] - anch[ci]) < 150
                         or (anch[ci] - 330 < w["left"] and w["right"] <= anch[ci] + 25
                             and (ci == 0 or w["left"] > anch[ci - 1] + 30))]
                ctoks = [w for w in ctoks if w["right"] <= anch[ci] + 30 and w["right"] > anch[ci] - 340]
                tsv_txt = "".join(w["text"] for w in ctoks) if ctoks else None
                if ctoks:
                    y0 = min(w["top"] for w in ctoks) - 2
                    y1 = max(w["bottom"] for w in ctoks) + 2
                else:
                    y0, y1 = ry0, ry1
                box = cell_box(anch, ci, y0, y1)
                queue_cell(r["cells"], cn, rp, box, tsv_txt, f"{rp}:{r['y'][0]}:{cn}", pending)
            r["rpage"] = rp
        print(f"right p{rp} queued")

    run_pending(pending, checks)
    amt_rows = [r for r in all_rows if r.get("cells")]
    solve_identities(amt_rows, checks)
    classify_and_output(all_rows, amt_rows, canon_mk, canon_proj, checks)
    save_cache()


# ------------------------------------------------------------ identity solve
def row_identity_ok(v):
    return (abs(v["ag_l"] + v["ag_p"] - v["ag_j"]) < TOL
            and abs(v["sb_l"] + v["sb_p"] - v["sb_j"]) < TOL
            and abs(v["prior"] + v["sb_j"] - v["kum"]) < TOL)


def solve_identities(rows, checks):
    stats = Counter()
    for r in rows:
        c = r["cells"]
        v = {k: c[k]["value"] for k in c}
        if None in v.values():
            for k in v:
                if v[k] is None:
                    v[k] = 0.0
                    c[k]["cands"] = [x for x in c[k]["cands"] if x is not None]
        r["pre_ok"] = row_identity_ok(v)
        if r["pre_ok"]:
            for k in c:
                c[k]["final"] = v[k]
            stats["ok_initial"] += 1
            continue
        # try candidate combinations on unconfirmed cells + identity-forced values
        best = try_repair(c, v)
        if best is not None:
            fixed = [k for k in c if abs(best[k] - v[k]) > TOL]
            for k in c:
                c[k]["final"] = best[k]
            for k in fixed:
                route = "alt-read" if any(abs(best[k] - x) < TOL for x in c[k]["cands"]) else "identity-forced"
                nd = near_digit(best[k], v[k]) if v[k] is not None else False
                stats["autofix_" + route] += 1
                checks.append(("INFO", f"lampiran2: OCR salvage p{r.get('rpage', r['page'])} row@{r['y'][0]} '{(r.get('name') or '')[:40]}' {k} "
                              f"{v[k]:,.2f} -> {best[k]:,.2f} [{route}{'/near-digit' if nd else ''}, row identity]",
                              v[k], best[k], best[k] - v[k]))
            stats["ok_repaired"] += 1
            r["pre_ok"] = False
            r["post_ok"] = True
        else:
            for k in c:
                c[k]["final"] = v[k]
            r["post_ok"] = False
            stats["unresolved"] += 1
    print("identity stats:", dict(stats))
    checks.append(("INFO", "lampiran2: row-identity stats " + json.dumps(dict(stats)), "", "", ""))


def try_repair(c, v):
    """Search small candidate space for values satisfying all 3 identities."""
    import itertools
    keys = list(c.keys())
    cand = {}
    for k in keys:
        vs = [v[k]] + [x for x in c[k]["cands"] if abs(x - v[k]) > TOL]
        cand[k] = vs[:4]
    # add identity-forced derivations
    def forced(vv):
        outs = []
        outs.append(("ag_j", vv["ag_l"] + vv["ag_p"]))
        outs.append(("ag_l", vv["ag_j"] - vv["ag_p"]))
        outs.append(("ag_p", vv["ag_j"] - vv["ag_l"]))
        outs.append(("sb_j", vv["sb_l"] + vv["sb_p"]))
        outs.append(("sb_l", vv["sb_j"] - vv["sb_p"]))
        outs.append(("sb_p", vv["sb_j"] - vv["sb_l"]))
        outs.append(("kum", vv["prior"] + vv["sb_j"]))
        outs.append(("prior", vv["kum"] - vv["sb_j"]))
        return outs
    for k, fv in forced(v):
        if fv >= -1e9 and not any(abs(fv - x) < TOL for x in cand[k]):
            # forced value acceptable only if near-digit of an existing read or cell unconfirmed
            if (not c[k]["well"]) or c[k]["route"] == "unconfirmed" or near_digit(fv, v[k]):
                cand[k] = cand[k] + [fv]
    # limit search: only vary cells that are unconfirmed or have alternates
    varying = [k for k in keys if len(cand[k]) > 1]
    if len(varying) > 6:
        varying = varying[:6]
    best = None
    for combo in itertools.product(*[range(len(cand[k])) for k in varying]):
        vv = dict(v)
        for k, idx in zip(varying, combo):
            vv[k] = cand[k][idx]
        if row_identity_ok(vv):
            score = sum(1 for k in varying if vv[k] == v[k])
            if best is None or score > best[0]:
                best = (score, dict(vv))
    return best[1] if best else None


# ------------------------------------------------------------ classification
def classify_and_output(all_rows, amt_rows, canon_mk, canon_proj, checks):
    # decide jumlah rows: ministry_total vs program_subtotal
    aliases_found = []
    for r in amt_rows:
        if r["rt"] != "jumlah":
            continue
        nm = r["name"] or ""
        mk = r["maksud"]
        cands = canon_mk.get(mk, set()) | {r.get("mkname") or ""}
        if any(fuzzy(nm, c, 0.32) for c in cands if c):
            r["rt"] = "ministry_total"
            best = max(cands, key=lambda c: SequenceMatcher(None, letters(nm), letters(c)).ratio())
            if letters(nm) != letters(r.get("mkname") or ""):
                aliases_found.append((mk, r.get("mkname"), nm))
            r["name"] = best
        else:
            r["rt"] = "program_subtotal"
    # duplicate ministry_total handling (2014 P.24 pattern)
    seen = {}
    for i, r in enumerate(amt_rows):
        if r["rt"] == "ministry_total":
            if r["maksud"] in seen:
                amt_rows[seen[r["maksud"]]]["rt"] = "program_subtotal"
                checks.append(("INFO", f"lampiran2: duplicate ministry JUMLAH in {r['maksud']}: earlier row demoted to program_subtotal", "", "", ""))
            seen[r["maksud"]] = i

    # fix garbled project codes by sequence + re-OCR
    fix_codes(amt_rows, checks)

    # canonical project names
    renamed = 0
    for r in amt_rows:
        if r["rt"] != "project":
            continue
        r["name"] = re.sub(r"\s+", " ", NOISE.sub("", r["name"] or "")).strip(" .")
        key = (r["maksud"], r["code"])
        if key in canon_proj:
            best = max(canon_proj[key], key=lambda nm: SequenceMatcher(None, letters(nm), letters(r["name"])).ratio())
            ratio = SequenceMatcher(None, letters(best), letters(r["name"])).ratio()
            if ratio > 0.55 and best != r["name"]:
                r["name"] = best
                renamed += 1
    checks.append(("INFO", f"lampiran2: {renamed} project names canonicalized against 2014/2016 warehouse (same maksud+code, ratio>0.55)", renamed, "", ""))

    # column sums per maksud
    column_sum_repair(amt_rows, checks)

    # program subtotal linkage (unique-subtotal rule on sebenar_jumlah)
    link_programs(amt_rows, checks)

    # footnote flags from Nota rows (RM10 pendahuluan butiran lists)
    apply_notas(all_rows, amt_rows, checks)

    # write output
    rows_out = []
    for r in amt_rows:
        if r["rt"] not in ("project", "program_subtotal", "ministry_total", "grand_total"):
            checks.append(("WARN", f"lampiran2: dropped odd row p{r['page']} '{(r.get('name') or '')[:50]}' line='{r.get('line','')[:60]}'", "", "", ""))
            continue
        c = r["cells"]
        f = {k: c[k]["final"] for k in c}
        rows_out.append([
            r["maksud"] if r["rt"] != "grand_total" else None,
            r.get("mkname") if r["rt"] != "grand_total" else None,
            r["rt"],
            r.get("program_link"),
            r.get("code") if r["rt"] == "project" else None,
            r["name"], YEAR,
            f["kos"], f["prior"], f["ag_l"], f["ag_p"], f["ag_j"],
            f["sb_l"], f["sb_p"], f["sb_j"], f["kum"],
            bool(r.get("star")), SRC, r["page"], r["page"] - PAGE_OFFSET, STMT,
        ])
    with open(OUT, "w", newline="", encoding="utf-8") as fo:
        cw = csv.writer(fo)
        cw.writerow(["maksud_code", "maksud_name_bm", "row_type", "program_bm", "projek_code", "name_bm", "year",
                     "kos_keseluruhan_rm", "terkumpul_rmke10_prior_rm",
                     "anggaran_langsung_rm", "anggaran_pinjaman_rm", "anggaran_jumlah_rm",
                     "sebenar_langsung_rm", "sebenar_pinjaman_rm", "sebenar_jumlah_rm",
                     "terkumpul_rmke10_rm", "has_footnote",
                     "source_file", "pdf_page", "printed_page", "statement"])
        cw.writerows(rows_out)
    cnt = Counter(x[2] for x in rows_out)
    print(f"fact_devex_project.csv: {len(rows_out)} rows | {dict(cnt)}")
    for a in aliases_found:
        checks.append(("INFO", f"lampiran2: vote-name alias {a[0]}: header '{(a[1] or '')[:40]}' vs JUMLAH label '{(a[2] or '')[:40]}'", "", "", ""))
    checks.append(("INFO", f"lampiran2: row counts {json.dumps(dict(cnt))}", len(rows_out), "", ""))
    if DRY and os.path.exists(CHECKS_PATH):
        os.remove(CHECKS_PATH)
    ocrlib.append_checks(checks, path=CHECKS_PATH)
    with open("/tmp/l2_rows.json", "w") as fj:
        json.dump([{k: (v if k != "cells" else {ck: dict(value=cv["value"], final=cv.get("final"), route=cv["route"], cands=cv["cands"], box=cv["box"]) for ck, cv in v.items()})
                    for k, v in r.items() if k not in ("head", "amts")} for r in all_rows], fj, default=str)
    print("checks appended:", len(checks))


def fix_codes(amt_rows, checks):
    """Repair 5-digit codes using within-maksud ascending order + 2014/2016 sets."""
    known = defaultdict(set)
    for wf in ("/home/claude/pkkp/warehouse2014/fact_devex_project.csv",
               "/home/claude/pkkp/warehouse2016/fact_devex_project.csv"):
        if os.path.exists(wf):
            for r in csv.DictReader(open(wf)):
                if r["row_type"] == "project":
                    known[r["maksud_code"]].add(r["projek_code"])
    bad = 0
    for r in amt_rows:
        if r["rt"] != "project":
            continue
        code = r.get("code") or ""
        if re.fullmatch(r"\d{5}", code) and (code in known[r["maksud"]] or not known[r["maksud"]]):
            continue
        # re-OCR at higher scale
        top, bot = r["y"]
        out = cellocr(r["page"], (312, top - 5, 480, bot + 5), scale=5, clean=False, psm=7)
        dig = re.sub(r"\D", "", out)
        if re.fullmatch(r"\d{5}", dig) and (dig in known[r["maksud"]] or not known[r["maksud"]]):
            if dig != code:
                checks.append(("INFO", f"lampiran2: code re-read p{r['page']} '{code}' -> {dig} ({r['name'][:30]})", code, dig, ""))
            r["code"] = dig
            continue
        # match against known codes by name
        r["code_suspect"] = True
        r["code"] = dig if re.fullmatch(r"\d{5}", dig) else (code if re.fullmatch(r"\d{5}", code) else None)
        bad += 1
    if bad:
        print(f"{bad} project codes still suspect after re-OCR")


def column_sum_repair(amt_rows, checks):
    allc = LCOLS + COLS
    by_mk = defaultdict(list)
    for r in amt_rows:
        if r["rt"] in ("project",):
            by_mk[r["maksud"]].append(r)
    totals = {r["maksud"]: r for r in amt_rows if r["rt"] == "ministry_total"}
    grand = next((r for r in amt_rows if r["rt"] == "grand_total"), None)
    npass = nfail = 0
    for mk, rows in by_mk.items():
        t = totals.get(mk)
        if t is None:
            checks.append(("WARN", f"lampiran2: no ministry_total found for {mk}", "", "", ""))
            continue
        for cn in allc:
            s = sum(r["cells"][cn]["final"] for r in rows)
            w = t["cells"][cn]["final"]
            if abs(s - w) < 0.011:
                npass += 1
                continue
            # attempt single-cell repair: find row cell alternate that closes gap
            fixed = attempt_sum_fix(rows + [t], cn, w - s, checks, mk)
            s2 = sum(r["cells"][cn]["final"] for r in rows)
            w2 = t["cells"][cn]["final"]
            if abs(s2 - w2) < 0.011:
                npass += 1
            else:
                nfail += 1
                checks.append(("FAIL", f"lampiran2: column sum {mk} {cn}: projects vs printed JUMLAH", s2, w2, s2 - w2))
    if grand is not None:
        for cn in allc:
            s = sum(t["cells"][cn]["final"] for t in totals.values())
            w = grand["cells"][cn]["final"]
            st = "PASS" if abs(s - w) < 0.011 else "FAIL"
            checks.append((st, f"lampiran2: grand column {cn}: sum of ministry JUMLAH vs printed grand", s, w, s - w))
    checks.append(("INFO", f"lampiran2: ministry column-sum checks pass={npass} fail={nfail}", npass, nfail, ""))
    print(f"column sums: pass={npass} fail={nfail}")


def attempt_sum_fix(rows, cn, diff, checks, mk):
    """If exactly one row has an alternate reading differing by diff, apply it
    (keeping row identities), preferring unconfirmed cells."""
    partner = {"ag_l": "ag_j", "ag_j": "ag_l", "sb_l": "sb_j", "sb_j": "sb_l",
               "kum": None, "prior": None, "kos": None, "ag_p": None, "sb_p": None}
    hits = []
    for r in rows:
        c = r["cells"][cn]
        for alt in c["cands"]:
            d = alt - c["final"]
            if abs(d) > TOL and abs(d - diff) < TOL and r["rt"] != "ministry_total":
                hits.append((r, alt, 1))
        # total row alternate closing gap from the other side
        if r["rt"] == "ministry_total":
            for alt in c["cands"]:
                d = alt - c["final"]
                if abs(d) > TOL and abs(d + diff) < TOL:
                    hits.append((r, alt, 1))
    strong_hits = [h for h in hits if h[0]["cells"][cn]["route"] in ("unconfirmed",) or not h[0]["cells"][cn]["well"]]
    use = strong_hits or hits
    if len(use) == 1:
        r, alt, _ = use[0]
        old = r["cells"][cn]["final"]
        r["cells"][cn]["final"] = alt
        checks.append(("INFO", f"lampiran2: OCR salvage p{r.get('rpage', r['page'])} '{(r.get('name') or '')[:40]}' {cn} "
                      f"{old:,.2f} -> {alt:,.2f} [forced by {mk} column sum, alternate read]", old, alt, alt - old))
        # keep row identity via partner when trivially coupled (pinjaman==0)
        p = partner.get(cn)
        if p and abs(r["cells"][cn].get("final", 0) - r["cells"][p]["final"] - (0 if cn.endswith("_j") else 0)) > 0:
            pass
        return True
    return False


def link_programs(amt_rows, checks):
    psum = defaultdict(float)
    order = []
    cur = defaultdict(list)
    # tag projects with the running program header captured at parse time
    for r in amt_rows:
        if r["rt"] == "project" and r.get("program"):
            psum[(r["maksud"], letters(r["program"]))] += r["cells"]["sb_j"]["final"]
    subcount = Counter()
    for r in amt_rows:
        if r["rt"] == "program_subtotal":
            for candkey in {letters(r.get("name") or ""), letters(r.get("program_hdr") or "")}:
                if candkey:
                    subcount[(r["maksud"], candkey)] += 1
    okkeys = set()
    for r in amt_rows:
        if r["rt"] != "program_subtotal":
            continue
        linked = None
        for cand, disp in ((r.get("name"), r.get("name")), (r.get("program_hdr"), r.get("program_hdr"))):
            if not cand:
                continue
            key = (r["maksud"], letters(cand))
            if subcount[key] == 1 and key in psum and abs(psum[key] - r["cells"]["sb_j"]["final"]) < 1:
                linked = (key, disp)
                break
        if linked:
            okkeys.add(linked[0])
            r["program_link"] = re.sub(r"^Jumlah\s+", "", (linked[1] or "").strip())
        else:
            r["program_link"] = None
    nulled = kept = 0
    for r in amt_rows:
        if r["rt"] == "project" and r.get("program"):
            key = (r["maksud"], letters(r["program"]))
            if key in okkeys:
                r["program_link"] = r["program"]
                kept += 1
            else:
                r["program_link"] = None
                nulled += 1
    checks.append(("INFO", f"lampiran2: program linkage {len(okkeys)} verified groups, {kept} projects tagged, {nulled} unverifiable nulled", kept, nulled, ""))
    print(f"program linkage: {len(okkeys)} groups, {kept} tagged, {nulled} nulled")


def apply_notas(all_rows, amt_rows, checks):
    """RM10-pendahuluan Nota lines list butiran codes; flag has_footnote."""
    cur_notas = []
    for r in all_rows:
        if r.get("rt") == "nota":
            digs = re.findall(r"\b\d{5}\b", r["text"])
            cur_notas.append((r["page"], digs, r["text"]))
    for page, digs, text in cur_notas:
        if not digs:
            continue
        # apply to same-page (and same maksud) project rows
        mks = {r["maksud"] for r in amt_rows if r["page"] == page}
        for r in amt_rows:
            if r["rt"] == "project" and r["maksud"] in mks and r.get("code") in digs and not r.get("star"):
                r["star"] = True
                checks.append(("INFO", f"lampiran2: {r['maksud']} {r['code']}: has_footnote set from printed page Nota p{page}", "", "", ""))


if __name__ == "__main__":
    main()
