#!/usr/bin/env python3
"""Extract Lampiran 3: Penyata Perbelanjaan Kumpulan Wang COVID-19 (PKKP 2023, pdf 234-235).

NEW table in the 2023 volume — no 2024 counterpart (the fund was wound down on
31.12.2022 and this is its final cumulative statement; the 2024 volume dropped it).
Two-page spread like Lampiran 2: left page = 5-digit program code + name (wraps) +
[Siling Keseluruhan | Perbelanjaan sehingga 31.12.2022]; right page (same y) =
[Virement Tambah/(Kurang) | Peruntukan Dipinda | Perbelanjaan Sebenar |
 Lebihan/(Kurangan) Belanja | Prestasi % | Perbelanjaan Terkumpul Sehingga 31.12.2023].
Output: fact_covid_fund_detail.csv (2023-only file, reported as a format difference).
"""
import csv
import re
import pdfplumber

YEAR = 2023
SRC = "2023_Penyata_Kewangan_Kerajaan_Persekutuan.pdf"
OUT = "/home/claude/pkkp/warehouse2023/fact_covid_fund_detail.csv"
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
            if (gap < 4.0 and re.match(r"^[\d,().*]+$", prev["text"])
                    and re.match(r"^[\d,().*%]+$", wd["text"])):
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


left_entries = []   # {'code','name','rt','y','siling','prior'}
with pdfplumber.open("/home/claude/pkkp/work/2023/2023.pdf") as pdf:
    # ---- LEFT page (pdf 234) ----
    pg = pdf.pages[233]
    pending_nums = None   # numbers seen before their label completes (wrapped rows)
    for top, ws in lines_of(pg):
        texts = [w["text"] for w in ws]
        line = " ".join(texts)
        if re.match(r"^(Penyata Perbelanjaan|bagi tahun|Maksud Perbelanjaan|Siling|sehingga|RM$|PENYATA KEWANGAN|LAMPIRAN|\d+$)", line):
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
            e = {"code": head[0], "name": label, "rt": "project", "y": top,
                 "siling": None, "prior": None}
            if len(nums) >= 2:
                e["siling"], e["prior"] = parse_amount(nums[-2]), parse_amount(nums[-1])
            left_entries.append(e)
        elif label.startswith("Jumlah"):
            e = {"code": None, "name": label, "rt": "total", "y": top,
                 "siling": None, "prior": None}
            if len(nums) >= 2:
                e["siling"], e["prior"] = parse_amount(nums[-2]), parse_amount(nums[-1])
            left_entries.append(e)
        elif not head and len(nums) >= 2 and left_entries:
            # numbers-only line belonging to the nearest entry without values
            tgt = min((e for e in left_entries if e["siling"] is None),
                      key=lambda e: abs(e["y"] - top), default=None)
            if tgt is not None and abs(tgt["y"] - top) < 20:
                tgt["siling"], tgt["prior"] = parse_amount(nums[-2]), parse_amount(nums[-1])
                tgt["y"] = (tgt["y"] + top) / 2  # centre y for right-page pairing
        elif label and not nums and left_entries and left_entries[-1]["rt"] == "project":
            left_entries[-1]["name"] += " " + label
    # ---- RIGHT page (pdf 235) ----
    pg = pdf.pages[234]
    numeric_lines = []
    for top, ws in lines_of(pg):
        texts = [w["text"] for w in ws]
        if len(texts) >= 5 and all(NUMTOK.match(t) or t == "%" for t in texts):
            numeric_lines.append({"y": top, "toks": [t for t in texts if t != "%"], "used": False})

rows = []
problems = []
for e in left_entries:
    best, bestd = None, 8.0
    for nl in numeric_lines:
        if nl["used"]:
            continue
        d = abs(nl["y"] - e["y"])
        if d < bestd:
            best, bestd = nl, d
    if best is None:
        problems.append(f"no right-page match: {e['rt']} {e['name'][:50]} y={e['y']:.0f}")
        continue
    best["used"] = True
    vals = [parse_amount(t) for t in best["toks"]]
    if len(vals) != 7:
        problems.append(f"odd col count {len(vals)}: {e['name'][:50]}")
        continue
    peruntukan, virement, dipinda, sebenar, varian, pct, terkumpul = vals
    rows.append([
        e["code"], e["name"], e["rt"], YEAR,
        e["siling"], e["prior"], peruntukan, virement, dipinda, sebenar, varian, pct, terkumpul, False,
        SRC, 234, 222, "Lampiran 3 Penyata Perbelanjaan Kumpulan Wang COVID-19",
    ])

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["projek_code", "name_bm", "row_type", "year",
                 "siling_keseluruhan_rm", "terkumpul_hingga_2022_rm",
                 "peruntukan_rm", "virement_rm", "peruntukan_dipinda_rm", "sebenar_rm",
                 "varian_rm", "prestasi_pct", "terkumpul_hingga_2023_rm", "has_footnote",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(rows)

print(f"fact_covid_fund_detail.csv: {len(rows)} rows")
for p in problems:
    print("!!", p)
# self-checks (reported, never corrected)
det_s = sum(r[4] for r in rows if r[2] == "project")
det_p = sum(r[5] for r in rows if r[2] == "project")
det_t = sum(r[12] for r in rows if r[2] == "project")
tot = [r for r in rows if r[2] == "total"][0]
print(f"siling: details {det_s:,.2f} vs total {tot[4]:,.2f} diff {det_s-tot[4]:,.2f}")
print(f"terkumpul2022: details {det_p:,.2f} vs total {tot[5]:,.2f} diff {det_p-tot[5]:,.2f}")
print(f"terkumpul2023: details {det_t:,.2f} vs total {tot[12]:,.2f} diff {det_t-tot[12]:,.2f}")
idbad = [r for r in rows if r[2] == "project" and abs(r[5] + r[9] - r[12]) > 1]
print(f"per-row identity prior+sebenar=terkumpul violations: {len(idbad)}")
