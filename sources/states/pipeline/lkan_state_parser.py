"""Generic parser for the National Audit Department's state financial-statement
volumes (LKAN "Penyata Kewangan Kerajaan Negeri" / "LKAN <n>/<year> <State>").

The Jabatan Audit Negara uses ONE template per era across all 13 states, so
nothing in this module is Selangor-specific.  Everything state-specific lives in
`state_config.py`; everything era-specific is expressed as *title regexes* in
`table_catalog.py`, never as page numbers or JADUAL numbers.

Extraction path
---------------
The signed statutory statements themselves (Lampiran III-VII: Penyata Kedudukan
Kewangan / Penerimaan dan Pembayaran / Prestasi Kewangan / Akaun Memorandum /
Nota) are IMAGE-ONLY scans in every volume checked (see README).  The text-layer
ground truth is the auditor's own analysis section, whose JADUAL tables restate
those statements in RM Juta and cite `Sumber: Penyata Kewangan Kerajaan Negeri`.
Those tables are what this module parses.

Text-layer hazards handled (cf. sources/audit-negara/pipeline/STRUCTURE_NOTES.md):
  * doubled footers / doubled running heads (era 3-4)
  * InDesign slug lines `<job>.indd <printed page> <date> <time>`
  * wrapped row labels printed above OR below their value line
  * right-aligned value columns with centred header spans
  * `-` / `–` for nil, `(x)` for negative (era >= FY2019), bare `-x` (era <= FY2018)
"""

from __future__ import annotations

import hashlib
import os
import re
from collections import Counter
import subprocess
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# page text
# --------------------------------------------------------------------------

_CACHE: dict[str, list[str]] = {}


def load_pages(pdf_path: str, cache_dir: str | None = None) -> list[str]:
    """Return the pdftotext -layout text of every page, 0-based list index i
    corresponding to pdf_page i+1."""
    key = os.path.abspath(pdf_path)
    if key in _CACHE:
        return _CACHE[key]
    txt = None
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        cf = os.path.join(cache_dir, os.path.basename(pdf_path)[:-4] + ".txt")
        if os.path.exists(cf):
            txt = open(cf, encoding="utf-8", errors="replace").read()
    if txt is None:
        txt = subprocess.run(
            ["pdftotext", "-layout", pdf_path, "-"],
            capture_output=True, text=True, errors="replace",
        ).stdout
        if cache_dir:
            open(cf, "w", encoding="utf-8").write(txt)
    pages = txt.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    _CACHE[key] = pages
    _PDF_PATH[os.path.basename(pdf_path)] = (pdf_path, cache_dir)
    return pages


_PDF_PATH: dict[str, tuple[str, str | None]] = {}
_YCACHE: dict[tuple[str, int], list[tuple[float, str]]] = {}


def page_lines_y(source_file: str, pno: int) -> list[tuple[float, str]]:
    """(yMin, text) of every printed text line on one page, from `pdftotext -bbox-layout`.

    The -layout text keeps x but loses the vertical gaps, so a label line printed exactly between two rows
    cannot be placed from the text alone; the glyph positions can (a line inside a cell sits closer to its
    own row than to the next).  Cached on disk beside the text cache.  Empty when the PDF is not at hand."""
    key = (source_file, pno)
    if key in _YCACHE:
        return _YCACHE[key]
    path, cache_dir = _PDF_PATH.get(source_file, (None, None))
    out: list[tuple[float, str]] = []
    cf = os.path.join(cache_dir, f"{source_file[:-4]}.p{pno}.y.tsv") if cache_dir else None
    if cf and os.path.exists(cf):
        for ln in open(cf, encoding="utf-8"):
            y, _, t = ln.rstrip("\n").partition("\t")
            out.append((float(y), t))
    elif path and os.path.exists(path):
        html = subprocess.run(["pdftotext", "-bbox-layout", "-f", str(pno), "-l", str(pno), path, "-"],
                              capture_output=True, text=True, errors="replace").stdout
        for m in re.finditer(r'<line xMin="[\d.]+" yMin="([\d.]+)"[^>]*>(.*?)</line>', html, re.S):
            words = re.findall(r">([^<]+)</word>", m.group(2))
            out.append((float(m.group(1)), " ".join(w.strip() for w in words)))
        out.sort()
        if cf:
            with open(cf, "w", encoding="utf-8") as f:
                f.writelines(f"{y}\t{t}\n" for y, t in out)
    _YCACHE[key] = out
    return out


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def body_line_ys(table: "RawTable") -> list[float | None]:
    """The printed y of each body line, matched in order by its leading text (None where unmatched)."""
    plines = page_lines_y(table.source_file, table.pdf_page)
    ys: list[float | None] = []
    floor = -1.0
    for ln in table.body:
        s = re.sub(r"^\s*\d{1,3}[.)]?\s+", "", ln)          # the Bil., printed with or without a dot
        words = _norm(s).split(" ")
        y = None
        if words and words[0]:
            head = " ".join(words[:3])
            for py, pt in plines:
                if py >= floor - 1 and (pt.startswith(head) or (len(pt) >= 6 and head.startswith(pt))):
                    y = py
                    break
        ys.append(y)
        if y is not None:
            floor = y
    return ys


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# printed page number
# --------------------------------------------------------------------------

_SLUG = re.compile(r"\.indd\s+(\d{1,4})\b")
_PIPE_R = re.compile(r"\|\s*(\d{1,3})\s*$")
_PIPE_L = re.compile(r"^\s*(\d{1,3})\s*\|")
_BARE = re.compile(r"^\s*(\d{1,3})\s*$")
_HEAD_NUM = re.compile(r"^\s{0,20}(\d{1,3})\s+[A-Za-z]")
_TAIL_NUM = re.compile(r"[A-Za-z].*?\s(\d{1,3})\s*$")


def printed_page(page_text: str) -> str:
    """Best-effort printed (typeset) page number.

    Slug lines are the most reliable marker in the 2019+ volumes; the 2017/2018
    volumes carry `... NEGERI <STATE> <YEAR> | <n>` footers; the 2016 volume
    prints a bare number.  Returns '' when nothing is resolvable.
    """
    m = _SLUG.search(page_text)
    if m:
        return m.group(1)
    lines = [l.rstrip() for l in page_text.split("\n") if l.strip()]
    for l in reversed(lines[-14:]):
        for pat in (_PIPE_R, _PIPE_L):
            m = pat.search(l)
            if m:
                return m.group(1)
    for l in reversed(lines[-4:]):
        m = _BARE.match(l)
        if m:
            return m.group(1)
    for l in reversed(lines[-6:]):
        for pat in (_HEAD_NUM, _TAIL_NUM):
            m = pat.search(l)
            if m:
                return m.group(1)
    return ""


# --------------------------------------------------------------------------
# amounts
# --------------------------------------------------------------------------

NIL_CHARS = {"-", "–", "—", "−"}

_NUM_RE = re.compile(
    r"\(?-?\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?\)?%?|\(?-?\d+\.\d+\)?%?"
)
_DECIMAL_RE = re.compile(r"^\(?-?\d{1,3}(?:,\d{3})*\.\d+\)?$")
# money-looking: a decimal amount, or a comma-grouped integer (the ABT/`(RM)`
# tables print whole ringgit with thousands separators and no sen)
_MONEY_RE = re.compile(
    r"^\(?-?\d{1,3}(?:,\d{3})*\.\d+\)?$|^\(?-?\d{1,3}(?:,\d{3})+\)?$")


def parse_amount(tok: str) -> float | None:
    """Verbatim -> float.  Parentheses = negative; en-dash / hyphen alone = 0.0
    (nil, per the repo's extraction convention)."""
    t = tok.strip()
    if t in NIL_CHARS:
        return 0.0
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").replace(",", "").replace(" ", "")
    if t.startswith("-"):
        neg = True
        t = t[1:]
    if not t:
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


# --------------------------------------------------------------------------
# table location
# --------------------------------------------------------------------------

_JADUAL_HEAD = re.compile(r"^\s*(JADUAL|Jadual)\s+(\d+(?:\.\d+)?)\s*\.?\s*$")
_STOP = re.compile(
    r"^\s*(Sumber\s*:|SUMBER\s*:|Nota\s*:|NOTA\s*:|CARTA\s+\d|Carta\s+\d|"
    r"JADUAL\s+\d|Jadual\s+\d)"
)
# A table block also ends where the narrative resumes.  Analysis paragraphs are
# numbered `4.4.2.` / `8.1.2.` and section headings `4.8. PENYATA ...`; without
# this, a table with no `Sumber:` line swallows the prose that follows it and
# the RM figures inside those sentences become phantom rows.
_NARRATIVE = re.compile(r"^\s{0,30}\d{1,2}(?:\.\d{1,2})+\.?\s+\S")
_SLUG_LINE = re.compile(r"\.indd\s+\d")
# Running heads/footers of these volumes.  The duplicated text layer prints
# them twice and `-layout` can drop them INSIDE a table block, where they would
# otherwise be stitched onto the last row's label.
_FOOTER_LINE = re.compile(
    # the doubled layer glues words (`LKANNegeri`, `AnalisisKewangan`), so no word boundary after LKAN / between
    r"\b(LKAN|RAHSIA\b|VERSI KABINET\b)|"
    r"\b(Penyata|PENYATA)\s+Kewangan\s+(Kerajaan|Agensi)\b|"
    r"\bAnalisis\s*Kewangan|\bKandungan\b|\bMuka\s+Surat\b", re.I)


@dataclass
class RawTable:
    jadual: str
    title: str
    title_lines: list[str]
    body: list[str]
    pdf_page: int
    printed_page: str
    source_file: str
    sumber: str = ""
    nota: list[str] = field(default_factory=list)


def _is_noise(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if _SLUG_LINE.search(s):
        return True
    if re.match(r"^(VERSI KABINET|SEMAKAN|Terkini)", s):
        return True
    if _FOOTER_LINE.search(s) and not re.search(r"\d{1,3}(,\d{3})*\.\d", s):
        return True
    return False


def _continuation_lines(pages: list[str], idx: int) -> list[str]:
    """Body lines of the page(s) that CONTINUE the table which ran off the
    bottom of page `idx`.

    A continued table reprints only its column-header strip (`BIL. | AGENSI |
    TARIKH PENYERAHAN`) at the top of the next page - never a new `JADUAL n`
    heading - so a page-at-a-time scanner silently loses the tail.  The
    long agency registers routinely run three pages.  Collection stops at the
    first `Sumber:`/`Nota:`/`CARTA`/`JADUAL` line or at narrative prose.
    """
    out: list[str] = []
    j = idx + 1
    while j < len(pages):
        lines = pages[j].split("\n")
        took = []
        stopped = False
        seen_any = False
        for ln in lines:
            if _is_noise(ln):
                continue
            if _STOP.match(ln) or _JADUAL_HEAD.match(ln):
                stopped = True
                break
            if seen_any and _is_prose(ln):
                stopped = True
                break
            if ln.strip():
                seen_any = True
            took.append(ln)
        if not seen_any:
            break
        out += took
        if stopped:
            break
        j += 1
    return out


def find_tables(pages: list[str], source_file: str,
                keep_empty: bool = False,
                join_continuations: bool = False) -> list[RawTable]:
    """Locate every `JADUAL n` block on every page.

    Blocks run from the heading to the first `Sumber:` / `Nota:` / next JADUAL /
    CARTA line, or the end of the page.  With `join_continuations`, a block that
    reaches the bottom of its page without a `Sumber:` line absorbs the
    following page(s) - the registers are printed that way.  It is OFF by
    default because the money JADUAL are single-page and joining would change
    their column geometry.
    """
    out: list[RawTable] = []
    for idx, page in enumerate(pages):
        pno = idx + 1
        pp = printed_page(page)
        lines = page.split("\n")
        i = 0
        while i < len(lines):
            m = _JADUAL_HEAD.match(lines[i])
            if not m:
                i += 1
                continue
            # Duplicated text layers print the heading twice; skip an immediate
            # repeat of the same jadual id on the same page.
            jad = m.group(2)
            j = i + 1
            title_lines: list[str] = []
            body: list[str] = []
            sumber = ""
            nota: list[str] = []
            seen_data = False
            while j < len(lines):
                ln = lines[j]
                if _is_noise(ln):
                    j += 1
                    continue
                st = _STOP.match(ln)
                if st:
                    tok = st.group(1).lower()
                    if tok.startswith("sumber"):
                        sumber = ln.strip()
                        k = j + 1
                        while k < len(lines) and re.match(r"^\s*(Nota|NOTA)\s*:", lines[k]):
                            nota.append(lines[k].strip())
                            k += 1
                        j = k
                    break
                if _JADUAL_HEAD.match(ln):
                    break
                if seen_data and _NARRATIVE.match(ln):
                    break
                if seen_data and _is_prose(ln):
                    break
                if _has_value(ln):
                    seen_data = True
                    body.append(ln)
                else:
                    (body if seen_data else title_lines).append(ln)
                j += 1
            if join_continuations and not sumber and j >= len(lines):
                body += _continuation_lines(pages, idx)
            title = " ".join(t.strip() for t in title_lines if t.strip())
            title = re.sub(r"\s+", " ", title).strip()
            if body or (keep_empty and title_lines):
                out.append(RawTable(
                    jadual=jad, title=title, title_lines=title_lines, body=body,
                    pdf_page=pno, printed_page=pp, source_file=source_file,
                    sumber=sumber, nota=nota,
                ))
            i = j if j > i else i + 1
    # drop exact duplicates produced by doubled text layers
    seen: set[tuple] = set()
    uniq = []
    for t in out:
        key = (t.pdf_page, t.jadual, t.title[:60], len(t.body))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(t)
    return uniq


# NB: the sentence test is CASE SENSITIVE - `. b` starts a new clause, `. B`
# is an abbreviation such as `Sdn. Bhd` or `No. Pinjaman`.
_SENTENCE_RE = re.compile(r"\.\s+[a-z]")
_PROSE_RE = re.compile(
    r"\bialah\b|\bdisebabkan\b|\bmenyebabkan\b|\bseperti di\b|"
    r"\bseperti dalam\b|\badalah seperti\b|\bButiran adalah\b|\bmanakala\b|"
    r"\bBagaimanapun\b|\bAnalisis Audit\b", re.I)


def _is_prose(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    words = re.findall(r"[A-Za-z]{2,}", s)
    return (bool(_PROSE_RE.search(s)) or bool(_SENTENCE_RE.search(s))) and len(words) >= 8


def _has_value(line: str) -> bool:
    """A data line carries at least one decimal-formatted amount."""
    for m in _NUM_RE.finditer(line):
        ms, me, s = m.start(), m.end(), m.group(0)
        s = s.replace(" ", "")
        before = line[ms - 1] if ms else " "
        after = line[me] if me < len(line) else " "
        if before.isdigit() or before == "." or after.isdigit() or after == ".":
            continue
        if _MONEY_RE.match(s):
            return True
    return False


# --------------------------------------------------------------------------
# column geometry (pdftotext -layout preserves x as character columns)
# --------------------------------------------------------------------------

@dataclass
class Column:
    left: int
    right: int
    header: str = ""
    year: str = ""
    unit: str = ""


@dataclass
class Row:
    label: str
    cells: dict[int, tuple[str, float]]  # column index -> (printed, value)
    ordinal_fallback: bool = False
    # every printed value token of the row, in printed (left-to-right) order, INCLUDING ones that
    # collided into a column already taken (those are dropped from `cells`)
    tokens: list = None


_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
# One printed UNIT cell of a column-header strip.  The closing bracket is
# optional and the run of spaces inside is bounded, because the doubled text
# layers of the 2019+ volumes wrap `(RM Juta)` onto two lines and drop a
# bracket - an unbounded `[^)]*` would then swallow the neighbouring year and
# make the token span half the page.
_UNIT_TOK = re.compile(
    r"\(\s{0,4}RM(?:\s{0,4}(?:Juta|JUTA|juta|Bilion|BILION|bilion))?\s{0,4}\)?"
    r"|\(\s{0,2}%\s{0,2}\)?")
_TITLEY = re.compile(r"BERBANDING|HINGGA|Berbanding|Hingga|SETAKAT|Setakat")


def _value_tokens(line: str, exact_flank: bool = False) -> list[tuple[int, int, str]]:
    """Value tokens with their character span.

    Guards: a token flanked by a digit or a dot is part of a date
    (`21.03.2024`) or a section number (`4.5.4.1.`), never an amount.
    """
    toks = []
    for m in _NUM_RE.finditer(line):
        ms, me, s = m.start(), m.end(), m.group(0).strip()
        if not s:
            continue
        # `\s?` in _NUM_RE (for `- 5.00`) also lets a match start at the single space BEFORE a number;
        # the flank test must look at the character before the number itself, or `1,886.80 100.0` loses
        # its `100.0` (the character before the space is the 0 of 1,886.80). Selangor CMD.41.2019 J11.
        # Used only as a row-level fallback (exact_flank=True): column building keeps the historical
        # tokenisation, because the extra tokens it would now see (`(4.20) (0.8)` change columns) break the
        # year-column geometry of tables that parse correctly today (Pahang CMD.37.2017 J4.6).
        if exact_flank and not m.group(0)[0].strip() and not m.group(0).lstrip().startswith("-"):
            ms += len(m.group(0)) - len(m.group(0).lstrip())
        before = line[ms - 1] if ms else " "
        after = line[me] if me < len(line) else " "
        if before.isdigit() or before == "." or after.isdigit() or after == ".":
            continue
        if _MONEY_RE.match(s.replace(" ", "")) or re.match(r"^\(?-?\d+\)?$", s):
            toks.append((ms, me, s))
    # Standalone nil markers ('-' / en-dash); never the '-' inside '(-)', and
    # never a printed BULLET.  These volumes list the sub-funds of Kumpulan
    # Wang Amanah Kerajaan as `- Kumpulan Wang Pembangunan   -658.29 ...`;
    # reading that leading dash as a nil cell made the row's label start after
    # it, so the label was empty, the section heading above was welded onto the
    # first sub-fund (Terengganu CMD.46.2016 J4.2 shipped KW Pembangunan's
    # -696.94 as `govt_trust_funds`) and `Kumpulan Wang Bekalan Air` was
    # dropped for having no label at all.  A dash followed by a WORD is a
    # bullet; a nil cell is followed by white space, another cell or the line
    # end.
    for m in re.finditer(r"(?<![\w.,()–—-])[-–—](?![\w.,\d()–—-])", line):
        if re.match(r"\s*[A-Za-z]", line[m.end():]):
            continue
        toks.append((m.start(), m.end(), line[m.start():m.end()]))
    toks.sort()
    return toks


def build_columns(body: list[str], header_lines: list[str]) -> list[Column]:
    """Cluster the right edges of value tokens into columns, then label each
    column from the header block (a header token may span several columns)."""
    per_line = [_value_tokens(ln) for ln in body]
    edges: list[tuple[int, int]] = [(s, e) for toks in per_line for s, e, _ in toks]
    if not edges:
        return []
    edges.sort(key=lambda x: x[1])
    cols: list[Column] = []
    for s, e in edges:
        if cols and abs(e - cols[-1].right) <= 2:
            cols[-1].left = min(cols[-1].left, s)
            cols[-1].right = max(cols[-1].right, e)
        else:
            cols.append(Column(left=s, right=e))

    # Merge x-overlapping clusters ONLY when they never co-occur on a line
    # (centred %/nisbah cells share a column; tightly-packed year columns that
    # appear together on every line must NOT be merged - see STRUCTURE_NOTES).
    def _nearest(e: int, cs: list[Column]) -> int:
        return min(range(len(cs)), key=lambda i: abs(cs[i].right - e))

    changed = True
    while changed and len(cols) > 1:
        changed = False
        cooc = [[False] * len(cols) for _ in cols]
        for toks in per_line:
            hit = {_nearest(e, cols) for _, e, _ in toks}
            for a in hit:
                for b in hit:
                    if a != b:
                        cooc[a][b] = True
        for i in range(len(cols) - 1):
            a, b = cols[i], cols[i + 1]
            if b.left <= a.right - 1 and not cooc[i][i + 1]:
                a.right = max(a.right, b.right)
                a.left = min(a.left, b.left)
                cols.pop(i + 1)
                changed = True
                break

    for hl in header_lines:
        if _TITLEY.search(hl) and "(RM" not in hl:
            continue
        for m in re.finditer(r"\(RM[^)]*\)|\(%\)|\b(?:19|20)\d{2}\b|[A-Za-z%()][A-Za-z%()./]*", hl):
            tok = m.group(0)
            ts, te = m.start(), m.end()
            for ci, c in enumerate(cols):
                if te > c.left - 3 and ts < c.right + 3:
                    c.header = (c.header + " " + tok).strip()
    # ------------------------------------------------------------------
    # UNIT (money vs percent) - resolved by NEAREST header token, never by
    # "any overlapping token, money wins".
    #
    # A `PENYUMBANG UTAMA` / trend table prints its unit strip as
    # `(RM Juta)  (%)  (RM Juta)  (%)`.  The `(%)` cluster sits between two
    # money clusters and the +/-3 proximity window that assigns header tokens
    # to columns reaches BOTH neighbours, so `c.header` for the percent column
    # became `... (RM Juta) (%) (RM Juta)` and the old `re.search(r"\(RM...")`
    # picked the money unit off a PERCENT column.  Melaka CMD.53.2015 J4.12
    # then shipped the printed FY2013 percentages (39.4, 20.8, 73.6) as
    # RM Juta and dropped the real money column (119.28, 62.96, 223.05),
    # `is_canonical=yes`, `column_geometry=clean`.
    #
    # The general rule: a money column and a percent column are distinguished
    # by WHICH header token is theirs, and a token is theirs only if no other
    # column has a better claim on it.  Two readings, in order:
    #
    #   (a) ORDINAL.  A unit strip is printed left-to-right in the same order
    #       as the columns it labels, so when the strip carries as many tokens
    #       as there are unit-bearing columns the k-th token IS the k-th
    #       column's unit.  This is exact even where the strip is typeset far
    #       more tightly than the data (Selangor CMD.52.2022 J13: ten tokens
    #       squeezed into 100 characters over data columns spread across 150,
    #       so `(RM Juta)` for FY2019 sits directly above the FY2018 `(%)`
    #       figures - no proximity rule can read that page correctly).
    #   (b) NEAREST, when the counts disagree: overlap decides, centre distance
    #       breaks ties.  A single `(RM Juta)` centred over several money
    #       columns still reaches all of them (it is every one of those
    #       columns' best and only candidate), so a legitimate spanning header
    #       is unaffected.
    #
    # Never "any overlapping token, and money wins", which is what shipped the
    # percentages.
    line_toks: list[list[tuple[int, int, str]]] = []
    for hl in header_lines:
        if _TITLEY.search(hl) and "(RM" not in hl:
            continue
        toks = [(m.start(), m.end(), m.group(0))
                for m in re.finditer(_UNIT_TOK, hl)]
        if toks:
            line_toks.append(toks)
    unit_toks = [t for L in line_toks for t in L]
    near: list[list[tuple[int, int, str]]] = []
    for c in cols:
        near.append([t for t in unit_toks
                     if not (t[1] <= c.left - 3 or t[0] >= c.right + 3)])
    bearing = [ci for ci in range(len(cols)) if near[ci]]
    strip = max(line_toks, key=len) if line_toks else []
    unit_of: dict[int, str] = {}

    def _claim(toks: list[tuple[int, int, str]]) -> dict[int, str]:
        """Best column for each token (max overlap, nearest centre breaks ties)."""
        out: dict[int, str] = {}
        for ts, te, tok in toks:
            best, best_score = None, None
            for ci, c in enumerate(cols):
                if te <= c.left - 3 or ts >= c.right + 3:
                    continue
                ov = min(te, c.right) - max(ts, c.left)
                cd = abs((ts + te) / 2 - (c.left + c.right) / 2)
                if best_score is None or (ov, -cd) > best_score:
                    best, best_score = ci, (ov, -cd)
            if best is not None:
                out.setdefault(best, tok)
        return out

    # A `(%)` header is often typeset on its own line ABOVE or BELOW the money
    # strip (`PERATUS` / `(%)` stacked over a narrow column, Pulau Pinang
    # CMD.40.2017 J4.14).  Settle those columns first, then read the money
    # strip ordinally over what is left - otherwise a two-token money strip is
    # laid over a money column and a PERCENT column and the state's actual
    # operating expenditure ships as `96.0`.
    others = [t for L in line_toks if L is not strip for t in L]
    aside: dict[int, str] = {}
    if others and all(t[2].startswith("(") and "%" in t[2] for t in others):
        aside = _claim(others)
    elif others:
        strip = []                      # units spread over lines: no ordinal
    unit_of.update(aside)
    left_all = [ci for ci in range(len(cols)) if ci not in aside]
    left_bear = [ci for ci in bearing if ci not in aside]
    # the money strip may be typeset entirely to the LEFT of the data columns,
    # so the right-most data column can sit outside every token's window and
    # drop out of `bearing`; match against the full column list first.
    ordinal_over = None
    if len(strip) > 1 and len(strip) == len(left_all):
        ordinal_over = left_all
    elif len(strip) > 1 and len(strip) == len(left_bear):
        ordinal_over = left_bear
    if ordinal_over is not None:
        for ci, (_s, _e, tok) in zip(ordinal_over, strip):
            unit_of[ci] = tok
    else:
        for ci in bearing:
            c = cols[ci]
            best, best_score = "", None
            for ts, te, tok in near[ci]:
                ov = min(te, c.right) - max(ts, c.left)
                cd = abs((ts + te) / 2 - (c.left + c.right) / 2)
                if best_score is None or (ov, -cd) > best_score:
                    best, best_score = tok, (ov, -cd)
            unit_of[ci] = best
    # A doubled text layer wraps `(RM Juta)` onto two lines and loses a
    # bracket, so a column's unit token can be the bare stem `(RM` with its
    # `Juta)` printed on the NEXT header line (Johor CMD.30.2019 J2, pdf p31).
    # Re-join the two before `unit_factor` sees it, or a whole statutory
    # statement is refused for "no money column".
    for ci in list(unit_of):
        if not re.fullmatch(r"\(\s*RM\s*\)?", unit_of[ci].strip()):
            continue
        c = cols[ci]
        for hl in header_lines:
            m = re.search(r"\b(Juta|JUTA|juta|Bilion|BILION|bilion)\s*\)", hl)
            if m and not (m.end() <= c.left - 3 or m.start() >= c.right + 3):
                unit_of[ci] = "(RM %s)" % m.group(1)
                break
    for ci, c in enumerate(cols):
        c.unit = re.sub(r"\s+", " ", unit_of.get(ci, "")).strip()
        c.year = ""

    # A centred year heading may span several columns (a `(RM Juta)` + `(%)`
    # pair) - that is intended.  But in the tightly-set 2016-2018 layout it can
    # also bleed onto the NEIGHBOURING year's money column; when two adjacent
    # money columns claim the same year, re-decide by nearest header centre.
    claims: list[list[tuple[str, float]]] = [[] for _ in cols]
    for hl in header_lines:
        if _TITLEY.search(hl) and "(RM" not in hl:
            continue
        for m in _YEAR_RE.finditer(hl):
            ts, te = m.start(), m.end()
            centre = (ts + te) / 2
            for ci, c in enumerate(cols):
                if te > c.left - 3 and ts < c.right + 3:
                    claims[ci].append((m.group(0), centre))
    for ci, c in enumerate(cols):
        if claims[ci]:
            mid = (c.left + c.right) / 2
            c.year = min(claims[ci], key=lambda t: abs(t[1] - mid))[0]

    # A centred year heading legitimately spans a `(RM Juta)` + `(%)` pair, but
    # must never claim two MONEY columns: when it does, the nearest column keeps
    # it and the other falls back to its next-nearest claim (usually none, which
    # is right - that column is a PERUBAHAN column).
    money = [ci for ci, c in enumerate(cols) if c.unit.startswith("(RM")]
    by_year: dict[str, list[int]] = {}
    for ci in money:
        if cols[ci].year:
            by_year.setdefault(cols[ci].year, []).append(ci)
    for yr, cis in by_year.items():
        if len(cis) < 2:
            continue
        def dist(ci):
            mid = (cols[ci].left + cols[ci].right) / 2
            return min((abs(c - mid) for y, c in claims[ci] if y == yr), default=1e9)
        keep = min(cis, key=dist)
        for ci in cis:
            if ci == keep:
                continue
            alt = [(y, c) for y, c in claims[ci] if y != yr]
            mid = (cols[ci].left + cols[ci].right) / 2
            cols[ci].year = min(alt, key=lambda t: abs(t[1] - mid))[0] if alt else ""
    return cols


def split_header(table: RawTable) -> list[str]:
    """Header block = the title lines that sit closest to the data and look like
    column headings (carry a year, a unit, or a stub label)."""
    keep = []
    for l in table.title_lines:
        s = l.strip()
        if not s:
            continue
        if _TITLEY.search(s) and "(RM" not in s:
            continue
        # A prose-length line is the printed table TITLE, not a column header
        # (titles such as `KEDUDUKAN BAKI AKAUN DEPOSIT PADA TAHUN 2024 DAN
        # 2023` carry years but no BERBANDING/HINGGA keyword).  A line that
        # OPENS with the `Bil.` stub is the column strip however many words it
        # carries - `Bil. | Butiran Hasil | Anggaran | Sebenar` is what tells
        # the estimate column from the actual one.
        if ("(RM" not in s and "(%)" not in s
                and not re.match(r"^\s*(BIL|Bil)\.?\s", s)
                and len(re.findall(r"[A-Za-z]{3,}", s)) >= 5):
            continue
        if (_YEAR_RE.search(s) or "(RM" in s or "(%)" in s
                or re.search(r"\b(BIL|BUTIRAN|PERKARA|KATEGORI|JUMLAH|PERATUS|PERUBAHAN|Bil|Butiran|Perkara)\b", s)):
            keep.append(l)
    return keep[-6:]


def _has_money(line: str) -> bool:
    return any(_MONEY_RE.match(t[2].replace(" ", "")) or t[2] in NIL_CHARS
               for t in _value_tokens(line))


# The Bil. may be the ONLY thing on its line - the template centres it against
# a two-line label, so `       5.` sits alone between the two label lines
# (Perak CMD.56.2015 J4.11).  Requiring text after it left that row with no
# anchor at all and its figures were folded into the row above.
_BIL_TOK = re.compile(r"^\s{0,40}(\d{1,3})\.(?=\s|$)")
_TOTAL_LAB = re.compile(r"^\s*(jumlah|total)\b", re.I)


def parse_rows_by_bil(table: RawTable, cols: list[Column]) -> list[Row] | None:
    """Group the body into printed rows delimited by the BIL. column.

    The 5-year `PENYUMBANG UTAMA HASIL` matrix prints ONE logical row across
    three physical lines, and the middle line (the one carrying the Bil.)
    is not the line that carries all the money:

        Premium Bagi                          1,537.44   618.74  1,008.37  ...
          1.               1,316.80    67.6      68.4      46.9      58.4
        Geran

    Line-at-a-time parsing therefore splits one printed item across two
    line_codes and drops values.  Here every body line is assigned to the
    NEAREST Bil. line, so the block above becomes one row whose label is
    `Premium Bagi Geran` and whose cells are the union of both value lines.
    A line whose own label starts with JUMLAH/TOTAL always opens its own row,
    so the printed total is never swallowed into the last item.

    Returns None when the table has no usable Bil. column, so the caller can
    fall back to the line-at-a-time parser.
    """
    bil_idx = [i for i, ln in enumerate(table.body) if _BIL_TOK.match(ln)]
    if len(bil_idx) < 2:
        return None
    # Row 1's Bil. line can be cut into the TITLE block (no figures on it, so the table body starts at its
    # value line): Pulau Pinang CMD.58.2015 J4.11 prints `1. Premium Tanah - Pemberian` / figures / `Hak
    # Milik`, and the body began at the figures. Those lines then joined row 2 (`2. Cukai Tanah`), whose
    # own figures collided and were dropped. A value line before the first Bil. line opens its own row,
    # labelled from the stray title line when there is one.
    lead_label = ""
    first_money = next((i for i in range(bil_idx[0]) if _has_money(table.body[i])), None)
    tail = table.title_lines[-1] if table.title_lines else ""
    # only when row 1's Bil. line really was cut into the title: otherwise figures above the first Bil. line
    # are row 1's own (the `Premium Bagi` / `1. 1,316.80 ...` / `Geran` layout, Selangor CMD.50.2021 J13)
    if (first_money is not None and _has_money(table.body[bil_idx[0]])
            and _BIL_TOK.match(tail) and not _value_tokens(tail)):
        lead_label = re.sub(r"^\s*\d{1,3}[.)]\s*", "", tail).strip()
        bil_idx = [first_money] + bil_idx
    tot_idx = [i for i, ln in enumerate(table.body)
               if i not in bil_idx and _TOTAL_LAB.match(ln) and _value_tokens(ln)]
    anchors = sorted(bil_idx + tot_idx)

    # The running footer (`Analisis Kewangan Kerajaan Negeri Selangor 41`, printed twice by the doubled text
    # layer) sits below the last row after a run of blank lines, and the nearest-anchor rule stitched it on to
    # the JUMLAH label (`JUMLAH AnalisisKewangan Kerajaan Negeri NegeriSelangor Selangor 4141`, 22 rows in 7
    # states). A label-only line below the last anchor and past a gap of 2+ blank lines is not part of the
    # table, nor is any label-only line that reads as a running head or footer.
    footer: set[int] = set()
    blanks, last, cut = 0, anchors[-1], False
    for i in range(len(table.body)):
        ln = table.body[i]
        if not ln.strip():
            blanks += 1
            continue
        # the footer starts after 2+ blank lines, or at a line of bare page numbers (`22      22`, `2 -212`)
        cut = cut or (i > last and (blanks >= 2 or (blanks >= 1 and re.fullmatch(r"[\d\s-]+", ln.strip()))))
        if not _has_money(ln) and (cut or _FOOTER_LINE.search(ln)):
            footer.add(i)
        blanks = 0

    groups: dict[int, list[int]] = {a: [a] for a in anchors}
    ys: list[float | None] | None = None
    for i in range(len(table.body)):
        if i in groups or i in footer:
            continue
        prev = max([a for a in anchors if a < i], default=None)
        nxt = min([a for a in anchors if a > i], default=None)
        if prev is None and nxt is None:
            return None
        if prev is None:
            target = nxt
        elif nxt is None:
            target = prev
        elif (i - prev) == (nxt - i) and not _has_money(table.body[i]) and not re.search(r"\d", table.body[i]):
            # A label-only line exactly between two rows: the text cannot tell a continuation of the row above
            # from the first line of a label centred on the row below.  The glyph positions can: a line inside
            # a cell sits closer to its own row.  Kedah CMD.42.2022 J10 printed `Pemberian Bayaran Bagi
            # Membiayai Separuh Kos` 12.2pt below `Lain-Lain Levi` and 9.6pt above its own row, and the old
            # tie-break (to the row above) shipped `Lain-Lain Levi Pemberian Bayaran ...`.  Without positions
            # the tie still goes to the row above.
            if ys is None:
                ys = body_line_ys(table)
            yi, yp, yn = ys[i], ys[prev], ys[nxt]
            target = nxt if (None not in (yi, yp, yn) and yp < yi < yn and (yn - yi) < (yi - yp) - 1.0) else prev
        else:
            target = prev if (i - prev) <= (nxt - i) else nxt
        # A printed row carries ONE set of figures.  When a value-bearing line
        # is equidistant between two Bil. lines the distance tie-break sent it
        # to the row above, which already had its own figures - and the second
        # set was then dropped on to already-occupied columns.  Perak
        # CMD.56.2015 J4.11 lost `Lesen, Bayaran Pendaftaran Dan Permit`
        # (80.58 / 88.12 / 50.22 / 41.72 / 42.32) that way, and its five-year
        # top-contributor subtotal came out RM80.58 juta short of the printed
        # `Jumlah`.  A line with figures belongs to the anchor that has none.
        if _has_money(table.body[i]):
            if _has_money(table.body[target]):
                other = nxt if target == prev else prev
                if other is not None and not _has_money(table.body[other]):
                    target = other
        # a fragment never crosses a JUMLAH boundary
        if target in tot_idx and i < target and prev is not None:
            target = prev
        # A label-only line printed DIRECTLY BELOW a row's figures continues that row's label
        # (`3. Premium Tanah - Tukar` / figures / `Syarat`): the distance tie-break sent `Syarat` to the next
        # Bil. line. Only when the figures line itself belongs to the previous row and that row's Bil. line
        # carries no figures of its own (the label-above-and-below layout).
        if (not _has_money(table.body[i]) and i > 0 and _has_money(table.body[i - 1])
                and target != prev and prev is not None and (i - 1) in groups.get(prev, [])
                and not _has_money(table.body[prev])):
            target = prev
        groups[target].append(i)

    rows: list[Row] = []
    for a in anchors:
        idxs = sorted(groups[a])
        label_parts: list[str] = []
        all_toks: list[tuple[int, int, str]] = []
        for i in idxs:
            ln = table.body[i]
            toks = [t for t in _value_tokens(ln)
                    if _MONEY_RE.match(t[2].replace(" ", "")) or t[2] in NIL_CHARS]
            first = min((t[0] for t in toks), default=len(ln))
            lab = ln[:first]
            lab = re.sub(r"^\s*\d{1,3}[.)]\s*", "", lab)
            lab = re.sub(r"\s+", " ", lab).strip(" .:")
            if lab:
                label_parts.append(lab)
            all_toks += toks
        all_toks.sort()
        # row-level fallback: if the historical tokeniser lost values (single-space separated), but the exact
        # one finds exactly one per column / per money-year column, use the exact tokens (Selangor J11 JUMLAH)
        exact = sorted(t for i in idxs for t in _value_tokens(table.body[i], exact_flank=True)
                       if _MONEY_RE.match(t[2].replace(" ", "")) or t[2] in NIL_CHARS)
        _yc = [ci for ci, c in enumerate(cols) if c.year and c.unit.startswith("(RM")] or \
              [ci for ci, c in enumerate(cols) if c.year]
        if (len(exact) > len(all_toks) and len(all_toks) not in (len(cols), len(_yc))
                and len(exact) in (len(cols), len(_yc))):
            all_toks = exact
        # an `(RM Juta) (%)` matrix row printed as amount, share, amount, share ...: when the exact tokens are
        # exactly two per money-year column, the amounts are the 1st, 3rd, 5th ... (Selangor CMD.50.2021 J13
        # `JUMLAH 1,946.54 100.0 2,246.29 100.0 ...`, where the historical tokeniser kept five of the ten and
        # they happened to equal the five year columns, shifting every year after 2016)
        pct = any(c.unit.startswith("(%") for c in cols)
        paired = (pct and len(_yc) >= 2 and len(exact) == 2 * len(_yc) and len(exact) > len(all_toks)
                  and all(_DECIMAL_RE.match(t[2]) or _MONEY_RE.match(t[2].replace(" ", "")) for t in exact))
        cells: dict[int, tuple[str, float]] = {}
        if paired:
            for ci, (s_, e_, t) in zip(_yc, exact[0::2]):
                v = parse_amount(t)
                if v is not None:
                    cells[ci] = (t, v)
            all_toks = []
        # A 5-year trend matrix prints one value per year column, but the
        # later rows and the JUMLAH row are typeset with their own spacing, so
        # overlap matching drifts them a whole year (Perlis J4.11 shipped the
        # FY2014 subtotal as FY2015, 51% larger than that year's total
        # revenue).  A row carrying exactly one token per YEAR column is
        # therefore assigned ordinally to the year columns.
        # MONEY year columns only.  In a matrix that interleaves `(RM Juta)`
        # and `(%)` a centred year heading legitimately labels both, so
        # counting the percent columns inflates `year_cols` until a row that
        # merely lost a token or two to the tokeniser happens to match its
        # length - and then every one of that row's figures is shifted one
        # column (Sarawak CMD.43.2018 J4.14 `Royalti Hutan`: FY2015 shipped as
        # 7.4, FY2016 as 9.5, both percentages).
        year_cols = [ci for ci, c in enumerate(cols)
                     if c.year and c.unit.startswith("(RM")]
        if not year_cols:
            year_cols = [ci for ci, c in enumerate(cols) if c.year]
        ordinal = bool(all_toks) and len(all_toks) == len(cols)
        ordinal_years = (bool(all_toks) and not ordinal and len(year_cols) >= 3
                         and len(all_toks) == len(year_cols))
        if ordinal_years:
            for ci, (s_, e_, t) in zip(year_cols, all_toks):
                v = parse_amount(t)
                if v is not None:
                    cells[ci] = (t, v)
        elif ordinal:
            # A row that carries exactly one token per column is assigned in
            # printed order.  The JUMLAH row is typeset with its own spacing
            # (`JUMLAH 1,946.54 100.0 2,246.29 100.0 ...`), so overlap matching
            # would collide two of its tokens onto one column and drop the rest.
            for ci, (s_, e_, t) in enumerate(all_toks):
                v = parse_amount(t)
                if v is not None:
                    cells[ci] = (t, v)
        else:
            for s_, e_, t in all_toks:
                best, bestov = None, 0
                for ci, c in enumerate(cols):
                    ov = min(e_, c.right) - max(s_, c.left)
                    if ov > bestov or (best is None and e_ > c.left and s_ < c.right):
                        best, bestov = ci, ov
                if best is None:
                    best = min(range(len(cols)),
                               key=lambda ci: abs(cols[ci].right - e_))
                v = parse_amount(t)
                if v is not None and best not in cells:
                    cells[best] = (t, v)
        if lead_label and a == anchors[0]:
            label_parts.insert(0, lead_label)
        lab = re.sub(r"\s+", " ", " ".join(label_parts)).strip(" .:")
        # printed bullets: real ones, the Symbol-font private-use glyph and the
        # plain hyphen these volumes use to list sub-funds (`- Saham Biasa`)
        lab = re.sub(r"^[•●▪■·--]+\s*", "", lab)
        if lab or cells:
            rows.append(Row(label=lab, cells=cells,
                            ordinal_fallback=ordinal or ordinal_years, tokens=list(all_toks)))
    # A JUMLAH row typeset to its own measure can sit left of the grid the item rows define, so its first
    # amount lands in a year-less phantom column and every later figure shifts one column (Negeri Sembilan
    # CMD.37.2018 J4.10: `JUMLAH 367.27 88.8 341.92 89.9` shipped FY2017 as 88.8, the percentage). When the
    # item rows agree on one set of columns and the total carries exactly that many figures, the total's
    # figures are assigned to those columns in printed order.
    from collections import Counter
    keysets = Counter(tuple(sorted(r.cells)) for r in rows
                      if r.cells and not _TOTAL_LAB.match(r.label or ""))
    if keysets:
        modal, n_modal = keysets.most_common(1)[0]
        if n_modal >= 2:
            for r in rows:
                if (_TOTAL_LAB.match(r.label or "") and r.tokens and len(r.tokens) == len(modal)
                        and tuple(sorted(r.cells)) != modal):
                    cells = {}
                    for ci, (s_, e_, t) in zip(modal, r.tokens):
                        v = parse_amount(t)
                        if v is not None:
                            cells[ci] = (t, v)
                    if len(cells) == len(modal):
                        r.cells, r.ordinal_fallback = cells, True
    return rows


def parse_rows(table: RawTable, cols: list[Column],
               strict_sections: bool = False) -> list[Row]:
    """Assign value tokens to columns; stitch wrapped labels to the nearest
    value line (labels wrap above OR below the value line in this template)."""
    entries: list[tuple[int, str, list[tuple[int, int, str]]]] = []
    for li, ln in enumerate(table.body):
        toks = _value_tokens(ln)
        real = [t for t in toks if _MONEY_RE.match(t[2].replace(" ", "")) or t[2] in NIL_CHARS]
        if real:
            first = min(t[0] for t in real)
            label = ln[:first]
            entries.append((li, label, real))
        else:
            entries.append((li, ln, []))

    value_idx = [k for k, e in enumerate(entries) if e[2]]
    if not value_idx:
        return []

    def _base(v: int) -> str:
        return re.sub(r"^\s*\d{1,3}[.)]?\s*", "", entries[v][1]).strip(" .:")

    def _x(text: str) -> int | None:
        """Character column at which the label text starts (its indent).

        The Bil. stub is blanked first.  It is NOT always printed with a dot -
        the e1 volumes set it as a bare `1` - and leaving a bare Bil. in place
        put the row's indent at the Bil. column, which made a printed section
        heading look as though it were indented FURTHER LEFT than only one of
        its neighbours.  It was then not recognised as a heading and was welded
        on: Negeri Sembilan CMD.54.2015 J4.25 shipped the revenue subtotal
        `Jumlah` (354.78 / 373.09) under `expenditure_total` because the
        `Perbelanjaan` section caption printed between the two blocks was
        glued to it.
        """
        s = re.sub(r"^(\s*)(\d{1,3}[.)]?(?=\s{2,})\s+)?",
                   lambda m: " " * len(m.group(0)), text)
        m = re.search(r"\S", s)
        return m.start() if m else None

    own_x = {v: _x(entries[v][1]) for v in value_idx}

    # A wrapped cell continues at the SAME indent as the label it continues, so
    # the indent decides the owner - not distance.  Distance alone welds a
    # section heading printed between two rows onto whichever row happens to be
    # nearer (`JUMLAH` + `PERBELANJAAN` -> `JUMLAH PERBELANJAAN`, which then
    # ships a REVENUE subtotal under `expenditure_total`), and welds a
    # continuation onto the FOLLOWING label (`Pindahan Ke Dalam Kumpulan Wang` /
    # `Pembangunan` / `Defisit` -> `Pembangunan Defisit`, which loses the
    # state's surplus line entirely).
    frag_for: dict[int, list[tuple[int, str]]] = {k: [] for k in value_idx}
    headings: list[tuple[int, str]] = []
    ys: list[float | None] | None = None
    for k, (li, txt, toks) in enumerate(entries):
        if toks or not txt.strip():
            continue
        prev = max([v for v in value_idx if v < k], default=None)
        nxt = min([v for v in value_idx if v > k], default=None)
        last = value_idx[-1]
        if k > last + 1:
            continue                       # stray text below the table
        fx = _x(txt)
        cands = [c for c in (prev, nxt) if c is not None]
        xs = [own_x[c] for c in cands if own_x[c] is not None]
        # the indent only discriminates when the two candidate rows are
        # themselves printed at different indents
        discriminating = len(xs) == 2 and abs(xs[0] - xs[1]) >= 3
        aligned = [c for c in cands
                   if own_x[c] is not None and fx is not None
                   and abs(own_x[c] - fx) <= 2]

        def _acc(v: int) -> str:
            """Label text accumulated for row v so far."""
            return " ".join([entries[v][1]] + [t for _, t in frag_for[v]])

        # `xs` may be short of `cands`: this template routinely prints a row's
        # label ABOVE its figures, so that row's own label cell is blank and
        # its indent is unknown.  Requiring every neighbour's indent then
        # disabled the heading test exactly where it was needed - Negeri
        # Sembilan CMD.54.2015 J4.25, where the `Perbelanjaan` caption sits
        # between the revenue `Jumlah` and a figures-only line.  Judge on the
        # indents that ARE known.
        looks_heading = (fx is not None and xs
                         and all(fx <= x - 3 for x in xs)
                         and len(txt.split()) <= 4
                         and not re.search(r"\d", txt))

        if strict_sections and discriminating and len(aligned) == 1:
            # The indent identifies the owner.  `Pindahan Ke Dalam Kumpulan
            # Wang` / `Pembangunan` / `Defisit`: the continuation is printed at
            # the FIRST row's indent, so it cannot belong to `Defisit` - and
            # welding it there loses that state's surplus line entirely.
            target = aligned[0]
        elif (strict_sections and prev is not None and ")" in txt
              and _acc(prev).count("(") > _acc(prev).count(")")):
            # the fragment closes a bracket the previous row opened
            # (`Perbelanjaan Mengurus (tidak termasuk caruman Kumpulan Wang` +
            # `Pembangunan)`), so it cannot belong to the following label
            target = prev
        elif strict_sections and looks_heading and not aligned:
            # Outdented from BOTH neighbours and shaped like a caption: a
            # printed SECTION HEADING between two rows, not a wrapped label.
            # Welding it on produces `JUMLAH` + `PERBELANJAAN` ->
            # `JUMLAH PERBELANJAAN`, i.e. a REVENUE subtotal shipped under
            # `expenditure_total`.
            headings.append((k, txt.strip()))
            continue
        elif prev is None:
            target = nxt
        elif nxt is None:
            target = prev
        elif (k - 1 not in value_idx and entries[k - 1][1].rstrip().endswith("-")
              and any(fk == k - 1 for v in value_idx for fk, _ in frag_for[v])):
            # the line above ends in a hyphen (`Jabatan-` / `Jabatan Di Bawah ...`): a word broken
            # across lines, so this line continues the SAME label.  Distance alone handed the second
            # half to the JUMLAH row below (Selangor CMD.61.2015 J4.11 shipped
            # `Jabatan Di Bawah Senarai Bersama Jumlah` as a component leaf).
            target = next(v for v in value_idx for fk, _ in frag_for[v] if fk == k - 1)
        elif (k - prev) != (nxt - k):
            target = prev if (k - prev) < (nxt - k) else nxt
        else:
            # tie: the wrapped fragment belongs to the value row whose own
            # printed label is empty (the template prints the label above or
            # below the figures line)
            pe, ne = _base(prev) == "", _base(nxt) == ""
            target = prev if (pe and not ne) else (nxt if ne else nxt)
            # ...unless the glyph positions say otherwise: a line inside a cell sits closer to its own row.
            # Johor CMD.51.2015 J4.4 `Pelaburan Kumpulan` / `Wang Amanah` / `Jumlah` shipped the total as
            # `Wang Amanah Jumlah`, a leaf component.
            # Never onto a complete total/balance line, never a line that opens a new numbered item or carries
            # digits: those are section heads or prose under the table (`JUMLAH` + `ii. Tunggakan ...`).
            closed = re.match(r"\s*(?:jumlah|baki pada|lebihan|kurangan|\(kurangan\)|surplus|defisit|"
                              r"perbelanjaan sebenar)\b", _base(prev), re.I)
            opens = (re.match(r"\s*(?:[a-z]|[ivx]+|\d{1,2}(?:\.\d+)*)[.)]\s", txt) or re.search(r"\d", txt)
                     or re.match(r"\s*[\u2022\u25cf\u25aa\u25a0\u00b7\ue000-\uf8ff]", txt))
            if not (pe or ne or closed or opens):
                if ys is None:
                    ys = body_line_ys(table)
                yi, yp, yn = ys[entries[k][0]], ys[entries[prev][0]], ys[entries[nxt][0]]
                if None not in (yi, yp, yn) and yp < yi < yn and abs((yi - yp) - (yn - yi)) > 1.0:
                    target = prev if (yi - yp) < (yn - yi) else nxt
        frag_for[target].append((k, txt))

    # a BIL. column exists if the printed header block names one - reading it
    # off the column objects misses tables where the Bil. digits did not
    # cluster into a column of their own
    has_bil = any(re.search(r"\b(BIL|Bil)\.?\b", l) for l in split_header(table)) \
        or any(re.search(r"\b(BIL|Bil)\b", c.header) for c in cols)
    rows: list[Row] = []
    row_at: list[int] = []
    for k in value_idx:
        li, label, toks = entries[k]
        own = "" if re.fullmatch(r"\s*\d{1,3}[.)]?\s*", label) else label
        pieces = sorted(frag_for[k] + [(k, own)], key=lambda x: x[0])
        lab = ""
        for p in pieces:                                       # a word broken at its hyphen rejoins with no space
            t = p[1].strip()
            if t:
                lab = lab + t if lab.endswith("-") and t[:1].isalpha() else (lab + " " + t).strip()
        lab = re.sub(r"\s+", " ", lab).strip()
        lab = re.sub(r"^\d{1,3}[.)]?\s+", "", lab)            # drop Bil.
        lab = re.sub(r"^\d{1,3}[.)]\s*", "", lab)
        lab = re.sub(r"^(?:[ivx]+|[a-z])[.)]\s+", "", lab)    # a. / i. / iii.
        if has_bil:                                            # neighbour's Bil.
            lab = re.sub(r"(?<=[A-Za-z%)]) \d{1,2}\.? (?=[A-Z])", " ", lab)
        lab = re.sub(r"\s+\d{1,3}\.?$", "", lab)              # trailing stray Bil.
        # bullets: real ones and the Symbol-font private-use glyph \uf0b7
        lab = re.sub(r"^[\u2022\u25cf\u25aa\u25a0\u00b7\ue000-\uf8ff\u2013\u2014-]+\s*", "", lab)
        lab = re.sub(r"\s+", " ", lab).strip(" .:")
        cells: dict[int, tuple[str, float]] = {}
        all_vals = [(t, parse_amount(t)) for _, _, t in _value_tokens(table.body[li], exact_flank=True)
                    if (_MONEY_RE.match(t.replace(" ", "")) or t in NIL_CHARS) and parse_amount(t) is not None]
        for s, e, t in toks:
            best, bestov = None, 0
            for ci, c in enumerate(cols):
                ov = min(e, c.right) - max(s, c.left)
                if ov > bestov or (best is None and e > c.left and s < c.right):
                    best, bestov = ci, ov
            if best is None:
                best = min(range(len(cols)), key=lambda ci: abs(cols[ci].right - e))
            v = parse_amount(t)
            if v is not None and best not in cells:
                cells[best] = (t, v)
        if lab or cells:
            rows.append(Row(label=lab, cells=cells, tokens=all_vals))
            row_at.append(k)

    # Printed section headings are emitted as valueless rows in printed order,
    # so a consumer can resolve a bare `JUMLAH` from the section it sits under.
    if headings:
        merged: list[Row] = []
        ri = 0
        for hk, htxt in headings:
            while ri < len(rows) and row_at[ri] < hk:
                merged.append(rows[ri])
                ri += 1
            merged.append(Row(label=re.sub(r"\s+", " ", htxt).strip(" .:"), cells={}))
        merged.extend(rows[ri:])
        rows = merged

    # Shifted block: every value row prints the same number of figures as the header strip prints
    # units, but the rows are set at different offsets, so right-edge clustering made MORE data columns
    # than the header labels and some figures fell into columns with no unit at all.  The printed order
    # is then the only reliable geometry: the k-th figure of each row belongs to the k-th unit column.
    # Selangor CMD.61.2015 J4.11: row 1 is set ~10 characters left of rows 2-5, which shipped the 2013
    # column (386.30, 62.97, 63.86, 45.37) as FY2014 and dropped the 2014 figures.
    unit_cols = [ci for ci, c in enumerate(cols) if c.unit]
    stray = any(not cols[ci].unit for r in rows for ci in r.cells)
    # The columns to map onto are the widest set used by a row that sits ON the strip (its every figure under a
    # unit), not every unit column: a misplaced row can itself create a spurious unit cluster (Melaka
    # CMD.53.2015 J4.22, whose `Baki Pada 31 Disember` would otherwise be pushed one year left).
    on_strip = Counter(tuple(sorted(r.cells)) for r in rows
                       if r.cells and all(cols[ci].unit for ci in r.cells))
    ref = max(on_strip, key=lambda t: (len(t), on_strip[t]), default=())
    if stray and len(ref) >= 2:
        for r in rows:
            # only a row that landed off the strip AND printed exactly one figure per reference column: Melaka
            # CMD.37.2016 J4.43 sets only its `Jumlah` line further right (the 2014 total 861.71 shipped as FY2015)
            if (any(not cols[ci].unit for ci in r.cells) and r.tokens
                    and len(r.tokens) == len(ref)):
                r.cells = dict(zip(ref, r.tokens))
                r.ordinal_fallback = True

    # Ordinal fallback: a few rows (typically the JUMLAH row) are printed with
    # their own spacing, so their tokens cluster into neighbouring columns.
    # Rows with the modal cell-count but a different index tuple are remapped
    # ordinally onto the modal tuple.
    tuples = Counter(tuple(sorted(r.cells)) for r in rows if r.cells)
    if tuples:
        # The modal tuple is chosen for covering the most YEAR columns, but in
        # a matrix that interleaves `(RM Juta)` and `(%)` a year legitimately
        # spans BOTH, so counting percent columns lets a `(%)`-heavy tuple win
        # and the remap then drags a row's money cells one column to the right
        # (Sarawak CMD.43.2018 J4.14 `Royalti Hutan`: FY2015 became 7.4).  Only
        # MONEY year columns count.
        yearcols = {ci for ci, c in enumerate(cols)
                    if c.year and c.unit.startswith("(RM")}
        if not yearcols:
            yearcols = {ci for ci, c in enumerate(cols) if c.year}
        modal, n = max(
            tuples.items(),
            key=lambda kv: (len(set(kv[0]) & yearcols), kv[1], -len(kv[0])),
        )
        if n >= 2:
            for r in rows:
                key = tuple(sorted(r.cells))
                if key != modal and len(key) == len(modal):
                    vals = [r.cells[k] for k in key]
                    r.cells = dict(zip(modal, vals))
                    r.ordinal_fallback = True
                elif key != modal and r.tokens and len(r.tokens) == len(modal) and len(key) < len(modal):
                    # Tokens COLLIDED: the row printed exactly as many values as the modal row has
                    # columns, but tighter spacing put two of them in one column and one was dropped.
                    # Selangor CMD.41.2019 J11 `JUMLAH 1,649.60 100.0 1,886.80 100.0 ...` shipped 2015's
                    # total as 100.0 (its share). Map the printed values in order onto the modal columns.
                    r.cells = dict(zip(modal, r.tokens))
                    r.ordinal_fallback = True
    return rows


def heading_of(table: RawTable) -> str:
    """The printed JADUAL title only, with the column-header block removed.

    Needed because a `-layout` dump glues the header words onto the title, and
    header words such as AGENSI would otherwise trip the agency-section filter.
    """
    hdr = set(id(l) for l in split_header(table))
    txt = " ".join(l.strip() for l in table.title_lines
                   if l.strip() and id(l) not in hdr)
    return re.sub(r"\s+", " ", txt).strip()


def parse_table(table: RawTable, group_by_bil: bool = False,
                strict_sections: bool = False
                ) -> tuple[list[Column], list[Row]]:
    """`strict_sections` turns on indent-aware label joining and printed
    section-heading detection.  It is used for the Penyata Prestasi Kewangan,
    whose strict two-tier `HASIL: / TOLAK: / PERBELANJAAN:` layout the
    distance-only join mangles; the department- and fund-detail tables have no
    such tiering and are left on the original join."""
    cols = build_columns(table.body, split_header(table))
    if not cols:
        return cols, []
    if group_by_bil:
        rows = parse_rows_by_bil(table, cols)
        if rows is not None:
            return cols, rows
    return cols, parse_rows(table, cols, strict_sections=strict_sections)
