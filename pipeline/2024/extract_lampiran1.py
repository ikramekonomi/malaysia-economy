#!/usr/bin/env python3
"""Extract Lampiran 1: Penyata Perbelanjaan Mengurus detail (pdf 101-205).

Hierarchy: Maksud (T.xx/B.xx) > Program (6-digit code, XX0000, ALL-CAPS name)
  > Aktiviti (6-digit code, XXYY00, YY!=00) > Object row (5-digit code 10000..50000).
Columns (7): Anggaran Asal | Tambahan/(Kurangan) | Viremen Tambah/(Kurang) | Jumlah
  | Sebenar Amaun | Prestasi % | Varian Kurang/(Lebih) Belanja.
Row types captured: object_aktiviti (leaf), object_program (recap, no code),
  jumlah_aktiviti, jumlah_program, jumlah_objek_maksud (Jumlah Emolumen etc.),
  jumlah_maksud (JUMLAH <NAME>), jumlah_jenis (PERBELANJAAN TANGGUNGAN/BEKALAN totals),
  jumlah_besar.
ALL printed rows are stored; row_type lets users avoid double counting.
"""
import csv
import re

SRC = "2024_Penyata_Kewangan_Kerajaan_Persekutuan.pdf"
OUT = "/home/claude/pkkp/warehouse/fact_opex_detail.csv"
pages = open("/home/claude/pkkp/work/2024_full.txt", encoding="utf-8").read().split("\f")

NUM = r"\*?\(?[\d,]+(?:\.\d+)?\)?|\*?[–—-]"
OBJ_CLASSES = {
    "10000": "Emolumen", "20000": "Perkhidmatan dan Bekalan", "30000": "Aset",
    "40000": "Pemberian dan Kenaan Bayaran Tetap", "50000": "Perbelanjaan-perbelanjaan Lain",
}
OBJ_NAMES = set(OBJ_CLASSES.values())


def parse_amount(tok):
    tok = tok.strip().replace("*", "")
    if tok in {"–", "-", "—", ""}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()").replace(",", "")
    v = float(tok)
    return -v if neg else v


def split_row(line, allow6=False):
    """Return (label, [7 numeric tokens]) or None. With allow6, salvage rows where a
    dash column was dropped by text extraction, using the row identities
    asal+tambahan+viremen=jumlah and pct≈sebenar/jumlah."""
    m = re.match(rf"^(.*?)\s+((?:(?:{NUM})\s+){{5,6}}(?:{NUM}))\s*$", line.rstrip())
    if not m:
        return None
    toks = re.findall(NUM, m.group(2))
    if len(toks) == 7:
        return m.group(1).strip(), toks
    if len(toks) == 6 and allow6:
        vals6 = [parse_amount(t) for t in toks]
        for pos in (1, 2, 4, 5):  # missing Tambahan/Viremen dash or blank Sebenar/%
            cand = vals6[:pos] + [0.0] + vals6[pos:]
            a, t, v, j, s, pct, var = cand
            if (abs(a + t + v - j) <= 2
                    and (j == 0 or abs(pct - (s / j * 100)) <= 0.06)
                    and abs((j - s) - var) <= 2):
                return m.group(1).strip(), toks[:pos] + ["–"] + toks[pos:]
    return None


rows = []
maksud = maksud_name = jenis = None
program_code = program_name = None
akt_code = akt_name = None
akt_foot = False  # aktiviti header printed with * (footnoted)
last_header = None  # 'program'/'aktiviti' when the previous line was a header (for name wraps)
pending_wrap = None  # for jumlah_maksud labels wrapped to next line

# One printed line in all of Lampiran 1 is glyph-corrupted in the PDF text layer
# (pdf 106, T.12 program 030000 recap: a dash overprints '50,000,000' rendering it
# unparseable as '50,0–0 0 , 0 00'). Values below are as printed on the page and
# independently re-derived from character coordinates by the verification pass.
MANUAL_SALVAGE = [
    dict(pdf_page=106, jenis="Tanggungan", maksud="T.12", maksud_name="Perbendaharaan",
         program="030000", program_name="BAYARAN PAMPASAN", rt="object_program",
         label="Pemberian dan Kenaan Bayaran Tetap", obj_class="Pemberian dan Kenaan Bayaran Tetap",
         vals=[109_500_000, 50_000_000, 50_490_000, 209_990_000, 204_660_478.32, 97.46, 5_329_521.68]),
]

for pno in range(101, 206):
    ptxt = pages[pno - 1]
    if "Penyata Perbelanjaan Mengurus" not in ptxt:
        continue
    printed = None
    mprint = re.search(r"^\s*(\d+)\s+PENYATA KEWANGAN|PENYATA KEWANGAN KERAJAAN PERSEKUTUAN 2024\s+(\d+)", ptxt, re.M)
    if mprint:
        printed = int(mprint.group(1) or mprint.group(2))
    plines = ptxt.split("\n")
    for li, raw in enumerate(plines):
        line = raw.rstrip()
        s = line.strip()
        if not s:
            continue
        # jenis section headers
        if re.match(r"^PERBELANJAAN TANGGUNGAN(\s|–|$)", s) and not split_row(line):
            jenis = "Tanggungan"
            continue
        if re.match(r"^PERBELANJAAN BEKALAN(\s|–|$)", s) and not split_row(line):
            jenis = "Bekalan"
            continue
        # maksud header: "T.03 KETUA HAKIM ..." possibly with – (SAMB.)
        mh = re.match(r"^([TB])\.\s?(\d{2})\s+(.+?)(\s*–\s*\(SAMB\.\))?$", s)
        if mh and not split_row(line):
            maksud = f"{mh.group(1)}.{mh.group(2)}"
            nm = mh.group(3).strip()
            if not mh.group(4):  # fresh header, not continuation
                maksud_name = nm
            jenis = "Tanggungan" if mh.group(1) == "T" else "Bekalan"
            program_code = program_name = akt_code = akt_name = None
            continue
        # maksud name continuation line (ALL CAPS, no numbers, short) e.g. "DAN HAKIM – (SAMB.)"
        if (maksud and not split_row(line) and s == s.upper() and not re.search(r"\d", s)
                and len(s) < 60 and not s.startswith("JUMLAH")
                and re.match(r"^[A-Z][A-Z ,/&()'.-]+$", s.replace("– (SAMB.)", "").strip() or "X")):
            # append to maksud_name only if last line set it (heuristic: endswith no punctuation)
            pass  # cosmetic; skip
        parsed = split_row(line, allow6=True)
        if parsed is not None and not parsed[0]:
            # numbers-only line: label wraps around it (e.g. "JUMLAH KETUA HAKIM NEGARA," /
            # <numbers> / "HAKIM BESAR DAN HAKIM"). Stitch from neighbours.
            lbl_parts = []
            for back in (1, 2):
                if li - back >= 0:
                    prev = plines[li - back].strip()
                    if prev and not re.search(r"\d", prev) and (prev.startswith("JUMLAH") or prev == prev.upper()):
                        lbl_parts.insert(0, prev)
                        break
            for fwd in (1, 2):
                if li + fwd < len(plines):
                    nxt = plines[li + fwd].strip()
                    if nxt and not re.search(r"\d", nxt) and nxt == nxt.upper() and not nxt.startswith(("T.", "B.", "JUMLAH", "PERBELANJAAN")):
                        lbl_parts.append(nxt)
                        break
            if lbl_parts:
                parsed = (" ".join(lbl_parts), parsed[1])
        if parsed is None:
            # program / aktiviti headers without numbers (optional * = footnoted aktiviti)
            ph = re.match(r"^(\*?)\s?(\d{6})\s+(.+?)(\s*[–—-]?\s*\(SAMB\.\))?$", s)
            if ph:
                code, name = ph.group(2), ph.group(3).strip()
                # scrub watermark fragments and any SAMB suffix that slipped into the capture
                name = re.sub(r"\s*\(dis\s?ambung[^)]*\)\s*$", "", name)
                name = re.sub(r"\s*[–—-]?\s*\(SAMB\.\)\s*$", "", name).strip()
                if code[2:] == "0000":
                    program_code, program_name = code, name
                    akt_code = akt_name = None
                    akt_foot = False
                    last_header = "program"
                else:
                    akt_code, akt_name = code, name
                    akt_foot = ph.group(1) == "*"
                    last_header = "aktiviti"
                continue
            # wrapped continuation of the header name (may span several lines);
            # short digits inside names ("ADF13", "Litar F1") are fine — only amount-like
            # tokens, footers and page headers disqualify the line
            if (last_header and len(s) < 70
                    and not re.search(r"[\d,]{5,}|\d{2}/\d{2}/\d{4}", s)
                    and "WJD" not in s and "PENYATA KEWANGAN" not in s
                    and not s.startswith(("JUMLAH", "Jumlah", "PERBELANJAAN"))):
                frag = re.sub(r"\s*[–—-]?\s*\(SAMB\.\)\s*$", "", s).strip()
                if frag:
                    if last_header == "program":
                        program_name = (program_name + " " + frag).strip()
                    else:
                        akt_name = (akt_name + " " + frag).strip()
                continue  # keep last_header: name may continue on the next line too
            last_header = None
            continue
        last_header = None
        label, toks = parsed
        label = label.lstrip("`'’* ").strip()  # stray artifact prefixes (e.g. p145)
        vals = [parse_amount(t) for t in toks]
        foot = any("*" in t for t in toks)
        asal, tambahan, viremen, jumlah, sebenar, pct, varian = vals
        rt = None
        obj_code = obj_class = None
        lab = label
        # classify
        m5 = re.match(r"^(\d{5})\s+(.+)$", label)
        m6h = re.match(r"^\*?\s?(\d{6})\s+(.+)$", label)
        if m5 and m5.group(1) in OBJ_CLASSES:
            rt, obj_code, obj_class = "object_aktiviti", m5.group(1), m5.group(2).strip()
        elif m6h:
            # program/aktiviti header printed on same line as numbers (rare) -> treat as its jumlah? skip
            code, name = m6h.group(1), m6h.group(2).strip()
            if code[2:] == "0000":
                program_code, program_name = code, name
            else:
                akt_code, akt_name = code, name
            continue
        elif re.match(r"^Jumlah\s+(\d{6})$", label):
            code = re.match(r"^Jumlah\s+(\d{6})$", label).group(1)
            rt = "jumlah_program" if code[2:] == "0000" else "jumlah_aktiviti"
            if rt == "jumlah_aktiviti" and code != akt_code:
                akt_code = code  # trust printed code
            lab = f"Jumlah {code}"
        elif re.match(r"^Jumlah\s+(Emolumen|Perkhidmatan|Aset|Pemberian|Perbelanjaan)", label):
            rt = "jumlah_objek_maksud"
            obj_class = re.sub(r"^Jumlah\s+", "", label).replace("& ", "dan ")
        elif label in OBJ_NAMES or re.match(r"^(Emolumen|Perkhidmatan dan Bekalan|Aset|Pemberian (dan|&) Kenaan Bayaran Tetap|Perbelanjaan\s*-\s*perbelanjaan Lain)$", label):
            rt, obj_class = "object_program", re.sub(r"\s*-\s*", "-", label) if "-" in label else label
        elif re.match(r"^JUMLAH PERBELANJAAN TANGGUNGAN", label):
            rt = "jumlah_jenis"
        elif re.match(r"^JUMLAH PERBELANJAAN BEKALAN", label):
            rt = "jumlah_jenis"
        elif re.match(r"^JUMLAH (PERBELANJAAN|KESELURUHAN) MENGURUS", label):
            rt = "jumlah_besar"
        elif re.match(r"^JUMLAH\s+", label):
            rt = "jumlah_maksud"
            lab = re.sub(r"^JUMLAH\s+", "", label).strip()
        else:
            rt = "unclassified"
        if rt in ("object_aktiviti", "jumlah_aktiviti") and akt_foot:
            foot = True  # aktiviti header printed with * — propagate to its rows
        rows.append([
            jenis, maksud, maksud_name,
            program_code, program_name, akt_code, akt_name,
            obj_code, obj_class, rt, lab, 2024,
            asal, tambahan, viremen, jumlah, sebenar, pct, varian, foot,
            SRC, pno, printed, "Lampiran 1 Penyata Perbelanjaan Mengurus",
        ])

# canonical maksud names (page headers wrap and truncate; Nota 5(b) names are complete)
CANON = {}
with open("/home/claude/pkkp/warehouse/fact_opex_maksud.csv", encoding="utf-8") as _f:
    for _r in csv.DictReader(_f):
        CANON[_r["maksud_code"]] = _r["maksud_name_bm"]
for r in rows:
    if r[1] in CANON:
        r[2] = CANON[r[1]]
    if r[9] == "jumlah_maksud" and r[1] in CANON:
        r[10] = CANON[r[1]]

# inject manually salvaged rows at the correct position (after the last row of their program on that page)
for msr in MANUAL_SALVAGE:
    newrow = [msr["jenis"], msr["maksud"], msr["maksud_name"],
              msr["program"], msr["program_name"], None, None,
              None, msr["obj_class"], msr["rt"], msr["label"], 2024,
              *msr["vals"], False,
              SRC, msr["pdf_page"], msr["pdf_page"] - 14, "Lampiran 1 Penyata Perbelanjaan Mengurus"]
    pos = None
    for i, r in enumerate(rows):
        if (r[20] == msr["pdf_page"] and r[1] == msr["maksud"] and r[3] == msr["program"]
                and r[9] == "object_program"):
            pos = i + 1
    rows.insert(pos if pos is not None else len(rows), newrow)

# reclassify object recap blocks that precede jenis/grand totals
IDX_RT, IDX_LBL = 9, 10
for i, r in enumerate(rows):
    if r[IDX_RT] in ("jumlah_jenis", "jumlah_besar"):
        newrt = "jumlah_objek_jenis" if r[IDX_RT] == "jumlah_jenis" else "jumlah_objek_keseluruhan"
        j = i - 1
        while j >= 0 and rows[j][IDX_RT] == "jumlah_objek_maksud":
            rows[j][IDX_RT] = newrt
            j -= 1

# hierarchy hygiene: program/maksud-level rows must not carry stale aktiviti/program codes
for r in rows:
    rt = r[9]
    if rt in ("object_program", "jumlah_program"):
        r[5] = r[6] = None
    elif rt in ("jumlah_objek_maksud", "jumlah_maksud"):
        r[3] = r[4] = r[5] = r[6] = None
    elif rt in ("jumlah_objek_jenis", "jumlah_jenis", "jumlah_objek_keseluruhan", "jumlah_besar"):
        r[1] = r[2] = r[3] = r[4] = r[5] = r[6] = None


with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow([
        "jenis_bm", "maksud_code", "maksud_name_bm",
        "program_code", "program_name_bm", "aktiviti_code", "aktiviti_name_bm",
        "objek_code", "objek_class_bm", "row_type", "label_bm", "year",
        "anggaran_asal_rm", "anggaran_tambahan_rm", "viremen_rm", "anggaran_jumlah_rm",
        "sebenar_rm", "prestasi_pct", "varian_rm", "has_footnote",
        "source_file", "pdf_page", "printed_page", "statement",
    ])
    cw.writerows(rows)

from collections import Counter
c = Counter(r[9] for r in rows)
print(f"fact_opex_detail.csv: {len(rows)} rows")
for k, v in c.most_common():
    print(f"  {k}: {v}")
# quick control: sum of jumlah_maksud sebenar should equal 324,617,649,248 minus transfer nuance
jm = sum(r[16] for r in rows if r[9] == "jumlah_maksud")
print(f"sum(jumlah_maksud sebenar) = {jm:,.2f}")
un = [r for r in rows if r[9] == "unclassified"]
print(f"unclassified: {len(un)}")
for r in un[:15]:
    print("   ?", r[10][:70], "p", r[21])
