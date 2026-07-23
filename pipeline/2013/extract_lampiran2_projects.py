#!/usr/bin/env python3
"""Extract Lampiran 2 at PROJECT level (PKKP 2013, pdf 226-253).

2013 LAYOUT (differs from 2016/2014): the Lampiran-2 table is a 2-up landscape
spread rendered as ONE PDF page whose visible CropBox (width 654) shows only the
LEFT printed page, but the page content stream carries the WHOLE spread out to
x~1160.  Each such PDF page is therefore a COMPLETE, self-contained 9-column
table (code | name | Kos Keseluruhan | terkumpul RMKe-10 hingga 31.12.2012 |
Anggaran 2013 Cara Langsung/Pinjaman/Jumlah | Sebenar 2013 Cara Langsung/
Pinjaman/Jumlah | terkumpul RMKe-10 hingga 31.12.2013).  Consecutive PDF pages
come in IDENTICAL content pairs (226==227, 228==229, ...) differing only by the
printed footer page number, so we process the EVEN page of each pair and drop
the width filter so the right-half columns are kept.

The left row band (code+name+kos+prior) and the right band (7 numeric columns)
sit ~1.9px apart vertically, so lines_of() (2.5px tolerance) merges them into a
single line of up to 9 numeric tokens.  Sparse rows (genuine blank cells) and
watermark artefacts ('999' inside a name, doubled letters 'PPrroojjeekk') are
resolved by column x1-anchors.  Row types: project / program_subtotal /
ministry_total / grand_total.  Footnotes flagged from a leading '*' on the code
AND from the printed "Nota: *P.xx - Butiran ..." lines.
"""
import csv
import re
import pdfplumber

YEAR = 2013
SRC = "2013_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
PDF = "/home/claude/pkkp/work/2013/2013.pdf"
OUT = "/home/claude/pkkp/warehouse2013/fact_devex_project.csv"
STMT = "Lampiran 2 Penyata Perbelanjaan Pembangunan"
PAGES = range(226, 254, 2)            # even page of each identical pair
NUMTOK = re.compile(r"^\*?\(?[\d,]+(?:\.\d+)?\)?$|^\*?[–—-]$")
# median right-edge (x1) of each of the 9 data columns, from the 808 full rows
ANCH = [465.0, 530.8, 752.4, 805.7, 886.5, 952.4, 1001.8, 1079.3, 1155.8]

ALIASES = {}


def unspread(s):
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\b([A-Z])\s+(?=[A-Z])", r"\1", s)
    return s


def dedouble(tok):
    """Collapse a watermark 'every-letter-doubled' token (PPrroojjeekk -> Projek)."""
    if len(tok) >= 6 and len(tok) % 2 == 0 and tok.isalpha() and tok[0::2] == tok[1::2]:
        return tok[0::2]
    return tok


def desp(s):
    return re.sub(r"\s+", "", s or "")


def parse_amount(tok):
    tok = tok.strip().replace("*", "")
    if tok in {"–", "-", "—", ""}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()").replace(",", "")
    return -float(tok) if neg else float(tok)


def merge_split_numbers(ws):
    out = []
    for wd in ws:
        if out:
            prev = out[-1]
            gap = wd["x0"] - prev["x1"]
            if (gap < 4.0 and re.match(r"^[\d,().*]+$", prev["text"])
                    and re.match(r"^[\d,().*]+$", wd["text"])):
                prev["text"] = prev["text"] + wd["text"]
                prev["x1"] = wd["x1"]
                continue
        out.append(dict(wd))
    return out


def lines_of(page_obj):
    """Full-width lines (NO CropBox width filter -> keep the right-half columns)."""
    words = sorted((w for w in page_obj.extract_words(x_tolerance=1.5, y_tolerance=2)
                    if w.get("upright", True) and 0 <= w["top"] <= page_obj.height),
                   key=lambda w: w["top"])
    cleaned = []
    for w in words:
        t = w["text"]
        if t.strip("!") == "":
            continue
        if "!" in t:
            w = dict(w)
            w["text"] = t.replace("!", "")
            if not w["text"]:
                continue
        cleaned.append(w)
    rows_, cur, cur_top = [], [], None
    for wd in cleaned:
        if cur and wd["top"] - cur_top > 2.5:
            rows_.append(cur)
            cur = []
        if not cur:
            cur_top = wd["top"]
        cur.append(wd)
    if cur:
        rows_.append(cur)
    out = []
    for ws in rows_:
        ws = sorted(ws, key=lambda x: x["x0"])
        out.append((ws[0]["top"], merge_split_numbers(ws)))
    return out


def assign9(cells):
    """Map right-side numeric words to the 9 columns by nearest x1 anchor.
    cells: list of word dicts (already NUMTOK & x0>400), sorted by x0.
    Returns 9 floats (blanks -> 0.0) or None if assignment is ambiguous."""
    vals = [None] * 9
    prev = -1
    for w in cells:
        best, bd = None, 1e9
        for i in range(9):
            d = abs(ANCH[i] - w["x1"])
            if d < bd:
                bd, best = d, i
        if bd > 22 or best <= prev:
            return None
        vals[best] = parse_amount(w["text"])
        prev = best
    return [0.0 if v is None else v for v in vals]


BOILER = re.compile(
    r"^(Penyata Perbelanjaan|bagi tahun|Maksud Perbelanjaan|Kos Keseluruhan|"
    r"Sebenar RMKe|Hingga |Anggaran Tahun|Cara Langsung|Pinjaman|Perbelanjaan\b|"
    r"RM( RM)*$|\( ?sambungan ?\)|PENYATA KEWANGAN|\d+\. lampiran)")


def is_footer(line):
    return bool(re.search(r"\.indd|9/27/14|10:24|8\. lampiran", line)
                or re.fullmatch(r"(\d{1,3}\s*)+", line))


rows = []
stats = {"unmatched": 0, "odd_cols": 0}
current_maksud = current_name = None
current_program = None
last_was_program_hdr = False
notas = {}   # maksud -> set(butiran codes) flagged by printed Nota

with pdfplumber.open(PDF) as pdf:
    for pno in PAGES:
        pg = pdf.pages[pno - 1]
        lns = lines_of(pg)
        last_entry = None
        for top, ws in lns:
            texts = [w["text"] for w in ws]
            line = " ".join(texts)
            if BOILER.match(line) or is_footer(line):
                continue

            # printed footnote lines (may start "Nota:" or directly "*P.xx - Butiran ...")
            m_nota = re.search(r"\*?(P\s?\.\s?\d{2,3})\s*[–-]\s*Butiran\s+(.*?)\s*[–-]\s*Peruntukan", line)
            if m_nota:
                mk = "P." + re.sub(r"\D", "", m_nota.group(1))
                notas.setdefault(mk, set()).update(re.findall(r"\d{5}", m_nota.group(2)))
                last_entry = None
                continue
            if (re.match(r"^Nota\b", line)
                    or re.search(r"Peruntukan sebanyak RM|dibentangkan dalam Sesi Parlimen", line)
                    or line.strip().startswith("pendahuluan")):
                last_entry = None
                continue

            # maksud header  "P.xx NAME [- (SAMB.)]"
            mh = re.match(r"^P\s?\.\s?(\d{2,3})\s+(.+)$", line)
            datacols = [w for w in ws if NUMTOK.match(w["text"]) and w["x0"] > 400]
            if mh and not datacols:
                current_maksud = f"P.{mh.group(1)}"
                is_samb = "(SAMB" in line.upper()
                nm = re.sub(r"\s*[–-]\s*\(SAMB\.?\)\s*$", "", mh.group(2).strip())
                current_name = unspread(nm)
                if not is_samb:
                    current_program = None
                last_entry = None
                last_was_program_hdr = False
                continue

            head = [w["text"] for w in ws if not (NUMTOK.match(w["text"]) and w["x0"] > 400)]
            head = [dedouble(h) for h in head]
            is_proj = bool(head) and re.match(r"^\*?\d{5}$", head[0])

            # code-bearing sub-program header (has a 5-digit code but no values)
            if is_proj and not datacols:
                lbl = " ".join(head[1:]).strip().rstrip(":")
                if lbl:
                    current_program = lbl
                    last_was_program_hdr = True
                last_entry = None
                continue

            if datacols:
                vals = assign9(datacols)
                if vals is None:
                    stats["odd_cols"] += 1
                    print(f"!! unsolvable columns p{pno}: {texts}")
                    continue
                foot2 = any("*" in w["text"] for w in datacols)
                if is_proj:
                    rt = "project"
                    code = head[0].lstrip("*")
                    name = " ".join(head[1:]).strip()
                    foot = head[0].startswith("*") or foot2
                    program = current_program
                    hdr = None
                elif re.match(r"^JUMLAH PERBELANJAAN PEMBANGUNAN", line):
                    rt, code, name = "grand_total", None, "JUMLAH PERBELANJAAN PEMBANGUNAN"
                    foot, program, hdr = foot2, None, None
                elif re.match(r"^JUMLAH\s+[A-Z]", line):
                    name = re.sub(r"^JUMLAH\s+", "", " ".join(head)).strip()
                    base = re.sub(r"\s*[–-]\s*\(SAMB\.?\)\s*$", "", current_name or "").strip()
                    base_cmp = re.sub(r"\s*\([^)]*\)\s*$", "", base).strip()
                    accept = {base, base_cmp} | ALIASES.get(current_maksud or "", set())
                    if desp(name) in {desp(a) for a in accept}:
                        rt, code, program, hdr = "ministry_total", None, None, None
                    else:
                        rt, code, program, hdr = "program_subtotal", None, name, current_program
                    foot = foot2
                elif re.match(r"^Jumlah\s+", " ".join(head)):
                    rt, code = "program_subtotal", None
                    name = re.sub(r"^Jumlah\s+", "", " ".join(head)).strip()
                    program, hdr = name, current_program
                    foot = foot2
                    current_program = None
                else:
                    name = " ".join(head).strip()
                    if not name:
                        continue  # stray dash / margin glyph, no label
                    rt, code = "other", None
                    foot, program, hdr = foot2, None, None
                    print(f"!! unclassified row p{pno}: {name[:50]} {vals}")

                entry = {
                    "maksud": current_maksud, "mname": current_name, "rt": rt,
                    "code": code, "name": name, "foot": foot, "program": program,
                    "hdr": hdr, "vals": vals, "page": pno,
                }
                rows.append(entry)
                last_entry = entry if rt == "project" else None
                last_was_program_hdr = False
                continue

            # non-numeric, non-code line: program header (ALL CAPS) or name wrap
            label = " ".join(dedouble(h) for h in head).strip()
            if not label or len(label) > 95:
                last_entry = None
                continue
            if re.match(r"^(PENYATA|LAMPIRAN|Nota)", label):
                last_entry = None
            elif label == label.upper() and re.match(r"^[A-Z(][A-Z0-9 /,&().'\-]{3,}$", label):
                frag = re.sub(r"\s*[–-]\s*\(SAMB\.?\)\s*$", "", label).strip()
                if last_was_program_hdr and current_program:
                    current_program = current_program + " " + frag
                else:
                    current_program = frag
                last_entry = None
                last_was_program_hdr = True
            elif last_entry is not None:
                last_entry["name"] = (last_entry["name"] + " " + label).strip()

# apply Nota-based footnote flags
for e in rows:
    if e["rt"] == "project" and e["code"] in notas.get(e["maksud"], set()):
        e["foot"] = True

# ---- program linkage: keep program_bm only where a UNIQUE program subtotal
# equals the sum of its tagged project rows (sebenar_jumlah col, index 7) ----
from collections import defaultdict
psum = defaultdict(float)
for e in rows:
    if e["rt"] == "project" and e["program"]:
        psum[(e["maksud"], e["program"].upper())] += e["vals"][7]
subcount = defaultdict(int)
for e in rows:
    if e["rt"] == "program_subtotal":
        for c in {x.upper() for x in (e["program"], e["hdr"]) if x}:
            subcount[(e["maksud"], c)] += 1
ok = set()
for e in rows:
    if e["rt"] != "program_subtotal":
        continue
    linked = None
    for cand in (e["program"], e["hdr"]):
        if not cand:
            continue
        key = (e["maksud"], cand.upper())
        if subcount[key] == 1 and key in psum and abs(psum[key] - e["vals"][7]) < 1:
            linked = key
            break
    if linked:
        ok.add(linked)
    else:
        e["program"] = None
nulled = 0
for e in rows:
    if e["rt"] == "project" and e["program"]:
        if (e["maksud"], e["program"].upper()) not in ok:
            e["program"] = None
            nulled += 1
print(f"program linkage: {len(ok)} verified groups; {nulled} project attributions nulled")

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["maksud_code", "maksud_name_bm", "row_type", "program_bm", "projek_code",
                 "name_bm", "year", "kos_keseluruhan_rm", "terkumpul_rmke10_prior_rm",
                 "anggaran_langsung_rm", "anggaran_pinjaman_rm", "anggaran_jumlah_rm",
                 "sebenar_langsung_rm", "sebenar_pinjaman_rm", "sebenar_jumlah_rm",
                 "terkumpul_rmke10_rm", "has_footnote", "source_file", "pdf_page",
                 "printed_page", "statement"])
    for e in rows:
        kos, prior, agl, agp, agj, sbl, sbp, sbj, kum = e["vals"]
        cw.writerow([e["maksud"], e["mname"], e["rt"], e["program"], e["code"], e["name"],
                     YEAR, kos, prior, agl, agp, agj, sbl, sbp, sbj, kum, e["foot"],
                     SRC, e["page"], e["page"] - 24, STMT])

from collections import Counter
c = Counter(e["rt"] for e in rows)
print(f"fact_devex_project.csv: {len(rows)} rows | {dict(c)} | stats={stats}")
