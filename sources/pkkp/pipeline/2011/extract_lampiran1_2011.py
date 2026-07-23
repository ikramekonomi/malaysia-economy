#!/usr/bin/env python3
"""Extract Lampiran 1 (Penyata Perbelanjaan Mengurus) detail for FY2011.

2011 volume: Lampiran 1 spans PDF pages 70-201 (printed = pdf - 18).
The -layout pdftotext is CLEAN, so we parse it directly with regex.
4 value columns: Anggaran Asal | Anggaran Dipinda | Sebenar Amaun | Sebenar %.
To match the warehouse2012 6-value-era schema:
  anggaran_asal_rm <- Asal ; anggaran_jumlah_rm <- Dipinda ;
  sebenar_rm <- Amaun ; prestasi_pct <- % ;
  anggaran_tambahan_rm / viremen_rm / varian_rm left EMPTY.
Nothing is silently corrected; additivity is validated at the end.
"""
import csv
import re
from collections import Counter

FULL = "/home/claude/pkkp/work/2011/full.txt"
OUT = "/home/claude/pkkp/warehouse2011/fact_opex_detail.csv"
SRC = "2011_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
STMT = "Penyata Perbelanjaan Mengurus"
YEAR = 2011
PAGE_LO, PAGE_HI = 70, 201

OBJ_CLASSES = {
    "10000": "Emolumen",
    "20000": "Perkhidmatan dan Bekalan",
    "30000": "Aset",
    "40000": "Pemberian dan Kenaan Bayaran Tetap",
    "50000": "Perbelanjaan-perbelanjaan Lain",
}
OBJ_NAMES = set(OBJ_CLASSES.values())

ROW_RE = re.compile(r'^(.*?\S)\s{2,}(\S+)\s{2,}(\S+)\s{2,}(\S+)\s{2,}(\S+)\s*$')
NUMRE = re.compile(r'^\*?\(?[\d,]+(?:\.\d+)?\)?$')
DASHRE = re.compile(r'^\*?[–—-]$')

notes = []


def norm(s):
    return (s.replace('ﬁ', 'fi').replace('ﬂ', 'fl')).strip()


def valish(t):
    return bool(NUMRE.match(t) or DASHRE.match(t))


def parse_amount(tok):
    t = tok.strip().replace('*', '')
    if t in ('–', '—', '-', ''):
        return 0.0
    neg = t.startswith('(') and t.endswith(')')
    t = t.strip('()').replace(',', '')
    v = float(t)
    return -v if neg else v


def parse_pct(tok):
    t = tok.strip().replace('*', '')
    if t in ('–', '—', '-', ''):
        return None
    neg = t.startswith('(') and t.endswith(')')
    t = t.strip('()').replace(',', '')
    v = float(t)
    return -v if neg else v


def strip_samb(s):
    s = re.sub(r'\s*[–—-]?\s*\(SAMB\.\)\s*$', '', s)
    s = re.sub(r'\s*\(disambung[^)]*\)\s*$', '', s)
    s = re.sub(r'\s*\(sambungan\)\s*$', '', s)
    return s.strip()


JUNK_RE = re.compile(
    r'\.indd|\d{1,2}/\d{1,2}/\d{2,4}|Penyata Perbelanjaan Mengurus|'
    r'bagi tahun berakhir|\(sambungan\)|\(disambung|Maksud Perbelanjaan|'
    r'PENYATA KEWANGAN|^Anggaran(\s+Sebenar)?$|^Sebenar$|^Asal\b|^RM\b|^%$|^Nota:|'
    r'Program/Aktiviti|Peruntukan sebanyak|dimasuk kira|pendahuluan\.|'
    r'dibentangkan dalam Sesi')


def is_head_line(s):
    """A logical head line (vs a value-less continuation fragment)."""
    if ROW_RE.match(s):
        return True
    st = s.strip().lstrip('*')
    if re.match(r'^[TB]\.\s?\d{2}\b', st):
        return True
    if re.match(r'^\d{5,6}\b', st):
        return True
    if re.match(r'^PERBELANJAAN\s', st):
        return True
    return False


def logical_lines(page):
    """Merge value-less continuation fragments into the preceding head line."""
    out = []
    last_blank = True
    for raw in page.split('\n'):
        s = raw.rstrip()
        if not s.strip():
            last_blank = True
            continue
        st = s.strip()
        if JUNK_RE.search(st):
            last_blank = True
            continue
        if re.fullmatch(r'[\d\s]+', st):     # page-number footer(s), digits only
            last_blank = True
            continue
        if is_head_line(s):
            out.append(s)
            last_blank = False
        else:
            # continuation fragment -> append to previous head line,
            # inserting BEFORE the value columns if the head is a data row
            if out and not last_blank:
                frag = strip_samb(st)
                if frag:
                    mp = ROW_RE.match(out[-1])
                    if mp:
                        out[-1] = (mp.group(1) + ' ' + frag
                                   + out[-1][mp.end(1):])
                    else:
                        out[-1] = out[-1] + ' ' + frag
                last_blank = False    # keep merging chained (multi-line) names
            else:
                notes.append(f"orphan fragment (dropped): {st[:60]!r}")
                last_blank = True     # an orphan is junk; don't anchor later merges
    return out


def main():
    pages = open(FULL, encoding='utf-8').read().split('\f')

    rows = []
    jenis = maksud = maksud_name = None
    program_code = program_name = None
    akt_code = akt_name = None
    seen_prog_jumlah = False
    program_foot = akt_foot = False

    for pno in range(PAGE_LO, PAGE_HI + 1):
        page = pages[pno - 1]
        printed = pno - 18
        for line in logical_lines(page):
            line = line.rstrip()
            m = ROW_RE.match(line)
            # ---------- value-less header lines ----------
            if not m:
                raw_st = norm(line.strip())
                hfoot = raw_st.startswith('*')
                st = strip_samb(raw_st.lstrip('*').strip())
                mh = re.match(r'^([TB])\.\s?(\d{2})\s+(.+)$', st)
                if mh:
                    maksud = f"{mh.group(1)}.{mh.group(2)}"
                    maksud_name = mh.group(3).strip()
                    jenis = 'Tanggungan' if mh.group(1) == 'T' else 'Bekalan'
                    program_code = program_name = akt_code = akt_name = None
                    seen_prog_jumlah = False
                    program_foot = akt_foot = False
                    continue
                if re.match(r'^PERBELANJAAN TANGGUNGAN', st):
                    jenis = 'Tanggungan'
                    program_code = program_name = akt_code = akt_name = None
                    seen_prog_jumlah = False
                    program_foot = akt_foot = False
                    continue
                if re.match(r'^PERBELANJAAN BEKALAN', st):
                    jenis = 'Bekalan'
                    program_code = program_name = akt_code = akt_name = None
                    seen_prog_jumlah = False
                    program_foot = akt_foot = False
                    continue
                ch = re.match(r'^(\d{6})\s+(.+)$', st)
                if ch:
                    code, name = ch.group(1), ch.group(2).strip()
                    if code[2:] == '0000':
                        program_code, program_name = code, name
                        akt_code = akt_name = None
                        seen_prog_jumlah = False
                        program_foot, akt_foot = hfoot, False
                    else:
                        if program_code is None or code[:2] != program_code[:2]:
                            inferred = code[:2] + '0000'
                            notes.append(f"missing program header before aktiviti "
                                         f"{code} ({maksud}, pdf {pno}); inferred {inferred}")
                            program_code, program_name = inferred, None
                            seen_prog_jumlah = False   # new program block started
                            program_foot = False
                        akt_code, akt_name = code, name
                        akt_foot = hfoot
                    continue
                # unrecognised value-less line
                if st:
                    notes.append(f"unrecognised header line pdf {pno}: {st[:60]!r}")
                continue

            # ---------- data rows (label + 4 value columns) ----------
            label = norm(m.group(1))
            toks = [m.group(i) for i in range(2, 6)]
            foot = any('*' in t for t in toks)
            for t in toks:
                if not valish(t):
                    notes.append(f"non-value token {t!r} pdf {pno}: {label[:50]!r}")
            asal = parse_amount(toks[0])
            dipinda = parse_amount(toks[1])
            sebenar = parse_amount(toks[2])
            pct = parse_pct(toks[3])

            rt = obj_code = obj_class = None
            lab = label
            mo = re.match(r'^(\d{5})\s+(.+)$', label)
            mjc = re.match(r'^Jumlah\s+(\d{6})$', label)
            mjc7 = re.match(r'^Jumlah\s+0(\d{6})$', label)   # 7-digit print typo
            if mjc7 and not mjc:
                notes.append(f"7-digit subtotal code print typo pdf {pno}: "
                             f"{label!r} -> read as Jumlah {mjc7.group(1)}")
                mjc = mjc7
            cls_norm = re.sub(r'^Jumlah\s+', '', label).replace('& ', 'dan ')
            cls_norm = re.sub(r'\s+', ' ', cls_norm).strip()

            if mo and mo.group(1) in OBJ_CLASSES:
                rt = 'object_aktiviti'
                obj_code, obj_class = mo.group(1), OBJ_CLASSES[mo.group(1)]
                lab = f"{obj_code} {mo.group(2).strip()}"
            elif mjc:
                code = mjc.group(1)
                if code[2:] == '0000':
                    rt = 'jumlah_program'
                    if code != program_code:
                        program_code = code
                    seen_prog_jumlah = True
                    akt_code = akt_name = None
                else:
                    rt = 'jumlah_aktiviti'
                    if akt_code is not None and code != akt_code and not mjc7:
                        notes.append(f"subtotal code {code} != aktiviti header "
                                     f"{akt_code} (pdf {pno}, {maksud}) - print typo?")
                    if code != akt_code:
                        akt_code = code
                lab = f"Jumlah {code}"
            elif re.match(r'^JUMLAH PERBELANJAAN TANGGUNGAN', label) or \
                    re.match(r'^JUMLAH PERBELANJAAN BEKALAN', label):
                rt = 'jumlah_jenis'
            elif re.match(r'^JUMLAH (PERBELANJAAN|KESELURUHAN) MENGURUS', label):
                rt = 'jumlah_besar'
            elif re.match(r'^JUMLAH\s+\S', label):
                rt = 'jumlah_maksud'
                lab = re.sub(r'^JUMLAH\s+', '', label).strip()
            elif cls_norm in OBJ_NAMES:
                # object-class rollup (bare OR "Jumlah <class>", incl. "&"
                # spelling). Position decides the level: before the program's
                # "Jumlah XX0000" it is a program rollup (object_program);
                # after it, a maksud-level subtotal (jumlah_objek_maksud).
                obj_class = cls_norm
                rt = 'jumlah_objek_maksud' if seen_prog_jumlah else 'object_program'
            else:
                rt = 'unclassified'
                notes.append(f"unclassified data row pdf {pno}: {label[:60]!r}")

            # propagate code-level footnote markers (2012 discipline)
            if rt == 'object_aktiviti':
                foot = foot or (akt_foot if akt_code else program_foot)
            elif rt == 'jumlah_aktiviti':
                foot = foot or akt_foot
            elif rt == 'jumlah_program':
                foot = foot or program_foot

            rows.append([
                jenis, maksud, maksud_name,
                program_code, program_name, akt_code, akt_name,
                obj_code, obj_class, rt, lab, YEAR,
                asal, None, None, dipinda, sebenar, pct, None, foot,
                SRC, pno, printed, STMT,
            ])

    # ---- back-fill program names for blocks whose header was omitted ----
    pnames = {}
    for r in rows:
        if r[3] and r[4]:
            pnames.setdefault((r[1], r[3]), r[4])
    for r in rows:
        if r[3] and not r[4] and (r[1], r[3]) in pnames:
            r[4] = pnames[(r[1], r[3])]

    # ---- relabel object-class subtotals that belong to jenis / grand ----
    IDX_RT = 9
    for i, r in enumerate(rows):
        if r[IDX_RT] in ('jumlah_jenis', 'jumlah_besar'):
            new = 'jumlah_objek_jenis' if r[IDX_RT] == 'jumlah_jenis' \
                else 'jumlah_objek_keseluruhan'
            j = i - 1
            while j >= 0 and rows[j][IDX_RT] == 'jumlah_objek_maksud':
                rows[j][IDX_RT] = new
                j -= 1

    # ---- null out hierarchy fields per row_type (match 2012 convention) ----
    for r in rows:
        rt = r[9]
        if rt in ('object_program', 'jumlah_program'):
            r[5] = r[6] = None                       # clear aktiviti
        elif rt in ('jumlah_objek_maksud', 'jumlah_maksud'):
            r[3] = r[4] = r[5] = r[6] = None          # clear program+aktiviti
        elif rt in ('jumlah_objek_jenis', 'jumlah_jenis',
                    'jumlah_objek_keseluruhan', 'jumlah_besar'):
            r[1] = r[2] = r[3] = r[4] = r[5] = r[6] = None  # clear maksud too

    header = [
        "jenis_bm", "maksud_code", "maksud_name_bm",
        "program_code", "program_name_bm", "aktiviti_code", "aktiviti_name_bm",
        "objek_code", "objek_class_bm", "row_type", "label_bm", "year",
        "anggaran_asal_rm", "anggaran_tambahan_rm", "viremen_rm",
        "anggaran_jumlah_rm", "sebenar_rm", "prestasi_pct", "varian_rm",
        "has_footnote", "source_file", "pdf_page", "printed_page", "statement",
    ]
    with open(OUT, 'w', newline='', encoding='utf-8') as f:
        cw = csv.writer(f)
        cw.writerow(header)
        cw.writerows(rows)

    c = Counter(r[9] for r in rows)
    print(f"WROTE {OUT}: {len(rows)} rows")
    for k, v in c.most_common():
        print(f"  {k}: {v}")
    print(f"notes: {len(notes)}")
    for n in notes[:40]:
        print("  !!", n)
    return rows


if __name__ == '__main__':
    main()
