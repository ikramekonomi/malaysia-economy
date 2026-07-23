#!/usr/bin/env python3
"""Build dim_maksud from fact_opex_maksud + fact_devex_maksud, with English glosses.

Design for cross-year loading: primary key (maksud_code, year). Ministries rename/merge
over time; each year's row records that year's official BM name. name_en is a gloss,
not an official translation.

2018 context: the May 2018 change of government restructured ministries mid-year.
The volume's own print carries the evidence (new votes with nil Anggaran Asal,
votes whose Dipinda collapses after functions moved); notes below record what is
printed, per vote.
"""
import csv

WH = "/home/claude/pkkp/warehouse2018"

EN = {
    "Peruntukan Diraja Bagi S.P.B. Yang di-Pertuan Agong": "Royal Provision for HM the Yang di-Pertuan Agong",
    "Elaun-elaun Diraja": "Royal Allowances",
    "Ketua Hakim Negara, Hakim Besar dan Hakim": "Chief Justice, Chief Judges and Judges",
    "Ketua Audit Negara": "Auditor General",
    "Yang di-Pertua Dewan Rakyat": "Speaker of the House of Representatives",
    "Yang di-Pertua Dewan Negara": "President of the Senate",
    "Suruhanjaya Pilihan Raya": "Election Commission",
    "Suruhanjaya Perkhidmatan Kehakiman dan Perundangan": "Judicial and Legal Service Commission",
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
    "Kementerian Hal Ehwal Ekonomi": "Ministry of Economic Affairs",
    "KEMENTERIAN HAL EHWAL EKONOMI": "Ministry of Economic Affairs",
    "Kementerian Industri Utama": "Ministry of Primary Industries",
    "KEMENTERIAN INDUSTRI UTAMA": "Ministry of Primary Industries",
    "Kementerian Pertanian dan Industri Asas Tani": "Ministry of Agriculture and Agro-based Industry",
    "KEMENTERIAN PERTANIAN DAN INDUSTRI ASAS TANI": "Ministry of Agriculture and Agro-based Industry",
    "Kementerian Pembangunan Luar Bandar": "Ministry of Rural Development",
    "KEMENTERIAN PEMBANGUNAN LUAR BANDAR": "Ministry of Rural Development",
    "Kementerian Air, Tanah dan Sumber Asli": "Ministry of Water, Land and Natural Resources",
    "KEMENTERIAN AIR, TANAH DAN SUMBER ASLI": "Ministry of Water, Land and Natural Resources",
    "Kementerian Perdagangan Antarabangsa dan Industri": "Ministry of International Trade and Industry",
    "KEMENTERIAN PERDAGANGAN ANTARABANGSA DAN INDUSTRI": "Ministry of International Trade and Industry",
    "KEMENTERIAN PERDAGANGAN ANTARABANGSA DAN INDUSTRI (MITI)": "Ministry of International Trade and Industry",
    "Kementerian Perdagangan Dalam Negeri dan Hal Ehwal Pengguna": "Ministry of Domestic Trade and Consumer Affairs",
    "KEMENTERIAN PERDAGANGAN DALAM NEGERI DAN HAL EHWAL PENGGUNA": "Ministry of Domestic Trade and Consumer Affairs",
    "Kementerian Pembangunan Usahawan": "Ministry of Entrepreneur Development",
    "KEMENTERIAN PEMBANGUNAN USAHAWAN": "Ministry of Entrepreneur Development",
    "Kementerian Kerja Raya": "Ministry of Works",
    "KEMENTERIAN KERJA RAYA": "Ministry of Works",
    "Kementerian Pengangkutan": "Ministry of Transport",
    "KEMENTERIAN PENGANGKUTAN": "Ministry of Transport",
    "Kementerian Tenaga, Teknologi Hijau dan Air": "Ministry of Energy, Green Technology and Water",
    "KEMENTERIAN TENAGA, TEKNOLOGI HIJAU DAN AIR": "Ministry of Energy, Green Technology and Water",
    "Kementerian Tenaga, Sains, Teknologi, Alam Sekitar dan Perubahan Iklim": "Ministry of Energy, Science, Technology, Environment and Climate Change",
    "KEMENTERIAN TENAGA, SAINS, TEKNOLOGI, ALAM SEKITAR DAN PERUBAHAN IKLIM": "Ministry of Energy, Science, Technology, Environment and Climate Change",
    "Kementerian Pelancongan, Seni dan Budaya": "Ministry of Tourism, Arts and Culture",
    "KEMENTERIAN PELANCONGAN, SENI DAN BUDAYA": "Ministry of Tourism, Arts and Culture",
    "Kementerian Wilayah Persekutuan": "Ministry of Federal Territories",
    "KEMENTERIAN WILAYAH PERSEKUTUAN": "Ministry of Federal Territories",
    "Kementerian Kesihatan": "Ministry of Health",
    "KEMENTERIAN KESIHATAN": "Ministry of Health",
    "Kementerian Perumahan dan Kerajaan Tempatan": "Ministry of Housing and Local Government",
    "KEMENTERIAN PERUMAHAN DAN KERAJAAN TEMPATAN": "Ministry of Housing and Local Government",
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

# Machinery-of-government notes, per what the 2018 print itself shows.
NOTES = {
    "B.15": "New vote created mid-year 2018 (Kementerian Hal Ehwal Ekonomi): Anggaran Asal prints nil; provision arises wholly by Anggaran Dipinda.",
    "P.15": "New vote created mid-year 2018 (Kementerian Hal Ehwal Ekonomi); development estimates arise by virement.",
    "B.26": "New vote created mid-year 2018 (Kementerian Pembangunan Usahawan): Anggaran Asal prints nil.",
    "P.26": "New vote created mid-year 2018 (Kementerian Pembangunan Usahawan).",
    "B.20": "Vote renamed Kementerian Industri Utama in the mid-2018 restructuring; Anggaran Dipinda (172.9m) is well below Asal (441.1m) as functions moved.",
    "B.22": "Anggaran Dipinda (2.68b) far below Asal (5.61b): rural-development functions moved in the mid-2018 restructuring.",
    "B.23": "Vote restructured as Kementerian Air, Tanah dan Sumber Asli in mid-2018; Dipinda exceeds Asal as water functions moved in.",
    "B.29": "Kementerian Tenaga, Teknologi Hijau dan Air wound down in the mid-2018 restructuring; Dipinda (154.9m) far below Asal (254.0m).",
    "B.30": "Vote restructured as Kementerian Tenaga, Sains, Teknologi, Alam Sekitar dan Perubahan Iklim (MESTECC) in mid-2018.",
    "P.70": "Contingency reserve vote, not a ministry.",
    "B.12": "Sebenar (3.59b) exceeds Dipinda (1.66b) at 215.45%: includes the RM1,922,069,620 caruman to Kumpulan Wang Pembangunan (printed *** footnote).",
    "B.11": "Sebenar includes RM2,839,225,279 SPV guaranteed-loan repayment grants (printed ** footnote).",
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
