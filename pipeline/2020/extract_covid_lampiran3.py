#!/usr/bin/env python3
"""Extract Lampiran 3: Penyata Perbelanjaan Kumpulan Wang COVID-19 (PKKP 2020, pdf 250-251).

FIRST year of the fund (established 26.10.2020 under Akta 830). The register
shape therefore differs from 2022:
  - columns printed: Siling Keseluruhan | Peruntukan | Tambahan | Tarik |
    Virement Tambah/(Kurang) | Peruntukan Dipinda | Perbelanjaan Sebenar |
    Lebihan/(Kurangan) Belanja | Perbelanjaan Terkumpul Sehingga 31.12.2020 | %
  - there is NO prior-year cumulative column (fund did not exist in 2019), and
    the mid-year COVID budget recast adds Tambahan and Tarik columns that the
    2022 volume does not print. Documented schema difference vs warehouse2022.

Text-layer pathology: pdf 250 and 251 hold IDENTICAL char content -- the full
wide table is drawn TWICE per page (two x-shifted copies for the two crop
views), interleaving glyphs in naive extraction. The content stream draws the
copies sequentially, so the first body segment (between the large upward top
jumps in stream order) is one complete clean copy; this parses that copy only.
"""
import csv
import re
import pdfplumber

YEAR = 2020
SRC = "2020_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2020/fact_covid_fund_detail.csv"
NUMTOK = re.compile(r"^\*?\(?[\d,]+(?:\.\d+)?\)?$|^\*?[–—-]$")


def parse_amount(tok):
    tok = tok.strip().replace("*", "")
    if tok in {"–", "-", "—", ""}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()").replace(",", "")
    v = float(tok)
    return -v if neg else v


pdf = pdfplumber.open("/home/claude/pkkp/work/2020/2020.pdf")
pg = pdf.pages[249]  # pdf 250
chars = pg.chars
# stream-order segmentation: copy boundaries are large upward jumps in 'top'
splits = [0] + [i for i in range(1, len(chars)) if chars[i - 1]["top"] - chars[i]["top"] > 300] + [len(chars)]
segments = [(splits[i], splits[i + 1]) for i in range(len(splits) - 1)]
body = None
for a, b in segments:
    txt = "".join(c["text"] for c in chars[a:b])
    if "00100" in txt:
        body = (a, b)
        break
assert body, "clean copy segment not found"
chars = chars[body[0]:body[1]]

# rebuild words from the clean copy (chars are in drawing order within a run)
ws = []
cur = None
for ch in chars:
    if ch["text"].strip() == "":
        cur = None
        continue
    if cur and abs(ch["top"] - cur["top"]) < 0.2 and -0.5 < ch["x0"] - cur["x1"] < 1.2:
        cur["text"] += ch["text"]
        cur["x1"] = ch["x1"]
    else:
        cur = dict(text=ch["text"], top=ch["top"], x0=ch["x0"], x1=ch["x1"])
        ws.append(cur)

rows_by_top = []
for w in sorted(ws, key=lambda x: x["top"]):
    if rows_by_top and w["top"] - rows_by_top[-1][0] < 0.3:
        rows_by_top[-1][1].append(w)
    else:
        rows_by_top.append((w["top"], [w]))

entries = []   # {'code','name','rt','toks':[(text,x1)...]}
for top, wlist in rows_by_top:
    wlist = sorted(wlist, key=lambda x: x["x0"])
    texts = [w["text"] for w in wlist]
    line = " ".join(texts)
    if top < 195:      # title/header band
        continue
    if re.match(r"^[\s,.]*$", line.replace(" ", "")):
        continue
    nums = []
    k = len(texts)
    while k > 0 and NUMTOK.match(texts[k - 1]):
        nums.insert(0, (texts[k - 1], wlist[k - 1]["x1"]))
        k -= 1
    head = texts[:k]
    # a project whose name wraps entirely to the next line leaves the 5-digit
    # code as the row's first 'numeric' token (e.g. 00900 Dana jaminan
    # makanan); recover it from the code column x-position
    if not head and nums and re.match(r"^\d{5}$", nums[0][0]) and nums[0][1] < 110:
        head = [nums[0][0]]
        nums = nums[1:]
    is_proj = head and re.match(r"^\d{5}$", head[0])
    label = " ".join(head[1:] if is_proj else head).strip()
    if is_proj:
        entries.append({"code": head[0], "name": label, "rt": "project", "toks": nums})
    elif re.sub(r"(.)\1", r"\1", label.replace(" ", "")).startswith(("JumlahKeseluruhan", "JumlahKeseluruhan".replace("h","hh"))) or \
            re.sub(r"(.)\1", r"\1", re.sub(r"(.)\1", r"\1", label.replace(" ", ""))).startswith("JumlahKeseluruhan"):
        entries.append({"code": None, "name": "Jumlah Keseluruhan", "rt": "total", "toks": nums})
    elif label and not nums and entries:
        # wrapped continuation of the previous project's name
        entries[-1]["name"] = (entries[-1]["name"] + " " + label).strip()

# column x1 anchors from full 10-token rows
full10 = [e["toks"] for e in entries if len(e["toks"]) == 10]
assert full10, "no full 10-column row found"
anchors = [sorted(t[i][1] for t in full10)[len(full10) // 2] for i in range(10)]

COLS = ["siling_keseluruhan_rm", "peruntukan_rm", "tambahan_rm", "tarik_rm",
        "virement_rm", "peruntukan_dipinda_rm", "sebenar_rm", "varian_rm",
        "terkumpul_hingga_2020_rm", "prestasi_pct"]

rows = []
problems = []
for e in entries:
    vals = [0.0] * 10
    ok = True
    prev = -1
    for text, x1 in e["toks"]:
        ci = min(range(10), key=lambda i: abs(anchors[i] - x1))
        if abs(anchors[ci] - x1) > 20 or ci <= prev:
            ok = False
            break
        vals[ci] = parse_amount(text)
        prev = ci
    if not ok:
        problems.append(f"column assignment failed: {e['rt']} {e['name'][:60]} toks={[t for t,_ in e['toks']]}")
        continue
    foot = any("*" in t for t, _ in e["toks"])
    # write order follows the warehouse2022 convention (prestasi_pct before the
    # cumulative column); parse order above follows the printed column order
    vals_out = vals[:8] + [vals[9], vals[8]]
    rows.append([e["code"], e["name"], e["rt"], YEAR] + vals_out + [foot, SRC, 250, 234,
                "Lampiran 3 Penyata Perbelanjaan Kumpulan Wang COVID-19"])

OUTCOLS = COLS[:8] + [COLS[9], COLS[8]]
with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["projek_code", "name_bm", "row_type", "year"] + OUTCOLS +
                ["has_footnote", "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(rows)

print(f"fact_covid_fund_detail.csv: {len(rows)} rows")
for p in problems:
    print("!!", p)
# self-checks (reported, never corrected)
tot = [r for r in rows if r[2] == "total"][0]
for i, col in enumerate(OUTCOLS):
    if col == "prestasi_pct":
        continue
    det = sum(r[4 + i] for r in rows if r[2] == "project")
    print(f"{col}: details {det:,.2f} vs total {tot[4+i]:,.2f} diff {det-tot[4+i]:,.2f}")
idbad = [r for r in rows if r[2] == "project" and abs(r[5] + r[6] + r[7] + r[8] - r[9]) > 1]
print(f"per-row identity peruntukan+tambahan+tarik+virement=dipinda violations: {len(idbad)}")
idbad2 = [r for r in rows if r[2] == "project" and abs(r[9] - r[10] - r[11]) > 1]
print(f"per-row identity dipinda-sebenar=varian violations: {len(idbad2)}")
idbad3 = [r for r in rows if r[2] == "project" and abs(r[10] - r[13]) > 0.005]
print(f"per-row identity sebenar=terkumpul2020 (first fund year) violations: {len(idbad3)}")
for r in idbad + idbad2 + idbad3:
    print("  !!", r[0], r[1][:50], r[4:14])
