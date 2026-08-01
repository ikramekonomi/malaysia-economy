#!/usr/bin/env python3
"""Shared extractor/validator for the per-vote DETAIL sections of the Anggaran
Perbelanjaan Persekutuan books (Budget 2024/2025/2026) — program/aktiviti x
objek-am grain plus the Bil. Jawatan (headcount) axis.

Source table (one per T./B. vote): `Butiran | Program/Aktiviti | Kod (Objek Am) |
Anggaran <yr-1> | Anggaran <yr> | Bil. Jawatan <yr-1>/<yr>` — program rows
(butiran xx0000), aktiviti rows (xx0100, xx0200, ...), each followed by its
objek-am (10000..50000) breakdown rows, the vote closing with `JUMLAH ANGGARAN
PERBELANJAAN MENGURUS`. Only Mengurus (T/B) votes carry this grain; P votes use a
project-list layout (Butiran (Projek)) — out of scope here, see README.

The three books share the layout; per-era quirks handled below:
  * 2024/2025 print `...  ...` dot leaders in the Kod column on butiran rows;
    2026 does not.
  * Every vote opens with a per-objek-am RINGKASAN block. In 2026 it sits on its
    own pages (no `Bil. Jawatan` header); in 2024/2025 it can share the first
    detail page of small votes. Never extracted: pages are gated on BOTH
    "(Objek Am)" and "Bil. Jawatan" being present, and objek/jumlah rows are only
    accepted once the vote has an open butiran (the ringkasan precedes all
    butiran rows, and its total line wording also differs: it carries the vote
    name / splits across lines).
  * 2026 can print a post-table footnote that starts with a butiran code
    ("022400 - Peruntukan Skim ..."): a code line with no amounts is logged and
    skipped, never extracted as data.
  * Butiran names may embed bare numbers ("Kepengerusian ASEAN 2025",
    "Cawangan Kerja Bangunan Am 1"): the LAST TWO numeric tokens of a butiran
    row are the amounts; anything before them belongs to the name.
  * Names wrap across lines; a wrapped name fragment can share a line with an
    objek row ("Tambahan kepada International   40000   100   58,583,800") —
    text left of the objek code is name continuation.
  * B.32 (2024, 2025 books) and B.33 (2024 book) are dissolved ministries kept
    in the summary for historical actuals only (zero budget-year allocation):
    the books print no detail section for them (documented in V3 coverage).

Amounts are whole RM exactly as printed. En-dash `–` = 0.0 (none actually
printed in these tables — support kept for the convention), parentheses =
negative (none printed), `*` on a value -> has_footnote (none printed).
A `*` may instead sit on a LABEL — the only case in the three books is 2026
B.12 aktiviti 240100 (printed p.186), where the marker keys a note explaining
that the allocation moved to B.11 aktiviti 022400, and the aktiviti drops from
RM20,000,000 to nil. The asterisk is preserved verbatim in butiran_name_bm and
the note text is carried in label_footnote_bm; has_footnote stays value-scoped.
Headcounts print on the 10000 (Emolumen) objek rows and on the JUMLAH row —
except T.08, which has no 10000 row and prints its block headcount on 20000.

Output (per book): sources/anggaran/data/<year>/fact_anggaran_detail_<year>.csv
— LONG format, one row per printed line per measure (anggaran_<yr-1>,
anggaran_<yr>), row_kind in program|aktiviti|objek_am|jumlah_maksud
(jumlah_butiran reserved: no book prints per-butiran subtotal lines).
maksud_code is normalised to the PKKP scheme (B.01 zero-padded), consistent
with _crosswalk_pkkp_<year>.csv; maksud_code_printed keeps the detail-page
header's own form ("B.1").

Requires: pdftotext (poppler). Reads PDFs from sources/anggaran/raw/ (gitignored).
"""
import csv
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(HERE, "..", "raw")
DATA_DIR = os.path.join(HERE, "..", "data")

CONFIGS = {
    2024: dict(
        source_file="Anggaran_Perbelanjaan_Persekutuan_2024.pdf",
        retrieved_from="https://belanjawan.mof.gov.my/pdf/belanjawan2024/perbelanjaan/Anggaran_Perbelanjaan_Persekutuan_2024.pdf",
        retrieved_date="2026-07-31",
        # summary votes with no detail section, with the book's own reason
        no_detail={
            "B.32": "Kementerian Wilayah Persekutuan dibubar dan dipindahkan kepada "
                    "Jabatan Perdana Menteri pada tahun 2023 (book footnote *, printed "
                    "p.27) - zero anggaran 2023/2024, summary kept for actuals only",
            "B.33": "Kementerian Alam Sekitar dan Air dibubar dan dipindahkan kepada "
                    "Kementerian Sumber Asli, Alam Sekitar dan Perubahan Iklim pada "
                    "tahun 2023 (book footnote **, printed p.27) - zero anggaran "
                    "2023/2024, summary kept for actuals only",
        },
    ),
    2025: dict(
        source_file="Anggaran_Perbelanjaan_Persekutuan_2025.pdf",
        retrieved_from="https://belanjawan.mof.gov.my/pdf/belanjawan2025/perbelanjaan/Anggaran_Perbelanjaan_Persekutuan_2025.pdf",
        retrieved_date="2026-07-31",
        no_detail={
            "B.32": "Kementerian Wilayah Persekutuan dibubar dan dipindahkan kepada "
                    "Jabatan Perdana Menteri pada tahun 2023 (book footnote 3, printed "
                    "p.30) - zero anggaran 2024/2025, summary kept for actuals only",
        },
    ),
    2026: dict(
        source_file="Anggaran_Perbelanjaan_Persekutuan_2026.pdf",
        retrieved_from="https://belanjawan.mof.gov.my/pdf/belanjawan2026/perbelanjaan/Anggaran_Perbelanjaan_Persekutuan_2026.pdf",
        retrieved_date="2026-07-31",
        no_detail={},  # B/P.32 left the 2026 book entirely; all 53 T/B votes have detail
    ),
}

# numeric token: optional "(", digits+commas, optional ")", optional "*";
# a lone en-dash is the books' nil marker (value 0); word-adjacent digits
# ("ADF13", "F1") are name text, not values
TOKEN = re.compile(r"(?<![\w,.])(?:\(?\d[\d,]*\)?\*?|–)(?![\w])")
BUTIRAN_START = re.compile(r"^\s*(\d{6})(?!\d)")
OBJEK_TOKEN = re.compile(r"(?<![\d,])([1-9]0000)(?![\d,])")
VOTE_HEADER = re.compile(
    r"Maksud (Tanggungan|Bekalan|Pembangunan)\s+(\d+)\s*(?:[–-]\s*(.*?))?\s*$")
TRAILING_CODE = re.compile(r"\s+([TB]\.\s?\d+)\s*$")
DOTS = re.compile(r"(?:\.\s*){2,}|…")
JUMLAH = "JUMLAH ANGGARAN PERBELANJAAN MENGURUS"


def tokens(line):
    """Numeric tokens as (value:int, negative/footnote applied, start, end, raw)."""
    out = []
    for m in TOKEN.finditer(line):
        raw = m.group(0)
        if raw == "–":
            out.append({"value": 0, "footnote": False, "start": m.start(),
                        "end": m.end(), "raw": raw})
            continue
        neg = raw.startswith("(") and ")" in raw
        foot = raw.endswith("*")
        digits = re.sub(r"[^\d]", "", raw)
        if not digits:
            continue
        val = int(digits)
        if neg:
            val = -val
        out.append({"value": val, "footnote": foot, "start": m.start(),
                    "end": m.end(), "raw": raw})
    return out


def is_furniture(s, year):
    t = s.strip()
    if not t:
        return True
    if "ANGGARAN PERBELANJAAN PERSEKUTUAN" in s:
        return True
    if "Pegawai Pengawal" in s or "Bil. Jawatan" in s or "(Objek Am)" in s:
        return True
    if t.startswith("Butiran"):
        return True
    if "MENGIKUT OBJEK AM" in s or "RINGKASAN" in s:
        return True
    if "(Muka surat" in s:
        return True
    if re.fullmatch(r"(RM\s*)*RM", t):
        return True
    if re.fullmatch(r"[TB]\.\s?\d+", t):
        return True
    # a column-years-only line (e.g. "2024   2025   2024   2025")
    if re.fullmatch(r"(?:(?:%d|%d)\s*)+" % (year - 1, year), t):
        return True
    return False


def clean_name(fragment):
    return " ".join(DOTS.sub(" ", fragment).split()).strip()


def extract_book(year):
    """Parse the detail sections; returns (votes, problems).

    votes: list of dicts {code, code_printed, jenis, name, butiran: [block...],
    jumlah: row|None}; block: {code, kind, name, amounts, footnotes, hc,
    pdf_page, printed_page, objek: [{objek_code, amounts, footnotes, hc,
    pdf_page, printed_page}]}.
    """
    cfg = CONFIGS[year]
    raw = os.path.join(RAW_DIR, cfg["source_file"])
    txt = subprocess.run(["pdftotext", "-layout", raw, "-"],
                         capture_output=True, text=True, check=True).stdout
    pages = txt.split("\f")

    votes, by_code = [], {}
    cur_vote = None
    cur_but = None
    problems = []
    pending_note = []

    def problem(pnum, kind, line):
        problems.append({"pdf_page": pnum, "kind": kind, "line": line.strip()})

    for pnum, page in enumerate(pages, 1):
        m = re.search(r"ANGGARAN PERBELANJAAN PERSEKUTUAN %d \| (\d+)" % year, page) \
            or re.search(r"(\d+) \| ANGGARAN PERBELANJAAN PERSEKUTUAN %d" % year, page)
        printed_page = m.group(1) if m else ""
        detail_page = "(Objek Am)" in page and "Bil. Jawatan" in page

        for line in page.splitlines():
            s = line.rstrip()
            vm = VOTE_HEADER.search(s)
            if vm:
                jenis_word, num, name = vm.group(1), int(vm.group(2)), vm.group(3) or ""
                if jenis_word == "Pembangunan":
                    cur_vote, cur_but = None, None  # P votes: project layout, out of scope
                    continue
                letter = "T" if jenis_word == "Tanggungan" else "B"
                code = f"{letter}.{num:02d}"
                tm = TRAILING_CODE.search(name)
                code_printed = tm.group(1).replace(" ", "") if tm else f"{letter}.{num}"
                if tm:
                    name = name[:tm.start()]
                if code not in by_code:
                    by_code[code] = {"code": code, "code_printed": code_printed,
                                     "jenis": jenis_word, "name": clean_name(name),
                                     "butiran": [], "jumlah": None}
                    votes.append(by_code[code])
                if cur_vote is not by_code[code]:
                    cur_vote, cur_but = by_code[code], None
                continue
            if not detail_page or cur_vote is None:
                continue
            if is_furniture(s, year):
                continue

            if JUMLAH in s:
                toks = tokens(s)
                if cur_vote["butiran"] and toks:
                    if len(toks) not in (2, 4):
                        problem(pnum, "jumlah_token_count", s)
                        continue
                    if cur_vote["jumlah"] is not None:
                        problem(pnum, "duplicate_jumlah", s)
                        continue
                    cur_vote["jumlah"] = {
                        "amounts": [t["value"] for t in toks[:2]],
                        "footnotes": [t["footnote"] for t in toks[:2]],
                        "hc": [t["value"] for t in toks[2:]] or [None, None],
                        "pdf_page": pnum, "printed_page": printed_page}
                    cur_but = None
                # else: the vote's RINGKASAN-block total (precedes any butiran) - skip
                continue

            bm = BUTIRAN_START.match(s)
            if bm:
                code = bm.group(1)
                rest_start = bm.end()
                toks = [t for t in tokens(s) if t["start"] >= rest_start]
                if len(toks) < 2:
                    # e.g. 2026 post-table footnote "022400 - Peruntukan Skim ..."
                    problem(pnum, "butiran_line_without_amounts", s)
                    pending_note.append(s.strip())
                    continue
                if cur_vote["jumlah"] is not None:
                    problem(pnum, "butiran_after_jumlah", s)
                    continue
                amt_toks = toks[-2:]          # the two Anggaran columns
                name = clean_name(s[rest_start:amt_toks[0]["start"]])
                cur_but = {"code": code,
                           "kind": "program" if code.endswith("0000") else "aktiviti",
                           "name_parts": [name] if name else [],
                           "amounts": [t["value"] for t in amt_toks],
                           "footnotes": [t["footnote"] for t in amt_toks],
                           "hc": [None, None],
                           "pdf_page": pnum, "printed_page": printed_page,
                           "objek": []}
                cur_vote["butiran"].append(cur_but)
                continue

            # objek row: a [1-9]0000 token in the Kod column, values to its right
            # (only whitespace between the code and its first value), optional
            # wrapped-name text to its left
            obj = None
            for om in OBJEK_TOKEN.finditer(s):
                after = s[om.end():]
                fv = TOKEN.search(after)
                if fv and after[:fv.start()].strip() == "":
                    obj = om
            if obj is not None:
                if cur_but is None:
                    # ringkasan block rows ("10000  Emolumen  <amounts>") land here
                    # too, but those carry text right of the code, so obj is None;
                    # a bare objek row with no butiran open is a real problem
                    problem(pnum, "objek_row_outside_butiran", s)
                    continue
                objcode = obj.group(1)
                if objcode[0] not in "12345":
                    problem(pnum, "unexpected_objek_class", s)
                    continue
                toks = [t for t in tokens(s) if t["start"] >= obj.end()]
                if len(toks) not in (2, 4):
                    problem(pnum, "objek_token_count", s)
                    continue
                left = clean_name(s[:obj.start()])
                if left:
                    cur_but["name_parts"].append(left)
                row = {"objek_code": objcode,
                       "amounts": [t["value"] for t in toks[:2]],
                       "footnotes": [t["footnote"] for t in toks[:2]],
                       "hc": [t["value"] for t in toks[2:]] or [None, None],
                       "pdf_page": pnum, "printed_page": printed_page}
                cur_but["objek"].append(row)
                # The block's Bil. Jawatan normally prints on the 10000
                # (Emolumen) objek row, so it propagates to the block's
                # program/aktiviti header row. T.08 has no 10000 row at all and
                # prints the headcount against 20000 — take the first objek row
                # that carries one, so no vote loses the propagated figure.
                if row["hc"][0] is not None and cur_but["hc"][0] is None:
                    cur_but["hc"] = row["hc"]
                continue

            # plain text on a detail page: wrapped butiran-name continuation.
            # A continuation may carry a stray number as name text ("(MAHA)
            # 2024", or a year alone on its own wrap line: "... Para ASEAN /
            # 2027") - accepted only in the name column (indent < 45; the
            # amount columns start past col 50). Anything with a plausible
            # amount PAIR stays flagged instead.
            if cur_but is not None:
                indent = len(s) - len(s.lstrip())
                if 4 <= indent < 45 and len(tokens(s)) < 2:
                    cur_but["name_parts"].append(clean_name(s))
                elif tokens(s):
                    problem(pnum, "unclassified_numeric_line", s)
                else:
                    problem(pnum, "unclassified_text_line", s)
            elif re.search(r"\d", s):
                if cur_vote["butiran"] and cur_vote["jumlah"] is None:
                    problem(pnum, "unclassified_numeric_line", s)

    # attach any trailing explanatory note to the aktiviti whose label carries
    # the matching footnote marker (2026 B.12 240100 is the only occurrence)
    for note in pending_note:
        m = re.match(r"(\d{6})\s*[-–]\s*(.+)", note)
        for v in votes:
            for b in v["butiran"]:
                nm = " ".join(b["name_parts"]) if b["name_parts"] else ""
                if "*" in nm and b.get("label_footnote") is None:
                    b["label_footnote"] = note
    for v in votes:
        for b in v["butiran"]:
            b["name"] = " ".join(b.pop("name_parts"))
    return votes, problems


def write_csv(year, votes):
    cfg = CONFIGS[year]
    measures = [f"anggaran_{year - 1}", f"anggaran_{year}"]
    outdir = os.path.join(DATA_DIR, str(year))
    os.makedirs(outdir, exist_ok=True)
    dest = os.path.join(outdir, f"fact_anggaran_detail_{year}.csv")
    cols = ["maksud_code", "maksud_code_printed", "butiran_code", "butiran_name_bm",
            "row_kind", "objek_code", "measure", "amount_rm",
            f"bil_jawatan_{year - 1}", f"bil_jawatan_{year}", "has_footnote",
            "label_footnote_bm",
            "source_file", "pdf_page", "printed_page", "retrieved_from",
            "retrieved_date"]
    n = 0
    with open(dest, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)

        def emit(v, butiran_code, name, kind, objek_code, rec):
            nonlocal n
            hc = rec.get("hc", [None, None])
            for i, meas in enumerate(measures):
                w.writerow([v["code"], v["code_printed"], butiran_code, name, kind,
                            objek_code, meas, rec["amounts"][i],
                            "" if hc[0] is None else hc[0],
                            "" if hc[1] is None else hc[1],
                            rec["footnotes"][i],
                            rec.get("label_footnote", "") or "",
                            cfg["source_file"], rec["pdf_page"], rec["printed_page"],
                            cfg["retrieved_from"], cfg["retrieved_date"]])
                n += 1

        for v in votes:
            for b in v["butiran"]:
                emit(v, b["code"], b["name"], b["kind"], "", b)
                for o in b["objek"]:
                    emit(v, b["code"], b["name"], "objek_am", o["objek_code"], o)
            if v["jumlah"] is not None:
                emit(v, "", "", "jumlah_maksud", "", v["jumlah"])
    return dest, n


# ---------------------------------------------------------------- validation

def load_detail(year):
    path = os.path.join(DATA_DIR, str(year), f"fact_anggaran_detail_{year}.csv")
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_maksud(year):
    path = os.path.join(DATA_DIR, str(year), f"fact_anggaran_maksud_{year}.csv")
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def validate_book(year):
    """V1 internal sums, V2 anchor vs verified maksud summary, V3 coverage,
    V4 headcount. Writes _validation_detail_<year>.csv; returns rows."""
    cfg = CONFIGS[year]
    measures = [f"anggaran_{year - 1}", f"anggaran_{year}"]
    hc_cols = [f"bil_jawatan_{year - 1}", f"bil_jawatan_{year}"]
    detail = load_detail(year)
    maksud = load_maksud(year)
    out = []

    def check(name, scope, measure, expected, derived, status=None, note=""):
        if status is None:
            status = "PASS" if int(expected) == int(derived) else "FAIL"
        out.append({"check": name, "scope": scope, "measure": measure,
                    "expected_printed": expected, "derived_from_leaves": derived,
                    "status": status, "note": note})

    # reshape detail: votes -> butiran blocks
    votes = {}
    for r in detail:
        v = votes.setdefault(r["maksud_code"], {"butiran": {}, "jumlah": {}, "hc": {}})
        key = (r["butiran_code"], r["row_kind"], r["objek_code"])
        if r["row_kind"] == "jumlah_maksud":
            v["jumlah"][r["measure"]] = int(r["amount_rm"])
            if r[hc_cols[0]]:
                v["hc"]["jumlah"] = (int(r[hc_cols[0]]), int(r[hc_cols[1]]))
        else:
            b = v["butiran"].setdefault(key, {})
            b[r["measure"]] = int(r["amount_rm"])
            if r[hc_cols[0]]:
                b["hc"] = (int(r[hc_cols[0]]), int(r[hc_cols[1]]))

    for code, v in sorted(votes.items()):
        blocks = v["butiran"]
        parents = {bc: vals for (bc, kind, oc), vals in blocks.items()
                   if kind in ("program", "aktiviti")}
        for meas in measures:
            # V1a: each butiran's printed total == sum of its objek-am lines
            for bc, vals in sorted(parents.items()):
                objsum = sum(o[meas] for (obc, kind, oc), o in blocks.items()
                             if kind == "objek_am" and obc == bc)
                check("V1a_butiran_objek_sum", f"{code}/{bc}", meas,
                      vals[meas], objsum)
            # V1b: each program == sum of its aktiviti
            for bc, vals in sorted(parents.items()):
                if not bc.endswith("0000"):
                    continue
                akt = [o[meas] for obc, o in parents.items()
                       if obc[:2] == bc[:2] and not obc.endswith("0000")]
                if akt:
                    check("V1b_program_aktiviti_sum", f"{code}/{bc}", meas,
                          vals[meas], sum(akt))
            # V1c: vote total == sum of program rows
            progsum = sum(vals[meas] for bc, vals in parents.items()
                          if bc.endswith("0000"))
            if meas in v["jumlah"]:
                check("V1c_vote_butiran_sum", code, meas, v["jumlah"][meas], progsum)

    # V2 anchor: detail JUMLAH MENGURUS == adversarially verified maksud summary
    summary = {}
    for r in maksud:
        summary[(r["maksud_code"], r["component"], r["measure"])] = int(r["amount_rm"])
    anchor_meas = {measures[0]: f"anggaran_asal_{year - 1}",
                   measures[1]: f"anggaran_{year}"}
    tb_votes = sorted({r["maksud_code"] for r in maksud
                       if r["maksud_code"][0] in "TB"})
    for code in tb_votes:
        comp = "jumlah" if code.startswith("T.") else "mengurus"
        if code not in votes:
            continue
        for meas in measures:
            exp = summary.get((code, comp, anchor_meas[meas]))
            got = votes[code]["jumlah"].get(meas)
            if exp is None or got is None:
                check("V2_anchor_maksud_total", code, meas, exp, got, "FAIL",
                      "missing side")
            else:
                check("V2_anchor_maksud_total", code, meas, exp, got,
                      note=f"summary component={comp}, measure={anchor_meas[meas]}")

    # V3 coverage: every summary T/B vote has a detail section (or documented why not)
    for code in tb_votes:
        if code in votes:
            check("V3_coverage", code, "", 1, 1)
        elif code in cfg["no_detail"]:
            check("V3_coverage", code, "", 1, 0, "ABSENT_DOCUMENTED",
                  cfg["no_detail"][code])
        else:
            check("V3_coverage", code, "", 1, 0, "FAIL", "no detail section found")
    for code in sorted(votes):
        if code not in tb_votes:
            check("V3_coverage", code, "", 0, 1, "FAIL",
                  "detail section for a vote not in the verified summary")
    kinds = {}
    for r in detail:
        if r["measure"] == measures[0]:
            kinds[r["row_kind"]] = kinds.get(r["row_kind"], 0) + 1
    check("V3_counts", "book", "",
          len(tb_votes), len(votes), "INFO",
          f"votes with detail={len(votes)}; printed lines by kind: " +
          ", ".join(f"{k}={n}" for k, n in sorted(kinds.items())))

    # V4 headcount: vote JUMLAH bil. jawatan == sum of program-level headcounts
    for code, v in sorted(votes.items()):
        if "jumlah" not in v["hc"]:
            continue
        for i, col in enumerate(hc_cols):
            prog_hc = sum(b["hc"][i] for (bc, kind, oc), b in v["butiran"].items()
                          if kind == "objek_am" and b.get("hc")
                          and bc.endswith("0000"))
            check("V4_jawatan_vote_sum", code, col, v["hc"]["jumlah"][i], prog_hc)

    dest = os.path.join(DATA_DIR, str(year), f"_validation_detail_{year}.csv")
    with open(dest, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["check", "scope", "measure",
                                          "expected_printed",
                                          "derived_from_leaves", "status", "note"])
        w.writeheader()
        w.writerows(out)
    n_fail = sum(1 for r in out if r["status"] == "FAIL")
    n_pass = sum(1 for r in out if r["status"] == "PASS")
    print(f"wrote {dest}: {len(out)} checks, {n_pass} PASS, {n_fail} FAIL, "
          f"{sum(1 for r in out if r['status'] == 'ABSENT_DOCUMENTED')} documented absences")
    for r in out:
        if r["status"] == "FAIL":
            print(f"  FAIL {r['check']} {r['scope']} {r['measure']}: "
                  f"printed {r['expected_printed']} vs derived {r['derived_from_leaves']} {r['note']}")
    return out
