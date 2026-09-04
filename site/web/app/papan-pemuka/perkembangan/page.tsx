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

const MIN_YEAR = 2009;
const MAX_YEAR = 2024;

const COMPONENT_GROUPS: { group: string; options: { key: string; label: string }[] }[] = [
  {
    group: "Hasil",
    options: [
      { key: "revenue_total", label: "Jumlah Hasil" },
      { key: "income_tax", label: "Cukai Pendapatan" },
    ],
  },
  {
    group: "Perbelanjaan Mengurus",
    options: [
      { key: "opex_net", label: "Jumlah OPEX (bersih)" },
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
      { key: "devex_net", label: "Jumlah DEVEX (bersih)" },
      { key: "devex_gross", label: "Jumlah DEVEX (kasar)" },
      { key: "devex_sector_economic", label: "Sektor Ekonomi" },
      { key: "devex_sector_social", label: "Sektor Sosial" },
      { key: "devex_sector_security", label: "Sektor Keselamatan" },
      { key: "devex_sector_general_admin", label: "Pentadbiran Am" },
    ],
  },
];

const LABEL_BY_KEY = Object.fromEntries(
  COMPONENT_GROUPS.flatMap((g) => g.options.map((o) => [o.key, o.label]))
);

// The 3.1/3.2/3.3-sourced components only cover the years the ingested Tinjauan Fiskal
// appendix does (2017-2021 today) -- everything else in the picker runs the full
// 2009-2024 warehouse range. Keep this in sync with sources/mof-fiscal-outlook's
// ingested coverage; it only affects the shaded "no data" band, never a silent gap.
const LIMITED_COVERAGE = new Set(
  COMPONENT_GROUPS.flatMap((g) => g.options.map((o) => o.key)).filter(
    (k) => k.startsWith("opex_component_") || k.startsWith("devex_sector_")
  )
);
const LIMITED_RANGE: [number, number] = [2017, 2021];

export default function PerkembanganPage() {
  const [componentKey, setComponentKey] = useState("opex_component_emoluments");
  const [availableKeys, setAvailableKeys] = useState<Set<string> | null>(null);
  const [data, setData] = useState<{ year: number; amount_rm: number }[]>([]);
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
        setData(r.rows.map((row) => ({ year: row.year, amount_rm: row.amount_rm / 1e6 })));
        setCitations(r.citations as { table: string; basis?: string }[]);
      })
      .catch((e) => {
        if (!stale) setError(String(e));
      });
    return () => {
      stale = true;
    };
  }, [componentKey]);

  const isLimited = LIMITED_COVERAGE.has(componentKey);
  const latest = data[data.length - 1];

  const chartData = useMemo(() => {
    return Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i).map((year) => {
      const row = data.find((d) => d.year === year);
      return { year, amount_rm: row?.amount_rm ?? null };
    });
  }, [data]);

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
        {isLimited && (
          <p className="text-xs opacity-70 mb-2">
            Pecahan ini kini hanya tersedia untuk {LIMITED_RANGE[0]}-{LIMITED_RANGE[1]}
            {" "}(edisi Tinjauan Fiskal yang telah dimasukkan setakat ini) — jurang di luar
            julat itu bukan data hilang secara senyap, sila lihat Metodologi.
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
                dot={false}
                connectNulls={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        {latest && (
          <p className="text-sm mt-2">
            {latest.year}: <span className="font-semibold tabular-nums">{formatRM(latest.amount_rm * 1e6, "juta")}</span>
          </p>
        )}
        <SourceCitation citations={citations} />
      </div>
    </div>
  );
}
