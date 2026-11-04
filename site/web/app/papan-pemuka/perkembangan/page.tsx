"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchComponentSeries, fetchComponents, formatRM } from "@/lib/api";
import DashboardSubnav from "@/components/DashboardSubnav";
import SourceCitation from "@/components/SourceCitation";
import { useCoverage } from "@/lib/useCoverage";


const COMPONENT_GROUPS: { group: string; options: { key: string; label: string }[] }[] = [
  {
    group: "Hasil",
    options: [
      { key: "revenue_total", label: "Jumlah Hasil — teraudit (PKKP)" },
      { key: "revenue_mof", label: "Jumlah Hasil — MOF, 2015-2025" },
      { key: "income_tax", label: "Cukai Pendapatan" },
    ],
  },
  {
    group: "Perbelanjaan Mengurus",
    options: [
      { key: "opex_net", label: "Jumlah OPEX (bersih) — teraudit (PKKP)" },
      { key: "opex_mof", label: "Jumlah OPEX (bersih) — MOF, 2015-2025" },
      { key: "opex_gross", label: "Jumlah OPEX (kasar)" },
      { key: "opex_component_emoluments", label: "Emolumen" },
      { key: "opex_component_retirement_charges", label: "Bayaran Persaraan" },
      { key: "opex_component_debt_service", label: "Bayaran Khidmat Hutang" },
      { key: "opex_component_supplies_services", label: "Perkhidmatan dan Bekalan" },
      { key: "opex_component_subsidies_social_assistance", label: "Subsidi dan Bantuan Sosial" },
      { key: "opex_component_asset_acquisition", label: "Pembelian Aset" },
      { key: "opex_component_refunds_writeoffs", label: "Bayaran Balik dan Hapus Kira" },
      { key: "opex_component_grants_statutory_bodies", label: "Pemberian kepada Badan Berkanun" },
    ],
  },
  {
    group: "Perbelanjaan Pembangunan",
    options: [
      { key: "devex_net_bnm", label: "Jumlah DEVEX (bersih) — BNM, 2009-2025" },
      { key: "devex_net", label: "Jumlah DEVEX (bersih) — MOF, 2015-2025" },
      { key: "devex_gross", label: "Jumlah DEVEX (kasar)" },
      { key: "devex_sector_economic", label: "Sektor Ekonomi" },
      { key: "devex_sector_social", label: "Sektor Sosial" },
      { key: "devex_sector_security", label: "Sektor Keselamatan" },
      { key: "devex_sector_general_admin", label: "Pentadbiran Am" },
    ],
  },
  {
    group: "Lain-lain & Baki",
    options: [
      { key: "covid_fund", label: "Kumpulan Wang COVID-19" },
      { key: "overall_balance", label: "Baki Keseluruhan (definisi MOF, dari angka teraudit)" },
      { key: "overall_balance_mof", label: "Baki Keseluruhan — seperti dicetak MOF, 2015-2025" },
    ],
  },
];

const LABEL_BY_KEY = Object.fromEntries(
  COMPONENT_GROUPS.flatMap((g) => g.options.map((o) => [o.key, o.label]))
);

// The 3.1/3.2/3.3-sourced components only cover the years the ingested Tinjauan Fiskal
// appendices do (2015 onward; earlier years sat in the Laporan Ekonomi) -- everything else in the picker runs the full
// 2009-2024 warehouse range. Keep this in sync with sources/mof-fiscal-outlook's
// ingested coverage; it only affects the shaded "no data" band, never a silent gap.
const LIMITED_COVERAGE = new Set(
  COMPONENT_GROUPS.flatMap((g) => g.options.map((o) => o.key)).filter(
    (k) => k.startsWith("opex_component_") || k.startsWith("devex_sector_")
  )
);
const LIMITED_RANGE: [number, number] = [2015, 2025];

// Net DEVEX has two publishers, kept as two separate series (curated/README.md). MOF's own
// figure exists only for the Tinjauan Fiskal editions ingested so far, so its years are
// scattered rather than a range; BNM's is complete. Each is plotted alone -- the gaps in
// the MOF series are shown as gaps, never filled from BNM.
const SPARSE_NOTES: Record<string, string> = {
  devex_net:
    "Angka MOF (Tinjauan Fiskal, sebenar rasmi) bagi 2015-2025, setiap tahun daripada edisinya " +
    "sendiri. Sebelum 2015 MOF menerbitkan jadual ini dalam Laporan Ekonomi, yang belum " +
    "dimasukkan — untuk siri lengkap 2009-2025, pilih \"Jumlah DEVEX (bersih) — BNM\". " +
    "Kedua-dua penerbit berbeza dalam lingkungan pembundaran MOF (RM1 juta), tetapi ia dua " +
    "penerbitan berasingan dan tidak dicantumkan dalam satu garis.",
  revenue_mof:
    "Angka sebenar rasmi MOF (Tinjauan Fiskal), satu edisi setiap tahun — merangkumi 2025, " +
    "yang belum mempunyai akaun teraudit. Angka MOF boleh dipinda dalam edisi kemudian; " +
    "untuk angka teraudit, pilih \"Jumlah Hasil — teraudit (PKKP)\".",
  opex_mof:
    "Angka sebenar rasmi MOF (Tinjauan Fiskal), satu edisi setiap tahun — merangkumi 2025, " +
    "yang belum mempunyai akaun teraudit. Untuk angka teraudit, pilih \"Jumlah OPEX (bersih) — " +
    "teraudit (PKKP)\". Kedua-dua siri berbeza dalam lingkungan pembundaran MOF.",
  overall_balance_mof:
    "Baki keseluruhan seperti dicetak MOF (Tinjauan Fiskal), satu edisi setiap tahun — " +
    "merangkumi 2025. Nilai negatif ialah defisit.",
  devex_net_bnm:
    "Siri lengkap daripada Bank Negara Malaysia (Buletin Statistik Bulanan, Jadual 3.1). " +
    "Penerbit berbeza daripada angka kasar PKKP teraudit; untuk angka rasmi MOF, pilih " +
    "\"Jumlah DEVEX (bersih) — MOF\".",
};

// Series built on the audited PKKP accounts: they end at the last audited year, and the
// years after it are a known gap (accounts not yet published), said so on the chart.
const AUDITED_SERIES = new Set(["revenue_total", "income_tax", "opex_net", "opex_gross",
  "devex_gross", "covid_fund", "overall_balance"]);

export default function PerkembanganPage() {
  const cov = useCoverage();
  const MIN_YEAR = cov.min_year;
  const MAX_YEAR = cov.max_year;
  const [componentKey, setComponentKey] = useState("opex_component_emoluments");
  const [availableKeys, setAvailableKeys] = useState<Set<string> | null>(null);
  const [data, setData] = useState<{ year: number; amount_rm: number | null }[]>([]);
  const [citations, setCitations] = useState<{ table: string; basis?: string }[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchComponents()
      .then((r) => setAvailableKeys(new Set(r.rows.map((row) => row.component_key))))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setError(null);
    let stale = false;
    fetchComponentSeries(componentKey, MIN_YEAR, MAX_YEAR)
      .then((r) => {
        if (stale) return;
        setData(
          r.rows.map((row) => ({
            year: row.year,
            amount_rm: row.amount_rm === null ? null : row.amount_rm / 1e6,
          }))
        );
        setCitations(r.citations as { table: string; basis?: string }[]);
      })
      .catch((e) => {
        if (!stale) setError(String(e));
      });
    return () => {
      stale = true;
    };
  }, [componentKey, MIN_YEAR, MAX_YEAR]);

  const isLimited = LIMITED_COVERAGE.has(componentKey);
  const sparseNote = SPARSE_NOTES[componentKey];
  const auditedGap = AUDITED_SERIES.has(componentKey) && MAX_YEAR > cov.audited_max_year
    ? `Siri ini daripada akaun teraudit PKKP, yang meliputi hingga ${cov.audited_max_year}. ` +
      `${cov.audited_max_year + 1}${MAX_YEAR > cov.audited_max_year + 1 ? `-${MAX_YEAR}` : ""} ` +
      `belum diaudit, jadi tiada titik — bukan sifar. Untuk angka MOF tahun itu, pilih siri "— MOF".`
    : null;
  // latest year that actually has a figure -- a trailing null is a gap, not a value
  const latest = [...data].reverse().find((d) => d.amount_rm !== null);

  const chartData = useMemo(() => {
    return Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i).map((year) => {
      const row = data.find((d) => d.year === year);
      return { year, amount_rm: row?.amount_rm ?? null };
    });
  }, [data, MIN_YEAR, MAX_YEAR]);

  return (
    <div className="mx-auto max-w-6xl px-5 py-10">
      <h1 className="text-2xl font-semibold mb-1">Papan Pemuka Fiskal</h1>
      <p className="text-sm opacity-70 mb-4">Bagaimana satu komponen berkembang dari semasa ke semasa.</p>
      <DashboardSubnav />

      <div className="flex flex-wrap items-end gap-4 mb-6 p-4 rounded border" style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
        <label className="text-sm flex-1 min-w-[260px]">
          Komponen
          <select
            className="block mt-1 border rounded px-2 py-1 w-full"
            style={{ borderColor: "var(--line)" }}
            value={componentKey}
            onChange={(e) => setComponentKey(e.target.value)}
          >
            {COMPONENT_GROUPS.map((g) => (
              <optgroup key={g.group} label={g.group}>
                {g.options
                  .filter((o) => availableKeys === null || availableKeys.has(o.key))
                  .map((o) => (
                    <option key={o.key} value={o.key}>{o.label}</option>
                  ))}
              </optgroup>
            ))}
          </select>
        </label>
      </div>

      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      <div className="rounded border p-4" style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
        <h2 className="font-medium mb-1">{LABEL_BY_KEY[componentKey] ?? componentKey}</h2>
        {sparseNote && <p className="text-xs opacity-70 mb-2">{sparseNote}</p>}
        {auditedGap && <p className="text-xs opacity-70 mb-2">{auditedGap}</p>}
        {isLimited && (
          <p className="text-xs opacity-70 mb-2">
            Pecahan ini tersedia untuk {LIMITED_RANGE[0]}-{LIMITED_RANGE[1]} (edisi Tinjauan
            Fiskal 2019-2027, setiap tahun daripada edisinya sendiri). Sebelum 2015 MOF
            menerbitkannya dalam Laporan Ekonomi — jurang itu bukan data hilang secara senyap.
            Perhatian: klasifikasi sektor berubah antara edisi (cth. Perumahan pada 2022), sila
            lihat Metodologi.
          </p>
        )}
        <div style={{ width: "100%", height: 360 }}>
          <ResponsiveContainer>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis dataKey="year" />
              <YAxis tickFormatter={(v) => v.toLocaleString()} width={70} />
              <Tooltip
                formatter={(v) => (v === null ? "tiada data" : `RM${Number(v).toLocaleString("ms-MY")} juta`)}
              />
              <Line
                type="monotone"
                dataKey="amount_rm"
                stroke="#1F6F5C"
                strokeWidth={2}
                dot={chartData.some((d, i) => d.amount_rm !== null
                  && (chartData[i - 1]?.amount_rm ?? null) === null
                  && (chartData[i + 1]?.amount_rm ?? null) === null) ? { r: 3 } : false}
                connectNulls={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        {latest && latest.amount_rm !== null && (
          <p className="text-sm mt-2">
            {latest.year}: <span className="font-semibold tabular-nums">{formatRM(latest.amount_rm * 1e6, "juta")}</span>
          </p>
        )}
        <SourceCitation citations={citations} />
      </div>
    </div>
  );
}
