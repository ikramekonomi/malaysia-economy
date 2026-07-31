#!/usr/bin/env python3
"""Extract the audit inventory + finding register from the five LKAN Aktiviti volumes.

Produces data/fact_lkan_audits.csv (one row per audit/chapter, from the scoping-pass
inventory, cross-checked against the text) and data/fact_lkan_findings.csv (one row
per finding unit) from page-aligned `pdftotext -layout` text (0-based `\\f`-split
chunk i == pdf_page i+1). Text is looked up in $LKAN_TEXT_DIR then raw/_text/, and
generated with pdftotext if missing. Structural map: pipeline/STRUCTURE_NOTES.md.

Three chapter architectures (see STRUCTURE_NOTES.md):
- numbered (audit_style chapter/kaa): full-width skeleton; finding units are the
  `P.x.` / `P.x.y.` headings/paragraphs under section `P. PENEMUAN ...` (P=5 for the
  Aktiviti skeleton, 2 for the CMD.14 KAA chapters, 4 for its V.1). A candidate
  number is accepted only if it is the valid successor of the previous unit
  (x+1 / x.1 / x.y+1), which kills lookalike table rows and wrapped cross-references.
  Units partition the section text; RM tokens, Maklum-balas response headings and
  two-line `Pendapat`/`Audit` boxes are harvested from each unit's span.
- margin (audit_style margin_label): CMD.9.2024 and CMD.14's IV.3/IV.4/V.2 print a
  narrow label column beside the body (continuous paragraph numbering per audit).
  Lines are split at the body column (taken from the nearest pure-body line);
  contiguous label-bearing lines form a block, split on caps/mixed case change, at
  `Maklum balas`/`Pendapat Audit` starts, and where a response block's body starts a
  new numbered paragraph. ALL-CAPS blocks are matched (line-greedy, longest-first)
  against the section vocabulary; mixed-case blocks whose first body line starts a
  numbered paragraph open a finding unit. One row per sub-topic label inside the
  content sections, section_path = the paragraph-number range it spans.
- register (CMD.2.2026 II.3, e-SelfAudit census): inventory row only, no per-finding
  rows — the chapter is a census of 852 entities, not a findings narrative.

Text-layer hazards handled: InDesign slug lines, duplicated/interleaved footers,
editorial marks, printed-page footers (all stripped before parsing). Amounts and
labels are kept exactly as printed; source quirks belong in
data/_source_anomalies_lkan.csv, never silently corrected.
"""
import csv
import os
import re
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "raw")
DATA = os.path.join(HERE, "..", "data")

# ---------------------------------------------------------------- inventory
# Verified scoping pass over the five volumes (pdf pages are 1-based, inclusive).
# parse: numbered | margin | register;  prefix: the penemuan section number for
# numbered chapters;  scope (margin): sections whose sub-topic labels become rows —
# "content" = the CMD.9 content sections only, "all" = everything outside the
# front/back matter sections (the CMD.14 margin chapters have no PENEMUAN divider).
A = "chapter"
INVENTORY = [
    # report, source_file, chapter_id, ministry_bm, entity_bm, topic_bm,
    # audit_style, pdf_start, pdf_end, parse, prefix/scope
    ("LKAN 2/2024", "CMD.8.2024.pdf", "1", "Jabatan Perdana Menteri",
     "Jabatan Wilayah Persekutuan",
     "Pengurusan Projek Sungai Nadi Kehidupan (River of Life)", A, 15, 80, "numbered", 5),
    ("LKAN 2/2024", "CMD.8.2024.pdf", "2", "Kementerian Ekonomi",
     "Majlis Pembangunan Wilayah Ekonomi Pantai Timur",
     "Pengurusan Projek dan Program di Bawah Wilayah Ekonomi Pantai Timur (ECER)",
     A, 81, 110, "numbered", 5),
    ("LKAN 2/2024", "CMD.8.2024.pdf", "3", "Kementerian Kemajuan Desa dan Wilayah", "",
     "Pengurusan Projek Bekalan Air Luar Bandar Sarawak dan Sabah", A, 111, 140, "numbered", 5),
    ("LKAN 2/2024", "CMD.8.2024.pdf", "4",
     "Kementerian Peralihan Tenaga dan Transformasi Air; "
     "Kementerian Sumber Asli dan Kelestarian Alam", "",
     "Pengurusan Air Negara", A, 141, 186, "numbered", 5),
    ("LKAN 2/2024", "CMD.8.2024.pdf", "5", "Kementerian Perumahan dan Kerajaan Tempatan",
     "Jabatan Bomba dan Penyelamat Malaysia",
     "Pengurusan Perkhidmatan Kebombaan", A, 187, 214, "numbered", 5),
    ("LKAN 2/2024", "CMD.8.2024.pdf", "6", "KPKT; NRES",
     "JWP, JKPTG, Jabatan Perumahan Negara, PTG WP, DBKL, Perbadanan Putrajaya, "
     "Perbadanan Labuan",
     "Pengurusan Kediaman Berstrata di Wilayah Persekutuan", A, 215, 250, "numbered", 5),
    ("LKAN 2/2024", "CMD.8.2024.pdf", "7", "Kementerian Komunikasi", "",
     "Pengurusan Program Pemerkasaan Jaringan dan Infrastruktur Telekomunikasi "
     "Jalur Lebar", A, 251, 282, "numbered", 5),
    ("LKAN 2/2024", "CMD.8.2024.pdf", "8", "MITI; Kementerian Digital; KUSKOP; KKDW", "",
     "Pengurusan Program Pembangunan Keusahawanan e-Dagang", A, 283, 306, "numbered", 5),
    ("LKAN 2/2024", "CMD.8.2024.pdf", "9", "Kementerian Pertahanan",
     "Tentera Laut Diraja Malaysia",
     "Pengurusan Kapal Tentera Laut Diraja Malaysia", A, 307, 328, "numbered", 5),

    ("LKAN 2/2024", "CMD.9.2024.pdf", "1", "Jabatan Perdana Menteri",
     "Majlis Profesor Negara (MPN)", "Tadbir urus dan kewangan MPN",
     "margin_label", 17, 54, "margin", "content"),
    ("LKAN 2/2024", "CMD.9.2024.pdf", "2a", "Kementerian Kewangan / MKD",
     "Mass Rapid Transit Corporation Sdn. Bhd.", "KVMRT + RTS Link",
     "margin_label", 55, 86, "margin", "content"),
    ("LKAN 2/2024", "CMD.9.2024.pdf", "2b", "Kementerian Kewangan / MKD",
     "Rangkaian Hotel Seri Malaysia Sdn. Bhd.", "Pengurusan syarikat",
     "margin_label", 87, 118, "margin", "content"),
    ("LKAN 2/2024", "CMD.9.2024.pdf", "3", "KKDW / MARA / MARA Corporation Sdn. Bhd.",
     "MARA Incorporated Sdn. Bhd.", "Pengurusan syarikat",
     "margin_label", 119, 152, "margin", "content"),
    ("LKAN 2/2024", "CMD.9.2024.pdf", "4", "Kementerian Pendidikan Tinggi",
     "International Islamic University Malaysia", "Pengurusan syarikat",
     "margin_label", 153, 188, "margin", "content"),
    ("LKAN 2/2024", "CMD.9.2024.pdf", "5", "Kementerian Sumber Manusia",
     "Pembangunan Sumber Manusia Berhad (PSMB)", "Pengurusan syarikat",
     "margin_label", 189, 230, "margin", "content"),
    ("LKAN 2/2024", "CMD.9.2024.pdf", "6", "Jabatan Perdana Menteri",
     "Institute of Strategic and International Studies (ISIS) Malaysia",
     "Pengurusan syarikat (ringkas)", "margin_label", 233, 252, "margin", "content"),
    ("LKAN 2/2024", "CMD.9.2024.pdf", "7", "Kementerian Kewangan / MKD / Khazanah",
     "i2M Ventures Sdn. Bhd.", "Pengurusan syarikat (ringkas)",
     "margin_label", 253, 272, "margin", "content"),

    ("LKAN 2/2025", "CMD.5.2025.pdf", "1", "MOF; PETRA; KKR; KKDW", "",
     "Pematuhan Terhadap Perolehan Tender Terbuka Pra-Kelayakan Terpilih",
     A, 13, 52, "numbered", 5),
    ("LKAN 2/2025", "CMD.5.2025.pdf", "2", "KKDW; MKD", "FELCRA Berhad",
     "Pengurusan Perolehan Ladang Sawit oleh FELCRA Berhad", A, 53, 82, "numbered", 5),
    ("LKAN 2/2025", "CMD.5.2025.pdf", "3",
     "Kementerian Perdagangan Dalam Negeri dan Kos Sara Hidup", "",
     "Pengurusan Kawalan Harga dan Subsidi Minyak Masak", A, 83, 128, "numbered", 5),
    ("LKAN 2/2025", "CMD.5.2025.pdf", "4", "Kementerian Pertahanan",
     "Tentera Darat Malaysia",
     "Pengurusan Kenderaan Perisai Tentera Darat Malaysia", A, 129, 144, "numbered", 5),
    ("LKAN 2/2025", "CMD.5.2025.pdf", "5", "Kementerian Pendidikan Tinggi",
     "Universiti Kebangsaan Malaysia",
     "Pengurusan Perolehan Bekalan, Perkhidmatan dan Kerja di UKM",
     A, 145, 176, "numbered", 5),

    ("LKAN 1/2026", "CMD.2.2026.pdf", "I.1",
     "KPT; MOSTI; MITI; KPKM; Kementerian Ekonomi; MOF", "",
     "Pengauditan Program Penyelidikan, Pembangunan, Pengkomersialan dan Inovasi "
     "(R&D&C&I)", A, 25, 62, "numbered", 5),
    ("LKAN 1/2026", "CMD.2.2026.pdf", "I.2", "MOSTI; KDN", "MIMOS Berhad",
     "Pengauditan Pematuhan Perbelanjaan Projek Pembangunan MyDigital ID",
     A, 63, 84, "numbered", 5),
    ("LKAN 1/2026", "CMD.2.2026.pdf", "II.3", "",
     "852 badan lain termasuk syarikat diwartakan",
     "Pengauditan Badan Lain Termasuk Syarikat Melalui Sistem e-SelfAudit",
     "register", 85, 130, "register", None),
    ("LKAN 1/2026", "CMD.2.2026.pdf", "III.4", "Jabatan Perdana Menteri / YPB",
     "Pelaburan Hartanah Berhad (PHB)", "Pengurusan syarikat", A, 131, 174, "numbered", 5),

    ("LKAN 3/2025", "CMD.14.2025.pdf", "IV.1", "Kementerian Pengangkutan",
     "Jabatan Pengangkutan Jalan",
     "Kutipan Hasil Penjualan Nombor Pendaftaran Kenderaan", "kaa", 94, 107, "numbered", 2),
    ("LKAN 3/2025", "CMD.14.2025.pdf", "IV.2", "Kementerian Dalam Negeri",
     "Agensi Penguatkuasaan Maritim Malaysia",
     "Penyenggaraan Aset Kapal dan Bot", "kaa", 108, 123, "numbered", 2),
    ("LKAN 3/2025", "CMD.14.2025.pdf", "IV.3", "Kementerian Kewangan", "",
     "Pengurusan Kenderaan Kerajaan di Bawah Perjanjian Konsesi",
     "margin_label", 124, 131, "margin", "all"),
    ("LKAN 3/2025", "CMD.14.2025.pdf", "IV.4", "KKR; NRES/JKPTG",
     "syarikat konsesi lebuh raya",
     "Kutipan Sewa Pajakan Pejabat Pentadbiran Syarikat Konsesi Lebuh Raya "
     "Semenanjung", "margin_label", 132, 141, "margin", "all"),
    ("LKAN 3/2025", "CMD.14.2025.pdf", "V.1", "Kementerian Luar Negeri",
     "ST Canberra, ST Singapura, ST Wellington, Kedutaan Hanoi",
     "Pengauditan Pejabat Perwakilan Malaysia", "kaa", 142, 157, "numbered", 4),
    ("LKAN 3/2025", "CMD.14.2025.pdf", "V.2", "Kementerian Pertahanan",
     "Pejabat Penasihat Pertahanan Canberra/Singapura/Wellington/Hanoi",
     "Pengauditan Pejabat Perwakilan", "margin_label", 158, 167, "margin", "all"),
    ("LKAN 3/2025", "CMD.14.2025.pdf", "VI", "KDN; KKR; ESSCOM; JKR", "",
     "Pengauditan Status Penyiapan Projek Pangkalan Operasi Hadapan (FOB) "
     "Pulau Mabul, Semporna, Sabah", A, 168, 203, "numbered", 5),
]

# ------------------------------------------------------------ text plumbing
NOISE = [
    re.compile(r"\.indd\s"),                            # InDesign slug lines
    re.compile(r"Laporan\s+Ketua(\s*A?\s*udit)?"),      # running footers (+ dupes)
    re.compile(r"^\s*\d{1,3}\s*[-–]\s*\d{1,3}\s*$"),    # printed page "5-12"
    re.compile(r"^\s*\d{1,3}\s+\d{1,3}\s*$"),           # doubled page "154 154"
    re.compile(r"^\s*\d{1,3}\s*$"),                     # bare page number
    re.compile(r"VERSI KABINET|Terkini \d|SEMAKAN KAN|\x03"),   # editorial marks
    re.compile(r"^\s*(?:\S\s){4,}\S\s*$"),              # interleaved letter-spaced dupes
]
MONTHS = ("Januari|Februari|Mac|April|Mei|Jun|Julai|Ogos|September|Oktober|"
          "November|Disember")
RM = re.compile(r"RM[\d][\d.,]*(?:\s*(?:juta|bilion))?")
# master response marker (STRUCTURE_NOTES) + the daripada/bertarikh/antara variants
MB_HEAD = re.compile(
    r"^Maklum\s+[Bb]alas\s+(?:yang\s+[Dd]iterima\s+daripada\s+)?"
    r"(?P<ent>[A-Za-z0-9 .,&()/\-']*?)\s*"
    r"(?:[Yy]ang\s+)?(?:[Dd]iterima(?:\s+masing-masing)?\s+(?:pada|antara)|"
    r"[Bb]ertarikh|[Pp]ada)\s+(?P<tail>.*)$")
DATE_TOK = re.compile(
    r"^(?:\d{1,2}|\d{4}|%s|dan|hingga|serta|pada|masing-masing|antara|,|"
    r"[A-Z][A-Za-z]{1,14},?)[.,]?$" % MONTHS)
PARA_NO = re.compile(r"^(\d{1,3})\.\s")

# margin-volume section vocabulary (joined ALL-CAPS label blocks, longest-first)
SECTIONS = [
    "PENEMUAN TERPERINCI AUDIT", "PENEMUAN AUDIT",
    "PRESTASI AKTIVITI PEMBANGUNAN", "PENGURUSAN AKTIVITI PEMBANGUNAN",
    "PRESTASI AKTIVITI", "PENGURUSAN AKTIVITI", "TADBIR URUS KORPORAT",
    "KEDUDUKAN KEWANGAN", "PRESTASI KEWANGAN", "PENGURUSAN KEWANGAN",
    "HASIL KUTIPAN SEWA PAJAKAN", "SKOP DAN METODOLOGI PENGAUDITAN",
    "OBJEKTIF PENGAUDITAN", "SKOP PENGAUDITAN", "METODOLOGI PENGAUDITAN",
    "RUMUSAN KESELURUHAN AUDIT", "RUMUSAN KESELURUHAN", "RUMUSAN AUDIT", "RUMUSAN",
    "SYOR AUDIT", "LATAR BELAKANG", "FAKTA AUDIT", "PENGENALAN", "OBJEKTIF",
    "SKOP", "METODOLOGI", "PENGAUDITAN",
]
FRONT_BACK = {"LATAR BELAKANG", "FAKTA AUDIT", "PENGENALAN", "OBJEKTIF",
              "OBJEKTIF PENGAUDITAN", "SKOP", "SKOP PENGAUDITAN",
              "SKOP DAN METODOLOGI PENGAUDITAN", "METODOLOGI",
              "METODOLOGI PENGAUDITAN", "PENGAUDITAN", "RUMUSAN", "RUMUSAN AUDIT",
              "RUMUSAN KESELURUHAN", "RUMUSAN KESELURUHAN AUDIT", "SYOR AUDIT"}
CONTENT = {"PENEMUAN AUDIT", "PENEMUAN TERPERINCI AUDIT", "PRESTASI AKTIVITI",
           "PRESTASI AKTIVITI PEMBANGUNAN", "PENGURUSAN AKTIVITI",
           "PENGURUSAN AKTIVITI PEMBANGUNAN", "TADBIR URUS KORPORAT",
           "KEDUDUKAN KEWANGAN", "PRESTASI KEWANGAN", "PENGURUSAN KEWANGAN",
           "HASIL KUTIPAN SEWA PAJAKAN"}


def volume_pages(source_file):
    """Page-aligned text: $LKAN_TEXT_DIR / raw/_text cache / pdftotext fallback."""
    base = source_file[:-4] + ".txt"
    cache = os.path.join(RAW, "_text")
    for d in (os.environ.get("LKAN_TEXT_DIR"), cache):
        if d and os.path.exists(os.path.join(d, base)):
            with open(os.path.join(d, base)) as f:
                return f.read().split("\f")
    os.makedirs(cache, exist_ok=True)
    dest = os.path.join(cache, base)
    subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8",
                    os.path.join(RAW, source_file), dest], check=True)
    with open(dest) as f:
        return f.read().split("\f")


def noisy(line):
    return any(p.search(line) for p in NOISE)


def chapter_lines(pages, start, end):
    """[(pdf_page, raw_line)] for the chapter, page furniture stripped."""
    out = []
    for p in range(start, end + 1):
        for ln in pages[p - 1].split("\n"):
            if ln.strip() and noisy(ln):
                continue
            out.append((p, ln.rstrip("\n")))
    return out


def squash(text):
    return re.sub(r"\s+", " ", text).strip()


def rm_tokens(text):
    """Ordered, deduped RM tokens; trailing punctuation stripped off the number."""
    toks, seen = [], set()
    for m in RM.finditer(squash(text)):
        t = m.group(0)
        t = re.sub(r"[.,]+(\s*(?:juta|bilion))?$", r"\1", t)
        t = re.sub(r"\s+", " ", t)
        if t not in seen:
            seen.add(t)
            toks.append(t)
    return toks


def parse_marker(text):
    """'entity|dates' from a whitespace-squashed response heading, else None."""
    m = MB_HEAD.match(text)
    if not m:
        return None
    if m.group("ent") and m.group("ent").strip().islower():
        return None       # prose ("Maklum balas telah diterima pada ..."),
                          # not a response heading — entities are proper nouns
    dates = []
    for tok in m.group("tail").split():
        if DATE_TOK.match(tok) and (dates or tok[0].isdigit()):
            dates.append(tok)
        elif tok[0].isdigit() and DATE_TOK.match(tok.rstrip(".,")):
            dates.append(tok)
        else:
            break
    while dates and not (dates[-1].rstrip(".,").isdigit()
                         or re.match(r"^(%s)[.,]?$" % MONTHS, dates[-1])):
        dates.pop()          # never end on a dangling 'dan'/'pada'/acronym
    return "%s|%s" % (squash(m.group("ent")), squash(" ".join(dates)).rstrip(".,"))


# ------------------------------------------------- numbered-skeleton chapters
def find_units_numbered(lines, prefix):
    """Finding units P.x./P.x.y. between 'P. PENEMUAN...' and section P+1."""
    start_re = re.compile(r"^%d\.\s+PENEMUAN" % prefix)
    # the closing section is always RUMUSAN/SYOR — a bare `N.` would false-hit
    # numbered table rows (BIL. columns share the paragraph-number shape)
    end_re = re.compile(r"^%d\.\s+(RUMUSAN|SYOR)" % (prefix + 1))
    unit_re = re.compile(r"^%d\.(\d{1,2})\.(?:(\d{1,2})\.)?\s+(\S.*)?$" % prefix)
    lo = hi = None
    for i, (_, ln) in enumerate(lines):
        s = ln.strip()
        if lo is None and start_re.match(s):
            lo = i
        elif lo is not None and end_re.match(s):
            hi = i
            break
    if lo is None:
        raise SystemExit("PENEMUAN section (prefix %d) not found" % prefix)
    hi = hi if hi is not None else len(lines)
    units, cur = [], (0, None)
    for i in range(lo, hi):
        page, ln = lines[i]
        m = unit_re.match(ln.strip())
        if not m:
            continue
        x, y = int(m.group(1)), (int(m.group(2)) if m.group(2) else None)
        ok = ((y is None and x == cur[0] + 1) or
              (y == 1 and x == cur[0]) or
              (y is not None and cur[1] is not None and x == cur[0] and y == cur[1] + 1))
        if not ok:
            continue                      # wrapped cross-reference / table lookalike
        cur = (x, y if y is not None else cur[1] if False else y)
        cur = (x, y)
        path = "%d.%d" % (prefix, x) if y is None else "%d.%d.%d" % (prefix, x, y)
        units.append({"i": i, "page": page, "path": path,
                      "rest": (m.group(3) or "").strip()})
    for k, u in enumerate(units):
        u["end"] = units[k + 1]["i"] if k + 1 < len(units) else hi
    return units


def first_paragraph(lines, i, end, rest):
    """Unit heading = marker-line remainder + wrap lines up to the first blank."""
    parts = [rest]
    for j in range(i + 1, min(i + 40, end)):
        s = lines[j][1].strip()
        if not s or PARA_NO.match(s):
            break
        parts.append(s)
    return squash(" ".join(parts))


def span_features(lines, i, end):
    """(rm, maklum, pendapat) harvested from a unit's line span."""
    text = squash(" ".join(ln for _, ln in lines[i:end]))
    mbs, pend = [], []
    j = i
    while j < end:
        s = lines[j][1].strip()
        if s.startswith("Maklum"):
            # guard only against a DIRECTLY preceding wrapped "Sumber:" table
            # citation — a blank line above means a real response heading
            prev = lines[j - 1][1].strip() if j > i else ""
            para = [s]
            for k in range(j + 1, min(j + 6, end)):
                nxt = lines[k][1].strip()
                if not nxt:
                    break
                para.append(nxt)
            got = parse_marker(squash(" ".join(para)))
            # 'Sumber:' citations wrap onto fresh lines — not response headings
            if got and not (prev.endswith((" dan", ",")) or "Sumber:" in prev):
                mbs.append(got)
        if re.match(r"^Pendapat\s*$|^Pendapat\s{2,}\S", s):
            nxt = next((k for k in range(j + 1, min(j + 3, end))
                        if lines[k][1].strip()), None)
            if nxt is not None and lines[nxt][1].strip().startswith("Audit"):
                box = [re.sub(r"^Pendapat\s*", "", s),
                       re.sub(r"^Audit\s*", "", lines[nxt][1].strip())]
                k = nxt + 1
                while k < end and lines[k][1].strip():
                    box.append(lines[k][1].strip())
                    k += 1
                pend.append(squash(" ".join(box)))
                j = k
        j += 1
    return rm_tokens(text), mbs, pend


def extract_numbered(chap, lines):
    units = find_units_numbered(lines, chap["prefix"])
    rows = []
    for u in units:
        rm, mbs, pend = span_features(lines, u["i"], u["end"])
        rows.append({
            "section_path": u["path"],
            "heading_or_label": first_paragraph(lines, u["i"], u["end"], u["rest"]),
            "pdf_page": u["page"], "rm_amounts": ";".join(rm),
            "maklum_balas": ";".join(mbs), "pendapat_audit": " | ".join(pend),
        })
    return rows


# --------------------------------------------------- margin-label chapters
def margin_indent(lines):
    """Mode indent of the known label anchors = the label column position."""
    anchor = re.compile(r"^(LATAR|PENEMUAN|SYOR|RUMUSAN|OBJEKTIF|SKOP|METODOLOGI|"
                        r"Maklum|Pendapat Audit)")
    cnt = Counter()
    for _, ln in lines:
        st = ln.lstrip()
        if st and anchor.match(st):
            cnt[len(ln) - len(st)] += 1
    if not cnt:
        raise SystemExit("margin chapter: no label anchors found")
    return cnt.most_common(1)[0][0]


def split_margin(lines, mx):
    """Per line: (page, label, body). Split at the nearest pure-body indent."""
    indents = []
    for _, ln in lines:
        st = ln.lstrip()
        indents.append(len(ln) - len(st) if st else None)
    body_mode = Counter(i for i in indents
                        if i is not None and mx + 8 < i < mx + 60)
    fallback = body_mode.most_common(1)[0][0] if body_mode else mx + 18
    out = []
    for k, (page, ln) in enumerate(lines):
        st = ln.lstrip()
        ind = indents[k]
        if not st:
            out.append((page, "", ""))
            continue
        if ind > mx + 6:
            out.append((page, "", st))
            continue
        if ind < mx - 2:                       # dividers/full-width heads: body
            out.append((page, "", st))
            continue
        # a narrow label chunk directly followed by a paragraph number is the
        # strongest cut signal ("PENEMUAN AUDIT 8. Pengauditan ...")
        m = re.match(r"^(\S.{0,22}?)\s+\d{1,3}\.\s", st)
        if m and not re.match(r"^(Sumber|Nota|Jadual|Carta|Rajah|Foto|Gambar)\b",
                              st):
            out.append((page, m.group(1).strip(),
                        st[m.end(1):].strip()))
            continue
        # body column: nearest pure-body indents that cut this line cleanly
        # (label column is at most ~16 chars wide, so candidates below mx+16
        # would truncate multi-word labels)
        cands = []
        for j in list(range(k + 1, k + 9)) + list(range(k - 1, k - 9, -1)):
            if 0 <= j < len(lines) and indents[j] is not None \
                    and mx + 12 < indents[j] < mx + 60 \
                    and indents[j] not in cands:
                cands.append(indents[j])
        bc = None
        for c in sorted(cands) + [fallback]:
            for d in (0, 1, -1, 2, -2, 3, -3):  # columns jitter by a few chars
                t = c + d
                clean = t > mx + 12 and (len(ln) <= t or
                                         (ln[t - 1] == " " and ln[t] != " "))
                # the label column is narrow — a cut that leaves a wide "label"
                # has landed inside the body text, not on its left edge
                if clean and len(ln[:t].rstrip()) - ind <= 24:
                    bc = t
                    break
            if bc is not None:
                break
        if bc is None:
            out.append((page, "", st))         # word straddles the column: no label
            continue
        lab = ln[:bc].strip()
        if re.match(r"^(Sumber|Nota|Jadual|Carta|Rajah|Foto|Gambar)\b", lab):
            out.append((page, "", st))         # table furniture, never a label
            continue
        body = ln[bc:].strip()
        m = re.search(r"(?:^|\s)(\d{1,3}\.)$", lab)
        if m:                                  # para number glued onto the label
            lab = lab[:m.start()].strip()
            body = (m.group(1) + " " + body).strip()
        out.append((page, lab, body))
    return out


def is_caps(text):
    alpha = [c for c in text if c.isalpha()]
    return len(alpha) >= 2 and sum(c.isupper() for c in alpha) / len(alpha) > 0.8


DATE_WORD = re.compile(r"^(?:\d{1,2}|\d{4}|%s|dan|hingga|serta|pada|"
                       r"masing-masing|,)[.,]?$" % MONTHS)


def label_blocks(split):
    """Group contiguous label-bearing lines into classified blocks."""
    blocks, run = [], []
    for k, (page, lab, body) in enumerate(split):
        if lab:
            run.append(k)
        elif run:
            blocks.extend(cut_run(split, run))
            run = []
    if run:
        blocks.extend(cut_run(split, run))
    # a response's date tail can trail below its body (label lines outnumbered
    # by body lines): fold pure-date blocks back into the Maklum block above
    out = []
    for blk in blocks:
        words = " ".join(split[k][1] for k in blk).split()
        if (out and split[out[-1][0]][1].startswith("Maklum")
                and blk[0] - out[-1][-1] <= 5
                and words and all(DATE_WORD.match(w) for w in words)):
            out[-1] = out[-1] + blk
        else:
            out.append(blk)
    return out


SECTION_WORDS = {w for s in SECTIONS for w in s.split()}


def cut_run(split, run):
    """Split one contiguous label run on case change / marker starts / grammar."""
    blocks, cur = [], []
    for k in run:
        lab = split[k][1]
        caps = is_caps(lab)
        new = False
        if cur:
            head = split[cur[0]][1]
            marker = bool(re.match(r"^(Maklum\b|Pendapat\b)", head))
            if re.match(r"^(Maklum\b|Pendapat\s+Audit\b)", lab):
                new = True
            elif marker:
                # a response/opinion label wraps freely (entity acronyms are
                # ALL-CAPS) — it ends where a new numbered paragraph starts,
                # or a genuine section head appears
                if PARA_NO.match(split[k][2] or ""):
                    new = True
                elif caps and lab.split()[0] in SECTION_WORDS:
                    new = True
            elif caps != is_caps(head) and not re.match(r"^[\d(]", lab):
                new = True
        if new:
            blocks.append(cur)
            cur = []
        cur.append(k)
    if cur:
        blocks.append(cur)
    return blocks


def match_sections(lines_):
    """Word-greedy longest-first match of an ALL-CAPS block against SECTIONS."""
    found, pos, words = [], 0, " ".join(lines_).split()
    while pos < len(words):
        hit = None
        for sec in SECTIONS:
            sw = sec.split()
            if [w.upper() for w in words[pos:pos + len(sw)]] == sw:
                if hit is None or len(sw) > len(hit.split()):
                    hit = sec
        if hit:
            found.append(hit)
            pos += len(hit.split())
        else:
            pos += 1
    return found


def para_chain(split):
    """{line_index: para_no} for the audit's continuous paragraph numbering.

    Margin chapters number paragraphs 1..N straight through, so only the exact
    successor of the previous accepted number is a paragraph start — numbered
    table rows (BIL. columns) restart at 1 and are rejected. The chain arms at
    the LATAR BELAKANG label: the FAKTA AUDIT cover sheet carries its own
    numbered digest that must not consume 1..k first.
    """
    ok, expected, armed = {}, 1, False
    for k, (_, lab, body) in enumerate(split):
        if not armed and lab.startswith("LATAR"):
            armed = True
        if not armed:
            continue
        m = PARA_NO.match(body or "")
        # a labelled line is a paragraph start by construction; for label-less
        # lines, bullets — or column gaps with numeric cells — betray numbered
        # table rows (heavy justification alone is normal in narrow columns)
        rest = body[m.end():] if m else ""
        rowish = m and not lab and ("•" in body or (
            re.search(r" {7,}", body)
            and re.search(r"(?:^|\s)[\d(][\d.,%()]*(?:\s|$)", rest)))
        if m and int(m.group(1)) in (expected, expected + 1) and not rowish:
            got = int(m.group(1))       # +1: tolerate a paragraph lost to a
            ok[k] = got                 # chart/graphic text layer
            expected = got + 1
    return ok


def extract_margin(chap, lines):
    mx = margin_indent(lines)
    split = split_margin(lines, mx)
    blocks = label_blocks(split)
    paras_at = para_chain(split)
    include = CONTENT if chap["scope"] == "content" else None
    section, rows, open_row = None, [], None

    def close(open_row, upto):
        if open_row is None:
            return
        i, page, label = open_row
        span = split[i:upto]
        text = squash(" ".join((l + " " + b).strip() for _, l, b in span))
        paras = [paras_at[k] for k in range(i, upto) if k in paras_at]
        mbs, pend = [], []
        for blk in [b for b in blocks if i <= b[0] < upto]:
            head = split[blk[0]][1]
            lab_text = squash(" ".join(split[k][1] for k in blk))
            if head.startswith("Maklum"):
                got = parse_marker(lab_text) or (
                    squash(re.sub(r"^Maklum\s+[Bb]alas", "", lab_text)) + "|")
                mbs.append(got)
            elif head.startswith("Pendapat"):
                # the box body: the block's own body lines, then pure-body
                # lines up to the first blank/labelled line
                body = [b for _, _, b in (split[k] for k in blk)]
                for k in range(blk[-1] + 1, upto):
                    _, lab2, b2 = split[k]
                    if lab2 or not b2:
                        break
                    body.append(b2)
                pend.append(squash(" ".join(body)))
        if not paras and not mbs and not pend:
            return                      # chapter-head / group-header debris
        rng = ("%d-%d" % (min(paras), max(paras)) if len(set(paras)) > 1
               else str(paras[0]) if paras else "")
        rows.append({"section_path": rng, "heading_or_label": label,
                     "pdf_page": page, "rm_amounts": ";".join(rm_tokens(text)),
                     "maklum_balas": ";".join(mbs),
                     "pendapat_audit": " | ".join(pend)})

    for blk in blocks:
        head = split[blk[0]][1]
        if is_caps(head):
            secs = match_sections([split[k][1] for k in blk])
            if secs:
                close(open_row, blk[0])
                open_row = None
                section = secs[-1]
                if section in CONTENT:
                    # content sections open their own unit: some carry
                    # paragraphs (and responses) before any sub-topic label —
                    # empty spans are dropped again inside close()
                    open_row = (blk[0], split[blk[0]][0], section)
            continue
        if head.startswith("Maklum") or head.startswith("Pendapat"):
            continue                            # harvested inside close()
        opens = any(k in paras_at for k in blk)
        if not opens and not split[blk[0]][2]:  # label-only: para may start below
            opens = any(k in paras_at
                        for k in range(blk[-1] + 1, blk[-1] + 3))
        if not opens or not re.match(r"[A-Z0-9(]", head):
            continue                            # labels are Title Case
        # scope "all" (CMD.14 margin chapters): no PENEMUAN divider exists, and
        # the topical labels open while LATAR BELAKANG is still the last section
        # head — so only the true front/back sections excise topics there.
        wanted = (section in include) if include is not None else \
            (section is None or section not in FRONT_BACK
             or section == "LATAR BELAKANG")
        if not wanted:
            continue
        close(open_row, blk[0])
        label = squash(" ".join(split[k][1] for k in blk))
        open_row = (blk[0], split[blk[0]][0], label)
    close(open_row, len(split))
    return rows


# ----------------------------------------------------------------- driver
STOP = {"pengurusan", "pengauditan", "projek", "program", "malaysia", "negara",
        "kementerian", "jabatan", "kerajaan", "bawah", "melalui", "termasuk",
        "syarikat", "dengan"}


def crosscheck(chap, pages):
    """Chapter-head words must appear within pdf_start..pdf_start+2."""
    window = " ".join(pages[p - 1] for p in
                      range(chap["pdf_start"], min(chap["pdf_start"] + 3,
                                                   len(pages) + 1))).lower()
    window = re.sub(r"\s+", " ", window)

    def hits(text):
        words = [re.sub(r"[^\w-]", "", w).lower() for w in text.split()]
        words = [w for w in words if len(w) >= 3 and w not in STOP]
        return (sum(w in window for w in words), len(words))

    for field in ("topic_bm", "entity_bm", "ministry_bm"):
        got, n = hits(chap[field])
        if n and got / n >= 0.6:
            return
    raise SystemExit("cross-check FAILED: %s %s chapter head not on pdf %d..%d"
                     % (chap["source_file"], chap["chapter_id"],
                        chap["pdf_start"], chap["pdf_start"] + 2))


def main():
    keys = ("report", "source_file", "chapter_id", "ministry_bm", "entity_bm",
            "topic_bm", "audit_style", "pdf_start", "pdf_end", "parse", "extra")
    chaps = [dict(zip(keys, row)) for row in INVENTORY]
    for c in chaps:
        c["prefix" if c["parse"] == "numbered" else "scope"] = c.pop("extra")

    texts, findings = {}, []
    for c in chaps:
        pages = texts.setdefault(c["source_file"],
                                 volume_pages(c["source_file"]))
        crosscheck(c, pages)
        if c["parse"] == "register":
            continue
        lines = chapter_lines(pages, c["pdf_start"], c["pdf_end"])
        rows = (extract_numbered if c["parse"] == "numbered"
                else extract_margin)(c, lines)
        for r in rows:
            r.update(report=c["report"], source_file=c["source_file"],
                     chapter_id=c["chapter_id"])
        findings.extend(rows)
        print("%s ch %-5s %-12s -> %3d units" %
              (c["source_file"], c["chapter_id"], c["audit_style"], len(rows)))

    acols = ["report", "source_file", "chapter_id", "ministry_bm", "entity_bm",
             "topic_bm", "audit_style", "pdf_start", "pdf_end"]
    with open(os.path.join(DATA, "fact_lkan_audits.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=acols, extrasaction="ignore")
        w.writeheader()
        w.writerows(chaps)
    fcols = ["report", "source_file", "chapter_id", "section_path",
             "heading_or_label", "pdf_page", "rm_amounts", "maklum_balas",
             "pendapat_audit"]
    with open(os.path.join(DATA, "fact_lkan_findings.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fcols)
        w.writeheader()
        w.writerows(findings)
    print("%d audits, %d finding units -> data/fact_lkan_*.csv"
          % (len(chaps), len(findings)))


if __name__ == "__main__":
    main()
