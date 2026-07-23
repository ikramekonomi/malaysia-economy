"""Shared OCR utilities for the PKKP 2015 volume (NO text layer; 144-dpi JPEG
scans OCR'd at 400 dpi with tesseract, rules stripped -- see ../preprocess.py).

Artifacts per page N (1..306), zero-padded 3 digits:
  /home/claude/pkkp/work/2015/png/p-NNN.png   cleaned 400-dpi grayscale render
  /home/claude/pkkp/work/2015/tsv/p-NNN.tsv   tesseract TSV (psm 6)
  /home/claude/pkkp/work/2015/txt/p-NNN.txt   tesseract plain text (psm 6)

printed_page = pdf_page - 14 throughout the statement sections.
Amount conventions: exact RM as printed (sen kept); en-dash = 0.0;
parentheses = negative; '*' -> has_footnote.
"""
import csv
import os
import re
import subprocess

WORK = "/home/claude/pkkp/work/2015"
SRC = "2015_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
YEAR = 2015
PRIOR = 2014
PAGE_OFFSET = 14  # printed = pdf - 14

NUMRE = re.compile(r"^\*?\(?[\d,]+(?:\.\d{1,2})?\)?$")
DASHRE = re.compile(r"^[-–—_=~.·]{1,3}$")


def parse_amount(tok):
    tok = str(tok).strip().replace("*", "").replace(" ", "")
    if tok in {"–", "-", "—", "_", ""}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()").replace(",", "").strip(".") or "0"
    v = float(tok)
    return -v if neg else v


def page_txt(pno):
    with open(f"{WORK}/txt/p-{pno:03d}.txt", encoding="utf-8") as f:
        return f.read()


def load_words(pno):
    """All TSV words: dicts with text,left,right,top,bottom,conf."""
    words = []
    with open(f"{WORK}/tsv/p-{pno:03d}.tsv", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            t = (r.get("text") or "").strip()
            if not t:
                continue
            left, top = int(r["left"]), int(r["top"])
            w, h = int(r["width"]), int(r["height"])
            words.append(dict(text=t, left=left, right=left + w, top=top,
                              bottom=top + h, conf=float(r.get("conf", 0))))
    words.sort(key=lambda w: (w["top"], w["left"]))
    return words


def cluster_lines(words, ytol=14):
    """Cluster words into lines by top coordinate. Returns list of
    (top, bottom, [words sorted by left])."""
    lines = []
    for w in sorted(words, key=lambda x: x["top"]):
        for ln in lines:
            if abs(w["top"] - ln["top"]) <= ytol:
                ln["ws"].append(w)
                break
        else:
            lines.append(dict(top=w["top"], ws=[w]))
    out = []
    for ln in sorted(lines, key=lambda l: l["top"]):
        ws = sorted(ln["ws"], key=lambda x: x["left"])
        top = min(x["top"] for x in ws)
        bot = max(x["bottom"] for x in ws)
        out.append((top, bot, ws))
    return out


def merge_number_fragments(ws, maxgap=24):
    """Merge adjacent numeric fragments OCR split ('148,631 ,837.65')."""
    merged = []
    for w in ws:
        if merged:
            p = merged[-1]
            gap = w["left"] - p["right"]
            if (gap < maxgap and re.match(r"^[\d,().*]+$", p["text"])
                    and re.match(r"^[\d,().]+$", w["text"])
                    and not (NUMRE.match(p["text"]) and NUMRE.match(w["text"])
                             and len(p["text"]) > 4 and len(w["text"]) > 4)):
                p = dict(p)
                p["text"] += w["text"]
                p["right"] = w["right"]
                merged[-1] = p
                continue
        merged.append(dict(w))
    return merged


from collections import OrderedDict

_page_img = OrderedDict()
_PAGE_IMG_CAP = 24     # LRU-evict beyond this many cached page images


def get_img(pno, clean=True):
    from PIL import Image
    key = (pno, clean)
    if key not in _page_img:
        if clean:
            _page_img[key] = Image.open(f"{WORK}/png/p-{pno:03d}.png").convert("L")
        else:
            # re-render the raw page (no rule-strip) at 400 dpi; keep the pgm
            # on disk so an evicted page reloads without re-rendering
            tmp = f"/tmp/reraw-{pno}"
            if not os.path.exists(f"{tmp}-{pno:03d}.pgm"):
                subprocess.run(["pdftoppm", "-r", "400", "-gray", "-f", str(pno),
                                "-l", str(pno), f"{WORK}/2015.pdf", tmp], check=True)
            _page_img[key] = Image.open(f"{tmp}-{pno:03d}.pgm").convert("L")
        while len(_page_img) > _PAGE_IMG_CAP:
            _page_img.popitem(last=False)
    else:
        _page_img.move_to_end(key)
    return _page_img[key]


def save_crop(pno, box, out, scale=1, clean=True):
    """Save a crop of page pno (box = x0,y0,x1,y1 in 400-dpi px) for
    eye-verification via the Read tool."""
    from PIL import Image
    img = get_img(pno, clean=clean)
    x0, y0, x1, y1 = [int(v) for v in box]
    crop = img.crop((max(0, x0), max(0, y0), min(img.width, x1), min(img.height, y1)))
    if scale != 1:
        crop = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
    crop.save(out)
    return out


def cell_ocr(pno, box, whitelist="0123456789,.()-*", psm=7, scale=3, clean=True):
    """Re-OCR a small region (box in 400-dpi px) with digit whitelist.
    Returns raw token string ('' if nothing)."""
    from PIL import Image
    img = get_img(pno, clean=clean)
    x0, y0, x1, y1 = [int(v) for v in box]
    crop = img.crop((max(0, x0 - 2), max(0, y0 - 2),
                     min(img.width, x1 + 3), min(img.height, y1 + 3)))
    big = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
    tmp = f"/tmp/cell_{os.getpid()}.png"
    big.save(tmp)
    args = ["tesseract", tmp, "stdout", "--psm", str(psm)]
    if whitelist:
        args += ["-c", f"tessedit_char_whitelist={whitelist}"]
    out = subprocess.run(args, capture_output=True, text=True).stdout.strip()
    return out.replace(" ", "")


def dark_stats(pno, box, clean=True, thresh=128):
    """(dark_pixel_count, width_of_ink, height_of_ink) inside box -- for
    dash/empty discrimination."""
    img = get_img(pno, clean=clean)
    x0, y0, x1, y1 = [int(v) for v in box]
    crop = img.crop((max(0, x0), max(0, y0), min(img.width, x1), min(img.height, y1)))
    px = crop.load()
    xs, ys, dark = [], [], 0
    for yy in range(crop.height):
        for xx in range(crop.width):
            if px[xx, yy] < thresh:
                dark += 1
                xs.append(xx)
                ys.append(yy)
    if not xs:
        return 0, 0, 0
    return dark, max(xs) - min(xs), max(ys) - min(ys)


def append_checks(rows, path="/home/claude/pkkp/warehouse2015/_validation_checks_2015.csv"):
    """rows: (status, check, extracted_value, printed_value, difference)."""
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["status", "check", "extracted_value", "printed_value", "difference"])
        for r in rows:
            w.writerow(r)
