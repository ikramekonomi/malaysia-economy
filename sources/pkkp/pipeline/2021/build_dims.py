#!/usr/bin/env python3
"""Build dim_maksud from fact_opex_maksud + fact_devex_maksud, with English glosses.

Design for cross-year loading: primary key (maksud_code, year). Ministries rename/merge
over time; each year's row records that year's official BM name. name_en is a gloss,
not an official translation.
"""
import csv

WH = "/home/claude/pkkp/warehouse2021"

EN = {
    "Peruntukan Diraja Bagi S.P.B. Yang Di-Pertuan Agong": "Royal Provision for HM the Yang di-Pertuan Agong",
    "Elaun-elaun Diraja": "Royal Allowances",
    "Ketua Hakim Negara, Hakim Besar dan Hakim": "Chief Justice, Chief Judges and Judges",
    "Ketua Audit Negara": "Auditor General",
    "Yang Di-Pertua Dewan Rakyat": "Speaker of the House of Representatives",
    "Yang Di-Pertua Dewan Negara": "President of the Senate",
    "Suruhanjaya Pilihan Raya": "Election Commission",
    "Suruhanjaya Perkhidmatan Kehakiman dan Perundangan": "Judicial and Legal Service Commission",
    "Suruhanjaya Perkhidmatan Awam": "Public Service Commission",
    "Suruhanjaya Perkhidmatan Pendidikan": "Education Service Commission",
    "Suruhanjaya Pasukan Polis": "Police Force Commission",
    "Perbendaharaan": "Treasury",
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
    "PERBENDAHARAAN": "Treasury",
    "Perkhidmatan Am Perbendaharaan": "Treasury General Services",
    "Peruntukan kepada Kumpulan Wang Terkanun": "Contributions to Statutory Funds",
    "Kementerian Luar Negeri": "Ministry of Foreign Affairs",
    "KEMENTERIAN LUAR NEGERI": "Ministry of Foreign Affairs",
    "Kementerian Perpaduan Negara": "Ministry of National Unity",
    "KEMENTERIAN PERPADUAN NEGARA": "Ministry of National Unity",
    "Kementerian Ekonomi": "Ministry of Economy",
    "KEMENTERIAN EKONOMI": "Ministry of Economy",
    "Kementerian Perladangan dan Komoditi": "Ministry of Plantation and Commodities",
    "KEMENTERIAN PERLADANGAN DAN KOMODITI": "Ministry of Plantation and Commodities",
    "Kementerian Pertanian dan Keterjaminan Makanan": "Ministry of Agriculture and Food Security",
    "KEMENTERIAN PERTANIAN DAN KETERJAMINAN MAKANAN": "Ministry of Agriculture and Food Security",
    "Kementerian Kemajuan Desa dan Wilayah": "Ministry of Rural and Regional Development",
    "KEMENTERIAN KEMAJUAN DESA DAN WILAYAH": "Ministry of Rural and Regional Development",
    "Kementerian Sumber Asli dan Kelestarian Alam": "Ministry of Natural Resources and Environmental Sustainability",
    "KEMENTERIAN SUMBER ASLI DAN KELESTARIAN ALAM": "Ministry of Natural Resources and Environmental Sustainability",
    "Kementerian Pelaburan, Perdagangan dan Industri": "Ministry of Investment, Trade and Industry",
    "KEMENTERIAN PELABURAN, PERDAGANGAN DAN INDUSTRI": "Ministry of Investment, Trade and Industry",
    "Kementerian Perdagangan Dalam Negeri dan Kos Sara Hidup": "Ministry of Domestic Trade and Cost of Living",
    "KEMENTERIAN PERDAGANGAN DALAM NEGERI DAN KOS SARA HIDUP": "Ministry of Domestic Trade and Cost of Living",
    "Kementerian Pembangunan Usahawan dan Koperasi": "Ministry of Entrepreneur and Cooperatives Development",
    "KEMENTERIAN PEMBANGUNAN USAHAWAN DAN KOPERASI": "Ministry of Entrepreneur and Cooperatives Development",
    "Kementerian Kerja Raya": "Ministry of Works",
    "KEMENTERIAN KERJA RAYA": "Ministry of Works",
    "Kementerian Pengangkutan": "Ministry of Transport",
    "KEMENTERIAN PENGANGKUTAN": "Ministry of Transport",
    "Kementerian Sains, Teknologi dan Inovasi": "Ministry of Science, Technology and Innovation",
    "KEMENTERIAN SAINS, TEKNOLOGI DAN INOVASI": "Ministry of Science, Technology and Innovation",
    "Kementerian Pelancongan, Seni dan Budaya": "Ministry of Tourism, Arts and Culture",
    "KEMENTERIAN PELANCONGAN, SENI DAN BUDAYA": "Ministry of Tourism, Arts and Culture",
    "Kementerian Peralihan Tenaga dan Transformasi Air": "Ministry of Energy Transition and Water Transformation",
    "KEMENTERIAN PERALIHAN TENAGA DAN TRANFORMASI AIR": "Ministry of Energy Transition and Water Transformation",
    "Kementerian Kesihatan": "Ministry of Health",
    "KEMENTERIAN KESIHATAN": "Ministry of Health",
    "Kementerian Perumahan dan Kerajaan Tempatan": "Ministry of Housing and Local Government",
    "KEMENTERIAN PERUMAHAN DAN KERAJAAN TEMPATAN": "Ministry of Housing and Local Government",
    "Kementerian Belia dan Sukan": "Ministry of Youth and Sports",
    "KEMENTERIAN BELIA DAN SUKAN": "Ministry of Youth and Sports",
    "Kementerian Sumber Manusia": "Ministry of Human Resources",
    "KEMENTERIAN SUMBER MANUSIA": "Ministry of Human Resources",
    "Kementerian Komunikasi": "Ministry of Communications",
    "KEMENTERIAN KOMUNIKASI": "Ministry of Communications",
    "Kementerian Pembangunan Wanita, Keluarga dan Masyarakat": "Ministry of Women, Family and Community Development",
    "KEMENTERIAN PEMBANGUNAN WANITA, KELUARGA DAN MASYARAKAT": "Ministry of Women, Family and Community Development",
    "Kementerian Digital": "Ministry of Digital",
    "KEMENTERIAN DIGITAL": "Ministry of Digital",
    "Kementerian Pertahanan": "Ministry of Defence",
    "KEMENTERIAN PERTAHANAN": "Ministry of Defence",
    "Kementerian Dalam Negeri": "Ministry of Home Affairs",
    "KEMENTERIAN DALAM NEGERI": "Ministry of Home Affairs",
    "Kementerian Pendidikan": "Ministry of Education",
    "KEMENTERIAN PENDIDIKAN": "Ministry of Education",
    "Kementerian Pendidikan Tinggi": "Ministry of Higher Education",
    "KEMENTERIAN PENDIDIKAN TINGGI": "Ministry of Higher Education",
    "KEMENTERIAN WILAYAH PERSEKUTUAN": "Ministry of Federal Territories",
    "SIMPANAN LUAR JANGKA": "Contingency Reserve",
    # --- 2022-volume ministry names (pre-Dec-2022 machinery of government) ---
    "Suruhanjaya Perkhidmatan Pelajaran": "Education Service Commission",
    "Kementerian Perusahaan Perladangan dan Komoditi": "Ministry of Plantation Industries and Commodities",
    "Kementerian Perusahaan Perladangan Dan Komoditi": "Ministry of Plantation Industries and Commodities",
    "KEMENTERIAN PERUSAHAAN PERLADANGAN DAN KOMODITI": "Ministry of Plantation Industries and Commodities",
    "Kementerian Pertanian dan Industri Makanan": "Ministry of Agriculture and Food Industries",
    "Kementerian Pertanian Dan Industri Makanan": "Ministry of Agriculture and Food Industries",
    "KEMENTERIAN PERTANIAN DAN INDUSTRI MAKANAN": "Ministry of Agriculture and Food Industries",
    "Kementerian Pembangunan Luar Bandar": "Ministry of Rural Development",
    "KEMENTERIAN PEMBANGUNAN LUAR BANDAR": "Ministry of Rural Development",
    "Kementerian Tenaga dan Sumber Asli": "Ministry of Energy and Natural Resources",
    "Kementerian Tenaga Dan Sumber Asli": "Ministry of Energy and Natural Resources",
    "KEMENTERIAN TENAGA DAN SUMBER ASLI": "Ministry of Energy and Natural Resources",
    "Kementerian Perdagangan Antarabangsa dan Industri": "Ministry of International Trade and Industry",
    "Kementerian Perdagangan Antarabangsa Dan Industri": "Ministry of International Trade and Industry",
    "KEMENTERIAN PERDAGANGAN ANTARABANGSA DAN INDUSTRI": "Ministry of International Trade and Industry",
    "Kementerian Perdagangan Dalam Negeri dan Hal Ehwal Pengguna": "Ministry of Domestic Trade and Consumer Affairs",
    "Kementerian Perdagangan Dalam Negeri Dan Hal Ehwal Pengguna": "Ministry of Domestic Trade and Consumer Affairs",
    "KEMENTERIAN PERDAGANGAN DALAM NEGERI DAN HAL EHWAL PENGGUNA": "Ministry of Domestic Trade and Consumer Affairs",
    "Kementerian Komunikasi dan Multimedia": "Ministry of Communications and Multimedia",
    "Kementerian Komunikasi Dan Multimedia": "Ministry of Communications and Multimedia",
    "KEMENTERIAN KOMUNIKASI DAN MULTIMEDIA": "Ministry of Communications and Multimedia",
    "Kementerian Wilayah Persekutuan": "Ministry of Federal Territories",
    # --- 2023-volume ministry names absent from the 2024 gloss dict ---
    "Kementerian Sumber Asli, Alam Sekitar dan Perubahan Iklim": "Ministry of Natural Resources, Environment and Climate Change",
    "Kementerian Sumber Asli, Alam Sekitar Dan Perubahan Iklim": "Ministry of Natural Resources, Environment and Climate Change",
    "KEMENTERIAN SUMBER ASLI, ALAM SEKITAR DAN PERUBAHAN IKLIM": "Ministry of Natural Resources, Environment and Climate Change",
    "Kementerian Komunikasi dan Digital": "Ministry of Communications and Digital",
    "Kementerian Komunikasi Dan Digital": "Ministry of Communications and Digital",
    "KEMENTERIAN KOMUNIKASI DAN DIGITAL": "Ministry of Communications and Digital",
    "Kementerian Alam Sekitar dan Air": "Ministry of Environment and Water",
    "Kementerian Alam Sekitar Dan Air": "Ministry of Environment and Water",
    "KEMENTERIAN ALAM SEKITAR DAN AIR": "Ministry of Environment and Water",
    "Kementerian Pengajian Tinggi": "Ministry of Higher Education",
    "KEMENTERIAN PENGAJIAN TINGGI": "Ministry of Higher Education",
    # --- 2021-volume vote names absent from later gloss dicts ---
    "KEMENTERIAN HAL EHWAL EKONOMI": "Ministry of Economic Affairs",
    "Kementerian Hal Ehwal Ekonomi": "Ministry of Economic Affairs",
    "KEMENTERIAN TENAGA, TEKNOLOGI HIJAU DAN AIR": "Ministry of Energy, Green Technology and Water",
    "Kementerian Tenaga, Teknologi Hijau Dan Air": "Ministry of Energy, Green Technology and Water",
    "Kementerian Tenaga, Teknologi Hijau dan Air": "Ministry of Energy, Green Technology and Water",
    "KEMENTERIAN PERDAGANGAN ANTARABANGSA DAN INDUSTRI (MITI)": "Ministry of International Trade and Industry",
    "Kementerian Perdagangan Antarabangsa Dan Industri (Miti)": "Ministry of International Trade and Industry",
    "JABATAN PERKHIDMATAN AWAM": "Public Service Department",
}

NOTES = {
    "P.70": "Contingency reserve vote, not a ministry.",
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
