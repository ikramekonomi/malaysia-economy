import Link from "next/link";

const CARDS = [
  { href: "/tanya-fiskal", title: "Tanya Fiskal", desc: "Tanya soalan tentang kewangan awam persekutuan dan dapatkan jawapan bersumber." },
  { href: "/papan-pemuka", title: "Papan Pemuka", desc: "Visualisasi opex/devex mengikut tahun dan kementerian." },
  { href: "/eksport-data", title: "Eksport Data", desc: "Muat turun jadual ringkasan mengikut julat tahun." },
  { href: "/metodologi", title: "Metodologi & Sumber", desc: "Bagaimana data disemak, dan had yang diketahui." },
];

export default function Home() {
  return (
    <div className="mx-auto max-w-4xl px-5 py-16">
      <h1 className="text-3xl font-semibold mb-3 tracking-tight">Fiskal Malaysia</h1>
      <p className="text-base opacity-70 mb-10 max-w-2xl">
        Data kewangan awam Persekutuan Malaysia — bermula dengan PKKP (penyata teraudit)
        dan Tinjauan Fiskal MOF — disemak dan boleh dikesan ke sumber asal setiap angka.
      </p>
      <div className="grid sm:grid-cols-2 gap-4">
        {CARDS.map((c) => (
          <Link
            key={c.href}
            href={c.href}
            className="block rounded border p-5 hover:shadow-sm transition-shadow"
            style={{ borderColor: "var(--line)", background: "var(--panel)" }}
          >
            <div className="font-medium mb-1">{c.title}</div>
            <div className="text-sm opacity-70">{c.desc}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
