#!/usr/bin/env python3
"""Extract Lampiran 1: Penyata Perbelanjaan Mengurus detail (PKKP 2019, pdf 77-173).

The 2019 volume HAS a clean text layer for Lampiran 1 (unlike 2020's vector
outlines), so this is the text-based extractor adapted from the proven 2021
pipeline -- but with the FOUR value columns of the 2019/2020 print era:
Anggaran Asal | Anggaran Dipinda | Sebenar Amaun | Prestasi %.
To keep the warehouse2020 schema, Dipinda is stored in anggaran_jumlah_rm and
anggaran_tambahan_rm / viremen_rm / varian_rm are left empty.

Hierarchy: Maksud (T.xx/B.xx) > Program (6-digit XX0000, ALL-CAPS) > Aktiviti
(6-digit XXYY00) > Object row (5-digit 10000..50000). Wrapped headers span
lines; '(SAMB.)' markers are scrubbed; '**'/'***' markers normalised to '*'.
"""
import csv
import re

SRC = "2019_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2019/fact_opex_detail.csv"
pages = open("/home/claude/pkkp/work/2019/full.txt", encoding="utf-8").read().split("\f")
YEAR = 2019

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


def split_row(line, allow3=False):
    """A data row carries 4 value tokens (Asal|Dipinda|Sebenar|Pct); a row whose
    Prestasi cell is omitted in print carries 3 (detected downstream)."""
    m = re.match(rf"^(.*?)\s+((?:(?:{NUM})\s+){{2,3}}(?:{NUM}))\s*$", line.rstrip())
    if not m:
        return None
    toks = re.findall(NUM, m.group(2))
    if len(toks) == 4:
        return m.group(1).strip(), toks
    if len(toks) == 3 and allow3:
        # missing Prestasi %: keep 3 RM columns, pct='–' placeholder -> None
        v3 = [parse_amount(t) for t in toks]
        # plausible only if the pct identity cannot hold with these as 4-col slice
        return m.group(1).strip(), toks + [None]
    return None


rows = []
maksud = maksud_name = jenis = None
program_code = program_name = None
akt_code = akt_name = None
akt_foot = False
last_header = None
objects_open = 0
report = []

for pno in range(77, 174):
    ptxt = pages[pno - 1]
    if "Penyata Perbelanjaan Mengurus" not in ptxt:
        continue
    printed = pno - 12
    ptxt = re.sub(r"\s+PENYATA KEWANGAN KERAJ.*$", "", ptxt, flags=re.M)
    plines = ptxt.replace("***", "*").replace("**", "*").split("\n")
    # print quirk: on some rows the Prestasi % drops to its own line (baseline
    # offset). Merge a lone 'NN.NN' line back into the previous data row.
    for li in range(1, len(plines)):
        st = plines[li].strip()
        if re.fullmatch(r"\d{1,3}\.\d{2}", st):
            for back in range(li - 1, max(li - 3, -1), -1):
                prev = plines[back].rstrip()
                if not prev.strip():
                    continue
                ptoks = re.findall(NUM, prev)
                if len(ptoks) >= 3:
                    plines[back] = prev + " " + st
                    plines[li] = ""
                break
    for li, raw in enumerate(plines):
        line = raw.rstrip()
        s = line.strip()
        if not s:
            continue
        if s.startswith(("Nota:", "Nota :", "(**)", "(*)")):
            continue
        if re.match(r"^\d+\s+PENYATA KEWANGAN|^6 Teks|^\d{1,3}$|^LAMPIRAN|^Penyata Perbelanjaan Mengurus$|^bagi tahun berakhir|^\(sambungan|^\(disambung|^Maksud Perbelanjaan$|^Anggaran$|^Asal\b|^Dipinda\b|^Amaun\b|^Prestasi$|^RM\b|^%$|^Sebenar$", s):
            continue
        if re.match(r"^PERBELANJAAN TANGGUNGAN(\s|–|-|$)", s) and not split_row(line):
            jenis = "Tanggungan"
            continue
        if re.match(r"^PERBELANJAAN BEKALAN(\s|–|-|$)", s) and not split_row(line):
            jenis = "Bekalan"
            continue
        mh = re.match(r"^([TB])\.\s?(\d{2})\s+(.+?)(\s*[–-]\s*\(SAMB\.\))?$", s)
        if mh and not split_row(line):
            maksud = f"{mh.group(1)}.{mh.group(2)}"
            nm = mh.group(3).strip()
            if not mh.group(4):
                maksud_name = nm
            jenis = "Tanggungan" if mh.group(1) == "T" else "Bekalan"
            program_code = program_name = akt_code = akt_name = None
            last_header = "maksud"
            continue
        parsed = split_row(line)
        if parsed is not None and not parsed[0]:
            # numbers-only line: label printed on a neighbouring line (wrapped JUMLAH)
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
            # print quirk (pdf 114, B.21): aktiviti header '20400 Perkhidmatan
            # Veterinar' drops its leading zero; restore (5-digit non-object code)
            m5h = re.match(r"^(\*?)\s?(\d{5})\s+([A-Za-z].+?)(\s*[–—-]?\s*\(SAMB\.\))?$", s)
            if m5h and m5h.group(2) not in OBJ_CLASSES and not re.search(r"[\d,]{7,}", s):
                s = f"{m5h.group(1)}0{m5h.group(2)} {m5h.group(3)}" + (m5h.group(4) or "")
                report.append(f".. leading zero restored on aktiviti header '{m5h.group(2)}' -> '0{m5h.group(2)}' (pdf {pno})")
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
                    if program_code is None or code[:2] != program_code[:2]:
                        inferred = code[:2] + "0000"
                        report.append(f"!! missing program header before aktiviti {code} "
                                      f"({maksud}, pdf {pno}): program {inferred} inferred from code prefix")
                        program_code, program_name = inferred, None
                    akt_code, akt_name = code, name
                    akt_foot = ph.group(1) == "*"
                    last_header = "aktiviti"
                    objects_open = 0
                continue
            if (last_header and len(s) < 75
                    and not re.search(r"[\d,]{5,}|\d{2}/\d{2}/\d{4}", s)
                    and "PENYATA KEWANGAN" not in s and "LAMPIRAN" not in s
                    and not s.startswith(("JUMLAH", "Jumlah", "PERBELANJAAN"))):
                frag = re.sub(r"\s*[–—-]?\s*\(SAMB\.\)\s*$", "", s).strip()
                if frag:
                    if last_header == "maksud" and maksud_name is not None:
                        maksud_name = (maksud_name + " " + frag).strip()
                    elif last_header == "program" and program_name is not None:
                        program_name = (program_name + " " + frag).strip()
                    elif last_header == "aktiviti" and akt_name is not None:
                        akt_name = (akt_name + " " + frag).strip()
                continue
            if re.search(r"[\d,]{7,}", s):
                report.append(f"?? unparsed numeric line p{pno}: {s[:100]!r}")
            last_header = None
            continue
        last_header = None
        label, toks = parsed
        label = label.lstrip("`'’* ").strip()
        # print quirk (e.g. pdf 129 'Jumlah 040100'): the row's Prestasi cell
        # drops to its own line as a lone en-dash, so the 6-digit code is
        # absorbed as the first value token. Restore: code -> label, pct=None.
        if label == "Jumlah" and re.fullmatch(r"\d{5,6}", toks[0].strip()):
            label = f"Jumlah {toks[0].strip().zfill(6)}"
            toks = toks[1:] + [None]
            report.append(f".. restored '{label}' with dropped Prestasi cell (pdf {pno})")
        vals = [parse_amount(t) if t is not None else None for t in toks]
        foot = any(t is not None and "*" in t for t in toks)
        asal, dipinda, sebenar, pct = vals
        if toks[3] is None or (isinstance(toks[3], str) and toks[3].strip("*") in ("–", "—", "-")):
            pct = None
        rt = None
        obj_code = obj_class = None
        lab = label
        m5 = re.match(r"^\*?\s?(\d{5})\s+(.+)$", label)
        m6h = re.match(r"^\*?\s?(\d{6})\s+(.+)$", label)
        mj = re.match(r"^Jumlah\s+[0OQ]?(\d{5,6})\b", label)
        if m5 and m5.group(1) in OBJ_CLASSES:
            rt, obj_code, obj_class = "object_aktiviti", m5.group(1), m5.group(2).strip()
            objects_open += 1
            if label.startswith("*"):
                foot = True
        elif m6h:
            code, name = m6h.group(1), m6h.group(2).strip()
            if code[2:] == "0000":
                program_code, program_name = code, name
            else:
                akt_code, akt_name = code, name
            continue
        elif mj:
            code = mj.group(1).zfill(6)
            rt = "jumlah_program" if code[2:] == "0000" else "jumlah_aktiviti"
            if rt == "jumlah_aktiviti" and code != akt_code:
                if objects_open and akt_code:
                    # PRINT ANOMALY (pdf 169, B.63): the subtotal row under aktiviti
                    # 060100 prints 'Jumlah 040200'. Label kept as printed; the row
                    # is attributed to the open aktiviti block whose object rows it
                    # closes. Reported, never silently corrected.
                    report.append(f"!! PRINT ANOMALY: 'Jumlah {code}' printed while aktiviti "
                                  f"{akt_code} block is open ({maksud}, pdf {pno}); label kept "
                                  f"as printed, row attributed to {akt_code}")
                else:
                    akt_code = code
            lab = f"Jumlah {code}"
            if rt == "jumlah_aktiviti":
                objects_open = 0
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
            obj_code, obj_class, rt, lab, YEAR,
            asal, None, None, dipinda, sebenar, pct, None, foot,
            SRC, pno, printed, "Lampiran 1 Penyata Perbelanjaan Mengurus",
        ])

# back-fill program names for inferred program blocks
_pnames = {}
for r in rows:
    if r[3] and r[4]:
        _pnames.setdefault((r[1], r[3]), r[4])
for r in rows:
    if r[3] and not r[4] and (r[1], r[3]) in _pnames:
        r[4] = _pnames[(r[1], r[3])]

# canonical maksud names from Nota 5(b)
CANON = {}
with open("/home/claude/pkkp/warehouse2019/fact_opex_maksud.csv", encoding="utf-8") as _f:
    for _r in csv.DictReader(_f):
        CANON[_r["maksud_code"]] = _r["maksud_name_bm"]
for r in rows:
    if r[1] in CANON:
        r[2] = CANON[r[1]]
    if r[9] == "jumlah_maksud" and r[1] in CANON:
        r[10] = CANON[r[1]]

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
for n in report:
    print(n)
jm = sum(r[16] for r in rows if r[9] == "jumlah_maksud")
print(f"sum(jumlah_maksud sebenar) = {jm:,.2f}")
un = [r for r in rows if r[9] == "unclassified"]
print(f"unclassified: {len(un)}")
for r in un[:15]:
    print("   ?", str(r[10])[:70], "p", r[21])
# self-check: pct identity on object rows
bad_pct = 0
for r in rows:
    if r[9] == "object_aktiviti" and r[15] and r[17] is not None and r[15] > 0:
        exp = r[16] / r[15] * 100
        if abs(exp - r[17]) > 0.6:
            bad_pct += 1
            if bad_pct <= 10:
                print(f"  pct? p{r[21]} {r[1]} {r[5]} {str(r[10])[:40]} dipinda={r[15]:,.2f} seb={r[16]:,.2f} pct={r[17]} exp={exp:.2f}")
print(f"object rows failing pct≈sebenar/dipinda: {bad_pct}")
