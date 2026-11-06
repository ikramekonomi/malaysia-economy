#!/usr/bin/env python3
"""The audit inventory of every LKAN activities/companies volume, read from its contents pages (data/lkan_toc/).

  python3 sources/audit-negara/pipeline/lkan_inventory.py -> sources/audit-negara/data/fact_lkan_audit_inventory.csv

One row per audit the contents pages list: the volume, the part (BAHAGIAN) it sits in, the audited body as printed
(the capitals line), the topic (the mixed-case lines), a company or agency printed under the body ('- X Sdn. Bhd.'),
and the printed page where the audit starts. Nothing is matched or classified here: the body is linked to an
entity (D33) and the topic to the declared taxonomy (meta/audit_topic_taxonomy.csv) in core.

How a contents page is read (the three layouts in the volumes: the page number at the left (2015-2018), at the left
behind a bar ('140  |', 2019-2025), or at the right (2026)):
  * a numbered line is an entry; every other line with text is either a heading or a line of an entry;
  * a heading: 'BAHAGIAN ...', the capitals lines straight after it (the part's title), and capitals lines naming a
    kind of part (AKTIVITI ..., PENGURUSAN SYARIKAT ..., PENYATA KEWANGAN ..., RINGKASAN LAPORAN, ...);
  * an entry's lines are the text on its number's line and the unnumbered lines nearest to it (lines above and below
    a number belong to the closer number; a heading or a numbered line stops them);
  * an audit is an entry in a part whose title names activities (AKTIVITI), companies (SYARIKAT) or statutory bodies
    (BADAN BERKANUN), or, in volumes without parts, an entry after such a heading, except the front and back matter
    (Pendahuluan, Rumusan, Penutup, Status Tindakan, ...). The RINGKASAN / INTI SARI digest repeats the audits and
    is skipped.
"""
import csv
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
TOC = os.path.join(SRC, "data", "lkan_toc")
OUT = os.path.join(SRC, "data", "fact_lkan_audit_inventory.csv")
FIELDS = ["report", "scope", "file_name", "part", "body_bm", "topic_bm", "sub_entity_bm", "entry_text",
          "printed_page", "toc_pdf_page"]
NUM_LEFT = re.compile(r"^(\s*)(\d{1,4}|[ivxlc]{1,6})(?:\s*\|\s*|\s{2,})(.*)$")
NUM_ONLY = re.compile(r"^\s*(\d{1,4}|[ivxlc]{1,6})\s*\|?\s*$")
NUM_RIGHT = re.compile(r"^(\s*)(\S.*?[A-Za-z)].*?)\s{3,}(\d{1,3})\s*$")
BAHAGIAN = re.compile(r"^BAHAGIAN\s+[IVXL]+\b")  # a part; 'BAHAGIAN TEKNOLOGI MAKLUMAT' is a division of a body
PART_KIND = re.compile(r"^(BAHAGIAN\s+[IVXL]+\b|AKTIVITI\b|PENGURUSAN SYARIKAT|PENGURUSAN AKTIVITI|BADAN BERKANUN|PENGESAHAN\b|"
                       r"ANALISIS\b|PENYATA KEWANGAN|PENYERAHAN|RANCANGAN PEMBANGUNAN|PERKARA AM|INTI SARI|"
                       r"RINGKASAN LAPORAN|KANDUNGAN|LAPORAN KETUA AUDIT)")
COMPANY = re.compile(r"\b(Sdn\.?\s*Bhd|Berhad|Bhd\.)", re.I)
AUDIT_PART = re.compile(r"AKTIVITI|SYARIKAT|BADAN BERKANUN", re.I)
SKIP_PART = re.compile(r"RINGKASAN|INTI SARI|PERKARA AM", re.I)
MATTER = re.compile(r"^(Pendahuluan|Rumusan|Penutup|PENUTUP|PENDAHULUAN|Status Tindakan|Lampiran|Objektif|Skop|"
                    r"Syor|Akronim|AKRONIM|Latar Belakang|Kandungan|Pembentangan Laporan|Kedudukan)", re.I)
NOISE = re.compile(r"\.indd\b|^\s*(v|vi|vii|viii|ix|x|xi|iii|iv)?\s*\|?\s*Kandungan\s*$|LKAN NEGERI|│", re.I)


def caps(t):
    letters = [c for c in t if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) / len(letters) > 0.8


def parse_page(text):
    """[(kind, line_no, text, number)] with kind heading / entry / line."""
    out = []
    head_indent = None  # indent of the heading just above, while its lines continue without a blank
    for i, raw in enumerate(text.splitlines()):
        if not raw.strip():
            head_indent = None
            continue
        if NOISE.search(raw):
            continue
        s = raw.strip()
        ind = len(raw) - len(raw.lstrip())
        m = NUM_LEFT.match(raw)
        n = NUM_ONLY.match(raw)
        r = NUM_RIGHT.match(raw)
        if n:
            out.append(("entry", i, "", n.group(1)))
            head_indent = None
        elif m and m.group(3) and caps(m.group(3)) and PART_KIND.match(m.group(3).strip()):
            out.append(("heading", i, m.group(3).strip(), None))  # 'xi    INTI SARI LAPORAN'
            head_indent = None
        elif m and m.group(3):
            out.append(("entry", i, m.group(3).strip(), m.group(2)))
            head_indent = None
        elif r and not PART_KIND.match(r.group(2).strip()):
            out.append(("entry", i, r.group(2).strip(), r.group(3)))
            head_indent = None
        elif BAHAGIAN.match(s) or (caps(s) and PART_KIND.match(s)) or (
                caps(s) and head_indent is not None and abs(ind - head_indent) <= 1):
            out.append(("heading", i, s, None))
            head_indent = ind
        else:
            out.append(("line", i, s, None))
            head_indent = None
    return out


def entries(items):
    """Attach each unnumbered line to the closer numbered line, never across a heading."""
    nums = [k for k, it in enumerate(items) if it[0] == "entry"]
    groups = {k: {"above": [], "on": items[k][2], "below": []} for k in nums}
    for k, it in enumerate(items):
        if it[0] != "line":
            continue
        prev = next((j for j in range(k - 1, -1, -1) if items[j][0] != "line"), None)
        nxt = next((j for j in range(k + 1, len(items)) if items[j][0] != "line"), None)
        cand = []
        if prev is not None and items[prev][0] == "entry":
            cand.append((it[1] - items[prev][1], 0, prev, "below"))
        if nxt is not None and items[nxt][0] == "entry":
            cand.append((items[nxt][1] - it[1], 1, nxt, "above"))
        if not cand:
            continue
        _, _, j, where = min(cand)
        groups[j][where].append(it[2])
    return [(k, groups[k]) for k in nums]


def main():
    rows = []
    for fn in sorted(os.listdir(TOC)):
        if not fn.endswith(".txt"):
            continue
        text = open(os.path.join(TOC, fn), encoding="utf-8").read()
        head = text.splitlines()[0].lstrip("# ").split(" | ")
        report, scope = (head + ["", ""])[:2]
        pages = re.split(r"^=== pdf page (\d+) ===$", text, flags=re.M)
        part = ""
        seen = set()
        for pno, body in zip(pages[1::2], pages[2::2]):
            if not re.search(r"KANDUNGAN|Kandungan|CONTENTS", body) and not part:
                continue
            items = parse_page(body)
            heads = [(it[1], it[2]) for it in items if it[0] == "heading"]
            for k, g in entries(items):
                line_no = items[k][1]
                hs = [h for i, h in heads if i < line_no]
                # the part: the last BAHAGIAN line and the headings after it; else the last kind-of-part heading
                if hs:
                    last_b = max((i for i, h in enumerate(hs) if BAHAGIAN.match(h)), default=None)
                    if last_b is not None:
                        part = " ".join(hs[last_b:])
                    else:  # no parts: the last kind-of-part heading and the heading lines after it
                        last_k = max((i for i, h in enumerate(hs) if PART_KIND.match(h)), default=len(hs) - 1)
                        part = " ".join(hs[last_k:])
                lines = [x.lstrip("| ").strip() for x in g["above"] + ([g["on"]] if g["on"] else []) + g["below"]]
                lines = [x for x in lines if x]
                text_all = " ".join(lines).strip()
                if not text_all or not AUDIT_PART.search(part) or SKIP_PART.search(part) or MATTER.match(text_all):
                    continue
                body_l = [x for x in lines if caps(x) and not x.startswith("-")]
                sub = [x.lstrip("- ").strip() for x in lines if x.startswith("-")]
                topic = [re.sub(r"^\d+\.\s*", "", x) for x in lines if not caps(x) and not x.startswith("-")]
                if not sub and topic and COMPANY.search(topic[-1]):
                    sub = [topic.pop()]  # a company audit names the company where a topic would be
                key = (items[k][3], text_all)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(dict(report=report, scope=scope, file_name=fn.replace(".txt", ".pdf"), part=part,
                                 body_bm=" ".join(body_l), topic_bm=" ".join(topic), sub_entity_bm="; ".join(sub),
                                 entry_text=text_all, printed_page=items[k][3], toc_pdf_page=pno))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"audit inventory: {len(rows)} audits in {len({r['file_name'] for r in rows})} volumes",
          dict(Counter(r["scope"].split(":")[0] for r in rows)))


if __name__ == "__main__":
    main()
