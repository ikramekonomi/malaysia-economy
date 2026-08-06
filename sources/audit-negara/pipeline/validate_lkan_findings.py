#!/usr/bin/env python3
"""Validate data/fact_lkan_findings.csv + fact_lkan_audits.csv against the text.

Checks (results -> data/_validation_lkan_findings.csv, PASS/FAIL per row):
1. maklum_balas coverage — per volume, response-marker entries in the findings
   CSV vs an independent recount over the chapter page ranges. The recount does
   not reuse the extractor's unit segmentation: full-width chapters are scanned
   line-by-line with the master marker regex (with the same Sumber:-citation
   guard); margin chapters count label-column lines that open with "Maklum"
   (the label column is located from the section-word anchors only).
2. section_path continuity — numbered chapters: 5.x runs 1..max without gaps,
   5.x.y restarts at 1 per x without gaps; margin chapters: paragraph ranges
   strictly increasing and non-overlapping (labels are not required to cover
   every paragraph — sections may carry unlabelled paragraphs).
3. every finding's pdf_page lies inside its chapter's pdf range.
4. chapter counts per volume match the scoped inventory.
5. every rm_amounts token matches ^RM[\\d.,]+( (juta|bilion))?$ and does not
   end in stray punctuation, unless listed verbatim in
   data/_source_anomalies_lkan.csv.

Discrepancies are reported, never silently corrected.
"""
import csv
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
sys.path.insert(0, HERE)
from extract_lkan_findings import volume_pages, NOISE, MONTHS  # noqa: E402

EXPECT_CHAPTERS = {"CMD.8.2024.pdf": 9, "CMD.9.2024.pdf": 8, "CMD.5.2025.pdf": 5,
                   "CMD.2.2026.pdf": 4, "CMD.14.2025.pdf": 8}
MARGIN = "margin_label"
RM_OK = re.compile(r"^RM[\d.,]+( (juta|bilion))?$")
MARKER = re.compile(
    r"^Maklum\s+[Bb]alas\s+(?:yang\s+[Dd]iterima\s+daripada\s+)?"
    r"(?P<ent>[A-Za-z0-9 .,&()/\-']*?)\s*"
    r"(?:[Yy]ang\s+)?(?:[Dd]iterima(?:\s+masing-masing)?\s+(?:pada|antara)|"
    r"[Bb]ertarikh|[Pp]ada)\s+\d")


def clean_lines(pages, a, b):
    out = []
    for p in range(a, b + 1):
        for ln in pages[p - 1].split("\n"):
            if ln.strip() and any(n.search(ln) for n in NOISE):
                continue
            out.append(ln)
    return out


def count_fullwidth(lines):
    """Independent marker count for the full-width (numbered) chapters."""
    n = 0
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s.startswith("Maklum"):
            continue
        para = [s]
        for j in range(i + 1, min(i + 6, len(lines))):
            nxt = lines[j].strip()
            if not nxt:
                break
            para.append(nxt)
        m = MARKER.match(re.sub(r"\s+", " ", " ".join(para)))
        if not m or (m.group("ent") and m.group("ent").strip().islower()) \
                or len(m.group("ent").split()) > 8:
            continue                      # not a heading / prose or table cell
        prev = lines[i - 1].strip() if i else ""
        if prev and (prev.endswith((" dan", ",")) or "Sumber:" in prev):
            continue                      # wrapped table-source citation
        n += 1
    return n


def count_margin(lines):
    """Independent marker count for margin chapters: 'Maklum' in the label
    column, located from the section anchors alone."""
    anchor = re.compile(r"^(LATAR|PENEMUAN|SYOR|RUMUSAN|OBJEKTIF|SKOP|"
                        r"METODOLOGI|Maklum|Pendapat Audit)")
    ind = Counter()
    for ln in lines:
        st = ln.lstrip()
        if st and anchor.match(st):
            ind[len(ln) - len(st)] += 1
    if not ind:
        return 0
    mx = ind.most_common(1)[0][0]
    n = 0
    for ln in lines:
        st = ln.lstrip()
        if st and abs(len(ln) - len(st) - mx) <= 4 and st.startswith("Maklum"):
            n += 1
    return n


def seq_check(paths):
    """Continuity of numbered section paths ['5.1','5.1.1',...]."""
    tops, subs = [], defaultdict(list)
    for p in paths:
        bits = [int(x) for x in p.split(".")]
        if len(bits) == 2:
            tops.append(bits[1])
        else:
            subs[bits[1]].append(bits[2])
    probs = []
    if tops != list(range(1, len(tops) + 1)):
        probs.append("top-level run %s" % tops)
    for x, ys in subs.items():
        if ys != list(range(1, len(ys) + 1)):
            probs.append("x=%d sub-run %s" % (x, ys))
    return probs


def range_check(paths):
    """Margin ranges: increasing, non-overlapping, and no interior paragraph
    gaps (leading background / trailing rumusan paragraphs are out of scope
    by design, but between the first and last unit every paragraph must
    belong to exactly one unit)."""
    probs, last, covered = [], 0, set()
    for p in paths:
        if not p:
            continue
        lo, hi = (int(x) for x in p.split("-")) if "-" in p else (int(p),) * 2
        if lo <= last:
            probs.append("range %s overlaps/regresses after %d" % (p, last))
        covered |= set(range(lo, hi + 1))
        last = max(last, hi)
    holes = [x for x in range(min(covered), max(covered))
             if x not in covered] if covered else []
    if holes:
        probs.append("interior paragraph gaps %s" % holes)
    return probs


def main():
    with open(os.path.join(DATA, "fact_lkan_audits.csv")) as f:
        audits = list(csv.DictReader(f))
    with open(os.path.join(DATA, "fact_lkan_findings.csv")) as f:
        finds = list(csv.DictReader(f))
    anomalies = set()
    anom_path = os.path.join(DATA, "_source_anomalies_lkan.csv")
    if os.path.exists(anom_path):
        with open(anom_path) as f:
            anomalies = {r["verbatim"] for r in csv.DictReader(f)}

    results = []

    def check(name, scope, expected, actual, ok, note=""):
        results.append({"check": name, "scope": scope, "expected": expected,
                        "actual": actual, "status": "PASS" if ok else "FAIL",
                        "note": note})

    # 1. maklum balas coverage per volume
    csv_mb = Counter()
    for r in finds:
        if r["maklum_balas"]:
            csv_mb[r["source_file"]] += len(r["maklum_balas"].split(";"))
    for vol in EXPECT_CHAPTERS:
        pages = volume_pages(vol)
        indep = 0
        for a in audits:
            if a["source_file"] != vol or a["audit_style"] == "register":
                continue
            lines = clean_lines(pages, int(a["pdf_start"]), int(a["pdf_end"]))
            indep += (count_margin(lines) if a["audit_style"] == MARGIN
                      else count_fullwidth(lines))
        check("maklum_balas_coverage", vol, indep, csv_mb[vol],
              csv_mb[vol] == indep,
              "independent recount over chapter ranges")

    # 2. section_path continuity per chapter
    for a in audits:
        if a["audit_style"] == "register":
            continue
        key = (a["source_file"], a["chapter_id"])
        paths = [r["section_path"] for r in finds
                 if (r["source_file"], r["chapter_id"]) == key]
        probs = (range_check(paths) if a["audit_style"] == MARGIN
                 else seq_check(paths))
        check("section_path_continuity", "%s ch %s" % key,
              "contiguous", "; ".join(probs) or "contiguous", not probs)

    # 3. pdf_page within chapter range
    bad = []
    arange = {(a["source_file"], a["chapter_id"]):
              (int(a["pdf_start"]), int(a["pdf_end"])) for a in audits}
    for r in finds:
        lo, hi = arange[(r["source_file"], r["chapter_id"])]
        if not lo <= int(r["pdf_page"]) <= hi:
            bad.append("%s ch %s p%s" % (r["source_file"], r["chapter_id"],
                                         r["pdf_page"]))
    check("pdf_page_in_chapter_range", "all volumes", "0 out-of-range",
          "; ".join(bad) or "0 out-of-range", not bad)

    # 4. chapter counts per volume
    have = Counter(a["source_file"] for a in audits)
    for vol, want in EXPECT_CHAPTERS.items():
        check("chapter_count", vol, want, have[vol], have[vol] == want)

    # 5. rm_amounts token format
    bad = []
    for r in finds:
        for tok in filter(None, r["rm_amounts"].split(";")):
            if not RM_OK.match(tok) and tok not in anomalies:
                bad.append("%s ch %s %s: %r" % (r["source_file"],
                                                r["chapter_id"],
                                                r["section_path"], tok))
    check("rm_token_format", "all volumes", "all normalised or in anomalies",
          "; ".join(bad[:8]) + (" (+%d more)" % (len(bad) - 8)
                                if len(bad) > 8 else "") or "all normalised",
          not bad)

    dest = os.path.join(DATA, "_validation_lkan_findings.csv")
    with open(dest, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["check", "scope", "expected",
                                          "actual", "status", "note"])
        w.writeheader()
        w.writerows(results)
    npass = sum(1 for r in results if r["status"] == "PASS")
    for r in results:
        if r["status"] == "FAIL":
            print("FAIL %-26s %-22s expected=%s actual=%s"
                  % (r["check"], r["scope"], r["expected"], r["actual"]))
    print("%d/%d PASS -> %s" % (npass, len(results), dest))
    print("totals: %d audits, %d findings, %d maklum-balas entries, "
          "%d rm tokens"
          % (len(audits), len(finds), sum(csv_mb.values()),
             sum(len([t for t in r["rm_amounts"].split(";") if t])
                 for r in finds)))


if __name__ == "__main__":
    main()
