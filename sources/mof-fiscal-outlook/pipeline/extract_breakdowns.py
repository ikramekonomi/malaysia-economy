#!/usr/bin/env python3
"""Extract Jadual 3.1 / 3.2 / 3.3 (operating expenditure by component, operating and
development expenditure by sector) from every Tinjauan Fiskal statistical appendix.

Run after extract_public_finance_stats.py (it reuses that module's page readers and its
per-year basis). Writes, per edition other than 2021:
    data/<edition>_public_finance_stats/fact_opex_by_component.csv
    data/<edition>_public_finance_stats/fact_opex_by_sector.csv
    data/<edition>_public_finance_stats/fact_devex_by_sector.csv
and data/_parser_check_2021_breakdowns.csv -- the parser re-run on the 2021 appendix and
compared, cell by cell, with the hand-transcribed and verified 2021 folder.

HOW A ROW IS IDENTIFIED
-----------------------
These tables wrap long labels, and the values sit on the label's LAST line; the English
label prints below. So the text between two values lines is the previous row's English
label followed by this row's Malay label. Rather than guess which is which, each values
line is labelled by matching the text immediately above it (and any text on the values
line itself) against a fixed Malay vocabulary -- the longest run of lines that forms a
known label wins. Any values line that matches nothing stops the build: a new or renamed
line is a fact about the source to be decided by a person, never something to guess.

LABEL CHANGES ACROSS EDITIONS
-----------------------------
"Pertanian dan pembangunan luar bandar" (agriculture AND rural development; editions
2019-2021) becomes "Pertanian" (agriculture; 2022 onward). They are kept under DIFFERENT
line keys (economic_agri_rural vs economic_agriculture): the overlap years show whether
the content changed, and a series is never run across a renamed category unnoticed.
"Pelajaran dan latihan" (2025-2026) is a synonym of "Pendidikan dan latihan" -- the
English label "Education and training" is identical -- and keeps its line key.

"Lain-lain" (Others) occurs at both levels; which one is decided by indentation.
"""
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_public_finance_stats as pfs  # noqa: E402

DATA = pfs.DATA

TABLES = {  # printed table no. (3.x, or 7.x in the 2023 edition) -> output and vocabulary
    "1": ("fact_opex_by_component", r"PERBELANJAAN MENGURUS[\s\S]{0,300}(?:KOMPONEN|OBJEK)"),
    "2": ("fact_opex_by_sector", r"PERBELANJAAN MENGURUS[\s\S]{0,300}SEKTOR"),
    "3": ("fact_devex_by_sector", r"PERBELANJAAN PEMBANGUNAN[\s\S]{0,300}SEKTOR"),
}

# (malay label, key, english, level, parent). Level-2 "lain-lain" is resolved separately.
COMPONENT = [
    ("emolumen", "emoluments", "Emoluments", 1, None),
    ("bayaran persaraan", "retirement_charges", "Retirement charges", 1, None),
    ("bayaran khidmat hutang", "debt_service", "Debt service charges", 1, None),
    ("dalam negeri", "debt_service_domestic", "Domestic", 2, "debt_service"),
    ("luar negeri", "debt_service_external", "External", 2, "debt_service"),
    ("pemberian dan serahan kepada kerajaan negeri", "grants_state_govts",
     "Grants and transfers to state governments", 1, None),
    ("pemberian di bawah perlembagaan", "grants_constitutional", "Constitutional grants", 2,
     "grants_state_govts"),
    ("pemberian/pindahan lain", "grants_other", "Other grants/transfers", 2, "grants_state_govts"),
    ("perkhidmatan dan bekalan", "supplies_services", "Supplies and services", 1, None),
    ("subsidi dan bantuan sosial", "subsidies_social_assistance",
     "Subsidies and social assistance", 1, None),
    ("pembelian aset", "asset_acquisition", "Asset acquisition", 1, None),
    ("bayaran balik dan hapus kira", "refunds_writeoffs", "Refunds and write-offs", 1, None),
    ("pemberian kepada badan berkanun", "grants_statutory_bodies", "Grants to statutory bodies", 1, None),
    ("lain-lain", "other", "Others", 1, None),
    ("jumlah", "total", "Total", 1, None),
]
SECTOR = [
    ("ekonomi", "economic", "Economic", 1, None),
    ("pertanian dan pembangunan luar bandar", "economic_agri_rural",
     "Agriculture and rural development", 2, "economic"),
    ("pertanian", "economic_agriculture", "Agriculture", 2, "economic"),
    ("tenaga dan kemudahan awam", "economic_energy_utilities", "Energy and public utilities", 2, "economic"),
    ("perdagangan dan perindustrian", "economic_trade_industry", "Trade and industry", 2, "economic"),
    ("pengangkutan", "economic_transport", "Transport", 2, "economic"),
    ("perhubungan", "economic_communications", "Communications", 2, "economic"),
    ("alam sekitar", "economic_environment", "Environment", 2, "economic"),
    ("sosial", "social", "Social", 1, None),
    ("pendidikan dan latihan", "social_education", "Education and training", 2, "social"),
    ("pelajaran dan latihan", "social_education", "Education and training", 2, "social"),
    ("kesihatan", "social_health", "Health", 2, "social"),
    ("perumahan", "social_housing", "Housing", 2, "social"),
    ("keselamatan", "security", "Security", 1, None),
    ("pertahanan", "security_defence", "Defence", 2, "security"),
    ("keselamatan dalam negeri", "security_internal", "Internal security", 2, "security"),
    ("pentadbiran am", "general_admin", "General administration", 1, None),
    ("lain-lain", "other", "Others", 1, None),
    ("jumlah", "total", "Total", 1, None),
]
VOCAB = {"1": COMPONENT, "2": SECTOR, "3": SECTOR}
PAREN_SHARE = re.compile(r"^\(-?\d[\d,]*\.\d+\)$")

FIELDS = ["edition", "table_no", "line", "line_bm", "line_en", "level", "parent_line", "target_year",
          "amount_rm_juta", "pct_share", "basis", "source_file", "pdf_page", "printed_page",
          "retrieved_from", "retrieved_date", "note"]


def norm(s):
    s = pfs.unshift(s).strip().lower()
    s = re.sub(r"(?<=[a-z\)])\d$", "", s)            # glued footnote digit
    return re.sub(r"\s+", " ", s)


def find_page(pdf, n):
    pat = TABLES[n][1]
    for p in range(1, pfs.npages(pdf) + 1):
        t = pfs.pdftext(pdf, p)
        m = re.search(rf"(?:^|\n)\s*([37])\.{n}\.?\s+{pat}", t[:1200])
        if m:
            return p, t, f"{m.group(1)}.{n}"
    raise SystemExit(f"{pdf}: table x.{n} not found")


def header_columns(lines):
    """-> (index, years[(year, right_edge)], pcts[right_edge] or [])"""
    for i, raw in enumerate(lines):
        line = pfs.unshift(raw)
        ys = [(int(m.group(1)), m.end()) for m in
              re.finditer(r"(20\d\d)[0-9¹²³⁰⁴-⁹Ȫȫ]?(?=\s|$)", line)]
        if len(ys) == 5 and all(b[0] == a[0] + 1 for a, b in zip(ys, ys[1:])):
            pcts = [m.end() for m in re.finditer(r"(?<=\s)%(?=\s|$)", line)]
            # Does the table carry a % share column per year? Decided from the data: the
            # first row with numbers prints ~10 of them (amount + share per year) or 5.
            has_share = None
            for l in lines[i + 1:]:
                nums = re.findall(r"(?<!\S)(?:\(?-?[\d,]+(?:\.\d+)?\)?|[-–])(?!\S)", l)
                if len(nums) >= 5 and re.search(r"\d", l):
                    has_share = len(nums) >= 9
                    break
            if has_share is None:
                raise SystemExit("cannot tell whether the table has share columns")
            return i, ys, pcts, has_share
    raise SystemExit("no five-year header found")


def split_values(raw, ys, pcts, has_share=True):
    """-> (text_part, indent, {year: (amount, pct)}) or None if no values on the line."""
    toks = [(m.group(0), m.start(), m.end()) for m in re.finditer(r"\S+", raw)]
    # numeric tail: walk from the right while tokens are numeric / nil / a share.
    # The 2022 edition prints shares in parentheses -- "(4.2)", "(100.0)". The repo
    # convention reads parentheses as negative, but a share of total spending cannot be
    # negative and the total row prints "(100.0)", so a parenthesised DECIMAL is a share.
    # A parenthesised whole number would be an amount and stops the build below.
    k = len(toks)
    while k > 0 and (pfs.NUM.match(toks[k - 1][0]) or toks[k - 1][0] in pfs.NIL
                     or PAREN_SHARE.match(toks[k - 1][0])):
        k -= 1
    tail = toks[k:]
    first_left = min(y[1] for y in ys) - 14
    tail = [t for t in tail if not (re.fullmatch(r"[1-9]", t[0]) and t[2] < first_left)]
    if not tail:
        return None
    if all(PAREN_SHARE.match(t[0]) for t in tail):
        # parenthesised decimals with no amount anywhere on the line: an unlabelled
        # growth-rate row (2019 prints one under "Economic"). A share can never appear
        # without its amount, so this is not data for these tables.
        return "RATE_ROW"
    # Amounts here are whole RM juta; shares print with one decimal. So a decimal token is
    # the % share of the amount immediately to its left, and only amounts are placed by
    # column -- this holds whether or not a "%" header line is present (2021 prints it
    # separately).
    # A row that prints an amount for every year needs no placing: amounts go to the
    # years in order. Only a row with gaps is placed by position (right edge under the
    # year header) -- tightly packed rows like 2022's totals drift too far for that.
    ordinal = None
    if not has_share and len(tail) == len(ys):
        ordinal = iter(y for y, _ in ys)
    elif has_share:
        # with shares, amounts are the tokens NOT immediately following another amount
        seq, prev_amt = [], False
        for t in tail:
            is_share_tok = PAREN_SHARE.match(t[0]) or "." in t[0] or (t[0] in pfs.NIL and prev_amt)
            if not is_share_tok:
                seq.append(t)
            prev_amt = not is_share_tok
        if len(seq) == len(ys):
            ordinal = iter(y for y, _ in ys)
    out, last_year = {}, None
    for tok, _, right in tail:
        is_nil = tok in pfs.NIL
        # In these expenditure tables a dash is a printed NIL -- no spending on that line
        # that year -- and is kept as 0.0, the repo-wide extraction convention (CLAUDE.md).
        # (Jadual 1.1 differs: there a dash in a budget-year financing row means "not
        # printed" and is left empty, as the verified 2021 transcription does.)
        if re.fullmatch(r"\(-?[\d,]+\)", tok):
            raise SystemExit(f"parenthesised whole number {tok!r}: amount or share? {raw.strip()!r}")
        paren = bool(PAREN_SHARE.match(tok))
        v = 0.0 if is_nil else float(tok.strip("()").replace(",", ""))
        # a dash right after an amount is that amount's share only where the table HAS a
        # share column (3.1, 3.3); in 3.2 every token is an amount
        # In a table WITHOUT share columns (3.2) every token is an amount, decimals
        # included: 2022 prints housing opex as "0.4" (RM juta).
        is_pct = has_share and (paren or "." in tok or (is_nil and last_year is not None
                                                        and out[last_year][1] == "pending"))
        if is_pct:
            if last_year is None:
                raise SystemExit(f"share {tok!r} with no amount to its left: {raw.strip()!r}")
            out[last_year] = (out[last_year][0], v)
            last_year = None
            continue
        if ordinal is not None:
            year = next(ordinal)
            edge = right
        else:
            year, edge = min(ys, key=lambda c: abs(c[1] - right))
        if abs(edge - right) > 9:
            raise SystemExit(f"value {tok!r} (col {right}) matches no year column in {raw.strip()!r}")
        if year in out:
            raise SystemExit(f"two amounts land in {year}: {raw.strip()!r}")
        out[year] = (v, "pending")
        last_year = year
    out = {y: (a, None if p == "pending" else p) for y, (a, p) in out.items()}
    text = raw[:toks[k][1]] if k else ""
    if text.strip() and k < len(toks) and not re.search(r"[A-Za-z]", text):
        text = ""
    return text, (len(text) - len(text.lstrip())) if text.strip() else None, out


def extract_table(edition, n, basis):
    pdf = os.path.join(pfs.RAW, str(edition), pfs.APPENDIX[edition])
    page, text, printed_no = find_page(pdf, n)
    lines = text.splitlines()
    hi, ys, pcts, has_share = header_columns(lines)
    vocab = VOCAB[n]
    by_label = {}
    for bm, key, en, lvl, parent in vocab:
        by_label.setdefault(bm, (key, en, lvl, parent))

    buffer = []          # (text, indent) of text lines since the last values line
    rows, base_indent, current_l1 = [], None, None
    body = [l for l in lines[hi + 1:] if l.strip()]
    consumed = set()     # lines already used as a label's forward continuation
    skip_rate_values = False
    for idx, raw in enumerate(body):
        if idx in consumed:
            continue
        s = norm(raw)
        if s.startswith(("% perubahan", "(% perubahan)", "% change", "% bahagian", "% share")):
            # a growth/share-rate row: its numbers print on the NEXT line -- skip that too
            buffer, skip_rate_values = [], s.startswith(("% perubahan", "(% perubahan)"))
            continue
        sv = split_values(raw, ys, pcts, has_share) if not skip_rate_values else None
        if skip_rate_values and re.fullmatch(r"[\d,.\-–\s()]+", raw):
            skip_rate_values = False
            continue
        if sv == "RATE_ROW":
            continue
        if sv is None:
            buffer.append((raw.strip(), len(raw) - len(raw.lstrip())))
            continue
        tail_text, tail_indent, vals = sv
        pieces = buffer + ([(tail_text.strip(), tail_indent)] if tail_text.strip() else [])
        buffer = []
        # The buffer holds only text since the previous values line: that row's English
        # label, then this row's Malay label -- and sometimes the first line of this row's
        # English label too, when the values print one line down (2022: "Subsidi dan
        # bantuan sosial" / "Subsidies and social" / values / "assistance"). So take the
        # LATEST run of consecutive lines that forms a known Malay label, longest first.
        match = None
        for end in range(len(pieces), 0, -1):
            for k in range(min(3, end), 0, -1):
                cand = norm(" ".join(t for t, _ in pieces[end - k:end]))
                if cand in by_label:
                    match = (cand, pieces[end - k][1])
                    break
            if match:
                break
        if match is None and tail_text.strip():
            # the values can sit on a label's FIRST line, with the rest wrapping below
            # ("Pemberian dan serahan  6,920 ..." / "kepada kerajaan negeri")
            ahead = []
            for j in range(idx + 1, min(idx + 3, len(body))):
                if split_values(body[j], ys, pcts, has_share) not in (None,):
                    break
                ahead.append(j)
                cand = norm(" ".join([tail_text.strip()] + [body[a].strip() for a in ahead]))
                if cand in by_label:
                    match = (cand, tail_indent)
                    consumed.update(ahead)
                    break
        if match is None:
            if not pieces:
                continue      # a stray superscript-only line
            raise SystemExit(f"edition {edition} table {printed_no}: values line with no "
                             f"known label above it: {[t for t, _ in pieces[-3:]]}")
        label, indent = match
        key, en, lvl, parent = by_label[label]
        if lvl == 1 and label != "lain-lain" and base_indent is None:
            base_indent = indent
        if label == "lain-lain" and base_indent is not None and indent > base_indent:
            lvl, parent, key = 2, current_l1, f"{current_l1}_other"
        if lvl == 1:
            current_l1 = key
        if key == "total":
            current_l1 = None
        for year, (amt, pct) in sorted(vals.items()):
            rows.append({"line": key, "line_bm": label_bm(label, vocab), "line_en": en,
                         "level": lvl, "parent_line": parent or "", "target_year": year,
                         "amount_rm_juta": None if amt is None else (int(amt) if amt == int(amt) else amt),
                         "pct_share": pct, "basis": basis[year]})
        if key == "total":
            break
    return pdf, page, printed_no, pfs.printed_page(lines), rows


def label_bm(norm_label, vocab):
    """Printed-style casing for the Malay label (first letter capital)."""
    return norm_label[:1].upper() + norm_label[1:]


def main():
    man = pfs.manifest()
    for edition in sorted(pfs.APPENDIX):
        _, _, _, cols, basis, _, _ = pfs.extract(edition)
        for n, (fname, _) in TABLES.items():
            pdf, page, printed_no, pp, rows = extract_table(edition, n, basis)
            m = man[(edition, os.path.basename(pdf))]
            out = []
            for r in rows:
                if r["amount_rm_juta"] is None and r["pct_share"] is None:
                    continue
                out.append(dict(r, edition=edition, table_no=printed_no, source_file=os.path.basename(pdf),
                                pdf_page=page, printed_page=pp, retrieved_from=m["url"],
                                retrieved_date=m["retrieved_date"],
                                note="" if pp is not None else
                                "printed page number not in this page's text layer; pdf_page is exact"))
            lines_found = len({r["line"] for r in out})
            print(f"{edition} {printed_no} {fname}: p.{page}, {lines_found} lines, {len(out)} cells")
            if edition == 2021:
                check_2021(fname, out)
                continue
            dest = os.path.join(DATA, f"{edition}_public_finance_stats", f"{fname}.csv")
            with open(dest, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS)
                w.writeheader()
                w.writerows(out)


CHECKS = []


def check_2021(fname, parsed):
    hand = list(csv.DictReader(open(os.path.join(DATA, "2021_public_finance_stats", f"{fname}.csv"))))
    k = lambda r: (r["line"], int(r["target_year"]))
    fl = lambda v: None if v in ("", None) else float(v)
    H = {k(r): (fl(r["amount_rm_juta"]), fl(r["pct_share"]), r["basis"], int(r["level"]),
                r["parent_line"]) for r in hand}
    P = {k(r): (fl(r["amount_rm_juta"]), fl(r["pct_share"]), r["basis"], int(r["level"]),
                r["parent_line"]) for r in parsed}
    bad = 0
    for key in sorted(set(H) | set(P)):
        ok = H.get(key) == P.get(key)
        bad += not ok
        CHECKS.append(["PASS" if ok else "FAIL", fname, key[0], key[1], H.get(key), P.get(key)])
    print(f"      parser vs hand-transcribed 2021 {fname}: {len(set(H) | set(P)) - bad}/"
          f"{len(set(H) | set(P))} agree")
    with open(os.path.join(DATA, "_parser_check_2021_breakdowns.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["status", "table", "line", "target_year",
                    "hand (amount, pct, basis, level, parent)", "parsed"])
        w.writerows(CHECKS)
    if bad:
        for c in CHECKS:
            if c[0] == "FAIL":
                print("      FAIL", c[1:])
        raise SystemExit("breakdown parser does not reproduce the verified 2021 transcription")


if __name__ == "__main__":
    main()
