#!/usr/bin/env python3
"""Extract all 13 Malaysian states' audited state finances from the Jabatan
Audit Negara "Penyata Kewangan Kerajaan Negeri" volumes.

    python3 pipeline/extract_states.py --all            # all 13 states
    python3 pipeline/extract_states.py --state Sarawak  # one state
    python3 pipeline/extract_states.py --all --national # + the national panel

Everything state-specific is in `state_config` (the volume manifest, the state's
own revenue heads, its agency-name prefixes); the parsing logic
(`lkan_state_parser`) and the table catalogue (`table_catalog`) are shared by
every state and contain no state name at all.

Outputs, per state slug:
    data/<slug>/state_reports_<slug>.csv
    data/<slug>/fact_state_finance_<slug>.csv
    data/<slug>/fact_state_revenue_<slug>.csv
    data/<slug>/fact_state_agency_sijil_<slug>.csv
    data/<slug>/_unparsed_tables_<slug>.csv   (matched but refused, with reason)
    data/<slug>/_dropped_rows_<slug>.csv      (label could not be defended)
and, with --national:
    data/_national/fact_state_finance_all.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lkan_state_parser as P            # noqa: E402
import state_config as SC                # noqa: E402
import table_catalog as TC               # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # sources/states
REPO = os.path.dirname(os.path.dirname(ROOT))
RAW = os.path.join(REPO, "sources", "audit-negara", "raw", "backfill")
DATA = os.path.join(ROOT, "data")
CACHE = os.path.join(ROOT, ".textcache")

SOURCE = "parlimen.gov.my Command Paper"


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------

_PENYUMBANG_TOTAL = re.compile(r"^\s*jumlah\s+penyumbang\b", re.I)

def cover_title(pages: list[str]) -> str:
    """The title block printed on the volume's own title page."""
    for p in pages[:6]:
        lines = [re.sub(r"\s+", " ", l.strip()) for l in p.split("\n") if l.strip()]
        lines = [l for l in lines if not re.search(r"\.indd|^www|^ISSN|^\d[\d ]+$", l)]
        caps = [l for l in lines if l.upper() == l and len(l) > 3]
        if len(caps) >= 3:
            return " ".join(caps[:9])
    return ""


def cover_fiscal_year(pages: list[str], state: str) -> str:
    """The fiscal year the volume ITSELF says it audits: the state-statement
    section heading first, the cover's `TAHUN <year>` second.  Returns '' when
    the volume states neither."""
    flat = re.sub(r"\s+", " ", "\n".join(pages))
    m = re.search(r"PENYATA KEWANGAN KERAJAAN NEGERI[^.]{0,60}?"
                  r"TAHUN BERAKHIR 31 DISEMBER (\d{4})", flat, re.I)
    if m:
        return m.group(1)
    front = re.sub(r"\s+", " ", "\n".join(pages[:4])).upper()
    m = re.search(r"TAHUN (20\d{2})", front)
    return m.group(1) if m else ""


def build_manifest(state: str) -> list[dict]:
    rows = []
    for v in SC.VOLUMES[state]:
        path = os.path.join(RAW, v["file"])
        pages = P.load_pages(path, CACHE)
        npages = int(subprocess.run(
            ["pdfinfo", path], capture_output=True, text=True
        ).stdout.split("Pages:")[1].split()[0])
        printed_fy = cover_fiscal_year(pages, state)
        cfg_fy = str(v["fiscal_year"] or "")
        if cfg_fy and printed_fy and printed_fy != cfg_fy:
            raise SystemExit(
                f"COVER MISMATCH {state} {v['file']}: config says FY{cfg_fy}, "
                f"the volume's own front matter says FY{printed_fy}")
        rows.append(dict(
            state=state,
            report=v["report"],
            volume_title_bm=cover_title(pages),
            fiscal_year_audited=cfg_fy,
            fiscal_year_printed_in_volume=printed_fy,
            agency_fiscal_year_reported=v["agency_fiscal_year"] or "",
            scope=v["scope"],
            era=v["era"],
            text_layer=v.get("text_layer", "text"),
            command_paper=v["command_paper"],
            file_name=v["file"],
            sha256=P.sha256(path),
            size_bytes=os.path.getsize(path),
            pages=npages,
            cover_verified="yes (cover title block + printed fiscal year)",
            source=SOURCE,
            source_url_note="join on command_paper to "
                            "sources/audit-negara/data/lkan_reports_backfill.csv",
        ))
    return rows


# ---------------------------------------------------------------------------
# fiscal tables
# ---------------------------------------------------------------------------

def unit_factor(unit: str) -> float | None:
    u = unit.replace(" ", "").lower()
    if "rmjuta" in u:
        return 1_000_000
    if "rmbilion" in u:
        return 1_000_000_000
    if u in ("(rm)", "rm"):
        return 1.0
    return None


_ANGGARAN = re.compile(r"anggaran|peruntukan", re.I)
_SEBENAR = re.compile(r"sebenar|kutipan|perbelanjaan", re.I)


def _undouble(rows: list) -> list:
    """Collapse a table printed twice by a DOUBLED text layer.

    The 2019+ volumes duplicate their whole text layer.  `find_tables` already
    drops a duplicated JADUAL block, but where `-layout` interleaves the two
    copies line by line the duplicate lands INSIDE one block and every printed
    item is parsed twice - with different label wrapping each time, so the
    labels do not match and no label-based test catches it:

        1.  Cukai Tanah                     119.61  122.35  120.74 ...
        1.  Cukai Tanah                     119.61  122.35  120.74 ...
            Perolehan daripada Jualan
        2.  Perolehan daripada Jualan       101.98  112.64   97.44 ...
        2.  Barang-barang                   101.98  112.64   97.44 ...

    The components of Negeri Sembilan CMD.34.2019 J11/J12 then summed to
    EXACTLY twice the printed JUMLAH, and that was filed as an
    Auditor-General misprint.  Identical cells are the reliable signal, so
    rows carrying byte-identical figures in byte-identical columns are folded
    - but only when most of the table is doubled, never on a lone coincidence.
    """
    sig = {}
    for i, r in enumerate(rows):
        # an all-nil row is not evidence of anything: several printed lines
        # legitimately read 0.00 / `-` in the same columns
        if r.cells and any(v[1] for v in r.cells.values()):
            sig.setdefault(tuple(sorted((c, v[0]) for c, v in r.cells.items())),
                           []).append(i)
    # the two copies are interleaved line by line, so a duplicate is ADJACENT;
    # two rows far apart carrying the same figures are two printed rows
    dup = {}
    for k, idxs in sig.items():
        keep = [idxs[0]]
        for i in idxs[1:]:
            if i - keep[-1] <= 2:
                dup.setdefault(k, []).append(i)
            else:
                keep.append(i)
    n_data = sum(1 for r in rows if r.cells)
    # a doubled LAYER doubles the whole table, so demand real evidence: at
    # least three duplicated items in a table of at least six.  Two rows of a
    # short investment table that happen to print the same figures are not it.
    if (len(dup) < 3 or n_data < 6
            or (sum(len(v) for v in dup.values()) + len(dup)) < 0.6 * n_data):
        return rows
    drop = {i for v in dup.values() for i in v}
    return [r for i, r in enumerate(rows) if i not in drop]


def extract_volume(state: str, v: dict, rev_rules) -> tuple[list, list, list, list]:
    path = os.path.join(RAW, v["file"])
    pages = P.load_pages(path, CACHE)
    fy = v["fiscal_year"]

    if v.get("text_layer") == "image_only":
        return [], [], [dict(
            state=state, fiscal_year=fy, spec_id="(whole volume)", jadual="",
            source_file=v["file"], pdf_page="", printed_page="",
            heading=cover_title(pages)[:200],
            reason="volume has no text layer (image-only scan): pdftotext "
                   "returns no JADUAL heading on any page - OCR required, "
                   "nothing extracted rather than partially extracted")], []

    tables = P.find_tables(pages, v["file"])
    if not tables:
        return [], [], [dict(
            state=state, fiscal_year=fy, spec_id="(whole volume)", jadual="",
            source_file=v["file"], pdf_page="", printed_page="",
            heading=cover_title(pages)[:200],
            reason="no JADUAL block found in the text layer")], []
    end = SC.state_section_end(pages, tables[0].pdf_page)

    fin: list[dict] = []
    rev: list[dict] = []
    bad: list[dict] = []
    dropped: list[dict] = []

    for t in tables:
        heading = P.heading_of(t)
        cls = TC.classify(heading, t.pdf_page < end)
        if not cls:
            continue
        spec_id, target, statement = cls
        cols, rows = P.parse_table(
            t, group_by_bil=spec_id in TC.BIL_GROUPED_SPECS,
            strict_sections=spec_id in TC.SECTIONED_SPECS)
        rows = _undouble(rows)
        penyumbang_total = (spec_id == "hasil_penyumbang_utama"
                            and any(_PENYUMBANG_TOTAL.match(r.label or "") for r in rows))
        year_cols = [ci for ci, c in enumerate(cols) if c.year and unit_factor(c.unit)]

        # `KUTIPAN HASIL SEBENAR BERBANDING ANGGARAN` prints estimate/actual
        # columns instead of year columns - identify them by header words, or
        # ordinally (the template always prints Anggaran first).
        measures: dict[int, str] = {}
        geometry = "clean"
        # `hasil_anggaran` IS the estimate-vs-actual table, so its columns are
        # resolved from the ANGGARAN/SEBENAR headers even when the title also
        # carries a year (`Kutipan Hasil Berbanding Anggaran ... Pada Tahun
        # 2014` gives BOTH columns the year 2014, and tagging both `actual`
        # ships the estimate as the state's revenue).
        if spec_id == "hasil_anggaran":
            money = [ci for ci, c in enumerate(cols) if unit_factor(c.unit)]
            # map the ANGGARAN / SEBENAR captions to columns by the caption's
            # own x-centre: a `header` string can pick up BOTH captions when
            # the columns are tightly set, and then neither can be told apart
            def _nearest_money(centre):
                if not money:
                    return None
                return min(money, key=lambda ci: abs(
                    (cols[ci].left + cols[ci].right) / 2 - centre))
            cap: dict[str, int] = {}
            for hl in P.split_header(t):
                for m in re.finditer(r"\b(Anggaran|ANGGARAN|Sebenar|SEBENAR)\b", hl):
                    ci = _nearest_money((m.start() + m.end()) / 2)
                    if ci is not None:
                        cap.setdefault(m.group(0).lower(), ci)
            if ("anggaran" in cap and "sebenar" in cap
                    and cap["anggaran"] != cap["sebenar"]):
                measures = {cap["anggaran"]: "estimate", cap["sebenar"]: "actual"}
                year_cols = list(measures)
        if not measures and spec_id in ("hasil_anggaran", "perbelanjaan_mengurus",
                       "perbelanjaan_pembangunan") and not year_cols:
            money = [ci for ci, c in enumerate(cols) if unit_factor(c.unit)]
            if len(money) >= 2:
                a = [ci for ci in money if _ANGGARAN.search(cols[ci].header)]
                s = [ci for ci in money if _SEBENAR.search(cols[ci].header)]
                if a and s and a[0] != s[0]:
                    measures = {a[0]: "estimate", s[0]: "actual"}
                else:
                    measures = {money[0]: "estimate", money[1]: "actual"}
                year_cols = list(measures)

        if not year_cols:
            bad.append(dict(state=state, fiscal_year=fy, spec_id=spec_id,
                            jadual=t.jadual, source_file=v["file"],
                            pdf_page=t.pdf_page, printed_page=t.printed_page,
                            heading=heading[:200],
                            reason="no money column with a resolvable year"))
            continue

        # Column-geometry guard.  In the 5-year trend tables that interleave a
        # (%) column after every year, the centred year headings can bleed onto
        # the neighbouring year's money column.  Refuse a table whose money
        # columns do not carry each header year exactly once, in printed order.
        if not measures:
            ys = [cols[ci].year for ci in year_cols]
            hdr_years = []
            for hl in P.split_header(t):
                for m in re.finditer(r"\b(?:19|20)\d{2}\b", hl):
                    if m.group(0) not in hdr_years:
                        hdr_years.append(m.group(0))
            ordered = ys == sorted(ys) or ys == sorted(ys, reverse=True)
            if len(set(ys)) != len(ys) or not ordered:
                bad.append(dict(
                    state=state, fiscal_year=fy, spec_id=spec_id,
                    jadual=t.jadual, source_file=v["file"],
                    pdf_page=t.pdf_page, printed_page=t.printed_page,
                    heading=heading[:200],
                    reason=f"column/year geometry unresolved: money columns={ys} "
                           f"header years={hdr_years}"))
                continue
            if hdr_years and set(ys) != set(hdr_years):
                # A column that lost its year cannot be told apart from one
                # that kept the WRONG year, so the whole table is rejected
                # rather than risk mislabelling a year (golden rule 2).
                bad.append(dict(
                    state=state, fiscal_year=fy, spec_id=spec_id,
                    jadual=t.jadual, source_file=v["file"],
                    pdf_page=t.pdf_page, printed_page=t.printed_page,
                    heading=heading[:200],
                    reason=f"column/year geometry unresolved (a printed year "
                           f"column could not be matched): money columns={ys} "
                           f"header years={hdr_years}"))
                continue

        sumber = re.sub(r"\s+", " ", t.sumber).strip()
        basis = "audited" if re.search(r"penyata kewangan", sumber, re.I) else "audit_analysis"

        n_years = len({cols[ci].year for ci in year_cols if cols[ci].year})
        table_role = "trend" if n_years > 2 else "current"

        # Row-completeness guard for the multi-year matrices.  These tables
        # print a figure in EVERY year column of EVERY row - none of them has a
        # ragged year.  So when most printed rows cannot be filled across the
        # year columns, the row/column geometry of that page has not been
        # resolved, whatever the header says, and the rows that DID land are
        # not trustworthy either (Sarawak CMD.44.2016 J4.13 pdf p34: two of
        # seven rows complete, `Royalti Hutan` welded onto the previous item's
        # wrapped `Minyak`, `Dividen` carrying one year of five).  Refuse the
        # whole table, as README section 8.3 already does for this class -
        # every one of those years is extracted from its own volume anyway.
        if (spec_id in TC.BIL_GROUPED_SPECS and not measures
                and n_years >= 3 and rows):
            data_rows = [r for r in rows if r.cells]
            full = sum(1 for r in data_rows
                       if all(ci in r.cells for ci in year_cols))
            if data_rows and full / len(data_rows) < 0.6:
                bad.append(dict(
                    state=state, fiscal_year=fy, spec_id=spec_id,
                    jadual=t.jadual, source_file=v["file"],
                    pdf_page=t.pdf_page, printed_page=t.printed_page,
                    heading=heading[:200],
                    reason=f"row/column geometry unresolved: only {full} of "
                           f"{len(data_rows)} printed rows could be filled "
                           f"across all {len(year_cols)} year columns"))
                continue

        # In a BIL-grouped matrix the printed JUMLAH row is typeset with its
        # own spacing and its tokens do not always land in the year columns.
        # Rather than emit a silently partial total, such a row is flagged.
        modal_cells = 0
        if spec_id in TC.BIL_GROUPED_SPECS and rows:
            from collections import Counter as _C
            cnt = _C(len(r.cells) for r in rows if r.cells)
            modal_cells = cnt.most_common(1)[0][0] if cnt else 0

        group = ""          # last printed group heading inside the table body
        section = ""        # last printed SECTION heading (Prestasi Kewangan)
        # The FIRST section caption of a Penyata Prestasi Kewangan is printed
        # above the first figures line, so it lands in the title block and the
        # row parser never sees it.  Without it the revenue block's bare
        # `Jumlah` has no section and cannot be told from the expenditure
        # block's (Negeri Sembilan CMD.54.2015 J4.25).
        for hl in reversed(t.title_lines):
            s0 = TC.section_group(re.sub(r"\s+", " ", hl).strip())
            if s0:
                section = s0
                break
        for r in rows:
            if not r.label:
                continue
            if not r.cells:
                s = TC.section_group(r.label)
                if s:
                    section = s
            g = TC.revenue_group(r.label)
            if g and not r.cells:
                group = g
                continue
            quality, why = label_quality(r.label)
            if quality == "reject":
                dropped.append(dict(
                    state=state, fiscal_year=fy, spec_id=spec_id,
                    jadual=t.jadual, source_file=v["file"],
                    pdf_page=t.pdf_page, printed_page=t.printed_page,
                    line_label_bm=r.label[:300], reason=why))
                continue
            if g:
                group = g
            code, conformed = TC.line_code(spec_id, r.label, section)
            # Table-level rule: Negeri Sembilan prints a `JUMLAH HASIL RM421.24 Juta` banner (ALL revenue) above
            # the contributor list AND the real subtotal `JUMLAH PENYUMBANG UTAMA HASIL 382.59` (CMD.34.2019 J11).
            # Where a table prints a `JUMLAH PENYUMBANG ...` line, that line alone is the top-five total; any
            # other JUMLAH line keeps its printed label under an unconformed code. In tables without one (15
            # other states), `JUMLAH HASIL` IS the top-five caption and the dictionary rule stands.
            if (code == "revenue_top_contributors_total" and penyumbang_total
                    and not _PENYUMBANG_TOTAL.match(r.label)):
                code, conformed = f"{spec_id}.{TC.slug(r.label)}", False
            # Once a financing line has been printed, a later bare `JUMLAH` is
            # the financing total - several states print the `Dibiayai oleh:`
            # caption glued to the first financing row instead of as its own
            # heading, so there is no standalone section line to read.
            if spec_id == "prestasi_kewangan" and code.startswith("financing_"):
                section = "pembiayaan"
            row_geometry = geometry
            if modal_cells and 0 < len(r.cells) < modal_cells:
                row_geometry = ("incomplete_row: %d of %d printed columns could "
                                "be assigned" % (len(r.cells), modal_cells))
            for ci in year_cols:
                if ci not in r.cells:
                    continue
                printed, val = r.cells[ci]
                f = unit_factor(cols[ci].unit)
                year = cols[ci].year or (str(fy) if fy else "")
                # `PERUNTUKAN DILULUSKAN / MUKTAMAD` is an APPROVED ALLOCATION,
                # i.e. an estimate, not an outturn - tag it the same way the
                # revenue file tags its ANGGARAN columns.
                meas = measures.get(ci, "actual")
                if spec_id == "peruntukan_mengurus" and meas == "actual":
                    meas = "estimate"
                rtype = TC.row_type(code, r.label)
                rec = dict(
                    state=state,
                    fiscal_year=year,
                    statement=statement,
                    spec_id=spec_id,
                    line_code=code,
                    line_code_conformed="yes" if conformed else "no",
                    line_label_bm=r.label,
                    amount_printed=printed,
                    unit_printed=cols[ci].unit,
                    amount_rm=f"{val * f:.2f}",
                    amount_rm_conformed=f"{(abs(val) if code in TC.LEVEL_CODES else val) * f:.2f}",
                    sign_convention=("level_abs" if code in TC.LEVEL_CODES
                                     else "as_printed"),
                    row_type=rtype,
                    is_leaf="yes" if rtype == "component" else "no",
                    measure=meas,
                    column_role="own_year" if str(fy) == year else "comparative",
                    table_role=table_role,
                    label_quality=quality,
                    basis=basis,
                    report=v["report"],
                    command_paper=v["command_paper"],
                    source_file=v["file"],
                    pdf_page=t.pdf_page,
                    printed_page=t.printed_page,
                    jadual=t.jadual,
                    table_title_bm=heading,
                    sumber_bm=sumber,
                    ordinal_fallback="yes" if r.ordinal_fallback else "no",
                    column_geometry=row_geometry,
                )
                if target == "revenue":
                    rec["revenue_class"] = TC.revenue_class(r.label, group, code,
                                                            rev_rules)
                    rec["revenue_group_printed_bm"] = group
                    rev.append(rec)
                else:
                    fin.append(rec)

    # `LEBIHAN` vs `LEBIHAN KESELURUHAN`.  Negeri Sembilan's Penyata Prestasi
    # Kewangan prints TWO balance lines - a first `LEBIHAN` that is only
    # revenue less operating expenditure, and `(KURANGAN)/LEBIHAN KESELURUHAN`
    # after development expenditure.  The plain label matched `surplus_deficit`
    # first, so the state's headline balance series carried the intermediate
    # figure (FY2020: 27.82 instead of (64.72), which is what the volume's own
    # `JUMLAH PEMBIAYAAN` and narrative both give).  Where a table prints both,
    # the KESELURUHAN line is the balance and the first one is demoted.
    by_tab: dict[tuple, list[dict]] = defaultdict(list)
    for rec in fin:
        if rec["spec_id"] == "prestasi_kewangan":
            by_tab[(rec["source_file"], rec["jadual"], rec["fiscal_year"],
                    rec["measure"])].append(rec)
    for recs in by_tab.values():
        whole = [r for r in recs
                 if "keseluruhan" in r["line_code"] and r["line_code_conformed"] == "no"]
        plain = [r for r in recs if r["line_code"] == "surplus_deficit"]
        if not whole or not plain:
            continue
        for r in plain:
            r["line_code"] = "prestasi_kewangan.lebihan_sebelum_perbelanjaan_pembangunan"
            r["line_code_conformed"] = "no"
            r["row_type"] = "subtotal"
            r["is_leaf"] = "no"
        for r in whole:
            r["line_code"] = "surplus_deficit"
            r["line_code_conformed"] = "yes"
            r["row_type"] = "derived"
            r["is_leaf"] = "no"
            r["sign_convention"] = "level_abs"
            r["amount_rm_conformed"] = "%.2f" % abs(float(r["amount_rm"]))
    return fin, rev, bad, dropped


# ---------------------------------------------------------------------------
# row hygiene
# ---------------------------------------------------------------------------

# `. b` starts a sentence; `. B` is an abbreviation (`Sdn. Bhd`, `No. Pinjaman`)
_SENTENCE = re.compile(r"\.\s+[a-z]")
_PROSE = re.compile(r"\bialah\b|\bdisebabkan\b|\bmenyebabkan\b|\bseperti di\b|"
                    r"\bseperti dalam\b|\badalah seperti\b|\bmanakala\b|"
                    r"\bBagaimanapun\b|\bAnalisis Audit\b", re.I)
_STRAY_BIL = re.compile(r"(?<=[A-Za-z%)])\s\d{1,2}\.?\s(?=[A-Z])")


def label_quality(label: str) -> tuple[str, str]:
    """-> ('clean'|'partial'|'reject', reason).

    The `-layout` dump can interleave a neighbouring narrative column or a
    running footer into a row label.  A label that reads as prose is rejected
    outright rather than emitted as a scrambled string (golden rule 3: a row
    whose identity cannot be defended is not a row).
    """
    n = len(label.split())
    if (_PROSE.search(label) or _SENTENCE.search(label)) and n >= 8:
        return "reject", "label reads as narrative prose, not a table row label"
    if n > 25:
        return "reject", f"label is {n} words - column interleaving suspected"
    if _STRAY_BIL.search(label):
        return "partial", "a neighbouring row's Bil. number remains in the label"
    #  is the Symbol-font private-use bullet the era-4 volumes use.
    if "" in label or "•" in label:
        return "partial", "a printed bullet separates two label tiers"
    return "clean", ""


# ---------------------------------------------------------------------------
# canonical row selection (so sum() over the file cannot double-count)
# ---------------------------------------------------------------------------

_TOLR = 11_000.0        # RM - the volumes print 2 dp in RM Juta


def arbitrate_prestasi(rows: list[dict]) -> list[dict]:
    """Resolve duplicate headline codes inside ONE printed Penyata Prestasi
    Kewangan using that volume's OWN arithmetic.

    Several states print the statement as a two-step ladder:

        JUMLAH HASIL                    1,674.29
        TOLAK: Perbelanjaan Mengurus      968.64
        LEBIHAN/(KURANGAN)                705.65   <- revenue less opex
        TOLAK: Perbelanjaan Pembangunan   665.82
        LEBIHAN/(KURANGAN)                 39.83   <- the OVERALL surplus
        ... JUMLAH                        (39.83)  <- financing block agrees

    Both rungs carry the identical printed label, so no label rule can tell
    them apart and picking blind ships the intermediate figure as the state's
    surplus (Johor FY2020: 705.65 against a true 39.83, 17.7x overstated).
    The volume itself says which is which: the overall surplus is the one that
    equals `revenue - expenditure` and `|financing_total|`.  The intermediate
    rung is re-coded `surplus_before_devex` rather than dropped.

    Returns the rows whose code changed, for the diagnostic log.
    """
    changed: list[dict] = []
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if r["spec_id"] == "prestasi_kewangan":
            groups[(r["source_file"], r["pdf_page"], r["jadual"],
                    r["fiscal_year"], r["measure"])].append(r)

    for key, grp in groups.items():
        by: dict[str, list[dict]] = defaultdict(list)
        for r in grp:
            by[r["line_code"]].append(r)

        def one(code):
            v = by.get(code)
            return float(v[0]["amount_rm"]) if v and len(v) == 1 else None

        rev, exp = one("revenue_total"), one("expenditure_total")
        opex, dev = one("opex_before_transfer"), one("devex_total")
        fin_t = one("financing_total")
        if exp is None and opex is not None and dev is not None:
            exp = abs(opex) + abs(dev)

        cands = by.get("surplus_deficit", [])
        if len(cands) < 2:
            continue
        targets = []
        if fin_t is not None:
            targets.append(abs(fin_t))
        if rev is not None and exp is not None:
            targets.append(abs(abs(rev) - abs(exp)))
        if not targets:
            continue
        best, bestd = None, None
        for r in cands:
            d = min(abs(abs(float(r["amount_rm"])) - t) for t in targets)
            if bestd is None or d < bestd:
                best, bestd = r, d
        if bestd is None or bestd > _TOLR:
            continue                      # cannot resolve: leave as printed
        inter = abs(abs(rev) - abs(opex)) if (rev is not None and opex is not None) else None
        for r in cands:
            if r is best:
                continue
            v = abs(float(r["amount_rm"]))
            if inter is not None and abs(v - inter) <= _TOLR:
                r["line_code"] = "surplus_before_devex"
            else:
                r["line_code"] = "surplus_deficit_intermediate"
            r["row_type"] = "derived"
            r["is_leaf"] = "no"
            changed.append(r)
    return changed


_TRUST_SUBFUNDS = ("development_fund", "housing_loan_fund",
                   "misc_govt_trust_funds", "forest_development_fund")


def mark_trust_hierarchy(rows: list[dict]) -> None:
    """Record whether each printed trust-account table is NESTED or FLAT, and
    make `row_type` agree with it.

    `govt_trust_funds` is a ROLL-UP of the four sub-funds in Kedah and Selangor
    but a SIBLING of them in Kelantan, so a single fixed `row_type` is wrong for
    one of the two and golden rule 5 cannot reconstruct the flat states'
    Akaun Amanah Disatukan.  Which hierarchy a table prints is decided from the
    table's OWN arithmetic - whichever composition reconciles to the printed
    `Akaun Amanah Disatukan` - and written to `hierarchy` on every row of that
    table.  In a flat table the four siblings are all `component`; in a nested
    table `govt_trust_funds` stays a `subtotal` and the sub-funds are its
    components.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if r["spec_id"] in ("kumpulan_wang_disatukan", "akaun_amanah_disatukan"):
            groups[(r["source_file"], r["pdf_page"], r["jadual"],
                    r["fiscal_year"], r["measure"])].append(r)

    for grp in groups.values():
        val: dict[str, float] = {}
        for r in grp:
            val.setdefault(r["line_code"], float(r["amount_rm"]))
        tot = val.get("trust_account_balance")
        gtf = val.get("govt_trust_funds")
        pub, dep = val.get("public_trust_funds"), val.get("deposit_account")
        subs = {c: val[c] for c in _TRUST_SUBFUNDS if c in val}
        hier = ""
        if None not in (tot, pub, dep) and gtf is not None:
            if abs(gtf + pub + dep - tot) <= _TOLR:
                hier = "nested"
            elif subs and abs(gtf + sum(subs.values()) + pub + dep - tot) <= _TOLR:
                hier = "flat"
        for r in grp:
            r["hierarchy"] = hier
            if hier == "flat" and r["line_code"] in (("govt_trust_funds",) + _TRUST_SUBFUNDS):
                r["row_type"] = "component"
                r["is_leaf"] = "yes"
            elif hier == "nested" and r["line_code"] in _TRUST_SUBFUNDS:
                r["row_type"] = "component"
                r["is_leaf"] = "yes"


def fix_debt_totals(rows: list[dict]) -> int:
    """Public-debt tables print several JUMLAH lines; only one is the year-end debt (page-proved 2026-11-04).

    * a MOVEMENT table ('PERGERAKAN HUTANG AWAM': opening, loans, repayments, closing) prints balances, not
      the year-end figure, by column (Selangor CMD.52.2022 J56, CMD.49.2023 J53): its JUMLAH lines become
      debt_movement_total;
    * where a table prints a grand total ('JUMLAH HUTANG AWAM' / 'JUMLAH KESELURUHAN'), a plain 'JUMLAH' in
      the same table is a subtotal (Pahang CMD.44.2021 J32: JUMLAH 3,009.89 federal loans + 60.00 financial
      institutions = JUMLAH HUTANG AWAM 3,069.89): it becomes debt_subtotal;
    * a table with one JUMLAH keeps it as debt_total."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if r["spec_id"] == "hutang_awam":
            groups[(r["source_file"], r["pdf_page"], r["jadual"], r["fiscal_year"], r["measure"],
                    r["column_role"])].append(r)
    n = 0
    for grp in groups.values():
        dt = [r for r in grp if r["line_code"] == "debt_total"]
        if not dt:
            continue
        if any("pergerakan" in (r.get("table_title_bm") or "").lower() for r in grp):
            for r in dt:
                r["line_code"], n = "debt_movement_total", n + 1
            continue
        grand = [r for r in dt if re.search(r"hutang awam|keseluruhan", r["line_label_bm"], re.I)]
        if grand:
            for r in dt:
                if r not in grand:
                    r["line_code"], n = "debt_subtotal", n + 1
    return n


def mark_canonical(rows: list[dict]) -> None:
    """Exactly one row per (source_file, fiscal_year, measure, line_code) gets
    is_canonical=yes.  Because a volume's own_year rows exist in that volume
    only, filtering `column_role=own_year AND is_canonical=yes AND
    measure=actual` yields exactly one row per (fiscal_year, line_code)."""
    best: dict[tuple, dict] = {}
    for r in rows:
        k = (r["source_file"], r["fiscal_year"], r["measure"], r["line_code"])
        cur = best.get(k)
        if cur is None or _rank(r) < _rank(cur):
            best[k] = r
    chosen = {id(r) for r in best.values()}
    for r in rows:
        r["is_canonical"] = "yes" if id(r) in chosen else "no"


def _rank(r: dict) -> tuple:
    """Lower is better: the statement that DEFINES the code, a current-year
    table over a trend table, a clean label, then the earliest jadual."""
    defining = TC.PRIMARY_SPEC_OF.get(r["line_code"])
    # position within the ordered preference list, so the DEFINING statement
    # wins consistently across eras rather than whichever table the auditor
    # happened to print first
    if defining and r["spec_id"] in defining:
        rank0 = defining.index(r["spec_id"])
    else:
        rank0 = 90 if defining else 95
    return (
        rank0,
        0 if r["table_role"] == "current" else 1,
        0 if r["label_quality"] == "clean" else 1,
        0 if r["line_code_conformed"] == "yes" else 1,
        [int(x) for x in r["jadual"].split(".")],
    )


# ---------------------------------------------------------------------------
# agency registers
# ---------------------------------------------------------------------------
# These volumes do NOT print a full per-agency opinion register the way the
# federal LKAN does.  They print
#   (a) `penyerahan_status`  - a submission / audit-status register listing
#       every state agency (Badan Berkanun Negeri, Majlis Agama Islam, Pihak
#       Berkuasa Tempatan) with its submission date and/or audit status; and
#   (b) `sijil_pendapat`     - ONLY the agencies whose Sijil Ketua Audit Negara
#       carried a modified or Emphasis-of-Matter opinion, grouped under the
#       opinion heading.
# Agencies given a plain unqualified opinion appear in (a) but their opinion is
# reported only as a COUNT in the narrative, so a complete opinion register at
# the grain of `sources/audit-negara/data/fact_agensi_sijil_*.csv` is NOT
# derivable from these volumes.  That is a source absence, not an extraction
# gap - see README section 6.
#
# The register is a THREE-COLUMN printed table (`BIL. | AGENSI | TARIKH
# PENYERAHAN` or `... | STATUS PENGAUDITAN` or `... | ASAS KEPADA PENDAPAT
# AUDIT`) whose cells wrap freely and whose rows are only reliably delimited by
# the BIL. column, so it is parsed geometrically:
#
#   1. the block is collected ACROSS PAGE BREAKS (`join_continuations=True`) -
#      a continued register reprints its column strip but never a new JADUAL
#      heading, and the registers routinely run three pages;
#   2. running heads, InDesign slugs and the repeated column strip are dropped
#      BEFORE row assembly, so footer text such as `... Prestasi Kewangan
#      Agensi Negeri` can never be harvested as an agency;
#   3. each line is cut into segments at runs of >= 3 spaces, and the segments
#      are clustered into the name column and the payload column;
#   4. every line is attached to its NEAREST BIL. line, so a wrapped agency
#      name and a payload cell typeset one line above or below its name are
#      recovered;
#   5. a line with no Bil. and no payload that matches a section/opinion
#      heading is a heading; `Majlis Agama Islam <state>` carries a Bil. and a
#      payload and is therefore an AGENCY, not the `MAJLIS AGAMA ISLAM` heading.

_AGENCY_TABLE = re.compile(
    r"(penyerahan penyata kewangan|kedudukan penyerahan penyata kewangan|"
    r"status pengauditan penyata kewangan)", re.I)
_OPINION_TABLE = re.compile(
    r"(sijil ketua audit negara (dengan|bagi)|penyata kewangan agensi yang diberikan|"
    r"pendapat diubahsuai diberikan)", re.I)
# tables that TALK ABOUT the opinion taxonomy instead of listing agencies
_OPINION_NOT = re.compile(
    r"pemakaian piawaian|pendapat audit dalam sijil|jenis sijil ketua audit", re.I)

_GROUPS = [
    (re.compile(r"^BADAN BERKANUN NEGERI\b", re.I), "badan_berkanun_negeri"),
    (re.compile(r"^MAJLIS AGAMA ISLAM\b", re.I), "majlis_agama_islam"),
    (re.compile(r"^(PIHAK BERKUASA TEMPATAN|PBT)\b", re.I), "pihak_berkuasa_tempatan"),
]
_OPGROUPS = [
    (re.compile(r"PENDAPAT TANPA TEGURAN DENGAN (EOM|PERENGGAN PENEGASAN)|"
                r"PERENGGAN PENEGASAN PERKARA", re.I),
     ("Tanpa Teguran", "Penegasan Perkara (EOM)")),
    (re.compile(r"PERENGGAN HAL-?HAL LAIN", re.I),
     ("Tanpa Teguran", "Hal-hal Lain (OM)")),
    (re.compile(r"PENDAPAT BERTEGURAN", re.I), ("Berteguran", "")),
    (re.compile(r"PENDAPAT BERTENTANGAN", re.I), ("Bertentangan", "")),
    (re.compile(r"PENAFIAN PENDAPAT", re.I), ("Penafian Pendapat", "")),
    (re.compile(r"PENDAPAT TANPA TEGURAN", re.I), ("Tanpa Teguran", "")),
]

_DATE = re.compile(r"(\d{1,2}[./]\d{1,2}[./]\d{2,4})|Belum\s+(diterima|Terima)", re.I)
_STATUS = re.compile(
    r"(Sijil Ketua Audit Negara telah dikeluarkan[^.]*\.?|"
    r"Mesyuarat penutup[^.]*\.?|Pengauditan telah selesai[^.]*\.?|"
    r"Pengauditan oleh[^.]*\.?|Pelantikan FAS[^.]*\.?|"
    r"Penyata kewangan belum diterima\.?|"
    r"Dalam proses pengauditan|Belum Terima|Belum diterima|"
    r"Sedang diaudit|Telah diaudit|Selesai)", re.I)

# lines that are part of the printed furniture, never a register row
# The repeated column strip on a continuation page, in any combination.
_HEADER_WORDS = {"bil", "agensi", "negeri", "tarikh", "diterima", "penyerahan",
                 "status", "pengauditan", "asas", "kepada", "pendapat", "audit",
                 "jenis", "sijil", "ketua", "nama", "no", "bilangan"}
# Running heads and doubled footers.  The duplicated text layer prints them
# with the spaces eaten (`PenyataKewangan KewanganKerajaan Negeri`), so the
# test is run against the line with ALL whitespace removed.
#
# `penyatakewangan` on its own is NOT a footer marker: `Penyata kewangan belum
# diterima.` is a printed audit STATUS, and matching it here silently deleted
# the three most audit-relevant rows of Melaka CMD.41.2023 pdf p91 (bils 9-11,
# the agencies that had not submitted at all).  The running footers always name
# whose statements they are - `... Penyata Kewangan Kerajaan Negeri`,
# `... Penyata Kewangan Agensi Negeri` - so the qualifier is required.
_REG_FOOTER_SQ = re.compile(
    r"\.indd\d|lkan|penyatakewangan(kerajaan|agensi|negeri)|kewangankerajaan|"
    r"kerajaannegeri|"
    r"^agensinegeri$|prestasikewanganagensi|penyerahan,pengesahan|"
    r"pembentanganpenyata|mukasurat|^kandungan$|^rahsia$|^versikabinet$|"
    r"^sumber:|jabatanauditnegara$|^\d+$", re.I)
# The printed column strip: `BIL.` in the stub followed by at least one more
# column caption.  It is reprinted at the top of every continuation page and is
# never a data row, whatever its other captions are called (`BBN`, `PBT`,
# `AGENSI NEGERI`, `Tarikh Serah`, ...).
_COL_STRIP = re.compile(r"^\s*(BIL|Bil)\.?(\s{2,}\S|\s*$)")


#
# The 2019+ volumes carry a DOUBLED text layer, and `-layout` shreds the
# duplicated running head/footer into short fragments spread over half a dozen
# lines with the spaces eaten and whole words repeated:
#
#     82 82            LKANNegeri
#                      LKAN NegeriKelantan
#                                  Kelantan  Tahun
#                                          Tahun    2021
#                      Penyerahan,Pengesahan
#     ...
#
# A squashed-substring blacklist cannot catch every one of those fragments,
# and each survivor is welded onto the last agency of the page (`Majlis Daerah
# Ketereh Kelantan Tahun Tahun 2021`).  So the test is done on TOKENS: split
# glued words, fold a word that is its own doubled self, and refuse the line
# when every word belongs to the running-furniture vocabulary AND at least one
# is a word that only ever appears in the furniture.  A genuine wrapped name
# fragment (`Negeri Kelantan`, `Dan Pelaburan Sabah`) carries no such word and
# is kept.
_FOOTER_ONLY = {
    "lkan", "rahsia", "tahun", "penyerahan", "pengesahan", "pembentangan",
    "prestasi", "muka", "surat", "kandungan", "teks", "indd", "versi",
    "kabinet", "semakan", "penyata", "kewangan", "agensi", "kerajaan",
    "berakhir", "disember", "sumber",
}
_FOOTER_OK = _FOOTER_ONLY | {
    "negeri", "dan", "bagi", "di", "pada", "setakat",
    "johor", "kedah", "kelantan", "melaka", "sembilan", "pahang", "perak",
    "perlis", "pulau", "pinang", "sabah", "sarawak", "selangor", "terengganu",
}


def _defold(w: str) -> list[str]:
    """`NegeriKelantan` -> [negeri, kelantan]; `dandan` -> [dan]."""
    outw = []
    for p in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", w):
        p = p.lower()
        n = len(p)
        if n >= 4 and n % 2 == 0 and p[: n // 2] == p[n // 2:]:
            p = p[: n // 2]
        outw.append(p)
    return outw


def _is_furniture(line: str) -> bool:
    toks = [t for w in re.findall(r"[A-Za-z0-9]+", line) for t in _defold(w)]
    words = [t for t in toks if t.isalpha() and len(t) > 1]
    if not words:
        return False                    # a bare date/page number is not text
    if not all(w in _FOOTER_OK for w in words):
        return False
    # a bare 4-digit year is as much a footer marker as `Tahun` is: the shred
    # leaves fragments such as `Selangor     2020` with no furniture WORD left
    return (any(w in _FOOTER_ONLY for w in words)
            or any(re.fullmatch(r"(19|20)\d{2}", t) for t in toks))


def _is_register_noise(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    sq = re.sub(r"\s+", "", s)
    if _REG_FOOTER_SQ.search(sq):
        return True
    if _COL_STRIP.match(line):
        return True
    if _BIL_LINE.match(line):
        # a numbered register row is never furniture, whatever its cells say:
        # `1.        tahun kewangan 2014.` is bil 1 of a wrapped opinion basis
        # (Pulau Pinang CMD.46.2023 pdf p96), not a running head
        return False
    if _is_furniture(line):
        return True
    # a bare printed folio / section marker (`3-4`, `3 -3`, `108 108|`, `80 80`)
    # - digits and rules only, and never a submission date
    # (no dots: `2.                    -` is a numbered row whose only printed
    # cell is a nil dash, not a folio)
    if re.fullmatch(r"[\d\s]*[-–—|][\d\s\-–—|]*", s):
        return True
    words = re.findall(r"[A-Za-z]+", s.lower())
    if words and all(w in _HEADER_WORDS for w in words):
        return True          # the column strip, e.g. `BIL.   AGENSI   TARIKH`
    return False

_BIL_LINE = re.compile(r"^(\s{0,40})(\d{1,3})\.?(?=\s{2,}|\s*$)")
# lazy optional tail: a cell ends at the FIRST run of >=3 spaces, so
# `     1     Perbadanan Wakaf Selangor (PWS)` yields ['1', 'Perbadanan ...'],
# not one merged cell.
_SEG = re.compile(r"\S(?:.*?\S)??(?=\s{3,}|$)")


def _segments(line: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group(0)) for m in _SEG.finditer(line) if m.group(0).strip()]


def _register_rows(lines: list[str], title: str = "") -> list[dict]:
    """-> [{bil, name, payload, heading}] for one printed register."""
    # Everything above the printed COLUMN STRIP (`BIL. | AGENSI | TARIKH ...`)
    # is the JADUAL title, not data.  Without this cut the title's own
    # `BADAN BERKANUN NEGERI, MAJLIS AGAMA ISLAM DAN / PIHAK BERKUASA
    # TEMPATAN BAGI TAHUN ...` reads as two section headings.
    clean = ["".join(ch for ch in ln if ch >= " " or ch == "\t") for ln in lines]
    start = 0
    for i, ln in enumerate(clean):
        # the printed `BIL.` stub is what marks the column strip; keying off
        # "every word is a known header word" fails the moment a volume names
        # its second column `BBN` or `PBT` (Sabah CMD.43.2016 pdf p66), and
        # then the JADUAL title itself is read as data and welded onto the
        # first agency (`Majlis Perbandaran Tawau Tahun 2015 Setakat 30 Jun
        # 2016 Bil. PBT`).
        if _COL_STRIP.match(ln):
            start = i + 1
            break
        words = re.findall(r"[A-Za-z]+", ln.lower())
        if words and all(w in _HEADER_WORDS for w in words) and "bil" in words:
            start = i + 1
            break
    kept: list[tuple[int, str]] = []
    for ln in clean[start:]:
        if _is_register_noise(ln):
            continue
        kept.append((len(kept), ln))
    if not kept:
        return []

    # -- column geometry -----------------------------------------------------
    bil_at: dict[int, str] = {}
    xs: list[int] = []
    per_line: list[tuple[int, list[tuple[int, str]]]] = []
    for i, ln in kept:
        m = _BIL_LINE.match(ln)
        if m:
            # blank the Bil. cell out before segmenting, so the row number can
            # never be glued to the agency name whatever the column spacing is
            bil_at[i] = m.group(2)
            ln = " " * m.end() + ln[m.end():]
        segs = _segments(ln)
        per_line.append((i, segs))
        xs += [x for x, _ in segs]
    if not xs:
        return []
    # Split the segments into the NAME column and the PAYLOAD column at the
    # midpoint of the two most FREQUENT left edges.  Frequency, not the widest
    # gap: a stray footer fragment at an odd x would otherwise define the cut
    # and swallow the whole payload column into the agency name.
    freq = Counter(xs)
    top = [x for x, _ in freq.most_common(6)]
    c1 = top[0]
    c2 = next((x for x in top[1:] if abs(x - c1) >= 12), None)
    if c2 is None:
        cut = float("inf")
    else:
        cut = (min(c1, c2) + max(c1, c2)) / 2

    out: list[dict] = []
    anchors = sorted(bil_at)
    for i, segs in per_line:
        name = " ".join(t for x, t in segs if x < cut)
        payload = " ".join(t for x, t in segs if x >= cut)
        out.append(dict(idx=i, bil=bil_at.get(i, ""), name=name.strip(),
                        frags=[t for x, t in segs if x < cut],
                        payload=payload.strip(), raw=" ".join(t for _, t in segs)))
    if not anchors:
        return out          # unnumbered register: one printed line = one row

    # -- attach every unnumbered line to its nearest Bil. line ---------------
    #
    # The two printed columns wrap INDEPENDENTLY, and the payload cell is
    # typeset vertically CENTRED on its row, so a three-line status begins one
    # line ABOVE the Bil. it belongs to.  Measuring the distance in raw page
    # lines therefore mixes the columns up:
    #   * Sabah CMD.43.2016 J6.1 - `Kumpulan Wang Penanaman` / `29.03.16` /
    #     `Semula Getah Sabah`: the name continuation is two page-lines from
    #     its own Bil. but only one from the next, so `Semula Getah Sabah` was
    #     welded onto `Lembaga Pelancongan Sabah` and bil 3 shipped truncated
    #     and marked `clean`;
    #   * Melaka CMD.41.2023 J5 - the first line of bil 3's three-line status
    #     is one page-line below bil 2's own status line, so bil 2 was given
    #     the WRONG status and bil 3 lost its opening clause.
    # Distances are therefore measured along each printed COLUMN separately,
    # and a payload fragment that opens a new sentence cannot be appended to a
    # payload cell that has already been closed by a full stop.
    order = [o["idx"] for o in out]
    merged: dict[int, dict] = {a: dict(out[order.index(a)]) for a in anchors}
    aset = set(anchors)
    # printed-order accumulators: a three-line cell is typeset with its MIDDLE
    # line on the Bil., so appending fragments as they are attached would emit
    # the cell as `<middle> <first> <last>`.  Keyed by line index, joined at
    # the end in printed order.
    parts: dict[int, dict[str, list[tuple[int, str]]]] = {
        a: {"name": [(a, merged[a]["name"])] if merged[a]["name"] else [],
            "payload": [(a, merged[a]["payload"])] if merged[a]["payload"] else []}
        for a in anchors}
    # Each column's own line sequence: the lines that print something in that
    # column, PLUS every Bil. line (a numbered row still occupies a line in a
    # column it happens to leave blank, so it must still be countable as a
    # neighbour there).
    name_seq = [o["idx"] for o in out if o["name"].strip() or o["idx"] in aset]
    pay_seq = [o["idx"] for o in out if o["payload"].strip() or o["idx"] in aset]

    def _neighbours(i: int, seq: list[int]):
        """(prev anchor, distance), (next anchor, distance) along one column."""
        if i not in seq:
            return (None, 0), (None, 0)
        pos = seq.index(i)
        prev = nxt = None
        pd = nd = 0
        for k in range(pos - 1, -1, -1):
            if seq[k] in aset:
                prev, pd = seq[k], pos - k
                break
        for k in range(pos + 1, len(seq)):
            if seq[k] in aset:
                nxt, nd = seq[k], k - pos
                break
        return (prev, pd), (nxt, nd)

    def _acc(a: int, field: str) -> str:
        return " ".join(t for _, t in sorted(parts[a][field])).strip()

    def _attach(i: int, seq: list[int], field: str, text: str):
        (prev, pd), (nxt, nd) = _neighbours(i, seq)
        if prev is None and nxt is None:
            return
        if prev is None:
            tgt = nxt
        elif nxt is None:
            tgt = prev
        elif (field == "payload" and pd <= nd
              and re.search(r"[A-Za-z)]\s*\.$", _acc(prev, "payload"))
              and re.match(r"^[A-Z]", text.strip())):
            # the previous cell is a closed sentence and this fragment starts a
            # new one, so it cannot be a continuation of the previous cell
            tgt = nxt
        elif pd != nd:
            tgt = prev if pd < nd else nxt
        else:
            # tie: the printed row whose own cell is EMPTY is the one whose
            # text was typeset on the wrapped line (`Kumpulan Wang Amanah
            # Memperingati Sir Henry Gurney` / `12.  24.05.2019` / `(KWAMSHG)`)
            pe = not _acc(prev, field)
            ne = not _acc(nxt, field)
            tgt = prev if (pe and not ne) else (nxt if ne else prev)
        # never let a fragment jump over an intervening heading
        if any(merged[k].get("heading") is not None
               and min(i, tgt) < k < max(i, tgt) for k in merged):
            return
        parts[tgt][field].append((i, text))
        if field == "name":
            merged[tgt]["frags"] = (merged[tgt].get("frags", [])
                                    + by_idx[i].get("frags", []))

    by_idx = {o["idx"]: o for o in out}
    for o in out:                       # headings first, so no fragment can be
        if o["idx"] in merged:          # attached across one that is only
            continue                    # discovered later in printed order
        heading = _heading_of_line(o)
        if heading is not None:
            merged[o["idx"]] = o | {"heading": heading}
    for o in out:
        if o["idx"] in merged:
            continue
        if o["name"].strip():
            _attach(o["idx"], name_seq, "name", o["name"])
        if o["payload"].strip():
            _attach(o["idx"], pay_seq, "payload", o["payload"])
    for a in anchors:
        merged[a]["name"] = _acc(a, "name")
        merged[a]["payload"] = _acc(a, "payload")
    return [merged[k] for k in sorted(merged)]


def _heading_of_line(o: dict) -> tuple | None:
    """A line with no Bil. and no payload that names a section or an opinion."""
    if o["bil"]:
        return None
    # A printed opinion heading can be typeset with wide inter-word gaps
    # (`PENDAPAT TANPA     TEGURAN    DENGAN   PERENGGAN ...`), so `-layout`
    # splits it into several segments and part of it lands past the name/
    # payload cut.  Judged on the payload alone it stops looking like a
    # heading, the two `1.` rows either side of it are then merged, and one
    # agency is lost (Pulau Pinang CMD.46.2023 pdf p96).  Judge the whole line.
    if o["payload"]:
        # only an OPINION caption may be recognised across the cut, and only
        # when the whole line is set in capitals - otherwise a wrapped agency
        # name printed beside its opinion basis (`Majlis Agama Islam Negeri
        # Pulau` + `. Saya ingin menarik perhatian ...`) reads as the
        # `MAJLIS AGAMA ISLAM` section heading and that agency is lost.
        s = re.sub(r"\s+", " ", o["raw"]).strip()
        if not s or re.search(r"[a-z]", s) or _DATE.search(s):
            return None
        for rx, op in _OPGROUPS:
            if rx.search(s.upper()):
                return ("opinion", op)
        return None
    s = o["name"].strip()
    if not s:
        return None
    for rx, g in _GROUPS:
        if rx.match(s):
            return ("group", g)
    for rx, op in _OPGROUPS:
        if rx.search(s.upper()):
            return ("opinion", op)
    return None


def extract_agency(state: str, v: dict, agency_dropped: list) -> list[dict]:
    """Per-agency register rows (see the module note above)."""
    if v.get("text_layer") == "image_only":
        return []
    path = os.path.join(RAW, v["file"])
    pages = P.load_pages(path, CACHE)
    tables = P.find_tables(pages, v["file"], keep_empty=True,
                           join_continuations=True)
    agency_name = SC.agency_name_re(state)
    out: list[dict] = []
    afy = v["agency_fiscal_year"]

    for t in tables:
        heading = P.heading_of(t)
        is_sub = bool(_AGENCY_TABLE.search(heading))
        is_op = (bool(_OPINION_TABLE.search(heading))
                 and not _OPINION_NOT.search(heading))
        if not (is_sub or is_op):
            continue
        # The two registers in one volume cover DIFFERENT years (the sijil
        # section lags the penyerahan register), so take each table's year from
        # its own printed heading, not from the volume.
        # `... AGENSI NEGERI TAHUN 2017 SEHINGGA 30 SEPTEMBER 2018` states the
        # register's year (2017) and its CUT-OFF date (2018).  The text layer
        # runs them together (`2017SEHINGGA`), so the cut-off clause is removed
        # before the year is read - otherwise every row is stamped with the
        # cut-off year.
        head_y = re.split(r"\bSEHINGGA\b|\bSETAKAT\b|\bSEHINGGA\b",
                          heading, flags=re.I)[0]
        ys = re.findall(r"\b(?:19|20)\d{2}\b", head_y)
        if not ys:
            ys = re.findall(r"\b(?:19|20)\d{2}\b", heading)
        table_year = ys[0] if ys else (str(afy) if afy else "")
        group = ""
        opinion, qualifier = "", ""
        # the opinion may be stated by the TABLE TITLE itself when the whole
        # table carries one opinion class
        for rx, op in _OPGROUPS:
            if rx.search(heading.upper()):
                opinion, qualifier = op
                break
        seen: set[str] = set()
        for row in _register_rows(t.title_lines + t.body, heading):
            h = row.get("heading")
            if h is not None:
                if h[0] == "group":
                    group = h[1]
                else:
                    opinion, qualifier = h[1]
                continue
            name = re.sub(r"\s+", " ", row["name"]).strip(" .:")
            name = re.sub(r"^\d{1,3}[.)]\s*", "", name)
            frags = [f for f in row.get("frags", []) if f.strip()]
            name_quality = "clean" if len(frags) <= 1 else "wrapped_joined"
            if not agency_name.match(name) and len(frags) == 2:
                # `-layout` emits the two halves of a wrapped name cell in the
                # WRONG order when a wide free-text column sits beside it
                # (`Perpustakaan Awam` / `Perbadanan`).  A single swap that
                # makes the name open with an institutional noun is accepted
                # and flagged; anything worse is refused, never guessed.
                alt = re.sub(r"\s+", " ", f"{frags[1]} {frags[0]}").strip(" .:")
                if agency_name.match(alt):
                    name, name_quality = alt, "reordered"
            if len(name) < 8 or not agency_name.match(name):
                if name:
                    agency_dropped.append(dict(
                        state=state, source_file=v["file"], pdf_page=t.pdf_page,
                        printed_page=t.printed_page, jadual=t.jadual,
                        register="penyerahan_status" if is_sub else "sijil_pendapat",
                        agency_name_bm=name[:200],
                        reason="agency name could not be reassembled from the "
                               "wrapped printed cell (column interleaving) - "
                               "row refused rather than emitted scrambled"))
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            pay = row["payload"]
            d = _DATE.search(pay) or _DATE.search(row["raw"])
            # The submission register's payload column IS the status column, so
            # the status is whatever it prints, minus the submission date.
            # Matching a whitelist of stock phrases instead lost every status
            # the list did not anticipate (`Sijil Audit Berteguran telah
            # dikeluarkan.`, `Dalam proses pensijilan.`) and truncated the
            # multi-line ones at their first clause, erasing the materially
            # different `oleh Firma Audit Swasta` / `oleh Jabatan Audit Negara`
            # (Melaka CMD.41.2023 pdf p91).
            if is_sub:
                status = re.sub(r"\s+", " ", pay).strip()
                # a payload that is nothing but a submission date is a date,
                # not a status
                if not re.search(r"[A-Za-z]{2}",
                                 re.sub(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}", " ",
                                        status)):
                    status = ""
            else:
                st = _STATUS.search(pay)
                status = re.sub(r"\s+", " ", st.group(0)).strip() if st else ""
            out.append(dict(
                state=state,
                fiscal_year_agency=table_year,
                fiscal_year_volume=v["fiscal_year"] or "",
                register="penyerahan_status" if is_sub else "sijil_pendapat",
                bil_printed=row["bil"],
                agency_name_bm=name,
                name_quality=name_quality,
                agency_type=group,
                submission_date=d.group(0) if (d and is_sub) else "",
                audit_status=status,
                opinion=opinion if is_op else "",
                opinion_qualifier=qualifier if is_op else "",
                opinion_basis_bm=(re.sub(r"\s+", " ", pay).strip()[:600]
                                  if is_op else ""),
                report=v["report"],
                command_paper=v["command_paper"],
                source_file=v["file"],
                pdf_page=t.pdf_page,
                printed_page=t.printed_page,
                jadual=t.jadual,
                table_title_bm=heading,
            ))
    return out


# ---------------------------------------------------------------------------

FIN_FIELDS = ["state", "fiscal_year", "statement", "line_code",
              "line_code_conformed", "line_label_bm", "amount_printed",
              "unit_printed", "amount_rm", "amount_rm_conformed",
              "sign_convention", "row_type", "is_leaf", "hierarchy",
              "measure", "column_role", "is_canonical",
              "table_role", "label_quality", "basis",
              "report", "command_paper", "source_file", "pdf_page",
              "printed_page", "jadual", "spec_id", "table_title_bm",
              "sumber_bm", "ordinal_fallback", "column_geometry",
              "data_quality"]
REV_FIELDS = ["state", "fiscal_year", "revenue_class",
              "revenue_group_printed_bm", "line_code",
              "line_code_conformed", "line_label_bm", "amount_printed",
              "unit_printed", "amount_rm", "amount_rm_conformed",
              "sign_convention", "row_type", "is_leaf",
              "measure", "column_role", "is_canonical",
              "table_role", "label_quality", "basis",
              "report", "command_paper", "source_file", "pdf_page",
              "printed_page", "jadual", "spec_id", "table_title_bm",
              "sumber_bm", "ordinal_fallback", "column_geometry",
              "data_quality"]
AG_FIELDS = ["state", "fiscal_year_agency", "fiscal_year_volume", "register",
             "bil_printed", "agency_name_bm", "name_quality", "agency_type", "submission_date",
             "audit_status", "opinion", "opinion_qualifier", "opinion_basis_bm",
             "report", "command_paper",
             "source_file", "pdf_page", "printed_page", "jadual",
             "table_title_bm", "data_quality"]


def write_csv(path: str, rows: list[dict], fields: list[str] | None = None) -> None:
    if not rows and not fields:
        return
    fields = fields or list(rows[0].keys())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {os.path.relpath(path, ROOT)}  ({len(rows)} rows)")


def run_state(state: str) -> dict:
    key = SC.slug(state)
    out = os.path.join(DATA, key)
    rev_rules = TC.compile_rules(
        SC.STATE_REVENUE_CLASSES.get(state, []) + SC.NATIONAL_REVENUE_CLASSES)

    print(f"=== {state}")
    manifest = build_manifest(state)
    write_csv(os.path.join(out, f"state_reports_{key}.csv"), manifest)

    fin: list[dict] = []
    rev: list[dict] = []
    bad: list[dict] = []
    drop: list[dict] = []
    ag: list[dict] = []
    agdrop: list[dict] = []
    for v in SC.VOLUMES[state]:
        if v["fiscal_year"] is None:
            print(f"  [skip] {v['file']} - {v['scope']}, no state financial statements")
            continue
        f, r, b, dr = extract_volume(state, v, rev_rules)
        fin += f
        rev += r
        bad += b
        drop += dr
        ag += extract_agency(state, v, agdrop)
        print(f"  {v['file']} FY{v['fiscal_year']}  finance={len(f)} "
              f"revenue={len(r)} unparsed={len(b)}")

    mark_trust_hierarchy(fin)
    nd = fix_debt_totals(fin)
    if nd:
        print(f"  re-coded {nd} public-debt JUMLAH row(s) that are not the year-end debt (subtotal or movement)")
    arb = arbitrate_prestasi(fin)
    if arb:
        print(f"  arbitrated {len(arb)} duplicate Penyata Prestasi Kewangan "
              f"ladder row(s) using the volume's own arithmetic")
    mark_canonical(fin)
    mark_canonical(rev)

    # `data_quality` - `suspect` marks a row covered by a diagnosed but unfixed
    # defect of OUR OWN (`state_config.KNOWN_EXTRACTION_DEFECTS`, reported in
    # `_known_extraction_defects_<slug>.csv`), so a consumer cannot use it
    # unaware.  It is never a statement about the printed source.
    n_susp = 0
    for target, rows_ in (("finance", fin), ("revenue", rev), ("agency", ag)):
        for r in rows_:
            bad_ = SC.is_known_defect_row(target, r)
            r["data_quality"] = "suspect" if bad_ else "ok"
            n_susp += bad_
    if n_susp:
        print(f"  flagged {n_susp} row(s) data_quality=suspect "
              f"(known extraction defects)")
    write_csv(os.path.join(out, f"_known_extraction_defects_{key}.csv"),
              SC.defect_entries(state), SC.DEFECT_FIELDS)

    write_csv(os.path.join(out, f"fact_state_finance_{key}.csv"), fin, FIN_FIELDS)
    write_csv(os.path.join(out, f"fact_state_revenue_{key}.csv"), rev, REV_FIELDS)
    write_csv(os.path.join(out, f"fact_state_agency_sijil_{key}.csv"), ag, AG_FIELDS)
    write_csv(os.path.join(out, f"_dropped_rows_{key}.csv"), drop,
              ["state", "fiscal_year", "spec_id", "jadual", "source_file",
               "pdf_page", "printed_page", "line_label_bm", "reason"])
    write_csv(os.path.join(out, f"_dropped_agency_rows_{key}.csv"), agdrop,
              ["state", "source_file", "pdf_page", "printed_page", "jadual",
               "register", "agency_name_bm", "reason"])
    write_csv(os.path.join(out, f"_unparsed_tables_{key}.csv"), bad,
              ["state", "fiscal_year", "spec_id", "jadual", "source_file",
               "pdf_page", "printed_page", "heading", "reason"])
    return dict(state=state, volumes=len(manifest), finance=len(fin),
                revenue=len(rev), agency=len(ag), unparsed=len(bad),
                dropped=len(drop))


# ---------------------------------------------------------------------------
# the national panel
# ---------------------------------------------------------------------------

PANEL_FIELDS = ["state", "fiscal_year", "line_code", "measure", "statement",
                "amount_rm_conformed", "amount_rm", "amount_printed",
                "unit_printed", "sign_convention", "row_type", "is_leaf",
                "hierarchy", "line_label_bm",
                "label_quality", "data_quality", "basis", "report",
                "command_paper",
                "source_file", "pdf_page", "printed_page", "jadual", "spec_id"]


def build_national() -> None:
    """One row per (state, fiscal_year, line_code, measure), canonical own-year
    rows only, conformed amounts.  This is the cross-state comparable panel."""
    rows: list[dict] = []
    for state in SC.STATES:
        key = SC.slug(state)
        for name in (f"fact_state_finance_{key}.csv", f"fact_state_revenue_{key}.csv"):
            p = os.path.join(DATA, key, name)
            if not os.path.exists(p):
                continue
            for r in csv.DictReader(open(p, encoding="utf-8")):
                if (r["column_role"] == "own_year" and r["is_canonical"] == "yes"
                        and r["line_code_conformed"] == "yes"):
                    rows.append(r)
    seen: dict[tuple, dict] = {}
    for r in rows:
        k = (r["state"], r["fiscal_year"], r["line_code"], r["measure"])
        seen.setdefault(k, r)
    out = [seen[k] for k in sorted(seen, key=lambda k: (k[0], k[1], k[2], k[3]))]
    write_csv(os.path.join(DATA, "_national", "fact_state_finance_all.csv"),
              out, PANEL_FIELDS)
    # national roll-up of the diagnosed-but-unfixed defects of our own
    write_csv(os.path.join(DATA, "_national", "_known_extraction_defects.csv"),
              SC.KNOWN_EXTRACTION_DEFECTS, SC.DEFECT_FIELDS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--national", action="store_true")
    args = ap.parse_args()

    states = SC.STATES if (args.all or not args.state) else [args.state]
    summary = [run_state(s) for s in states]
    if args.national or args.all:
        build_national()
    print()
    print(f"{'state':18s} {'vols':>5s} {'finance':>8s} {'revenue':>8s} "
          f"{'agency':>7s} {'unparsed':>9s} {'dropped':>8s}")
    for s in summary:
        print(f"{s['state']:18s} {s['volumes']:5d} {s['finance']:8d} "
              f"{s['revenue']:8d} {s['agency']:7d} {s['unparsed']:9d} "
              f"{s['dropped']:8d}")


if __name__ == "__main__":
    main()
