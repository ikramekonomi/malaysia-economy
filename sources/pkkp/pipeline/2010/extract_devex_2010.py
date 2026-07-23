#!/usr/bin/env python3
"""Extract Lampiran 2 Penyata Perbelanjaan Pembangunan, PKKP 2010 (RMKe-9, 2006-2010).

Two-page spread: LEFT page (even pdf 182..224) carries project code+name and 3
numeric cols [kos_keseluruhan, anggaran_rmke9_2006_2010, terkumpul_rmke9_prior
(hingga 31.12.2009)]; facing RIGHT page (odd pdf 183..225) carries 7 numeric cols
[ang langsung, ang pinjaman, ang jumlah, sebenar langsung, sebenar pinjaman,
sebenar jumlah, terkumpul_rmke9 (hingga 31.12.2010)]. Rows join by top-coord.

RMKe-9 volume (9th Malaysia Plan) NOT RMKe-10: cumulative cols named
terkumpul_rmke9_prior_rm / terkumpul_rmke9_rm; NEW col anggaran_rmke9_2006_2010_rm
sits right after kos_keseluruhan_rm (no 2012 equivalent).

Hierarchy: P.xx maksud header > ALL-CAPS program header (may wrap a lowercase
parenthetical) > 5-digit project rows (leaves carry amounts; a butiran header
ending ':' with no amounts is a grouping label, not emitted) > 'Jumlah <Program>'
program_subtotal > 'JUMLAH <MINISTRY>' ministry_total > 'JUMLAH PERBELANJAAN
PEMBANGUNAN' grand_total. One row (p186 *70101 Johor) is vertically misaligned:
its 3 left numbers render a line above; repaired by pairing.
"""
import csv
import re
import pdfplumber
from collections import Counter, defaultdict

YEAR = 2010
SRC = "2010_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
PDF = "/home/claude/pkkp/work/2010/2010.pdf"
OUT = "/home/claude/pkkp/warehouse2010/fact_devex_project.csv"
OUT_M = "/home/claude/pkkp/warehouse2010/fact_devex_maksud.csv"
NUMTOK = re.compile(r"^\*?\(?[\d,]+(?:\.\d+)?\)?$|^\*?[–—-]$")
NUMX = 350.0  # left-page numeric columns start at x0>=364; names end by ~300

SKIP_LEFT = re.compile(
    r"^(Penyata Perbelanjaan|bagi tahun|Anggaran Perbelanjaan|Jumlah Anggaran|"
    r"Maksud Perbelanjaan|Harga Projek|2006|RM( RM)*$|Sebenar RMKe|Hingga|"
    r"PENYATA KEWANGAN|LAMPIRAN|\(sambungan\)|\( ?sambungan ?\))")
NOTE_START = re.compile(r"^(Nota\b|Nota:|\*P\s?\.\s?\d)")
NOTE_CONT = re.compile(r"(dibentangkan dalam Sesi Parlimen|dimasuk kira sebagai pendahuluan|yang akan dibentangkan)")


def norm_key(s):
    s = (s or "").upper()
    s = re.sub(r"[–—]", "-", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_amount(tok):
    tok = tok.strip().replace("*", "").replace(" ", "")
    if tok in {"–", "-", "—", ""}:
        return 0.0
    neg = tok.startswith("(")
    tok = tok.strip("()").replace(",", "")
    return -float(tok) if neg else float(tok)


def merge_numbers(ws):
    out = []
    for wd in ws:
        wd = dict(wd)
        if out:
            prev = out[-1]
            gap = wd["x0"] - prev["x1"]
            if wd["text"].strip() == ")" and prev["text"].startswith("("):
                prev["text"] = prev["text"].rstrip() + ")"
                prev["x1"] = wd["x1"]
                continue
            if (gap < 4.5 and re.match(r"^[\(\d,().*]+$", prev["text"])
                    and re.match(r"^[\d,().*]+$", wd["text"])):
                prev["text"] += wd["text"]
                prev["x1"] = wd["x1"]
                continue
        out.append(wd)
    return out


def lines_of(pg):
    words = [w for w in pg.extract_words(x_tolerance=1.5, y_tolerance=2)
             if w.get("upright", True) and w["x0"] >= 0
             and w["x1"] <= pg.width + 5 and 0 <= w["top"] <= pg.height]
    words = [w for w in words
             if not (re.fullmatch(r"\d{1,3}", w["text"]) and (w["x0"] < 62 or w["x0"] > 585))]
    words.sort(key=lambda w: (w["top"], w["x0"]))
    rows_, cur, ct = [], [], None
    for wd in words:
        if cur and wd["top"] - ct > 2.5:
            rows_.append(cur)
            cur = []
        if not cur:
            ct = wd["top"]
        cur.append(wd)
    if cur:
        rows_.append(cur)
    return [(ws[0]["top"], merge_numbers(sorted(ws, key=lambda x: x["x0"]))) for ws in rows_]


def assign7(nums_ws, col_x1):
    nums = [parse_amount(w["text"]) for w in nums_ws]
    if len(nums) == 7:
        return nums
    if col_x1 is None:
        return None
    cand = [None] * 7
    prev = -1
    for w, v in zip(nums_ws, nums):
        ci = min(range(7), key=lambda i: abs(col_x1[i] - w["x1"]))
        if abs(col_x1[ci] - w["x1"]) > 16 or ci <= prev or cand[ci] is not None:
            return None
        cand[ci] = v
        prev = ci
    cand = [0.0 if c is None else c for c in cand]
    if abs(cand[0] + cand[1] - cand[2]) <= 2 and abs(cand[3] + cand[4] - cand[5]) <= 2:
        return cand
    return None


rows = []
stats = Counter()
anomalies = []
current_maksud = current_name = current_program = None
pending = []

with pdfplumber.open(PDF) as pdf:
    for pno in range(182, 226):
        pg = pdf.pages[pno - 1]
        lns = lines_of(pg)
        joined = " ".join(w["text"] for _, ws in lns for w in ws)
        is_right = "Anggaran Tahun" in joined and "Maksud Perbelanjaan" not in joined

        if not is_right:
            # classify each visual line; collect orphan numeric-only lines for repair
            classified = []
            orphan_nums = []
            in_notes = False
            for top, ws in lns:
                texts = [w["text"] for w in ws]
                line = " ".join(texts)
                numws = [w for w in ws if w["x0"] >= NUMX and NUMTOK.match(w["text"])]
                labws = [w for w in ws if w not in numws]
                # a maksud header (P.xx NAME, no leading '*', no numbers) is kept even
                # inside a page-bottom notes region (P.31 is a widow below the Nota block)
                is_maksud_hdr = bool(re.match(r"^P\s?\.\s?\d{2,3}\s+\S", line)) and not numws
                if (in_notes or NOTE_START.match(line) or NOTE_CONT.search(line)) and not is_maksud_hdr:
                    in_notes = True
                    continue
                if numws and not labws:
                    orphan_nums.append([top, numws, False])
                    continue
                classified.append((top, ws, numws, labws))

            last_proj = None
            last_was_prog = False
            for top, ws, numws, labws in classified:
                line = " ".join(w["text"] for w in ws)
                label = " ".join(w["text"] for w in labws).strip()
                if SKIP_LEFT.match(line):
                    last_proj = None
                    last_was_prog = False
                    continue
                mh = re.match(r"^P\s?\.\s?(\d{2,3})\s+(.+)$", line)
                if mh and not numws:
                    current_maksud = f"P.{mh.group(1)}"
                    nm = re.sub(r"\s*-?\s*\(SAMB\.?\)\s*$", "", mh.group(2).strip())
                    if "(SAMB" not in line.upper():
                        current_name = nm
                        current_program = None
                    last_proj = None
                    last_was_prog = False
                    continue

                is_proj = bool(labws) and re.match(r"^\*?\d{5}$", labws[0]["text"])
                if is_proj:
                    code = labws[0]["text"].lstrip("*")
                    name = " ".join(w["text"] for w in labws[1:]).strip()
                    nums3 = [w["text"] for w in numws]
                    if not nums3:
                        # 0-amount 5-digit line: butiran grouping header (skip) unless a
                        # misaligned orphan-numeric line nearby belongs to it
                        if not name.rstrip().endswith(":"):
                            cand = [o for o in orphan_nums if not o[2] and abs(o[0] - top) < 25]
                            if cand:
                                o = min(cand, key=lambda o: abs(o[0] - top))
                                o[2] = True
                                nums3 = [w["text"] for w in o[1]]
                                anomalies.append(f"repaired misaligned row {current_maksud} {code} p{pno}: numbers from top {o[0]:.0f}")
                                stats["repaired_misalign"] += 1
                        if not nums3:
                            stats["butiran_header"] += 1
                            last_proj = None
                            last_was_prog = False
                            continue
                    if len(nums3) != 3:
                        anomalies.append(f"project {current_maksud} {code} p{pno}: {len(nums3)} numeric cells {nums3}")
                        stats["left_bad_ncol"] += 1
                    foot = labws[0]["text"].startswith("*") or any("*" in t for t in nums3)
                    ent = dict(rt="project", maksud=current_maksud, mname=current_name,
                               program=current_program, code=code, name=name,
                               kos=parse_amount(nums3[0]), ang9=parse_amount(nums3[1]) if len(nums3) > 1 else 0.0,
                               prior=parse_amount(nums3[2]) if len(nums3) > 2 else 0.0,
                               foot=foot, y=top, page=pno)
                    pending.append(ent)
                    last_proj = ent
                    last_was_prog = False
                    continue

                if numws:  # total / subtotal (label may precede OR follow numbers)
                    nums3 = [w["text"] for w in numws]
                    lab = re.sub(r"\s+", " ", label).strip()
                    if re.match(r"^JUMLAH PERBELANJAAN PEMBANGUNAN", lab):
                        rt, nm = "grand_total", "JUMLAH PERBELANJAAN PEMBANGUNAN"
                    elif re.match(r"^JUMLAH\b", lab):
                        rt, nm = "ministry_total", re.sub(r"^JUMLAH\s+", "", lab).strip()
                    elif re.match(r"^Jumlah\b", lab):
                        rt, nm = "program_subtotal", re.sub(r"^Jumlah\s+", "", lab).strip()
                    else:
                        anomalies.append(f"unclassified numeric row p{pno}: {lab!r} {nums3}")
                        stats["unclassified"] += 1
                        last_proj = None
                        last_was_prog = False
                        continue
                    if len(nums3) != 3:
                        anomalies.append(f"{rt} {nm!r} p{pno}: {len(nums3)} numeric cells {nums3}")
                        stats["left_bad_ncol"] += 1
                    ent = dict(rt=rt, maksud=current_maksud, mname=current_name,
                               program=(nm if rt == "program_subtotal" else None),
                               code=None, name=nm,
                               kos=parse_amount(nums3[0]), ang9=parse_amount(nums3[1]) if len(nums3) > 1 else 0.0,
                               prior=parse_amount(nums3[2]) if len(nums3) > 2 else 0.0,
                               foot=any("*" in t for t in nums3), y=top, page=pno)
                    pending.append(ent)
                    last_proj = None
                    last_was_prog = False
                    if rt == "program_subtotal":
                        current_program = None
                    continue

                # no numbers, non-skip, non-maksud, non-project text line
                if label and not re.search(r"\bP\s?\.\s?\d{2}\b", label):
                    if re.fullmatch(r"\d{1,3}", label):  # stray page number
                        continue
                    letters = re.sub(r"[^A-Za-z]", "", label)
                    if letters and label == label.upper() and re.match(r"^[A-Z0-9(]", label):
                        frag = re.sub(r"\s*-?\s*\(SAMB\.?\)\s*$", "", label).strip()
                        current_program = (current_program + " " + frag) if (last_was_prog and current_program) else frag
                        last_proj = None
                        last_was_prog = True
                        stats["program_hdr"] += 1
                        continue
                    if last_was_prog and current_program and (label.startswith("(") or label[:1].islower()):
                        current_program = current_program + " " + label.strip()
                        stats["program_hdr_cont"] += 1
                        continue
                    if last_proj is not None and letters and len(label) < 90:
                        last_proj["name"] = (last_proj["name"] + " " + label).strip()
                        stats["name_wrap"] += 1
                        continue
                    anomalies.append(f"orphan text line p{pno}: {label!r}")
                    stats["orphan"] += 1

            for o in orphan_nums:
                if not o[2]:
                    anomalies.append(f"unconsumed orphan-numbers p{pno} top{o[0]:.0f}: {[w['text'] for w in o[1]]}")
                    stats["orphan_nums_unused"] += 1
        else:
            mine = [p for p in pending if p["page"] == pno - 1]
            numlines = []
            for top, ws in lns:
                nws = [w for w in ws if NUMTOK.match(w["text"])]
                if len(nws) >= 5 and len(nws) == len(ws):
                    numlines.append(dict(y=top, ws=nws, used=False))
            full7 = [nl for nl in numlines if len(nl["ws"]) == 7]
            col_x1 = [sorted(nl["ws"][i]["x1"] for nl in full7)[len(full7) // 2] for i in range(7)] if full7 else None
            for p in mine:
                best, bestd = None, 5.0
                for nl in numlines:
                    if nl["used"]:
                        continue
                    d = abs(nl["y"] - p["y"])
                    if d < bestd:
                        best, bestd = nl, d
                if best is None:
                    stats["unmatched_right"] += 1
                    anomalies.append(f"unmatched right for {p['rt']} {p.get('code') or p['name'][:40]} p{p['page']} y={p['y']:.0f}")
                    continue
                best["used"] = True
                vals = assign7(best["ws"], col_x1)
                if vals is None:
                    stats["right_odd"] += 1
                    anomalies.append(f"unsolvable right ({len(best['ws'])} cells) {p.get('code') or p['name'][:40]} p{pno}: {[w['text'] for w in best['ws']]}")
                    continue
                foot2 = any("*" in w["text"] for w in best["ws"])
                ag_l, ag_p, ag_j, sb_l, sb_p, sb_j, kum = vals
                rows.append([
                    p["maksud"], p["mname"], p["rt"], p["program"], p["code"], p["name"], YEAR,
                    p["kos"], p["ang9"], p["prior"], ag_l, ag_p, ag_j, sb_l, sb_p, sb_j, kum,
                    p["foot"] or foot2, SRC, p["page"], p["page"] - 10,
                    "Lampiran 2 Penyata Perbelanjaan Pembangunan",
                ])
            for nl in numlines:
                if not nl["used"]:
                    anomalies.append(f"unused right numeric line p{pno} y{nl['y']:.0f}: {[w['text'] for w in nl['ws']]}")
                    stats["right_unused"] += 1
            pending = [p for p in pending if p["page"] != pno - 1]

# ---- program_bm linkage: keep only where tagged projects sum exactly & uniquely ----
IDX_PROG, IDX_SEBJ = 3, 15
psum = defaultdict(float)
for r in rows:
    if r[2] == "project" and r[IDX_PROG]:
        psum[(r[0], norm_key(r[IDX_PROG]))] += r[IDX_SEBJ]
subcount = defaultdict(int)
subval = {}
for r in rows:
    if r[2] == "program_subtotal":
        key = (r[0], norm_key(r[5]))
        subcount[key] += 1
        subval[key] = r[IDX_SEBJ]
ok = set()
for key, n in subcount.items():
    if n == 1 and key in psum and abs(psum[key] - subval[key]) < 1:
        ok.add(key)
    elif n > 1:
        anomalies.append(f"duplicate program-subtotal name {key} x{n}: attribution nulled")
nulled = 0
for r in rows:
    if r[2] == "project" and r[IDX_PROG]:
        if (r[0], norm_key(r[IDX_PROG])) not in ok:
            r[IDX_PROG] = None
            nulled += 1
print(f"program linkage: {len(ok)} verified groups; {nulled} project attributions nulled")

HEADER = ["maksud_code", "maksud_name_bm", "row_type", "program_bm", "projek_code", "name_bm", "year",
          "kos_keseluruhan_rm", "anggaran_rmke9_2006_2010_rm", "terkumpul_rmke9_prior_rm",
          "anggaran_langsung_rm", "anggaran_pinjaman_rm", "anggaran_jumlah_rm",
          "sebenar_langsung_rm", "sebenar_pinjaman_rm", "sebenar_jumlah_rm", "terkumpul_rmke9_rm",
          "has_footnote", "source_file", "pdf_page", "printed_page", "statement"]
with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(HEADER)
    cw.writerows(rows)

mrows = []
for r in rows:
    if r[2] in ("ministry_total", "grand_total"):
        mk = "TOTAL" if r[2] == "grand_total" else r[0]
        lbl = r[5] if r[2] == "ministry_total" else "JUMLAH PERBELANJAAN PEMBANGUNAN"
        mrows.append([mk, r[1] if r[2] == "ministry_total" else "JUMLAH PERBELANJAAN PEMBANGUNAN",
                      lbl, YEAR, r[7], r[8], r[9], r[10], r[11], r[12], r[13], r[14], r[15], r[16],
                      r[17], r[18], r[19], r[20], r[21]])
HEADER_M = ["maksud_code", "maksud_name_bm", "jumlah_label_bm", "year",
            "kos_keseluruhan_rm", "anggaran_rmke9_2006_2010_rm", "terkumpul_rmke9_prior_rm",
            "anggaran_langsung_rm", "anggaran_pinjaman_rm", "anggaran_jumlah_rm",
            "sebenar_langsung_rm", "sebenar_pinjaman_rm", "sebenar_jumlah_rm", "terkumpul_rmke9_rm",
            "has_footnote", "source_file", "pdf_page", "printed_page", "statement"]
with open(OUT_M, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(HEADER_M)
    cw.writerows(mrows)

c = Counter(r[2] for r in rows)
print(f"\nfact_devex_project.csv: {len(rows)} rows | {dict(c)}")
print(f"fact_devex_maksud.csv: {len(mrows)} rows")
print(f"stats={dict(stats)}")
print(f"\n=== ANOMALIES ({len(anomalies)}) ===")
for a in anomalies:
    print("  ", a)
