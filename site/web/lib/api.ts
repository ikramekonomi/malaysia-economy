const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8123";

export type Citation = {
  table: string;
  basis?: string;
  side?: string;
  doc?: string;
};

export type HeadlineRow = {
  year: number;
  revenue_rm: number | null;
  opex_gross_rm: number;
  opex_net_rm: number | null;
  devex_gross_rm: number;
  /** MOF Tinjauan Fiskal official_actual -- FY2015-2025, each year from its own edition. */
  devex_net_rm: number | null;
  devex_net_basis: string | null;
  /** BNM MSB 3.1, complete FY2009-2025. A different publication: never splice with the MOF column. */
  devex_net_bnm_rm: number | null;
  devex_net_bnm_basis: string | null;
  /** Kumpulan Wang COVID-19 spending -- outside opex and devex. Null before the fund existed. */
  covid_fund_rm: number | null;
  covid_fund_status: "printed" | "printed_nil" | "not_established" | "not_available";
  /** revenue - opex_net - devex_net_bnm - COVID-19 fund (MOF's definition). */
  overall_balance_rm: number | null;
  overall_balance_basis: string | null;
  /** MOF's own official_actual figures, one edition per year (FY2015 onward). The only
   *  national figures for a year the audited accounts do not cover yet (FY2025). */
  revenue_mof_rm: number | null;
  opex_mof_rm: number | null;
  devex_gross_mof_rm: number | null;
  covid_fund_mof_rm: number | null;
  overall_balance_mof_rm: number | null;
  mof_edition: number | null;
  note: string | null;
};

export type MinistryRow = {
  year: number;
  jenis: "opex" | "devex";
  amount_rm: number;
  note: string | null;
};

export type Ministry = { code: string; name_bm: string; jenis: string };

export type Coverage = {
  min_year: number;
  max_year: number;
  /** last year the audited PKKP accounts cover */
  audited_max_year: number;
  /** first year MOF's own Tinjauan Fiskal figures cover */
  mof_min_year: number;
};

/** Used until /api/meta/coverage answers -- the warehouse itself is the source of truth. */
export const DEFAULT_COVERAGE: Coverage = {
  min_year: 2009, max_year: 2025, audited_max_year: 2024, mof_min_year: 2015,
};

export function fetchCoverage() {
  return getJSON<Coverage>("/api/meta/coverage");
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export function fetchHeadline(yearFrom: number, yearTo: number) {
  return getJSON<{ rows: HeadlineRow[]; citations: Citation[] }>(
    `/api/fiscal/headline?year_from=${yearFrom}&year_to=${yearTo}`
  );
}

export function fetchMinistries() {
  return getJSON<{ rows: Ministry[]; citations: Citation[] }>("/api/ministries");
}

export function fetchMinistryFiscal(code: string, yearFrom: number, yearTo: number) {
  return getJSON<{ ministry_name_bm: string; rows: MinistryRow[]; citations: Citation[] }>(
    `/api/fiscal/ministry?code=${encodeURIComponent(code)}&year_from=${yearFrom}&year_to=${yearTo}`
  );
}

export function exportHeadlineUrl(yearFrom: number, yearTo: number) {
  return `${API_BASE}/api/export/headline.csv?year_from=${yearFrom}&year_to=${yearTo}`;
}

export function exportMinistryUrl(code: string, yearFrom: number, yearTo: number) {
  return `${API_BASE}/api/export/ministry.csv?code=${encodeURIComponent(code)}&year_from=${yearFrom}&year_to=${yearTo}`;
}

export async function askChat(question: string) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<{ answer: string; citations: Citation[] }>;
}

export type RevenueByCategoryRow = { year: number; category_bm: string; amount_rm: number };

export type BreakdownRow = {
  line: string;
  line_bm: string;
  line_en: string;
  level: number;
  parent_line: string | null;
  amount_rm: number;
  pct_share: number | null;
  basis: string;
  note: string | null;
};

export type FinancingRow = { component_bm: string; amount_rm: number };

export type MinistryBreakdownRow = { label: string | null; amount_rm: number };

export function fetchRevenueByCategory(yearFrom: number, yearTo: number) {
  return getJSON<{ rows: RevenueByCategoryRow[]; citations: Citation[] }>(
    `/api/fiscal/revenue-by-category?year_from=${yearFrom}&year_to=${yearTo}`
  );
}

export function fetchOpexByType(year: number) {
  return getJSON<{ rows: BreakdownRow[]; not_available: boolean; note?: string; citations: Citation[] }>(
    `/api/fiscal/opex-by-type?year=${year}`
  );
}

export function fetchDevexBySector(year: number) {
  return getJSON<{ rows: BreakdownRow[]; not_available: boolean; note?: string; citations: Citation[] }>(
    `/api/fiscal/devex-by-sector?year=${year}`
  );
}

export function fetchFinancing(year: number) {
  return getJSON<{ rows: FinancingRow[]; not_available: boolean; note?: string; citations: Citation[] }>(
    `/api/fiscal/financing?year=${year}`
  );
}

export function fetchComponents() {
  return getJSON<{ rows: { component_key: string }[]; citations: Citation[] }>("/api/fiscal/components");
}

export function fetchComponentSeries(componentKey: string, yearFrom: number, yearTo: number) {
  // amount_rm is null for a year the source does not cover
  return getJSON<{ rows: { year: number; amount_rm: number | null }[]; citations: Citation[] }>(
    `/api/fiscal/component-series?component_key=${encodeURIComponent(componentKey)}&year_from=${yearFrom}&year_to=${yearTo}`
  );
}

export function fetchMinistryBreakdown(code: string, year: number, jenis: "Bekalan" | "Pembangunan") {
  return getJSON<{
    ministry_name_bm: string;
    raw_code: string;
    rows: MinistryBreakdownRow[];
    object_class_rows: MinistryBreakdownRow[];
    citations: Citation[];
  }>(`/api/fiscal/ministry-breakdown?code=${encodeURIComponent(code)}&year=${year}&jenis=${jenis}`);
}

export function formatRM(value: number | null | undefined, unit: "bil" | "juta" = "bil") {
  if (value === null || value === undefined) return "—";
  const divisor = unit === "bil" ? 1e9 : 1e6;
  return `RM${(value / divisor).toLocaleString("ms-MY", { maximumFractionDigits: 1 })} ${unit}`;
}
