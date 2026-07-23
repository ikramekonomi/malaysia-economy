#!/usr/bin/env python3
"""Extract development expenditure per Maksud (ministry) from Lampiran 2 (pdf pages 176-211).

Layout: two-page spreads. Left page = maksud header (P.xx NAME), project rows,
'JUMLAH <MINISTRY>' total row with [kos keseluruhan, perbelanjaan RMKe-12 hingga 31.12.2018].
Right page = same rows' numeric columns: [anggaran langsung, anggaran pinjaman, anggaran jumlah,
sebenar langsung, sebenar pinjaman, sebenar jumlah, terkumpul hingga 31.12.2019].
Rows align by vertical position across the pair.
"""
import csv
import re
import pdfplumber

YEAR = 2019
SRC = "2019_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2019/fact_devex_maksud.csv"
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
    # fine-grained clustering: some 2020 L2 pages are squeezed to ~7.5pt row
    # pitch with distinct rows only 1.2pt apart (see extract_lampiran2_projects)
    words = sorted((w for w in page_obj.extract_words(x_tolerance=1.5, y_tolerance=0.12)
                    if w["x0"] >= 0 and w["x1"] <= page_obj.width and w.get("upright", True)),  # drop off-page spread ghosts + rotated sidebar
                   key=lambda w: w["top"])
    rows_, cur, cur_top = [], [], None
    for wd in words:
        if cur and wd["top"] - cur_top > 0.25:
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


rows = []
current_maksud = None
current_name = None
pending = []  # totals awaiting right-page numbers: (label, y, kos, kumul_prior)
grand = None

with pdfplumber.open("/home/claude/pkkp/work/2019/2019.pdf") as pdf:
    for pno in range(176, 212):
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
                    SRC, p["page"], p["page"] - 12, "Lampiran 2 Penyata Perbelanjaan Pembangunan",
                ])
            pending = [p for p in pending if p["page"] != pno - 1]

# 2019 print quirk (P.24): an interim 'JUMLAH KEMENTERIAN ...' prints mid-block
# on pdf 188; only the final row per (maksud,label) is the ministry total. Drop
# earlier duplicates from the maksud-grain fact (they remain in fact_devex_project).
seen_last = {}
for i, r in enumerate(rows):
    seen_last[(r[0], r[2])] = i
drop = [i for i, r in enumerate(rows) if seen_last[(r[0], r[2])] != i]
for i in drop:
    print(f"!! interim duplicate JUMLAH row dropped from maksud fact: {rows[i][0]} p{rows[i][15]} sebenar={rows[i][11]:,.2f}")
rows = [r for i, r in enumerate(rows) if i not in drop]

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["maksud_code", "maksud_name_bm", "jumlah_label_bm", "year",
                 "kos_keseluruhan_rm", "terkumpul_rmke11_prior_rm",
                 "anggaran_langsung_rm", "anggaran_pinjaman_rm", "anggaran_jumlah_rm",
                 "sebenar_langsung_rm", "sebenar_pinjaman_rm", "sebenar_jumlah_rm",
                 "terkumpul_rmke11_rm", "has_footnote",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(rows)
print(f"fact_devex_maksud.csv: {len(rows)} rows")
for r in rows:
    print(r[0], "|", (r[2] or "")[:52], "| sebenar_jumlah:", f"{r[11]:,.2f}")
