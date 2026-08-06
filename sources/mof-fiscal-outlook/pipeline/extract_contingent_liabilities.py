#!/usr/bin/env python3
"""Extract the Seksyen 5 (Risiko Fiskal dan Liabiliti) contingent-liability /
guarantee tables from the MOF Tinjauan Fiskal PDFs into
data/fact_contingent_liabilities.csv, and reconcile every table against its own
printed totals into data/_validation_contingent_liabilities.csv.

Tables extracted (BM section of each edition):

  FO2025 (tinjauan_fiskal_2025.pdf, Budget 2025 edition, Oct 2024)
    Jadual 5.1  Pendedahan Hutang dan Liabiliti Kerajaan Persekutuan (RM bilion)   printed p.81
    Jadual 5.2  Jaminan Kewangan (RM bilion)                                       printed p.82
    Jadual 5.3  Penerima Utama Jaminan di bawah Akta 96 (RM juta)                  printed p.83
    Jadual 5.4  Komitmen Jaminan (RM juta)                                         printed p.91
  FO2026 (tinjauan_fiskal_2026.pdf, Budget 2026 edition, Oct 2025)
    Jadual 5.1  (RM juta)  printed p.76      Jadual 5.2  (RM juta)  printed p.76
    Jadual 5.3  (RM juta)  printed p.77      Jadual 5.4  (RM juta)  printed p.85

Column semantics (per the tables' own footnotes): the first value column is the
prior end-of-year position; the second is the *mid-year* position ("Akhir Jun")
of the edition's reference year. `asof` records this — do not compare a Jun
position with a Dec position without noting it.

Verbatim rules (CLAUDE.md): amounts as printed (value_printed keeps the printed
string; en-dash '–' = nil = 0.0), never corrected. Row labels are printed labels
with superscript footnote markers moved to footnote_ref (the marker is not part
of the entity name). The FO2026 text layer garbles some header/label glyphs
("ja ual", "Jumlah 10 penerima utama" → "0"); labels are therefore assigned
positionally from the printed row order (read off the page), while every VALUE
is parsed from the PDF text layer and reconciled against the table's own totals
below. Percent-share columns (bahagian % / % KDNK) are carried as share_pct /
share_gdp_pct where printed.

Run:  python3 sources/mof-fiscal-outlook/pipeline/extract_contingent_liabilities.py
Needs poppler-utils (pdftotext).
"""
import csv
import re
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
RAW = SRC / "raw"
DATA = SRC / "data"

RETRIEVED = {
    "tinjauan_fiskal_2025.pdf": (
        "https://belanjawan.mof.gov.my/pdf/belanjawan2025/hasil/tinjauan_fiskal_2025.pdf",
        "2026-07-31",
    ),
    "tinjauan_fiskal_2026.pdf": (
        "https://belanjawan.mof.gov.my/pdf/belanjawan2026/hasil/tinjauan_fiskal_2026.pdf",
        "2026-07-31",
    ),
}

# ---------------------------------------------------------------------------
# Table specifications.
# rows: (label_bm, row_type, footnote_ref) in printed order. footnote_ref is the
# superscript marker printed against the label (kept out of the label itself).
# arity: numeric fields per row. cols: (col_year, asof, which value columns map
# to amount / share_pct / share_gdp_pct).
# ---------------------------------------------------------------------------

J51_ROWS = [
    ("Hutang Kerajaan Persekutuan", "detail", None),
    ("Komitmen jaminan", "detail", None),
    ("Liabiliti lain", "detail", None),
    ("Jumlah", "total", None),
]
J52_ROWS = [
    ("Jaminan di bawah Akta 96", "detail", None),
    ("Jaminan di bawah Akta 61", "subtotal", None),  # = Ikatan dan Sokongan + Skim Jaminan
    ("Ikatan dan Sokongan", "detail", None),
    ("Skim Jaminan", "detail", None),
    ("Jumlah", "total", None),
]
J53_ROWS_2025 = [
    ("DanaInfra Nasional Berhad", "detail", None),
    ("Malaysia Rail Link Sdn. Bhd.", "detail", "1"),
    ("Lembaga Pembiayaan Perumahan Sektor Awam", "detail", None),
    ("Perbadanan Tabung Pendidikan Tinggi Nasional", "detail", None),
    ("Prasarana Malaysia Berhad", "detail", None),
    ("Projek Lebuhraya Usahasama Berhad", "detail", None),
    ("Lembaga Kemajuan Tanah Persekutuan (FELDA)", "detail", None),
    ("Pengurusan Air SPV Berhad", "detail", None),
    ("Suria Strategic Energy Resources Sdn. Bhd.", "detail", "1"),
    ("Jambatan Kedua Sdn. Bhd.", "detail", "1"),
    ("Jumlah penerima utama", "subtotal", None),
    ("Penerima lain", "detail", None),
    ("Jumlah jaminan kerajaan", "total", None),
]
J53_ROWS_2026 = [
    ("DanaInfra Nasional Berhad", "detail", None),
    ("Lembaga Pembiayaan Perumahan Sektor Awam", "detail", None),
    ("Malaysia Rail Link Sdn. Bhd.", "detail", "1"),
    ("Prasarana Malaysia Berhad", "detail", None),
    ("Perbadanan Tabung Pendidikan Tinggi Nasional", "detail", None),
    ("Projek Lebuhraya Usahasama Berhad", "detail", None),
    ("Lembaga Kemajuan Tanah Persekutuan (FELDA)", "detail", None),
    ("Pengurusan Air SPV Berhad", "detail", None),
    ("Suria Strategic Energy Resources Sdn. Bhd.", "detail", "1"),
    ("1Malaysia Development Berhad", "detail", None),
    ("Jumlah 10 penerima utama", "subtotal", None),
    ("Penerima lain", "detail", None),
    # printed label verified from the rendered page image (the FO2026 text
    # layer garbles this row): "Jumlah jaminan", not bare "Jumlah"
    ("Jumlah jaminan", "total", None),
]
J54_ROWS_2025 = [
    ("DanaInfra Nasional Berhad", "detail", None),
    ("Malaysia Rail Link Sdn. Bhd.", "detail", "1"),
    ("Prasarana Malaysia Berhad", "detail", None),
    ("Urusharta Jamaah Sdn. Bhd.", "detail", "2"),
    ("Lembaga Kemajuan Tanah Persekutuan (FELDA)", "detail", None),
    ("Suria Strategic Energy Resources Sdn. Bhd.", "detail", "1"),
    ("Jambatan Kedua Sdn. Bhd.", "detail", "1"),
    ("1Malaysia Development Berhad", "detail", None),
    ("Turus Pesawat Sdn. Bhd.", "detail", None),
    ("GovCo Holdings Berhad", "detail", None),
    ("MKD Kencana Sdn. Bhd.", "detail", None),
    ("MKD Signature Sdn. Bhd.", "detail", "2"),
    ("TRX City Sdn. Bhd.", "detail", None),
    ("Syarikat Perumahan Negara Berhad", "detail", None),
    ("Jumlah", "total", None),
]
J54_ROWS_2026 = [
    ("DanaInfra Nasional Berhad", "detail", None),
    ("Malaysia Rail Link Sdn. Bhd.", "detail", "1"),
    ("Prasarana Malaysia Berhad", "detail", None),
    ("Urusharta Jamaah Sdn. Bhd.", "detail", "2"),
    ("Lembaga Kemajuan Tanah Persekutuan (FELDA)", "detail", None),
    ("Suria Strategic Energy Resources Sdn. Bhd.", "detail", "1"),
    ("1Malaysia Development Berhad", "detail", None),
    ("Jambatan Kedua Sdn. Bhd.", "detail", "1"),
    ("Turus Pesawat Sdn. Bhd.", "detail", None),
    ("GovCo Holdings Berhad", "detail", None),
    ("MKD Kencana Sdn. Bhd.", "detail", None),
    ("MKD Signature Sdn. Bhd.", "detail", "2"),
    ("TRX City Sdn. Bhd.", "detail", None),
    ("Syarikat Perumahan Negara Berhad", "detail", None),
    ("Jumlah", "total", None),
]

TABLES = [
    # (source_file, jadual_no, title_bm, pdf_page, printed_page, unit,
    #  rows, arity, col spec [(col_year, asof), ...], value layout)
    # value layout: 4 fields = amt_y1 amt_y2 x_y1 x_y2 where x is share_gdp (J5.1/5.2)
    #               or share (J5.4); 6 fields = amt amt share share gdp gdp (J5.3).
    dict(f="tinjauan_fiskal_2025.pdf", j="5.1",
         t="Pendedahan Hutang dan Liabiliti Kerajaan Persekutuan",
         pdf=95, pp=81, unit="RM Bilion", rows=J51_ROWS, arity=4, clip=(68, None),
         cols=[("2023", "2023-12-31"), ("2024", "2024-06-30")], layout="amt2gdp2"),
    dict(f="tinjauan_fiskal_2025.pdf", j="5.2", t="Jaminan Kewangan",
         pdf=96, pp=82, unit="RM Bilion", rows=J52_ROWS, arity=4, clip=(0, 84),
         cols=[("2023", "2023-12-31"), ("2024", "2024-06-30")], layout="amt2gdp2"),
    dict(f="tinjauan_fiskal_2025.pdf", j="5.3",
         t="Penerima Utama Jaminan di bawah Akta 96",
         pdf=97, pp=83, unit="RM Juta", rows=J53_ROWS_2025, arity=6,
         cols=[("2023", "2023-12-31"), ("2024", "2024-06-30")], layout="amt2share2gdp2"),
    dict(f="tinjauan_fiskal_2025.pdf", j="5.4", t="Komitmen Jaminan",
         pdf=105, pp=91, unit="RM Juta", rows=J54_ROWS_2025, arity=4,
         cols=[("2023", "2023-12-31"), ("2024", "2024-06-30")], layout="amt2share2"),
    dict(f="tinjauan_fiskal_2026.pdf", j="5.1",
         t="Pendedahan Hutang dan Liabiliti Kerajaan Persekutuan",
         pdf=90, pp=76, unit="RM Juta", rows=J51_ROWS, arity=4, clip=(0, 84),
         cols=[("2024", "2024-12-31"), ("2025", "2025-06-30")], layout="amt2gdp2"),
    dict(f="tinjauan_fiskal_2026.pdf", j="5.2", t="Jaminan Kewangan",
         pdf=90, pp=76, unit="RM Juta", rows=J52_ROWS, arity=4, clip=(84, None),
         cols=[("2024", "2024-12-31"), ("2025", "2025-06-30")], layout="amt2gdp2"),
    dict(f="tinjauan_fiskal_2026.pdf", j="5.3",
         t="Penerima Utama Jaminan di bawah Akta 96",
         pdf=91, pp=77, unit="RM Juta", rows=J53_ROWS_2026, arity=6,
         cols=[("2024", "2024-12-31"), ("2025", "2025-06-30")], layout="amt2share2gdp2"),
    dict(f="tinjauan_fiskal_2026.pdf", j="5.4", t="Komitmen Jaminan",
         pdf=99, pp=85, unit="RM Juta", rows=J54_ROWS_2026, arity=4,
         cols=[("2024", "2024-12-31"), ("2025", "2025-06-30")], layout="amt2share2"),
]

NUM_RE = re.compile(r"^\(?(?:[\d,]+(?:\.\d+)?|–|-)\)?$")


def page_text(pdf: Path, page: int) -> str:
    out = subprocess.run(
        ["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(pdf), "-"],
        capture_output=True, text=True, check=True)
    return out.stdout


def numeric_field(tok: str) -> bool:
    return bool(NUM_RE.match(tok)) and "%" not in tok


def parse_value(tok: str) -> float:
    if tok in ("–", "-"):
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    v = float(tok.strip("()").replace(",", ""))
    return -v if neg else v


def numeric_runs(text: str, start_anchor: re.Pattern, min_arity: int,
                 clip=None):
    """Yield lists of numeric tokens (printed strings) from lines after the
    anchor up to the 'Sumber:' line — the table body region. `clip` is an
    optional (lo, hi) character range isolating one column of a two-column
    page (both editions print the narrow J5.1/J5.2 tables beside narrative
    text, and FO2026 prints them side by side)."""
    lines = text.splitlines()
    if clip:
        lo, hi = clip
        lines = [l[lo:hi] for l in lines]
    idx = next(i for i, l in enumerate(lines) if start_anchor.search(l))
    runs = []
    for line in lines[idx:]:
        if "Sumber:" in line:
            break
        fields = line.split()
        toks = [t for t in fields if numeric_field(t)]
        if len(toks) < min_arity:
            continue
        # header lines print only 4-digit years / stray superscripts: a real data
        # row always carries at least one token with a comma or decimal point
        if not any(("," in t or "." in t) for t in toks):
            continue
        runs.append(toks)
    return runs


def extract_table(spec):
    pdf = RAW / spec["f"]
    txt = page_text(pdf, spec["pdf"])
    anchor = re.compile(r"(JaDUaL|JADUAL|Jadual|ja ual)\s*" +
                        (re.escape(spec["j"].replace(".", "")) + "|" +
                         re.escape(spec["j"])))
    # anchor on the jadual heading followed by its title's first word
    title_word = spec["t"].split()[0]
    pat = re.compile(rf"(JaDUaL|JADUAL|ja ual)\s*\S*\s*.*{re.escape(title_word)}")
    runs = numeric_runs(txt, pat, spec["arity"], spec.get("clip"))
    fixed = []
    for r in runs:
        # narrow tables share the page with a narrative column: a trailing
        # plain-integer token is narrative text ("... Akta 61"), not data
        while len(r) > spec["arity"] and "," not in r[-1] and "." not in r[-1]:
            r = r[:-1]
        if len(r) == spec["arity"] + 1 and r[0] in ("0", "1", "2", "3", "4"):
            # leading token is a superscript footnote marker (or an OCR-garbled
            # label fragment, e.g. FO2026 J5.3 'Jumlah 10 penerima utama' -> '0')
            r = r[1:]
        if len(r) != spec["arity"]:
            raise SystemExit(f"{spec['f']} J{spec['j']}: bad run {r}")
        fixed.append(r)
    if len(fixed) != len(spec["rows"]):
        raise SystemExit(
            f"{spec['f']} J{spec['j']}: expected {len(spec['rows'])} rows, "
            f"parsed {len(fixed)}:\n{fixed}")
    url, rdate = RETRIEVED[spec["f"]]
    edition = "2025" if "2025" in spec["f"] else "2026"
    mult = 1e9 if spec["unit"] == "RM Bilion" else 1e6
    out = []
    for (label, row_type, fn), toks in zip(spec["rows"], fixed):
        n = spec["arity"] // 2  # two report columns
        for ci, (col_year, asof) in enumerate(spec["cols"]):
            amt_tok = toks[ci]
            if spec["layout"] == "amt2gdp2":
                share, gdp = "", toks[2 + ci]
            elif spec["layout"] == "amt2share2":
                share, gdp = toks[2 + ci], ""
            else:  # amt2share2gdp2
                share, gdp = toks[2 + ci], toks[4 + ci]
            out.append({
                "edition_year": edition,
                "jadual_no": spec["j"],
                "jadual_title_bm": spec["t"],
                "line_bm": label,
                "row_type": row_type,
                "footnote_ref": fn or "",
                "col_year": col_year,
                "asof": asof,
                "value_printed": amt_tok,
                "unit": spec["unit"],
                "amount_rm": parse_value(amt_tok) * mult,
                "share_pct": share if share in ("", "–", "-") else parse_value(share),
                "share_gdp_pct": gdp if gdp in ("", "–", "-") else parse_value(gdp),
                "source_file": spec["f"],
                "pdf_page": spec["pdf"],
                "printed_page": spec["pp"],
                "retrieved_from": url,
                "retrieved_date": rdate,
            })
    return out


def validate(rows):
    """Reconcile each table against its own printed totals."""
    checks = []

    def amt(ed, j, line, cy):
        m = [r for r in rows if r["edition_year"] == ed and r["jadual_no"] == j
             and r["line_bm"] == line and r["col_year"] == cy]
        assert len(m) == 1, (ed, j, line, cy, len(m))
        return m[0]["amount_rm"]

    def add(name, printed, derived, tol):
        checks.append({
            "check": name,
            "status": "PASS" if abs(printed - derived) <= tol else "FAIL",
            "printed_value_rm": printed,
            "derived_value_rm": derived,
            "difference_rm": derived - printed,
        })

    for ed in ("2025", "2026"):
        cols = [("2023", "2024") if ed == "2025" else ("2024", "2025")][0]
        # totals are printed at the tables' own rounding (0.1 bilion in FO2025
        # J5.1/5.2, 1 juta elsewhere) -> tolerance = half a printed unit summed
        tol51 = 0.05e9 * 4 if ed == "2025" else 0.5e6 * 4
        for cy in cols:
            j = "5.1"
            add(f"FO{ed} J5.1 [{cy}]: components sum to Jumlah",
                amt(ed, j, "Jumlah", cy),
                sum(amt(ed, j, l, cy) for l in
                    ("Hutang Kerajaan Persekutuan", "Komitmen jaminan",
                     "Liabiliti lain")), tol51)
            j = "5.2"
            add(f"FO{ed} J5.2 [{cy}]: Ikatan+Skim = Jaminan di bawah Akta 61",
                amt(ed, j, "Jaminan di bawah Akta 61", cy),
                amt(ed, j, "Ikatan dan Sokongan", cy) +
                amt(ed, j, "Skim Jaminan", cy), tol51)
            add(f"FO{ed} J5.2 [{cy}]: Akta 96 + Akta 61 = Jumlah",
                amt(ed, j, "Jumlah", cy),
                amt(ed, j, "Jaminan di bawah Akta 96", cy) +
                amt(ed, j, "Jaminan di bawah Akta 61", cy), tol51)
            j = "5.3"
            det = [r for r in rows if r["edition_year"] == ed
                   and r["jadual_no"] == j and r["col_year"] == cy
                   and r["row_type"] == "detail" and r["line_bm"] != "Penerima lain"]
            sub = [r for r in rows if r["edition_year"] == ed
                   and r["jadual_no"] == j and r["col_year"] == cy
                   and r["row_type"] == "subtotal"]
            tot = [r for r in rows if r["edition_year"] == ed
                   and r["jadual_no"] == j and r["col_year"] == cy
                   and r["row_type"] == "total"]
            add(f"FO{ed} J5.3 [{cy}]: 10 penerima utama sum to subtotal",
                sub[0]["amount_rm"], sum(r["amount_rm"] for r in det), 0.5e6 * 10)
            add(f"FO{ed} J5.3 [{cy}]: subtotal + Penerima lain = Jumlah",
                tot[0]["amount_rm"],
                sub[0]["amount_rm"] +
                amt(ed, j, "Penerima lain", cy), 0.5e6 * 2)
            j = "5.4"
            det = [r for r in rows if r["edition_year"] == ed
                   and r["jadual_no"] == j and r["col_year"] == cy
                   and r["row_type"] == "detail"]
            add(f"FO{ed} J5.4 [{cy}]: 14 entities sum to Jumlah",
                amt(ed, j, "Jumlah", cy),
                sum(r["amount_rm"] for r in det), 0.5e6 * 14)
        # cross-table: J5.4 Jumlah = J5.1 Komitmen jaminan (same concept,
        # J5.1 printed in bilion in FO2025 -> tolerance half a bilion-unit)
        for cy in cols:
            add(f"FO{ed} cross [{cy}]: J5.4 Jumlah = J5.1 Komitmen jaminan",
                amt(ed, "5.1", "Komitmen jaminan", cy),
                amt(ed, "5.4", "Jumlah", cy),
                0.05e9 if ed == "2025" else 0.5e6)
            add(f"FO{ed} cross [{cy}]: J5.3 Jumlah = J5.2 Jaminan di bawah Akta 96",
                amt(ed, "5.2", "Jaminan di bawah Akta 96", cy),
                amt(ed, "5.3", "Jumlah jaminan kerajaan" if ed == "2025" else "Jumlah jaminan", cy),
                0.05e9 if ed == "2025" else 0.5e6)
    return checks


def main():
    all_rows = []
    for spec in TABLES:
        all_rows.extend(extract_table(spec))
    checks = validate(all_rows)
    DATA.mkdir(exist_ok=True)
    with open(DATA / "fact_contingent_liabilities.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(all_rows[0].keys()))
        w.writeheader()
        w.writerows(all_rows)
    with open(DATA / "_validation_contingent_liabilities.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(checks[0].keys()))
        w.writeheader()
        w.writerows(checks)
    npass = sum(c["status"] == "PASS" for c in checks)
    print(f"rows: {len(all_rows)}  checks: {npass}/{len(checks)} PASS")
    for c in checks:
        if c["status"] != "PASS":
            print("FAIL:", c)
    if npass != len(checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
