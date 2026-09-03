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
import {
  Citation,
  HeadlineRow,
  Ministry,
  MinistryRow,
  fetchHeadline,
  fetchMinistries,
  fetchMinistryFiscal,
  formatRM,
} from "@/lib/api";
import SourceCitation from "@/components/SourceCitation";

const MIN_YEAR = 2009;
const MAX_YEAR = 2024;

export default function DashboardPage() {
  const [yearFrom, setYearFrom] = useState(2015);
  const [yearTo, setYearTo] = useState(MAX_YEAR);
  const [ministries, setMinistries] = useState<Ministry[]>([]);
  const [ministryCode, setMinistryCode] = useState<string>("");
  const [headline, setHeadline] = useState<HeadlineRow[]>([]);
  const [ministryData, setMinistryData] = useState<MinistryRow[]>([]);
  const [ministryName, setMinistryName] = useState<string>("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [basis, setBasis] = useState<"net" | "gross">("net");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMinistries()
      .then((r) => setMinistries(r.rows))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setError(null);
    if (ministryCode) {
      fetchMinistryFiscal(ministryCode, yearFrom, yearTo)
        .then((r) => {
          setMinistryData(r.rows);
          setMinistryName(r.ministry_name_bm);
          setCitations(r.citations);
        })
        .catch((e) => setError(String(e)));
    } else {
      fetchHeadline(yearFrom, yearTo)
        .then((r) => {
          setHeadline(r.rows);
          setCitations(r.citations);
        })
        .catch((e) => setError(String(e)));
    }
  }, [yearFrom, yearTo, ministryCode]);

  const chartData = useMemo(() => {
    if (ministryCode) {
      const byYear = new Map<number, { year: number; opex?: number; devex?: number }>();
      for (const r of ministryData) {
        const entry = byYear.get(r.year) ?? { year: r.year };
        entry[r.jenis] = r.amount_rm / 1e6;
        byYear.set(r.year, entry);
      }
      return [...byYear.values()].sort((a, b) => a.year - b.year);
    }
    return headline.map((r) => ({
      year: r.year,
      opex: (basis === "net" ? r.opex_net_rm ?? r.opex_gross_rm : r.opex_gross_rm) / 1e6,
      devex: (basis === "net" ? r.devex_net_rm ?? r.devex_gross_rm : r.devex_gross_rm) / 1e6,
    }));
  }, [headline, ministryData, ministryCode, basis]);

  return (
    <div className="mx-auto max-w-6xl px-5 py-10">
      <h1 className="text-2xl font-semibold mb-1">Papan Pemuka Fiskal</h1>
      <p className="text-sm opacity-70 mb-6">
        Perbelanjaan mengurus (opex) dan pembangunan (devex) kerajaan persekutuan,
        {" "}{MIN_YEAR}–{MAX_YEAR}.
      </p>

      <div className="flex flex-wrap items-end gap-4 mb-6 p-4 rounded border" style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
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
        <label className="text-sm flex-1 min-w-[220px]">
          Kementerian
          <select
            className="block mt-1 border rounded px-2 py-1 w-full"
            style={{ borderColor: "var(--line)" }}
            value={ministryCode}
            onChange={(e) => setMinistryCode(e.target.value)}
          >
            <option value="">Semua (jumlah negara)</option>
            {ministries.map((m) => (
              <option key={m.code} value={m.code}>{m.name_bm} ({m.code})</option>
            ))}
          </select>
        </label>
        <label className="text-sm" title={ministryCode ? "Angka kasar sahaja wujud pada peringkat kementerian" : undefined}>
          Asas
          <select
            className="block mt-1 border rounded px-2 py-1 disabled:opacity-40"
            style={{ borderColor: "var(--line)" }}
            value={basis}
            disabled={!!ministryCode}
            onChange={(e) => setBasis(e.target.value as "net" | "gross")}
          >
            <option value="net">Bersih (net)</option>
            <option value="gross">Kasar (gross)</option>
          </select>
        </label>
      </div>

      {ministryCode && (
        <p className="text-xs opacity-70 mb-3">
          Angka kementerian sentiasa <strong>kasar</strong> — tiada konsep &quot;bersih&quot;
          pada peringkat kementerian (lihat Metodologi).
        </p>
      )}

      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      <div className="rounded border p-4" style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
        <h2 className="font-medium mb-3">
          {ministryCode ? ministryName : "Jumlah Negara"}
        </h2>
        <div style={{ width: "100%", height: 340 }}>
          <ResponsiveContainer>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis dataKey="year" />
              <YAxis tickFormatter={(v) => `${v.toLocaleString()}`} width={70} />
              <Tooltip
                formatter={(value) => `RM${Number(value).toLocaleString("ms-MY", { maximumFractionDigits: 1 })} juta`}
              />
              <Line type="monotone" dataKey="opex" name="Opex" stroke="#1F6F5C" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="devex" name="Devex" stroke="#A9762E" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <SourceCitation citations={citations} />
      </div>

      {!ministryCode && headline.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6">
          {(() => {
            const last = headline[headline.length - 1];
            return (
              <>
                <Stat label={`Opex bersih ${last.year}`} value={formatRM(last.opex_net_rm ?? last.opex_gross_rm)} />
                <Stat label={`Opex kasar ${last.year}`} value={formatRM(last.opex_gross_rm)} />
                <Stat label={`Devex bersih ${last.year}`} value={formatRM(last.devex_net_rm ?? last.devex_gross_rm)} />
                <Stat label={`Devex kasar ${last.year}`} value={formatRM(last.devex_gross_rm)} />
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border p-3" style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
      <div className="text-xs opacity-60">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
    </div>
  );
}
