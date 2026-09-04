"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Ministry, fetchMinistries, fetchMinistryBreakdown, formatRM } from "@/lib/api";
import DashboardSubnav from "@/components/DashboardSubnav";
import SourceCitation from "@/components/SourceCitation";

const MIN_YEAR = 2009;
const MAX_YEAR = 2024;
const PALETTE = [
  "#1F6F5C", "#A9762E", "#4A6FA5", "#B25D5D", "#6B4E71",
  "#5C8A72", "#C08A3E", "#7C7C7C", "#3E7CB1", "#9B5A44", "#999999",
];

export default function KementerianPage() {
  const [ministries, setMinistries] = useState<Ministry[]>([]);
  const [code, setCode] = useState("");
  const [year, setYear] = useState(2023);
  const [jenis, setJenis] = useState<"Bekalan" | "Pembangunan">("Bekalan");
  const [result, setResult] = useState<Awaited<ReturnType<typeof fetchMinistryBreakdown>> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMinistries()
      .then((r) => {
        setMinistries(r.rows);
        if (!code && r.rows.length) setCode(r.rows.find((m) => m.jenis === "Bekalan")?.code ?? r.rows[0].code);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!code) return;
    setError(null);
    let stale = false;
    // A canonical ministry code carries its own jenis (opex codes start with B., devex
    // with P.) -- resolve the matching code for the selected jenis rather than assuming
    // the same code string works for both.
    const ministry = ministries.find((m) => m.code === code);
    const pairedCode = ministry
      ? ministries.find((m) => m.name_bm === ministry.name_bm && m.jenis === jenis)?.code ?? code
      : code;
    fetchMinistryBreakdown(pairedCode, year, jenis)
      .then((r) => {
        if (!stale) setResult(r);
      })
      .catch((e) => {
        if (!stale) {
          setError(String(e));
          setResult(null);
        }
      });
    return () => {
      stale = true;
    };
  }, [code, year, jenis, ministries]);

  const yearOptions = Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i);
  const opexMinistries = ministries.filter((m) => m.jenis === "Bekalan");

  return (
    <div className="mx-auto max-w-6xl px-5 py-10">
      <h1 className="text-2xl font-semibold mb-1">Papan Pemuka Fiskal</h1>
      <p className="text-sm opacity-70 mb-4">Ke mana perbelanjaan satu kementerian pergi.</p>
      <DashboardSubnav />

      <div className="flex flex-wrap items-end gap-4 mb-6 p-4 rounded border" style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
        <label className="text-sm flex-1 min-w-[240px]">
          Kementerian
          <select className="block mt-1 border rounded px-2 py-1 w-full" style={{ borderColor: "var(--line)" }}
            value={code} onChange={(e) => setCode(e.target.value)}>
            {opexMinistries.map((m) => <option key={m.code} value={m.code}>{m.name_bm}</option>)}
          </select>
        </label>
        <label className="text-sm">
          Tahun
          <select className="block mt-1 border rounded px-2 py-1" style={{ borderColor: "var(--line)" }}
            value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {yearOptions.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </label>
        <label className="text-sm">
          Jenis
          <select className="block mt-1 border rounded px-2 py-1" style={{ borderColor: "var(--line)" }}
            value={jenis} onChange={(e) => setJenis(e.target.value as "Bekalan" | "Pembangunan")}>
            <option value="Bekalan">Mengurus (OPEX)</option>
            <option value="Pembangunan">Pembangunan (DEVEX)</option>
          </select>
        </label>
      </div>

      {year === 2015 && (
        <p className="text-xs opacity-70 mb-3">
          FY2015: perincian aktiviti/program peringkat objek adalah OCR-provisional
          (imbasan imej sahaja) — lihat Metodologi.
        </p>
      )}
      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      {result && (
        <>
          <div className="rounded border p-4 mb-6" style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
            <h2 className="font-medium mb-3">
              {result.ministry_name_bm} — ke mana perbelanjaan pergi ({year})
            </h2>
            <div style={{ width: "100%", height: Math.max(280, result.rows.length * 36) }}>
              <ResponsiveContainer>
                <BarChart data={result.rows} layout="vertical" margin={{ left: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                  <XAxis type="number" tickFormatter={(v) => v.toLocaleString()} />
                  <YAxis
                    type="category"
                    dataKey="label"
                    width={220}
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => v ?? "(tiada label)"}
                  />
                  <Tooltip formatter={(v) => `RM${Number(v).toLocaleString("ms-MY")}`} />
                  <Bar dataKey="amount_rm">
                    {result.rows.map((_, i) => (
                      <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <SourceCitation citations={result.citations} />
          </div>

          {jenis === "Bekalan" && result.object_class_rows.length > 0 && (
            <div className="rounded border p-4" style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
              <h2 className="font-medium mb-3">Pecahan mengikut kelas objek</h2>
              <div style={{ width: "100%", height: 220 }}>
                <ResponsiveContainer>
                  <BarChart data={result.object_class_rows} layout="vertical" margin={{ left: 24 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                    <XAxis type="number" tickFormatter={(v) => v.toLocaleString()} />
                    <YAxis type="category" dataKey="label" width={220} tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v) => `RM${Number(v).toLocaleString("ms-MY")}`} />
                    <Bar dataKey="amount_rm">
                      {result.object_class_rows.map((_, i) => (
                        <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4 mt-6">
            <Stat label="Jumlah (10 teratas + lain-lain)" value={formatRM(result.rows.reduce((s, r) => s + r.amount_rm, 0), "juta")} />
          </div>
        </>
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
