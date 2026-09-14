import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Fiskal Malaysia",
  description:
    "Data kewangan awam Persekutuan Malaysia — PKKP dan Tinjauan Fiskal, disemak dan boleh disahkan.",
};

const NAV = [
  { href: "/tanya-fiskal", label: "Tanya Fiskal" },
  { href: "/papan-pemuka", label: "Papan Pemuka" },
  { href: "/eksport-data", label: "Eksport Data" },
  { href: "/metodologi", label: "Metodologi & Sumber" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="ms"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <header className="border-b" style={{ borderColor: "var(--line)" }}>
          <div className="mx-auto max-w-6xl px-5 flex items-center justify-between h-16">
            <Link href="/" className="font-semibold text-lg tracking-tight">
              Fiskal <span style={{ color: "var(--accent)" }}>Malaysia</span>
            </Link>
            <nav className="flex items-center gap-6 text-sm">
              {NAV.map((item) => (
                <Link key={item.href} href={item.href} className="hover:opacity-70">
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer
          className="border-t text-xs px-5 py-6 text-center opacity-70"
          style={{ borderColor: "var(--line)" }}
        >
          Projek data awam bebas dan tidak rasmi. Bukan penerbitan kerajaan. Setiap
          angka dikesan kembali ke halaman dokumen sumbernya — lihat{" "}
          <Link href="/metodologi" className="underline">
            Metodologi &amp; Sumber
          </Link>
          .
        </footer>
      </body>
    </html>
  );
}
