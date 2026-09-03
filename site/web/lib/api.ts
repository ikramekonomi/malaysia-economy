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
  devex_net_rm: number | null;
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

export function formatRM(value: number | null | undefined, unit: "bil" | "juta" = "bil") {
  if (value === null || value === undefined) return "—";
  const divisor = unit === "bil" ? 1e9 : 1e6;
  return `RM${(value / divisor).toLocaleString("ms-MY", { maximumFractionDigits: 1 })} ${unit}`;
}
