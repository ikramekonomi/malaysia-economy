#!/usr/bin/env python3
"""Build dim_maksud from fact_opex_maksud + fact_devex_maksud (PKKP 2014).

Primary key (maksud_code, year); each year's row records that year's official
BM name as printed. name_en is a gloss, not an official translation.

2014 context: BN-era ministry structure, pre-GST (SST era), RMKe-10 year 4.
49 opex maksud (T.01-T.14 + 35 B votes) and 27 devex votes (26 ministries +
P.70 Simpanan Luar Jangka). Vote-name deltas vs opex: P.41 KEMENTERIAN
PELAJARAN (opex B.41 Kementerian Pendidikan), P.31 KEMENTERIAN PELANCONGAN
(opex B.31 ... dan Kebudayaan), P.32 KEMENTERIAN WILAYAH PERSEKUTUAN DAN
KESEJAHTERAAN BANDAR (opex B.32 Kementerian Wilayah Persekutuan), P.43
KEMENTERIAN PERUMAHAN DAN KERAJAAN TEMPATAN (opex B.43 Kementerian
Kesejahteraan Bandar, Perumahan dan Kerajaan Tempatan). B.12's sebenar
includes the RM1,036,530,784 caruman to Kumpulan Wang Pembangunan (printed
** footnote).
"""
import csv

WH = "/home/claude/pkkp/warehouse2013"

EN = {
    "Peruntukan Diraja Bagi S.P.B. Yang Di-Pertuan Agong": "Royal Provision for HM the Yang di-Pertuan Agong",
    'Yang Dipertua Dewan Rakyat': 'Speaker of the House of Representatives',
    'Yang Dipertua Dewan Negara': 'President of the Senate',
    'Kementerian Pelajaran': 'Ministry of Education',
    'KEMENTERIAN PELAJARAN': 'Ministry of Education (devex vote name)',
    'Kementerian Pendidikan': 'Ministry of Education',
    'KEMENTERIAN WILAYAH PERSEKUTUAN DAN KESEJAHTERAAN BANDAR': 'Ministry of Federal Territories and Urban Wellbeing (devex vote name)',
    'KEMENTERIAN PERDAGANGAN ANTARABANGSA DAN INDUSTRI (MITI)': 'Ministry of International Trade and Industry',
    'KEMENTERIAN PERDAGANGAN DALAM NEGERI, KOPERASI DAN KEPENGGUNAAN': 'Ministry of Domestic Trade, Co-operatives and Consumerism',
    'Kementerian Kesejahteraan Bandar, Perumahan dan Kerajaan Tempatan': 'Ministry of Urban Wellbeing, Housing and Local Government',
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
    "KEMENTERIAN PELANCONGAN": "Ministry of Tourism (and Culture; devex vote printed as Kementerian Pelancongan)",
    "Kementerian Wilayah Persekutuan": "Ministry of Federal Territories",
    "KEMENTERIAN WILAYAH PERSEKUTUAN": "Ministry of Federal Territories",
    "Kementerian Kesihatan": "Ministry of Health",
    "KEMENTERIAN KESIHATAN": "Ministry of Health",
    "Kementerian Kesejahteraan Bandar, Perumahan dan Kerajaan Tempatan": "Ministry of Urban Wellbeing, Housing and Local Government",
    "KEMENTERIAN PERUMAHAN DAN KERAJAAN TEMPATAN": "Ministry of Housing and Local Government (devex vote name)",
    "Kementerian Belia dan Sukan": "Ministry of Youth and Sports",
    "KEMENTERIAN BELIA DAN SUKAN": "Ministry of Youth and Sports",
    "Kementerian Sumber Manusia": "Ministry of Human Resources",
    "KEMENTERIAN SUMBER MANUSIA": "Ministry of Human Resources",
    "Kementerian Komunikasi dan Multimedia": "Ministry of Communications and Multimedia",
    "Kementerian Pengajian Tinggi": "Ministry of Higher Education",
    "KEMENTERIAN KOMUNIKASI DAN MULTIMEDIA": "Ministry of Communications and Multimedia",
    "Kementerian Pembangunan Wanita, Keluarga dan Masyarakat": "Ministry of Women, Family and Community Development",
    "KEMENTERIAN PEMBANGUNAN WANITA, KELUARGA DAN MASYARAKAT": "Ministry of Women, Family and Community Development",
    "Kementerian Pertahanan": "Ministry of Defence",
    "KEMENTERIAN PERTAHANAN": "Ministry of Defence",
    "Kementerian Dalam Negeri": "Ministry of Home Affairs",
    "KEMENTERIAN DALAM NEGERI": "Ministry of Home Affairs",
    "Kementerian Pendidikan": "Ministry of Education",
    "KEMENTERIAN PENDIDIKAN MALAYSIA": "Ministry of Education Malaysia",
    "Kementerian Pendidikan Tinggi": "Ministry of Higher Education",
    "KEMENTERIAN PENGAJIAN TINGGI": "Ministry of Higher Education",
    "SIMPANAN LUAR JANGKA": "Contingency Reserve",
}


EN.update({
    "KEMENTERIAN PENDIDIKAN": "Ministry of Education (devex vote name)",
    "KEMENTERIAN PENERANGAN, KOMUNIKASI DAN KEBUDAYAAN": "Ministry of Information, Communications and Culture (2013 devex vote name)",
    "KEMENTERIAN PENGAJIAN TINGGI": "Ministry of Higher Education",
    "KEMENTERIAN PEMBANGUNAN WANITA, KELUARGA DAN MASYARAKAT": "Ministry of Women, Family and Community Development",
    "Kementerian Komunikasi dan Multimedia": "Ministry of Communications and Multimedia",
    "Kementerian Pengajian Tinggi": "Ministry of Higher Education",
})

NOTES = {
    "B.12": "Peruntukan kepada Kumpulan Wang Terkanun; 2013 Sebenar 4,948,695,753 exceeds Dipinda 2,911,350,000 at 169.98%: includes the RM2,099,876,765 caruman/pindahan lebihan hasil ke Kumpulan Wang Pembangunan (printed ** footnote).",
    "B.11": "Perkhidmatan Am Perbendaharaan: general treasury services vote.",
    "P.70": "Simpanan Luar Jangka (contingency reserve vote), not a ministry.",
    "P.31": "Devex vote printed as KEMENTERIAN PELANCONGAN; the opex vote B.31 prints Kementerian Pelancongan dan Kebudayaan.",
    "P.32": "Devex vote printed as KEMENTERIAN WILAYAH PERSEKUTUAN DAN KESEJAHTERAAN BANDAR; the opex vote B.32 prints Kementerian Wilayah Persekutuan.",
    "P.41": "Devex vote printed KEMENTERIAN PENDIDIKAN; opex vote B.41 prints Kementerian Pendidikan.",
    "P.43": "Devex vote printed as KEMENTERIAN PERUMAHAN DAN KERAJAAN TEMPATAN; the opex vote B.43 prints Kementerian Kesejahteraan Bandar, Perumahan dan Kerajaan Tempatan.",
    "P.24": "Header prints KEMENTERIAN PERDAGANGAN ANTARABANGSA DAN INDUSTRI (MITI); vote total omits the (MITI) suffix.",
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
