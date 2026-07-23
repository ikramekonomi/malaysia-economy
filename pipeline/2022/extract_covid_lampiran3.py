#!/usr/bin/env python3
"""Extract Lampiran 3: Penyata Perbelanjaan Kumpulan Wang COVID-19 (PKKP 2022, pdf 232-233).

LIVE table in the 2022 volume (fund active; RM30,979,119,546 spent in 2022; the fund
wound up 31.12.2022). Unlike 2023 (a genuine two-page spread), the 2022 PDF prints the
lampiran as ONE wide table whose full word layer is present on pdf page 232 (page 233
repeats the same words shifted left — a print-crop duplicate). So this parses page 232
alone: each program row = 5-digit code + name (may wrap around the numbers line) +
9 numeric columns [Siling Keseluruhan | Perbelanjaan sehingga 31.12.2021 | Peruntukan |
Viremen Tambah/(Kurang) | Peruntukan Dipinda | Perbelanjaan Sebenar |
Lebihan/(Kurangan) Belanja | Prestasi % | Perbelanjaan Terkumpul Sehingga 31.12.2022].
Column names follow the 2023 file's convention (printed cut-off dates), so the two
cumulative columns are terkumpul_hingga_2021_rm / terkumpul_hingga_2022_rm here.
"""
import csv
import re
import pdfplumber

YEAR = 2022
SRC = "2022_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2022/fact_covid_fund_detail.csv"
NUMTOK = re.compile(r"^\*?\(?[\d,]+(?:\.\d+)?\)?$|^\*?[–—-]$")


def parse_amount(tok):
    tok = tok.strip().replace("*", "")
    if tok in {"–", "-", "—", ""}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()").replace(",", "")
    v = float(tok)
    return -v if neg else v


def merge_split_numbers(ws):
    out = []
    for wd in ws:
        if out:
            prev = out[-1]
            gap = wd["x0"] - prev["x1"]
            # merge kerned fragments: '2' + ',342,133,000.00', '(' + '1,400,000,000.00)'
            if (gap < 6.0 and re.match(r"^[\d,().*]+$", prev["text"])
                    and re.match(r"^[\d,().*%]+$", wd["text"])
                    and not prev["text"].endswith(")")
                    and not (NUMTOK.match(prev["text"]) and NUMTOK.match(wd["text"])
                             and "," in prev["text"] and "," in wd["text"])):
                prev["text"] = prev["text"] + wd["text"]
                prev["x1"] = wd["x1"]
                continue
        out.append(dict(wd))
    return out


def lines_of(page_obj):
    words = sorted(page_obj.extract_words(x_tolerance=1.5, y_tolerance=2), key=lambda w: w["top"])
    rows_, cur, cur_top = [], [], None
    for wd in words:
        if cur and wd["top"] - cur_top > 2.5:
            rows_.append(cur)
            cur = []
        if not cur:
            cur_top = wd["top"]
        cur.append(wd)
    if cur:
        rows_.append(cur)
    return [(sorted(ws, key=lambda x: x["x0"])[0]["top"], merge_split_numbers(sorted(ws, key=lambda x: x["x0"]))) for ws in rows_]


entries = []   # {'code','name','rt','vals' or None}
with pdfplumber.open("/home/claude/pkkp/work/2022/2022.pdf") as pdf:
    pg = pdf.pages[231]   # pdf 232
    for top, ws in lines_of(pg):
        texts = [w["text"] for w in ws]
        line = " ".join(texts)
        if re.match(r"^(Penyata Perbelanjaan|bagi tahun|Maksud Perbelanjaan|Siling|sehingga|RM( |$)|PENYATA KEWANGAN|LAMPIRAN|Teks |\d+$|Peruntukan( |$)|Tambah/|Perbelanjaan$|%$)", line):
            continue
        nums = []
        k = len(texts)
        while k > 0 and NUMTOK.match(texts[k - 1]):
            nums.insert(0, texts[k - 1])
            k -= 1
        head = texts[:k]
        is_proj = head and re.match(r"^\d{5}$", head[0])
        label = " ".join(head[1:] if is_proj else head).strip()
        if is_proj:
            entries.append({"code": head[0], "name": label, "rt": "project",
                            "vals": nums if len(nums) == 9 else None})
        elif label.startswith("Jumlah"):
            entries.append({"code": None, "name": label, "rt": "total",
                            "vals": nums if len(nums) == 9 else None})
        elif not head and len(nums) == 9 and entries and entries[-1]["vals"] is None:
            entries[-1]["vals"] = nums
        elif label and not nums and entries and entries[-1]["rt"] == "project":
            entries[-1]["name"] += " " + label

rows = []
problems = []
for e in entries:
    if e["vals"] is None:
        problems.append(f"row without 9 values: {e['rt']} {e['name'][:60]}")
        continue
    foot = any("*" in t for t in e["vals"])
    siling, prior, peruntukan, virement, dipinda, sebenar, varian, pct, terkumpul = [parse_amount(t) for t in e["vals"]]
    rows.append([
        e["code"], e["name"], e["rt"], YEAR,
        siling, prior, peruntukan, virement, dipinda, sebenar, varian, pct, terkumpul, foot,
        SRC, 232, 220, "Lampiran 3 Penyata Perbelanjaan Kumpulan Wang COVID-19",
    ])

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["projek_code", "name_bm", "row_type", "year",
                 "siling_keseluruhan_rm", "terkumpul_hingga_2021_rm",
                 "peruntukan_rm", "virement_rm", "peruntukan_dipinda_rm", "sebenar_rm",
                 "varian_rm", "prestasi_pct", "terkumpul_hingga_2022_rm", "has_footnote",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(rows)

print(f"fact_covid_fund_detail.csv: {len(rows)} rows")
for p in problems:
    print("!!", p)
# self-checks (reported, never corrected)
det_s = sum(r[4] for r in rows if r[2] == "project")
det_p = sum(r[5] for r in rows if r[2] == "project")
det_x = sum(r[9] for r in rows if r[2] == "project")
det_t = sum(r[12] for r in rows if r[2] == "project")
tot = [r for r in rows if r[2] == "total"][0]
print(f"siling: details {det_s:,.2f} vs total {tot[4]:,.2f} diff {det_s-tot[4]:,.2f}")
print(f"terkumpul2021: details {det_p:,.2f} vs total {tot[5]:,.2f} diff {det_p-tot[5]:,.2f}")
print(f"sebenar2022: details {det_x:,.2f} vs total {tot[9]:,.2f} diff {det_x-tot[9]:,.2f}")
print(f"terkumpul2022: details {det_t:,.2f} vs total {tot[12]:,.2f} diff {det_t-tot[12]:,.2f}")
idbad = [r for r in rows if r[2] == "project" and abs(r[5] + r[9] - r[12]) > 1]
print(f"per-row identity prior+sebenar=terkumpul violations: {len(idbad)}")
for r in idbad:
    print("  !!", r[0], r[1][:50], r[5], r[9], r[12])
