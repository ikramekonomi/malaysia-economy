#!/usr/bin/env python3
"""Template-matching digit reader for Lampiran 2 amount cells (PKKP 2015).

The 144-dpi scan defeats tesseract on these small financial digits, but the
numerals are one consistent font. This module learns average glyph templates
(0-9 , .) from cells whose tesseract reads were independently confirmed, then
reads every cell by normalized cross-correlation + a right-to-left Viterbi
over the printed amount grammar

    dd '.' ddd (',' ddd)*      (all amounts print sen; leading group 1-3)

Outputs best string plus per-glyph margins and alternative values for weak
glyphs (consumed by the arithmetic identity solver in the extractor).
"""
import json
import os
import re

import numpy as np
from scipy.ndimage import maximum_filter1d
from skimage.feature import match_template

import ocrlib

TDIR = "/home/claude/pkkp/work/2015/cache"
TPATH = os.path.join(TDIR, "lamp2_templates.npz")

GH = 34               # template height (rows), anchored at glyph-band top
YPAD = 5
JIT = 3               # advance jitter (px)
DIGITS = "0123456789"


def band_of(pno, box, clean=True, pad=10):
    img = ocrlib.get_img(pno, clean=clean)
    x0, y0, x1, y1 = [int(v) for v in box]
    crop = img.crop((max(0, x0 - pad), max(0, y0 - pad),
                     min(img.width, x1 + pad), min(img.height, y1 + pad)))
    a = np.asarray(crop, dtype=np.float32)
    return (220.0 - np.clip(a, 0, 220)) / 220.0


def runs_of(sal, thr=0.12):
    cs = (sal > thr).sum(axis=0)
    runs, start = [], None
    for i, v in enumerate(cs):
        if v > 0 and start is None:
            start = i
        elif v == 0 and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(cs)))
    return runs


def digit_band_top(sal, thr=0.12):
    rs = (sal > thr).sum(axis=1)
    nz = np.nonzero(rs > 1)[0]
    return int(nz[0]) if len(nz) else 0


# ------------------------------------------------------------------ training
def train(samples, out=TPATH):
    """samples: (pno, box, clean, text); text like '1,234.56'."""
    acc = {c: [] for c in DIGITS + ",."}
    adv = {c: [] for c in DIGITS + ",."}
    wid = {c: [] for c in DIGITS + ",."}
    used = skipped = 0
    for pno, box, clean, text in samples:
        text = text.replace(" ", "")
        if not re.fullmatch(r"[\d,]+\.\d{2}", text):
            continue
        sal = band_of(pno, box, clean)
        rr = runs_of(sal)
        chars = list(text)
        if len(rr) != len(chars):
            skipped += 1
            continue
        top = digit_band_top(sal)
        ok = True
        for (s, e), ch in zip(rr, chars):
            w = e - s
            if ch in DIGITS and not (5 <= w <= 24):
                ok = False
            if ch in ",." and w > 12:
                ok = False
        if not ok:
            skipped += 1
            continue
        used += 1
        for i, ((s, e), ch) in enumerate(zip(rr, chars)):
            w = e - s
            seg = sal[max(0, top - 3):max(0, top - 3) + GH, s:e]
            acc[ch].append((seg, w))
            wid[ch].append(w)
            if i + 1 < len(rr):
                adv[ch].append(rr[i + 1][0] - s)
    temps, advs, counts = {}, {}, {}
    for c in acc:
        if not acc[c]:
            continue
        W = int(np.median(wid[c]))
        stack = []
        for seg, w in acc[c]:
            p = np.zeros((GH, W), np.float32)
            seg = seg[:, :W]
            p[:seg.shape[0], :seg.shape[1]] = seg
            stack.append(p)
        temps[c] = np.mean(stack, axis=0)
        advs[c] = float(np.median(adv[c])) if adv[c] else (W + 4.0)
        counts[c] = len(stack)
    np.savez(out, **{f"t_{c}": temps[c] for c in temps},
             meta=json.dumps({c: [advs[c], counts[c]] for c in temps}))
    global _loaded
    _loaded = None
    return counts, used, skipped


_loaded = None


def load_templates(path=TPATH):
    global _loaded
    if _loaded is None:
        z = np.load(path, allow_pickle=True)
        meta = json.loads(str(z["meta"]))
        temps = {c: z[f"t_{c}"] for c in meta}
        _loaded = (temps, {c: meta[c][0] for c in meta})
    return _loaded


# ---------------------------------------------------------------- classify
def glyph_scores(sal, temps, top):
    """score[c][x] = best NCC of template c with left edge at x (y searched)."""
    H, W = sal.shape
    y0 = max(0, top - 3 - YPAD)
    y1 = min(H, top - 3 + GH + YPAD)
    band = sal[y0:y1]
    out = {}
    for c, t in temps.items():
        th, tw = t.shape
        if band.shape[0] < th:
            padb = np.zeros((th, band.shape[1]), np.float32)
            padb[:band.shape[0]] = band
            b = padb
        else:
            b = band
        if b.shape[1] < tw + 2:
            out[c] = np.full(W, -1.0, np.float32)
            continue
        m = match_template(b, t)          # (H-th+1, W-tw+1), anchored top-left
        best = m.max(axis=0)
        sc = np.full(W, -1.0, np.float32)
        sc[:best.shape[0]] = best
        out[c] = sc
    return out


def cell_scores(pno, box, clean=True):
    """(sc dict, x_left, x_right, colink) for one printed instance."""
    temps, advs = load_templates()
    sal = band_of(pno, box, clean)
    rr = runs_of(sal)
    rr = [r for r in rr if sal[:, r[0]:r[1]].sum() > 2.0]
    if not rr:
        return None
    x_left, x_right = rr[0][0], rr[-1][1]
    top = digit_band_top(sal[:, x_left:x_right])
    sc = glyph_scores(sal, temps, top)
    return sc, x_left, x_right, sal


def read_amount(pno, box, clean=True, kbest_margin=0.055, debug=False):
    return read_amount_multi([(pno, box)], clean=clean,
                             kbest_margin=kbest_margin, debug=debug)


def read_amount_multi(instances, clean=True, kbest_margin=0.055, debug=False):
    """Joint decode of one number printed in several cells (same font/layout).
    Scores are aligned at the ink right edge and averaged (with +-2px slack)."""
    temps, advs = load_templates()
    parts = []
    for pno, box in instances:
        cs = cell_scores(pno, box, clean)
        if cs is not None:
            parts.append(cs)
    if not parts:
        return None
    # common coordinate: u = x_right - x  (distance left of right ink edge)
    UMAX = max(xr - xl for _, xl, xr, _ in parts) + 30
    sc = {}
    for c in temps:
        stack = []
        for psc, xl, xr, _ in parts:
            arr = psc[c]
            u = np.full(UMAX, -1.0, np.float32)
            for uu in range(UMAX):
                x = xr - uu
                if 0 <= x < len(arr):
                    lo, hi = max(0, x - 2), min(len(arr) - 1, x + 2)
                    u[uu] = arr[lo:hi + 1].max()
            stack.append(u)
        sc[c] = np.mean(stack, axis=0)
    # ink profile: use the first instance for termination, in u-coords
    _, xl0, xr0, sal0 = parts[0]
    colink = sal0.sum(axis=0)
    inkleft = np.zeros(UMAX, np.float32)   # ink further left than u
    for uu in range(UMAX):
        x = xr0 - uu
        inkleft[uu] = colink[max(0, xl0):max(0, x - 2)].sum() if x - 2 > xl0 else 0.0
    W = UMAX
    NEG = -1e9

    # grammar right-to-left in u-space (u grows leftward from ink right edge)
    plan = ["d", "d", ".", "d", "d", "d"] + [",", "d", "d", "d"] * 4
    maxg = len(plan)
    D = [np.full(W, NEG, np.float32) for _ in range(maxg + 1)]
    BP = [np.full((W, 2), -1, np.int32) for _ in range(maxg + 1)]  # (prev_u, class)
    classes = list(DIGITS + ",.")
    cidx = {c: i for i, c in enumerate(classes)}

    for c in DIGITS:
        tw = temps[c].shape[1]
        for u in range(max(0, tw - JIT - 2), min(W, tw + JIT + 3)):
            v = sc[c][u]
            if v > D[1][u]:
                D[1][u] = v
                BP[1][u] = (-1, cidx[c])
    ends = []
    for g in range(1, maxg):
        kind = plan[g]
        cls = DIGITS if kind == "d" else [kind]
        prev = D[g]
        if not np.any(prev > NEG / 2):
            break
        prevmax = maximum_filter1d(prev, size=2 * JIT + 1)
        newD = D[g + 1]
        newBP = BP[g + 1]
        for c in cls:
            if c not in temps:
                continue
            adv = int(round(advs[c]))
            shifted = np.full(W, NEG, np.float32)
            if adv < W:
                shifted[adv:] = prevmax[:W - adv]
            cand = sc[c] + shifted
            better = cand > newD
            if np.any(better):
                us = np.nonzero(better)[0]
                newD[us] = cand[us]
                for u in us:
                    lo, hi = max(0, u - adv - JIT), max(0, min(W - 1, u - adv + JIT))
                    pu = lo + int(np.argmax(prev[lo:hi + 1]))
                    newBP[u] = (pu, cidx[c])
        if kind == "d" and g >= 3:
            for u in np.nonzero(newD > NEG / 2)[0]:
                if inkleft[u] < 5.0:
                    ends.append((float(newD[u]), g + 1, int(u)))
    if not ends:
        return None
    ends.sort(key=lambda e: -(e[0] / e[1]))
    score, n, u = ends[0]
    chars, us = [], []
    g, cu = n, u
    while g >= 1 and cu >= 0:
        pu, ci = BP[g][cu]
        chars.append(classes[ci])
        us.append(cu)
        cu = pu
        g -= 1
    text = "".join(chars)   # leftmost glyph first
    if not re.fullmatch(r"\d[\d,]*\.\d{2}", text):
        return None
    val = float(re.sub(r"[^\d]", "", text)) / 100.0
    weak, alts, margins = [], [], []
    digpos = [(i, uu) for (i, (ch, uu)) in enumerate(zip(chars, us)) if ch in DIGITS]
    for i, uu in digpos:
        ch = chars[i]
        s1 = float(sc[ch][uu])
        best2, c2 = -1, None
        for c in DIGITS:
            if c == ch:
                continue
            lo, hi = max(0, uu - 2), min(W - 1, uu + 2)
            v = float(np.max(sc[c][lo:hi + 1]))
            if v > best2:
                best2, c2 = v, c
        margins.append((s1 - best2, i, c2))
    for mg, i, c2 in sorted(margins)[:5]:
        if mg < kbest_margin:
            t2 = chars.copy()
            t2[i] = c2
            alt = float(re.sub(r"[^\d]", "", "".join(t2))) / 100.0
            if alt != val:
                alts.append(alt)
                weak.append(i)
    out = dict(text=text, value=val, mean=score / n, alts=alts, weak=weak,
               minmargin=min(m[0] for m in margins) if margins else 1.0)
    if debug:
        out["us"] = us
        out["margins"] = margins
    return out
