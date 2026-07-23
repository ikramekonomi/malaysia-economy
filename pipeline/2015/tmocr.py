"""Template-correlation digit OCR for the 2015 volume's numeric cells.

tesseract misreads a large share of numeric cells on this 144-dpi JPEG scan
(confusions 3<->8, 5<->6, 0<->9, 4<->1).  The tables however use ONE upright
sans font for every value cell, so a scan-self-trained template classifier
far outperforms a generic engine:

  1. HARVEST -- every page-TSV word that (a) parses as a well-formed amount,
     (b) has tesseract confidence >= 88, and (c) segments into exactly
     len(token) glyphs with per-char plausible widths, contributes labeled
     glyph bitmaps cut from the RAW 400-dpi render.  Tens of thousands of
     samples -> per-char mean templates (height-normalised to 32 px).
  2. DECODE -- a cell strip is height-normalised the same way; every template
     is slid across it (normalised cross-correlation); dynamic programming
     picks the char sequence that best tiles the ink (skipping ink is
     penalised, background gaps are free).

The decoder returns (string, mean_corr).  Callers treat mean_corr >= .8 reads
as a strong independent source ('tm') beside the tesseract reads.
"""
import csv
import os
import pickle
import re
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, "/home/claude/pkkp/work/2015/pipeline")
import ocrlib

WORK = ocrlib.WORK
H = 32                      # normalised glyph height
CHARS = "0123456789,."      # decoded alphabet (dash cells handled upstream)
AMT = re.compile(r"^\d{1,3}(?:,\d{3})+(?:\.\d{2})?$|^\d{2,6}(?:\.\d{2})?$")
TMPL_PATH = f"{WORK}/tm_templates.pkl"

# plausible ink-span widths at 400 dpi (pre-normalisation)
WIDTH_OK = {c: (12, 30) for c in "023456789"}
WIDTH_OK["1"] = (4, 16)
WIDTH_OK[","] = (2, 12)
WIDTH_OK["."] = (2, 10)
THRESH = 178


def _main_band(arr):
    """Rows spanned by the digit bodies (excludes comma descenders and
    speckle): contiguous run of rows with ink >= 20% of the peak row-ink."""
    ink = (arr < THRESH)
    prof = ink.sum(axis=1).astype(float)
    if prof.max() <= 0:
        return None
    thr = 0.2 * prof.max()
    good = np.where(prof >= thr)[0]
    return good.min(), good.max()


def _spans(arr):
    """Ink column spans of a grey 2D array."""
    ink = (arr < THRESH)
    proj = ink.sum(axis=0)
    spans = []
    x = 0
    W = len(proj)
    while x < W:
        if proj[x] > 0:
            x1 = x
            while x1 < W and proj[x1] > 0:
                x1 += 1
            spans.append((x, x1))
            x = x1
        else:
            x += 1
    return spans


def _norm_patch(arr, w_out=None):
    """Height-normalise an ink patch to H rows (ink bbox), return float array
    ink-intensity 0..1."""
    ink = (arr < THRESH)
    rows = np.where(ink.any(axis=1))[0]
    if len(rows) == 0:
        return None
    a = arr[rows.min():rows.max() + 1]
    img = Image.fromarray(a.astype(np.uint8))
    scale = H / img.height
    w = w_out or max(2, int(round(img.width * scale)))
    img = img.resize((w, H), Image.LANCZOS)
    f = 1.0 - np.asarray(img, dtype=np.float32) / 255.0
    return f


def harvest(pages, min_conf=78, min_per_char=25):
    samples = {c: [] for c in CHARS}
    widths = {c: [] for c in CHARS}
    for pno in pages:
        tsvp = f"{WORK}/tsv/p-{pno:03d}.tsv"
        if not os.path.exists(tsvp):
            continue
        try:
            img = ocrlib.get_img(pno, clean=False)
        except Exception:
            continue
        arr_full = np.asarray(img)
        for r in csv.DictReader(open(tsvp), delimiter="\t", quoting=csv.QUOTE_NONE):
            t = (r.get("text") or "").strip()
            if not t or not AMT.match(t) or float(r.get("conf", 0)) < min_conf:
                continue
            left, top = int(r["left"]), int(r["top"])
            w, h = int(r["width"]), int(r["height"])
            if left < 1500 or h < 20 or h > 45:
                continue
            a = arr_full[max(0, top - 2): top + h + 2, max(0, left - 2): left + w + 3]
            spans = _spans(a)
            if len(spans) != len(t):
                continue
            ok = True
            for ch, (x0, x1) in zip(t, spans):
                lo, hi = WIDTH_OK.get(ch, (2, 30))
                if not (lo <= x1 - x0 <= hi):
                    ok = False
                    break
            if not ok:
                continue
            # digits normalised over the token's main (digit-body) band
            mb = _main_band(a)
            if mb is None:
                continue
            rtop, rbot = mb
            if rbot - rtop < 18:
                continue
            for ch, (x0, x1) in zip(t, spans):
                if not ch.isdigit():
                    continue
                ga = a[rtop:rbot + 1, x0:x1]
                gi = Image.fromarray(ga.astype(np.uint8))
                sc = H / gi.height
                gi = gi.resize((max(2, int(round(gi.width * sc))), H), Image.LANCZOS)
                f = 1.0 - np.asarray(gi, dtype=np.float32) / 255.0
                samples[ch].append(f)
                widths[ch].append(f.shape[1])
    def _ncc(a, b):
        az, bz = a - a.mean(), b - b.mean()
        return float((az * bz).sum() / ((np.sqrt((az * az).sum()) + 1e-6)
                                        * (np.sqrt((bz * bz).sum()) + 1e-6)))

    tmpl = {}
    normed = {}
    for c in CHARS:
        if len(samples[c]) < (min_per_char if c.isdigit() else 8):
            continue
        wmed = int(round(np.median(widths[c])))
        fs = []
        for f in samples[c]:
            if f.shape[1] != wmed:
                f = np.asarray(Image.fromarray(
                    ((1 - f) * 255).astype(np.uint8)).resize((wmed, H), Image.LANCZOS),
                    dtype=np.float32)
                f = 1.0 - f / 255.0
            fs.append(f)
        normed[c] = fs
        tmpl[c] = np.mean(fs, axis=0)
    # purification: tesseract's own confusions (3<->8, 5<->6, 0<->9) pollute
    # the labels; iteratively drop samples that fit their label worse than a
    # competing char's template, then re-average
    for _ in range(3):
        newtmpl = {}
        for c, fs in normed.items():
            keep = []
            for f in fs:
                self_c = _ncc(f, tmpl[c] if tmpl[c].shape == f.shape else tmpl[c])
                rival = -1.0
                for c2, t2 in tmpl.items():
                    if c2 == c or t2.shape[1] < 6 or abs(t2.shape[1] - f.shape[1]) > 6:
                        continue
                    t2r = t2
                    if t2.shape != f.shape:
                        t2r = np.asarray(Image.fromarray(((1 - t2) * 255).astype(np.uint8))
                                         .resize((f.shape[1], H), Image.LANCZOS), dtype=np.float32)
                        t2r = 1.0 - t2r / 255.0
                    rival = max(rival, _ncc(f, t2r))
                if self_c >= rival - 0.02 and self_c > 0.5:
                    keep.append(f)
            if len(keep) >= 8:
                normed[c] = keep
                newtmpl[c] = np.mean(keep, axis=0)
            else:
                newtmpl[c] = tmpl[c]
        tmpl = newtmpl
    counts = {c: len(samples[c]) for c in CHARS}
    # synthetic fallback for undersampled chars (Liberation Sans ~ the print
    # font), blurred to approximate the scan
    missing = [c for c in CHARS if c not in tmpl]
    if missing:
        from PIL import ImageDraw, ImageFont, ImageFilter
        # calibrate synth size so digit widths match harvested medians
        med_dig = np.median([w for c in "0234567" if widths.get(c)
                             for w in widths[c]]) if any(widths.get(c) for c in "0234567") else 21
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 120)
        for c in missing:
            im = Image.new("L", (200, 200), 255)
            d = ImageDraw.Draw(im)
            d.text((40, 40), c, font=font, fill=0)
            im = im.filter(ImageFilter.GaussianBlur(2.5))
            a = np.asarray(im)
            ink = a < 200
            if not ink.any():
                continue
            rs = np.where(ink.any(axis=1))[0]
            cs = np.where(ink.any(axis=0))[0]
            g = a[rs.min():rs.max() + 1, cs.min():cs.max() + 1]
            gi = Image.fromarray(g)
            if c.isdigit():
                sc = H / gi.height
                gi = gi.resize((max(2, int(round(gi.width * sc))), H), Image.LANCZOS)
            else:
                # comma/period: shrink to observed size relative to digits
                sc = (H * 0.28) / gi.height if c in ",." else H / gi.height
                gw = max(3, int(round(gi.width * sc)))
                gh = max(3, int(round(gi.height * sc)))
                small = gi.resize((gw, gh), Image.LANCZOS)
                canvas = Image.new("L", (gw, H), 255)
                # comma sits at baseline (bottom), period likewise
                canvas.paste(small, (0, H - gh - (2 if c == "." else -2 if c == "," else 0)))
                gi = canvas
            f = 1.0 - np.asarray(gi, dtype=np.float32) / 255.0
            tmpl[c] = f
            counts[c] = 0
    return tmpl, counts


_templates = None


def load_templates():
    global _templates
    if _templates is None:
        if os.path.exists(TMPL_PATH):
            with open(TMPL_PATH, "rb") as f:
                _templates = pickle.load(f)
        else:
            raise RuntimeError("run tmocr.py harvest first")
    return _templates


def _corr_maps(strip, tmpls):
    """corr maps for many templates at once, grouped by width.
    Returns {char: corr array over x}."""
    from numpy.lib.stride_tricks import sliding_window_view
    Hs, W = strip.shape
    out = {}
    bywidth = {}
    for c, t in tmpls.items():
        bywidth.setdefault(t.shape[1], []).append(c)
    for w, chars in bywidth.items():
        if W < w:
            for c in chars:
                out[c] = np.full(1, -1.0, dtype=np.float32)
            continue
        win = sliding_window_view(strip, (Hs, w))[0]      # (P, Hs, w)
        P = win.shape[0]
        wf = win.reshape(P, -1).astype(np.float32)
        wm = wf.mean(axis=1, keepdims=True)
        wz = wf - wm
        wn = np.sqrt((wz * wz).sum(axis=1)) + 1e-6
        T = np.stack([tmpls[c] for c in chars]).reshape(len(chars), -1).astype(np.float32)
        Tz = T - T.mean(axis=1, keepdims=True)
        Tn = np.sqrt((Tz * Tz).sum(axis=1)) + 1e-6
        cc = (wz @ Tz.T) / (wn[:, None] * Tn[None, :])
        for k, c in enumerate(chars):
            out[c] = cc[:, k]
    return out


def decode_cell(arr, min_corr=0.55):
    """arr: grey 2D numpy of the cell strip (raw render). Return
    (string, mean_corr) or ("", 0)."""
    tmpl = load_templates()
    arr = np.asarray(arr, dtype=np.uint8).copy()
    ink = (arr < THRESH)
    # strip box/table rules: near-full rows and columns of ink
    rowfrac = ink.mean(axis=1)
    colfrac = ink.mean(axis=0)
    arr[rowfrac > 0.6, :] = 255
    arr[:, colfrac > 0.8] = 255
    # kill residual 1-2px speckle rows at crop edges
    ink = (arr < THRESH)
    if ink.sum() < 12:
        return "", 0.0, []
    rows = np.where(ink.sum(axis=1) >= 2)[0]
    if len(rows) == 0 or rows.max() - rows.min() < 12:
        return "–", 1.0, []
    mb = _main_band(arr)
    if mb is None or mb[1] - mb[0] < 14:
        return "–", 1.0, []
    rtop, rbot = mb
    cols = np.where(ink[rtop:rbot + 1].sum(axis=0) >= 1)[0]
    if len(cols) == 0:
        return "", 0.0, []
    a = arr[rtop:rbot + 1, cols.min():cols.max() + 1]
    img = Image.fromarray(a.astype(np.uint8))
    sc = H / img.height
    img = img.resize((max(4, int(round(img.width * sc))), H), Image.LANCZOS)
    strip = 1.0 - np.asarray(img, dtype=np.float32) / 255.0
    W = strip.shape[1]
    # skip cost weighted by ink in the upper 3/4 of the band: commas and
    # periods live near the baseline and may be skipped cheaply
    inkcol = strip[: int(H * 0.72)].sum(axis=0)
    corr = _corr_maps(strip, {c: t for c, t in tmpl.items() if c.isdigit()})
    # DP over x: dp[x] = (score, prev_x, char)
    NEG = -1e9
    dp = np.full(W + 1, NEG, dtype=np.float64)
    dp[0] = 0.0
    bk = [None] * (W + 1)
    skip_pen = 0.06
    for x in range(W):
        if dp[x] <= NEG / 2:
            continue
        # skip this column
        pen = skip_pen * inkcol[x]
        if dp[x] - pen > dp[x + 1]:
            dp[x + 1] = dp[x] - pen
            bk[x + 1] = (x, None)
        # place a char here
        for c, cm in corr.items():
            w = tmpl[c].shape[1]
            if x >= len(cm):
                continue
            cc = cm[x]
            thr = min_corr + (0.12 if w <= 12 else 0.0)
            if cc < thr:
                continue
            gain = (cc - min_corr) * (1.0 + 0.06 * w) - 0.10
            nx = x + w
            if nx > W:
                continue
            if dp[x] + gain > dp[nx]:
                dp[nx] = dp[x] + gain
                bk[nx] = (x, c)
    # best end position (allow trailing background)
    x = W
    out = []       # (char, x0, x1, corr)
    while x > 0 and bk[x] is not None:
        px, c = bk[x]
        if c is not None:
            out.append((c, px, x, float(corr[c][px])))
        x = px
    if x != 0:
        return "", 0.0
    out.reverse()
    if not out:
        return "", 0.0
    # split into tokens at gaps > ~1.5 digit widths; the value is the
    # RIGHTMOST token (crops may catch the previous column's tail)
    toks = [[out[0]]]
    for g in out[1:]:
        if g[1] - toks[-1][-1][2] > 30:
            toks.append([g])
        else:
            toks[-1].append(g)
    last = toks[-1]
    s = "".join(g[0] for g in last)
    sc = float(np.mean([g[3] for g in last]))
    # close alternates per position (confusable second-best chars)
    alts = []
    for k, (c, px, x1, cc) in enumerate(last):
        for c2, cm2 in corr.items():
            if c2 == c or px >= len(cm2):
                continue
            if cm2[px] >= cc - 0.06:
                alts.append((k, c2))
    return s, sc, alts


def decode_box(pno, x0, y0, x1, y1):
    img = ocrlib.get_img(pno, clean=False)
    a = np.asarray(img)[int(y0):int(y1), int(x0):int(x1)]
    return decode_cell(a)


if __name__ == "__main__":
    if sys.argv[1] == "harvest":
        pages = range(80, 242)
        tmpl, counts = harvest(pages)
        print("glyph sample counts:", counts)
        print("templates built for:", sorted(tmpl.keys()))
        with open(TMPL_PATH, "wb") as f:
            pickle.dump(tmpl, f)
    elif sys.argv[1] == "test":
        # oracle benchmark on jumlah_maksud rows
        import difflib
        ORACLE = {}
        for r in csv.DictReader(open("/home/claude/pkkp/warehouse2015/fact_opex_maksud.csv")):
            ORACLE[r["maksud_name_bm"].upper()] = (
                float(r["anggaran_asal_rm"]), float(r["anggaran_dipinda_rm"]))
        def ratio(a, b):
            return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()
        hits = tot = 0
        found = 0
        for pno in range(80, 140):
            try:
                ws = ocrlib.load_words(pno)
            except FileNotFoundError:
                continue
            for top, bot, lws in ocrlib.cluster_lines(ws, 16):
                if top < 1000 or top > 4400:
                    continue
                lab = " ".join(w["text"] for w in lws if w["right"] < 1650)
                if not lab.upper().startswith(("JUML", "JUMI", "JOM", "JUMA", "JUM")):
                    continue
                rest = re.sub(r"^\S+\s*", "", lab)
                best = max(ORACLE, key=lambda k: ratio(rest[:len(k) + 4], k))
                if ratio(rest[:len(best) + 4], best) < 0.62:
                    continue
                a5, d5 = ORACLE[best]
                found += 1
                for anchor, want in ((1930, a5), (2272, d5)):
                    s, c, _alts = decode_box(pno, anchor - 400, top - 4, anchor + 10, bot + 4)
                    digs = re.sub(r"[^0-9]", "", s)
                    got = float(digs) if digs else None
                    ok = got is not None and abs(got - want) < 0.5
                    hits += ok
                    tot += 1
                    if not ok:
                        print(f"  miss p{pno} y{top}: decoded {s!r} ({c:.2f}) want {want:,.0f}")
        print(f"rows {found}; cell accuracy {hits}/{tot} = {hits/max(tot,1):.0%}")
