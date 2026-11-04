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
import { useCoverage, yearRange } from "@/lib/useCoverage";
import SourceCitation from "@/components/SourceCitation";

type FlowBasis = "audited" | "mof" | "none";
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
  const [flowBasis, setFlowBasis] = useState<FlowBasis>("audited");
  const [revenueNote, setRevenueNote] = useState<string | null>(null);
  const [financingNote, setFinancingNote] = useState<string | null>(null);
  const cov = useCoverage();
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

        // ONE PUBLISHER PER COMPARISON. Both years are shown on the same basis or not at
        // all -- never an audited year beside a MOF year as if they were one series:
        //   audited  both years have audited PKKP accounts (<= audited_max_year). Revenue,
        //            opex and the COVID-19 fund are PKKP as printed; net DEVEX is BNM MSB
        //            3.1 for both bars (complete; overall_balance_rm is built on it).
        //   mof      a year has no audited accounts yet (FY2025): both bars switch to MOF's
        //            own official_actual Tinjauan Fiskal figures, one edition per year,
        //            including MOF's printed overall balance.
        //   none     no single publisher covers both years (2009-2014 has no MOF figures;
        //            2025 has no audited ones) -- the chart says so instead of mixing.
        // A missing figure is left missing -- never drawn as zero.
        const audited = (y: number) => y <= cov.audited_max_year;
        const hasMof = (y: number) => y >= cov.mof_min_year && hByYear.get(y)?.mof_edition != null;
        const basis: FlowBasis =
          audited(yearA) && audited(yearB) ? "audited"
            : hasMof(yearA) && hasMof(yearB) ? "mof"
              : "none";
        setFlowBasis(basis);

        const CATEGORIES = basis === "mof"
          ? ["Hasil", "Perbelanjaan Mengurus", "Perbelanjaan Pembangunan", "Kumpulan Wang COVID-19",
             "Baki Keseluruhan"]
          : ["Hasil", "Perbelanjaan Mengurus", "Perbelanjaan Pembangunan", "Kumpulan Wang COVID-19",
             "Defisit/Lebihan", "Dibiayai Bersih"];
        const missing: string[] = [];
        const noCovidFund: number[] = [];
        const years = [
          [String(yearA), yearA, revA, finA] as const,
          [String(yearB), yearB, revB, finB] as const,
        ];
        for (const [, y] of years) {
          const h = hByYear.get(y);
          const covidAbsent = basis === "mof"
            ? h?.covid_fund_mof_rm == null && (y < 2020 || y > 2022)
            : h?.covid_fund_status === "not_established";
          if (covidAbsent) noCovidFund.push(y);
        }
        const juta = (v: number | null | undefined) => (v == null ? null : v / 1e6);
        setFlowData(
          basis === "none" ? [] : CATEGORIES.map((category) => {
            const row: { category: string; [k: string]: string | number | null } = { category };
            for (const [label, y, rev, fin] of years) {
              const h = hByYear.get(y);
              let val: number | null = null;
              if (basis === "audited") {
                // revenue/financing come from per-year PKKP tables: no rows means no
                // audited figure, NOT zero
                if (category === "Hasil") val = rev.rows.length ? revTotal(rev.rows) / 1e6 : null;
                if (category === "Perbelanjaan Mengurus") val = juta(h?.opex_net_rm);
                if (category === "Perbelanjaan Pembangunan") val = juta(h?.devex_net_bnm_rm);
                if (category === "Kumpulan Wang COVID-19") val = juta(h?.covid_fund_rm);
                if (category === "Defisit/Lebihan") val = juta(h?.overall_balance_rm);
                if (category === "Dibiayai Bersih") val = fin.not_available ? null : finTotal(fin.rows) / 1e6;
              } else {
                if (category === "Hasil") val = juta(h?.revenue_mof_rm);
                if (category === "Perbelanjaan Mengurus") val = juta(h?.opex_mof_rm);
                if (category === "Perbelanjaan Pembangunan") val = juta(h?.devex_net_rm);
                if (category === "Kumpulan Wang COVID-19") val = juta(h?.covid_fund_mof_rm);
                if (category === "Baki Keseluruhan") val = juta(h?.overall_balance_mof_rm);
              }
              // a fund that did not exist (or had closed) is not a missing figure
              const notApplicable = category === "Kumpulan Wang COVID-19" && noCovidFund.includes(y);
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
        const revNA = [[yearA, revA], [yearB, revB]].filter(([, r]) => !(r as typeof revA).rows.length)
          .map(([y]) => y as number);
        setRevenueNote(revNA.length
          ? `Belum tersedia untuk ${revNA.join(" dan ")}: pecahan hasil ini daripada akaun teraudit ` +
            `PKKP, dan akaun FY${revNA[0]} belum diterbitkan.`
          : null);

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

        const finNA = [[yearA, finA], [yearB, finB]].filter(([, f]) => (f as typeof finA).not_available)
          .map(([y]) => y as number);
        setFinancingNote(finNA.length
          ? `Belum tersedia untuk ${finNA.join(" dan ")}: panel pembiayaan ini daripada akaun teraudit ` +
            `PKKP, yang belum meliputi tahun itu.`
          : null);
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
  }, [yearA, yearB, cov]);

  const yearOptions = useMemo(() => yearRange(cov.min_year, cov.max_year), [cov]);

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
          Pecahan OPEX/DEVEX terperinci tersedia untuk 2015-2025 (Tinjauan Fiskal edisi
          2019-2027) — tahun sebelum 2015 boleh dipilih, carta berkenaan akan menunjukkan
          &quot;belum tersedia&quot;.
        </p>
      </div>

      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      <ChartCard
        title={flowBasis === "mof"
          ? "Ringkasan Aliran Fiskal — angka MOF (belum teraudit)"
          : "Ringkasan Aliran Fiskal"}
        unavailableNote={flowBasis === "none"
          ? `Tiada satu penerbit yang meliputi kedua-dua tahun: ${Math.max(yearA, yearB) > cov.audited_max_year
              ? `FY${Math.max(yearA, yearB)} belum mempunyai akaun teraudit, dan angka MOF hanya bermula ${cov.mof_min_year}`
              : "tahun ini tiada angka yang sama asas"}. Pilih dua tahun dari ${cov.mof_min_year} ke atas untuk ` +
            `perbandingan atas asas MOF, atau dua tahun hingga ${cov.audited_max_year} untuk akaun teraudit.`
          : null}
        citations={flowBasis === "mof" ? [
          {
            table: "curated.fact_fiscal_headline",
            basis:
              "Semua bar — MOF Tinjauan Fiskal, angka sebenar rasmi (official_actual), satu edisi " +
              "setiap tahun (tahun ini dicetak sebagai sebenar terkini dalam edisi tersebut). " +
              "Perbelanjaan Pembangunan bersih — kasar tolak pemulihan pinjaman. Baki keseluruhan " +
              "seperti dicetak MOF.",
          },
        ] : [
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
        {flowBasis === "mof" ? (
          <p className="text-xs mb-2 p-2 rounded" style={{ background: "var(--line)" }}>
            FY{cov.audited_max_year + 1} belum mempunyai akaun teraudit (PKKP), jadi kedua-dua
            tahun ditunjukkan dengan angka sebenar rasmi MOF (Tinjauan Fiskal) — bukan angka
            teraudit, dan tidak dicampur dengan angka teraudit tahun lain. Angka MOF boleh
            dipinda dalam edisi kemudian. Pembiayaan tidak ditunjukkan atas asas ini.
          </p>
        ) : (
          <p className="text-xs opacity-70 mb-2">
            Defisit/Lebihan = Hasil − Perbelanjaan Mengurus − Perbelanjaan Pembangunan −
            Kumpulan Wang COVID-19, mengikut definisi MOF (sama dengan baki keseluruhan yang
            diterbitkan MOF). PKKP mencetak baki keseluruhan dengan definisi berbeza (semua
            terimaan Kumpulan Wang Pembangunan ditolak, bukan pemulihan pinjaman sahaja), jadi
            angkanya boleh berbeza sehingga RM1.9 bilion.
          </p>
        )}
        {flowNoCovid && (
          <p className="text-xs opacity-70 mb-2">
            Kumpulan Wang COVID-19 tiada perbelanjaan pada {flowNoCovid.join(" dan ")} — dana ini
            ditubuhkan pada 2020 dan berbelanja hanya pada 2020-2022.
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

      <ChartCard title="Dari Mana Hasil Datang" citations={[{ table: "pkkp.fact_revenue", basis: "audited actual" }]}
        unavailableNote={revenueNote}>
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

      <ChartCard title="Bagaimana Perbelanjaan Dibiayai" citations={[{ table: "pkkp.fact_timeseries_2010_2024", basis: "Dibiayai oleh:" }]}
        unavailableNote={financingNote}>
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
