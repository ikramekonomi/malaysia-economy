"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  BreakdownRow,
  Citation,
  fetchDevexBySector,
  fetchFinancing,
  fetchHeadline,
  fetchOpexByType,
  fetchRevenueByCategory,
  formatRM,
} from "@/lib/api";
import DashboardSubnav from "@/components/DashboardSubnav";
import SourceCitation from "@/components/SourceCitation";

const MIN_YEAR = 2009;
const MAX_YEAR = 2024;
const PALETTE = [
  "#1F6F5C", "#A9762E", "#4A6FA5", "#B25D5D", "#6B4E71",
  "#5C8A72", "#C08A3E", "#7C7C7C", "#3E7CB1", "#9B5A44",
];

function ChartCard({
  title, children, citations, unavailableNote,
}: {
  title: string;
  children: React.ReactNode;
  citations?: Citation[];
  unavailableNote?: string | null;
}) {
  return (
    <div className="rounded border p-4 mb-6" style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
      <h2 className="font-medium mb-3">{title}</h2>
      {unavailableNote ? (
        <p className="text-sm opacity-70 py-8 text-center">{unavailableNote}</p>
      ) : (
        children
      )}
      {citations && <SourceCitation citations={citations} />}
    </div>
  );
}

function pivotBreakdown(yearA: number, yearB: number, rowsA: BreakdownRow[], rowsB: BreakdownRow[]) {
  const level1A = rowsA.filter((r) => r.level === 1 && r.line !== "total" && r.line !== "other");
  const otherA = rowsA.find((r) => r.line === "other" && r.level === 1);
  const lines = level1A.map((r) => r.line);
  const byYear: Record<number, Record<string, number>> = {
    [yearA]: {}, [yearB]: {},
  };
  for (const r of rowsA) if (r.level === 1) byYear[yearA][r.line] = r.amount_rm / 1e6;
  for (const r of rowsB) if (r.level === 1) byYear[yearB][r.line] = r.amount_rm / 1e6;
  const allLines = otherA ? [...lines, "other"] : lines;
  const data = [yearA, yearB].map((y) => ({ year: String(y), ...byYear[y] }));
  const labelOf = (line: string) => {
    const r = rowsA.find((x) => x.line === line) ?? rowsB.find((x) => x.line === line);
    return r?.line_bm ?? line;
  };
  return { data, lines: allLines, labelOf };
}

export default function RingkasanPage() {
  const [yearA, setYearA] = useState(2017);
  const [yearB, setYearB] = useState(2021);

  const [flowData, setFlowData] = useState<
    { category: string; [k: string]: string | number | null }[]
  >([]);
  const [flowMissing, setFlowMissing] = useState<string[] | null>(null);
  const [flowNoCovid, setFlowNoCovid] = useState<number[] | null>(null);
  const [revenueRows, setRevenueRows] = useState<
    { data: { year: string; [k: string]: string | number }[]; lines: string[]; labelOf: (l: string) => string }
  >({ data: [], lines: [], labelOf: (l) => l });
  const [opexPivot, setOpexPivot] = useState<ReturnType<typeof pivotBreakdown> | null>(null);
  const [opexNote, setOpexNote] = useState<string | null>(null);
  const [devexPivot, setDevexPivot] = useState<ReturnType<typeof pivotBreakdown> | null>(null);
  const [devexNote, setDevexNote] = useState<string | null>(null);
  const [financingData, setFinancingData] = useState<{ component: string; [k: string]: string | number }[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    let stale = false;
    (async () => {
      try {
        const [headline, revA, revB, opexA, opexB, devexA, devexB, finA, finB] = await Promise.all([
          fetchHeadline(Math.min(yearA, yearB), Math.max(yearA, yearB)),
          fetchRevenueByCategory(yearA, yearA),
          fetchRevenueByCategory(yearB, yearB),
          fetchOpexByType(yearA),
          fetchOpexByType(yearB),
          fetchDevexBySector(yearA),
          fetchDevexBySector(yearB),
          fetchFinancing(yearA),
          fetchFinancing(yearB),
        ]);
        if (stale) return;

        const hByYear = new Map(headline.rows.map((r) => [r.year, r]));
        const revTotal = (rows: typeof revA.rows) => rows.reduce((s, r) => s + r.amount_rm, 0);
        const finTotal = (rows: typeof finA.rows) => rows.reduce((s, r) => s + r.amount_rm, 0);

        // Net DEVEX comes from ONE publisher for both years being compared. MOF's own
        // figure covers 2015-2024 only, so picking "MOF where available" would quietly
        // compare a MOF year with a BNM year for any pair reaching back before 2015. BNM
        // MSB 3.1 is complete for 2009-2024 -- and overall_balance_rm is built on it -- so
        // it is used for both bars.
        //
        // FY2020-2022 spending through the Kumpulan Wang COVID-19 sat outside both opex
        // and devex, so it gets its own bar, and the balance is read from the warehouse
        // (curated overall_balance_rm, which includes it and is checked against MOF's
        // own published figure) rather than computed here. A missing figure is left
        // missing -- never drawn as zero.
        const CATEGORIES = [
          "Hasil", "Perbelanjaan Mengurus", "Perbelanjaan Pembangunan",
          "Kumpulan Wang COVID-19", "Defisit/Lebihan", "Dibiayai Bersih",
        ];
        const missing: string[] = [];
        const noCovidFund: number[] = [];
        const years = [
          [String(yearA), yearA, revA, finA] as const,
          [String(yearB), yearB, revB, finB] as const,
        ];
        for (const [, y] of years) {
          if (hByYear.get(y)?.covid_fund_status === "not_established") noCovidFund.push(y);
        }
        setFlowData(
          CATEGORIES.map((category) => {
            const row: { category: string; [k: string]: string | number | null } = { category };
            for (const [label, y, rev, fin] of years) {
              const h = hByYear.get(y);
              const juta = (v: number | null | undefined) => (v == null ? null : v / 1e6);
              let val: number | null = null;
              if (category === "Hasil") val = revTotal(rev.rows) / 1e6;
              if (category === "Perbelanjaan Mengurus") val = juta(h?.opex_net_rm);
              if (category === "Perbelanjaan Pembangunan") val = juta(h?.devex_net_bnm_rm);
              if (category === "Kumpulan Wang COVID-19") val = juta(h?.covid_fund_rm);
              if (category === "Defisit/Lebihan") val = juta(h?.overall_balance_rm);
              if (category === "Dibiayai Bersih") val = finTotal(fin.rows) / 1e6;
              // a fund that did not yet exist is not a missing figure
              const notApplicable = category === "Kumpulan Wang COVID-19" && h?.covid_fund_status === "not_established";
              if (val === null && !notApplicable) missing.push(`${category} ${y}`);
              row[label] = val === null ? null : Math.round(val);
            }
            return row;
          })
        );
        setFlowMissing(missing.length ? missing : null);
        setFlowNoCovid(noCovidFund.length ? noCovidFund : null);

        const revLines = Array.from(new Set([...revA.rows, ...revB.rows].map((r) => r.category_bm)));
        const revByYear: Record<number, Record<string, number>> = { [yearA]: {}, [yearB]: {} };
        for (const r of revA.rows) revByYear[yearA][r.category_bm] = r.amount_rm / 1e6;
        for (const r of revB.rows) revByYear[yearB][r.category_bm] = r.amount_rm / 1e6;
        setRevenueRows({
          data: [yearA, yearB].map((y) => ({ year: String(y), ...revByYear[y] })),
          lines: revLines,
          labelOf: (l) => l,
        });

        const naYear = (a: typeof opexA, b: typeof opexB) => (a.not_available ? yearA : yearB);
        if (opexA.not_available || opexB.not_available) {
          setOpexNote(`Belum tersedia pada tahap perincian ini untuk ${naYear(opexA, opexB)}.`);
          setOpexPivot(null);
        } else {
          setOpexNote(null);
          setOpexPivot(pivotBreakdown(yearA, yearB, opexA.rows, opexB.rows));
        }

        if (devexA.not_available || devexB.not_available) {
          setDevexNote(`Belum tersedia pada tahap perincian ini untuk ${naYear(devexA, devexB)}.`);
          setDevexPivot(null);
        } else {
          setDevexNote(null);
          setDevexPivot(pivotBreakdown(yearA, yearB, devexA.rows, devexB.rows));
        }

        const finComponents = Array.from(new Set([...finA.rows, ...finB.rows].map((r) => r.component_bm)));
        setFinancingData(
          finComponents.map((component) => {
            const a = finA.rows.find((r) => r.component_bm === component)?.amount_rm ?? 0;
            const b = finB.rows.find((r) => r.component_bm === component)?.amount_rm ?? 0;
            return { component, [String(yearA)]: Math.round(a / 1e6), [String(yearB)]: Math.round(b / 1e6) };
          })
        );
      } catch (e) {
        if (!stale) setError(String(e));
      }
    })();
    return () => {
      stale = true;
    };
  }, [yearA, yearB]);

  const yearOptions = useMemo(
    () => Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i),
    []
  );

  return (
    <div className="mx-auto max-w-6xl px-5 py-10">
      <h1 className="text-2xl font-semibold mb-1">Papan Pemuka Fiskal</h1>
      <p className="text-sm opacity-70 mb-4">Ringkasan perbandingan dua tahun fiskal.</p>
      <DashboardSubnav />

      <div className="flex flex-wrap items-end gap-4 mb-6 p-4 rounded border" style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
        <label className="text-sm">
          Tahun A
          <select className="block mt-1 border rounded px-2 py-1" style={{ borderColor: "var(--line)" }}
            value={yearA} onChange={(e) => setYearA(Number(e.target.value))}>
            {yearOptions.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </label>
        <label className="text-sm">
          Tahun B
          <select className="block mt-1 border rounded px-2 py-1" style={{ borderColor: "var(--line)" }}
            value={yearB} onChange={(e) => setYearB(Number(e.target.value))}>
            {yearOptions.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </label>
        <p className="text-xs opacity-60 max-w-sm">
          Pecahan OPEX/DEVEX terperinci tersedia untuk 2015-2024 (Tinjauan Fiskal edisi
          2019-2027) — tahun sebelum 2015 boleh dipilih, carta berkenaan akan menunjukkan
          &quot;belum tersedia&quot;.
        </p>
      </div>

      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      <ChartCard
        title="Ringkasan Aliran Fiskal"
        citations={[
          { table: "pkkp.fact_revenue", basis: "Hasil — sebenar teraudit PKKP" },
          {
            table: "curated.fact_fiscal_headline",
            basis:
              "Perbelanjaan Mengurus bersih — PKKP teraudit, Akaun Hasil Disatukan (sebelum pindahan " +
              "ke Kumpulan Wang Pembangunan). Perbelanjaan Pembangunan bersih — BNM Buletin " +
              "Statistik Bulanan 3.1 (kasar tolak pemulihan pinjaman), digunakan untuk kedua-dua " +
              "tahun supaya perbandingan memakai satu penerbit. Kumpulan Wang COVID-19 — PKKP " +
              "teraudit, Lampiran 3. Defisit/Lebihan — definisi MOF (hasil tolak tiga perbelanjaan " +
              "di atas), disemak dengan baki keseluruhan yang diterbitkan MOF.",
          },
          { table: "pkkp.fact_timeseries_2010_2024", basis: "Dibiayai oleh:" },
        ]}
      >
        <p className="text-xs opacity-70 mb-2">
          Defisit/Lebihan = Hasil − Perbelanjaan Mengurus − Perbelanjaan Pembangunan −
          Kumpulan Wang COVID-19, mengikut definisi MOF (sama dengan baki keseluruhan yang
          diterbitkan MOF). PKKP mencetak baki keseluruhan dengan definisi berbeza (semua
          terimaan Kumpulan Wang Pembangunan ditolak, bukan pemulihan pinjaman sahaja), jadi
          angkanya boleh berbeza sehingga RM1.9 bilion.
        </p>
        {flowNoCovid && (
          <p className="text-xs opacity-70 mb-2">
            Kumpulan Wang COVID-19 belum wujud pada {flowNoCovid.join(" dan ")} — ditubuhkan pada
            2020 dan berbelanja hanya pada 2020-2022.
          </p>
        )}
        {flowMissing && (
          <p className="text-xs text-red-700 mb-2">
            Tiada data untuk: {flowMissing.join(", ")} — dibiarkan kosong, bukan sifar.
          </p>
        )}
        <div style={{ width: "100%", height: 300 }}>
          <ResponsiveContainer>
            <BarChart data={flowData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis dataKey="category" tick={{ fontSize: 11 }} interval={0} angle={-10} textAnchor="end" height={60} />
              <YAxis tickFormatter={(v) => v.toLocaleString()} width={70} />
              <Tooltip
                formatter={(v) => (v === null || v === undefined ? "tiada data" : `RM${Number(v).toLocaleString("ms-MY")} juta`)}
              />
              <Legend />
              <Bar dataKey={String(yearA)} fill={PALETTE[0]} />
              <Bar dataKey={String(yearB)} fill={PALETTE[1]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </ChartCard>

      <ChartCard title="Dari Mana Hasil Datang" citations={[{ table: "pkkp.fact_revenue", basis: "audited actual" }]}>
        <div style={{ width: "100%", height: 300 }}>
          <ResponsiveContainer>
            <BarChart data={revenueRows.data}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis dataKey="year" />
              <YAxis tickFormatter={(v) => v.toLocaleString()} width={70} />
              <Tooltip formatter={(v) => `RM${Number(v).toLocaleString("ms-MY")} juta`} />
              <Legend />
              {revenueRows.lines.map((line, i) => (
                <Bar key={line} dataKey={line} stackId="rev" fill={PALETTE[i % PALETTE.length]} name={line} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </ChartCard>

      <ChartCard
        title="Pecahan Perbelanjaan Mengurus (mengikut komponen)"
        citations={[{ table: "curated.fact_opex_by_component", basis: "MOF Tinjauan Fiskal, Jadual 3.1" }]}
        unavailableNote={opexNote}
      >
        {opexPivot && (
          <div style={{ width: "100%", height: 340 }}>
            <ResponsiveContainer>
              <BarChart data={opexPivot.data}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                <XAxis dataKey="year" />
                <YAxis tickFormatter={(v) => v.toLocaleString()} width={70} />
                <Tooltip formatter={(v) => `RM${Number(v).toLocaleString("ms-MY")} juta`} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {opexPivot.lines.map((line, i) => (
                  <Bar key={line} dataKey={line} stackId="opex" fill={PALETTE[i % PALETTE.length]} name={opexPivot.labelOf(line)} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </ChartCard>

      <ChartCard
        title="Pecahan Perbelanjaan Pembangunan (mengikut sektor)"
        citations={[{ table: "curated.fact_devex_by_sector", basis: "MOF Tinjauan Fiskal, Jadual 3.3" }]}
        unavailableNote={devexNote}
      >
        {devexPivot && (
          <div style={{ width: "100%", height: 340 }}>
            <ResponsiveContainer>
              <BarChart data={devexPivot.data}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                <XAxis dataKey="year" />
                <YAxis tickFormatter={(v) => v.toLocaleString()} width={70} />
                <Tooltip formatter={(v) => `RM${Number(v).toLocaleString("ms-MY")} juta`} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {devexPivot.lines.map((line, i) => (
                  <Bar key={line} dataKey={line} stackId="devex" fill={PALETTE[i % PALETTE.length]} name={devexPivot.labelOf(line)} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </ChartCard>

      <ChartCard title="Bagaimana Perbelanjaan Dibiayai" citations={[{ table: "pkkp.fact_timeseries_2010_2024", basis: "Dibiayai oleh:" }]}>
        <div style={{ width: "100%", height: 280 }}>
          <ResponsiveContainer>
            <BarChart data={financingData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis dataKey="component" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={(v) => v.toLocaleString()} width={70} />
              <Tooltip formatter={(v) => `RM${Number(v).toLocaleString("ms-MY")} juta`} />
              <Legend />
              <Bar dataKey={String(yearA)} fill={PALETTE[0]} />
              <Bar dataKey={String(yearB)} fill={PALETTE[1]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </ChartCard>

      <p className="text-xs opacity-60 mt-2">
        Nota: nilai negatif dalam carta pembiayaan menunjukkan pertambahan aset / bayaran
        balik bersih, bukan ralat data.
      </p>
    </div>
  );
}
