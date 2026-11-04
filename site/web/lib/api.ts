const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8123";

export type Citation = {
  table: string;
  basis?: string;
  side?: string;
  doc?: string;
};

export type HeadlineRow = {
  year: number;
  opex_gross_rm: number;
  opex_net_rm: number | null;
  devex_gross_rm: number;
  /** MOF Tinjauan Fiskal official_actual -- FY2017-2019 and FY2024 only. */
  devex_net_rm: number | null;
  devex_net_basis: string | null;
  /** BNM MSB 3.1, complete FY2009-2024. A different publication: never splice with the MOF column. */
  devex_net_bnm_rm: number | null;
  devex_net_bnm_basis: string | null;
  note: string | null;
};

export type MinistryRow = {
  year: number;
  jenis: "opex" | "devex";
  amount_rm: number;
  note: string | null;
};

export type Ministry = { code: string; name_bm: string; jenis: string };

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
