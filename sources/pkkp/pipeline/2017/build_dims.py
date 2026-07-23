#!/usr/bin/env python3
"""Build dim_maksud from fact_opex_maksud + fact_devex_maksud, with English glosses.

Design for cross-year loading: primary key (maksud_code, year). Ministries rename/merge
over time; each year's row records that year's official BM name. name_en is a gloss,
not an official translation.

2017 context: pre-GE14 (BN-era) ministry structure -- the last full year of the
2016-style maksud list (Kementerian Pendidikan Tinggi separate, Kemajuan Luar
Bandar dan Wilayah, Sumber Asli dan Alam Sekitar, Perdagangan Dalam Negeri
Koperasi dan Kepenggunaan, etc.). The May 2018 restructuring happens in the
NEXT volume; expect large maksud-level restatements against the 2018 volume's
comparatives.
"""
import csv

WH = "/home/claude/pkkp/warehouse2017"

EN = {
    "Peruntukan Diraja Bagi S.P.B. Yang di-Pertuan Agong": "Royal Provision for HM the Yang di-Pertuan Agong",
    "Elaun-elaun Diraja": "Royal Allowances",
    "Ketua Hakim Negara, Hakim Besar dan Hakim": "Chief Justice, Chief Judges and Judges",
    "Ketua Audit Negara": "Auditor General",
    "Yang di-Pertua Dewan Rakyat": "Speaker of the House of Representatives",
    "Yang di-Pertua Dewan Negara": "President of the Senate",
    "Suruhanjaya Pilihan Raya": "Election Commission",
    "Suruhanjaya Perkhidmatan Perundangan": "Legal Service Commission",
    "Suruhanjaya Perkhidmatan Awam": "Public Service Commission",
    "Suruhanjaya Perkhidmatan Pelajaran": "Education Service Commission",
    "Suruhanjaya Pasukan Polis": "Police Force Commission",
    "Perbendaharaan": "Treasury",
    "PERBENDAHARAAN": "Treasury",
    "Perbelanjaan Kerana Hutang Negara": "National Debt Charges",
    "Pencen, Elaun Bersara dan Ganjaran": "Pensions, Retirement Allowances and Gratuities",
    "Parlimen": "Parliament",
    "Pejabat Penyimpan Mohor Besar Raja-Raja": "Office of the Keeper of the Rulers' Seal",
    "Jabatan Audit Negara": "National Audit Department",
    "Jabatan Perdana Menteri": "Prime Minister's Department",
    "JABATAN PERDANA MENTERI": "Prime Minister's Department",
    "Jabatan Perkhidmatan Awam": "Public Service Department",
    "JABATAN PERKHIDMATAN AWAM": "Public Service Department",
    "Jabatan Peguam Negara": "Attorney General's Chambers",
    "Suruhanjaya Pencegahan Rasuah Malaysia": "Malaysian Anti-Corruption Commission",
    "Perkhidmatan Am Perbendaharaan": "Treasury General Services",
    "Peruntukan kepada Kumpulan Wang Terkanun": "Contributions to Statutory Funds",
    "Kementerian Luar Negeri": "Ministry of Foreign Affairs",
    "KEMENTERIAN LUAR NEGERI": "Ministry of Foreign Affairs",
    "Kementerian Perusahaan Perladangan dan Komoditi": "Ministry of Plantation Industries and Commodities",
    "KEMENTERIAN PERUSAHAAN PERLADANGAN DAN KOMODITI": "Ministry of Plantation Industries and Commodities",
    "Kementerian Pertanian dan Industri Asas Tani": "Ministry of Agriculture and Agro-based Industry",
    "KEMENTERIAN PERTANIAN DAN INDUSTRI ASAS TANI": "Ministry of Agriculture and Agro-based Industry",
    "Kementerian Kemajuan Luar Bandar dan Wilayah": "Ministry of Rural and Regional Development",
    "KEMENTERIAN KEMAJUAN LUAR BANDAR DAN WILAYAH": "Ministry of Rural and Regional Development",
    "Kementerian Sumber Asli dan Alam Sekitar": "Ministry of Natural Resources and Environment",
    "KEMENTERIAN SUMBER ASLI DAN ALAM SEKITAR": "Ministry of Natural Resources and Environment",
    "Kementerian Perdagangan Antarabangsa dan Industri": "Ministry of International Trade and Industry",
    "KEMENTERIAN PERDAGANGAN ANTARABANGSA DAN INDUSTRI": "Ministry of International Trade and Industry",
    "KEMENTERIAN PERDAGANGAN ANTARABANGSA DAN INDUSTRI (MITI)": "Ministry of International Trade and Industry",
    "Kementerian Perdagangan Dalam Negeri, Koperasi dan Kepenggunaan": "Ministry of Domestic Trade, Co-operatives and Consumerism",
    "KEM. PERDAGANGAN DALAM NEGERI, KOPERASI & KEPENGGUNAAN": "Ministry of Domestic Trade, Co-operatives and Consumerism",
    "Kementerian Kerja Raya": "Ministry of Works",
    "KEMENTERIAN KERJA RAYA": "Ministry of Works",
    "Kementerian Pengangkutan": "Ministry of Transport",
    "KEMENTERIAN PENGANGKUTAN": "Ministry of Transport",
    "Kementerian Tenaga, Teknologi Hijau dan Air": "Ministry of Energy, Green Technology and Water",
    "KEMENTERIAN TENAGA, TEKNOLOGI HIJAU DAN AIR": "Ministry of Energy, Green Technology and Water",
    "Kementerian Sains, Teknologi dan Inovasi": "Ministry of Science, Technology and Innovation",
    "KEMENTERIAN SAINS, TEKNOLOGI DAN INOVASI": "Ministry of Science, Technology and Innovation",
    "Kementerian Pelancongan dan Kebudayaan": "Ministry of Tourism and Culture",
    "KEMENTERIAN PELANCONGAN DAN KEBUDAYAAN": "Ministry of Tourism and Culture",
    "Kementerian Wilayah Persekutuan": "Ministry of Federal Territories",
    "KEMENTERIAN WILAYAH PERSEKUTUAN": "Ministry of Federal Territories",
    "Kementerian Kesihatan": "Ministry of Health",
    "KEMENTERIAN KESIHATAN": "Ministry of Health",
    "Kementerian Kesejahteraan Bandar, Perumahan dan Kerajaan Tempatan": "Ministry of Urban Wellbeing, Housing and Local Government",
    "KEMENTERIAN KESEJAHTERAAN BANDAR, PERUMAHAN DAN KERAJAAN TEMPATAN": "Ministry of Urban Wellbeing, Housing and Local Government",
    "Kementerian Belia dan Sukan": "Ministry of Youth and Sports",
    "KEMENTERIAN BELIA DAN SUKAN": "Ministry of Youth and Sports",
    "Kementerian Sumber Manusia": "Ministry of Human Resources",
    "KEMENTERIAN SUMBER MANUSIA": "Ministry of Human Resources",
    "Kementerian Komunikasi dan Multimedia": "Ministry of Communications and Multimedia",
    "KEMENTERIAN KOMUNIKASI DAN MULTIMEDIA": "Ministry of Communications and Multimedia",
    "Kementerian Pembangunan Wanita, Keluarga dan Masyarakat": "Ministry of Women, Family and Community Development",
    "KEMENTERIAN PEMBANGUNAN WANITA, KELUARGA DAN MASYARAKAT": "Ministry of Women, Family and Community Development",
    "Kementerian Pertahanan": "Ministry of Defence",
    "KEMENTERIAN PERTAHANAN": "Ministry of Defence",
    "Kementerian Dalam Negeri": "Ministry of Home Affairs",
    "KEMENTERIAN DALAM NEGERI": "Ministry of Home Affairs",
    "Kementerian Pendidikan": "Ministry of Education",
    "KEMENTERIAN PENDIDIKAN": "Ministry of Education",
    "Kementerian Pendidikan Tinggi": "Ministry of Higher Education",
    "KEMENTERIAN PENDIDIKAN TINGGI": "Ministry of Higher Education",
    "SIMPANAN LUAR JANGKA": "Contingency Reserve",
}

# Notes per what the 2017 print itself shows.
NOTES = {
    "B.12": "Sebenar (4,467,209,216) is 231.77% of Dipinda (1,927,400,200): includes the "
            "RM2,710,809,216 caruman to Kumpulan Wang Pembangunan (printed ** footnote).",
    "P.70": "Contingency reserve vote, not a ministry; all columns print nil in Lampiran 2.",
    "P.25": "Lampiran 2 vote-total row prints the abbreviated label 'JUMLAH KEM. PERDAGANGAN "
            "DALAM NEGERI, KOPERASI & KEPENGGUNAAN'.",
    "B.06": "Lampiran 1 program 530000 header is omitted in print; aktiviti 530100-530300 "
            "carry the block, program code inferred from the aktiviti prefix.",
}

rows = {}
with open(f"{WH}/fact_opex_maksud.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        code = r["maksud_code"]
        rows[code] = {
            "maksud_code": code,
            "code_num": int(code.split(".")[1]),
            "jenis": {"T": "Tanggungan", "B": "Bekalan"}[code[0]],
            "name_bm": r["maksud_name_bm"],
            "name_en": EN.get(r["maksud_name_bm"], ""),
            "note": NOTES.get(code, ""),
            "year": r["year"],
        }
with open(f"{WH}/fact_devex_maksud.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        code = r["maksud_code"]
        if code == "TOTAL":
            continue
        name = r["jumlah_label_bm"]
        rows[code] = {
            "maksud_code": code,
            "code_num": int(code.split(".")[1]),
            "jenis": "Pembangunan",
            "name_bm": name.title() if name.isupper() else name,
            "name_en": EN.get(name, EN.get(name.title(), "")),
            "note": NOTES.get(code, ""),
            "year": r["year"],
        }

missing = [v["name_bm"] for v in rows.values() if not v["name_en"]]
if missing:
    print("MISSING EN GLOSS:", missing)

with open(f"{WH}/dim_maksud.csv", "w", newline="", encoding="utf-8") as f:
    cw = csv.DictWriter(f, fieldnames=["maksud_code", "code_num", "jenis", "name_bm", "name_en", "note", "year"])
    cw.writeheader()
    for k in sorted(rows, key=lambda c: (c[0], int(c.split(".")[1]))):
        cw.writerow(rows[k])
print(f"dim_maksud.csv: {len(rows)} rows")
