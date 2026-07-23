#!/usr/bin/env python3
"""Extract Lampiran 3: Penyata Perbelanjaan Kumpulan Wang COVID-19 (PKKP 2021, pdf 248-249).

LIVE fund, two-page spread. LEFT (pdf 248): 5-digit code + name (may wrap around
the numbers line) + 4 columns [Siling Keseluruhan | Perbelanjaan Sehingga
31.12.2020 | Peruntukan | Tambahan]. RIGHT (pdf 249), same y: 6 columns
[Virement Tambah/(Kurang) | Peruntukan Dipinda | Perbelanjaan Sebenar |
Lebihan/(Kurangan) Belanja | Perbelanjaan Terkumpul Sehingga 31.12.2021 |
Prestasi %]. The 2021 layout adds a 'Tambahan' column absent in 2022 (heavy
supplementary appropriations year); cumulative columns are named by the printed
cut-off dates (terkumpul_hingga_2020_rm / terkumpul_hingga_2021_rm).
The Prestasi % cell sometimes drops half a line below its row (e.g. 00900) —
row pairing tolerates it via nearest-y matching per column count.
"""
import csv
import re
import pdfplumber

YEAR = 2021
SRC = "2021_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2021/fact_covid_fund_detail.csv"
NUMTOK = re.compile(r"^\*?\(?[\d,]+(?:\.\d+)?\)?$|^\*?[–—-]$")


def parse_amount(tok):
    if tok is None:
        return None
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


def lines_of(page_obj, gap=2.5):
    words = sorted(page_obj.extract_words(x_tolerance=1.5, y_tolerance=2), key=lambda w: w["top"])
    rows_, cur, cur_top = [], [], None
    for wd in words:
        if cur and wd["top"] - cur_top > gap:
            rows_.append(cur)
            cur = []
        if not cur:
            cur_top = wd["top"]
        cur.append(wd)
    if cur:
        rows_.append(cur)
    return [(sorted(ws, key=lambda x: x["x0"])[0]["top"], merge_split_numbers(sorted(ws, key=lambda x: x["x0"]))) for ws in rows_]


SKIP = re.compile(r"^(Penyata Perbelanjaan|bagi tahun|Maksud Perbelanjaan|Siling|sehingga|Sehingga|RM( |$)|"
                  r"PENYATA KEWANGAN|LAMPIRAN|Teks |\d+$|Peruntukan( |$)|Tambahan$|Virement|"
                  r"Perbelanjaan$|Perbelanjaan Sebenar$|Lebihan|Prestasi|%$|Sebenar 2021|Varian 2021)")

entries = []   # left-page rows: {'code','name','rt','vals4','y'}
with pdfplumber.open("/home/claude/pkkp/work/2021/2021.pdf") as pdf:
    # ---- LEFT page (pdf 248): code/name + 4 numeric columns
    for top, ws in lines_of(pdf.pages[247]):
        texts = [w["text"] for w in ws]
        line = " ".join(texts)
        if SKIP.match(line):
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
            entries.append({"code": head[0], "name": label, "rt": "project", "y": top,
                            "vals4": nums if len(nums) == 4 else None})
        elif label.startswith("Jumlah"):
            entries.append({"code": None, "name": label, "rt": "total", "y": top,
                            "vals4": nums if len(nums) == 4 else None})
        elif not head and len(nums) == 4 and entries and entries[-1]["vals4"] is None:
            entries[-1]["vals4"] = nums
            entries[-1]["y"] = top
        elif label and not nums and entries and entries[-1]["rt"] == "project":
            entries[-1]["name"] += " " + label

    # ---- RIGHT page (pdf 249): 6 numeric columns at the same y.
    # The Prestasi % occasionally drops to its own line; collect numeric rows,
    # then merge any lone percent-like token into the nearest 5-token row above.
    numlines = []
    for top, ws in lines_of(pdf.pages[248]):
        texts = [w["text"] for w in ws]
        if all(NUMTOK.match(t) for t in texts) and texts:
            numlines.append({"y": top, "toks": texts, "used": False})
    merged = []
    for nl in numlines:
        if (len(nl["toks"]) == 1 and re.fullmatch(r"\d{1,3}\.\d{2}", nl["toks"][0]) and merged
                and len(merged[-1]["toks"]) == 5 and nl["y"] - merged[-1]["y"] < 14):
            merged[-1]["toks"].append(nl["toks"][0])
            continue
        merged.append(nl)
    numlines = [nl for nl in merged if len(nl["toks"]) >= 5]

rows = []
problems = []
for e in entries:
    if e["vals4"] is None:
        problems.append(f"left row without 4 values: {e['rt']} {e['name'][:60]}")
        continue
    best, bestd = None, 6.0
    for nl in numlines:
        if nl["used"]:
            continue
        d = abs(nl["y"] - e["y"])
        if d < bestd:
            best, bestd = nl, d
    if best is None:
        problems.append(f"no right-page match: {e['rt']} {e['name'][:60]} y={e['y']:.0f}")
        continue
    best["used"] = True
    toks6 = best["toks"]
    if len(toks6) == 5:
        toks6 = toks6 + [None]   # Prestasi % printed blank/dash for nil rows
    foot = any(t and "*" in t for t in e["vals4"] + [t for t in toks6 if t])
    siling, prior, peruntukan, tambahan = [parse_amount(t) for t in e["vals4"]]
    virement, dipinda, sebenar, varian, terkumpul, pct = [parse_amount(t) for t in toks6]
    rows.append([
        e["code"], e["name"], e["rt"], YEAR,
        siling, prior, peruntukan, tambahan, virement, dipinda, sebenar, varian, pct, terkumpul, foot,
        SRC, 248, 236, "Lampiran 3 Penyata Perbelanjaan Kumpulan Wang COVID-19",
    ])

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["projek_code", "name_bm", "row_type", "year",
                 "siling_keseluruhan_rm", "terkumpul_hingga_2020_rm",
                 "peruntukan_rm", "tambahan_rm", "virement_rm", "peruntukan_dipinda_rm", "sebenar_rm",
                 "varian_rm", "prestasi_pct", "terkumpul_hingga_2021_rm", "has_footnote",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(rows)

print(f"fact_covid_fund_detail.csv: {len(rows)} rows")
for p in problems:
    print("!!", p)
# self-checks (reported, never corrected)
tot = [r for r in rows if r[2] == "total"][0]
for idx, nm in [(4, "siling"), (5, "terkumpul2020"), (6, "peruntukan"), (7, "tambahan"),
                (8, "virement"), (9, "dipinda"), (10, "sebenar2021"), (11, "varian"), (13, "terkumpul2021")]:
    det = sum(r[idx] for r in rows if r[2] == "project" and r[idx] is not None)
    print(f"{nm}: details {det:,.2f} vs total {tot[idx]:,.2f} diff {det-tot[idx]:,.2f}")
idbad = [r for r in rows if r[2] == "project" and abs(r[5] + r[10] - r[13]) > 1]
print(f"per-row identity prior+sebenar=terkumpul violations: {len(idbad)}")
for r in idbad:
    print("  !!", r[0], r[1][:50], r[5], r[10], r[13])
idbad2 = [r for r in rows if r[2] == "project" and abs(r[6] + r[7] + r[8] - r[9]) > 1]
print(f"per-row identity peruntukan+tambahan+virement=dipinda violations: {len(idbad2)}")
for r in idbad2:
    print("  !!", r[0], r[1][:50], r[6], r[7], r[8], r[9])
