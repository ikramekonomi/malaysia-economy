#!/usr/bin/env python3
"""Extract the per-agency sijil registers (Lampiran 2) from the LKAN Agensi volumes.

One row per federal agency whose financial statements received the Auditor-General's
certificate: FY2023 from CMD.4.2025.pdf (LKAN 1/2025, register as at 8 Jan 2025),
FY2024 from CMD.1.2026.pdf (LKAN 1/2026, as at 9 Jan 2026).

Layout notes (both volumes):
- three sub-registers per year (Badan Berkanun Persekutuan; Kumpulan Wang Persekutuan
  dan Akaun Amanah; Agensi Persekutuan Lain), ministries as lettered group headers,
  BIL numbering continuous across all three;
- the opinion column wraps to its own lines with a parenthesised qualifier, and agency
  names wrap above/below their BIL line, so cells are re-assembled by y-distance to
  the nearest BIL anchor;
- the PDFs carry a duplicated, slightly-offset text layer -> pdfplumber dedupe_chars;
- the "Lain" register adds an incorporating-act line under each agency name.

Writes data/fact_agensi_sijil_<year>.csv with per-row pdf_page provenance.
Values kept exactly as printed; never corrected.
"""
import csv
import os
import re

import pdfplumber

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "raw")
DATA = os.path.join(HERE, "..", "data")

VOLUMES = {
    2023: ("CMD.4.2025.pdf", "LKAN 1/2025", range(109, 115)),
    2024: ("CMD.1.2026.pdf", "LKAN 1/2026", range(107, 112)),
}
SECTIONS = (("KUMPULAN WANG PERSEKUTUAN", "kumpulan_wang"),
            ("AGENSI PERSEKUTUAN LAIN", "lain"),
            ("BADAN BERKANUN PERSEKUTUAN", "badan_berkanun"))
NOISE = re.compile(r"^(RAHSIA|Lampiran \d|BIL\.?|JENIS PENDAPAT AUDIT|20\d\d|"
                   r"PIAWAIAN PERAKAUNAN|\d+\s+Lampiran \d|PENYATA KEWANGAN AGENSI.*|"
                   r"YANG DIBERIKAN SIJIL.*|TAHUN 20\d\d.*JANUARI 20\d\d)$")
MINISTRY = re.compile(r"^[A-Z]{1,2}$")
BIL = re.compile(r"^(\d{1,3})\.$")
OPINIONS = ("Tanpa Teguran", "Berteguran", "Bertentangan", "Penafian")
# cells whose only usable text layer is the per-character-spaced duplicate, where
# the generic fold cannot recover printed word spacing; values are the printed
# readings confirmed by the independent two-engine verifier pass (pdftotext
# -layout in-box + pdfplumber) against the page itself
LAYOUT_REPAIRS = {
    (2023, 80): {"agency_name_bm": "Yayasan Pelajaran Persatuan Peladang dan "
                                   "Pertubuhan Peladang Mada (YP MADA)",
                 "agency_abbr": "YP MADA"},
}
QUALIFIERS = ("Penegasan Perkara dan Hal-hal Lain", "Penegasan Perkara",
              "Hal-hal Lain", "Perkara Utama Audit")
QUAL_LEAK = re.compile(r"^\(?(Penegasan|Perkara|Hal-hal|dan Hal-hal)")


def parse_opinion(blob):
    """Normalise an opinion cell robust to loose letter-spacing and wraps."""
    flat = re.sub(r"\s+", "", blob)
    for op in OPINIONS:
        if flat.startswith(op.replace(" ", "")):
            rest = flat[len(op.replace(" ", "")):]
            if not rest:
                return op, ""
            m = re.match(r"^\((.+)\)$", rest)
            if not m:
                # wrapped qualifier re-assembled out of order:
                # "Perkara dan Hal-hal Lain)(Penegasan" -> "(Penegasan Perkara ...)"
                m2 = re.match(r"^([^()]*)\)\((.+)$", rest)
                if m2:
                    m = re.match(r"^\((.+)\)$", f"({m2.group(2)}{m2.group(1)})")
            if m:
                for q in QUALIFIERS:
                    if m.group(1) == q.replace(" ", ""):
                        return op, q
            return op, rest  # keep unrecognised remainder visibly raw
    return blob, ""


def lines_of(page):
    """Deduped (y, left, right) text lines split at the JENIS header x.

    These PDFs are exported from spreads: each page's text layer also contains
    the NEIGHBOURING printed page positioned outside the page box (x<0 or
    x>width), plus a duplicated slightly-offset copy of the real text. Keep only
    in-box words and dedupe aggressively.
    """
    page = page.dedupe_chars(tolerance=1)
    words = [w for w in page.extract_words(x_tolerance=1.5)
             if w["x0"] >= -2 and w["x1"] <= page.width + 2]
    seen, uniq = set(), []
    for w in sorted(words, key=lambda w: (round(w["top"] / 4), w["x0"])):
        key = (w["text"], round(w["x0"] / 4), round(w["top"] / 4))
        if key not in seen:
            seen.add(key)
            uniq.append(w)
    words = uniq
    jenis = [w for w in words if w["text"].startswith("JENIS")]
    boundary = (min(w["x0"] for w in jenis) - 12) if jenis else 0.66 * page.width
    rows = {}
    for w in words:
        key = min(rows, key=lambda k: abs(k - w["top"]), default=None)
        if key is None or abs(key - w["top"]) > 2.5:
            key = w["top"]
            rows[key] = []
        rows[key].append(w)
    out = []
    for k in sorted(rows):
        ws = sorted(rows[k], key=lambda w: w["x0"])
        left = " ".join(w["text"] for w in ws if w["x0"] < boundary).strip()
        right = " ".join(w["text"] for w in ws if w["x0"] >= boundary).strip()
        out.append((k, left, right))
    return out


def extract(year):
    fname, report, pages = VOLUMES[year]
    anchors = []          # [{bil, y, page, section, ...}]
    marks = []            # (page, y, kind, payload) for section/ministry switches
    frags = []            # (page, y, side, text)
    with pdfplumber.open(os.path.join(RAW, fname)) as pdf:
        for pno in pages:
            for y, left, right in lines_of(pdf.pages[pno - 1]):
                up = left.upper()
                hit = next((c for s, c in SECTIONS if s in up), None)
                if hit:
                    marks.append((pno, y, "section", hit))
                    continue
                toks = left.split(None, 1)
                if toks and MINISTRY.match(toks[0]) and len(toks) > 1 and toks[1].isupper():
                    marks.append((pno, y, "ministry", (toks[0], toks[1].strip())))
                    continue
                if toks and BIL.match(toks[0]):
                    anchors.append({"bil": int(toks[0].rstrip(".")), "page": pno, "y": y})
                    if len(toks) > 1 and not NOISE.match(toks[1]):
                        frags.append((pno, y, 0, "L", toks[1].strip()))
                elif left and not NOISE.match(left):
                    # wide qualifier lines start left of the column boundary
                    side = "R" if QUAL_LEAK.match(left) else "L"
                    frags.append((pno, y, 0, side, left))
                if right and not NOISE.match(right) and not right.isdigit():
                    frags.append((pno, y, 1, "R", right))

    # section / ministry state per anchor, by document order (8px slack: a
    # section header's line can register a hair below the first row it governs)
    for a in anchors:
        a["section"], a["ministry_group"], a["ministry_bm"] = "badan_berkanun", "", ""
        for mp, my, kind, payload in marks:
            if (mp, my - 8) <= (a["page"], a["y"]):
                if kind == "section":
                    if payload != a["section"]:
                        # ministry groups restart per sub-register (Lain has
                        # none) — but the section title also repeats as a table
                        # header on every page, which must NOT reset anything
                        a["ministry_group"], a["ministry_bm"] = "", ""
                    a["section"] = payload
                else:
                    a["ministry_group"], a["ministry_bm"] = payload
        a["Lparts"], a["Rparts"] = [], []

    for fp, fy, fx, side, text in frags:
        same = [a for a in anchors if a["page"] == fp]
        if not same:
            continue
        best = min(same, key=lambda a: abs(a["y"] - fy))
        if abs(best["y"] - fy) <= 26:
            best["Lparts" if side == "L" else "Rparts"].append((fy, fx, text))

    recs = []
    for a in sorted(anchors, key=lambda a: (a["page"], a["y"])):
        lparts = [t for _, _, t in sorted(a["Lparts"])]
        act = " ".join(t for t in lparts if t.startswith(("Akta", "[Akta")))
        name = " ".join(t for t in lparts if not t.startswith(("Akta", "[Akta")))
        blob = " ".join(t for _, _, t in sorted(a["Rparts"]))
        # a qualifier's opening fragment can end up glued to the name line
        leak = re.search(r"\(\s*(?:Penegasan|Perkara|Hal-hal)[^)]*$", name)
        if leak:
            blob = f"{blob} {leak.group(0)}"
            name = name[:leak.start()].strip()
        opinion, qualifier = parse_opinion(blob.strip())
        # rows the duplicated text layer renders with per-character spacing:
        # fold runs of single-character tokens back into words
        if len([t for t in name.split() if len(t) == 1]) >= 3:
            folded, carry = [], ""
            for tok in name.split():
                if len(tok) == 1 and tok not in "-–":
                    carry += tok
                else:
                    folded.append(carry + tok)
                    carry = ""
            if carry:
                folded.append(carry)
            name = " ".join(folded)
        am = re.search(r"\(([^()]+)\)\s*$", name)
        fix = LAYOUT_REPAIRS.get((year, a["bil"]), {})
        name = fix.get("agency_name_bm", name)
        am = re.search(r"\(([^()]+)\)\s*$", name)
        recs.append({
            "year": year, "register": a["section"], "bil": a["bil"],
            "ministry_group": a["ministry_group"], "ministry_bm": a["ministry_bm"],
            "agency_name_bm": name,
            "agency_abbr": fix.get("agency_abbr", am.group(1) if am else ""),
            "opinion": opinion, "opinion_qualifier": qualifier,
            "incorporating_act": act, "report": report,
            "source_file": fname, "pdf_page": a["page"],
        })
    return recs


def main():
    for year in sorted(VOLUMES):
        recs = extract(year)
        dest = os.path.join(DATA, f"fact_agensi_sijil_{year}.csv")
        cols = ["year", "register", "bil", "ministry_group", "ministry_bm",
                "agency_name_bm", "agency_abbr", "opinion", "opinion_qualifier",
                "incorporating_act", "report", "source_file", "pdf_page"]
        with open(dest, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(recs)
        clean = sum(1 for r in recs if r["opinion"] in OPINIONS)
        bils = [r["bil"] for r in recs]
        gaps = [b for prev, b in zip(bils, bils[1:]) if b != prev + 1]
        print(f"{year}: {len(recs)} rows, opinions parsed {clean}, "
              f"bil {min(bils)}..{max(bils)}, sequence breaks at {gaps or 'none'} -> {dest}")


if __name__ == "__main__":
    main()
