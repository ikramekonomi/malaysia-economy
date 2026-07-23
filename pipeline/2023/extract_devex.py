#!/usr/bin/env python3
"""Extract development expenditure per Maksud (ministry) from Lampiran 2 (pdf pages 206-243).

Layout: two-page spreads. Left page = maksud header (P.xx NAME), project rows,
'JUMLAH <MINISTRY>' total row with [kos keseluruhan, perbelanjaan RMKe-12 hingga 31.12.2023].
Right page = same rows' numeric columns: [anggaran langsung, anggaran pinjaman, anggaran jumlah,
sebenar langsung, sebenar pinjaman, sebenar jumlah, terkumpul hingga 31.12.2024].
Rows align by vertical position across the pair.
"""
import csv
import re
import pdfplumber

YEAR = 2023
SRC = "2023_Penyata_Kewangan_Kerajaan_Persekutuan.pdf"
OUT = "/home/claude/pkkp/warehouse2023/fact_devex_maksud.csv"
NUMTOK = re.compile(r"^\*?\(?[\d,]+(?:\.\d+)?\)?$|^[–—-]$")


def parse_amount(tok):
    tok = tok.strip().replace("*", "")
    if tok in {"–", "-", "—", ""}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()").replace(",", "")
    v = float(tok)
    return -v if neg else v


def merge_split_numbers(ws):
    """pdfplumber sometimes splits a kerned number ('1' + '4,454,283,483.32').
    Merge consecutive numeric fragments separated by a tiny x-gap."""
    out = []
    for wd in ws:
        if out:
            prev = out[-1]
            gap = wd["x0"] - prev["x1"]
            if (gap < 4.0
                    and re.match(r"^[\d,().*]+$", prev["text"])
                    and re.match(r"^[\d,().*]+%?$", wd["text"])):
                prev["text"] = prev["text"] + wd["text"]
                prev["x1"] = wd["x1"]
                continue
        out.append(dict(wd))
    return out


def lines_of(page_obj):
    words = page_obj.extract_words(x_tolerance=1.5, y_tolerance=2)
    lines = {}
    for wd in words:
        key = round(wd["top"] / 3.0)
        lines.setdefault(key, []).append(wd)
    out = []
    for key in sorted(lines):
        ws = sorted(lines[key], key=lambda x: x["x0"])
        out.append((ws[0]["top"], merge_split_numbers(ws)))
    return out


rows = []
current_maksud = None
current_name = None
pending = []  # totals awaiting right-page numbers: (label, y, kos, kumul_prior)
grand = None

with pdfplumber.open("/home/claude/pkkp/work/2023/2023.pdf") as pdf:
    for pno in range(196, 232):
        pg = pdf.pages[pno - 1]
        lns = lines_of(pg)
        joined = " ".join(w["text"] for _, ws in lns for w in ws)
        is_right = "Anggaran Tahun" in joined and "Maksud Perbelanjaan" not in joined
        if not is_right:
            # LEFT page: maksud headers and JUMLAH rows
            for top, ws in lns:
                texts = [w["text"] for w in ws]
                line = " ".join(texts)
                mh = re.match(r"^P\.\s?(\d{2,3})\s+(.+)$", line)
                if mh and not any(NUMTOK.match(t) for t in texts[2:]):
                    current_maksud = f"P.{mh.group(1)}"
                    current_name = mh.group(2).strip()
                    continue
                if re.match(r"^JUMLAH\s+[A-Z]", line) and not re.match(r"^JUMLAH PERBELANJAAN PEMBANGUNAN", line):
                    nums = [t for t in texts if NUMTOK.match(t)]
                    label = " ".join(t for t in texts if not NUMTOK.match(t))
                    label = re.sub(r"^JUMLAH\s+", "", label).strip()
                    if len(nums) >= 2:
                        pending.append({
                            "maksud": current_maksud, "name": current_name,
                            "label": label, "y": top, "page": pno,
                            "kos": parse_amount(nums[0]), "kumul_prior": parse_amount(nums[1]),
                            "footnote": any("*" in t for t in nums),
                        })
                if re.match(r"^JUMLAH PERBELANJAAN PEMBANGUNAN", line):
                    nums = [t for t in texts if NUMTOK.match(t)]
                    if len(nums) >= 2:
                        pending.append({
                            "maksud": "TOTAL", "name": "JUMLAH PERBELANJAAN PEMBANGUNAN",
                            "label": "JUMLAH PERBELANJAAN PEMBANGUNAN", "y": top, "page": pno,
                            "kos": parse_amount(nums[0]), "kumul_prior": parse_amount(nums[1]),
                            "footnote": any("*" in t for t in nums),
                        })
        else:
            # RIGHT page: resolve pending totals from the immediately previous left page
            mine = [p for p in pending if p["page"] == pno - 1]
            numlines = []
            for top, ws in lns:
                texts = [w["text"] for w in ws]
                if len(texts) >= 5 and all(NUMTOK.match(t) for t in texts):
                    numlines.append((top, texts, [w["x1"] for w in ws]))
            col_x1 = None
            full7 = [(t, x) for _, t, x in numlines if len(t) == 7]
            if full7:
                col_x1 = [sorted(x[i] for _, x in full7)[len(full7) // 2] for i in range(7)]
            for p in mine:
                best, bestx, bestd = None, None, 6.0
                for top, texts, xs in numlines:
                    d = abs(top - p["y"])
                    if d < bestd:
                        best, bestx, bestd = texts, xs, d
                if best is None:
                    print(f"!! no right-page match for {p['label']} (p{p['page']} y={p['y']:.0f})")
                    continue
                nums = [parse_amount(t) for t in best]
                if len(nums) == 7:
                    ag_l, ag_p, ag_j, sb_l, sb_p, sb_j, kumul = nums
                elif len(nums) == 6 and col_x1 is not None:
                    # x-position assignment: map tokens to column right-edges; the
                    # unmatched column is a dropped dash (= 0)
                    cand = [0.0] * 7
                    ok = True
                    prev = -1
                    for x1t, v in zip(bestx, nums):
                        ci = min(range(7), key=lambda i: abs(col_x1[i] - x1t))
                        if abs(col_x1[ci] - x1t) > 15 or ci <= prev:
                            ok = False
                            break
                        cand[ci] = v
                        prev = ci
                    if not ok:
                        print(f"!! 6-col x-assignment failed for {p['label']}: {best}")
                        continue
                    ag_l, ag_p, ag_j, sb_l, sb_p, sb_j, kumul = cand
                    if abs(ag_l + ag_p - ag_j) > 2 or abs(sb_l + sb_p - sb_j) > 2:
                        print(f"!! 6-col identities fail for {p['label']}: {cand}")
                        continue
                else:
                    print(f"!! odd column count {len(nums)} for {p['label']}: {best}")
                    continue
                rows.append([
                    p["maksud"], p["name"], p["label"], YEAR,
                    p["kos"], p["kumul_prior"],
                    ag_l, ag_p, ag_j, sb_l, sb_p, sb_j, kumul, p["footnote"],
                    SRC, p["page"], p["page"] - 14, "Lampiran 2 Penyata Perbelanjaan Pembangunan",
                ])
            pending = [p for p in pending if p["page"] != pno - 1]

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["maksud_code", "maksud_name_bm", "jumlah_label_bm", "year",
                 "kos_keseluruhan_rm", "terkumpul_rmke12_prior_rm",
                 "anggaran_langsung_rm", "anggaran_pinjaman_rm", "anggaran_jumlah_rm",
                 "sebenar_langsung_rm", "sebenar_pinjaman_rm", "sebenar_jumlah_rm",
                 "terkumpul_rmke12_rm", "has_footnote",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(rows)
print(f"fact_devex_maksud.csv: {len(rows)} rows")
for r in rows:
    print(r[0], "|", (r[2] or "")[:52], "| sebenar_jumlah:", f"{r[11]:,.2f}")
