#!/usr/bin/env python3
"""Extract Lampiran 1: Penyata Perbelanjaan Mengurus detail (PKKP 2023, pdf 97-194).

Adapted from the proven 2024 pipeline. Layout identical to 2024:
Hierarchy: Maksud (T.xx/B.xx) > Program (6-digit, XX0000, ALL-CAPS) > Aktiviti
(6-digit, XXYY00) > Object row (5-digit 10000..50000).
Columns (7): Anggaran Asal | Tambahan/(Kurangan) | Viremen | Jumlah | Sebenar | % | Varian.
2023 notes: no watermark in text layer; '**' markers normalised to '*';
MANUAL_SALVAGE empty unless a glyph-corrupted row is found (reported, never silent).
"""
import csv
import re

SRC = "2023_Penyata_Kewangan_Kerajaan_Persekutuan.pdf"
OUT = "/home/claude/pkkp/warehouse2023/fact_opex_detail.csv"
pages = open("/home/claude/pkkp/work/2023/full.txt", encoding="utf-8").read().split("\f")

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
    m = re.match(rf"^(.*?)\s+((?:(?:{NUM})\s+){{5,6}}(?:{NUM}))\s*$", line.rstrip())
    if not m:
        return None
    toks = re.findall(NUM, m.group(2))
    if len(toks) == 7:
        return m.group(1).strip(), toks
    if len(toks) == 6 and allow6:
        vals6 = [parse_amount(t) for t in toks]
        for pos in (1, 2, 4, 5):
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
akt_foot = False
last_header = None
unparsed_report = []

MANUAL_SALVAGE = []

for pno in range(97, 195):
    ptxt = pages[pno - 1]
    if "Penyata Perbelanjaan Mengurus" not in ptxt:
        continue
    printed = None
    mprint = re.search(r"^\s*(\d+)\s+PENYATA KEWANGAN|PENYATA KEWANGAN KERAJAAN PERSEKUTUAN 2023\s+(\d+)", ptxt, re.M)
    if mprint:
        printed = int(mprint.group(1) or mprint.group(2))
    plines = ptxt.replace("**", "*").split("\n")
    for li, raw in enumerate(plines):
        line = raw.rstrip()
        s = line.strip()
        if not s:
            continue
        if s.startswith("Nota:") or s.startswith("Nota :") or s.startswith("(**)") or s.startswith("(*)"):
            continue
        if re.match(r"^PERBELANJAAN TANGGUNGAN(\s|–|$)", s) and not split_row(line):
            jenis = "Tanggungan"
            continue
        if re.match(r"^PERBELANJAAN BEKALAN(\s|–|$)", s) and not split_row(line):
            jenis = "Bekalan"
            continue
        mh = re.match(r"^([TB])\.\s?(\d{2})\s+(.+?)(\s*–\s*\(SAMB\.\))?$", s)
        if mh and not split_row(line):
            maksud = f"{mh.group(1)}.{mh.group(2)}"
            nm = mh.group(3).strip()
            if not mh.group(4):
                maksud_name = nm
            jenis = "Tanggungan" if mh.group(1) == "T" else "Bekalan"
            program_code = program_name = akt_code = akt_name = None
            continue
        parsed = split_row(line, allow6=True)
        if parsed is not None and not parsed[0]:
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
            ph = re.match(r"^(\*?)\s?(\d{6})\s+(.+?)(\s*[–—-]?\s*\(SAMB\.\))?$", s)
            if ph:
                code, name = ph.group(2), ph.group(3).strip()
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
            if (last_header and len(s) < 70
                    and not re.search(r"[\d,]{5,}|\d{2}/\d{2}/\d{4}", s)
                    and "PENYATA KEWANGAN" not in s and "LAMPIRAN" not in s
                    and not s.startswith(("JUMLAH", "Jumlah", "PERBELANJAAN"))):
                frag = re.sub(r"\s*[–—-]?\s*\(SAMB\.\)\s*$", "", s).strip()
                if frag:
                    if last_header == "program":
                        program_name = (program_name + " " + frag).strip()
                    else:
                        akt_name = (akt_name + " " + frag).strip()
                continue
            last_header = None
            continue
        last_header = None
        label, toks = parsed
        label = label.lstrip("`'’* ").strip()
        vals = [parse_amount(t) for t in toks]
        foot = any("*" in t for t in toks)
        asal, tambahan, viremen, jumlah, sebenar, pct, varian = vals
        rt = None
        obj_code = obj_class = None
        lab = label
        m5 = re.match(r"^(\d{5})\s+(.+)$", label)
        m6h = re.match(r"^\*?\s?(\d{6})\s+(.+)$", label)
        if m5 and m5.group(1) in OBJ_CLASSES:
            rt, obj_code, obj_class = "object_aktiviti", m5.group(1), m5.group(2).strip()
        elif m6h:
            code, name = m6h.group(1), m6h.group(2).strip()
            if code[2:] == "0000":
                program_code, program_name = code, name
            else:
                akt_code, akt_name = code, name
            continue
        elif re.match(r"^Jumlah\s+(\d{7})$", label) and akt_code and re.match(r"^Jumlah\s+(\d{7})$", label).group(1).lstrip("0").zfill(6) == akt_code:
            # glyph repair (pdf 190): 'Jumlah 0060700' printed for aktiviti 060700 —
            # a doubled leading '0' in the text layer; verified against the aktiviti header
            rt = "jumlah_aktiviti"
            lab = f"Jumlah {akt_code}"
        elif re.match(r"^Jumlah\s+(\d{6})$", label):
            code = re.match(r"^Jumlah\s+(\d{6})$", label).group(1)
            rt = "jumlah_program" if code[2:] == "0000" else "jumlah_aktiviti"
            if rt == "jumlah_aktiviti" and code != akt_code:
                akt_code = code
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
            foot = True
        rows.append([
            jenis, maksud, maksud_name,
            program_code, program_name, akt_code, akt_name,
            obj_code, obj_class, rt, lab, 2023,
            asal, tambahan, viremen, jumlah, sebenar, pct, varian, foot,
            SRC, pno, printed, "Lampiran 1 Penyata Perbelanjaan Mengurus",
        ])

# canonical maksud names from Nota 5(b)
CANON = {}
with open("/home/claude/pkkp/warehouse2023/fact_opex_maksud.csv", encoding="utf-8") as _f:
    for _r in csv.DictReader(_f):
        CANON[_r["maksud_code"]] = _r["maksud_name_bm"]
for r in rows:
    if r[1] in CANON:
        r[2] = CANON[r[1]]
    if r[9] == "jumlah_maksud" and r[1] in CANON:
        r[10] = CANON[r[1]]

for msr in MANUAL_SALVAGE:
    newrow = [msr["jenis"], msr["maksud"], msr["maksud_name"],
              msr["program"], msr["program_name"], None, None,
              None, msr["obj_class"], msr["rt"], msr["label"], 2023,
              *msr["vals"], False,
              SRC, msr["pdf_page"], msr["pdf_page"] - 12, "Lampiran 1 Penyata Perbelanjaan Mengurus"]
    pos = None
    for i, r in enumerate(rows):
        if (r[21] == msr["pdf_page"] and r[1] == msr["maksud"] and r[3] == msr["program"]
                and r[9] == "object_program"):
            pos = i + 1
    rows.insert(pos if pos is not None else len(rows), newrow)

IDX_RT, IDX_LBL = 9, 10
for i, r in enumerate(rows):
    if r[IDX_RT] in ("jumlah_jenis", "jumlah_besar"):
        newrt = "jumlah_objek_jenis" if r[IDX_RT] == "jumlah_jenis" else "jumlah_objek_keseluruhan"
        j = i - 1
        while j >= 0 and rows[j][IDX_RT] == "jumlah_objek_maksud":
            rows[j][IDX_RT] = newrt
            j -= 1

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
jm = sum(r[16] for r in rows if r[9] == "jumlah_maksud")
print(f"sum(jumlah_maksud sebenar) = {jm:,.2f}")
un = [r for r in rows if r[9] == "unclassified"]
print(f"unclassified: {len(un)}")
for r in un[:15]:
    print("   ?", r[10][:70], "p", r[21])
