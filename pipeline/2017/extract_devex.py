#!/usr/bin/env python3
"""Extract development expenditure per Maksud (ministry) from Lampiran 2 (pdf pages 218-253).

Layout: two-page spreads. Left page = maksud header (P.xx NAME), project rows,
'JUMLAH <MINISTRY>' total row with [kos keseluruhan, perbelanjaan RMKe-11 hingga 31.12.2017].
Right page = same rows' numeric columns: [anggaran langsung, anggaran pinjaman, anggaran jumlah,
sebenar langsung, sebenar pinjaman, sebenar jumlah, terkumpul hingga 31.12.2017].
Rows align by vertical position across the pair.
"""
import csv
import re
import pdfplumber

YEAR = 2017
SRC = "2017_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2017/fact_devex_maksud.csv"
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
            wide_ok = (gap < 8.0 and (wd["text"].startswith((",", "."))
                       or re.fullmatch(r"\*?\d{1,3}", prev["text"])))
            if ((gap < 4.0 or wide_ok)
                    and re.match(r"^[\d,().*]+$", prev["text"])
                    and re.match(r"^[\d,().*]+%?$", wd["text"])):
                prev["text"] = prev["text"] + wd["text"]
                prev["x1"] = wd["x1"]
                continue
        out.append(dict(wd))
    return out


def lines_of(page_obj):
    """Gap-based row clustering at 2.5pt (bucket rounding split the 2021 grand
    total's label from its numbers)."""
    words = sorted((w for w in page_obj.extract_words(x_tolerance=1.5, y_tolerance=2)
                    if w.get("upright", True)
                    and w["x0"] >= 0 and w["x1"] <= page_obj.width + 5
                    and 0 <= w["top"] <= page_obj.height),
                   key=lambda w: w["top"])
    # strip the 2018 volume's stray '!' watermark glyphs (printed as lone '!'
    # words and as trailing '!' on header words)
    cleaned = []
    for w in words:
        t = w["text"]
        if t.strip("!") == "":
            continue
        if t.endswith("!") and not re.search(r"[!]{2,}", t):
            w = dict(w)
            w["text"] = t.rstrip("!")
        cleaned.append(w)
    # drop the sidebar printed-page-number glyphs (bare 1-3 digit integers in
    # the left/right margin zones); Lampiran 2 amounts always carry sen
    cleaned = [w for w in cleaned
               if not (re.fullmatch(r"\d{1,3}", w["text"])
                       and (w["x0"] < 62 or w["x0"] > 590))]
    words = cleaned
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
    return [(sorted(ws, key=lambda x: x["x0"])[0]["top"],
             merge_split_numbers(sorted(ws, key=lambda x: x["x0"]))) for ws in rows_]


rows = []
current_maksud = None
current_name = None
pending = []  # totals awaiting right-page numbers: (label, y, kos, kumul_prior)
grand = None

with pdfplumber.open("/home/claude/pkkp/work/2017/2017.pdf") as pdf:
    for pno in range(218, 252):
        pg = pdf.pages[pno - 1]
        lns = lines_of(pg)
        joined = " ".join(w["text"] for _, ws in lns for w in ws)
        is_right = "Anggaran Tahun" in joined and "Maksud Perbelanjaan" not in joined
        if not is_right:
            # LEFT page: maksud headers and JUMLAH rows
            for top, ws in lns:
                texts = [w["text"] for w in ws]
                line = " ".join(texts)
                # kerned header repair: 'P . 2 7 KEMENTERIAN ...' / 'P . 27 ...' -> 'P.27 ...'
                kern = re.match(r"^P\s*\.\s*((?:\d\s*){1,3})([A-Z!].*)$", line)
                if kern:
                    line = "P." + re.sub(r"\s", "", kern.group(1)) + " " + kern.group(2).strip()
                mh = re.match(r"^P\.\s?(\d{2,3})\s+(.+)$", line)
                if mh and not re.search(r"\d,\d{3}|\d+\.\d{2}", line):
                    current_maksud = f"P.{mh.group(1)}"
                    current_name = mh.group(2).strip()
                    continue
                if re.match(r"^JUMLAH\s+[A-Z]", line) and not re.match(r"^JUMLAH PERBELANJAAN PEMBANGUNAN", line):
                    nums = [t for t in texts if NUMTOK.match(t)]
                    label = " ".join(t for t in texts if not NUMTOK.match(t))
                    label = re.sub(r"^JUMLAH\s+", "", label).strip()
                    base_name = re.sub(r"\s*(?:–\s*|-\s*)?\(SAMB\.?\)\s*$", "", current_name or "").strip()
                    # header may carry a parenthetical acronym the JUMLAH row omits (P.24 '(MITI)')
                    base_cmp = re.sub(r"\s*\([^)]*\)\s*$", "", base_name).strip()
                    # JUMLAH may abbreviate 'KEMENTERIAN' to 'KEM.' (P.25)
                    cands = {base_name, base_cmp,
                             base_name.replace("KEMENTERIAN", "KEM."),
                             base_cmp.replace("KEMENTERIAN", "KEM.")}
                    if label not in cands:
                        continue  # sub-block subtotal (e.g. P.63 JUMLAH PENDIDIKAN), not the vote total
                    if len(nums) >= 2:
                        dup = [p for p in pending if p["maksud"] == current_maksud and p["label"] == label]
                        if dup:
                            # a same-named block subtotal precedes the vote total
                            # (P.24 MITI block); the LAST printed JUMLAH closes the
                            # vote -- keep it, drop the block subtotal here (it
                            # remains in fact_devex_project as program_subtotal)
                            print(f"!! duplicate JUMLAH {label!r} in {current_maksud} p{pno}: keeping the last (vote total)")
                            pending.remove(dup[0])
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
            diffs = []
            for p in mine:
                if numlines:
                    d = min((abs(top - p["y"]), p["y"] - top) for top, _, _ in numlines)[1]
                    if abs(d) < 8:
                        diffs.append(d)
            off = sorted(diffs)[len(diffs) // 2] if diffs else 0.0
            for p in mine:
                best, bestx, bestd = None, None, 4.0
                for top, texts, xs in numlines:
                    d = abs(top + off - p["y"])
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
                    SRC, p["page"], p["page"] - 11, "Lampiran 2 Penyata Perbelanjaan Pembangunan",
                ])
            pending = [p for p in pending if p["page"] != pno - 1]

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
