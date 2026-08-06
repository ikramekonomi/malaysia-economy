#!/usr/bin/env python3
"""Extract the e-SelfAudit census registers of gazetted off-budget entities.

Two LKAN chapters carry the census of badan lain termasuk syarikat gazetted
under the amended Akta Audit 1957 (P.U.(A) 331/2024, 1,856 entities):
- CMD.2.2026.pdf (LKAN 1/2026 vol 2) Bahagian II.3, pdf 85-126 — the FY2024
  reporting round over the 852 federal-level entities. Four sub-reports, each
  restarting its JADUAL numbering: the chapter intro (pdf 85-89), Pencapaian
  Mandat dan Objektif (93-97), Aspek Tatakelola (101-107) and Prestasi
  Kewangan Syarikat (111-125).
- CMD.14.2025.pdf (LKAN 3/2025) Bahagian VII, pdf 204-207 — the 2025 census
  announcement over all 1,856 entities (federal + state registers).

One long-format row per printed register cell -> data/fact_eselfaudit_registers.csv.

Layout logic (pdfplumber; the pdftotext -layout cache cannot band the
multi-line register rows):
- every JADUAL here is a ruled InDesign table whose CELL BORDERS are thin
  vertical rects: their x positions give the column boundaries and their
  y extents give the printed row bands, so a wrapped label (or the bullet
  sub-lines inside II.3 JADUAL 3 row 4) stays inside its own row.
- a table runs from its centred `JADUAL n` heading to its `Sumber:` line;
  a table crossing a page break (Prestasi J4, J7) restarts at the top of the
  continuation page, whose reprinted header block is re-detected and skipped
  (header bands = leading bands of caps/unit/year-only cells).
- words are clipped to the page box and deduplicated: these volumes carry
  duplicated slightly-offset text layers, and a ghost copy of the NEIGHBOUR
  page's text sits at negative x (it contains lookalike `JADUAL`/`Sumber:`
  lines, so heading/stop detection also ignores it).
- column labels/units are declared per table (verbatim from the printed
  header, which is stacked/merged and not reliably reconstructable from
  geometry); the printed header words are still asserted present in the
  header bands. `unit` = 'bilangan' marks entity-count columns, RM units as
  printed, '' for text columns.
- row_type: `line` register rows, `total` printed JUMLAH rows, `group`
  full-width/label-only section rows (their text is rebuilt in reading
  order, since a two-line group heading interleaves across column bands).
- Prestasi J2 prints one label cell merged over each Bilangan/RM Juta row
  pair: the pair is re-joined and the label fragments re-attached in band
  order; each sub-row keeps its own unit.
Values are kept exactly as printed (parentheses negatives, `-` nils kept as
the hyphen the text layer yields, `> 10`, `*`/`**` note markers).
Word building uses y_tolerance=1: the doubled offset text layer leaves
ghost lines between the printed baselines, and the default tolerance
interleaves two printed lines into letter-fragment words (Prestasi J7 row 4).
"""
import csv
import os
import re

import pdfplumber

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "raw")
DATA = os.path.join(HERE, "..", "data")

V2, V14 = "CMD.2.2026.pdf", "CMD.14.2025.pdf"
R2, R14 = "LKAN 1/2026", "LKAN 3/2025"

BIL_CELL = re.compile(r"^\d{1,3}\.$")
YEAR_CELL = re.compile(r"^\d{4}$")

def T(report, source, bahagian, jadual, pages, title, cols, groups_re=None,
      mode=None, excerpt=""):
    return dict(report=report, source=source, bahagian=bahagian,
                jadual=jadual, pages=pages, title=title, cols=cols,
                groups_re=groups_re, mode=mode, excerpt=excerpt)


BIL = "bilangan"
RMJ = "RM Juta"

TABLES = [
    # ---- CMD.2.2026 Bahagian II.3 — chapter intro (pdf 85-89) ----
    T(R2, V2, "II.3", 1, [85], "KOMPOSISI ENTITI YANG DIWARTAKAN",
      [("JUMLAH", BIL)]),
    T(R2, V2, "II.3", 2, [87],
      "PELAKSANAAN KHIDMAT MEJA BANTUAN FIZIKAL DAN TAKLIMAT KHAS BAGI "
      "SISTEM e-SELFAUDIT KEPADA ENTITI DIWARTAKAN",
      [("BILANGAN", BIL)]),
    T(R2, V2, "II.3", 3, [88],
      "STATUS PELAKSANAAN SISTEM e-SELFAUDIT BAGI SYARIKAT "
      "KERAJAAN PERSEKUTUAN",
      [("JUMLAH", BIL)]),
    T(R2, V2, "II.3", 4, [89],
      "SYARIKAT KERAJAAN PERSEKUTUAN MENGIKUT JENIS DAN STATUS",
      [("AKTIF SPV", BIL), ("AKTIF BUKAN SPV", BIL), ("DORMAN", BIL),
       ("JUMLAH", BIL)]),
    # ---- II.3 Pencapaian Mandat dan Objektif Penubuhan (pdf 93-97) ----
    T(R2, V2, "II.3 Mandat", 1, [94],
      "PEMATUHAN AKTIVITI UTAMA SYARIKAT BERBANDING PERLEMBAGAAN",
      [("JUMLAH", BIL)]),
    T(R2, V2, "II.3 Mandat", 2, [94],
      "AKTIVITI UTAMA TIDAK SELARAS DENGAN PERLEMBAGAAN SYARIKAT",
      [("PERLEMBAGAAN SYARIKAT", ""), ("AKTIVITI UTAMA", "")]),
    T(R2, V2, "II.3 Mandat", 3, [95],
      "PEMATUHAN PELAN STRATEGIK BERBANDING OBJEKTIF PENUBUHAN",
      [("JUMLAH", BIL)]),
    T(R2, V2, "II.3 Mandat", 4, [97],
      "PEMATUHAN PETUNJUK PRESTASI UTAMA BERBANDING "
      "PELAN STRATEGIK SYARIKAT",
      [("JUMLAH", BIL)]),
    T(R2, V2, "II.3 Mandat", 5, [97],
      "KELULUSAN PETUNJUK PRESTASI UTAMA OLEH LEMBAGA PENGARAH",
      [("JUMLAH", BIL)]),
    T(R2, V2, "II.3 Mandat", 6, [97],
      "SYARIKAT MKD ATAU SYARIKAT SUBSIDIARI MKD YANG TIDAK MENYEDIAKAN KPI",
      [("SYARIKAT INDUK", "")]),
    # ---- II.3 Aspek Tatakelola (pdf 101-107) ----
    T(R2, V2, "II.3 Tatakelola", 1, [103],
      "STATUS KEANGGOTAAN LEMBAGA PENGARAH", [("JUMLAH", BIL)]),
    T(R2, V2, "II.3 Tatakelola", 2, [104],
      "STATUS PELANTIKAN PENGARAH BEBAS DALAM LEMBAGA PENGARAH",
      [("JUMLAH", BIL)]),
    T(R2, V2, "II.3 Tatakelola", 3, [106], "STATUS PENUBUHAN JKA",
      [("JUMLAH", BIL)]),
    T(R2, V2, "II.3 Tatakelola", 4, [107],
      "PEMBENTANGAN LAPORAN JAWATANKUASA AUDIT KEPADA LEMBAGA PENGARAH",
      [("JUMLAH", BIL)]),
    # ---- II.3 Prestasi Kewangan Syarikat (pdf 111-125) ----
    T(R2, V2, "II.3 Prestasi", 1, [111], "KEUNTUNGAN/(KERUGIAN) CLBS AKTIF",
      [("SYARIKAT UNTUNG BILANGAN", BIL), ("SYARIKAT UNTUNG RM Juta", RMJ),
       ("SYARIKAT RUGI BILANGAN", BIL), ("SYARIKAT RUGI RM Juta", RMJ)]),
    T(R2, V2, "II.3 Prestasi", 2, [112], "LEBIHAN/(KURANGAN) CLBG",
      [("2022", ""), ("2023", ""), ("CATATAN", "")], mode="clbg"),
    T(R2, V2, "II.3 Prestasi", 3, [114],
      "SYARIKAT CLBS YANG MEMBAYAR DIVIDEN KEPADA KERAJAAN "
      "PERSEKUTUAN PADA TAHUN 2022 DAN 2023",
      [("TAHUN 2023", RMJ), ("TAHUN 2022", RMJ),
       ("PERUBAHAN RM Juta", RMJ), ("PERUBAHAN %", "%")]),
    T(R2, V2, "II.3 Prestasi", 4, [115, 116],
      "SYARIKAT MKD BERSTATUS CLBS MENCATAT KEUNTUNGAN "
      "TETAPI TIDAK MEMBAYAR DIVIDEN PADA TAHUN 2022 DAN 2023",
      [("NAMA AGENSI/SYARIKAT INDUK", ""),
       ("KEUNTUNGAN TAHUN SEMASA 2023", RMJ),
       ("KEUNTUNGAN TAHUN SEMASA 2022", RMJ),
       ("KEUNTUNGAN TERKUMPUL 2023", RMJ),
       ("NISBAH SEMASA 2023", ""), ("NISBAH SOLVENSI 2023", "")]),
    T(R2, V2, "II.3 Prestasi", 5, [118],
      "BILANGAN SYARIKAT YANG MEMPUNYAI "
      "ISU USAHA BERTERUSAN DALAM SIJIL JURUAUDIT LUAR",
      [("BIL. SYARIKAT", BIL)]),
    T(R2, V2, "II.3 Prestasi", 6, [119],
      "BILANGAN SYARIKAT YANG MEMPUNYAI "
      "ASAS KEPADA ISU USAHA BERTERUSAN DALAM NOTA KEPADA AKAUN",
      [("BIL. SYARIKAT", BIL)]),
    T(R2, V2, "II.3 Prestasi", 7, [120, 121],
      "SYARIKAT DENGAN BAKI PENDAPATAN GERAN TERTUNDA "
      "BAGI TAHUN BERAKHIR 2023",
      [("BAKI GERAN TERTUNDA BAGI TAHUN BERAKHIR 2023", RMJ),
       ("RINGKASAN OBJEKTIF PENUBUHAN SYARIKAT", ""),
       ("TUJUAN GERAN DISALURKAN", "")],
      groups_re=re.compile(r"^(Syarikat yang melaksanakan|"
                           r"Geran digunakan untuk)")),
    T(R2, V2, "II.3 Prestasi", 8, [121],
      "SYARIKAT DENGAN BAKI SOKONGAN KEWANGAN "
      "TERTINGGI BAGI TAHUN BERAKHIR 2023",
      [("AGENSI/SYARIKAT INDUK", ""),
       ("BAKI SOKONGAN KEWANGAN* BAGI TAHUN BERAKHIR 2023", RMJ)],
      excerpt="10 tertinggi daripada 119 syarikat (teks p121 perenggan d)"),
    T(R2, V2, "II.3 Prestasi", 9, [123],
      "PERBELANJAAN STATUTORI FI AUDIT "
      "BAGI SYARIKAT BERSTATUS DORMAN BAGI TAHUN 2022 DAN 2023",
      [("BILANGAN SYARIKAT", BIL), ("TAHUN 2022", RMJ),
       ("TAHUN 2023", RMJ), ("JUMLAH", RMJ)]),
    T(R2, V2, "II.3 Prestasi", 10, [124],
      "MAKLUMAT ASET/LIABILITI BERSIH TAHUN 2023 "
      "BAGI SYARIKAT DORMAN MELEBIHI LIMA TAHUN",
      [("BILANGAN SYARIKAT", BIL), ("RM Juta", RMJ)],
      groups_re=re.compile(r"^Syarikat (Masih|Tidak) Mempunyai")),
    T(R2, V2, "II.3 Prestasi", 11, [125],
      "JENIS PERBELANJAAN YANG DIREKODKAN OLEH SYARIKAT PERSEKUTUAN "
      "YANG MEMPUNYAI OBLIGASI KEWANGAN DAN BERADA DALAM KEDUDUKAN "
      "LIABILITI BERSIH",
      [("2022", RMJ), ("2023", RMJ), ("JUMLAH", RMJ)]),
    T(R2, V2, "II.3 Prestasi", 12, [125],
      "JENIS PERBELANJAAN YANG DIREKODKAN OLEH SYARIKAT YANG TIDAK "
      "MEMPUNYAI OBLIGASI KEWANGAN TETAPI BERADA DALAM KEDUDUKAN "
      "LIABILITI BERSIH",
      [("2022", RMJ), ("2023", RMJ), ("JUMLAH", RMJ)]),
    # ---- CMD.14.2025 Bahagian VII — the 2025 census (pdf 204-207) ----
    T(R14, V14, "VII", 1, [204],
      "KOMPOSISI BADAN LAIN TERMASUK SYARIKAT YANG DIWARTAKAN",
      [("JUMLAH", BIL)]),
    T(R14, V14, "VII", 2, [206],
      "STATUS PELAKSANAAN SISTEM e-SELFAUDIT BAGI BADAN LAIN "
      "TERMASUK SYARIKAT DI PERINGKAT KERAJAAN PERSEKUTUAN",
      [("JUMLAH", BIL)]),
    T(R14, V14, "VII", 3, [206],
      "STATUS PELAKSANAAN SISTEM e-SELFAUDIT BAGI BADAN LAIN "
      "TERMASUK SYARIKAT DI PERINGKAT KERAJAAN NEGERI",
      [("MAKLUM BALAS (Sistem e-SelfAudit) KEMUKA", BIL),
       ("MAKLUM BALAS (Sistem e-SelfAudit) TIDAK KEMUKA", BIL),
       ("STATUS (Winding Up/Dissolved/Tidak Lagi Berkaitan Dengan "
        "Kerajaan)", BIL),
       ("JUMLAH", BIL)]),
    T(R14, V14, "VII", 4, [207], "CIRI-CIRI CLBS DAN CLBG",
      [("CIRI-CIRI UTAMA", "")]),
    T(R14, V14, "VII", 5, [207],
      "KATEGORI SYARIKAT YANG MENGEMUKAKAN MAKLUM BALAS e-SELFAUDIT",
      [("AKTIF CLBS", BIL), ("AKTIF CLBG", BIL),
       ("SPV CLBS", BIL), ("SPV CLBG", BIL),
       ("DORMAN CLBS", BIL), ("DORMAN CLBG", BIL),
       ("SEDANG DALAM PROSES WINDING UP/DISSOLVED CLBS", BIL),
       ("SEDANG DALAM PROSES WINDING UP/DISSOLVED CLBG", BIL),
       ("JUMLAH", BIL)]),
]


def squish(text):
    return re.sub(r"\s+", " ", text).strip()


def cluster(vals, tol):
    out = []
    for v in sorted(vals):
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(c) / len(c) for c in out]


def page_words(page):
    """Words clipped to the page box (the ghost copy of the neighbouring
    page's text sits at negative x; out-of-box text beyond page.width) and
    deduplicated across the doubled slightly-offset text layers."""
    seen, out = set(), []
    for w in sorted(page.extract_words(y_tolerance=1),
                    key=lambda w: (w["top"], w["x0"])):
        if w["x0"] < 0 or w["x1"] > page.width + 1 or w["top"] < 0 \
                or w["bottom"] > page.height + 1:
            continue
        key = (w["text"], round(w["x0"] / 2), round(w["top"] / 2))
        if key in seen:
            continue
        seen.add(key)
        out.append(w)
    return out


def find_jadual(words, n):
    """bottom y of the centred 'JADUAL n' heading line."""
    for w in words:
        if w["text"] == "JADUAL":
            line = [v for v in words if abs(v["top"] - w["top"]) < 2]
            txt = " ".join(v["text"] for v in line)
            if re.search(r"\bJADUAL %d\b" % n, txt):
                return w["bottom"]
    return None


def sumber_after(words, y, page_h):
    cands = [w["top"] for w in words
             if w["text"].startswith("Sumber:") and w["top"] > y + 1]
    return min(cands) if cands else page_h


def reading_text(ws):
    """Join words in printed reading order (line by line)."""
    lines = {}
    for w in ws:
        key = round(w["top"] / 4)
        lines.setdefault(key, []).append(w)
    out = []
    for key in sorted(lines):
        out.extend(t["text"] for t in sorted(lines[key],
                                             key=lambda w: w["x0"]))
    return squish(" ".join(out))


NUM_CELL = re.compile(r"^\(?[\d,]+(\.\d+)?\)?%?\*{0,2}$")


def is_data_band(cells, rdtext, groups_re):
    """The (reprinted) header block ends at the first band carrying a BIL
    running number, a non-year numeric cell, or a declared group heading."""
    if groups_re and groups_re.match(rdtext):
        return True
    for c in cells:
        if BIL_CELL.match(c):
            return True
        if NUM_CELL.match(c) and not YEAR_CELL.match(c):
            return True
    return False


def band_region(page, top, bottom):
    """(xs, bands, words) for the ruled table between y=top and y=bottom."""
    vr = [r for r in page.rects
          if r["width"] < 2.5 and r["height"] > 5
          and r["top"] >= top - 2 and r["bottom"] <= bottom + 2
          and 0 <= r["x0"] <= page.width]
    if not vr:
        raise RuntimeError("no cell-border rects in region")
    xs = cluster([r["x0"] for r in vr], 5)
    ys = cluster([r["top"] for r in vr] + [r["bottom"] for r in vr], 3)
    bands = [(ys[i], ys[i + 1]) for i in range(len(ys) - 1)
             if any(r["top"] - 2 <= (ys[i] + ys[i + 1]) / 2 <= r["bottom"] + 2
                    for r in vr)]
    words = [w for w in page_words(page)
             if top <= (w["top"] + w["bottom"]) / 2 <= bottom
             and xs[0] - 2 <= (w["x0"] + w["x1"]) / 2 <= xs[-1] + 2]
    return xs, bands, words


def band_rows(page, top, bottom):
    """[(cells, reading_order_text)] per printed row band; empty columns
    (padding rects double some borders) are dropped."""
    xs, bands, words = band_region(page, top, bottom)
    rows = []
    for (b0, b1) in bands:
        ws = [w for w in words if b0 <= (w["top"] + w["bottom"]) / 2 < b1]
        cells = [[] for _ in range(len(xs) - 1)]
        for w in sorted(ws, key=lambda w: (w["top"], w["x0"])):
            xc = (w["x0"] + w["x1"]) / 2
            for i in range(len(xs) - 1):
                if xs[i] <= xc < xs[i + 1]:
                    cells[i].append(w["text"])
                    break
        rows.append(([squish(" ".join(c)) for c in cells],
                     reading_text(ws)))
    return rows


def title_text(page, jadual_y, table_top):
    ws = [w for w in page_words(page)
          if jadual_y - 1 < (w["top"] + w["bottom"]) / 2 < table_top]
    return reading_text(ws)


def parse_table(pdf, spec):
    """-> (title_found, [row dicts]) for one JADUAL."""
    out = []
    title_found = None
    for pi, pno in enumerate(spec["pages"]):
        page = pdf.pages[pno - 1]
        words = page_words(page)
        if pi == 0:
            jy = find_jadual(words, spec["jadual"])
            if jy is None:
                raise RuntimeError("JADUAL %d head not found on pdf %d"
                                   % (spec["jadual"], pno))
            bottom = sumber_after(words, jy, page.height)
            xs, bands, _ = band_region(page, jy, bottom)
            title_found = title_text(page, jy, min(b0 for b0, _ in bands))
            top = jy
        else:                       # continuation page: top -> its Sumber:
            top, bottom = 0, sumber_after(words, 0, page.height)
        rows = band_rows(page, top, bottom)
        in_header, data = True, []
        for cells, rdtext in rows:
            if in_header and not is_data_band(cells, rdtext,
                                              spec["groups_re"]):
                continue
            in_header = False
            data.append((cells, rdtext))
        # drop columns that no data band of this page uses (padding rects
        # double some borders; header-only words must not keep them alive)
        used = [i for i in range(len(data[0][0]) if data else 0)
                if any(cells[i] for cells, _ in data)]
        for cells, rdtext in data:
            out.append({"pdf_page": pno, "cells": [cells[i] for i in used],
                        "read": rdtext})
    return title_found, out


def classify(label, spec, rdtext, has_values):
    if spec["groups_re"] and spec["groups_re"].match(rdtext):
        return "group"
    if not has_values and not label.upper().startswith("JUMLAH"):
        return "group"
    if label.upper().startswith("JUMLAH"):
        return "total"
    return "line"


def emit(recs, spec, row_label, col_label, value, unit, row_type, page):
    recs.append({
        "report": spec["report"], "source_file": spec["source"],
        "bahagian": spec["bahagian"], "jadual_no": spec["jadual"],
        "jadual_title_bm": spec["title"], "row_label_bm": row_label,
        "col_label_bm": col_label, "value_verbatim": value, "unit": unit,
        "row_type": row_type, "pdf_page": page})


def rows_standard(recs, spec, rows):
    n = 0
    for r in rows:
        if spec["groups_re"] and spec["groups_re"].match(r["read"]):
            emit(recs, spec, r["read"], "", "", "", "group", r["pdf_page"])
            continue
        cells = list(r["cells"])
        if cells and BIL_CELL.match(cells[0]):
            cells = cells[1:]
        elif len(cells) == len(spec["cols"]) + 2 and not cells[0]:
            cells = cells[1:]                       # empty BIL cell (JUMLAH)
        label, vals = cells[0], cells[1:]
        if len(vals) != len(spec["cols"]):
            raise RuntimeError("%s J%d: %d value cells for %d columns: %r"
                               % (spec["bahagian"], spec["jadual"],
                                  len(vals), len(spec["cols"]), cells))
        rtype = classify(label, spec, r["read"], any(vals))
        if rtype == "group":
            emit(recs, spec, r["read"] if spec["groups_re"] else label,
                 "", "", "", "group", r["pdf_page"])
            continue
        for (cl, unit), v in zip(spec["cols"], vals):
            if v == "":
                continue
            emit(recs, spec, label, cl, v, unit, rtype, r["pdf_page"])
            n += 1
    return n


def rows_clbg(recs, spec, rows):
    """Prestasi J2: label cells merge over each Bilangan/RM Juta row pair."""
    n = 0
    pend = None                       # (label_frags, perkara, cells, page)
    groups = []
    for r in rows:
        label, perkara, vals = r["cells"][0], r["cells"][1], r["cells"][2:]
        if perkara == "Bilangan" and pend is not None:
            groups.append(pend)
            pend = None
        if pend is None:
            pend = {"labels": [], "subs": []}
        if label:
            pend["labels"].append(label)
        pend["subs"].append((perkara, vals, r["pdf_page"]))
    if pend:
        groups.append(pend)
    for g in groups:
        row_label = squish(" ".join(g["labels"]))
        for perkara, vals, page in g["subs"]:
            unit = BIL if perkara == "Bilangan" else RMJ
            for (cl, _), v in zip(spec["cols"], vals):
                if v == "":
                    continue
                emit(recs, spec, row_label, cl, v,
                     "" if cl == "CATATAN" else unit, "line", page)
                n += 1
    return n


def main():
    pdfs = {}
    recs, log = [], []
    for spec in TABLES:
        if spec["source"] not in pdfs:
            pdfs[spec["source"]] = pdfplumber.open(
                os.path.join(RAW, spec["source"]))
        title, rows = parse_table(pdfs[spec["source"]], spec)
        got, want = squish(title).upper(), squish(spec["title"]).upper()
        if got != want:
            print("  ! %s J%d title mismatch:\n      page: %r\n      spec: %r"
                  % (spec["bahagian"], spec["jadual"], got, want))
        n = (rows_clbg if spec["mode"] == "clbg" else
             rows_standard)(recs, spec, rows)
        log.append((spec, n))
    cols = ["report", "source_file", "bahagian", "jadual_no",
            "jadual_title_bm", "row_label_bm", "col_label_bm",
            "value_verbatim", "unit", "row_type", "pdf_page"]
    dest = os.path.join(DATA, "fact_eselfaudit_registers.csv")
    with open(dest, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows([{c: r[c] for c in cols} for r in recs])
    print("%d cell rows, %d tables -> %s" % (len(recs), len(log), dest))
    for spec, n in log:
        print("  %-11s %-16s J%-2d %-52s %3d cells"
              % (spec["source"].replace(".pdf", ""), spec["bahagian"],
                 spec["jadual"], spec["title"][:52], n))


if __name__ == "__main__":
    main()
