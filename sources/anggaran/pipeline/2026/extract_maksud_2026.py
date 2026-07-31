#!/usr/bin/env python3
"""Extract the per-maksud summary of Anggaran Perbelanjaan Persekutuan 2026.

Source table: "RINGKASAN PERBELANJAAN SEBENAR DAN ANGGARAN PERBELANJAAN MENGURUS DAN
PEMBANGUNAN" (printed pages ~5-33 of Anggaran_Perbelanjaan_Persekutuan_2026.pdf).
Four amount columns: Perbelanjaan Sebenar 2023, Perbelanjaan Sebenar 2024,
Anggaran Asal 2025, Anggaran 2026 (whole RM as printed).

Layout differs from the 2025 book: the vote code sits inline on the first component
row ("B.62 Mengurus <amounts>", "P.62  Pembangunan <amounts>"), the vote name is the
text line(s) above (CAPS ministry headers / Title-case vote names); "JUMLAH" rows
close a vote (for a B+P pair the JUMLAH is the combined ministry total - skipped, as
are the unlabelled multi-vote ministry roll-ups, both re-derived by validate_2026.py).
T votes print a "Mengurus" total row (captured as component mengurus, like B votes).
P.70 Simpanan Luar Jangka appears once inside the final RINGKASAN KESELURUHAN.

Output: sources/anggaran/data/2026/fact_anggaran_maksud_2026.csv - long format, one
row per (maksud x component x measure), same schema as the 2025 file. maksud_name_bm
carries the printed line(s) above the vote code (may include the ministry group
header); the crosswalk name check uses word overlap, so this is match evidence, not a
canonical label - join on codes, never names.
"""
import csv
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "..", "raw", "Anggaran_Perbelanjaan_Persekutuan_2026.pdf")
OUTDIR = os.path.join(HERE, "..", "..", "data", "2026")
SOURCE_FILE = "Anggaran_Perbelanjaan_Persekutuan_2026.pdf"
RETRIEVED_FROM = "https://belanjawan.mof.gov.my/pdf/belanjawan2026/perbelanjaan/Anggaran_Perbelanjaan_Persekutuan_2026.pdf"
RETRIEVED_DATE = "2026-07-31"
MEASURES = ["sebenar_2023", "sebenar_2024", "anggaran_asal_2025", "anggaran_2026"]
HDR1, HDR2 = "RINGKASAN PERBELANJAAN SEBENAR DAN", "ANGGARAN PERBELANJAAN MENGURUS DAN PEMBANGUNAN"

AMT = re.compile(r"(?<![\d,.])\d{1,3}(?:,\d{3})*(?![\d,.])")
CODE = re.compile(r"^\s*(T|B|P)\.(\d+)\s+(.*)$")
COMPONENT_LABELS = [
    ("Perbelanjaan-perbelanjaan Lain", "lain", "leaf"),
    ("Cara Langsung", "cara_langsung", "leaf"),
    ("Pinjaman", "pinjaman", "leaf"),
    ("Emolumen", "emolumen", "leaf"),
    ("Mengurus", "mengurus", "total"),
    ("Pembangunan", "pembangunan", "total"),
    ("JUMLAH", "jumlah", "total"),
]
SKIP_PREFIX = ("RINGKASAN PERBELANJAAN", "ANGGARAN PERBELANJAAN MENGURUS",
               "Maksud Perbelanjaan", "Sebenar", "Asal", "Anggaran",
               "RM", "(Muka surat")


def amounts(line):
    return [int(m.replace(",", "")) for m in AMT.findall(line)]


def main():
    txt = subprocess.run(["pdftotext", "-layout", RAW, "-"], capture_output=True,
                         text=True, check=True).stdout
    pages = txt.split("\f")
    rows, cur, pending = [], None, []
    for pnum, page in enumerate(pages, 1):
        if HDR1 not in page or HDR2 not in page:
            continue
        m = re.search(r"ANGGARAN PERBELANJAAN PERSEKUTUAN 2026 \| (\d+)", page) or \
            re.search(r"(\d+) \| ANGGARAN PERBELANJAAN PERSEKUTUAN 2026", page)
        printed = m.group(1) if m else ""
        for line in page.splitlines():
            s = line.strip()
            if not s or any(s.startswith(p) for p in SKIP_PREFIX) or re.match(r"^\d", s) \
               or "ANGGARAN PERBELANJAAN PERSEKUTUAN 2026" in s:
                continue
            if s.startswith("RINGKASAN KESELURUHAN"):
                cur, pending = None, []
                continue
            cm = CODE.match(s)
            if cm:
                jl, num, rest = cm.group(1), int(cm.group(2)), cm.group(3)
                vals = amounts(rest)
                label = AMT.sub("", rest).strip().rstrip("-").strip()
                name = re.sub(r"\s*\d+$", "", " ".join(pending[-2:])).strip()
                if label in ("Mengurus", "Pembangunan") and len(vals) == 4:
                    cur = (jl, num, name)
                    rows.append(make_row(cur, "mengurus" if label == "Mengurus" else "pembangunan",
                                         "total", vals, pnum, printed))
                elif len(vals) == 4:
                    # single-line vote (P.70 Simpanan Luar Jangka)
                    rows.append(make_row((jl, num, label), "pembangunan" if jl == "P" else "jumlah",
                                         "leaf", vals, pnum, printed))
                    cur = None
                pending = []
                continue
            vals = amounts(s)
            if cur is not None and len(vals) == 4:
                label = AMT.sub("", s).strip().rstrip("-").strip()
                for prefix, comp, rtype in COMPONENT_LABELS:
                    if label.startswith(prefix):
                        if comp == "jumlah":
                            if cur[0] != "P":
                                rows.append(make_row(cur, comp, rtype, vals, pnum, printed))
                            cur = None
                        else:
                            rows.append(make_row(cur, comp, rtype, vals, pnum, printed))
                        break
                continue
            if len(vals) < 4 and re.search(r"[A-Za-z]", s) \
               and not s.startswith(("JUMLAH", "Perbelanjaan")):
                # name line (footnote superscripts like "KEMENTERIAN DIGITAL 6" carry
                # a stray digit - strip it, it is not an amount)
                pending.append(AMT.sub("", s).strip())

    # P.x name from paired B.x (P rows carry no own printed name); P.70 keeps its label
    bname = {r["maksud_code"][2:]: r["maksud_name_bm"] for r in rows
             if r["maksud_code"].startswith("B.")}
    for r in rows:
        num = r["maksud_code"][2:]
        if r["maksud_code"].startswith("P.") and num in bname and num != "70":
            r["maksud_name_bm"] = bname[num]
    write(rows)


def make_row(cur, comp, rtype, vals, pnum, printed):
    jl, num, name = cur
    return {"maksud_code": f"{jl}.{num:02d}", "maksud_code_printed": f"{jl}.{num}",
            "jenis": {"T": "Tanggungan", "B": "Bekalan", "P": "Pembangunan"}[jl],
            "maksud_name_bm": name, "component": comp, "row_type": rtype, "vals": vals,
            "pdf_page": pnum, "printed_page": printed}


def write(rows):
    os.makedirs(OUTDIR, exist_ok=True)
    dest = os.path.join(OUTDIR, "fact_anggaran_maksud_2026.csv")
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
