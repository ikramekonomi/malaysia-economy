#!/usr/bin/env python3
"""Extract Nota 6 'Penyata Akaun Pinjaman Disatukan' for the 2017 volume (pdf 64, printed 53).

2017 structure (OLD accounting policy: loan receipts at proceeds, no Pelarasan
Akaun Premium/Diskaun row; NON-NIL closing balance RM33,482,397,941):
PINJAMAN (Dalam Negeri WITH 'Baki pada 1 Januari' / Luar Negeri without),
per-sub 'Baki pada 31 Disember' rows, 'Jumlah Pinjaman pada 31 Disember',
BANTUAN LUAR NEGERI (Multilateral / Bilateral WITH openings),
'Jumlah Bantuan Luar Negeri pada 31 Disember',
'Jumlah Pinjaman dan Bantuan Luar Negeri pada 31 Disember',
'Pindahan Ke / Kumpulan Wang Pembangunan',
'BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER'.
Two value columns: 2017 and 2016, (Debit)/Kredit convention."""
import csv
import re

NUM = r"\(?[\d,]+\)?|[–—-]"


def parse_amount(tok):
    tok = tok.strip()
    if tok in {"–", "-", "—", ""}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    v = float(tok.strip("()").replace(",", ""))
    return -v if neg else v


def extract(fulltxt_path, pdf_page, src, year, prior, out_path):
    pages = open(fulltxt_path, encoding="utf-8").read().split("\f")
    t = pages[pdf_page - 1]
    i = t.find("Penyata Akaun Pinjaman Disatukan pada")
    region = t[i:] if i >= 0 else t
    rows = []
    group = None
    sub = None
    for line in region.split("\n"):
        s = line.rstrip()
        st = s.strip()
        if not st or st.startswith(("(Debit)", "RM", "NOTA KEPADA", "PENYATA KEWANGAN", "NOT A", "B AG I", "6. Teks", "5 WJD")):
            continue
        s = re.sub(r"^(\s*)\d{1,3}(\s{3,})", r"\1\2", s)  # strip margin page number
        s = re.sub(r"(\s{6,})\d{1,3}\s*$", "", s)
        s = re.sub(r"(\S)\s{4,}[A-Z][A-Z ]{9,}$", r"\1", s)  # rotated sidebar overprint
        st = s.strip()
        if not st:
            continue
        m = re.match(rf"^(.*?)\s\s+((?:(?:{NUM})\s+)?(?:{NUM}))\s*$", s)
        toks = re.findall(NUM, m.group(2)) if m else []
        label = m.group(1).strip() if m else st
        if not m or not toks:
            if st in ("PINJAMAN", "BANTUAN LUAR NEGERI"):
                group = st
                sub = None
            elif st in ("Dalam Negeri", "Luar Negeri", "Pinjaman Multilateral", "Pinjaman Bilateral"):
                sub = st
            elif st.startswith("Pelarasan"):
                group, sub = "PELARASAN", None
            elif st.startswith("Pindahan Ke"):
                group, sub = "PINDAHAN KE", None
            continue
        if len(toks) < 2 and label in ("PINJAMAN", "BANTUAN LUAR NEGERI"):
            continue
        vals = [parse_amount(x) for x in toks]
        if label in ("PINJAMAN", "BANTUAN LUAR NEGERI"):
            group, sub = label, None
            rt = "group_total"
        elif label.startswith("Jumlah Pinjaman dan Bantuan"):
            group, sub, rt = "JUMLAH", None, "total"
            label = "Jumlah Pinjaman dan Bantuan Luar Negeri pada 31 Disember"
        elif label.startswith("Jumlah Pinjaman pada"):
            group, sub, rt = "PINJAMAN", None, "group_total"
            label = "Jumlah Pinjaman pada 31 Disember"
        elif label.startswith("Jumlah Bantuan Luar Negeri pada"):
            group, sub, rt = "BANTUAN LUAR NEGERI", None, "group_total"
            label = "Jumlah Bantuan Luar Negeri pada 31 Disember"
        elif label.startswith("Pelarasan Akaun Premium"):
            group, sub, rt = "PELARASAN", None, "adjustment"
            label = "Pelarasan Akaun Premium/Diskaun Sekuriti Kerajaan"
        elif label in ("Kumpulan Wang Pembangunan", "Kumpulan Wang COVID-19"):
            group, sub, rt = "PINDAHAN KE", None, "transfer"
        elif label == label.upper() and label.startswith("BAKI"):
            group, sub, rt = "BAKI", None, ("opening" if "1 JANUARI" in label.upper() else "closing")
        elif label in ("Baki pada 1 Januari", "Terimaan", "Bayaran", "Baki pada 31 Disember"):
            rt = "detail"
        else:
            rt = "other"
        if not label:
            continue
        cur = vals[0] if len(vals) >= 1 else None
        pri = vals[1] if len(vals) >= 2 else None
        base = "Nota 6 Penyata Akaun Pinjaman Disatukan"
        rows.append([group, sub, label, rt, year, cur, src, pdf_page, pdf_page - 11, base])
        if pri is not None:
            rows.append([group, sub, label, rt, prior, pri, src, pdf_page, pdf_page - 11, base])
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        cw = csv.writer(f)
        cw.writerow(["group_bm", "sub_bm", "line_item_bm", "row_type", "year", "amount_rm",
                     "source_file", "pdf_page", "printed_page", "statement"])
        cw.writerows(rows)
    # validate identities per year
    import collections
    V = collections.defaultdict(dict)
    for r in rows:
        V[(r[0], r[1], r[2])][r[4]] = r[5]
    ok = True
    for yr in (year, prior):
        for grp, subs, jlbl in [("PINJAMAN", ["Dalam Negeri", "Luar Negeri"], "Jumlah Pinjaman pada 31 Disember"),
                                ("BANTUAN LUAR NEGERI", ["Pinjaman Multilateral", "Pinjaman Bilateral"],
                                 "Jumlah Bantuan Luar Negeri pada 31 Disember")]:
            gt = V.get((grp, None, jlbl), {}).get(yr)
            ss = sum(V.get((grp, sb, "Baki pada 31 Disember"), {}).get(yr, 0.0) for sb in subs)
            if gt is None or abs(gt - ss) > 1:
                print(f"FAIL {src} {yr} {grp}: total={gt} vs subs={ss}")
                ok = False
        j = V.get(("JUMLAH", None, "Jumlah Pinjaman dan Bantuan Luar Negeri pada 31 Disember"), {}).get(yr)
        p = V.get(("PINJAMAN", None, "Jumlah Pinjaman pada 31 Disember"), {}).get(yr, 0.0)
        b = V.get(("BANTUAN LUAR NEGERI", None, "Jumlah Bantuan Luar Negeri pada 31 Disember"), {}).get(yr, 0.0)
        if j is None or abs((p + b) - j) > 1:
            print(f"FAIL {src} {yr}: PINJAMAN+BANTUAN={p+b} vs JUMLAH={j}")
            ok = False
        adj = sum(v.get(yr, 0.0) for k, v in V.items() if k[0] in ("PELARASAN", "PINDAHAN KE"))
        closing = next((v.get(yr) for k, v in V.items() if k[0] == "BAKI" and "31" in k[2]), None)
        if closing is not None and j is not None and abs(j + adj - closing) > 1:
            print(f"FAIL {src} {yr}: jumlah+pelarasan+pindahan={j+adj} vs closing={closing}")
            ok = False
    print(f"{out_path}: {len(rows)} rows, identities {'PASS' if ok else 'SEE FAILURES'}")
    return ok


extract("/home/claude/pkkp/work/2017/full.txt", 64,
        "2017_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf", 2017, 2016,
        "/home/claude/pkkp/warehouse2017/fact_loan_account_statement.csv")
