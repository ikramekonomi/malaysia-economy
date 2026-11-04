"use client";

import { useEffect, useState } from "react";
import { DEFAULT_COVERAGE } from "@/lib/api";
import { useCoverage } from "@/lib/useCoverage";
import { Ministry, exportHeadlineUrl, exportMinistryUrl, fetchMinistries } from "@/lib/api";


export default function ExportPage() {
  const cov = useCoverage();
  const MIN_YEAR = cov.min_year;
  const MAX_YEAR = cov.max_year;
  const [yearFrom, setYearFrom] = useState(DEFAULT_COVERAGE.min_year);
  const [yearTo, setYearTo] = useState(DEFAULT_COVERAGE.max_year);
  const [ministries, setMinistries] = useState<Ministry[]>([]);
  const [ministryCode, setMinistryCode] = useState("");

  useEffect(() => {
    fetchMinistries().then((r) => setMinistries(r.rows)).catch(() => {});
  }, []);

  return (
    <div className="mx-auto max-w-3xl px-5 py-10">
      <h1 className="text-2xl font-semibold mb-1">Eksport Data</h1>
      <p className="text-sm opacity-70 mb-6">
        Muat turun jadual ringkasan (headline/curated) mengikut julat tahun. Data
        peringkat butiran (leaf-level, cth. 76,000+ baris perbelanjaan objek PKKP)
        akan datang — lihat Metodologi.
      </p>

      <div className="rounded border p-4 space-y-4" style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
        <div className="flex flex-wrap gap-4">
          <label className="text-sm">
            Tahun dari
            <select
              className="block mt-1 border rounded px-2 py-1"
              style={{ borderColor: "var(--line)" }}
              value={yearFrom}
              onChange={(e) => setYearFrom(Number(e.target.value))}
            >
              {Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i).map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Tahun hingga
            <select
              className="block mt-1 border rounded px-2 py-1"
              style={{ borderColor: "var(--line)" }}
              value={yearTo}
              onChange={(e) => setYearTo(Number(e.target.value))}
            >
              {Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i).map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="pt-2 border-t" style={{ borderColor: "var(--line)" }}>
          <h2 className="font-medium mb-2 text-sm">Jumlah Negara</h2>
          <a
            href={exportHeadlineUrl(yearFrom, yearTo)}
            className="inline-block px-4 py-2 rounded text-sm font-medium text-white"
            style={{ background: "var(--accent)" }}
          >
            Muat turun CSV — Opex/Devex Kasar &amp; Bersih
          </a>
          {yearTo > cov.audited_max_year && (
            <p className="text-xs opacity-70 mt-2">
              FY{cov.audited_max_year + 1} belum mempunyai akaun teraudit: dalam fail ini lajur
              PKKP tahun itu kosong, dan angka MOF (Tinjauan Fiskal, belum teraudit) berada dalam
              lajur *_mof_rm. Jangan cantumkan kedua-duanya dalam satu siri.
            </p>
          )}
        </div>

        <div className="pt-4 border-t" style={{ borderColor: "var(--line)" }}>
          <h2 className="font-medium mb-2 text-sm">Mengikut Kementerian</h2>
          <div className="flex flex-wrap items-end gap-3">
            <select
              className="border rounded px-2 py-1.5 text-sm min-w-[240px]"
              style={{ borderColor: "var(--line)" }}
              value={ministryCode}
              onChange={(e) => setMinistryCode(e.target.value)}
            >
              <option value="">Pilih kementerian…</option>
              {ministries.map((m) => (
                <option key={m.code} value={m.code}>{m.name_bm} ({m.code})</option>
              ))}
            </select>
            <a
              href={ministryCode ? exportMinistryUrl(ministryCode, yearFrom, yearTo) : undefined}
              aria-disabled={!ministryCode}
              className="inline-block px-4 py-2 rounded text-sm font-medium text-white aria-disabled:opacity-40 aria-disabled:pointer-events-none"
              style={{ background: "var(--accent)" }}
            >
              Muat turun CSV
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
