const SOURCES = [
  {
    name: "PKKP — Penyata Kewangan Kerajaan Persekutuan",
    desc: "Akaun teraudit persekutuan, FY2009–2024, diaudit oleh Ketua Audit Negara.",
    status: "Disahkan",
  },
  {
    name: "Tinjauan Fiskal MOF (& Anggaran Hasil)",
    desc: "Unjuran rasmi Kementerian Kewangan untuk hasil, perbelanjaan, defisit dan hutang.",
    status: "Disahkan (edisi 2025–2026; edisi lebih awal dalam proses)",
  },
];

const CAVEATS = [
  {
    title: "FY2015 — imbasan imej sahaja",
    body: "Jumlah peringkat objek/aktiviti tahun ini adalah OCR-provisional. Angka peringkat kementerian (fact_opex_maksud/fact_devex_maksud) digunakan dan disahkan sepadan dengan jadual fiskal 15-tahun rasmi.",
  },
  {
    title: "FY2019 — anomali cetakan",
    body: "Satu muka surat Lampiran 1 hilang dalam cetakan rasmi kerajaan (antara muka 77–78), menjejaskan butiran dua kementerian (B.05, B.06). Angka peringkat kementerian yang lengkap digunakan; didokumenkan dalam fail pengesahan sumber, bukan pembetulan senyap.",
  },
  {
    title: "FY2014 & FY2019 — Pengajian Tinggi disatukan dengan Pendidikan",
    body: "Kementerian Pengajian Tinggi tiada kod berasingan pada dua tahun ini — disahkan daripada senarai program Kementerian Pendidikan tahun berkenaan. Dianggap termasuk dalam angka Pendidikan; tidak dianggarkan sebagai nombor berasingan.",
  },
  {
    title: "OPEX/DEVEX kasar berbanding bersih",
    body: "Angka \"kasar\" (gross) ialah perbelanjaan sebenar teraudit PKKP. Angka \"bersih\" (net) mengikut konvensyen Tinjauan Fiskal MOF (kasar tolak pindahan ke Kumpulan Wang Pembangunan bagi opex; kasar tolak pemulihan pinjaman bagi devex). Kedua-duanya sah — jangan campurkan tanpa menyatakan asas. DEVEX bersih mempunyai dua penerbit yang disimpan berasingan: angka rasmi MOF (Tinjauan Fiskal edisi 2019-2027, bagi 2015-2024 — setiap tahun daripada edisinya sendiri; sebelum 2015 jadual MOF diterbitkan dalam Laporan Ekonomi, yang belum dimasukkan) dan siri lengkap 2009-2024 Bank Negara Malaysia (Buletin Statistik Bulanan, Jadual 3.1). Ia berbeza dalam lingkungan pembundaran MOF (tidak lebih RM0.6 juta) bagi setiap tahun yang ada pada kedua-duanya, tetapi tidak pernah dicantumkan dalam satu siri.",
  },
  {
    title: "Pecahan perbelanjaan MOF — satu tahun, satu edisi",
    body: "Setiap edisi Tinjauan Fiskal mencetak lima tahun, jadual yang sama untuk satu tahun muncul dalam tiga edisi dan kadangkala berbeza. Setiap tahun diambil daripada edisi yang mencetaknya sebagai angka sebenar terkini (edisinya sendiri), dan angka edisi kemudian dicatat dalam lajur restated_in. Dua perubahan klasifikasi perlu diketahui: \"Pertanian dan pembangunan luar bandar\" menjadi \"Pertanian\" mulai edisi 2022 (disimpan sebagai baris berasingan), dan edisi 2024 memindahkan kira-kira RM1.1–1.2 bilion setahun daripada Pentadbiran Am ke Perumahan — maka Perumahan melonjak pada 2022 kerana klasifikasi, bukan perbelanjaan.",
  },
  {
    title: "FY2020–2022 — Kumpulan Wang COVID-19 dan baki keseluruhan",
    body: "Perbelanjaan melalui Kumpulan Wang COVID-19 (RM38.0 bilion 2020, RM37.7 bilion 2021, RM31.0 bilion 2022) berada di luar perbelanjaan mengurus dan pembangunan, jadi ia ditunjukkan sebagai baris tersendiri — tanpanya defisit tahun-tahun itu kelihatan jauh lebih kecil. Angka dibaca hingga sen daripada Lampiran 3 setiap jilid PKKP. Dana ini belum wujud sebelum 2020 (bukan sifar — tiada). Baki keseluruhan mengikut definisi MOF dan sepadan dengan angka terbitan MOF; PKKP mencetak baki keseluruhan dengan definisi berbeza (semua terimaan Kumpulan Wang Pembangunan ditolak, bukan pemulihan pinjaman sahaja), jadi kedua-duanya boleh berbeza sehingga RM1.9 bilion.",
  },
];

export default function MethodologyPage() {
  return (
    <div className="mx-auto max-w-3xl px-5 py-10 space-y-10">
      <div>
        <h1 className="text-2xl font-semibold mb-1">Metodologi &amp; Sumber</h1>
        <p className="text-sm opacity-70">
          Fiskal Malaysia ialah projek data awam bebas dan tidak rasmi. Setiap angka
          dikesan kembali ke halaman dokumen sumber, disemak terhadap jumlah cetakan
          sumber itu sendiri, dan disahkan semula oleh proses pengesahan bebas.
        </p>
      </div>

      <section>
        <h2 className="font-medium mb-3">Sumber data</h2>
        <div className="space-y-3">
          {SOURCES.map((s) => (
            <div key={s.name} className="rounded border p-4" style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium text-sm">{s.name}</span>
                <span
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
                >
                  {s.status}
                </span>
              </div>
              <p className="text-sm opacity-70 mt-1">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="font-medium mb-3">Had data yang diketahui</h2>
        <div className="space-y-3">
          {CAVEATS.map((c) => (
            <div key={c.title} className="rounded border-l-4 p-4" style={{ borderColor: "var(--gold)", background: "var(--panel)" }}>
              <div className="font-medium text-sm">{c.title}</div>
              <p className="text-sm opacity-70 mt-1">{c.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="font-medium mb-3">Bagaimana kami menyemak</h2>
        <p className="text-sm opacity-70">
          Setiap sumber disemak terhadap jumlah cetakannya sendiri, kemudian dijalani
          semakan bebas oleh pihak yang tidak terlibat dalam pengekstrakan asal.
          Percanggahan tidak pernah dibetulkan secara senyap — didokumenkan dengan
          bukti dalam fail pengesahan sumber berkenaan.
        </p>
      </section>
    </div>
  );
}
