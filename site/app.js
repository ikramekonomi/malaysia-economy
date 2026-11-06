/* Malaysia Economy Data Warehouse: the public site. A static app over site/data/*.json (apps/site/build_site_data.py).
   No server, no SQL, no number computed that the warehouse does not hold, except the plain arithmetic it shows
   (differences, shares) with its inputs beside it. Routes: #/about #/explore #/explore/<code> #/gaps #/gaps/<name>
   #/states #/state/<geo> #/sources #/method. */
"use strict";

const D = {};               // loaded data
const cache = new Map();     // fetched JSON by path
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const J = (p) => {
  if (!cache.has(p)) cache.set(p, fetch("data/" + p).then((r) => { if (!r.ok) throw new Error(p + " " + r.status); return r.json(); }));
  return cache.get(p);
};
const REPO = "https://github.com/ikramekonomi/malaysia-economy";

/* ---------- formatting ---------- */
const NF = (d) => new Intl.NumberFormat("en-MY", { maximumFractionDigits: d, minimumFractionDigits: 0 });
const exact = (v) => (v == null || v === "" ? "–" : typeof v === "number" ? NF(10).format(v) : esc(v));
function compact(v, unit = "") {
  if (v == null || v === "" || isNaN(v)) return "–";
  const a = Math.abs(v), rm = /^RM/.test(unit) || unit === "rm";
  let s;
  if (a >= 1e12) s = NF(2).format(v / 1e12) + " tn";
  else if (a >= 1e9) s = NF(2).format(v / 1e9) + " bn";
  else if (a >= 1e6) s = NF(2).format(v / 1e6) + " mn";
  else if (a >= 1e4) s = NF(0).format(v);
  else s = NF(a < 10 ? 2 : 1).format(v);
  if (rm) return (v < 0 ? "−RM " + s.replace("-", "") : "RM " + s);
  if (unit === "percent") return s + "%";
  return s;
}
const million = (v) => (v >= 1e6 ? NF(2).format(v / 1e6) + " million" : NF(0).format(v));
const pct = (v, d = 1) => (v == null || v === "" ? "–" : NF(d).format(v * 100) + "%");
const unitShort = (u) => ({ percent: "%", RM: "RM" }[u] || u);

/* ---------- places ---------- */
const STATES = [
  ["MY-09", "PLS", 0, 0], ["MY-02", "KDH", 1, 0], ["MY-03", "KTN", 2, 0], ["MY-07", "PNG", 0, 1], ["MY-08", "PRK", 1, 1],
  ["MY-11", "TRG", 2, 1], ["MY-10", "SGR", 0, 2], ["MY-14", "KUL", 1, 2], ["MY-06", "PHG", 2, 2], ["MY-16", "PJY", 0, 3],
  ["MY-05", "NSN", 1, 3], ["MY-04", "MLK", 1, 4], ["MY-01", "JHR", 2, 4], ["MY-15", "LBN", 5, 0], ["MY-12", "SBH", 6, 0],
  ["MY-13", "SWK", 5, 1],
];
const geoName = (g) => (D.geoIx[g]?.name || g);
function geoLabel(g) {
  const x = D.geoIx[g];
  if (!x) return g;
  if (x.level === "state" || x.level === "country") return x.name;
  const st = stateOf(g);
  return `${x.name}${st && st !== g ? " · " + geoName(st) : ""}`;
}
const stateOf = (g) => { const m = /^(MY-\d\d)/.exec(g); return m ? m[1] : null; };
const LEVELS = { country: "Malaysia", state: "States", district: "Districts", parlimen: "Parlimen", dun: "DUN", unallocated: "Not allocated" };

/* ---------- periods ---------- */
function pdate(p) {
  let m = /^(\d{4})-(\d{2})$/.exec(p); if (m) return new Date(Date.UTC(+m[1], +m[2] - 1, 1));
  m = /^(\d{4})-Q(\d)$/.exec(p); if (m) return new Date(Date.UTC(+m[1], (+m[2] - 1) * 3, 1));
  m = /^(\d{4})/.exec(p); if (m) return new Date(Date.UTC(+m[1], 0, 1));
  return null;
}
const isMonthly = (p) => /^\d{4}-\d{2}$/.test(p);

/* ---------- breakdown labels ---------- */
const AXIS = { sex: "Sex", hh_head_sex: "Head of household: sex", hh_head_ethnicity: "Head of household: ethnicity",
  hh_head_age: "Head of household: age", hh_size: "Household size", strata: "Strata", age: "Age", citizenship: "Citizenship",
  coicop: "CPI division", ethnicity: "Ethnicity", charged_head: "Charged expenditure", maksud: "Vote (maksud)", geo_scope: "Area",
  pli_component: "PLI component", percentile_group: "Percentile group", reserve_head: "Reserve" };
function brkLabel(b) {
  if (!b || b === "_total") return "Total";
  return b.split("|").map((kv) => { const [k, v] = kv.split("="); if (k === "body") return D.entities?.[v] || v; return `${AXIS[k] || k.replace(/_/g, " ")}: ${(v || "").replace(/_/g, " ")}`; }).join(" · ");
}

/* ---------- readable names for editions and publishers ---------- */
const PUB = { dosm: "DOSM", bnm: "Bank Negara", mof: "Ministry of Finance", pkkp: "Accountant General (PKKP)", anggaran: "Budget books (MOF)",
  anggaran_hasil: "Revenue estimates (MOF)", rmk: "Malaysia Plan (EPU)", states: "State governments", audit: "Auditor-General", parliament: "Parliament" };
const pubName = (p) => PUB[String(p).toLowerCase()] || String(p).toUpperCase();
function edLabel(id) {
  id = String(id || ""); let m;
  if ((m = /^pkkp:(\d{4})_/.exec(id))) return `PKKP FY${m[1]}, audited accounts`;
  if ((m = /^anggaran:.*?(\d{4})\.pdf$/i.exec(id))) return `Budget book ${m[1]} (expenditure estimates)`;
  if ((m = /^anggaran_hasil:.*?(\d{4})/i.exec(id))) return `Revenue estimates ${m[1]}`;
  if ((m = /^mof:tinjauan_fiskal@(\d{4})/.exec(id))) return `MOF Fiscal Outlook ${m[1]}`;
  if ((m = /^bnm:([^@]+)@(.+)$/.exec(id))) return `Bank Negara ${m[1].replace(/_/g, " ").toUpperCase()}, as of ${m[2]}`;
  if ((m = /^dosm:report\.([^@]+)@(.+)$/.exec(id))) return `DOSM report: ${m[1].replace(/_/g, " ")} (${m[2]})`;
  if ((m = /^dosm:([^@]+)@(.+)$/.exec(id))) return `DOSM ${m[1].replace(/_/g, " ")}, as of ${m[2]}`;
  if (/^rmk:rmk12/.test(id)) return "Twelfth Malaysia Plan (2021–2025)";
  if ((m = /^states:(.+)$/.exec(id))) return `State accounts: ${m[1].replace(/_/g, " ").replace(/\.pdf$/i, "")}`;
  return id;
}

/* ---------- small UI helpers ---------- */
function toast(t) { const el = $("#toast"); el.textContent = t; el.classList.add("on"); clearTimeout(toast.t); toast.t = setTimeout(() => el.classList.remove("on"), 1800); }
async function copy(t, msg = "Copied") { try { await navigator.clipboard.writeText(t); toast(msg); } catch { toast("Copy failed: select and copy by hand"); } }
function download(name, text, type = "text/csv") {
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
const csvCell = (v) => (v == null ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
const toCSV = (cols, rows) => [cols.join(","), ...rows.map((r) => r.map(csvCell).join(","))].join("\n");
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const SER = () => ["--s1", "--s2", "--s3", "--s4", "--s5", "--s6"].map(css);
function crumbs(parts) {
  $("#crumbs").innerHTML = parts.map((p, i) => (i === parts.length - 1 ? `<b>${esc(p[0])}</b>` : `<a href="${p[1]}">${esc(p[0])}</a><span>/</span>`)).join("");
}
function hashParams() { const h = location.hash.slice(1); const i = h.indexOf("?"); return [i < 0 ? h : h.slice(0, i), new URLSearchParams(i < 0 ? "" : h.slice(i + 1))]; }
function setParams(path, params) {
  const s = params.toString(); history.replaceState(null, "", "#" + path + (s ? "?" + s : ""));
}
const chip = (t, cls = "") => `<span class="chip ${cls}">${t}</span>`;
const themeName = (t) => D.themes[t] || (t ? "Theme " + t : "Unthemed");
const kv = (k, v) => (v ? `<tr><th style="position:static;cursor:auto;width:34%">${esc(k)}</th><td>${v}</td></tr>` : "");

/* ---------- status vocabulary (gap views) ---------- */
const STATUS = {
  agree: ["Agree", "good"], consistent: ["Consistent", "good"], within_estimate: ["Within estimate", "good"], within_allocation: ["Within allocation", "good"],
  on_estimate: ["On estimate", "good"], agree_after_other_lenders: ["Agree (after other lenders)", "good"],
  differ: ["Differ", "bad"], differ_minor: ["Differ (minor)", "warn"], underspent: ["Underspent", "warn"], overspent: ["Overspent", "bad"],
  below_estimate: ["Below estimate", "warn"], above_estimate: ["Above estimate", "neutral"], below_target: ["Outcome below target", "neutral"],
  above_target: ["Outcome above target", "neutral"], below_range: ["Below the target range", "neutral"],
  grew_faster_than_debt: ["Grew faster than debt", "warn"], grew_slower_than_debt: ["Grew slower than debt", "neutral"], the_benchmark: ["The benchmark (debt)", "neutral"],
  first_year: ["First year held", "muted"], not_held: ["Not held", "muted"], no_allocation: ["No allocation printed", "muted"], reserve: ["Contingency reserve", "muted"],
  share: ["Share of a class total", "neutral"], state_not_printed: ["State did not print it", "muted"], own_volume_not_held: ["State volume not held", "muted"],
  state_table_not_extracted: ["State table not yet extracted", "muted"], no_state_government: ["No state government (FT)", "muted"],
  federal_not_held: ["Federal figure not held", "muted"], printed_in_later_volume_only: ["Printed in a later volume only", "muted"],
  lampiran_e_unreconciled: ["Lampiran E not reconciled", "warn"], offset_entry: ["Offset entry", "muted"],
};
function statusChip(s) {
  if (!s) return "";
  const [t, k] = STATUS[s] || [s.replace(/_/g, " "), "neutral"];
  const col = { good: "var(--good)", bad: "var(--bad)", warn: "var(--warn)", neutral: "var(--accent)", muted: "var(--text-3)" }[k];
  return `<span class="chip"><i class="dot" style="background:${col}"></i>${esc(t)}</span>`;
}
const statusText = (s) => (STATUS[s] || [String(s || "").replace(/_/g, " ")])[0];

/* =====================================================================================================
   BOOT
   ===================================================================================================== */
async function boot() {
  initTheme();
  logo();
  const [meta, cat, geo, themes, caveats, breaks, gaps, registry, entities] = await Promise.all(
    ["meta.json", "catalogue.json", "geo.json", "themes.json", "caveats.json", "breaks.json", "gaps.json", "registry.json", "entities.json"].map((f) => J(f).catch(() => ({}))));
  Object.assign(D, { meta, cat, geo, themes, caveats, breaks, gaps, registry, entities });
  D.geoIx = Object.fromEntries(geo.map((g) => [g.code, g]));
  D.catIx = Object.fromEntries(cat.map((c) => [c.code, c]));
  $("#release").textContent = "release " + meta.release_id.replace("core-", "");
  window.addEventListener("hashchange", route);
  initPalette();
  initSort();
  $("#burger").onclick = () => $("#side").classList.toggle("open");
  $("#copyLink").onclick = () => copy(location.href, "Link to this view copied");
  route();
}

function logo() {
  // IKRAM's own logo file wins when present (site/assets/ikram-logo.png); otherwise a plain mark
  const el = $("#logo");
  const img = new Image(); img.alt = "IKRAM"; img.src = "assets/ikram-logo.png";
  img.onload = () => { el.innerHTML = ""; el.appendChild(img); };
  el.innerHTML = `<svg viewBox="0 0 34 34" aria-label="IKRAM"><rect width="34" height="34" rx="9" fill="#0f8fb0"/><circle cx="17" cy="10" r="4.2" fill="#1f9d4f" stroke="#fff" stroke-width="1.4"/><rect x="13.6" y="16" width="6.8" height="11.5" rx="2.2" fill="#fff"/></svg>`;
}

function initTheme() {
  const saved = (() => { try { return localStorage.getItem("theme"); } catch { return null; } })();
  if (saved) document.documentElement.dataset.theme = saved;
  $("#themeBtn").onclick = () => {
    const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch {}
    route();
  };
}

function route() {
  const [path] = hashParams();
  const seg = path.split("/").filter(Boolean);
  const top = seg[0] || "about";
  $$("#nav a").forEach((a) => a.classList.toggle("on", a.dataset.r === (top === "state" ? "states" : top === "bubbles" ? "compare" : top)));
  $("#side").classList.remove("open");
  const v = $("#view");
  window.scrollTo(0, 0);
  const R = { about: viewAbout, explore: (v) => (seg[1] ? viewIndicator(decodeURIComponent(seg[1]), v) : viewExplore(v)),
    gaps: (v) => (seg[1] ? viewGap(seg[1], v) : viewGaps(v)), states: viewStates, state: (v) => viewState(decodeURIComponent(seg[1] || ""), v),
    sources: viewSources, method: viewMethod, compare: viewBubbles, bubbles: viewBubbles };
  Promise.resolve((R[top] || viewAbout)(v)).catch((e) => { v.innerHTML = `<div class="note">Could not load this view: ${esc(e.message)}</div>`; console.error(e); });
}

/* =====================================================================================================
   ABOUT
   ===================================================================================================== */
async function viewAbout(v) {
  crumbs([["About", "#/about"]]);
  const m = D.meta, sc = m.scale || {};
  // every number on this page is computed from the warehouse on load, so the page can never drift from the data
  const [pl, ob, tg, ra, rev] = await Promise.all([
    ...["gap_federal_placement", "gap_obligations_growth", "gap_target_vs_outcome", "gap_reported_vs_audited"].map((n) => J(`gap/${n}.json`).then(objs).catch(() => [])),
    J("ind/federal_gov.revenue.total.json").catch(() => null)]);
  const plMY = pl.filter((r) => r.geo_code === "MY" && r.placed_share != null).sort((a, b) => a.year - b.year);
  const plLast = plMY[plMY.length - 1] || {};
  const obY = Math.max(...ob.map((r) => +r.year));
  const obOf = (k) => ob.find((r) => +r.year === obY && r.instrument === k) || {};
  const below = tg.filter((r) => /^below/.test(r.status)).length, above = tg.filter((r) => r.status === "above_target").length;
  const bothRA = ra.filter((r) => r.bnm_vs_pkkp_status && r.bnm_vs_pkkp_status !== "not_held"), agreeRA = bothRA.filter((r) => r.bnm_vs_pkkp_status === "agree").length;
  const HELD = new Set(["verified", "extracted", "held"]);
  const held = D.registry.filter((r) => HELD.has(r.status));

  // anatomy of a number: the latest audited federal revenue, walked back to its page and file
  let anat = "";
  if (rev) {
    const rr = rev.rows.map((r) => Object.fromEntries(COLS.map((k, i) => [k, r[i]])));
    const aud = rr.filter((r) => r.geo === "MY" && r.basis === "audited" && r.breakdown === "_total").sort((a, b) => b.period.localeCompare(a.period))[0];
    if (aud) {
      const ci = rev.cites[aud.cite] || {}, ed = rev.editions[aud.edition] || {};
      const bnm = rr.find((r) => r.geo === "MY" && r.period === aud.period && r.basis !== "audited" && (rev.editions[r.edition]?.publisher || "") === "bnm");
      const step = (k, val, sub) => `<div class="an-row"><span class="an-k">${k}</span><span class="an-v">${val}${sub ? `<small>${sub}</small>` : ""}</span></div>`;
      anat = `<div class="anat card"><div class="an-head"><span class="small muted">Anatomy of a number</span><a class="small" href="#/explore/federal_gov.revenue.total">Open the series →</a></div>
        <div class="an-big">${compact(aud.value, "RM")}</div><div class="small muted" style="margin:-2px 0 12px">Federal revenue, ${esc(aud.period)}, audited</div>
        ${step("As printed", `RM ${exact(aud.value)}`)}
        ${step("Document", esc(ed.id ? ed.id.replace(/^pkkp:/, "").replace(/_/g, " ").replace(/\.pdf$/, "") : "–"), "Federal Government Financial Statements, audited")}
        ${step("Table and page", `${esc(ci.table || "–")}${ci.pdf_page ? ` · pdf page ${esc(ci.pdf_page)}` : ""}${ci.printed_page ? ` (printed ${esc(ci.printed_page)})` : ""}`)}
        ${step("File fingerprint", `<span class="mono">${esc((ci.sha256 || "").slice(0, 16))}…</span>`, "sha256 of the archived PDF")}
        ${step("Source row", `<span class="mono small">${l1link(aud.l1_ref)}</span>`)}
        ${bnm ? step("Cross-check", `Bank Negara prints RM ${exact(bnm.value)}`, bnm.value === aud.value ? "the same to the ringgit" : `a difference of RM ${exact(Math.abs(bnm.value - aud.value))}, kept and shown`) : ""}
      </div>`;
    }
  }

  const spark = (pts, color = "var(--accent)", ref) => {
    if (pts.length < 2) return "";
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]).concat(ref != null ? [ref] : []);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(0, ...ys), y1 = Math.max(...ys);
    const X = (x) => 4 + ((x - x0) / (x1 - x0 || 1)) * 252, Y = (y) => 56 - ((y - y0) / (y1 - y0 || 1)) * 50;
    return `<svg viewBox="0 0 260 62" class="fspark" aria-hidden="true">${ref != null ? `<line x1="4" x2="256" y1="${Y(ref)}" y2="${Y(ref)}" stroke="var(--warn)" stroke-dasharray="3,3"/>` : ""}<polyline points="${pts.map((p) => `${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(" ")}" fill="none" stroke="${color}" stroke-width="2"/></svg>`;
  };
  const bar = (a, b, la, lb) => `<div class="fbar"><span style="flex:${a}">${la}</span><span style="flex:${b}" class="o">${lb}</span></div>`;
  const obSeries = (k) => ob.filter((r) => r.instrument === k && r.index_first_year != null).sort((a, b) => a.year - b.year).map((r) => [+r.year, r.index_first_year]);
  const finding = (big, title, txt, viz, href) => `<a class="finding2 card link" href="${href}"><div class="f-big">${big}</div><h3>${title}</h3><p>${txt}</p>${viz}<span class="small">See the evidence →</span></a>`;
  const themeRows = Object.entries(D.themes).filter(([k]) => k !== "cross").map(([k, name]) => {
    const rs = D.registry.filter((r) => String(r.theme || "").split(";").includes(k));
    const h = rs.filter((r) => HELD.has(r.status)).length, n = D.cat.filter((c) => c.theme === k).length;
    const obsN = D.cat.filter((c) => c.theme === k).reduce((s, c) => s + c.n, 0);
    return { k, name, h, all: rs.length, n, obsN };
  });
  const sec = (title, intro, body) => `<section class="sec"><div class="sec-l"><h2>${title}</h2>${intro ? `<p>${intro}</p>` : ""}</div><div class="sec-r">${body}</div></section>`;

  v.innerHTML = `
  <section class="hero2">
    <div>
      <div class="kicker">Malaysia Economy Data Warehouse · by IKRAM</div>
      <h1 class="display">From data to policy change.</h1>
      <p class="lede big">Malaysia publishes what it plans, collects, spends and audits. But it is spread across hundreds of documents, a dozen websites and many formats. This warehouse puts it in one place, checks every number against its source, and shows where the institutions agree and where they don't.</p>
      <p class="lede big" style="margin-top:10px">So a policy case can rest on evidence that anyone can verify.</p>
      <div class="row" style="margin:22px 0 8px;gap:10px"><a class="btn primary lg" href="#/gaps">Start with a question →</a><a class="btn lg" href="#/explore">Explore the data</a><a class="btn lg" href="#/compare">Compare over time</a></div>
      <div class="muted small">Tip: press <kbd>⌘K</kbd> (or Ctrl K) anywhere to search.</div>
    </div>
    ${anat}
  </section>

  <div class="stats big">
    <div><b>${million(sc.source_rows)}</b><span>rows copied from ${NF(0).format(sc.source_tables)} official tables, as printed</span></div>
    <div><b>${NF(0).format(m.observations)}</b><span>numbers on one common core, each linked to its page</span></div>
    <div><b>${NF(0).format(sc.checks)}</b><span>automatic checks, re-run on every change</span></div>
    <div><b>${NF(0).format(sc.l0_files)}</b><span>original documents archived (${NF(1).format(sc.l0_gb)} GB), never overwritten</span></div>
    <div><b>${sc.anomalies}</b><span>publisher errors caught and kept as printed, with proof</span></div>
    <div><b>${sc.series_held} <small>of ${m.series_registered}</small></b><span>official series held, from the list of what policy work needs</span></div>
    <div><b>${NF(0).format(m.places)}</b><span>places: Malaysia, 16 states and FTs, every district, parlimen and DUN</span></div>
    <div><b>${sc.first_year}–${sc.last_year}</b><span>${sc.last_year - sc.first_year + 1} years of history</span></div>
  </div>
  <p class="muted small" style="margin:8px 0 0">Counted from the repository every time this site is built.</p>

  ${sec("What it has found so far", "Four findings that only appear when sources are read side by side. Each opens the rows, the chart and the caveats behind it.", `<div class="findings">
    ${finding(pct(plLast.placed_share), "Most federal money has no address", `Only this share of federal spending in ${plLast.year} can be placed in a state from the federal accounts. Salaries, subsidies, cash aid and most projects carry no location. Any claim about federal spending "in" a state needs a source.`, spark(plMY.map((r) => [+r.year, r.placed_share]), "var(--accent)", 0.6) + `<div class="small muted">Share placeable by year; dashed line: the 60% needed before amounts by state are published.</div>`, "#/gaps/gap_federal_placement")}
    ${finding(compact(obOf("commitments").amount_rm, "RM"), "Obligations sit outside the debt figure", `Financial commitments in ${obY}, beside ${compact(obOf("pfi").amount_rm, "RM")} of PFI liabilities and ${compact(obOf("loan_guarantees").amount_rm, "RM")} of loan guarantees. None is counted in the ${compact(obOf("debt").amount_rm, "RM")} of federal debt. They can overlap, so they are never added up.`, spark(obSeries("loan_guarantees"), "var(--s2)") + `<div class="small muted">Loan guarantees, indexed to the first year held (federal debt: +${pct((obOf("debt").index_first_year || 0) / 100 - 1, 0)} over the same years).</div>`, "#/gaps/gap_obligations_growth")}
    ${finding(`${below} of ${tg.length}`, "The Plan's targets, against outcomes", `Twelfth Malaysia Plan targets ended below the number the Plan set; ${above} ended above. Below is not always bad: lower unemployment is good news, a lower GDP is not. Every target is shown beside its outcome and its source.`, bar(below, above, `${below} below`, `${above} above`), "#/gaps/gap_target_vs_outcome")}
    ${finding(`${agreeRA} of ${bothRA.length}`, "Three institutions, one number?", `Times Bank Negara's fiscal figure matches the audited accounts. Where they differ, both are kept and the gap is measured, from a few ringgit to over a million.`, bar(agreeRA, bothRA.length - agreeRA, `${agreeRA} agree`, `${bothRA.length - agreeRA} differ`), "#/gaps/gap_reported_vs_audited")}
  </div>`)}

  ${sec("Why it exists", "The data is already public. Using it well is the hard part.", `<div class="tablewrap" style="max-height:none"><table class="cmp ww">
    <thead><tr><th style="width:20%">When you want to…</th><th>Without the warehouse</th><th>With it</th></tr></thead><tbody>
    <tr><td><b>Find a figure</b></td><td class="x">Search PDFs on many websites, each in its own format and language.</td><td class="y">Search once. One set of codes, one timeline, ${NF(0).format(m.places)} places.</td></tr>
    <tr><td><b>Prove it</b></td><td class="x">Quote a number and hope no one asks for the page.</td><td class="y">Every value cites its document, table, page and file fingerprint.</td></tr>
    <tr><td><b>Compare sources</b></td><td class="x">MOF, Bank Negara and the audited accounts print different figures. Which is right?</td><td class="y">All of them side by side, with the difference measured.</td></tr>
    <tr><td><b>Compare places</b></td><td class="x">States, districts and constituencies use different codes and boundaries.</td><td class="y">Official codes throughout, from the nation to every DUN.</td></tr>
    <tr><td><b>Track change</b></td><td class="x">Methods change quietly, and old and new numbers get mixed.</td><td class="y">Changes of method are marked, and never compared across.</td></tr>
    <tr><td><b>Judge certainty</b></td><td class="x">A survey estimate looks as exact as an audited account.</td><td class="y">Uncertainty is carried, and small areas are never ranked.</td></tr>
    </tbody></table></div>`)}

  ${sec("How it compares", "The official portals are where these figures are born, and the place for the newest release. This warehouse adds what none of them does alone: different publishers on the same page.", `<div class="tablewrap" style="max-height:none"><table class="cmp">
    <thead><tr><th>What you need</th><th>This warehouse</th><th>OpenDOSM / data.gov.my</th><th>World Bank WDI</th><th>MOF / AG portals</th></tr></thead>
    <tbody>
      ${cmpRow("Statistics of people, jobs, prices", "y:Yes, from DOSM", "y:Yes, the source", "p:National only", "x:No")}
      ${cmpRow("Federal budget, accounts and audit together", "y:Yes, FY2009–2026", "x:No", "x:No", "p:Separate PDFs")}
      ${cmpRow("State governments' own accounts", "y:13 states", "x:No", "x:No", "p:Per state, as PDFs")}
      ${cmpRow("Below state: district, parlimen, DUN", "y:Yes, flagged", "y:Yes", "x:No", "x:No")}
      ${cmpRow("Same figure from different publishers, compared", "y:Agree / differ, by how much", "x:No", "x:No", "x:No")}
      ${cmpRow("Every value cited to table, page and file", "y:Yes", "p:Dataset level", "p:Series level", "p:Document level")}
      ${cmpRow("Series breaks and caveats on the chart", "y:Yes", "p:In notes", "p:In notes", "x:No")}
      ${cmpRow("Plan targets vs outcomes", "y:RMKe-12", "x:No", "x:No", "x:No")}
      ${cmpRow("Typed tools for AI agents, every answer cited", "y:Yes", "p:API", "p:API", "x:No")}
      ${cmpRow("Latest release, same day", "p:Daily for DOSM", "y:Yes", "p:Annual", "y:Yes")}
      ${cmpRow("International comparison", "x:Malaysia only", "x:No", "y:Yes", "x:No")}
    </tbody></table></div>
    <p class="muted small" style="margin-top:8px">● yes &nbsp; ◐ in part &nbsp; ○ no</p>`)}

  ${sec("How a number gets here", "Five layers. Each is rebuilt from the one below, so any figure on this site can be walked back to the file it came from.", `<div class="pipe">
    ${[["L0", "Raw files", "Every PDF and data file, exactly as released, kept by its sha256 fingerprint.", `${NF(0).format(sc.l0_files)} files`],
       ["L1", "Source tables", "Each table copied as printed, row by row. The publisher's own totals are re-added; a misprint is kept and documented, never corrected.", `${million(sc.source_rows)} rows`],
       ["L2", "One common core", "The same codes for place, time, measure, body and source, so different publishers can sit side by side.", `${NF(0).format(m.observations)} numbers`],
       ["L3", "Gap views", "Named comparisons with methods fixed before the results were seen: budget vs spending, plan vs outcome, need vs money.", `${m.gap_views} views`],
       ["L4", "Ways in", "This website, CSV downloads, and typed tools for AI agents that never return a number without its citation.", "3 ways in"]]
      .map(([t, b, d, n]) => `<div class="pstep"><div class="pt">${t}</div><b>${b}</b><p>${d}</p><span class="chip accent">${n}</span></div>`).join("")}
  </div>`)}

  ${sec("How every number is checked", "No single safeguard is enough. Each one catches what the one before it cannot. What fails is not shown.", `<div class="tablewrap" style="max-height:none"><table class="cmp">
    <thead><tr><th style="width:26%">Check</th><th>What it does</th><th style="width:18%">When</th></tr></thead><tbody>
    <tr><td><b>The source's own sums</b></td><td>Every printed total is re-added from its printed parts. A publisher's error is kept as printed, with proof (${sc.anomalies} so far).</td><td class="small">at extraction</td></tr>
    <tr><td><b>Automatic checks</b></td><td>${NF(0).format(sc.checks)} checks and ${sc.eval_questions} test questions re-run on every change; anything that alters a figure is blocked.</td><td class="small">every change</td></tr>
    <tr><td><b>Independent reviewer</b></td><td>A separate reviewer, blind to the code, re-derives figures from the original pages and tries to break them.</td><td class="small">every new source</td></tr>
    <tr><td><b>Source against source</b></td><td>The same figure from different institutions is compared to the ringgit; differences are published, not hidden.</td><td class="small">every build</td></tr>
    <tr><td><b>A person</b></td><td>A human checks a random sample against the archived page before IKRAM publishes a finding.</td><td class="small">before publication</td></tr>
    <tr><td><b>Nothing overwritten</b></td><td>Every raw file and every data release is kept, so any figure can be re-checked years later.</td><td class="small">always</td></tr>
    </tbody></table></div>
    <p class="muted small" style="margin-top:8px">Example: the audit-findings inventory failed its independent review on 2026-11-06, so it stays a draft and is not on this site.</p>`)}

  ${sec("What is inside", "Nine themes across the economy. The bars show how much of each theme's needed data is already held.", `<div class="tablewrap" style="max-height:none"><table class="cov">
    <thead><tr><th>Theme</th><th class="n">Indicators</th><th class="n">Numbers</th><th style="width:34%">Series held</th></tr></thead><tbody>
    ${themeRows.map((t) => `<tr><td><a href="#/explore?theme=${t.k}">${esc(t.name)}</a></td><td class="n">${t.n}</td><td class="n">${NF(0).format(t.obsN)}</td><td><div class="covbar"><i style="width:${t.all ? (100 * t.h) / t.all : 0}%"></i></div><span class="small muted">${t.h} of ${t.all}</span></td></tr>`).join("")}
    </tbody></table></div>
    <details class="srcs"><summary>Every source held, one by one (${held.length})</summary>
      <input type="search" id="srcq" placeholder="Filter sources…" style="width:240px;margin:10px 0">
      <div class="tablewrap" id="srct" style="max-height:420px"><table><thead><tr><th>Theme</th><th>Publisher</th><th>Series</th><th>What we hold</th></tr></thead><tbody>
      ${[...held].sort((a, b) => String(a.theme).localeCompare(String(b.theme), "en", { numeric: true })).map((r) => `<tr><td class="small">${esc(themeName(String(r.theme || "").split(";")[0]))}</td><td class="small">${esc(r.publisher)}</td><td>${esc(r.title_en)}</td><td class="small muted">${esc(r.held_coverage)}</td></tr>`).join("")}
      </tbody></table></div></details>`)}

  ${sec("Who it is for", "Built for people who need to be right in public.", `<div class="tablewrap" style="max-height:none"><table class="cmp">
    <thead><tr><th style="width:20%">You are</th><th>You can</th><th style="width:22%">Start here</th></tr></thead><tbody>
    <tr><td><b>Policy advocate</b></td><td>Ask a question in plain words and leave with a finding, its source and its caveats, ready for a brief.</td><td><a href="#/gaps">Policy gaps</a></td></tr>
    <tr><td><b>Data analyst</b></td><td>Pull any series by place, group and year, as published, with every citation; download it as CSV.</td><td><a href="#/explore">Explore data</a></td></tr>
    <tr><td><b>Journalist</b></td><td>Check a claim in seconds: what was budgeted, what was spent, and where it is printed.</td><td><a href="#/gaps/gap_budget_vs_actual">Budget vs actual</a></td></tr>
    <tr><td><b>Elected representative</b></td><td>See your state beside Malaysia on poverty, income, jobs and the state's own accounts.</td><td><a href="#/states">States</a></td></tr>
    <tr><td><b>Researcher</b></td><td>Set two measures against each other for states, ministries or projects, across years, and rebuild any figure from the repository.</td><td><a href="#/compare">Compare</a></td></tr>
    </tbody></table></div>`)}

  ${sec("Rules it never breaks", "These hold for every number, in every view.", `<div class="rules">
    ${[["Kept as printed", "A publisher's figure is never silently corrected. Errors are documented beside it."],
       ["Cited, always", "No number appears without its document, page and file."],
       ["Neutral by design", "Methods are fixed before results are seen. Every view covers all 13 states and the Federal Territories. No party data is held."],
       ["Honest about doubt", "Survey estimates carry their uncertainty. Small areas are never ranked."],
       ["Lawful and private", "Only lawfully published documents. Individuals are never shown. Licences are tracked for every series, and takedown requests are honoured."],
       ["Open to check", "Every table and the code that built it are public, so anyone can rebuild a figure."]]
      .map(([t, d]) => `<div class="rule"><b>${t}</b><p>${d}</p></div>`).join("")}
  </div>`)}

  ${sec("Limits, and what comes next", "What it cannot tell you yet, stated plainly.", `<div class="grid g2">
    <div class="note"><b>Small places are estimates.</b> DOSM publishes no error margin below state level. A small gap between two districts may not be real.</div>
    <div class="note"><b>Most federal money has no address.</b> Federal amounts by state stay hidden until at least 60% can be placed (today ${pct(plLast.placed_share)}).</div>
    <div class="note"><b>Some years are missing.</b> A gap in a line is a year with no published figure, not a zero.</div>
    <div class="note"><b>Malaysia only.</b> For other countries, use the World Bank or the IMF.</div>
  </div>
  <h3 style="margin:20px 0 8px">Next to be added</h3>
  <ul class="next2">
    <li>Audit findings by ministry, once the inventory passes its re-check.</li>
    <li>Welfare and health by state: social transfers and the National Health and Morbidity Survey.</li>
    <li>Procurement awards from MyProcurement, companies only.</li>
    <li>Environment, climate and disasters beyond what DOSM already gives.</li>
    <li>State budget books for every state, beside their audited accounts.</li>
  </ul>`)}

  <div class="cta card">
    <div><h3 style="margin:0 0 4px">Open by design.</h3><p class="muted small" style="margin:0">Every table is a plain CSV in the <a href="${REPO}" target="_blank" rel="noopener">repository</a>, with the code that built it and the checks it passed. Release ${esc(m.release_id.replace("core-", ""))}. <a href="#/method">Method &amp; trust →</a></p></div>
    <a class="btn primary lg" href="#/gaps">Ask your first question →</a>
  </div>`;
  $("#srcq") && ($("#srcq").oninput = (e) => filterTable($("#srct"), e.target.value));
}

const kpi = (v, l) => `<div class="card kpi"><div class="v">${v}</div><div class="l">${l}</div></div>`;
const layer = (t, b, d) => `<div class="layer"><div class="t">${t}</div><b>${b}</b><div class="small muted">${d}</div></div>`;
const step = (n, t, d) => `<div class="card"><div class="mono" style="color:var(--accent)">0${n}</div><h3 style="margin-top:4px">${t}</h3><div class="small muted">${d}</div></div>`;
const use = (t, d, h) => `<a class="card link" href="${h}"><h3>${t}</h3><div class="small muted">${d}</div></a>`;
function cmpRow(k, ...cells) { return `<tr><td>${k}</td>${cells.map((c) => { const [cl, t] = c.split(/:(.*)/s); return `<td class="${cl}">${{ y: "●", p: "◐", x: "○" }[cl]} ${esc(t)}</td>`; }).join("")}</tr>`; }

/* =====================================================================================================
   EXPLORE (catalogue)
   ===================================================================================================== */
function viewExplore(v) {
  crumbs([["Explore data", "#/explore"]]);
  const [, P] = hashParams();
  const st = { q: P.get("q") || "", theme: P.get("theme") || "", lvl: P.get("lvl") || "", pub: P.get("pub") || "", sort: P.get("sort") || "theme" };
  const themes = [...new Set(D.cat.map((c) => c.theme))].sort((a, b) => (a === "cross") - (b === "cross") || a.localeCompare(b, "en", { numeric: true }));
  const pubs = [...new Set(D.cat.flatMap((c) => c.publishers))].sort();
  const y0 = D.meta.scale?.first_year || 1957, y1 = D.meta.scale?.last_year || 2026;
  const LV = { country: ["MY", "Malaysia"], state: ["ST", "States"], district: ["DT", "Districts"], parlimen: ["PAR", "Parlimen"], dun: ["DUN", "DUN"] };
  const SORTS = { theme: "Theme", name: "Name", latest: "Most recent", longest: "Longest history", places: "Most places", data: "Most data" };
  v.innerHTML = `
    <div class="phead"><div><h1>Explore data</h1><p class="lede">${D.cat.length} indicators, ${NF(0).format(D.meta.observations)} numbers. Pick one and see it as published, by place, year and group, with every value cited.</p></div>
      <div class="pactions"><button class="btn" id="eCsv" type="button">Download catalogue</button></div></div>
    <label class="searchbar"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
      <input type="search" id="eq" placeholder="Search indicators: poverty, wages, hospital beds, inflation…" value="${esc(st.q)}" autocomplete="off"><span class="muted small" id="eCount"></span></label>
    <div class="pills" id="fTheme"></div>
    <div class="toolbar slim">
      <div><span class="tl-lab">Level</span><select id="fLvl"><option value="">Any</option>${Object.entries(LV).map(([k, [, l]]) => `<option value="${k}" ${st.lvl === k ? "selected" : ""}>${l}</option>`).join("")}</select></div>
      <div><span class="tl-lab">Publisher</span><select id="fPub"><option value="">Any</option>${pubs.map((p) => `<option value="${esc(p)}" ${st.pub === p ? "selected" : ""}>${esc(pubName(p))}</option>`).join("")}</select></div>
      <div><span class="tl-lab">Sort</span><select id="fSort">${Object.entries(SORTS).map(([k, l]) => `<option value="${k}" ${st.sort === k ? "selected" : ""}>${l}</option>`).join("")}</select></div>
      <button class="btn ghost" id="fClear" type="button">Clear filters</button>
    </div>
    <div class="ilist"><div class="irow ihead"><span>Indicator</span><span class="hide-sm">Levels</span><span class="hide-sm">Coverage, ${y0}–${y1}</span><span class="n hide-sm">Numbers</span></div><div id="eList"></div></div>`;
  const match = (c, s2) => {
    if (s2.theme && c.theme !== s2.theme) return false;
    if (s2.lvl && !c.levels.includes(s2.lvl)) return false;
    if (s2.pub && !c.publishers.includes(s2.pub)) return false;
    if (s2.q) { const t = (c.name + " " + c.code + " " + c.definition + " " + c.name_bm + " " + c.source + " " + themeName(c.theme)).toLowerCase(); return s2.q.toLowerCase().split(/\s+/).every((w) => t.includes(w)); }
    return true;
  };
  const yr = (p) => +String(p).slice(0, 4);
  const row = (c) => {
    const a = yr(c.first), b = yr(c.last), L = ((a - y0) / (y1 - y0 + 1)) * 100, W = Math.max(1.2, ((b - a + 1) / (y1 - y0 + 1)) * 100);
    return `<a class="irow" href="#/explore/${encodeURIComponent(c.code)}${st.lvl ? "?lvl=" + st.lvl : ""}">
      <span class="iname"><b>${esc(c.name)}</b><small>${esc(c.definition || "")}</small><span class="imeta"><i class="tdot t${esc(c.theme)}"></i>${esc(themeName(c.theme))} · ${esc(c.unit || "–")}${c.n_breakdowns > 1 ? ` · ${c.n_breakdowns} breakdowns` : ""} · ${c.publishers.map((p) => esc(pubName(p))).join(", ")}</span></span>
      <span class="ilv hide-sm">${Object.entries(LV).map(([k, [ab, l]]) => `<i class="${c.levels.includes(k) ? "on" : ""}" title="${l}">${ab}</i>`).join("")}</span>
      <span class="itl hide-sm" title="${esc(c.first)} to ${esc(c.last)}"><span class="track"><span class="bar" style="left:${L.toFixed(1)}%;width:${W.toFixed(1)}%"></span></span><small class="mono">${esc(c.first)}${c.last !== c.first ? "–" + esc(c.last) : ""}</small></span>
      <span class="n mono small hide-sm">${NF(0).format(c.n)}</span></a>`;
  };
  function draw() {
    const P2 = new URLSearchParams(); Object.entries(st).forEach(([k, x]) => x && !(k === "sort" && x === "theme") && P2.set(k, x)); setParams("/explore", P2);
    $("#fTheme").innerHTML = [["", "All"], ...themes.map((t) => [t, themeName(t)])].map(([k, l]) => {
      const n = D.cat.filter((c) => match(c, { ...st, theme: k })).length;
      return `<button type="button" data-k="${esc(k)}" class="pill ${st.theme === k ? "on" : ""}" ${n ? "" : "disabled"}>${k ? `<i class="tdot t${esc(k)}"></i>` : ""}${esc(l)} <span>${n}</span></button>`; }).join("");
    $$("#fTheme button").forEach((b) => (b.onclick = () => { st.theme = b.dataset.k; draw(); }));
    let rs = D.cat.filter((c) => match(c, st));
    const by = { name: (a, b) => a.name.localeCompare(b.name), latest: (a, b) => yr(b.last) - yr(a.last) || a.name.localeCompare(b.name), longest: (a, b) => (yr(b.last) - yr(b.first)) - (yr(a.last) - yr(a.first)),
      places: (a, b) => b.n_geo - a.n_geo, data: (a, b) => b.n - a.n, theme: (a, b) => a.theme.localeCompare(b.theme, "en", { numeric: true }) || a.name.localeCompare(b.name) };
    rs.sort(by[st.sort] || by.theme);
    $("#eCount").textContent = `${rs.length} of ${D.cat.length}`;
    let html = "";
    if (st.sort === "theme" && !st.theme) { let cur = null; for (const c of rs) { if (c.theme !== cur) { cur = c.theme; const n = rs.filter((x) => x.theme === cur).length; html += `<div class="igroup"><i class="tdot t${esc(cur)}"></i>${esc(themeName(cur))} <span>${n}</span></div>`; } html += row(c); } }
    else html = rs.map(row).join("");
    $("#eList").innerHTML = html || `<div class="skel">Nothing matches. Try fewer words, or <a href="#/explore">clear the filters</a>.</div>`;
  }
  $("#eq").oninput = (e) => { st.q = e.target.value; draw(); };
  $("#fLvl").onchange = (e) => { st.lvl = e.target.value; draw(); };
  $("#fPub").onchange = (e) => { st.pub = e.target.value; draw(); };
  $("#fSort").onchange = (e) => { st.sort = e.target.value; draw(); };
  $("#fClear").onclick = () => { Object.assign(st, { q: "", theme: "", lvl: "", pub: "", sort: "theme" }); $("#eq").value = ""; $("#fLvl").value = ""; $("#fPub").value = ""; $("#fSort").value = "theme"; draw(); };
  $("#eCsv").onclick = () => download("catalogue.csv", toCSV(["code", "name", "theme", "unit", "statistic", "first", "last", "levels", "publishers", "observations", "definition"],
    D.cat.map((c) => [c.code, c.name, themeName(c.theme), c.unit, c.statistic, c.first, c.last, c.levels.join(";"), c.publishers.join(";"), c.n, c.definition])));
  draw();
  setTimeout(() => $("#eq")?.focus(), 30);
}

/* =====================================================================================================
   INDICATOR
   ===================================================================================================== */
const COLS = ["geo", "period", "breakdown", "value", "edition", "basis", "status", "ci_low", "ci_high", "reliability", "cite", "l1_ref", "caveats"];
const BASIS = { statistic: "Published statistic", audited: "Audited actual (PKKP)", actual: "Actual (as reported)", budget_estimate: "Budget estimate",
  revised_estimate: "Revised estimate", allocation: "Allocation", target: "Plan target" };

async function viewIndicator(code, v = $("#view")) {
  const c = D.catIx[code];
  if (!c) { v.innerHTML = `<div class="note">No indicator <span class="mono">${esc(code)}</span>. <a href="#/explore">Back to the catalogue</a></div>`; return; }
  crumbs([["Explore data", "#/explore"], [themeName(c.theme), "#/explore?theme=" + c.theme], [c.name, ""]]);
  v.innerHTML = `<div class="skel">Loading ${esc(c.name)}…</div>`;
  const d = await J(`ind/${code}.json`);
  const rows = d.rows.map((r) => Object.fromEntries(COLS.map((k, i) => [k, r[i]])));
  const [, P] = hashParams();
  const levels = c.levels.filter((l) => l !== "unallocated");
  const brks = [...new Set(rows.map((r) => r.breakdown))].sort((a, b) => (a !== "_total") - (b !== "_total") || (a.startsWith("body=") - b.startsWith("body=")) || brkLabel(a).localeCompare(brkLabel(b), "en", { numeric: true }));
  const bases = [...new Set(rows.map((r) => r.basis))];
  const st = {
    b: brks.includes(P.get("b")) ? P.get("b") : brks[0],
    lvl: levels.includes(P.get("lvl")) ? P.get("lvl") : levels.includes("country") ? "country" : levels.includes("state") ? "state" : levels[0],
    geo: (P.get("geo") || "").split(",").filter(Boolean),
    view: P.get("view") || "chart", show: P.get("show") || "value",
    basis: bases.length > 1 ? (P.get("basis") || "") : "",
    ctx: P.get("ctx") ?? "",
  };
  const reg = D.registry.find((r) => r.series_id === (c.source || "").split(":").pop());
  const breaks = D.breaks.filter((b) => code.startsWith(b.indicator_prefix));
  v.innerHTML = `
    <div class="phead"><div style="min-width:0">
        <div class="row" style="gap:6px">${chip(esc(themeName(c.theme)))}${c.publishers.map((p) => chip(esc(pubName(p)), "accent")).join("")}</div>
        <h1>${esc(c.name)}</h1><p class="lede clamp3" id="defn" title="Click to expand">${esc(c.definition)}</p></div>
      <div class="pactions"><button class="btn" id="dl" type="button">Download CSV</button><button class="btn" id="cite" type="button">Cite</button><button class="btn" id="share" type="button">Share</button></div></div>
    <div class="split">
      <div class="main-col">
        <div class="answer" id="headline"></div>
        <div class="toolbar" id="ctl"></div>
        <div class="card"><div id="chartHead" class="row" style="justify-content:space-between;margin-bottom:4px"></div><div class="legend" id="legend"></div><div class="chart" id="chart"></div><div id="chartNotes" class="small muted" style="margin-top:8px"></div></div>
        <div id="tilesBox"></div>
        <div class="sechead"><h2>Values and sources</h2><span class="small muted" id="tCount"></span><input type="search" id="tq" placeholder="Filter rows…"></div>
        <div class="tablewrap" id="tbl"></div>
      </div>
      <aside class="insp">
        <div class="insp-sec"><h4>At a glance</h4><div class="kvs">
          <div><span>Coverage</span><b>${esc(c.first)}–${esc(c.last)}</b></div><div><span>Numbers</span><b>${NF(0).format(rows.length)}</b></div>
          <div><span>Places</span><b>${NF(0).format(c.n_geo)}</b></div><div><span>Breakdowns</span><b>${NF(0).format(c.n_breakdowns)}</b></div>
          <div><span>Unit</span><b>${esc(c.unit)}</b></div><div><span>Statistic</span><b>${esc(c.statistic || "–")}</b></div></div></div>
        <div class="insp-sec"><h4>Caveats</h4><div id="cavs" class="small"></div>${breaks.map((b) => `<div class="note" style="margin-top:8px"><b>Method changed in ${esc(b.first_period_new_basis)}.</b> ${esc(b.what_changed)}</div>`).join("")}</div>
        <div class="insp-sec"><h4>About this indicator</h4><table class="small">${kv("Universe", esc(c.universe))}${kv("Price basis", esc(c.price_basis))}${kv("Adds up across places", c.additive_geo === "true" ? "Yes" : c.additive_geo === "false" ? "No: do not sum places" : "")}${kv("Malay name", esc(c.name_bm))}${kv("Coverage", esc(c.coverage_note))}${reg ? kv("Licence", esc(reg.licence) + (reg.redistribution ? ` · ${esc(reg.redistribution)}` : "")) : ""}${kv("Source", `<span class="mono">${esc(c.source)}</span>`)}${kv("Code", `<span class="mono">${esc(code)}</span>`)}</table></div>
        <div class="insp-sec"><h4>Next steps</h4><div class="links">
          ${c.levels.includes("state") ? `<a href="#/compare?x=${encodeURIComponent(code)}">Compare against another measure →</a>` : ""}
          <a href="#/explore?theme=${esc(c.theme)}">More in ${esc(themeName(c.theme))} →</a><a href="#/method">How the charts are drawn →</a></div></div>
      </aside>
    </div>`;
  $("#defn").onclick = (e) => e.currentTarget.classList.toggle("open");
  $("#share").onclick = () => copy(location.href, "Link to this exact view copied");

  const P2 = () => { const p = new URLSearchParams(); if (st.b !== brks[0]) p.set("b", st.b); p.set("lvl", st.lvl); if (st.geo.length) p.set("geo", st.geo.join(",")); if (st.view !== "chart") p.set("view", st.view); if (st.show !== "value") p.set("show", st.show); if (st.basis) p.set("basis", st.basis); if (st.ctx) p.set("ctx", st.ctx); return p; };
  const atLevel = (r) => (D.geoIx[r.geo]?.level || "") === st.lvl;
  function places() { return [...new Set(rows.filter((r) => r.breakdown === st.b && atLevel(r)).map((r) => r.geo))].sort((a, b) => geoLabel(a).localeCompare(geoLabel(b))); }

  function controls() {
    const pl = places();
    if (!st.geo.length || !st.geo.every((g) => pl.includes(g))) st.geo = st.geo.filter((g) => pl.includes(g));
    if (!st.geo.length) st.geo = st.lvl === "country" ? pl.slice(0, 1) : st.lvl === "state" ? [] : pl.slice(0, 1);
    const ctx = st.ctx === "" ? (st.lvl === "state" && st.geo.length === 0 ? "1" : "") : st.ctx;
    st._ctx = ctx === "1";
    $("#ctl").innerHTML = `
      ${levels.length > 1 ? `<div><div class="small muted">Level</div><div class="seg" id="sLvl">${levels.map((l) => `<button type="button" data-v="${l}" class="${l === st.lvl ? "on" : ""}">${LEVELS[l]}</button>`).join("")}</div></div>` : ""}
      ${brks.length > 1 ? `<div style="min-width:220px;flex:1"><div class="small muted">Breakdown</div><select id="sB" style="width:100%">${brks.map((b) => `<option value="${esc(b)}" ${b === st.b ? "selected" : ""}>${esc(brkLabel(b))}</option>`).join("")}</select></div>` : ""}
      ${bases.length > 1 ? `<div><div class="small muted">Basis</div><select id="sBasis"><option value="">All, each its own line</option>${bases.map((b) => `<option value="${b}" ${b === st.basis ? "selected" : ""}>${esc(BASIS[b] || b)}</option>`).join("")}</select></div>` : ""}
      ${pl.length > 1 ? `<div style="flex:2;min-width:260px"><div class="small muted">Places (${pl.length} at this level)</div><div class="row" style="gap:5px">${st.geo.map((g) => `<span class="chip">${esc(geoLabel(g))} <a href="#" data-rm="${esc(g)}" title="Remove" style="color:var(--text-3)">×</a></span>`).join("")}
        <select id="sAdd" style="max-width:220px"><option value="">+ Add a place</option>${pl.filter((g) => !st.geo.includes(g)).map((g) => `<option value="${esc(g)}">${esc(geoLabel(g))}</option>`).join("")}</select>
        ${st.lvl === "state" ? `<label class="small muted" style="display:inline-flex;gap:5px;align-items:center"><input type="checkbox" id="sCtx" ${st._ctx ? "checked" : ""}> all states as context</label>` : ""}</div></div>` : ""}
      <div><div class="small muted">Show as</div><div class="seg" id="sShow">${[["value", "Value"], ["change", c.unit === "percent" ? "Change (pts)" : "Change (%)"], ["index", "Index"]].map(([x, l]) => `<button type="button" data-v="${x}" class="${x === st.show ? "on" : ""}" title="${{ value: "The value as published", change: "Change since the previous published period, never across a change of method", index: "First period shown = 100, from the latest change of method" }[x]}">${l}</button>`).join("")}</div></div>
      <div style="margin-left:auto"><div class="small muted">View</div><div class="seg" id="sView">${["chart", ...(st.lvl === "state" ? ["grid"] : []), "table"].map((x) => `<button type="button" data-v="${x}" class="${x === st.view ? "on" : ""}">${{ chart: "Chart", grid: "Every state", table: "Table only" }[x]}</button>`).join("")}</div></div>`;
    if (st.view === "grid" && st.lvl !== "state") st.view = "chart";
    $$("#sLvl button").forEach((b) => (b.onclick = () => { st.lvl = b.dataset.v; st.geo = []; st.ctx = ""; draw(); }));
    $$("#sView button").forEach((b) => (b.onclick = () => { st.view = b.dataset.v; draw(); }));
    $$("#sShow button").forEach((b) => (b.onclick = () => { st.show = b.dataset.v; draw(); }));
    $("#sB") && ($("#sB").onchange = (e) => { st.b = e.target.value; draw(); });
    $("#sBasis") && ($("#sBasis").onchange = (e) => { st.basis = e.target.value; draw(); });
    $("#sAdd") && ($("#sAdd").onchange = (e) => { if (e.target.value) { st.geo.push(e.target.value); draw(); } });
    $("#sCtx") && ($("#sCtx").onchange = (e) => { st.ctx = e.target.checked ? "1" : "0"; draw(); });
    $$("[data-rm]", $("#ctl")).forEach((a) => (a.onclick = (e) => { e.preventDefault(); st.geo = st.geo.filter((g) => g !== a.dataset.rm); if (!st.geo.length && st.lvl === "state") st.ctx = "1"; draw(); }));
  }

  function draw() {
    controls();
    setParams("/explore/" + encodeURIComponent(code), P2());
    const sel = rows.filter((r) => r.breakdown === st.b && atLevel(r) && (!st.basis || r.basis === st.basis));
    const shown = st.geo.length ? sel.filter((r) => st.geo.includes(r.geo)) : sel;
    $("#chart").parentElement.style.display = st.view === "table" ? "none" : "";
    const nat = st.lvl !== "country" ? rows.filter((r) => r.geo === "MY" && r.breakdown === st.b && (!st.basis || r.basis === st.basis)) : [];
    if (st.view === "chart") chart(c, d, sel, st, breaks, nat);
    else if (st.view === "grid") gridChart(c, d, sel, st, breaks, nat);
    headline(c, d, sel, st, breaks, nat);
    tiles(c, d, rows, st);
    table(c, d, st.geo.length ? shown : sel);
    $("#tq").oninput = (e) => filterTable($("#tbl"), e.target.value);
    const used = new Set(sel.flatMap((r) => (r.caveats || "").split(";").filter(Boolean)));
    $("#cavs").innerHTML = [...used].sort().map((k) => `<div style="margin-bottom:6px"><span class="chip warn">${esc(k)}</span> ${esc(D.caveats[k] || "")}</div>`).join("") || `<span class="muted">No caveat is attached to these rows.</span>`;
  }

  $("#dl").onclick = () => {
    const sel = rows.filter((r) => r.breakdown === st.b && atLevel(r) && (!st.geo.length || st.geo.includes(r.geo)));
    download(`${code}.csv`, toCSV(["indicator", "geo_code", "place", "period", "breakdown", "value", "unit", "basis", "edition", "table", "pdf_page", "printed_page", "file_sha256", "l1_ref", "reliability", "ci_low", "ci_high", "caveats"],
      sel.map((r) => { const ci = d.cites[r.cite] || {}; return [code, r.geo, geoLabel(r.geo), r.period, r.breakdown, r.value, c.unit, r.basis, d.editions[r.edition]?.id, ci.table, ci.pdf_page, ci.printed_page, ci.sha256, r.l1_ref, r.reliability, r.ci_low, r.ci_high, r.caveats]; })));
  };
  $("#cite").onclick = () => copy(`${c.name} (${c.unit}), ${c.first}–${c.last}. ${c.publishers.map((p) => p.toUpperCase()).join(", ")}; via Malaysia Economy Data Warehouse (IKRAM), release ${D.meta.release_id}, indicator ${code}. ${location.href}`, "Citation copied");
  draw();
}

/* pick, for each series and period, the edition to draw: the period's own volume first, else the latest vintage */
function editionScore(ed, period) {
  const id = ed?.id || "";
  const own = period && id.includes(period.slice(0, 4)) && /pkkp:|anggaran|tinjauan|@\d{4}$/.test(id) ? 1 : 0;
  return [own, ed?.vintage || id];
}
function seriesOf(c, d, sel, st) {
  const pub = (r) => d.editions[r.edition]?.publisher || "";
  const pubs = new Set(sel.map(pub)), bases = new Set(sel.map((r) => r.basis));
  const key = (r) => [r.geo, bases.size > 1 ? r.basis : "", pubs.size > 1 ? pub(r) : ""].join("|");
  const groups = new Map();
  for (const r of sel) { const k = key(r); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(r); }
  const out = [];
  for (const [k, rs] of groups) {
    const byP = new Map();
    for (const r of rs) { if (!byP.has(r.period)) byP.set(r.period, []); byP.get(r.period).push(r); }
    const pts = [], alt = [];
    for (const [p, list] of byP) {
      list.sort((a, b) => { const A = editionScore(d.editions[a.edition], p), B = editionScore(d.editions[b.edition], p); return B[0] - A[0] || String(B[1]).localeCompare(String(A[1])); });
      const main = list[0];
      pts.push({ ...main, others: list.slice(1) });
      for (const o of list.slice(1)) if (o.value !== main.value) alt.push({ ...o, main });
    }
    pts.sort((a, b) => pdate(a.period) - pdate(b.period));
    const [geo, basis, pb] = k.split("|");
    out.push({ key: k, geo, basis, pub: pb, label: [geoLabel(geo), basis ? BASIS[basis] || basis : "", pb ? pb.toUpperCase() : ""].filter(Boolean).join(" · "), pts, alt });
  }
  return out;
}
/* split a series into runs: a new run where the step is far longer than the series' usual cadence, or at a break */
function runs(pts, breaks) {
  if (pts.length < 2) return [pts];
  const t = pts.map((p) => +pdate(p.period));
  const steps = t.slice(1).map((x, i) => x - t[i]).sort((a, b) => a - b);
  const med = steps[Math.floor(steps.length / 2)];
  const brk = breaks.map((b) => +pdate(b.first_period_new_basis));
  const out = [[pts[0]]];
  for (let i = 1; i < pts.length; i++) {
    const gap = t[i] - t[i - 1] > med * 1.6 + 864e5 * 20;
    const crosses = brk.some((b) => t[i - 1] < b && t[i] >= b);
    if (gap || crosses) out.push([]);
    out[out.length - 1].push(pts[i]);
  }
  return out;
}

function tipText(c, d, p) {
  const ci = d.cites[p.cite] || {}, ed = d.editions[p.edition] || {};
  const lines = [`${geoLabel(p.geo)} · ${p.period}`, p.orig != null ? `${exact(p.orig)} ${c.unit} (shown as ${NF(2).format(p.value)})` : `${exact(p.value)} ${c.unit}`, `${BASIS[p.basis] || p.basis} · ${edLabel(ed.id)}`,
    `${ci.table || ""}${ci.pdf_page ? " · pdf p" + ci.pdf_page : ""}${ci.printed_page ? " (printed " + ci.printed_page + ")" : ""}`];
  if (p.ci_low != null) lines.push(`95% interval ${exact(p.ci_low)} – ${exact(p.ci_high)}`);
  if (p.reliability && p.reliability !== "unknown") lines.push(`Reliability: ${p.reliability}`);
  if (p.others?.length) lines.push(`Also printed: ${p.others.map((o) => exact(o.value) + " (" + edLabel(d.editions[o.edition]?.id) + ")").join("; ")}`);
  if (p.main) lines.push(`Main line uses ${exact(p.main.value)} (${edLabel(d.editions[p.main.edition]?.id)})`);
  return lines.filter(Boolean).join("\n");
}

function chart(c, d, sel, st, breaks, nat = []) {
  const el = $("#chart");
  if (!window.Plot) { el.innerHTML = `<div class="note">The chart library did not load (offline?). The table below holds every value.</div>`; return; }
  const all = seriesOf(c, d, sel, st);
  const focus = all.filter((s) => st.geo.includes(s.geo));
  const context = st._ctx ? all.filter((s) => !st.geo.includes(s.geo)) : [];
  const series = focus.length ? focus : context.length ? [] : all.slice(0, 6);
  const colors = SER();
  series.forEach((s, i) => (s.color = colors[i % colors.length]));
  const natS = nat.length ? seriesOf(c, d, nat, st) : [];

  for (const s of [...series, ...context, ...natS]) { s.pts = transform(s.pts, st.show, c, breaks); s.alt = st.show === "value" ? s.alt : []; }
  const allPts = [...series, ...context, ...natS].flatMap((s) => s.pts);
  const head = $("#chartHead");
  if (!allPts.length) { el.innerHTML = `<div class="skel">No values for this selection. Try another breakdown or level.</div>`; $("#legend").innerHTML = ""; head.innerHTML = ""; $("#chartNotes").innerHTML = ""; return; }
  const vals = allPts.map((p) => p.value).filter((x) => typeof x === "number");
  const nonneg = vals.every((x) => x >= 0);
  const zero = st.show === "change" ? true : st.show === "index" ? false : nonneg && !["rate", "index", "ratio"].includes(c.statistic) && c.unit !== "index" || (c.unit === "percent" && c.statistic === "share");
  const yUnit = st.show === "change" ? (c.unit === "percent" ? "percentage points" : "% change") : st.show === "index" ? "index" : c.unit;
  const monthly = isMonthly(allPts[0].period);
  const single = new Set(allPts.map((p) => p.period)).size === 1;
  head.innerHTML = `<div><b>${esc(brkLabel(st.b))}</b> <span class="muted small">· ${esc(yUnit)}${st.show === "change" ? ", change since the previous published period" : st.show === "index" ? ", first period shown = 100" : ""}${st.lvl !== "country" ? " · " + LEVELS[st.lvl] : ""}</span></div><span class="muted small">${zero ? "Axis starts at zero" : "Axis fitted to the data (not from zero)"}</span>`;
  $("#legend").innerHTML = series.map((s) => `<span><i style="background:${s.color}"></i>${esc(s.label)}</span>`).join("") + (natS.length ? `<span><i style="background:var(--text);height:2px;border-top:1px dashed var(--text)"></i>Malaysia (reference)</span>` : "") + (context.length ? `<span><i style="background:var(--line-2)"></i>${context.length} other places (context)</span>` : "");

  const marks = [];
  const W = el.clientWidth || 900;
  if (single && st.show === "value") {
    // one period only: a dot plot of the places, alphabetical (never ranked)
    const pts = series.length ? series.flatMap((s) => s.pts.map((p) => ({ ...p, color: s.color }))) : context.flatMap((s) => s.pts);
    pts.sort((a, b) => geoLabel(a.geo).localeCompare(geoLabel(b.geo)));
    el.innerHTML = "";
    el.append(Plot.plot({ width: W, height: Math.max(160, 22 * pts.length + 40), marginLeft: 170, style: { background: "transparent", fontSize: "12px" },
      x: { grid: true, zero, label: c.unit, tickFormat: (x) => compact(x, c.unit) }, y: { label: null, domain: pts.map((p) => geoLabel(p.geo)) },
      marks: [Plot.ruleX(zero ? [0] : []), Plot.ruleY(pts, { x1: zero ? 0 : undefined, x2: "value", y: (p) => geoLabel(p.geo), stroke: "var(--line-2)" }),
        Plot.dot(pts, { x: "value", y: (p) => geoLabel(p.geo), r: 4.5, fill: (p) => p.color || colors[0], tip: true, title: (p) => tipText(c, d, p) })] }));
    $("#chartNotes").innerHTML = `Only ${esc(allPts[0].period)} is published for this selection, so places are shown side by side, in alphabetical order.`;
    return;
  }
  for (const s of context) for (const run of runs(s.pts, breaks)) marks.push(Plot.line(run, { x: (p) => pdate(p.period), y: "value", stroke: css("--line-2"), strokeWidth: 1, curve: "linear" }));
  for (const s of natS) for (const run of runs(s.pts, breaks)) marks.push(Plot.line(run, { x: (p) => pdate(p.period), y: "value", stroke: css("--text"), strokeWidth: 1.6, strokeDasharray: "5,3" }));
  series.forEach((s, i) => (s.w = series.length > 1 ? Math.max(1.3, 3 - i * 0.55) : 2));
  for (const s of series) {
    const ci = s.pts.filter((p) => p.ci_low != null && p.ci_high != null);
    if (ci.length) marks.push(Plot.areaY(ci, { x: (p) => pdate(p.period), y1: "ci_low", y2: "ci_high", fill: s.color, fillOpacity: 0.14 }));
    for (const run of runs(s.pts, breaks)) marks.push(Plot.line(run, { x: (p) => pdate(p.period), y: "value", stroke: s.color, strokeWidth: s.w, curve: "linear" }));
    const showDots = s.pts.length <= 80 || !monthly;
    if (showDots) marks.push(Plot.dot(s.pts, { x: (p) => pdate(p.period), y: "value", r: s.pts.length > 40 ? 1.8 : 3, fill: (p) => (p.reliability === "low" ? css("--panel") : s.color), stroke: s.color, strokeWidth: 1.4 }));
    if (s.alt.length) marks.push(Plot.dot(s.alt, { x: (p) => pdate(p.period), y: "value", r: 4, stroke: s.color, fill: "none", strokeDasharray: "2,1.5", tip: true, title: (p) => tipText(c, d, p) }));
  }
  for (const b of breaks) {
    const x = pdate(b.first_period_new_basis);
    marks.push(Plot.ruleX([x], { stroke: css("--warn"), strokeDasharray: "4,3" }));
    marks.push(Plot.text([x], { x: (z) => z, frameAnchor: "top", dy: -2, dx: 4, textAnchor: "start", text: () => "new basis", fill: css("--warn"), fontSize: 11 }));
  }
  if (zero) marks.push(Plot.ruleY([0], { stroke: css(st.show === "change" ? "--text-3" : "--line-2") }));
  if (st.show === "index") marks.push(Plot.ruleY([100], { stroke: css("--text-3"), strokeDasharray: "2,3" }));
  const tipPts = [...(series.length ? series : context), ...natS].flatMap((s) => s.pts);
  marks.push(Plot.tip(tipPts, Plot.pointer({ x: (p) => pdate(p.period), y: "value", title: (p) => tipText(c, d, p), fontSize: 12, fill: css("--panel"), stroke: css("--line-2") })));
  marks.push(Plot.dot(tipPts, Plot.pointer({ x: (p) => pdate(p.period), y: "value", r: 5, fill: "none", stroke: css("--text"), strokeWidth: 1.5 })));
  el.innerHTML = "";
  el.append(Plot.plot({
    width: W, height: Math.min(440, Math.max(300, W * 0.42)), marginLeft: 64, marginRight: 18, marginTop: 22,
    style: { background: "transparent", fontSize: "12px", color: css("--text-2") },
    x: { type: "utc", label: null, grid: false, ...(monthly ? {} : { tickFormat: (d) => String(d.getUTCFullYear()), ticks: d3.utcYear.every(Math.max(1, Math.ceil((d3.max(allPts, (p) => pdate(p.period)) - d3.min(allPts, (p) => pdate(p.period))) / (365.25 * 864e5) / (W < 640 ? 5 : 10)))) }) }, y: { grid: true, zero, label: unitShort(yUnit), tickFormat: (x) => (st.show === "value" ? compact(x, c.unit) : NF(1).format(x)) }, marks,
  }));
  const notes = [];
  const altN = series.reduce((a, s) => a + s.alt.length, 0);
  if (altN) notes.push(`<b>${altN}</b> value${altN > 1 ? "s" : ""} printed differently in another edition: shown as hollow dashed points; hover to see both.`);
  if (series.some((s) => s.pts.some((p) => p.reliability === "low"))) notes.push(`Hollow points: the publisher marks the estimate as of low reliability.`);
  if (series.length > 1 && new Set(series.map((s) => s.geo)).size === 1) notes.push(`Lines are drawn thinner in turn so that where sources agree they overlap visibly; hover to see each.`);
  if (series.some((s) => runs(s.pts, []).length > 1)) notes.push(`Breaks in a line are years with no published value, not zeros.`);
  if (breaks.length) notes.push(`Dashed orange rule: the series' method changed; values either side are not one series and should not be differenced.`);
  if (["district", "parlimen", "dun"].includes(st.lvl)) notes.push(`Below state level DOSM publishes no sampling error: a small difference between places may not be real (D10).`);
  else if (!sel.some((r) => r.ci_low != null) && (D.catIx[c.code]?.publishers || []).includes("dosm") && /survey|HIES|LFS/i.test(c.definition)) notes.push(`A survey estimate: DOSM publishes no confidence interval for it here, so no band is drawn.`);
  $("#chartNotes").innerHTML = notes.join(" ");
}

/* states as a tile map, banded against Malaysia, never ranked */
function tiles(c, d, rows, st) {
  const box = $("#tilesBox");
  const sel = rows.filter((r) => r.breakdown === st.b && (D.geoIx[r.geo]?.level === "state" || r.geo === "MY") && (!st.basis || r.basis === st.basis));
  const stRows = sel.filter((r) => r.geo !== "MY");
  if (stRows.length < 5) { box.innerHTML = ""; return; }
  const periods = [...new Set(stRows.map((r) => r.period))].sort((a, b) => pdate(a) - pdate(b));
  const P = new URLSearchParams(location.hash.split("?")[1] || "");
  let per = periods.includes(P.get("tp")) ? P.get("tp") : periods[periods.length - 1];
  const render = () => {
    const pick = (g) => { const xs = sel.filter((r) => r.geo === g && r.period === per); xs.sort((a, b) => String(d.editions[b.edition]?.vintage).localeCompare(String(d.editions[a.edition]?.vintage))); const r = xs[0]; if (r) r._also = xs.filter((x) => x.value !== r.value); return r; };
    const nat = pick("MY");
    const band = c.unit === "percent" ? 1 : null;
    const cls = (r) => {
      if (!r || !nat || typeof r.value !== "number") return "na";
      if (r.ci_low != null && nat.ci_low != null) return r.ci_low > nat.ci_high ? "hi" : r.ci_high < nat.ci_low ? "lo" : "eq";
      const diff = r.value - nat.value;
      const tol = band != null ? band : Math.abs(nat.value) * 0.05;
      return Math.abs(diff) <= tol ? "eq" : diff > 0 ? "hi" : "lo";
    };
    const fill = { hi: "color-mix(in srgb, var(--s1) 30%, var(--panel))", lo: "color-mix(in srgb, var(--s2) 28%, var(--panel))", eq: "var(--bg-2)", na: "transparent" };
    const counts = { hi: 0, lo: 0, eq: 0, na: 0 };
    const cells = STATES.map(([g, ab, x, y]) => {
      const r = pick(g), k = cls(r); counts[k]++;
      return `<a class="tile" href="#/state/${g}" title="${esc(geoName(g))}: ${r ? exact(r.value) + " " + esc(c.unit) + " (" + esc(d.editions[r.edition]?.id || "") + ")" + (r._also?.length ? "; also printed as " + r._also.map((x) => exact(x.value) + " (" + esc(d.editions[x.edition]?.id || "") + ")").join(", ") : "") : "not published"}" style="grid-column:${x + 1};grid-row:${y + 1};background:${fill[k]};${k === "na" ? "border-style:dashed;" : ""}color:var(--text)"><b>${ab}${r?._also?.length ? ' <span title="printed differently in another edition" style="color:var(--warn)">*</span>' : ""}</b><span>${r ? compact(r.value, c.unit) : "–"}</span></a>`;
    }).join("");
    box.innerHTML = `<h2>States in ${esc(per)}, against Malaysia</h2>
      <div class="card"><div class="row" style="justify-content:space-between;margin-bottom:10px">
        <div class="legend" style="margin:0"><span><i style="background:color-mix(in srgb, var(--s1) 50%, var(--panel));height:10px"></i>above Malaysia</span><span><i style="background:var(--line-2);height:10px"></i>about the same</span><span><i style="background:color-mix(in srgb, var(--s2) 50%, var(--panel));height:10px"></i>below Malaysia</span></div>
        ${periods.length > 1 ? `<div class="row"><button class="btn" id="tplay" type="button">▶ Play</button><select id="tp">${periods.map((p) => `<option ${p === per ? "selected" : ""}>${esc(p)}</option>`).join("")}</select></div>` : ""}</div>
        <div class="tiles" style="grid-template-columns:repeat(7,1fr);max-width:640px">${cells}</div>
        <p class="small muted" style="margin:10px 0 0">${nat ? `Malaysia: <b>${exact(nat.value)}</b> ${esc(c.unit)}. "About the same" is within ${band != null ? "1 percentage point" : "5%"} of Malaysia${stRows.some((r) => r.ci_low != null) ? ", or where the confidence intervals overlap" : ""}: a band, not a ranking. Higher is not always better: read the indicator.` : "Malaysia's own figure is not published for this period, so states are not banded."} ${counts.hi} above, ${counts.eq} about the same, ${counts.lo} below${counts.na ? `, ${counts.na} not published` : ""}. Click a state for its profile.</p></div>`;
    $("#tp") && ($("#tp").onchange = (e) => { per = e.target.value; render(); });
    const anyAlso = STATES.some(([g]) => pick(g)?._also?.length);
    if (anyAlso) box.querySelector("p").insertAdjacentHTML("beforeend", ` <span style="color:var(--warn)">*</span> printed differently in another edition: the tile shows the latest edition; hover for both.`);
    $("#tplay") && ($("#tplay").onclick = () => {
      if (tiles.timer) { clearInterval(tiles.timer); tiles.timer = null; return render(); }
      let i = 0; per = periods[0]; render(); $("#tplay").textContent = "❚❚ Pause";
      tiles.timer = setInterval(() => { i++; if (i >= periods.length || !document.body.contains(box)) { clearInterval(tiles.timer); tiles.timer = null; render(); return; } per = periods[i]; render(); $("#tplay").textContent = "❚❚ Pause"; }, 800);
    });
  };
  render();
}

function table(c, d, sel) {
  const rs = [...sel].sort((a, b) => geoLabel(a.geo).localeCompare(geoLabel(b.geo)) || pdate(b.period) - pdate(a.period));
  const lim = 400;
  $("#tCount").textContent = `${NF(0).format(rs.length)} rows${rs.length > lim ? `, first ${lim} shown (download for all)` : ""}`;
  $("#tbl").innerHTML = `<table><thead><tr><th>Place</th><th>Period</th><th class="n">Value (as printed)</th><th>Basis</th><th>Edition</th><th>Table · page</th><th>Source row (L1)</th><th>Caveats</th></tr></thead><tbody>
    ${rs.slice(0, lim).map((r) => { const ci = d.cites[r.cite] || {}; return `<tr><td>${esc(geoLabel(r.geo))}</td><td class="mono">${esc(r.period)}</td><td class="n">${exact(r.value)}${r.ci_low != null ? `<div class="small muted">${exact(r.ci_low)}–${exact(r.ci_high)}</div>` : ""}${r.reliability === "low" ? `<div>${chip("low reliability", "warn")}</div>` : ""}</td><td class="small">${esc(BASIS[r.basis] || r.basis)}</td><td class="small" title="${esc(d.editions[r.edition]?.id || "")}">${esc(edLabel(d.editions[r.edition]?.id))}</td><td class="small">${esc(ci.table || "")}${ci.pdf_page ? ` · p${esc(ci.pdf_page)}` : ""}${ci.printed_page ? ` <span class="muted">(${esc(ci.printed_page)})</span>` : ""}<div class="mono muted" title="file sha256">${esc((ci.sha256 || "").slice(0, 12))}</div></td><td class="small mono">${l1link(r.l1_ref)}</td><td>${(r.caveats || "").split(";").filter(Boolean).map((k) => `<span class="chip warn" title="${esc(D.caveats[k] || "")}">${esc(k)}</span>`).join(" ")}</td></tr>`; }).join("")}
  </tbody></table>`;
}
function l1link(ref) {
  if (!ref) return "";
  const m = /^(sources\/[^#]+?)(?:#row(\d+))?(?:\s|$)/.exec(ref);
  return m ? `<a href="${REPO}/blob/main/${esc(m[1])}${m[2] ? "#L" + (+m[2] + 1) : ""}" target="_blank" rel="noopener">${esc(ref)}</a>` : esc(ref);
}

/* =====================================================================================================
   BUBBLES: two indicators, every state, through time (a Gapminder-style moving chart)
   ===================================================================================================== */
const REGION = (g) => (["MY-12", "MY-13"].includes(g) ? "Sabah & Sarawak" : ["MY-14", "MY-15", "MY-16"].includes(g) ? "Federal Territories" : "Peninsular states");
const NOT_OUTCOME = new Set(["target", "budget_estimate", "revised_estimate", "allocation"]);
/* {year: {geo: row}} for an indicator's _total at state level (and Malaysia), the latest edition winning */
async function stateYears(code) {
  const d = await J(`ind/${code}.json`);
  const out = {};
  for (const r0 of d.rows) {
    const r = Object.fromEntries(COLS.map((k, i) => [k, r0[i]]));
    if (r.breakdown !== "_total" || NOT_OUTCOME.has(r.basis) || !/^\d{4}$/.test(r.period) || typeof r.value !== "number") continue;
    const lvl = D.geoIx[r.geo]?.level;
    if (lvl !== "state" && r.geo !== "MY") continue;
    const y = (out[r.period] ||= {});
    const ed = d.editions[r.edition] || {};
    const prev = y[r.geo];
    if (!prev || String(ed.vintage || ed.id) > String(prev.ed.vintage || prev.ed.id)) y[r.geo] = { ...r, ed, cite: d.cites[r.cite] || {} };
  }
  return out;
}
let bubbleTimer = null;
/* COMPARE: two measures, any kind of unit (states, ministries, development projects), through time.
   Each unit kind declares its measures and how to load one point per unit per year. */
const PROJ_OK = (r) => r.status !== "reserve" && r.maksud_code !== "P.70";
const UNITS = {
  state: {
    label: "States", noun: "states", one: "state", sizeLabel: "population",
    measures: () => D.cat.filter((c) => c.levels.includes("state") && /^\d{4}$/.test(c.first) && /^\d{4}$/.test(c.last)).sort((a, b) => a.name.localeCompare(b.name)).map((c) => ({ key: c.code, name: c.name, unit: c.unit, survey: /HIES|LFS|survey/i.test(c.definition) })),
    defaults: { x: "hh_income.gross.median", y: "poverty.absolute.rate", s: "pop.total" },
    sizes: [["pop.total", "Population"], ["", "Same size"]],
    groups: ["Peninsular states", "Sabah & Sarawak", "Federal Territories"],
    traceList: () => STATES.map(([g]) => [g, geoName(g)]).sort((a, b) => a[1].localeCompare(b[1])),
    async load(st) {
      const [X, Y, S] = await Promise.all([stateYears(st.x), stateYears(st.y), st.s ? stateYears(st.s) : Promise.resolve({})]);
      const sizeOf = (g, y) => { if (!st.s) return 1; for (let k = 0; k <= 3; k++) for (const yy of [String(+y - k), String(+y + k)]) if (S[yy]?.[g]) return S[yy][g].value; return null; };
      const years = Object.keys(X).filter((y) => Y[y]).sort();
      const pts = years.flatMap((y) => STATES.map(([g, ab]) => [g, ab]).filter(([g]) => X[y][g] && Y[y][g]).map(([g, ab]) => ({ id: g, y, x: X[y][g].value, yv: Y[y][g].value, s: sizeOf(g, y), name: geoName(g), ab, group: REGION(g), src: `${X[y][g].ed.id}\n${Y[y][g].ed.id}` })));
      const nat = years.map((y) => (X[y].MY && Y[y].MY ? { y, x: X[y].MY.value, yv: Y[y].MY.value } : null)).filter(Boolean);
      return { pts, nat, natLabel: "Malaysia" };
    },
  },
  ministry: {
    label: "Ministries", noun: "ministries and bodies", one: "ministry or body", sizeLabel: "allocation",
    measures: () => [
      { key: "estimate_revised_pkkp", name: "Allocation (accounts)", unit: "RM" }, { key: "actual_audited", name: "Spent (audited)", unit: "RM" },
      { key: "execution_rate", name: "Share of allocation spent", unit: "percent", pct: true }, { key: "unspent_rm", name: "Left unspent", unit: "RM" },
      { key: "estimate_original_pkkp", name: "Original estimate", unit: "RM" }],
    defaults: { x: "estimate_revised_pkkp", y: "execution_rate", s: "estimate_revised_pkkp", logx: "1", flow: "devex" },
    sizes: [["estimate_revised_pkkp", "Allocation"], ["", "Same size"]],
    groups: ["Within allocation", "Underspent", "Overspent"],
    filters: [["flow", "Money", [["devex", "Development"], ["opex", "Operating"]]]],
    async rows() { return objs(await J("gap/gap_budget_vs_actual.json")).filter((r) => r.breakdown_key === "_total" && r.entity_id !== "E000001" && r.actual_audited != null); },
    traceList: async (st) => [...new Map((await UNITS.ministry.rows()).filter((r) => r.flow === st.flow).map((r) => [r.entity_id, r.body])).entries()].sort((a, b) => a[1].localeCompare(b[1])),
    async load(st) {
      const rs = (await this.rows()).filter((r) => r.flow === (st.flow || "devex"));
      const val = (r, k) => (k === "execution_rate" ? (r[k] != null ? r[k] * 100 : null) : r[k]);
      const grp = (r) => ({ underspent: "Underspent", overspent: "Overspent" }[r.status] || "Within allocation");
      const pts = rs.map((r) => ({ id: r.entity_id, y: String(r.year), x: val(r, st.x), yv: val(r, st.y), s: st.s ? val(r, st.s) : 1, name: r.body, ab: "", group: grp(r), src: "PKKP (audited accounts), gap_budget_vs_actual" })).filter((p) => typeof p.x === "number" && typeof p.yv === "number");
      return { pts, nat: [], note: "Ministries and other bodies with a vote, as the audited accounts (PKKP) report them. Bodies change over time: a ministry that was split or renamed appears under each name in its own years." };
    },
  },
  project: {
    label: "Development projects", noun: "projects", one: "project", sizeLabel: "allocation",
    measures: () => [
      { key: "allocation_pkkp_rm", name: "Allocation (accounts)", unit: "RM" }, { key: "actual_pkkp_rm", name: "Spent (audited)", unit: "RM" },
      { key: "execution_rate", name: "Share of allocation spent", unit: "percent", pct: true }, { key: "unspent_rm", name: "Left unspent", unit: "RM" },
      { key: "tabled_rm", name: "Tabled in Parliament", unit: "RM" }, { key: "total_cost_book_rm", name: "Total project cost (budget book)", unit: "RM" }],
    defaults: { x: "allocation_pkkp_rm", y: "execution_rate", s: "allocation_pkkp_rm", logx: "1", vote: "" },
    sizes: [["allocation_pkkp_rm", "Allocation"], ["", "Same size"]],
    groups: ["Within allocation", "Underspent", "Overspent"],
    async rows() { return objs(await J("gap/gap_project_budget_vs_actual.json")).filter(PROJ_OK); },
    filterOpts: async () => { const rs = await UNITS.project.rows(); return [["vote", "Vote (ministry)", [["", "All votes"], ...[...new Set(rs.map((r) => r.maksud_code))].sort((a, b) => a.localeCompare(b, "en", { numeric: true })).map((m) => [m, `${m} · ${D.voteName?.[m] || ""}`])]]]; },
    traceList: async (st) => (await UNITS.project.rows()).filter((r) => !st.vote || r.maksud_code === st.vote).reduce((m, r) => (m.set(`${r.maksud_code}/${r.projek_code}`, `${r.maksud_code}/${r.projek_code} ${r.name_pkkp || r.name_book || ""}`.slice(0, 70)), m), new Map()),
    async load(st) {
      const rs = (await this.rows()).filter((r) => !st.vote || r.maksud_code === st.vote);
      const val = (r, k) => (k === "execution_rate" ? (r[k] != null ? r[k] * 100 : null) : r[k]);
      const grp = (r) => ({ underspent: "Underspent", overspent: "Overspent" }[r.status] || "Within allocation");
      const pts = rs.map((r) => ({ id: `${r.maksud_code}/${r.projek_code}`, y: String(r.year), x: val(r, st.x), yv: val(r, st.y), s: st.s ? val(r, st.s) : 1, name: `${r.maksud_code}/${r.projek_code} ${r.name_pkkp || r.name_book || ""}`, ab: "", group: grp(r), src: r.pkkp_ref || r.tabled_ref || "" })).filter((p) => typeof p.x === "number" && typeof p.yv === "number");
      return { pts, nat: [], note: "Development projects (B-vote projects) of FY2023–2025, joined on their vote and project codes. The contingency reserve (P.70) is left out. FY2025 has budget-book figures only, so measures from the audited accounts start in FY2023 and end in FY2024." };
    },
  },
};

async function viewBubbles(v) {
  crumbs([["Compare", "#/compare"]]);
  clearInterval(bubbleTimer); bubbleTimer = null;
  const [, P] = hashParams();
  const kind = UNITS[P.get("u")] ? P.get("u") : "state";
  const U = UNITS[kind];
  if (kind === "project" && !D.voteName) { D.voteName = {}; try { for (const [k, x] of Object.entries(await J("votes.json"))) D.voteName[k] = x.name; } catch {} }
  const ms = U.measures();
  const has = (k) => ms.some((x) => x.key === k);
  const st = { u: kind, ...U.defaults };
  for (const k of ["x", "y"]) if (has(P.get(k))) st[k] = P.get(k);
  if (P.has("s")) st.s = U.sizes.some(([k]) => k === P.get("s")) ? P.get("s") : st.s;
  if (P.has("logx")) st.logx = P.get("logx"); if (P.has("logy")) st.logy = P.get("logy");
  st.trace = (P.get("trace") || "").split(",").filter(Boolean); st.year = P.get("year") || "";
  const filters = U.filters || (U.filterOpts ? await U.filterOpts() : []);
  for (const [k, , opts] of filters) if (opts.some(([o]) => o === P.get(k))) st[k] = P.get(k);
  const sel = (id, list, cur) => `<select id="${id}" style="width:100%">${list.map(([k, l]) => `<option value="${esc(k)}" ${k === cur ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>`;
  v.innerHTML = `
    <div class="phead"><div><h1>Compare</h1><p class="lede">Two measures, one circle per ${esc(U.one)}, sized by ${esc(U.sizeLabel)}. Press play to watch the years go by; trace one to follow its path.</p></div>
      <div class="pactions"><button class="btn" id="cshare" type="button">Share</button></div></div>
    <div class="tabs" id="bu">${Object.entries(UNITS).map(([k, u]) => `<button type="button" data-v="${k}" class="${k === kind ? "on" : ""}">${u.label}</button>`).join("")}</div>
    <div class="toolbar" id="bc">
      <div style="flex:1;min-width:190px"><span class="tl-lab">Across (x)</span>${sel("bx", ms.map((x) => [x.key, x.name]), st.x)}</div>
      <div style="flex:1;min-width:190px"><span class="tl-lab">Up (y)</span>${sel("by", ms.map((x) => [x.key, x.name]), st.y)}</div>
      <div><span class="tl-lab">Size</span>${sel("bs", U.sizes, st.s)}</div>
      ${filters.map(([k, l, opts]) => `<div style="min-width:160px"><span class="tl-lab">${esc(l)}</span>${sel("bf_" + k, opts, st[k] || "")}</div>`).join("")}
      <div><span class="tl-lab">Scale</span><span class="row" style="gap:10px;height:30px"><label class="small"><input type="checkbox" id="blog" ${st.logx === "1" ? "checked" : ""}> log x</label><label class="small"><input type="checkbox" id="blogy" ${st.logy === "1" ? "checked" : ""}> log y</label></span></div>
      <div style="min-width:180px"><span class="tl-lab">Trace</span><select id="bt" style="width:100%"><option value="">+ add one</option></select></div>
      <button class="btn ghost" id="bswap" type="button" title="Swap the axes" style="align-self:flex-end">⇄ Swap</button>
    </div>
    <div class="split">
      <div class="main-col"><div class="card"><div class="row" style="justify-content:space-between"><div class="legend" id="blegend" style="margin:0"></div><div id="btchips" class="row" style="gap:5px"></div></div>
        <div class="chart" id="bchart" style="margin-top:6px"></div>
        <div class="player"><button class="btn primary" id="bplay" type="button">▶ Play</button><input type="range" id="byr" min="0" max="0" step="1"><b id="byl" class="mono"></b></div></div></div>
      <aside class="insp">
        <div class="insp-sec"><h4>What the chart shows</h4><div id="bstory" class="small"></div></div>
        <div class="insp-sec"><h4>Read it carefully</h4><p class="small" id="bnote" style="margin:0;color:var(--text-2)"></p></div>
        <div class="insp-sec"><h4>How to read it</h4><ul class="small tight"><li>Each circle is one ${esc(U.one)} in the year shown.</li><li>Up and to the right means more of both measures.</li><li>The axes never change while it plays, so movement is real.</li><li>Hover a circle for its exact figures and source.</li></ul></div>
      </aside>
    </div>`;
  $("#cshare").onclick = () => copy(location.href, "Link to this exact view copied");
  const go = () => { const p = new URLSearchParams({ u: st.u, x: st.x, y: st.y, s: st.s }); for (const k of ["logx", "logy"]) if (st[k] === "1") p.set(k, "1"); for (const [k] of filters) if (st[k]) p.set(k, st[k]); if (st.trace.length) p.set("trace", st.trace.join(",")); if (st.year) p.set("year", st.year); setParams("/compare", p); };
  const mx = (k) => ms.find((x) => x.key === k) || { name: k, unit: "" };
  async function fillTrace() { const list = await U.traceList(st); $("#bt").innerHTML = `<option value="">+ add one</option>` + [...list].map(([k, l]) => `<option value="${esc(k)}">${esc(l)}</option>`).join(""); }
  async function load() {
    clearInterval(bubbleTimer); bubbleTimer = null; $("#bplay").textContent = "▶ Play";
    $("#bchart").innerHTML = `<div class="skel">Loading…</div>`;
    const cx = mx(st.x), cy = mx(st.y);
    const data = await U.load(st);
    const logx = st.logx === "1", logy = st.logy === "1";
    let pts = data.pts, dropped = 0;
    if (logx || logy) { const keep = pts.filter((p) => (!logx || p.x > 0) && (!logy || p.yv > 0)); dropped = pts.length - keep.length; pts = keep; }
    const nat = data.nat.filter((p) => (!logx || p.x > 0) && (!logy || p.yv > 0));
    const counts = d3.rollup(pts, (a) => a.length, (p) => p.y);
    const years = [...counts.keys()].filter((y) => counts.get(y) >= 3).sort();
    if (!years.length) { $("#bchart").innerHTML = `<div class="skel">These two measures share no year with enough ${esc(U.noun)}. Pick another pair.</div>`; $("#bstory").innerHTML = ""; $(".player").style.display = "none"; $("#bnote").innerHTML = ""; return; }
    $(".player").style.display = years.length > 1 ? "" : "none";
    const ext = (a) => d3.extent(a);
    const xd = ext([...pts.map((p) => p.x), ...nat.map((p) => p.x)]), yd = ext([...pts.map((p) => p.yv), ...nat.map((p) => p.yv)]);
    const pad = (e, z, lg) => { if (lg) return [e[0] * 0.85, e[1] * 1.15]; const w = (e[1] - e[0]) || Math.abs(e[1]) || 1; return [z && e[0] >= 0 ? 0 : e[0] - w * 0.06, e[1] + w * 0.08]; };
    const zx = cx.unit === "percent" || /^RM/.test(cx.unit), zy = cy.unit === "percent" || /^RM/.test(cy.unit);
    // fit the axes to the bulk of the data (1st-99th percentile over all years), so a few extreme values do not flatten the rest
    const robust = (vals, lg) => { const q = vals.filter((x) => typeof x === "number" && (!lg || x > 0)).sort((a, b) => a - b); if (q.length < 20) return d3.extent(q);
      const lo = d3.quantileSorted(q, 0.01), hi = d3.quantileSorted(q, 0.99), mn = q[0], mx2 = q[q.length - 1], w = hi - lo || Math.abs(hi) || 1;
      // trim only genuine outliers: values far beyond the bulk, not the largest real cases
      const top = lg ? (mx2 > hi * 5 ? hi : mx2) : (mx2 - hi > 2 * w ? hi : mx2), bot = lg ? (mn < lo / 5 ? lo : mn) : (lo - mn > 2 * w ? lo : mn);
      return [bot, top]; };
    const xr = robust(pts.map((p) => p.x).concat(nat.map((p) => p.x)), logx), yr2 = robust(pts.map((p) => p.yv).concat(nat.map((p) => p.yv)), logy);
    const xDom = pad(xr[1] < xd[1] || xr[0] > xd[0] ? xr : xd, zx, logx), yDom = pad(yr2[1] < yd[1] || yr2[0] > yd[0] ? yr2 : yd, zy, logy);
    const outside = (p) => p.x < xDom[0] || p.x > xDom[1] || p.yv < yDom[0] || p.yv > yDom[1];
    const sMax = d3.max(pts, (p) => p.s) || 1;
    const rc = [css("--s1"), css("--s2"), css("--s3")];
    $("#blegend").innerHTML = U.groups.map((r, i) => `<span><i style="background:${rc[i]};height:10px;width:10px;border-radius:50%"></i>${r}</span>`).join("") + (nat.length ? `<span><i style="border:2px solid var(--text);height:10px;width:10px;border-radius:50%;background:none"></i>${esc(data.natLabel)}</span>` : "");
    const slider = $("#byr"); slider.max = years.length - 1;
    let yi = years.includes(st.year) ? years.indexOf(st.year) : years.length - 1;
    const many = d3.max([...counts.values()]) > 60;
    const fmt = (v, c) => (c.pct ? NF(1).format(v) + "%" : compact(v, c.unit));
    const draw = () => {
      const yr = years[yi]; st.year = yr; slider.value = yi; $("#byl").textContent = yr; go();
      const now = pts.filter((p) => p.y === yr), natNow = nat.find((p) => p.y === yr);
      const trails = pts.filter((p) => st.trace.includes(p.id) && p.y <= yr);
      const traced = now.filter((p) => st.trace.includes(p.id));
      const el = $("#bchart"); el.innerHTML = "";
      const W = el.clientWidth || 900;
      const off = now.filter(outside);
      el.append(Plot.plot({ width: W, height: Math.min(580, Math.max(380, W * 0.56)), marginLeft: 70, marginBottom: 44, clip: true, style: { background: "transparent", fontSize: "12px", color: css("--text-2") },
        x: { domain: xDom, type: logx ? "log" : "linear", label: `${cx.name} →`, grid: true, tickFormat: (x) => fmt(x, cx), ticks: logx ? 5 : undefined },
        y: { domain: yDom, type: logy ? "log" : "linear", label: `↑ ${cy.name}`, grid: true, tickFormat: (x) => fmt(x, cy), ticks: logy ? 5 : undefined },
        r: { domain: [0, sMax], range: [0, st.s ? (many ? 16 : 32) : (many ? 3.5 : 8)] },
        marks: [
          Plot.text([yr], { frameAnchor: "middle", text: (t) => t, fontSize: Math.min(170, W / 5), fill: css("--line"), fontWeight: 700 }),
          ...(cy.pct ? [Plot.ruleY([100], { stroke: css("--text-3"), strokeDasharray: "3,3" })] : []), ...(cx.pct ? [Plot.ruleX([100], { stroke: css("--text-3"), strokeDasharray: "3,3" })] : []),
          Plot.line(trails, { x: "x", y: "yv", z: "id", stroke: css("--text-3"), strokeWidth: 1.3, marker: "dot" }),
          Plot.dot(natNow ? [natNow] : [], { x: "x", y: "yv", r: 9, stroke: css("--text"), strokeWidth: 2.2, fill: "none" }),
          Plot.dot(now, { x: "x", y: "yv", r: (p) => (st.s ? p.s ?? sMax * 0.02 : 1), fill: (p) => rc[Math.max(0, U.groups.indexOf(p.group))], fillOpacity: many ? 0.55 : 0.72, stroke: css("--panel"), strokeWidth: many ? 0.5 : 1, sort: { channel: "r", order: "descending" } }),
          Plot.text(now.filter((p) => p.ab), { x: "x", y: "yv", text: "ab", fontSize: 10, fontWeight: 600, fill: css("--text") }),
          Plot.text(traced, { x: "x", y: "yv", text: (p) => p.name.slice(0, 40), dy: -14, fontSize: 11, fontWeight: 600, fill: css("--text") }),
          Plot.tip(now, Plot.pointer({ x: "x", y: "yv", title: (p) => `${p.name} · ${yr}\n${cx.name}: ${cx.pct ? NF(2).format(p.x) + "%" : exact(p.x) + " " + cx.unit}\n${cy.name}: ${cy.pct ? NF(2).format(p.yv) + "%" : exact(p.yv) + " " + cy.unit}${st.s && kind === "state" ? `\npopulation ${p.s != null ? exact(p.s) : "not published"}` : ""}\n${p.src}` })),
        ] }));
      const n = now.length;
      const xs = [...now].sort((a, b) => b.x - a.x), ys = [...now].sort((a, b) => b.yv - a.yv);
      const r = n > 2 ? pearson(now.map((p) => p.x), now.map((p) => p.yv)) : null;
      const byG = d3.rollup(now, (a) => a.length, (p) => p.group);
      $("#bstory").innerHTML = `<div class="muted" style="margin-bottom:4px">In ${yr}</div><div style="color:var(--text);line-height:1.55">${n} ${esc(U.noun)} have both figures.${natNow ? ` ${esc(data.natLabel)} as a whole: <b>${fmt(natNow.x, cx)}</b> and <b>${fmt(natNow.yv, cy)}</b>.` : ""} ${esc(cx.name)} runs from <b>${fmt(xs[n - 1].x, cx)}</b> to <b>${fmt(xs[0].x, cx)}</b>; ${esc(lc(cy.name))} from <b>${fmt(ys[n - 1].yv, cy)}</b> to <b>${fmt(ys[0].yv, cy)}</b>.${kind !== "state" ? ` ${U.groups.map((g) => `${byG.get(g) || 0} ${g.toLowerCase()}`).join(", ")}.` : ""}${r != null ? ` The two ${Math.abs(r) < 0.3 ? "barely move together" : r > 0 ? "tend to rise together" : "tend to move in opposite directions"} (correlation ${NF(2).format(r)}). A pattern, not a cause.` : ""}</div>`;
      const surveys = [cx, cy].filter((c) => c.survey);
      $("#bnote").innerHTML = [off.length ? `<b>${off.length}</b> extreme value${off.length > 1 ? "s are" : " is"} off the chart in ${yr} (${off.slice(0, 3).map((p) => esc(p.name.slice(0, 50))).join("; ")}${off.length > 3 ? "; …" : ""}); the axes are fitted to the bulk of the data, and the full rows are in the policy-gap tables.` : "", `Each year uses only figures published for that year; anything without a figure is left out, not guessed. Axes stay fixed across years, so movement is real.`,
        surveys.length ? `${surveys.map((c) => esc(c.name)).join(" and ")} ${surveys.length > 1 ? "are survey estimates" : "is a survey estimate"} without a published error margin: small gaps between states may not be real.` : "",
        dropped ? `${dropped} points with zero or negative values are hidden on a log scale.` : "", data.note || "", st.s && kind === "state" ? "Circle size: population in the same year (or the nearest year within 3)." : ""].filter(Boolean).join(" ");
    };
    slider.oninput = () => { yi = +slider.value; draw(); };
    $("#bplay").onclick = () => {
      if (bubbleTimer) { clearInterval(bubbleTimer); bubbleTimer = null; $("#bplay").textContent = "▶ Play"; return; }
      if (yi >= years.length - 1) yi = 0;
      $("#bplay").textContent = "❚❚ Pause"; draw();
      bubbleTimer = setInterval(() => { if (!document.body.contains(slider) || yi >= years.length - 1) { clearInterval(bubbleTimer); bubbleTimer = null; if ($("#bplay")) $("#bplay").textContent = "▶ Play"; return; } yi++; draw(); }, 900);
    };
    draw();
  }
  const chips = async () => {
    const list = new Map(await U.traceList(st));
    $("#btchips").innerHTML = st.trace.map((g) => `<span class="chip">${esc((list.get(g) || g).slice(0, 40))} <a href="#" data-rm="${esc(g)}" style="color:var(--text-3)">×</a></span>`).join("");
    $$("#btchips [data-rm]").forEach((a) => (a.onclick = (e) => { e.preventDefault(); st.trace = st.trace.filter((x) => x !== a.dataset.rm); chips(); load(); }));
  };
  $$("#bu button").forEach((b) => (b.onclick = () => { location.hash = "#/compare?u=" + b.dataset.v; }));
  $("#bx").onchange = (e) => { st.x = e.target.value; st.year = ""; load(); };
  $("#by").onchange = (e) => { st.y = e.target.value; st.year = ""; load(); };
  $("#bs").onchange = (e) => { st.s = e.target.value; load(); };
  $("#blog").onchange = (e) => { st.logx = e.target.checked ? "1" : ""; load(); };
  $("#blogy").onchange = (e) => { st.logy = e.target.checked ? "1" : ""; load(); };
  for (const [k] of filters) $("#bf_" + k).onchange = async (e) => { st[k] = e.target.value; st.trace = []; await fillTrace(); chips(); load(); };
  $("#bt").onchange = (e) => { if (e.target.value && !st.trace.includes(e.target.value)) st.trace.push(e.target.value); e.target.value = ""; chips(); load(); };
  $("#bswap").onclick = () => { [st.x, st.y] = [st.y, st.x]; [st.logx, st.logy] = [st.logy, st.logx]; $("#bx").value = st.x; $("#by").value = st.y; $("#blog").checked = st.logx === "1"; $("#blogy").checked = st.logy === "1"; load(); };
  await fillTrace(); chips(); await load();
}

function pearson(a, b) {
  const n = a.length, ma = d3.mean(a), mb = d3.mean(b);
  let num = 0, da = 0, db = 0;
  for (let i = 0; i < n; i++) { num += (a[i] - ma) * (b[i] - mb); da += (a[i] - ma) ** 2; db += (b[i] - mb) ** 2; }
  return da && db ? num / Math.sqrt(da * db) : null;
}

/* =====================================================================================================
   INDICATOR HELPERS: transforms, the one-sentence headline, every-state grid; tables that sort and filter
   ===================================================================================================== */
const segOf = (p, breaks) => breaks.filter((b) => pdate(p.period) >= pdate(b.first_period_new_basis)).length;
/* value | change since the previous published period | index (first period of the latest method = 100); never across a break */
function transform(pts, show, c, breaks) {
  if (show === "value") return pts;
  const num = pts.filter((p) => typeof p.value === "number");
  if (show === "change") {
    const out = [];
    for (let i = 1; i < num.length; i++) {
      const a = num[i - 1], b = num[i];
      if (segOf(a, breaks) !== segOf(b, breaks)) continue;
      const v = c.unit === "percent" ? b.value - a.value : a.value > 0 ? (b.value / a.value - 1) * 100 : null;
      if (v == null) continue;
      out.push({ ...b, orig: b.value, value: v, ci_low: null, ci_high: null, others: [] });
    }
    return out;
  }
  const last = Math.max(...num.map((p) => segOf(p, breaks)));
  const keep = num.filter((p) => segOf(p, breaks) === last);
  const base = keep[0]?.value;
  if (!base || base <= 0) return [];
  return keep.map((p) => ({ ...p, orig: p.value, value: (p.value / base) * 100, ci_low: p.ci_low != null ? (p.ci_low / base) * 100 : null, ci_high: p.ci_high != null ? (p.ci_high / base) * 100 : null, others: [] }));
}
const lc = (n) => (/^[A-Z]{2}/.test(n) ? n : n[0].toLowerCase() + n.slice(1));
function fmtU(v, unit) {
  if (/^RM/.test(unit) || unit === "percent") return compact(v, unit) + (/^RM per/.test(unit) ? unit.replace(/^RM/, "") : "");
  return compact(v, unit) + (unit ? " " + unit : "");
}
function headline(c, d, sel, st, breaks, nat) {
  const el = $("#headline");
  const geo = st.geo[0] || (st.lvl === "country" ? "MY" : null);
  let rows = geo ? sel.filter((r) => r.geo === geo) : nat;
  const place = geo ? geoLabel(geo) : "Malaysia";
  const bases = [...new Set(rows.map((r) => r.basis))];
  const basis = ["statistic", "audited", "actual"].find((b) => bases.includes(b)) || bases[0];
  rows = rows.filter((r) => r.basis === basis);
  if (!rows.length) { el.style.display = "none"; return; }
  el.style.display = "";
  const pts = seriesOf(c, d, rows, st)[0].pts.filter((p) => typeof p.value === "number");
  if (!pts.length) { el.style.display = "none"; return; }
  const last = pts[pts.length - 1], prev = pts[pts.length - 2];
  const what = `${lc(c.name)}${st.b !== "_total" ? ` (${brkLabel(st.b).toLowerCase()})` : ""}`;
  let t = `In <b>${esc(last.period)}</b>, ${esc(what)} in ${esc(place)} was <b>${fmtU(last.value, c.unit)}</b>${basis !== "statistic" ? ` (${esc((BASIS[basis] || basis).toLowerCase())})` : ""}`;
  if (prev) {
    const br = breaks.find((b) => pdate(prev.period) < pdate(b.first_period_new_basis) && pdate(last.period) >= pdate(b.first_period_new_basis));
    const dl = last.value - prev.value;
    if (br) t += `. The method changed in ${esc(br.first_period_new_basis)}, so it cannot be compared with ${esc(prev.period)} or earlier.`;
    else if (dl === 0) t += `, the same as in ${esc(prev.period)}.`;
    else if (c.unit === "percent") t += `: <b>${NF(1).format(Math.abs(dl))} percentage points ${dl > 0 ? "higher" : "lower"}</b> than in ${esc(prev.period)} (${fmtU(prev.value, c.unit)}).`;
    else if (prev.value > 0) t += `: <b>${NF(1).format(Math.abs((dl / prev.value) * 100))}% ${dl > 0 ? "higher" : "lower"}</b> than in ${esc(prev.period)} (${fmtU(prev.value, c.unit)}).`;
    else t += `, against ${fmtU(prev.value, c.unit)} in ${esc(prev.period)}.`;
    const seg = pts.filter((p) => segOf(p, breaks) === segOf(last, breaks));
    if (seg.length > 3 && seg[0] !== prev) t += ` In ${esc(seg[0].period)} it was ${fmtU(seg[0].value, c.unit)}.`;
  } else t += ".";
  if (["district", "parlimen", "dun"].includes(st.lvl)) t += ` <span class="muted">A small-area estimate with no published error margin: read it as approximate.</span>`;
  el.innerHTML = `<div class="small muted" style="margin-bottom:4px">In one sentence</div><div class="finding">${t}</div>`;
}
function gridChart(c, d, sel, st, breaks, nat) {
  const el = $("#chart");
  const all = seriesOf(c, d, sel, st).filter((s) => D.geoIx[s.geo]?.level === "state");
  const natS = nat.length ? seriesOf(c, d, nat, st) : [];
  [...all, ...natS].forEach((s) => (s.pts = transform(s.pts, st.show, c, breaks)));
  const geos = [...new Set(all.map((s) => s.geo))].sort((a, b) => geoName(a).localeCompare(geoName(b)));
  if (!geos.length) { el.innerHTML = `<div class="skel">No state values for this selection.</div>`; return; }
  const W = el.clientWidth || 900, cols = W < 640 ? 2 : 4, nrow = Math.ceil(geos.length / cols);
  const pos = Object.fromEntries(geos.map((g, i) => [g, { fx: i % cols, fy: Math.floor(i / cols) }]));
  const lines = [], natLines = [];
  all.forEach((s) => runs(s.pts, breaks).forEach((run, k) => run.forEach((p) => lines.push({ ...p, z: s.key + "#" + k, ...pos[s.geo] }))));
  natS.forEach((s) => runs(s.pts, breaks).forEach((run, k) => geos.forEach((g) => run.forEach((p) => natLines.push({ ...p, z: "MY" + g + k, ...pos[g] })))));
  const vals = [...lines, ...natLines].map((p) => p.value);
  const zero = st.show === "change" || (st.show === "value" && vals.every((x) => x >= 0) && !["rate", "index", "ratio"].includes(c.statistic));
  const x = (p) => pdate(p.period);
  el.innerHTML = "";
  el.append(Plot.plot({ width: W, height: nrow * 150 + 30, marginLeft: 52, marginTop: 8, style: { background: "transparent", fontSize: "11px", color: css("--text-2") },
    fx: { axis: null, padding: 0.1 }, fy: { axis: null, padding: 0.16 },
    x: { type: "utc", ticks: 3, label: null }, y: { grid: true, zero, ticks: 3, label: null, tickFormat: (v) => (st.show === "value" ? compact(v, c.unit) : NF(0).format(v)) },
    marks: [Plot.frame({ stroke: css("--line") }),
      ...breaks.map((b) => Plot.ruleX([pdate(b.first_period_new_basis)], { stroke: css("--warn"), strokeDasharray: "3,3" })),
      Plot.line(natLines, { x, y: "value", z: "z", fx: "fx", fy: "fy", stroke: css("--text-3"), strokeDasharray: "4,3", strokeWidth: 1 }),
      Plot.line(lines, { x, y: "value", z: "z", fx: "fx", fy: "fy", stroke: css("--s1"), strokeWidth: 1.8 }),
      Plot.dot(lines, { x, y: "value", fx: "fx", fy: "fy", fill: css("--s1"), r: 1.5 }),
      Plot.text(geos.map((g) => ({ g, ...pos[g] })), { fx: "fx", fy: "fy", text: (o) => geoName(o.g), frameAnchor: "top-left", dx: 6, dy: 6, fontWeight: 600, fill: css("--text"), fontSize: 11 }),
      Plot.tip(lines, Plot.pointer({ x, y: "value", fx: "fx", fy: "fy", title: (p) => tipText(c, d, p) }))] }));
  $("#legend").innerHTML = `<span><i style="background:var(--s1)"></i>the state</span>${natS.length ? `<span><i style="background:var(--text-3)"></i>Malaysia (dashed)</span>` : ""}`;
  $("#chartHead").innerHTML = `<div><b>Every state, one scale</b> <span class="muted small">· ${esc(st.show === "value" ? c.unit : st.show === "change" ? (c.unit === "percent" ? "percentage points" : "% change") : "index")} · alphabetical, not ranked</span></div><span class="muted small">Same axis in every panel, so heights compare directly</span>`;
  $("#chartNotes").innerHTML = `Small multiples: each panel is one state against Malaysia. Breaks in a line are years with no published value.`;
}
function filterTable(box, q) {
  const w = q.toLowerCase().split(/\s+/).filter(Boolean);
  let n = 0;
  box.querySelectorAll("tbody tr").forEach((tr) => { const ok = !w.length || w.every((x) => tr.innerText.toLowerCase().includes(x)); tr.style.display = ok ? "" : "none"; n += ok; });
  return n;
}
function initSort() {
  document.addEventListener("click", (e) => {
    const th = e.target.closest(".tablewrap thead th");
    if (!th) return;
    const table = th.closest("table"), tb = table.tBodies[0];
    if (!tb) return;
    const i = [...th.parentNode.children].indexOf(th);
    const dir = th.dataset.dir === "asc" ? "desc" : "asc";
    [...th.parentNode.children].forEach((x) => delete x.dataset.dir);
    th.dataset.dir = dir;
    const key = (tr) => {
      const t = (tr.cells[i]?.innerText || "").trim().split("\n")[0];
      const n = parseFloat(t.replace(/−/g, "-").replace(/RM|,|%|\s/g, ""));
      return /\d/.test(t) && !isNaN(n) && /^[-−RM\d.,%\s]+$/.test(t) ? n : t.toLowerCase();
    };
    const rows = [...tb.rows];
    rows.sort((a, b) => { const A = key(a), B = key(b); const c = typeof A === typeof B ? (A < B ? -1 : A > B ? 1 : 0) : typeof A === "number" ? -1 : 1; return dir === "asc" ? c : -c; });
    rows.forEach((r) => tb.appendChild(r));
  });
}

/* the live headline number on each policy-gap card */
const maxYear = (rs) => Math.max(...rs.map((r) => +r.year).filter((x) => !isNaN(x)));
const HEAD = {
  gap_budget_vs_actual(a) {
    const y = maxYear(a.filter((r) => r.actual_audited != null && r.flow === "devex"));
    const h = a.filter((r) => +r.year === y && r.flow === "devex" && r.breakdown_key === "_total" && r.entity_id !== "E000001" && r.actual_audited != null && r.estimate_revised_pkkp);
    return [pct(d3.sum(h, (r) => r.actual_audited) / d3.sum(h, (r) => r.estimate_revised_pkkp)), `of development allocations spent in ${y}; ${h.filter((r) => r.status === "underspent").length} bodies underspent`];
  },
  gap_project_budget_vs_actual(a) {
    const y = maxYear(a.filter((r) => r.actual_pkkp_rm != null));
    return [a.filter((r) => +r.year === y && r.status !== "reserve" && r.maksud_code !== "P.70" && r.allocation_pkkp_rm > 0 && r.actual_pkkp_rm === 0).length, `development projects in ${y} had an allocation and spent nothing`];
  },
  gap_revenue_estimate_vs_collected(a) {
    const h = a.filter((r) => r.breakdown_key === "_total" && r.actual_audited != null && r.estimate_original);
    return [`${h.filter((r) => r.collection_rate_original < 1).length} of ${h.length}`, "years federal revenue came in below the original estimate"];
  },
  gap_reported_vs_audited(a) {
    const h = a.filter((r) => r.bnm_vs_pkkp_status && r.bnm_vs_pkkp_status !== "not_held");
    return [`${h.filter((r) => r.bnm_vs_pkkp_status === "agree").length} of ${h.length}`, "times Bank Negara's figure matches the audited accounts"];
  },
  gap_obligations_growth(a) {
    const y = maxYear(a);
    const h = a.filter((r) => +r.year === y && r.instrument !== "debt");
    return [`${h.filter((r) => r.status === "grew_faster_than_debt").length} of ${h.length}`, `obligations outside debt grew faster than debt in ${y}`];
  },
  gap_target_vs_outcome: (a) => [`${a.filter((r) => /^below/.test(r.status)).length} of ${a.length}`, "Twelfth Plan targets ended below the number set"],
  gap_need_vs_money(a) {
    const y = maxYear(a.filter((r) => r.state_gov_expenditure_per_capita_rm != null && r.poverty_absolute_rate != null));
    const h = a.filter((r) => +r.year === y && r.state_gov_expenditure_per_capita_rm != null && r.poverty_absolute_rate != null);
    const rr = pearson(h.map((r) => r.poverty_absolute_rate), h.map((r) => r.state_gov_expenditure_per_capita_rm));
    return [rr == null ? "–" : NF(2).format(rr), `correlation between poverty and state spending per person, ${h.length} states, ${y}`];
  },
  gap_federal_vs_state(a) {
    const h = a.filter((r) => r.geo_code !== "_states" && r.federal_paid_rm != null && r.state_recorded_rm != null);
    return [`${h.filter((r) => r.status === "differ").length} of ${h.length}`, "state-years where the federal and state figures differ"];
  },
  gap_federal_placement(a) {
    const h = a.filter((r) => r.geo_code === "MY" && r.placed_share != null).sort((x, y) => x.year - y.year);
    const l = h[h.length - 1] || {};
    return [pct(l.placed_share), `of federal spending in ${l.year} can be placed in a state`];
  },
};

/* =====================================================================================================
   STATES
   ===================================================================================================== */
function viewStates(v) {
  crumbs([["States", "#/states"]]);
  v.innerHTML = `<h1>States and Federal Territories</h1><p class="lede">Every view runs for all 13 states and the three Federal Territories. Pick one for its profile.</p>
    <div class="tiles" style="grid-template-columns:repeat(7,1fr);max-width:720px;margin:20px 0">${STATES.map(([g, ab, x, y]) => `<a class="tile" href="#/state/${g}" style="grid-column:${x + 1};grid-row:${y + 1};background:var(--panel);color:var(--text)"><b>${ab}</b><span style="font-weight:500;font-size:11px">${esc(geoName(g))}</span></a>`).join("")}</div>
    <div class="grid g4">${STATES.map(([g]) => g).sort((a, b) => geoName(a).localeCompare(geoName(b))).map((g) => `<a class="card link" href="#/state/${g}"><b>${esc(geoName(g))}</b><div class="small muted mono">${g}</div></a>`).join("")}</div>`;
}

const PROFILE = [
  ["pop.total", "Population"], ["poverty.absolute.rate", "Absolute poverty"], ["hh_income.gross.median", "Median household income"],
  ["hh_income.gini", "Gini coefficient"], ["lfs.unemployment_rate", "Unemployment rate"], ["lfs.participation_rate", "Labour force participation"],
  ["wages.median", "Median monthly wage"], ["gdp.real", "GDP, constant prices"], ["amenities.piped_water.share", "Households with piped water"],
  ["life_expectancy", "Life expectancy"], ["state_gov.revenue.total", "State government revenue"], ["state_gov.expenditure.total", "State government spending"],
  ["state_gov.debt.total", "State government debt"], ["state_gov.revenue.federal_grants_total", "Federal grants to the state"],
];
async function viewState(g, v = $("#view")) {
  if (!D.geoIx[g]) { v.innerHTML = `<div class="note">No such state. <a href="#/states">All states</a></div>`; return; }
  crumbs([["States", "#/states"], [geoName(g), ""]]);
  const ft = ["MY-14", "MY-15", "MY-16"].includes(g);
  v.innerHTML = `<div class="row">${chip(g, "accent")}${ft ? chip("Federal Territory") : chip("State")}</div><h1>${esc(geoName(g))}</h1>
    <p class="lede">The latest figure published for ${esc(geoName(g))} beside Malaysia's for the same year. Click a card for the full series. ${ft ? "A Federal Territory has no state government, so it has no state accounts." : ""}</p>
    <div class="grid g3" id="prof" style="margin-top:16px">${PROFILE.map(() => `<div class="card skel" style="padding:24px">…</div>`).join("")}</div>
    <h2>Everything published for ${esc(geoName(g))}</h2><div class="card" style="padding:0"><div class="list" id="all"></div></div>`;
  const list = D.cat.filter((c) => c.levels.includes("state"));
  $("#all").innerHTML = list.map((c) => `<a class="item" href="#/explore/${encodeURIComponent(c.code)}?lvl=state&geo=${g}"><b>${esc(c.name)}</b><span class="muted small mono">${esc(c.first)}–${esc(c.last)}</span><div class="meta">${esc(themeName(c.theme))} · ${esc(c.unit)}</div></a>`).join("");
  const cards = await Promise.all(PROFILE.filter(([k]) => D.catIx[k]).map(async ([k, label]) => {
    const c = D.catIx[k];
    const d = await J(`ind/${k}.json`);
    const rs = d.rows.map((r) => Object.fromEntries(COLS.map((x, i) => [x, r[i]]))).filter((r) => r.breakdown === "_total" && r.basis !== "target" && r.basis !== "budget_estimate");
    const mine = rs.filter((r) => r.geo === g).sort((a, b) => pdate(b.period) - pdate(a.period) || String(d.editions[b.edition]?.vintage).localeCompare(String(d.editions[a.edition]?.vintage)));
    if (!mine.length) return `<div class="card"><div class="small muted">${esc(label)}</div><div class="muted" style="margin-top:6px">Not published for ${esc(geoName(g))}</div></div>`;
    const last = mine[0];
    const nat = rs.filter((r) => r.geo === "MY" && r.period === last.period)[0];
    const ser = mine.filter((r, i, a) => a.findIndex((x) => x.period === r.period) === i).reverse();
    return `<a class="card link" href="#/explore/${encodeURIComponent(k)}?lvl=state&geo=${g}">
      <div class="small muted">${esc(label)} · ${esc(last.period)}</div>
      <div class="kpi"><div class="v" style="font-size:22px">${compact(last.value, c.unit)}</div></div>
      <div class="small muted">${nat ? `Malaysia ${compact(nat.value, c.unit)}` : "Malaysia: not published for this year"}${c.unit && !/^RM/.test(c.unit) && c.unit !== "percent" ? " · " + esc(c.unit) : ""}</div>
      ${spark(ser)}</a>`;
  }));
  $("#prof").innerHTML = cards.join("");
}
function spark(ser) {
  if (ser.length < 2) return "";
  const xs = ser.map((r) => +pdate(r.period)), ys = ser.map((r) => r.value);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const X = (x) => 2 + ((x - x0) / (x1 - x0 || 1)) * 196, Y = (y) => 30 - ((y - y0) / (y1 - y0 || 1)) * 26;
  const pts = ser.map((r, i) => `${X(xs[i]).toFixed(1)},${Y(ys[i]).toFixed(1)}`).join(" ");
  return `<svg viewBox="0 0 200 34" style="width:100%;height:34px;margin-top:8px" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="var(--accent)" stroke-width="1.6"/>${ser.map((r, i) => `<circle cx="${X(xs[i]).toFixed(1)}" cy="${Y(ys[i]).toFixed(1)}" r="1.6" fill="var(--accent)"/>`).join("")}</svg><div class="row small muted" style="justify-content:space-between"><span>${esc(ser[0].period)}</span><span>${esc(ser[ser.length - 1].period)}</span></div>`;
}

/* =====================================================================================================
   POLICY GAPS
   ===================================================================================================== */
const QUESTIONS = [
  ["Was the money budgeted actually spent?", "gap_budget_vs_actual", "budget spent spending underspent overspent ministry execution allocation belanja"],
  ["Which development projects got money but spent little or none?", "gap_project_budget_vs_actual", "project projek development devex unspent zero spend tabled"],
  ["Did the Twelfth Malaysia Plan hit its 2025 targets?", "gap_target_vs_outcome", "plan rmk target outcome twelfth 12mp goal"],
  ["Does money follow need across the states?", "gap_need_vs_money", "need poverty poor income state per capita fair money follow"],
  ["Was revenue collected as estimated?", "gap_revenue_estimate_vs_collected", "revenue tax hasil collected estimate collection"],
  ["Do MOF, Bank Negara and the audited accounts print the same figures?", "gap_reported_vs_audited", "audit audited reported mof bnm agree differ accounts deficit"],
  ["Are guarantees and PFI growing faster than debt?", "gap_obligations_growth", "debt guarantee pfi commitments hidden liabilities obligations risk"],
  ["Does what the federal government paid each state match what the state recorded?", "gap_federal_vs_state", "federal state grant capitation transfer loans paid received"],
  ["How much federal spending can be placed in a state at all?", "gap_federal_placement", "federal where place location state map placed"],
];
function viewGaps(v) {
  crumbs([["Policy gaps", "#/gaps"]]);
  v.innerHTML = `<h1>Policy gaps</h1>
    <p class="lede">Ask a question. Get the answer, the evidence and the caveats. Each view sets two things side by side that should line up: a plan and its outcome, a budget and its spending, need and money, a report and its audit.</p>
    <div class="card" style="margin:18px 0;padding:14px"><input type="search" id="gq" placeholder="Ask, e.g. “was the education budget spent?”, “poverty in Kelantan”, “PFI”" style="width:100%;font-size:15px;padding:10px 12px"><div id="gans" style="margin-top:10px"></div></div>
    <div class="grid g3" id="gcards">${QUESTIONS.map(([q, name]) => { const g = D.gaps.find((x) => x.name === name); return g ? `<a class="card link qcard" href="#/gaps/${name}"><div class="small muted">${esc(g.title)}</div><h3 style="margin:4px 0 10px;font-size:15px">${esc(q)}</h3><div class="gh" data-n="${name}"><span class="muted small">…</span></div><div class="small" style="margin-top:10px">Open the analysis →</div></a>` : ""; }).join("")}</div>
    <div class="note info" style="margin-top:18px">Every view follows a method declared before its results were seen, runs for all states and Federal Territories, and keeps the sources' own figures. The plain-language reading at the top of each view is generated by fixed rules from the rows below it, not written by hand.</div>`;
  $$(".gh").forEach((el) => J(`gap/${el.dataset.n}.json`).then(objs).then((a) => { const [big, txt] = HEAD[el.dataset.n](a); el.innerHTML = `<div class="ghb">${big}</div><div class="small muted">${esc(txt)}</div>`; }).catch(() => (el.innerHTML = "")));
  $("#gq").oninput = (e) => {
    const q = e.target.value.toLowerCase().trim();
    if (!q) { $("#gans").innerHTML = ""; return; }
    const words = q.split(/\W+/).filter((w) => w.length > 2);
    const gs = QUESTIONS.map(([t, n, kw]) => [words.filter((w) => kw.includes(w) || t.toLowerCase().includes(w)).length, t, n]).filter((x) => x[0]).sort((a, b) => b[0] - a[0]).slice(0, 3);
    const st = STATES.map(([g]) => g).filter((g) => words.some((w) => geoName(g).toLowerCase().includes(w)));
    const inds = D.cat.map((c) => [words.filter((w) => (c.name + " " + c.definition).toLowerCase().includes(w)).length, c]).filter((x) => x[0]).sort((a, b) => b[0] - a[0]).slice(0, 5);
    $("#gans").innerHTML = (gs.length ? `<div class="small muted">Gap views</div>${gs.map(([, t, n]) => `<div><a href="#/gaps/${n}">${esc(t)}</a></div>`).join("")}` : "")
      + (st.length ? `<div class="small muted" style="margin-top:8px">States</div>${st.map((g) => `<div><a href="#/state/${g}">${esc(geoName(g))} profile</a></div>`).join("")}` : "")
      + (inds.length ? `<div class="small muted" style="margin-top:8px">Indicators</div>${inds.map(([, c]) => `<div><a href="#/explore/${encodeURIComponent(c.code)}${st.length ? "?lvl=state&geo=" + st.join(",") : ""}">${esc(c.name)}</a> <span class="muted small">${esc(c.first)}–${esc(c.last)}</span></div>`).join("")}` : "")
      + (inds.length > 1 ? `<div class="small muted" style="margin-top:8px">Compare two of them across states</div><div><a href="#/compare?x=${encodeURIComponent(inds[0][1].code)}&y=${encodeURIComponent(inds[1][1].code)}">${esc(inds[0][1].name)} against ${esc(inds[1][1].name)}, state by state</a></div>` : "")
      || `<span class="muted small">No match yet. Try words like budget, poverty, plan, debt, revenue, or a state's name.</span>`;
  };
}

/* the gap views: each declares its filters, its reading, its chart and its table */
const G = {};
const col = (d, k) => d.cols.indexOf(k);
const objs = (d) => d.rows.map((r) => Object.fromEntries(d.cols.map((k, i) => [k, r[i]])));
const sum = (a) => a.reduce((s, x) => s + (typeof x === "number" ? x : 0), 0);
const years = (rs) => [...new Set(rs.map((r) => r.year))].sort();
const mstate = (rs) => rs.filter((r) => r.geo_code && r.geo_code !== "MY");

G.gap_budget_vs_actual = {
  filters: (rs) => ({ year: years(rs.filter((r) => r.actual_audited != null)), flow: ["opex", "devex"] }),
  flowLabel: { opex: "Operating", devex: "Development" },
  rows: (rs, f) => rs.filter((r) => r.year === f.year && r.flow === f.flow && r.breakdown_key === "_total" && r.entity_id !== "E000001"),
  read(rs, f) {
    const held = rs.filter((r) => r.actual_audited != null && r.estimate_revised_pkkp);
    const est = sum(held.map((r) => r.estimate_revised_pkkp)), act = sum(held.map((r) => r.actual_audited));
    const under = held.filter((r) => r.status === "underspent"), over = held.filter((r) => r.status === "overspent");
    const big = held.filter((r) => r.unspent_rm > 0).sort((a, b) => b.unspent_rm - a.unspent_rm).slice(0, 3);
    return `In <b>${f.year}</b>, ${held.length} ministries and bodies had ${f.flow === "opex" ? "an" : "a"} ${this.flowLabel[f.flow].toLowerCase()} allocation and an audited actual. Together they spent <b>${compact(act, "RM")}</b> of <b>${compact(est, "RM")}</b> allocated (<b>${pct(act / est)}</b>). <b>${under.length}</b> spent less than their allocation by the view's threshold and <b>${over.length}</b> spent more.${big.length ? ` The largest amounts left unspent, whatever the share: ${big.map((r) => `${esc(r.body)} (${compact(r.unspent_rm, "RM")}, ${pct(r.execution_rate)} spent)`).join("; ")}.` : ""}${f.flow === "opex" ? " Charged expenditure (debt service, pensions) is not a ministry vote and is left out." : ""}`;
  },
  chart(rs) {
    const h = rs.filter((r) => r.execution_rate != null).sort((a, b) => a.execution_rate - b.execution_rate);
    if (!h.length) return null;
    return Plot.plot({ height: Math.max(240, h.length * 17 + 40), marginLeft: 230, x: { label: "Share of allocation spent (audited)", tickFormat: (x) => pct(x, 0), grid: true },
      y: { label: null, domain: h.map((r) => r.body), tickFormat: (d) => (d.length > 36 ? d.slice(0, 35) + "…" : d) },
      marks: [Plot.ruleX([1], { stroke: css("--text-3"), strokeDasharray: "3,3" }), Plot.barX(h, { x: "execution_rate", y: "body", fill: (r) => (r.status === "underspent" ? css("--s2") : r.status === "overspent" ? css("--s3") : css("--s1")), title: (r) => `${r.body}\nallocation ${exact(r.estimate_revised_pkkp)}\naudited actual ${exact(r.actual_audited)}\n${pct(r.execution_rate)} spent · ${statusText(r.status)}` }), Plot.tip(h, Plot.pointerY({ x: "execution_rate", y: "body", title: (r) => `${r.body}\nallocation RM ${exact(r.estimate_revised_pkkp)}\naudited actual RM ${exact(r.actual_audited)}\n${pct(r.execution_rate)} spent · ${statusText(r.status)}` }))] });
  },
  legend: [["--s1", "within the allocation"], ["--s2", "underspent"], ["--s3", "overspent"]],
  drill: {
    title: "Follow one body across the years", hint: "Or click a row in the table below",
    keys: (all, f) => [...new Set(all.filter((r) => r.flow === f.flow && r.breakdown_key === "_total" && r.actual_audited != null && r.entity_id !== "E000001").map((r) => r.body))].sort(),
    pick: (all, f, keys) => { const y = all.filter((r) => r.year === f.year && r.flow === f.flow && r.breakdown_key === "_total" && r.unspent_rm > 0).sort((a, b) => b.unspent_rm - a.unspent_rm)[0]; return y && keys.includes(y.body) ? y.body : keys[0]; },
    fromRow: (tr) => tr.cells[0]?.innerText.trim(),
    render(all, f, body) {
      const h = all.filter((r) => r.body === body && r.flow === f.flow && r.breakdown_key === "_total").sort((a, b) => a.year - b.year);
      const long = h.flatMap((r) => [["Allocation (accounts)", r.estimate_revised_pkkp], ["Audited spending", r.actual_audited]].filter((x) => x[1] != null).map(([k, v]) => ({ k, y: +r.year, v, r })));
      const ex = h.filter((r) => r.execution_rate != null);
      const low = ex.filter((r) => r.status === "underspent").map((r) => r.year);
      const chart = Plot.plot({ height: 300, marginLeft: 70, x: { label: null, tickFormat: "d" }, y: { grid: true, zero: true, label: "RM", tickFormat: (x) => compact(x, "RM") },
        color: { domain: ["Allocation (accounts)", "Audited spending"], range: [css("--s6"), css("--s1")] },
        marks: [Plot.barY(long.filter((p) => p.k === "Allocation (accounts)"), { x: "y", y: "v", fill: css("--line-2"), inset: 4 }), Plot.line(long.filter((p) => p.k === "Audited spending"), { x: "y", y: "v", stroke: css("--s1"), strokeWidth: 2.4 }),
          Plot.dot(long.filter((p) => p.k === "Audited spending"), { x: "y", y: "v", fill: (p) => (p.r.status === "underspent" ? css("--s2") : p.r.status === "overspent" ? css("--s3") : css("--s1")), r: 4 }),
          Plot.tip(long, Plot.pointer({ x: "y", y: "v", title: (p) => `${body} · ${p.y}\n${p.k}: RM ${exact(p.v)}\n${p.r.execution_rate != null ? pct(p.r.execution_rate) + " spent · " + statusText(p.r.status) : ""}` }))] });
      const tot = d3.sum(ex, (r) => r.estimate_revised_pkkp), act = d3.sum(ex, (r) => r.actual_audited);
      return { chart, legend: `<span><i style="background:var(--line-2);height:10px"></i>allocation in the accounts (bars)</span><span><i style="background:var(--s1)"></i>audited spending (line; orange dot = underspent year)</span>`,
        read: ex.length ? `${esc(body)}: <b>${ex.length}</b> years with an audited figure (${ex[0].year}–${ex[ex.length - 1].year}). It spent <b>${compact(act, "RM")}</b> of <b>${compact(tot, "RM")}</b> allocated over those years (${pct(act / tot)}).${low.length ? ` Underspent in <b>${low.length}</b> year${low.length > 1 ? "s" : ""}: ${low.join(", ")}.` : " It was not underspent in any year held."}` : "No audited year held for this body." };
    },
  },
  table: ["body", "estimate_original_pkkp", "estimate_revised_pkkp", "actual_audited", "execution_rate", "unspent_rm", "status", "note"],
};
G.gap_project_budget_vs_actual = {
  filters: (rs) => ({ year: years(rs.filter((r) => r.actual_pkkp_rm != null)), status: ["", "underspent", "overspent", "within_allocation", "no_allocation", "not_held"] }),
  rows: (rs, f) => rs.filter((r) => r.year === f.year && r.status !== "reserve" && (!f.status || r.status === f.status)),
  read(rs, f, all) {
    const yr = all.filter((r) => r.year === f.year && r.status !== "reserve" && r.maksud_code !== "P.70");
    const tab = sum(yr.map((r) => r.tabled_rm)), alloc = sum(yr.map((r) => r.allocation_pkkp_rm)), act = sum(yr.map((r) => r.actual_pkkp_rm));
    const zero = yr.filter((r) => r.allocation_pkkp_rm > 0 && r.actual_pkkp_rm === 0);
    const under = yr.filter((r) => r.status === "underspent");
    const tabHeld = yr.some((r) => r.tabled_rm != null);
    const zeroIn = zero.filter((r) => r.status === "underspent").length;
    return `For <b>${f.year}</b>, leaving out the contingency reserve (P.70), ${tabHeld ? `Parliament was tabled <b>${compact(tab, "RM")}</b> for development projects; ` : "the amounts tabled in Parliament are not held for this year; "}the audited accounts show an allocation of <b>${compact(alloc, "RM")}</b> and spending of <b>${compact(act, "RM")}</b> (<b>${pct(act / alloc)}</b> of the allocation). <b>${under.length}</b> projects spent markedly less than allocated${zero.length ? `, and <b>${zero.length}</b> projects had an allocation and spent nothing${zeroIn === zero.length ? " (these are among the " + under.length + ")" : ""}` : ""}.${tabHeld ? " Tabled and allocated differ because allocations are revised during the year (supplementary supply, virement)." : ""}`;
  },
  chart(rs) {
    const by = d3.rollups(rs, (v) => v.length, (r) => r.status).map(([s, n]) => ({ s: statusText(s), n })).sort((a, b) => b.n - a.n);
    return Plot.plot({ height: 40 + by.length * 26, marginLeft: 190, x: { label: "Projects", grid: true }, y: { label: null, domain: by.map((x) => x.s) },
      marks: [Plot.barX(by, { x: "n", y: "s", fill: css("--s1") }), Plot.text(by, { x: "n", y: "s", text: (x) => NF(0).format(x.n), dx: 4, textAnchor: "start", fill: css("--text-2") })] });
  },
  sort: (a, b) => (b.unspent_rm || 0) - (a.unspent_rm || 0),
  table: ["maksud_code", "projek_code", "name_pkkp", "tabled_rm", "allocation_pkkp_rm", "actual_pkkp_rm", "execution_rate", "unspent_rm", "status", "name_check", "pkkp_ref"],
};
G.gap_revenue_estimate_vs_collected = {
  filters: () => ({}),
  rows: (rs) => rs.filter((r) => r.breakdown_key === "_total"),
  read(rs) {
    const h = rs.filter((r) => r.actual_audited != null && r.estimate_original);
    const below = h.filter((r) => r.collection_rate_original < 1);
    const last = h[h.length - 1];
    return `Across <b>${h.length}</b> years with an audited actual (${h[0]?.year}–${last?.year}), federal revenue came in below the original estimate in <b>${below.length}</b> (${below.map((r) => r.year).join(", ") || "none"}). In ${last?.year}, <b>${compact(last?.actual_audited, "RM")}</b> was collected against an original estimate of <b>${compact(last?.estimate_original, "RM")}</b> (${pct(last?.collection_rate_original)}).`;
  },
  chart(rs) {
    const h = rs.filter((r) => r.estimate_original != null || r.actual_audited != null);
    const long = h.flatMap((r) => [["Original estimate", r.estimate_original], ["Revised estimate", r.estimate_revised], ["Audited actual", r.actual_audited]].filter((x) => x[1] != null).map(([k, v]) => ({ k, y: +r.year, v })));
    return Plot.plot({ height: 340, marginLeft: 70, x: { label: null, tickFormat: "d" }, y: { grid: true, zero: true, label: "RM", tickFormat: (x) => compact(x, "RM") }, color: { domain: ["Original estimate", "Revised estimate", "Audited actual"], range: [css("--s6"), css("--s2"), css("--s1")], legend: true },
      marks: [Plot.line(long, { x: "y", y: "v", stroke: "k", strokeWidth: 2 }), Plot.dot(long, { x: "y", y: "v", fill: "k", r: 2.6 }), Plot.tip(long, Plot.pointer({ x: "y", y: "v", title: (p) => `${p.y} · ${p.k}\nRM ${exact(p.v)}` }))] });
  },
  table: ["year", "revenue_type", "estimate_original", "estimate_revised", "actual_audited", "collection_rate_original", "collection_rate_revised", "status", "note"],
};
G.gap_reported_vs_audited = {
  filters: (rs) => ({ indicator: [...new Set(rs.map((r) => r.indicator))] }),
  rows: (rs, f) => rs.filter((r) => r.indicator === f.indicator),
  read(rs, f, all) {
    const n = all.filter((r) => r.bnm_vs_pkkp_status !== "not_held").length, ag = all.filter((r) => r.bnm_vs_pkkp_status === "agree").length;
    const m = all.filter((r) => r.mof_vs_pkkp_status !== "not_held").length, mg = all.filter((r) => r.mof_vs_pkkp_status === "agree").length;
    const big = all.filter((r) => r.bnm_minus_pkkp_rm != null).sort((a, b) => Math.abs(b.bnm_minus_pkkp_rm) - Math.abs(a.bnm_minus_pkkp_rm))[0];
    return `Across all headline figures, Bank Negara's series agrees with the audited accounts in <b>${ag} of ${n}</b> year-figures that both hold, and MOF's Fiscal Outlook in <b>${mg} of ${m}</b>.${big ? ` The largest BNM–audited gap is ${esc(big.indicator)} in ${big.year}: <b>${compact(big.bnm_minus_pkkp_rm, "RM")}</b> (${statusText(big.bnm_vs_pkkp_status)}).` : ""} Shown: <b>${esc(f.indicator)}</b>.`;
  },
  chart(rs) {
    const long = rs.flatMap((r) => [["Audited (PKKP)", r.pkkp_audited], ["BNM", r.bnm_actual], ["MOF Fiscal Outlook", r.mof_actual]].filter((x) => x[1] != null).map(([k, v]) => ({ k, y: +r.year, v })));
    return Plot.plot({ height: 320, marginLeft: 70, x: { label: null, tickFormat: "d" }, y: { grid: true, label: "RM", tickFormat: (x) => compact(x, "RM") }, color: { domain: ["Audited (PKKP)", "BNM", "MOF Fiscal Outlook"], range: [css("--s1"), css("--s2"), css("--s3")], legend: true },
      marks: [Plot.line(long, { x: "y", y: "v", stroke: "k", z: "k", strokeWidth: (p) => ({ "Audited (PKKP)": 4, BNM: 2.2, "MOF Fiscal Outlook": 1.2 }[p.k]) }), Plot.dot(long, { x: "y", y: "v", stroke: "k", r: 3.2, fill: css("--panel") }), Plot.tip(long, Plot.pointer({ x: "y", y: "v", title: (p) => `${p.y} · ${p.k}\nRM ${exact(p.v)}` }))] });
  },
  table: ["year", "pkkp_audited", "bnm_actual", "mof_actual", "mof_edition", "bnm_minus_pkkp_rm", "mof_minus_pkkp_rm", "bnm_vs_pkkp_status", "mof_vs_pkkp_status", "note"],
};
G.gap_obligations_growth = {
  filters: () => ({}),
  rows: (rs) => rs,
  read(rs) {
    const last = Math.max(...rs.map((r) => +r.year));
    const ly = rs.filter((r) => +r.year === last && r.instrument !== "debt" && r.instrument !== "deposit_guarantees");
    const debt = rs.find((r) => +r.year === last && r.instrument === "debt");
    return `In <b>${last}</b>, federal debt stood at <b>${compact(debt?.amount_rm, "RM")}</b>${debt?.growth != null ? `, up ${pct(debt.growth)} on the year` : ""}. Beside it, outside the debt figure: ${ly.map((r) => `${esc(r.instrument_label)} <b>${compact(r.amount_rm, "RM")}</b> (${r.growth != null ? (r.growth >= 0 ? "+" : "") + pct(r.growth) : "growth n/a"}, ${statusText(r.status).toLowerCase()})`).join("; ")}. These instruments can overlap, so they are never added together. Deposit and contributor guarantees (EPF, Tabung Haji and others) are savings guaranteed by statute, not borrowing, and are never added to debt.`;
  },
  chart(rs) {
    const h = rs.filter((r) => r.index_first_year != null);
    return Plot.plot({ height: 340, marginLeft: 56, x: { label: null, tickFormat: "d" }, y: { grid: true, label: "Index, first year held = 100" }, color: { legend: true, range: SER() },
      marks: [Plot.ruleY([100], { stroke: css("--line-2") }), Plot.line(h, { x: (r) => +r.year, y: "index_first_year", stroke: "instrument_label", strokeWidth: (r) => (r.instrument === "debt" ? 3 : 1.6) }), Plot.dot(h, { x: (r) => +r.year, y: "index_first_year", fill: "instrument_label", r: 2.4 }),
        Plot.tip(h, Plot.pointer({ x: (r) => +r.year, y: "index_first_year", title: (r) => `${r.instrument_label} · ${r.year}\nRM ${exact(r.amount_rm)}\nindex ${exact(r.index_first_year)}${r.growth != null ? "\ngrowth " + pct(r.growth) + " (debt " + pct(r.debt_growth) + ")" : ""}` }))] });
  },
  table: ["year", "instrument_label", "amount_rm", "growth", "debt_growth", "growth_minus_debt_pp", "ratio_to_debt", "status", "note"],
};
G.gap_target_vs_outcome = {
  filters: () => ({}),
  rows: (rs) => rs,
  read(rs) {
    const by = d3.rollup(rs, (v) => v.length, (r) => r.status);
    return `The Twelfth Malaysia Plan (2021–2025) set <b>${rs.length}</b> quantified targets held here. For <b>${by.get("above_target") || 0}</b> the outcome came in above the target and for <b>${(by.get("below_target") || 0) + (by.get("below_range") || 0)}</b> below it. Above or below is not good or bad by itself: unemployment below target is good news, a deficit below target is not. Read each line. Targets are the plan's original 2021 figures; the 2023 mid-term review's revisions are not held.`;
  },
  chart(rs) {
    const h = rs.filter((r) => typeof r.ratio === "number").map((r) => ({ ...r, lab: `${D.catIx[r.indicator_code]?.name || r.indicator_code}${r.geo_code && r.geo_code !== "MY" ? ", " + geoName(r.geo_code) : ""}${r.breakdown_key !== "_total" ? " (" + brkLabel(r.breakdown_key) + ")" : ""} · ${r.target_line.replace("RMKe-12 Lampiran ", "")}` }));
    return Plot.plot({ height: 40 + h.length * 17, marginLeft: 270, x: { label: "Outcome ÷ target", grid: true, type: "log", tickFormat: (x) => NF(2).format(x) }, y: { label: null, domain: h.map((r) => r.lab), tickFormat: (d) => (d.length > 44 ? d.slice(0, 43) + "…" : d) },
      marks: [Plot.ruleX([1], { stroke: css("--text-3"), strokeDasharray: "3,3" }), Plot.ruleY(h, { x1: 1, x2: "ratio", y: "lab", stroke: css("--line-2") }), Plot.dot(h, { x: "ratio", y: "lab", fill: (r) => (r.ratio >= 1 ? css("--s1") : css("--s2")), r: 4 }),
        Plot.tip(h, Plot.pointerY({ x: "ratio", y: "lab", title: (r) => `${r.lab}\ntarget ${exact(r.target)}\noutcome ${exact(r.outcome)}\n${r.outcome_source}` }))] });
  },
  legend: [["--s1", "outcome at or above target"], ["--s2", "outcome below target"]],
  table: ["indicator_code", "geo_code", "breakdown_key", "target_line", "target", "outcome", "outcome_source", "difference", "ratio", "status", "note"],
};
const NEED = { poverty_absolute_rate: "Absolute poverty rate (%)", income_median_rm: "Median household income (RM)", unemployment_rate: "Unemployment rate (%)", gini: "Gini coefficient" };
const MONEY_M = { state_gov_expenditure_per_capita_rm: "State government spending per person (RM)", state_gov_receipts_per_capita_rm: "State government receipts per person (RM)" };
G.gap_need_vs_money = {
  filters: (rs) => ({ year: years(rs.filter((r) => r.state_gov_expenditure_per_capita_rm != null)), need: Object.keys(NEED), money: Object.keys(MONEY_M) }),
  defaults: { need: "poverty_absolute_rate", money: "state_gov_expenditure_per_capita_rm" },
  labels: { need: NEED, money: MONEY_M },
  rows: (rs, f) => rs.filter((r) => r.year === f.year),
  read(rs, f) {
    const h = rs.filter((r) => r[f.money] != null && r[f.need] != null);
    const fed = rs.find((r) => r.federal_placed_share != null);
    const rr = h.length > 2 ? pearson(h.map((r) => r[f.need]), h.map((r) => r[f.money])) : null;
    const needUp = f.need !== "income_median_rm";
    return `For <b>${f.year}</b>, <b>${h.length}</b> states have both figures. The chart sets ${MONEY_M[f.money].replace(/ \(RM\)/, "").toLowerCase()} against ${NEED[f.need].replace(/ \(.*\)/, "").toLowerCase()}: if money followed need, the points would ${needUp ? "rise to the right" : "fall to the right"}.${rr != null ? ` Across these states the correlation is <b>${NF(2).format(rr)}</b>: ${Math.abs(rr) < 0.3 ? "little sign that money follows need" : (rr > 0) === needUp ? "more money tends to go with more need" : "more money tends to go with less need"}. A pattern, not a cause.` : ""} This is the state governments' own money only.${fed ? ` Federal spending by state is withheld: what the state governments record receiving from the federal government places only <b>${pct(fed.federal_placed_share)}</b> of federal spending in ${f.year} (the guard is 60%; see <a href="#/gaps/gap_federal_placement">where federal money lands</a> for what the federal accounts themselves place).` : ""}`;
  },
  chart(rs, f) {
    const h = rs.filter((r) => r[f.money] != null && r[f.need] != null);
    return Plot.plot({ height: 400, marginLeft: 70, grid: true, x: { label: NEED[f.need] + " →", zero: f.need !== "gini" }, y: { label: "↑ " + MONEY_M[f.money], zero: true, tickFormat: (x) => NF(0).format(x) },
      marks: [Plot.linearRegressionY(h, { x: f.need, y: f.money, stroke: css("--text-3"), strokeDasharray: "3,3", ci: 0 }), Plot.dot(h, { x: f.need, y: f.money, r: 6, fill: css("--s1"), fillOpacity: 0.85 }), Plot.text(h, { x: f.need, y: f.money, text: "state", dy: -11, fontSize: 11, fill: css("--text-2") }),
        Plot.tip(h, Plot.pointer({ x: f.need, y: f.money, title: (r) => `${r.state} · ${r.year}\npoverty ${exact(r.poverty_absolute_rate)}%\nunemployment ${exact(r.unemployment_rate)}%\nmedian income RM ${exact(r.income_median_rm)}\nstate spending RM ${exact(r.state_gov_expenditure_rm)} (${r.state_gov_expenditure_basis})\nper person RM ${exact(r.state_gov_expenditure_per_capita_rm)}` }))] });
  },
  table: ["state", "population", "poverty_absolute_rate", "income_median_rm", "gini", "unemployment_rate", "state_gov_expenditure_rm", "state_gov_expenditure_basis", "state_gov_expenditure_per_capita_rm", "state_gov_receipts_per_capita_rm", "verification_tier", "coverage_note"],
};
G.gap_federal_vs_state = {
  filters: (rs) => ({ transfer: [...new Set(rs.map((r) => r.transfer))], year: years(rs) }),
  transferLabel: { capitation: "Capitation grant", concurrent_list: "Concurrent-list grant", named: "Grants to a named state", loans: "Federal loans to states" },
  rows: (rs, f) => rs.filter((r) => r.transfer === f.transfer && r.year === f.year),
  read(rs, f, all) {
    const t = all.filter((r) => r.transfer === f.transfer && r.geo_code !== "_states");
    const both = t.filter((r) => r.federal_paid_rm != null && r.state_recorded_rm != null);
    const by = d3.rollup(both, (v) => v.length, (r) => r.status);
    const ms = t.filter((r) => r.by_state_status && r.by_state_status !== "not_applicable");
    const msBy = d3.rollup(ms, (v) => v.length, (r) => r.by_state_status);
    const tot = all.filter((r) => r.transfer === f.transfer && r.geo_code === "_states" && r.status);
    return `Across all years held, <b>${both.length}</b> state-years of the <b>${(this.transferLabel[f.transfer] || f.transfer).toLowerCase()}</b> have both the federal figure and the state's own printed figure: ${[...by].sort((a, b) => b[1] - a[1]).map(([k, n]) => `<b>${n}</b> ${statusText(k).toLowerCase()}`).join(", ") || "none"}.${ms.length ? ` Against MOF's own split by state (Lampiran E): ${[...msBy].sort((a, b) => b[1] - a[1]).map(([k, n]) => `<b>${n}</b> ${statusText(k).toLowerCase()}`).join(", ")}.` : ""}${tot.length ? ` The all-states totals are tested separately, one per year: ${tot.filter((r) => ["agree", "consistent"].includes(r.status)).length} of ${tot.length} consistent.` : ""} The table shows ${f.year}; the other rows say why they cannot be compared yet.`;
  },
  chart(rs) {
    const by = d3.rollups(rs, (v) => v.length, (r) => r.status).map(([s, n]) => ({ s: statusText(s), n })).sort((a, b) => b.n - a.n);
    return Plot.plot({ height: 40 + by.length * 26, marginLeft: 220, x: { label: "States", grid: true }, y: { label: null, domain: by.map((x) => x.s) }, marks: [Plot.barX(by, { x: "n", y: "s", fill: css("--s1") })] });
  },
  table: ["place", "comparison", "federal_paid_rm", "federal_recipient", "state_recorded_rm", "difference_rm", "state_share_of_federal", "status", "note"],
};
G.gap_federal_placement = {
  filters: () => ({}),
  rows: (rs) => rs.filter((r) => r.geo_code === "MY"),
  read(rs) {
    const h = rs.filter((r) => r.placed_share != null).sort((a, b) => a.year - b.year);
    const last = h[h.length - 1];
    return `Only <b>${pct(last?.placed_share)}</b> of federal spending in ${last?.year} (RM ${compact(last?.federal_total_rm).replace("RM ", "")} in all) can be placed in a state from the federal accounts: projects whose name names one place, grants to a named state government, and from FY2019 the class grants at MOF's own split by state. Salaries, subsidies, cash transfers and most projects carry no place. That is why federal amounts by state are withheld: the warehouse's guard requires 60% before it publishes them.`;
  },
  chart(rs) {
    const h = rs.filter((r) => r.placed_share != null);
    return Plot.plot({ height: 300, marginLeft: 56, x: { label: null, tickFormat: "d" }, y: { label: "Share of federal spending that can be placed", domain: [0, 1], tickFormat: (x) => pct(x, 0), grid: true },
      marks: [Plot.ruleY([0.6], { stroke: css("--warn"), strokeDasharray: "4,3" }), Plot.text([0.6], { y: (x) => x, x: Math.min(...h.map((r) => +r.year)), text: () => "publication guard: 60%", dy: -7, textAnchor: "start", fill: css("--warn"), fontSize: 11 }),
        Plot.areaY(h, { x: (r) => +r.year, y: "placed_share", fill: css("--s1"), fillOpacity: 0.15 }), Plot.line(h, { x: (r) => +r.year, y: "placed_share", stroke: css("--s1"), strokeWidth: 2 }), Plot.dot(h, { x: (r) => +r.year, y: "placed_share", fill: css("--s1") }),
        Plot.tip(h, Plot.pointer({ x: (r) => +r.year, y: "placed_share", title: (r) => `${r.year}\nplaced ${pct(r.placed_share)}\nfederal total RM ${exact(r.federal_total_rm)}` }))] });
  },
  table: ["year", "federal_total_rm", "placed_rm", "placed_share", "projects_none_rm", "note"],
};

const MONEY = /(_rm|^estimate|^actual|amount|tabled|allocation|_audited|_actual|population|federal_total|prior_year|change_rm|^target$|^outcome$|^difference$|bnm_actual|mof_actual)/;
function cellFmt(k, v) {
  if (v == null || v === "") return `<span class="muted">–</span>`;
  if (k === "status" || /_status$/.test(k)) return statusChip(v);
  if (/(rate|share|growth|ratio)$/.test(k) && typeof v === "number" && !/poverty|unemployment|pp$/.test(k) && Math.abs(v) < 20 && k !== "ratio_to_debt") return pct(v, 2);
  if (/_ref$/.test(k)) return `<span class="mono small">${l1link(v)}</span>`;
  if (k === "indicator_code") return esc(D.catIx[v]?.name || v);
  if (k === "geo_code") return esc(geoName(v));
  if (typeof v === "string" && v.length > 90) return `<div class="clamp2" title="${esc(v)}">${esc(v)}</div>`;
  if (typeof v === "number") return NF(2).format(v);
  return esc(v);
}
const COLNAME = { body: "Ministry or body", estimate_original_pkkp: "Original estimate (RM)", estimate_revised_pkkp: "Allocation (RM)", actual_audited: "Spent, audited (RM)",
  execution_rate: "Share spent", unspent_rm: "Unspent (RM)", maksud_code: "Vote", projek_code: "Project", name_pkkp: "Project name", tabled_rm: "Tabled (RM)",
  allocation_pkkp_rm: "Allocation (RM)", actual_pkkp_rm: "Spent, audited (RM)", name_check: "Name check", pkkp_ref: "Source row", revenue_type: "Revenue type",
  estimate_original: "Original estimate (RM)", estimate_revised: "Revised estimate (RM)", collection_rate_original: "Collected vs original", collection_rate_revised: "Collected vs revised",
  pkkp_audited: "Audited, PKKP (RM)", bnm_actual: "Bank Negara (RM)", mof_actual: "MOF (RM)", mof_edition: "MOF edition", bnm_minus_pkkp_rm: "BNM − audited (RM)", mof_minus_pkkp_rm: "MOF − audited (RM)",
  bnm_vs_pkkp_status: "BNM vs audited", mof_vs_pkkp_status: "MOF vs audited", instrument_label: "Obligation", amount_rm: "Amount (RM)", growth: "Growth", debt_growth: "Debt growth",
  growth_minus_debt_pp: "Growth − debt growth (pp)", ratio_to_debt: "Ratio to debt", indicator_code: "Indicator", geo_code: "Area", breakdown_key: "Breakdown", target_line: "Plan table",
  target: "Target", outcome: "Outcome", outcome_source: "Outcome source", difference: "Difference", ratio: "Outcome ÷ target", state: "State", population: "Population",
  poverty_absolute_rate: "Poverty (%)", income_median_rm: "Median income (RM)", gini: "Gini", unemployment_rate: "Unemployment (%)", state_gov_expenditure_rm: "State spending (RM)",
  state_gov_expenditure_basis: "Basis", state_gov_expenditure_per_capita_rm: "State spending per person (RM)", state_gov_receipts_per_capita_rm: "State receipts per person (RM)",
  verification_tier: "Checked to", coverage_note: "Coverage", place: "State", comparison: "Comparison", federal_paid_rm: "Federal paid (RM)", federal_recipient: "Paid to",
  state_recorded_rm: "State recorded (RM)", difference_rm: "Difference (RM)", state_share_of_federal: "State share", year: "Year", federal_total_rm: "Federal spending (RM)",
  placed_rm: "Placeable (RM)", placed_share: "Share placeable", projects_none_rm: "Projects with no place (RM)", status: "Status", note: "Note" };
const colLabel = (k) => COLNAME[k] || k.replace(/_rm$/, " (RM)").replace(/_/g, " ").replace(/\bpkkp\b/g, "PKKP").replace(/\bbnm\b/g, "BNM").replace(/\bmof\b/g, "MOF").replace(/^./, (x) => x.toUpperCase());

async function viewGap(name, v = $("#view")) {
  const g = D.gaps.find((x) => x.name === name);
  if (!g) { v.innerHTML = `<div class="note">No gap view ${esc(name)}. <a href="#/gaps">All views</a></div>`; return; }
  crumbs([["Policy gaps", "#/gaps"], [g.title, ""]]);
  v.innerHTML = `<div class="skel">Loading ${esc(g.title)}…</div>`;
  const d = await J(`gap/${name}.json`);
  const all = objs(d);
  const cfg = G[name] || { filters: () => ({}), rows: (r) => r, read: () => "", chart: () => null, table: d.cols };
  const opts = cfg.filters(all);
  const [, P] = hashParams();
  const f = {};
  for (const [k, list] of Object.entries(opts)) f[k] = list.includes(P.get(k)) ? P.get(k) : (k === "status" ? "" : list[list.length - 1 - (k === "indicator" || k === "transfer" || k === "flow" ? list.length - 1 : 0)]);
  if (opts.flow) f.flow = opts.flow.includes(P.get("flow")) ? P.get("flow") : "devex";
  for (const [k, dv] of Object.entries(cfg.defaults || {})) if (!opts[k].includes(P.get(k))) f[k] = dv;
  const qs = QUESTIONS.find((q) => q[1] === name);
  const cavs = [...new Set(all.flatMap((r) => String(r.caveats || "").split(";").filter(Boolean)))].sort();
  const METHOD = {
    gap_budget_vs_actual: "One row per body, year and kind of money (operating or development). The allocation is the revised estimate printed in the audited accounts (PKKP); spending is the audited actual from the same volume. Share spent = spent ÷ allocation. Budget-book figures sit in their own columns and are never mixed with the audited ones.",
    gap_project_budget_vs_actual: "One row per development project and year, joined on its vote and project codes. Tabled amounts come from the Development Estimates book; allocation and spending come from the audited accounts. The contingency reserve (P.70) is left out of every total, because it is drawn by transfers to other votes.",
    gap_revenue_estimate_vs_collected: "Federal revenue by type and year: the original and revised estimates against the audited collection. Collection rate = collected ÷ estimate.",
    gap_reported_vs_audited: "The same headline figure (revenue, spending, balance) as printed by the audited accounts, by Bank Negara and by MOF's Fiscal Outlook. Differences are shown to the ringgit; small rounding differences are marked minor.",
    gap_obligations_growth: "Each obligation outside federal debt (commitments, PFI, guarantees) by year, its growth, and its growth set against the growth of debt. They can overlap, so they are never added together.",
    gap_target_vs_outcome: "Each numeric target in the Twelfth Malaysia Plan's appendix tables, beside the outcome later published by DOSM or MOF for the same year and area. Above or below is a fact, not a verdict.",
    gap_need_vs_money: "By state and survey year: measures of need (poverty, income, unemployment, inequality) beside the state government's own spending and receipts per person. Federal spending by state is withheld below the 60% placement guard.",
    gap_federal_vs_state: "By transfer, state and year: what the federal accounts say was paid, beside what the state's own audited statement records receiving. Each row says how they compare, or why they cannot be compared yet.",
    gap_federal_placement: "For each year: how much federal spending can be given a state from the federal accounts (projects named for one place, grants to a named state government, and from FY2019 MOF's split by state). The rest has no place.",
  };
  v.innerHTML = `
    <div class="phead"><div style="min-width:0"><div class="row" style="gap:6px">${chip("Policy gap", "accent")}${chip(esc(g.title))}</div>
        <h1>${esc(qs ? qs[0] : g.question)}</h1></div>
      <div class="pactions"><button class="btn primary" id="brief" type="button">Copy as brief</button><button class="btn" id="gcsv" type="button">Download CSV</button><button class="btn" id="gshare" type="button">Share</button></div></div>
    <div class="toolbar" id="gf"></div>
    <div class="split">
      <div class="main-col">
        <div class="answer"><div class="small muted" style="margin-bottom:6px">The answer, from the rows below</div><div class="finding" id="read"></div></div>
        <div class="card" style="margin-top:12px"><div class="legend" id="glegend"></div><div class="chart" id="gchart"></div></div>
        ${cfg.drill ? `<div class="sechead"><h2>${esc(cfg.drill.title)}</h2><span class="small muted">${esc(cfg.drill.hint)}</span></div><div class="card"><select id="gdsel" style="min-width:300px;margin-bottom:6px"></select><div class="legend" id="gdleg"></div><div class="chart" id="gdchart"></div><div class="finding small" id="gdread" style="margin-top:8px"></div></div>` : ""}
        <div class="sechead"><h2>The rows</h2><span class="small muted" id="gcount"></span><input type="search" id="gq2" placeholder="Filter rows…"></div>
        <div class="tablewrap" id="gtbl"></div>
      </div>
      <aside class="insp">
        <div class="insp-sec"><h4>How this is worked out</h4><p class="small" style="margin:0;color:var(--text-2)">${esc(METHOD[name] || g.question)}</p><p class="small" style="margin:8px 0 0"><a href="${REPO}/blob/main/core/README.md" target="_blank" rel="noopener">Full method (core/README.md) →</a></p></div>
        <div class="insp-sec"><h4>Data</h4><div class="kvs"><div><span>Rows</span><b>${NF(0).format(all.length)}</b></div><div><span>Caveats</span><b>${cavs.length}</b></div></div>
          <p class="small" style="margin:8px 0 0"><a href="${REPO}/blob/main/core/${name}.csv" target="_blank" rel="noopener">Source table on GitHub →</a></p></div>
        ${cavs.length ? `<div class="insp-sec"><h4>Caveats</h4>${cavs.map((k) => `<details class="cav"><summary><span class="chip warn">${esc(k)}</span> ${esc((D.caveats[k] || "").split(/[.:]/)[0])}</summary><p>${esc(D.caveats[k] || "")}</p></details>`).join("")}</div>` : ""}
        <div class="insp-sec"><h4>Next steps</h4><div class="links">${name === "gap_budget_vs_actual" ? `<a href="#/compare?u=ministry">Compare ministries over time →</a>` : name === "gap_project_budget_vs_actual" ? `<a href="#/compare?u=project">Compare projects over time →</a>` : name === "gap_need_vs_money" ? `<a href="#/compare">Compare states over time →</a>` : ""}<a href="#/gaps">All policy questions →</a></div></div>
      </aside>
    </div>`;
  $("#gshare").onclick = () => copy(location.href, "Link to this exact view copied");
  const label = (k, x) => (cfg.labels?.[k]?.[x] || (k === "flow" ? cfg.flowLabel[x] : k === "transfer" ? cfg.transferLabel[x] : k === "status" ? (x ? statusText(x) : "All") : x));
  function draw() {
    const p = new URLSearchParams(Object.entries(f).filter(([, x]) => x)); setParams("/gaps/" + name, p);
    $("#gf").innerHTML = Object.entries(opts).map(([k, list]) => list.length <= 4 ? `<div><div class="small muted">${colLabel(k)}</div><div class="seg">${list.map((x) => `<button type="button" data-k="${k}" data-v="${esc(x)}" class="${f[k] === x ? "on" : ""}">${esc(label(k, x))}</button>`).join("")}</div></div>`
      : `<div><div class="small muted">${colLabel(k)}</div><select data-k="${k}">${list.map((x) => `<option value="${esc(x)}" ${f[k] === x ? "selected" : ""}>${esc(label(k, x))}</option>`).join("")}</select></div>`).join("") || `<span class="small muted" style="padding:4px 2px">No filters: every year and series is shown.</span>`;
    $$("#gf button").forEach((b) => (b.onclick = () => { f[b.dataset.k] = b.dataset.v; draw(); }));
    $$("#gf select").forEach((s) => (s.onchange = () => { f[s.dataset.k] = s.value; draw(); }));
    const rs = cfg.rows(all, f);
    $("#read").innerHTML = cfg.read(rs, f, all) || "";
    const el = $("#gchart"); el.innerHTML = "";
    $("#glegend").innerHTML = (cfg.legend || []).map(([c, t]) => `<span><i style="background:var(${c});height:10px"></i>${esc(t)}</span>`).join("");
    if (window.Plot) {
      const W = el.clientWidth || 900, P0 = Plot.plot;
      Plot.plot = (o) => P0({ width: W, ...o, style: { background: "transparent", fontSize: "12px", color: css("--text-2"), ...(o.style || {}) } });
      let ch = null; try { ch = rs.length ? cfg.chart(rs, f) : null; } finally { Plot.plot = P0; }
      el.parentElement.style.display = ch ? "" : "none"; if (ch) el.append(ch);
    }
    const tc = (cfg.table || d.cols).filter((k) => d.cols.includes(k));
    const sorted = cfg.sort ? [...rs].sort(cfg.sort) : rs;
    $("#gcount").textContent = `${NF(0).format(rs.length)} rows${rs.length > 500 ? " · first 500 shown" : ""}`;
    $("#gtbl").innerHTML = `<table><thead><tr>${tc.map((k) => `<th class="${typeof rs[0]?.[k] === "number" ? "n" : ""}">${esc(colLabel(k))}</th>`).join("")}</tr></thead><tbody>${sorted.slice(0, 500).map((r) => `<tr>${tc.map((k) => `<td class="${typeof r[k] === "number" ? "n" : ""} ${k === "note" ? "small muted" : ""}" ${k === "note" || k === "federal_recipient" || k === "outcome_source" ? 'style="min-width:240px;max-width:360px"' : ""}>${cellFmt(k, r[k])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    $("#brief").onclick = () => {
      const txt = $("#read").innerText;
      copy(`${qs ? qs[0] : g.question}\n\n${txt}\n\nSource: Malaysia Economy Data Warehouse (IKRAM), gap view ${name}, release ${D.meta.release_id}${Object.keys(f).length ? " (" + Object.entries(f).filter(([, x]) => x).map(([k, x]) => `${k} ${x}`).join(", ") + ")" : ""}. Rows and citations: ${location.href}\n${cavs.length ? "Caveats: " + cavs.map((k) => `${k} ${D.caveats[k] || ""}`).join(" ") : ""}`, "Brief copied, with its source");
    };
    $("#gcsv").onclick = () => download(`${name}.csv`, toCSV(d.cols, d.rows));
    $("#gq2").oninput = (e) => filterTable($("#gtbl"), e.target.value);
    if ($("#gq2").value) filterTable($("#gtbl"), $("#gq2").value);
    if (cfg.drill) drill();
  }
  function drill() {
    const keys = cfg.drill.keys(all, f);
    const sel = $("#gdsel");
    const cur = keys.includes(f._d) ? f._d : keys.includes(P.get("d")) ? P.get("d") : cfg.drill.pick(all, f, keys);
    f._d = cur;
    sel.innerHTML = keys.map((k) => `<option ${k === cur ? "selected" : ""}>${esc(k)}</option>`).join("");
    sel.onchange = () => { f._d = sel.value; drill(); };
    const el = $("#gdchart"); el.innerHTML = "";
    const W = el.clientWidth || 900, P0 = Plot.plot;
    Plot.plot = (o) => P0({ width: W, ...o, style: { background: "transparent", fontSize: "12px", color: css("--text-2") } });
    try { const out = cfg.drill.render(all, f, cur); if (out?.chart) el.append(out.chart); $("#gdread").innerHTML = out?.read || ""; $("#gdleg").innerHTML = out?.legend || ""; } finally { Plot.plot = P0; }
  }
  $("#gtbl").addEventListener("click", (e) => { const tr = e.target.closest("tbody tr"); if (!tr || !cfg.drill) return; const k = cfg.drill.fromRow?.(tr); if (k) { f._d = k; drill(); $("#gdsel").scrollIntoView({ behavior: "smooth", block: "center" }); } });
  draw();
}

/* =====================================================================================================
   SOURCES, METHOD
   ===================================================================================================== */
function viewSources(v) {
  crumbs([["Sources & caveats", "#/sources"]]);
  const stCount = d3.rollup(D.registry, (x) => x.length, (r) => r.status);
  v.innerHTML = `<h1>Sources &amp; caveats</h1><p class="lede">The registry is one checklist of every series the warehouse holds or needs: its publisher, coverage, licence and whether it may be redistributed. Series marked no_redistribution never leave the warehouse.</p>
    <div class="row" style="margin:14px 0">${[...stCount].sort((a, b) => b[1] - a[1]).map(([s, n]) => chip(`${esc(s)} · ${n}`)).join("")}</div>
    <input type="search" id="rq" placeholder="Filter the registry…" style="width:100%;max-width:420px;margin-bottom:10px">
    <div class="tablewrap" id="reg"></div>
    <h2>Caveats</h2><p class="muted small">Attached to rows by code; the same code means the same warning everywhere.</p>
    <div class="grid g2">${Object.entries(D.caveats).sort((a, b) => a[0].localeCompare(b[0], "en", { numeric: true })).map(([k, t]) => `<div class="card small"><span class="chip warn">${esc(k)}</span> ${esc(t)}</div>`).join("")}</div>
    <h2>Series breaks</h2><div class="tablewrap" style="max-height:none"><table><thead><tr><th>Indicator</th><th>New basis from</th><th>What changed</th><th>Evidence</th></tr></thead><tbody>${D.breaks.map((b) => `<tr><td class="mono small">${esc(b.indicator_prefix)}</td><td>${esc(b.first_period_new_basis)}</td><td>${esc(b.what_changed)}</td><td class="small mono">${esc(b.evidence)}</td></tr>`).join("")}</tbody></table></div>`;
  const draw = (q = "") => {
    const rs = D.registry.filter((r) => !q || Object.values(r).join(" ").toLowerCase().includes(q.toLowerCase()));
    $("#reg").innerHTML = `<table><thead><tr><th>Series</th><th>Title</th><th>Publisher</th><th>Status</th><th>Theme</th><th>Depth</th><th>Held</th><th>Missing</th><th>Licence</th><th>Redistribution</th></tr></thead><tbody>${rs.map((r) => `<tr><td class="mono small">${esc(r.series_id)}</td><td>${esc(r.title_en)}</td><td>${esc(r.publisher)}</td><td>${chip(esc(r.status), ["verified", "extracted", "held"].includes(r.status) ? "accent" : "")}</td><td class="small">${esc(themeName(r.theme))}</td><td class="small">${esc(r.geo_depth)}</td><td class="small">${esc(r.held_coverage)}</td><td class="small muted">${esc(r.missing_coverage)}</td><td class="small">${esc(r.licence)}</td><td class="small">${r.redistribution === "no_redistribution" ? chip("never leaves", "warn") : esc(r.redistribution)}</td></tr>`).join("")}</tbody></table>`;
  };
  $("#rq").oninput = (e) => draw(e.target.value);
  draw();
}

function viewMethod(v) {
  crumbs([["Method & trust", "#/method"]]);
  const rule = (n, t, d) => `<div class="card"><div class="mono" style="color:var(--accent)">${n}</div><h3 style="margin-top:4px">${t}</h3><div class="small muted">${d}</div></div>`;
  v.innerHTML = `<h1>Method &amp; trust</h1><p class="lede">Every number has to survive a hostile reader: traceable to its page, checked, carrying its uncertainty and its caveats. These are the rules that make that true, and how the charts on this site keep them.</p>
    <h2>The warehouse's rules</h2><div class="grid g3">
      ${rule("01", "Kept as printed", "A misprint is kept and documented with proof in the source's validation file, never corrected silently. Fixing an extraction bug is fine; altering what a publisher printed is not.")}
      ${rule("02", "Every row cited", "Each value keeps its file, table, pdf page and printed page, and the source row it was read from.")}
      ${rule("03", "Checked twice", "Each source is reconciled to its own printed totals, then an independent verifier, blind to the extraction code, re-derives a sample from the original. Anything IKRAM publishes also needs a human spot-check.")}
      ${rule("04", "Codes, not names", "Places, ministries, votes and projects are joined on official codes, never on names.")}
      ${rule("05", "Every vintage kept", "A refresh never destroys the previous release; each is logged by sha256 and date so it can be recovered exactly.")}
      ${rule("06", "Uncertainty carried", "A survey estimate carries its confidence interval, or says it is unknown. Small areas are never ranked.")}
      ${rule("07", "Licence checked", "Every series has its licence and redistribution status in the registry. Nothing marked no_redistribution leaves the warehouse; individuals are never returned.")}
      ${rule("08", "Neutral by construction", "Methods are declared before results are seen, every view runs for all states and Federal Territories, and the core holds no party attribute.")}
      ${rule("09", "Report figures only where needed", "Figures from printed reports enter only where the open data lack them, or diverge from them, and the divergence is registered.")}
    </div>
    <h2>How the charts keep them</h2><div class="card"><ul style="margin:0;padding-left:18px;line-height:1.9">
      <li>No smoothing and no interpolation: a missing year is a break in the line, never a zero or a guess.</li>
      <li>A dashed orange rule marks a change of method (for example the 2019 poverty line); the line does not run across it.</li>
      <li>Each basis (estimate, revised estimate, audited actual, target) and each publisher is its own line; they are never blended.</li>
      <li>Where two editions print different values for the same year, the main line uses the year's own volume, else the latest edition, and the other value is drawn as a hollow dashed point.</li>
      <li>Amounts and counts start at zero; rates, indices and growth are fitted to the data, and the chart says which.</li>
      <li>Every tooltip gives the value exactly as printed, its edition, table, page and file.</li>
      <li>States are compared in bands against Malaysia (within 1 percentage point, or 5%, or overlapping confidence intervals), never ranked; below state level nothing is coloured or ranked.</li>
    </ul></div>
    <h2>What is not published</h2><div class="grid g2">
      <div class="note">The audit-findings inventory and its recurrence view failed blind verification on 2026-11-06 and are held as drafts until it is fixed; they are not on this site.</div>
      <div class="note">Federal amounts by state, wherever less than 60% of federal spending can be placed, are withheld; their share placed is shown instead.</div>
    </div>`;
}

/* =====================================================================================================
   COMMAND PALETTE
   ===================================================================================================== */
let palItems = [], palSel = 0;
function openPalette() { $("#palette").classList.add("open"); $("#pq").value = ""; palRender(""); $("#pq").focus(); }
window.openPalette = openPalette;
function closePalette() { $("#palette").classList.remove("open"); }
function initPalette() {
  $("#openPalette").onclick = openPalette;
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); $("#palette").classList.contains("open") ? closePalette() : openPalette(); }
    else if (e.key === "/" && !/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) { e.preventDefault(); openPalette(); }
    else if (e.key === "Escape") closePalette();
  });
  $("#palette").onclick = (e) => { if (e.target.id === "palette") closePalette(); };
  $("#pq").oninput = (e) => palRender(e.target.value);
  $("#pq").onkeydown = (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); palSel = Math.max(0, Math.min(palItems.length - 1, palSel + (e.key === "ArrowDown" ? 1 : -1))); palMark(); }
    else if (e.key === "Enter" && palItems[palSel]) { location.hash = palItems[palSel][1]; closePalette(); }
  };
}
function palRender(q) {
  const base = [
    ...[["About", "#/about"], ["Explore data", "#/explore"], ["Policy gaps", "#/gaps"], ["Compare: states, ministries or projects, over time", "#/compare"], ["States", "#/states"], ["Sources & caveats", "#/sources"], ["Method & trust", "#/method"]].map(([t, h]) => ["Page", h, t, ""]),
    ...QUESTIONS.map(([t, n]) => ["Gap", "#/gaps/" + n, t, D.gaps.find((g) => g.name === n)?.title || ""]),
    ...STATES.map(([g]) => ["State", "#/state/" + g, geoName(g), g]),
    ...D.cat.map((c) => ["Data", "#/explore/" + encodeURIComponent(c.code), c.name, `${c.first}–${c.last}`, c.definition + " " + c.code + " " + themeName(c.theme)]),
  ];
  const w = q.toLowerCase().split(/\s+/).filter(Boolean);
  palItems = (w.length ? base.filter((x) => w.every((t) => (x[2] + " " + x[3] + " " + (x[4] || "")).toLowerCase().includes(t))) : base.slice(0, 18)).slice(0, 40);
  palSel = 0;
  $("#pres").innerHTML = palItems.map((x, i) => `<a href="${x[1]}" data-i="${i}"><span class="k">${x[0]}</span><span>${esc(x[2])}</span><small>${esc(x[3])}</small></a>`).join("") || `<div class="skel">No match</div>`;
  $$("#pres a").forEach((a) => (a.onclick = closePalette));
  palMark();
}
function palMark() { $$("#pres a").forEach((a, i) => a.classList.toggle("sel", i === palSel)); $$("#pres a")[palSel]?.scrollIntoView({ block: "nearest" }); }

boot().catch((e) => { $("#view").innerHTML = `<div class="note">The warehouse data did not load: ${esc(e.message)}. If you opened index.html from disk, serve the folder instead (python3 -m http.server -d site) after building it (python3 apps/site/build_site_data.py).</div>`; });
