#!/usr/bin/env python3
"""Structural parse probe for Lampiran 2 (PKKP 2015, pdf 242-271, two-page
spreads). Stage 1: left pages (even) rows; Stage 2: right pages (odd) column
anchors + row grouping. Diagnostics only -- extraction lives in
extract_lampiran2_projects.py which imports these functions.
"""
import re
import sys

sys.path.insert(0, "/home/claude/pkkp/work/2015/pipeline")
import ocrlib

LEFT_PAGES = list(range(242, 271, 2))
RIGHT_PAGES = list(range(243, 272, 2))

NUMISH = re.compile(r"^[\d,.()*OoSeGIl|!]+$")
HASDIG = re.compile(r"\d")


def letters(s):
    return re.sub(r"[^A-Za-z]", "", s or "")


def fuzzy_eq(a, b, maxdiff=2):
    """Loose Levenshtein<=maxdiff on letters-only uppercase."""
    a, b = letters(a).upper(), letters(b).upper()
    if abs(len(a) - len(b)) > maxdiff:
        return False
    # small DP
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
        if min(prev) > maxdiff:
            return False
    return prev[-1] <= maxdiff


def amountish(w):
    """Token that plausibly belongs to an amount column (digits/dash)."""
    t = w["text"]
    if ocrlib.DASHRE.match(t):
        return True
    if not HASDIG.search(t):
        # OCR of digits as letters (OO, Se) only counts if attached to digits later
        return False
    return bool(re.match(r"^[\d,.()*OoSl|!~—–-]+$", t))


def parse_left_page(pno):
    """Return dict with header info and raw row records."""
    words = ocrlib.load_words(pno)
    lines = ocrlib.cluster_lines(words, ytol=14)
    out = dict(pno=pno, rows=[], headers=[], notes=[], skipped=[])
    for top, bot, ws in lines:
        ws = ocrlib.merge_number_fragments(ws, maxgap=28)
        texts = [w["text"] for w in ws]
        line = " ".join(texts)
        # split head vs amounts: amount tokens sit right of x=1650
        amts = [w for w in ws if w["left"] > 1650 and amountish(w)]
        head = [w for w in ws if w not in amts]
        headtxt = " ".join(w["text"] for w in head)
        L = letters(headtxt).upper()
        y = (top, bot)
        # boilerplate
        if not head and not amts:
            continue
        if (fuzzy_eq(" ".join(texts[:3]), "PENYATA KEWANGAN KERAJAAN", 4)
                or L.startswith(("PENYATAKEWANGAN", "PENYATAPERBELANJAAN"))
                or L.startswith("BAGITAHUN")
                or fuzzy_eq(headtxt, "Maksud Perbelanjaan Kos Keseluruhan Sebenar RMKe-10", 12)
                or (("MAKSUD" in L or "KESEL" in L or "KOSKE" in L) and top < 900)
                or (L.startswith("HINGGA") and top < 900)
                or (L in ("", "AN", "AL", "ANM") and len(headtxt) < 6)
                or L.startswith("PERBEAENAAI") or (top < 900 and "RMKE" in L)
                or L.startswith(("SAMBUNGAN", "FSAMBUNGAN", "TSAMBUNGAN"))):
            out["skipped"].append((y, line))
            continue
        first = head[0] if head else None
        if head and (fuzzy_eq(head[0]["text"], "Nota", 1) or L.startswith("NOTA")):
            out["notes"].append((y, line))
            continue
        # classification
        rec = dict(y=y, ws=ws, head=head, amts=amts, line=line)
        if head and first["left"] < 470:
            code_tok = first["text"]
            rest = head[1:]
            caps = letters(" ".join(w["text"] for w in rest))
            if rest and caps and caps == caps.upper() and not amts and len(caps) > 5:
                rec["kind"] = "maksud_header"
            elif re.match(r"^\*?[\dOoQGSseflc€un]{4,6}$", code_tok) and rest:
                rec["kind"] = "project"
            elif letters(code_tok).upper().startswith(("JUM", "UUM", "IUM", "JUR", "UM")) and "JUMLAHPERBELANJAANPEMBANGUNAN" in L.replace(" ", ""):
                rec["kind"] = "grand_total"
            elif fuzzy_eq(code_tok, "JUMLAH", 2) and caps == caps.upper():
                rec["kind"] = "jumlah_caps"
            else:
                rec["kind"] = "unknown_left"
        else:
            w0 = head[0]["text"] if head else ""
            if fuzzy_eq(w0, "Jumlah", 2) and head and head[0]["text"][:1].isupper() and not letters(headtxt).isupper():
                rec["kind"] = "jumlah_program"
            elif fuzzy_eq(w0, "JUMLAH", 2) and letters(headtxt).upper() == letters(headtxt):
                # JUMLAH at name-column x (some ministries)
                if "PERBELANJAANPEMBANGUNAN" in L.replace(" ", ""):
                    rec["kind"] = "grand_total"
                else:
                    rec["kind"] = "jumlah_caps"
            elif not amts and letters(headtxt) and letters(headtxt) == letters(headtxt).upper():
                rec["kind"] = "program_header"
            elif not amts:
                rec["kind"] = "wrap"
            else:
                rec["kind"] = "unknown"
        out["rows"].append(rec)
    return out


def right_page_tokens(pno):
    """Numeric/dash tokens on a right page, with per-page column anchors."""
    words = ocrlib.load_words(pno)
    toks = []
    for w in words:
        t = w["text"]
        if w["top"] < 900:
            continue
        if ocrlib.DASHRE.match(t) or (HASDIG.search(t) and re.match(r"^[\d,.()*OoSGl|!~—–-]+$", t)):
            toks.append(w)
    return toks


if __name__ == "__main__":
    for pno in LEFT_PAGES:
        out = parse_left_page(pno)
        from collections import Counter
        kinds = Counter(r["kind"] for r in out["rows"])
        print(f"p{pno}: {dict(kinds)} notes={len(out['notes'])}")
        for r in out["rows"]:
            if r["kind"].startswith("unknown"):
                print("   ??", r["y"][0], r["line"][:110])
            if r["kind"] in ("maksud_header", "jumlah_caps", "grand_total"):
                print("   >>", r["kind"], r["y"][0], r["line"][:100])
