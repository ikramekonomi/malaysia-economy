#!/usr/bin/env python3
"""Extract Jadual 1.1 (Kewangan Kerajaan Persekutuan / Federal Government Finance) from
every Tinjauan Fiskal statistical appendix in raw/, edition by edition.

Run:  python3 sources/mof-fiscal-outlook/pipeline/fetch_editions.py      (first)
      python3 sources/mof-fiscal-outlook/pipeline/extract_public_finance_stats.py
Writes: data/<edition>_public_finance_stats/fact_headline.csv   (2019-2027, not 2021)
        data/_parser_check_2021.csv  -- the parser re-run on the 2021 appendix and
                                        compared, value by value, with the 2021 folder
                                        that was transcribed by hand and verified

Unlike extract_2021_public_finance_stats.py, nothing here is typed in. Every figure is
read from `pdftotext -layout` output of the official PDF named in
data/_editions_manifest.csv, on the page recorded in the row.

HOW A PAGE IS READ
------------------
The table prints each line as three text lines: the Malay label, the values, the English
label. A values line is one made only of numeric tokens. Its label is the nearest label
line above it. A value is assigned to a year column by its right edge -- the figures are
right-aligned under their year header -- so a row that prints only some columns (the
COVID-19 fund, the financing rows) lands in the right years and the rest stay empty.

Signs and blanks, as printed:  "-40,321" is negative;  a lone "-" or "–" is nil/not
printed and is left empty;  "% perubahan" rows are growth rates and are skipped.

BASIS, FROM THE PAGE ITSELF
---------------------------
A year header carrying a footnote marker (20204, 2024⁴) is an estimate; the footnote's
own text says which: "Anggaran disemak / Revised estimate" -> official_revised,
"Anggaran belanjawan / Budget estimate" -> official_projection, "Awalan / Preliminary"
-> official_preliminary. A year with no marker is official_actual. The marker-to-text
mapping is read from the page's footnotes, not assumed from column position, and the build
stops if a marked year's footnote cannot be found.

THE 2023 EDITION'S HEADER
-------------------------
jadual_perangkaan.pdf prints its last two year headers in a font whose text layer is
offset by 0x1D: the bytes 15 13 15 15 are "2022", 15 13 15 16 are "2023". They are
decoded by that offset (the same table on the next page prints the column readably as
"2022³", confirming it), and the trailing glyphs U+022A/U+022B are that font's
superscript 4 and 5 -- the "Awalan" and "Anggaran belanjawan" footnotes.
"""
import csv
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
RAW = os.path.join(ROOT, "raw")
DATA = os.path.join(ROOT, "data")
MANIFEST = os.path.join(DATA, "_editions_manifest.csv")

APPENDIX = {2019: "st_kewangan.pdf", 2020: "st_kewangan.pdf", 2021: "st_kewangan.pdf",
            2022: "st_kewangan.pdf", 2023: "jadual_perangkaan.pdf", 2024: "st_kewangan.pdf",
            2025: "st_kewangan.pdf", 2026: "st_kewangan.pdf", 2027: "st_kewangan.pdf"}

# Malay label (normalised, footnote digits stripped) -> line key. Same keys as the
# hand-transcribed 2021 folder so the editions UNION cleanly.
LABELS = [
    ("hasil", "revenue"),
    ("perbelanjaan mengurus", "operating_expenditure"),
    ("baki semasa", "current_balance"),
    ("perbelanjaan pembangunan kasar", "development_expenditure_gross"),
    ("perbelanjaan langsung", "development_expenditure_direct"),
    ("pinjaman kasar", "development_expenditure_gross_lending"),
    ("tolak: terimaan balik pinjaman", "development_expenditure_loan_recovery"),
    ("perbelanjaan pembangunan bersih", "development_expenditure_net"),
    ("kumpulan wang covid-19", "covid19_fund"),
    ("baki keseluruhan", "overall_balance"),
    ("tolak: bayaran khidmat hutang", "debt_service_charges"),
    ("baki primer", "primary_balance"),
    ("pinjaman bersih luar pesisir", "net_offshore_borrowings"),
    ("pinjaman bersih dalam negeri", "net_domestic_borrowings"),
    ("perubahan aset", "change_in_assets"),
    ("perubahan dalam aset", "change_in_assets"),
]
NOT_PRINTED_IF_DASH = {"net_offshore_borrowings", "net_domestic_borrowings", "change_in_assets"}
SKIP_LABELS = ("% perubahan", "(% perubahan)", "sumber pembiayaan")
PCT_LABEL = "% kdnk"          # % of GDP of the amount row above it

SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
SHIFTED_SUPER = {"Ȫ": "4", "ȫ": "5"}       # 2023 edition's footnote glyphs
NUM = re.compile(r"^-?[\d,]+(\.\d+)?$")
GLUED_FOOTNOTE = re.compile(r"^(-?\d{1,3}(?:,\d{3})+)(\d)$")
FOOTNOTED = {}          # year -> footnote marker, for the values line being parsed
NIL = {"-", "–", "—"}

BASIS_BY_FOOTNOTE = [
    (re.compile(r"anggaran disemak|revised estimate", re.I), "official_revised"),
    (re.compile(r"anggaran belanjawan|budget estimate", re.I), "official_projection"),
    (re.compile(r"\bawalan\b|preliminary", re.I), "official_preliminary"),
]


def pdftext(pdf, page):
    return subprocess.run(["pdftotext", "-layout", "-f", str(page), "-l", str(page), pdf, "-"],
                          capture_output=True, text=True, check=True).stdout


def npages(pdf):
    out = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
    return int(re.search(r"Pages:\s+(\d+)", out).group(1))


def unshift(s):
    """Undo the 2023 edition's 0x1D font offset on control-range characters."""
    return "".join(chr(ord(c) + 0x1D) if 0x10 <= ord(c) <= 0x1C else
                   ("" if ord(c) == 0x03 else c) for c in s)


def find_table_page(pdf):
    for p in range(1, npages(pdf) + 1):
        t = pdftext(pdf, p)
        if re.search(r"KEWANGAN KERAJAAN PERSEKUTUAN|FEDERAL GOVERNMENT FINANCE", t) and \
                re.search(r"Baki keseluruhan", t):
            return p, t
    raise SystemExit(f"{pdf}: Jadual 1.1 not found")


def printed_table_no(text):
    """The table number as printed: 1.1 in most editions, 5.1 in the 2023 edition."""
    m = re.search(r"(?:^|\n)\s*(\d)\.1\.?\s+KEWANGAN KERAJAAN PERSEKUTUAN", text)
    if not m:
        raise SystemExit("cannot read the federal-finance table number")
    return f"{m.group(1)}.1"


def _unused_find_table_page(pdf):
    for p in range(1, npages(pdf) + 1):
        t = pdftext(pdf, p)
        if re.search(r"KEWANGAN KERAJAAN PERSEKUTUAN|FEDERAL GOVERNMENT FINANCE", t) and \
                re.search(r"Baki keseluruhan", t):
            return p, t
    raise SystemExit(f"{pdf}: Jadual 1.1 not found")


def parse_header(lines):
    """-> (line_index, [(year, footnote_or_None, right_edge)])"""
    for i, raw in enumerate(lines):
        line = unshift(raw)
        cols = []
        for m in re.finditer(r"(20\d\d)([0-9¹²³⁰⁴-⁹Ȫȫ]?)(?=\s|$)", line):
            fn = m.group(2)
            fn = SHIFTED_SUPER.get(fn, fn.translate(SUPERSCRIPT)) or None
            cols.append((int(m.group(1)), fn, m.end()))
        if len(cols) == 5 and all(b[0] == a[0] + 1 for a, b in zip(cols, cols[1:])):
            return i, cols
    raise SystemExit("no five-year header line found")


def footnote_text(lines, start):
    """Map footnote marker -> its text, from the footnote block below the table.

    Footnotes print as a marker on its own (or leading) line followed by the Malay text,
    with the English text in a second column; markers and text can sit on adjacent lines.
    """
    block = [l for l in lines[start:]]
    out = {}
    for i, l in enumerate(block):
        for m in re.finditer(r"(?:^|\s{2,})([1-9])(?:\s{2,}|\s*$)", l):
            n = m.group(1)
            ctx = " ".join(block[max(0, i - 1): i + 3])
            for pat, basis in BASIS_BY_FOOTNOTE:
                if pat.search(ctx) and n not in out:
                    # take the closest keyword to this marker's line
                    out.setdefault(n, [])
            # collect the text that follows the marker on this and the next line
            after = (l[m.end():] + " " + (block[i + 1] if i + 1 < len(block) else "")).strip()
            out.setdefault(n, []).append(after)
    return {n: " ".join(v) for n, v in out.items()}


FOOTNOTE_TEXTS = {}
TABLE_NO = {}


def malay_footnotes(lines, start):
    """Marker -> its Malay footnote text, read as printed below the table: a marker on
    its own (or leading) line, then the text on that or the following line(s). The English
    column to the right is cut off at the first wide gap."""
    out, cur = {}, None
    for l in lines[start:]:
        left = re.split(r"\s{4,}", l.strip())[0] if l.strip() else ""
        m = re.match(r"^([1-9])(?:\s+(.*))?$", left)
        if m:
            cur = m.group(1)
            out[cur] = (m.group(2) or "").strip()
        elif cur and left and not re.match(r"^\d", left):
            out[cur] = (out[cur] + " " + left).strip() if len(out[cur]) < 160 else out[cur]
    return out


def classify(fn, fn_texts):
    txt = fn_texts.get(fn, "")
    hits = [b for pat, b in BASIS_BY_FOOTNOTE if pat.search(txt)]
    return hits[0] if len(hits) == 1 else None


def printed_page(lines):
    """The printed page number from the page footer, where the text layer carries one.

    Footers print the number either before the running title ("184  tinjauan fiskal ...")
    or after it ("Tinjauan Fiskal  Fiscal Outlook 2020      151"); in the 2022/2023
    appendices the running title is in a font with no usable text layer, but the number
    after it is still plain digits. A lone footnote marker (one digit) is never a page
    number. Returns None where the page prints none in its text layer (2019 appendix).
    """
    tail = [l for l in lines if l.strip()][-6:]
    for l in reversed(tail):
        if re.search(r"(?i)fiscal|fiskal|[\u0800-\u08ff]", l):
            m = re.search(r"\s{3,}(\d{2,3})\s*$", l)
            if m:
                return int(m.group(1))
            m = re.search(r"(?i)(?:^|\s)(\d{2,3})\s+(?:tinjauan|\S*[\u0800-\u08ff])", l)
            if m:
                return int(m.group(1))
    return None


def norm_label(s):
    s = unshift(s).strip().lower()
    s = re.sub(r"(?<=[a-z\)])\d$", "", s)           # glued footnote digit: "baki primer2"
    s = re.sub(r"(?<=covid-19)\d$", "", s)          # "covid-191"
    return re.sub(r"\s+", " ", s)


def label_key(label):
    for prefix, key in LABELS:
        if label == prefix or label.startswith(prefix + " ") or label == prefix.rstrip(":"):
            return key
    return None


def parse_values(line, cols):
    """Numeric tokens -> {year: value}; returns None if the line is not a values line."""
    toks = [(m.group(0), m.end()) for m in re.finditer(r"\S+", line)]
    if not toks or not all(NUM.match(t) or t in NIL for t, _ in toks):
        return None
    first_left = min(c[2] for c in cols) - 12
    # a lone footnote digit far left of every year column is the English label's
    # superscript bleeding into the values line ("Primary balance¹"), not a value
    toks = [(t, r) for t, r in toks if not (re.fullmatch(r"[1-9]", t) and r < first_left)]
    if not toks:
        return None
    out = {}
    for tok, right in toks:
        year = min(cols, key=lambda c: abs(c[2] - right))
        if abs(year[2] - right) > 12:
            raise SystemExit(f"value {tok!r} at col {right} matches no year column")
        if year[0] in out:
            raise SystemExit(f"two values land in {year[0]}: {line.strip()!r}")
        m = GLUED_FOOTNOTE.match(tok)
        if m:
            # "51,9734" is 51,973 carrying footnote marker 4: a thousands group can only
            # hold three digits, so a fourth trailing digit is the superscript, not value
            FOOTNOTED[year[0]] = m.group(2)
            tok = m.group(1)
        out[year[0]] = None if tok in NIL else float(tok.replace(",", ""))
    return out


def extract(edition):
    pdf = os.path.join(RAW, str(edition), APPENDIX[edition])
    page, text = find_table_page(pdf)
    lines = text.splitlines()
    hi, cols = parse_header(lines)

    rows, unknown, last_amount_key, label = [], [], None, None
    end = len(lines)
    for i in range(hi + 1, len(lines)):
        raw = lines[i]
        if re.match(r"^\s*[1-9]\s*$", raw) or re.match(r"^\s*[1-9]\s{2,}[A-Za-z(]", raw):
            # a footnote marker followed by TEXT (or alone on its line) opens the footnote
            # block; a marker followed by numbers is a stray superscript in a values line
            end = i
            break
        if not raw.strip():
            continue
        FOOTNOTED.clear()
        vals = parse_values(raw, cols)
        cell_fn = dict(FOOTNOTED)
        if vals is None:
            # the nearest text line above a values line is its Malay label (the English
            # label prints below the values, so it is overwritten before the next row)
            label = norm_label(raw)
            continue
        lab, label = label, None
        if lab is None or lab.startswith(SKIP_LABELS):
            continue
        if lab.startswith(PCT_LABEL):
            key, is_pct = f"{last_amount_key}_pct_gdp", True
        else:
            key, is_pct = label_key(lab), False
            if key is None:
                unknown.append(lab)
                continue
            last_amount_key = key
        if key not in NOT_PRINTED_IF_DASH:
            # a printed dash is a NIL (repo convention, CLAUDE.md): e.g. the COVID-19 fund
            # in years it spent nothing. Only the budget-year financing rows use a dash to
            # mean "not printed", and stay empty.
            vals = {y: (0.0 if v is None else v) for y, v in vals.items()}
        rows.append((key, is_pct, vals, cell_fn))
    fn_texts = footnote_text(lines, end)

    basis = {}
    for year, fn, _ in cols:
        if fn is None:
            basis[year] = "official_actual"
        else:
            b = classify(fn, fn_texts)
            if b is None:
                raise SystemExit(f"edition {edition}: footnote {fn} on {year} has no "
                                 f"recognisable basis text: {fn_texts.get(fn)!r}")
            basis[year] = b
    FOOTNOTE_TEXTS[edition] = malay_footnotes(lines, end)
    TABLE_NO[edition] = printed_table_no(text)
    return pdf, page, printed_page(lines), cols, basis, rows, unknown


def manifest():
    return {(int(r["edition"]), r["file"]): r for r in csv.DictReader(open(MANIFEST))}


FIELDS = ["edition", "table_no", "line", "target_year", "amount_rm_juta", "pct_of_gdp", "basis",
          "source_file", "pdf_page", "printed_page", "retrieved_from", "retrieved_date", "note"]


def to_rows(edition, extracted, man):
    pdf, page, pp, cols, basis, rows, _ = extracted
    m = man[(edition, os.path.basename(pdf))]
    fn_texts = FOOTNOTE_TEXTS.get(edition, {})
    out = []
    for key, is_pct, vals, cell_fn in rows:
        for year, v in sorted(vals.items()):
            if v is None:
                continue
            notes = []
            if pp is None:
                notes.append("printed page number not in this page's text layer; pdf_page is exact")
            if year in cell_fn:
                n = cell_fn[year]
                notes.append(f"printed with footnote {n}: {fn_texts.get(n, '(see page)').strip()}")
            out.append({
                "edition": edition, "table_no": TABLE_NO[edition], "line": key, "target_year": year,
                "amount_rm_juta": None if is_pct else (int(v) if v == int(v) else v),
                "pct_of_gdp": v if is_pct else None,
                "basis": basis[year], "source_file": os.path.basename(pdf),
                "pdf_page": page, "printed_page": pp,
                "retrieved_from": m["url"], "retrieved_date": m["retrieved_date"],
                "note": "; ".join(notes),
            })
    return out


def main():
    man = manifest()
    for edition in sorted(APPENDIX):
        ex = extract(edition)
        pdf, page, pp, cols, basis, rows, unknown = ex
        if unknown:
            raise SystemExit(f"edition {edition}: unmapped labels {unknown} -- add to LABELS")
        out = to_rows(edition, ex, man)
        years = ", ".join(f"{y}={basis[y].replace('official_', '')}" for y, _, _ in cols)
        print(f"{edition}: p.{page} (printed {pp})  {len(out)} cells  [{years}]")
        if edition == 2021:
            check_against_hand_transcription(out)
            continue
        dest = os.path.join(DATA, f"{edition}_public_finance_stats")
        os.makedirs(dest, exist_ok=True)
        with open(os.path.join(dest, "fact_headline.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(out)


def check_against_hand_transcription(parsed):
    """The parser must reproduce the verified, hand-transcribed 2021 folder exactly."""
    hand = list(csv.DictReader(open(os.path.join(
        DATA, "2021_public_finance_stats", "fact_headline.csv"))))
    key = lambda r: (r["line"], int(r["target_year"]))
    val = lambda r: r["amount_rm_juta"] if r["amount_rm_juta"] not in ("", None) else r["pct_of_gdp"]
    H = {key(r): (float(val(r)), r["basis"]) for r in hand}
    P = {key(r): (float(val(r)), r["basis"]) for r in parsed}
    rows = []
    for k in sorted(set(H) | set(P)):
        h, p = H.get(k), P.get(k)
        status = "PASS" if h == p else "FAIL"
        rows.append([status, k[0], k[1], h[0] if h else "", p[0] if p else "",
                     h[1] if h else "", p[1] if p else ""])
    with open(os.path.join(DATA, "_parser_check_2021.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["status", "line", "target_year", "hand_transcribed", "parsed",
                    "hand_basis", "parsed_basis"])
        w.writerows(rows)
    fails = [r for r in rows if r[0] == "FAIL"]
    print(f"      parser vs hand-transcribed 2021 folder: {len(rows) - len(fails)}/{len(rows)} agree")
    for r in fails:
        print("      FAIL", r)
    if fails:
        raise SystemExit("parser does not reproduce the verified 2021 transcription")


if __name__ == "__main__":
    main()
