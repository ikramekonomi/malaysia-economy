#!/usr/bin/env python3
"""Extract the per-maksud summary of Anggaran Perbelanjaan Persekutuan 2024.

Source table: "RINGKASAN PERBELANJAAN SEBENAR DAN ANGGARAN MENGURUS DAN PEMBANGUNAN"
(printed pages ~21-33 of Anggaran_Perbelanjaan_Persekutuan_2024.pdf), four amount
columns per row: Perbelanjaan Sebenar 2022, Perbelanjaan Sebenar 2023,
Anggaran Asal 2024, Anggaran 2025. Amounts are whole RM as printed.

Output: sources/anggaran/data/2025/fact_anggaran_maksud_2024.csv — long format,
one row per (maksud x component x measure). Components as printed:
  T.x : emolumen, lain, jumlah(total)
  B.x : mengurus(total), emolumen, lain [, jumlah(total) when printed]
  P.x : pembangunan(total), cara_langsung, pinjaman
row_type: leaf = emolumen/lain/cara_langsung/pinjaman (and P.70's single line),
total = the rest. "Jumlah Kementerian ..." (B+P combined) rows are not extracted
(they mix jenis; the validation script re-derives and checks the printed grand totals).

maksud_code is normalised to the PKKP scheme (T.01/B.01/P.06 — zero-padded);
maksud_code_printed keeps the book's own "T. 1" form. The mapping is exercised and
name-checked by _crosswalk_pkkp_2024.csv (see build_crosswalk_2024.py).

Requires: pdftotext (poppler). Reads the PDF from sources/anggaran/raw/ (gitignored).
"""
import csv
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "..", "raw", "Anggaran_Perbelanjaan_Persekutuan_2024.pdf")
OUTDIR = os.path.join(HERE, "..", "..", "data", "2024")
SOURCE_FILE = "Anggaran_Perbelanjaan_Persekutuan_2024.pdf"
RETRIEVED_FROM = "https://belanjawan.mof.gov.my/pdf/belanjawan2024/perbelanjaan/Anggaran_Perbelanjaan_Persekutuan_2024.pdf"
RETRIEVED_DATE = "2026-07-31"
MEASURES = ["sebenar_2021", "sebenar_2022", "anggaran_asal_2023", "anggaran_2024"]
HEADER = "RINGKASAN PERBELANJAAN SEBENAR DAN ANGGARAN PERBELANJAAN MENGURUS"

AMT = re.compile(r"(?<![\d,.])\d{1,3}(?:,\d{3})*(?![\d,.])")
CODE = re.compile(r"^\s*(T|B|P)\.\s*(\d+)\s+(.*)$")

COMPONENT_LABELS = [
    ("Perbelanjaan-perbelanjaan Lain", "lain", "leaf"),
    ("Cara Langsung", "cara_langsung", "leaf"),
    ("Pinjaman", "pinjaman", "leaf"),
    ("Emolumen", "emolumen", "leaf"),
    ("Mengurus", "mengurus", "total"),
    ("Pembangunan", "pembangunan", "total"),
    ("Jumlah", "jumlah", "total"),
]


def amounts(line):
    return [int(m.replace(",", "")) for m in AMT.findall(line)]


def main():
    txt = subprocess.run(["pdftotext", "-layout", RAW, "-"], capture_output=True,
                         text=True, check=True).stdout
    pages = txt.split("\f")
    rows = []
    cur = None            # (jenis_letter, num, name_parts)
    pending_name = None   # name continuation lines before first component
    for pnum, page in enumerate(pages, 1):
        if HEADER not in page:
            continue
        m = re.search(r"ANGGARAN PERBELANJAAN PERSEKUTUAN 2024 \| (\d+)", page)
        printed = m.group(1) if m else ""
        for line in page.splitlines():
            s = line.strip()
            if not s or s.startswith(("RINGKASAN", "Maksud Perbelanjaan", "RM")) \
               or re.match(r"^(Perbelanjaan\s+Perbelanjaan|Sebenar|Asal|\d{4}\s+\d{4})", s) \
               or s.startswith("ANGGARAN PERBELANJAAN PERSEKUTUAN"):
                continue
            if s.startswith("Ringkasan"):
                # summary block ("Ringkasan Maksud Tanggungan" / final "Ringkasan"):
                # its Emolumen/Lain/Jumlah grand totals belong to no maksud —
                # they are checked as printed constants by validate_2025.py
                cur = None
                continue
            cm = CODE.match(s)
            if cm:
                jenis_letter, num, rest = cm.group(1), int(cm.group(2)), cm.group(3)
                # inline single-line maksud with amounts (P. 70 Simpanan Luar Jangka)
                vals = amounts(rest)
                name = AMT.sub("", rest).strip().rstrip("-").strip()
                cur = (jenis_letter, num, [name] if name else [])
                if len(vals) == 4:
                    if name == "Pembangunan":
                        # "P. x  Pembangunan  <amounts>": total inline on the code line;
                        # keep cur so Cara Langsung / Pinjaman sub-rows attach
                        rows.append(make_row(cur, "pembangunan", "total", vals, pnum, printed))
                    else:
                        # true single-line maksud (P. 70 Simpanan Luar Jangka)
                        rows.append(make_row(cur, "pembangunan" if jenis_letter == "P" else "jumlah",
                                             "leaf", vals, pnum, printed))
                        cur = None
                continue
            if cur is None:
                continue
            vals = amounts(s)
            if len(vals) == 4 or (len(vals) > 0 and s.split()[0] in
                                  ("Jumlah",) and ".." in s):
                label = AMT.sub("", s).replace("..", "").strip().rstrip("-").strip()
                for prefix, comp, rtype in COMPONENT_LABELS:
                    if label.startswith(prefix):
                        if comp == "jumlah":
                            # a Jumlah row closes the current maksud; capture it only
                            # for T/B maksud own totals ("Jumlah ..") — a "Jumlah
                            # <ministry>" after a P.x block is the combined B+P
                            # ministry total, not a P-maksud figure (checked
                            # arithmetically by validate_2025.py instead). Closing
                            # cur also drops the unlabelled ministry roll-up blocks
                            # that follow multi-vote ministries (e.g. Kementerian
                            # Kewangan after B.12).
                            if cur[0] != "P" and len(vals) == 4:
                                rows.append(make_row(cur, comp, rtype, vals, pnum, printed))
                            cur = None
                            break
                        if len(vals) == 4:
                            rows.append(make_row(cur, comp, rtype, vals, pnum, printed))
                        break
                # "Jumlah Kementerian X" / "Jumlah <name>" combined rows: skipped by
                # the break-less fallthrough unless label starts with a known prefix
                continue
            if not vals and cur[2] is not None and not s.startswith(("JABATAN", "KEMENTERIAN", "Ringkasan", "Jumlah")):
                # continuation of the maksud name (before components start)
                if len([r for r in rows if r["maksud_code_printed"] == printed_code(cur)]) == 0:
                    cur[2].append(s.rstrip("-").strip())

    write(rows)


def printed_code(cur):
    return f"{cur[0]}. {cur[1]}"


def make_row(cur, comp, rtype, vals, pnum, printed):
    jl, num, name_parts = cur
    jenis = {"T": "Tanggungan", "B": "Bekalan", "P": "Pembangunan"}[jl]
    return {
        "maksud_code": f"{jl}.{num:02d}",
        "maksud_code_printed": printed_code(cur),
        "jenis": jenis,
        "maksud_name_bm": " ".join(name_parts).strip(),
        "component": comp,
        "row_type": rtype,
        "vals": vals,
        "pdf_page": pnum,
        "printed_page": printed,
    }


def write(rows):
    # P.x rows are labelled just "Pembangunan" in the summary table; carry the vote
    # name from the paired B.x maksud (same vote number, same source). P.70 keeps
    # its own printed name (Simpanan Luar Jangka).
    bname = {r["maksud_code"][2:]: r["maksud_name_bm"] for r in rows
             if r["maksud_code"].startswith("B.")}
    for r in rows:
        if r["maksud_code"].startswith("P.") and r["maksud_name_bm"] == "Pembangunan":
            num = r["maksud_code"][2:]
            if num in bname:
                r["maksud_name_bm"] = bname[num]
    os.makedirs(OUTDIR, exist_ok=True)
    dest = os.path.join(OUTDIR, "fact_anggaran_maksud_2024.csv")
    with open(dest, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["maksud_code", "maksud_code_printed", "jenis", "maksud_name_bm",
                    "component", "row_type", "measure", "amount_rm",
                    "source_file", "pdf_page", "printed_page", "retrieved_from", "retrieved_date"])
        n = 0
        for r in rows:
            for measure, amt in zip(MEASURES, r["vals"]):
                w.writerow([r["maksud_code"], r["maksud_code_printed"], r["jenis"],
                            r["maksud_name_bm"], r["component"], r["row_type"], measure, amt,
                            SOURCE_FILE, r["pdf_page"], r["printed_page"],
                            RETRIEVED_FROM, RETRIEVED_DATE])
                n += 1
    codes = {r["maksud_code"] for r in rows}
    print(f"wrote {dest}: {n} rows, {len(codes)} maksud "
          f"(T:{len([c for c in codes if c[0]=='T'])} B:{len([c for c in codes if c[0]=='B'])} "
          f"P:{len([c for c in codes if c[0]=='P'])})")


if __name__ == "__main__":
    main()
