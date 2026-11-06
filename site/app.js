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
const REPO = "https://github.com/ammarroslizar/malaysia-economy";

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
  return b.split("|").map((kv) => { const [k, v] = kv.split("="); return `${AXIS[k] || k.replace(/_/g, " ")}: ${(v || "").replace(/_/g, " ")}`; }).join(" · ");
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
  const [meta, cat, geo, themes, caveats, breaks, gaps, registry] = await Promise.all(
    ["meta.json", "catalogue.json", "geo.json", "themes.json", "caveats.json", "breaks.json", "gaps.json", "registry.json"].map(J));
  Object.assign(D, { meta, cat, geo, themes, caveats, breaks, gaps, registry });
  D.geoIx = Object.fromEntries(geo.map((g) => [g.code, g]));
  D.catIx = Object.fromEntries(cat.map((c) => [c.code, c]));
  $("#release").textContent = "release " + meta.release_id.replace("core-", "");
  window.addEventListener("hashchange", route);
  initPalette();
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
  $$("#nav a").forEach((a) => a.classList.toggle("on", a.dataset.r === (top === "state" ? "states" : top)));
  $("#side").classList.remove("open");
  const v = $("#view");
  window.scrollTo(0, 0);
  const R = { about: viewAbout, explore: (v) => (seg[1] ? viewIndicator(decodeURIComponent(seg[1]), v) : viewExplore(v)),
    gaps: (v) => (seg[1] ? viewGap(seg[1], v) : viewGaps(v)), states: viewStates, state: (v) => viewState(decodeURIComponent(seg[1] || ""), v),
    sources: viewSources, method: viewMethod };
  Promise.resolve((R[top] || viewAbout)(v)).catch((e) => { v.innerHTML = `<div class="note">Could not load this view: ${esc(e.message)}</div>`; console.error(e); });
}

/* =====================================================================================================
   ABOUT
   ===================================================================================================== */
function viewAbout(v) {
  crumbs([["About", "#/about"]]);
  const m = D.meta, lv = m.by_level;
  const nThemes = new Set(D.cat.map((c) => c.theme)).size;
  const smallArea = (lv.district || 0) + (lv.parlimen || 0) + (lv.dun || 0);
  v.innerHTML = `
  <div class="row" style="gap:6px;margin-bottom:6px">${chip("Open · free · every figure cited", "accent")}${chip("Built for IKRAM")}</div>
  <h1 style="font-size:34px;max-width:860px">Malaysia's economy, from the nation down to the DUN, with every number traced to its page.</h1>
  <p class="lede">A data warehouse that brings together what DOSM, Bank Negara, the Ministry of Finance, the Accountant General, the Auditor-General, the Economic Planning Unit and the state governments publish, puts it on one set of codes, and checks the sources against each other. Where they agree to the ringgit, you can rely on it; where they differ, it shows you by how much.</p>
  <div class="row" style="margin:18px 0 26px"><a class="btn primary" href="#/explore">Explore the data →</a><a class="btn" href="#/gaps">See the policy gaps</a><button class="btn" type="button" onclick="openPalette()">Search <kbd>⌘K</kbd></button></div>

  <div class="grid g4">
    ${kpi(NF(0).format(m.observations), "observations, each with its citation")}
    ${kpi(m.indicators, `indicators across ${nThemes} themes`)}
    ${kpi(NF(0).format(m.places), "places: Malaysia, 16 states and FTs, districts, parlimen, DUN")}
    ${kpi(m.gap_views, "policy-gap views: plan, budget, need, federal–state, audit")}
  </div>

  <h2>Three ways in</h2>
  <div class="grid g3">
    <a class="card link" href="#/explore"><h3>Explore data</h3><p class="muted small">Browse by theme, pick a place and a breakdown, and see the series as published: gaps where years are missing, breaks where the method changed, each source as its own line. Download any view as CSV with its citations.</p><span class="small">Open the catalogue →</span></a>
    <a class="card link" href="#/gaps"><h3>Policy gaps</h3><p class="muted small">Start from a question: was the budget spent? Did the Plan hit its targets? Does money follow need? Each view gives a plain-language reading, the chart, the rows behind it and the caveats, ready to copy into a brief.</p><span class="small">Ask a question →</span></a>
    <a class="card link" href="#/states"><h3>States</h3><p class="muted small">One page per state and Federal Territory: population, poverty, income, jobs and the state government's own accounts, each beside Malaysia's. States are compared in bands, never ranked.</p><span class="small">Pick a state →</span></a>
  </div>

  <h2>How it is built</h2>
  <p class="muted" style="max-width:780px">Five layers. Each one can be rebuilt from the one below it, so any number on this site can be walked back to the file it came from.</p>
  <div class="layers">
    ${layer("L0", "Raw files", "PDFs and CSVs as the publisher released them, kept by sha256 in a private archive.")}
    ${layer("L1", "Source tables", "Each table as printed: row by row, page by page, with the publisher's own totals checked.")}
    ${layer("L2", "Conformed core", "One set of codes for place, period, indicator, breakdown, entity and source; every row cites L1.")}
    ${layer("L3", "Gap views", "Named comparisons across sources: budget vs actual, plan vs outcome, need vs money.")}
    ${layer("L4", "Applications", "This site, the agent tools (no SQL, every number cited) and models, which are never data.")}
  </div>
  <div class="grid g2" style="margin-top:14px">
    <div class="card"><h3>Truth by reconciliation</h3><p class="small muted" style="margin:0">No single source is taken as the truth. Each domain has a hub that the others are checked against: DOSM for the real economy and people, the audited federal accounts (PKKP) for federal money, each state's audited statements for the states, BNM for money and credit. The product is the reconciliation: where independent institutions agree, and where they diverge, kept as published.</p></div>
    <div class="card"><h3>What is held</h3><p class="small muted" style="margin:0">${m.series_held} of ${m.series_registered} registered series are held today: federal accounts FY2009–2024, budgets and development estimates, revenue estimates, nine MOF Fiscal Outlooks, BNM, 121 DOSM datasets refreshed daily, the Auditor-General's reports, 13 states' accounts, DOSM survey reports and the Twelfth Malaysia Plan. <a href="#/sources">See the registry →</a></p></div>
  </div>

  <h2>How to use it</h2>
  <div class="grid g4">
    ${step(1, "Find", "Press ⌘K (or Ctrl K) and type a topic, a state or a question: poverty, Kelantan, unspent.")}
    ${step(2, "Read", "Each chart says what it shows. Hover any point for the value exactly as printed, its table, page and file.")}
    ${step(3, "Check", "Open the citation table under every chart: the edition, the page and the source row (L1) behind each value.")}
    ${step(4, "Use", "Download the CSV, copy a link to the exact view, or copy a gap view as a brief with its sources.")}
  </div>

  <h2>What you can do with it</h2>
  <div class="grid g3">
    ${use("Advocacy brief", "Show that a ministry left a share of its development money unspent, year after year, with the audited figure and the page.", "#/gaps/gap_budget_vs_actual")}
    ${use("Plan accountability", "Put each Twelfth Malaysia Plan 2025 target beside the outcome that DOSM or MOF later published.", "#/gaps/gap_target_vs_outcome")}
    ${use("Need vs money", "Line up poverty, income and unemployment with what each state government spends per person.", "#/gaps/gap_need_vs_money")}
    ${use("Fiscal risk", "Track guarantees, PFI and commitments, which sit outside debt, against the growth of debt itself.", "#/gaps/gap_obligations_growth")}
    ${use("Constituency profile", "See poverty, income and jobs for a parlimen or DUN, with the caveat that DOSM publishes no sampling error there.", "#/explore/poverty.absolute.rate?lvl=parlimen")}
    ${use("Source check", "See where the Ministry of Finance, Bank Negara and the audited accounts print the same figure, and where they differ.", "#/gaps/gap_reported_vs_audited")}
  </div>

  <h2>How it compares</h2>
  <p class="muted" style="max-width:780px">The official portals are the source of most of these figures, and the place to go for the latest release. This warehouse adds what none of them does on its own: putting different publishers side by side.</p>
  <div class="tablewrap" style="max-height:none"><table class="cmp">
    <thead><tr><th style="cursor:auto">What you need</th><th style="cursor:auto">This warehouse</th><th style="cursor:auto">OpenDOSM / data.gov.my</th><th style="cursor:auto">World Bank WDI</th><th style="cursor:auto">MOF / AG portals</th></tr></thead>
    <tbody>
      ${cmpRow("Statistics of people, jobs, prices", "y:Yes, from DOSM", "y:Yes, the source", "p:National only", "x:No")}
      ${cmpRow("Federal budget, accounts and audit together", "y:Yes, FY2009–2026", "x:No", "x:No", "p:Separate PDFs")}
      ${cmpRow("State governments' own accounts", "y:13 states", "x:No", "x:No", "p:Per state, as PDFs")}
      ${cmpRow("Below state: district, parlimen, DUN", "y:Yes, flagged", "y:Yes", "x:No", "x:No")}
      ${cmpRow("Same figure from different publishers, compared", "y:Yes: agree / differ, by how much", "x:No", "x:No", "x:No")}
      ${cmpRow("Every value cited to table, page and file", "y:Yes", "p:Dataset level", "p:Series level", "p:Document level")}
      ${cmpRow("Series breaks and caveats on the chart", "y:Yes", "p:In notes", "p:In notes", "x:No")}
      ${cmpRow("Plan targets vs outcomes", "y:RMKe-12", "x:No", "x:No", "x:No")}
      ${cmpRow("Latest release, same day", "p:Daily for DOSM; reports as loaded", "y:Yes", "p:Annual", "y:Yes")}
      ${cmpRow("International comparison", "x:Malaysia only", "x:No", "y:Yes", "x:No")}
    </tbody></table></div>

  <h2>Read before you publish</h2>
  <div class="grid g2">
    <div class="note">Survey estimates (poverty, income, jobs) carry sampling error. DOSM publishes none below state level, so a small difference between two districts, parlimen or DUN may not be real. The site never ranks or colours them.</div>
    <div class="note">Most federal spending has no place in the federal accounts (salaries, subsidies, cash transfers, most projects). Federal amounts by state are withheld wherever less than 60% can be placed; what is shown is the share that can be.</div>
    <div class="note info">Figures are kept exactly as printed. Where a publisher misprints, the misprint is kept and documented, never corrected silently. Where two publishers differ, both are shown.</div>
    <div class="note info">Methods are declared before results are seen, and every view runs for all 13 states and the Federal Territories. The warehouse holds no party attribute. <a href="#/method">Method &amp; trust →</a></div>
  </div>

  <h2>For analysts and developers</h2>
  <div class="card"><div class="grid g3 small">
    <div><b>Every table as CSV.</b> <span class="muted">The conformed core (<span class="mono">core/</span>) and every source table (<span class="mono">sources/&lt;name&gt;/data</span>) are plain CSV in the repository, with their provenance columns.</span></div>
    <div><b>Agent tools.</b> <span class="muted">Typed tools over the core (<span class="mono">apps/tools/</span>) answer questions for people and AI agents with no SQL, every number cited, arithmetic only through a declared derive step.</span></div>
    <div><b>Rebuild it yourself.</b> <span class="muted">One command rebuilds this site's data from the core: <span class="mono">python3 apps/site/build_site_data.py</span>. See the <a href="${REPO}#readme" target="_blank" rel="noopener">README</a> and HANDOVER.</span></div>
  </div></div>
  <p class="muted small" style="margin-top:28px">Built from ${esc(m.built_from)}. Figures are official statistics and accounts republished with their citation; licences are tracked per series in the <a href="#/sources">registry</a>. A publisher's takedown request is honoured.</p>`;
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
  const [path, P] = hashParams();
  const st = { q: P.get("q") || "", theme: P.get("theme") || "", lvl: P.get("lvl") || "", pub: P.get("pub") || "" };
  const themes = [...new Set(D.cat.map((c) => c.theme))].sort((a, b) => (a === "cross") - (b === "cross") || a.localeCompare(b, "en", { numeric: true }));
  const pubs = [...new Set(D.cat.flatMap((c) => c.publishers))].sort();
  v.innerHTML = `
    <h1>Explore data</h1>
    <p class="lede">${D.cat.length} indicators, ${NF(0).format(D.meta.observations)} observations. Pick one to chart it by place, period and breakdown, with every value cited.</p>
    <div class="layout-2" style="margin-top:18px">
      <aside class="facets">
        <input type="search" id="eq" placeholder="Filter indicators…" value="${esc(st.q)}" style="width:100%;margin-bottom:12px">
        <div class="small muted" style="padding:0 9px 4px">Theme</div>
        <div id="fTheme"></div>
        <div class="small muted" style="padding:14px 9px 4px">Lowest level</div>
        <div id="fLvl"></div>
        <div class="small muted" style="padding:14px 9px 4px">Publisher</div>
        <div id="fPub"></div>
      </aside>
      <section><div class="row" style="justify-content:space-between;margin-bottom:8px"><span class="muted small" id="eCount"></span>
        <button class="btn" id="eCsv" type="button">Download catalogue (CSV)</button></div>
        <div class="card" style="padding:0"><div class="list" id="eList"></div></div></section>
    </div>`;
  const facet = (el, key, items, label) => {
    $(el).innerHTML = [["", "All"], ...items.map((x) => [x, label(x)])].map(([k, l]) =>
      `<a href="#" data-k="${esc(k)}" class="${st[key] === k ? "on" : ""}"><span>${esc(l)}</span><span class="muted small">${k ? count({ ...st, [key]: k }) : ""}</span></a>`).join("");
    $$("a", $(el)).forEach((a) => (a.onclick = (e) => { e.preventDefault(); st[key] = a.dataset.k; draw(); }));
  };
  const match = (c, s) => {
    if (s.theme && c.theme !== s.theme) return false;
    if (s.lvl && !c.levels.includes(s.lvl)) return false;
    if (s.pub && !c.publishers.includes(s.pub)) return false;
    if (s.q) { const t = (c.name + " " + c.code + " " + c.definition + " " + c.name_bm + " " + c.source).toLowerCase(); return s.q.toLowerCase().split(/\s+/).every((w) => t.includes(w)); }
    return true;
  };
  const count = (s) => D.cat.filter((c) => match(c, s)).length;
  function draw() {
    const P2 = new URLSearchParams(); Object.entries(st).forEach(([k, x]) => x && P2.set(k, x)); setParams("/explore", P2);
    facet("#fTheme", "theme", themes, themeName);
    facet("#fLvl", "lvl", ["country", "state", "district", "parlimen", "dun"], (l) => LEVELS[l]);
    facet("#fPub", "pub", pubs, (p) => p.toUpperCase());
    const rows = D.cat.filter((c) => match(c, st));
    $("#eCount").textContent = `${rows.length} indicator${rows.length === 1 ? "" : "s"}`;
    $("#eList").innerHTML = rows.map((c) => `
      <a class="item" href="#/explore/${encodeURIComponent(c.code)}${st.lvl ? "?lvl=" + st.lvl : ""}">
        <b>${esc(c.name)}</b><span class="muted small mono">${esc(c.first)}${c.last !== c.first ? "–" + esc(c.last) : ""}</span>
        <div class="meta">${esc(c.definition || "")}</div>
        <div class="meta row" style="gap:6px">${chip(esc(themeName(c.theme)))}${chip(esc(c.unit || "–"))}${c.levels.filter((l) => l !== "unallocated").map((l) => chip(LEVELS[l] || l)).join("")}${c.n_breakdowns > 1 ? chip(c.n_breakdowns + " breakdowns") : ""}${c.publishers.map((p) => chip(p.toUpperCase(), "accent")).join("")}</div>
      </a>`).join("") || `<div class="skel">Nothing matches. Try fewer words, or clear a filter.</div>`;
  }
  $("#eq").oninput = (e) => { st.q = e.target.value; draw(); };
  $("#eCsv").onclick = () => download("catalogue.csv", toCSV(["code", "name", "theme", "unit", "statistic", "first", "last", "levels", "publishers", "observations", "definition"],
    D.cat.map((c) => [c.code, c.name, themeName(c.theme), c.unit, c.statistic, c.first, c.last, c.levels.join(";"), c.publishers.join(";"), c.n, c.definition])));
  draw();
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
  const brks = [...new Set(rows.map((r) => r.breakdown))].sort((a, b) => (a !== "_total") - (b !== "_total") || a.localeCompare(b, "en", { numeric: true }));
  const bases = [...new Set(rows.map((r) => r.basis))];
  const st = {
    b: brks.includes(P.get("b")) ? P.get("b") : brks[0],
    lvl: levels.includes(P.get("lvl")) ? P.get("lvl") : levels.includes("country") ? "country" : levels.includes("state") ? "state" : levels[0],
    geo: (P.get("geo") || "").split(",").filter(Boolean),
    view: P.get("view") || "chart",
    basis: bases.length > 1 ? (P.get("basis") || "") : "",
    ctx: P.get("ctx") ?? "",
  };
  const reg = D.registry.find((r) => r.series_id === (c.source || "").split(":").pop());
  const breaks = D.breaks.filter((b) => code.startsWith(b.indicator_prefix));
  v.innerHTML = `
    <div class="row" style="gap:6px">${chip(esc(themeName(c.theme)))}${c.publishers.map((p) => chip(p.toUpperCase(), "accent")).join("")}${chip(esc(c.unit))}${c.statistic ? chip(esc(c.statistic)) : ""}${c.price_basis ? chip(esc(c.price_basis)) : ""}</div>
    <h1>${esc(c.name)}</h1>
    <p class="lede">${esc(c.definition)}</p>
    <div class="row" style="margin:10px 0 18px">
      <button class="btn" id="dl" type="button">Download CSV</button>
      <button class="btn" id="cite" type="button">Copy citation</button>
      <span class="muted small mono">${esc(code)} · ${NF(0).format(rows.length)} observations · ${esc(c.first)}–${esc(c.last)}</span>
    </div>
    <div class="card" style="padding:12px 14px;margin-bottom:12px"><div class="row" id="ctl" style="gap:14px"></div></div>
    <div class="card"><div id="chartHead" class="row" style="justify-content:space-between;margin-bottom:4px"></div><div class="legend" id="legend"></div><div class="chart" id="chart"></div><div id="chartNotes" class="small muted" style="margin-top:8px"></div></div>
    <div id="tilesBox"></div>
    <h2>The values and where each comes from</h2>
    <div class="row" style="justify-content:space-between;margin-bottom:8px"><span class="small muted" id="tCount"></span></div>
    <div class="tablewrap" id="tbl"></div>
    <div class="grid g2" style="margin-top:18px">
      <div class="card"><h3>About this indicator</h3><table class="small">${kv("Code", `<span class="mono">${esc(code)}</span>`)}${kv("Unit", esc(c.unit))}${kv("Statistic", esc(c.statistic))}${kv("Universe", esc(c.universe))}${kv("Price basis", esc(c.price_basis))}${kv("Adds up across places", c.additive_geo === "true" ? "Yes" : c.additive_geo === "false" ? "No: do not sum places" : "")}${kv("Source dataset", `<span class="mono">${esc(c.source)}</span>`)}${kv("Malay name", esc(c.name_bm))}${kv("Coverage", esc(c.coverage_note))}${reg ? kv("Licence", esc(reg.licence) + (reg.redistribution ? ` · ${esc(reg.redistribution)}` : "")) : ""}</table></div>
      <div class="card"><h3>Caveats that apply</h3><div id="cavs" class="small"></div>${breaks.map((b) => `<div class="note" style="margin-top:8px"><b>Series break from ${esc(b.first_period_new_basis)}.</b> ${esc(b.what_changed)}</div>`).join("")}</div>
    </div>`;

  const P2 = () => { const p = new URLSearchParams(); if (st.b !== brks[0]) p.set("b", st.b); p.set("lvl", st.lvl); if (st.geo.length) p.set("geo", st.geo.join(",")); if (st.view !== "chart") p.set("view", st.view); if (st.basis) p.set("basis", st.basis); if (st.ctx) p.set("ctx", st.ctx); return p; };
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
      <div style="margin-left:auto"><div class="small muted">View</div><div class="seg" id="sView">${["chart", "table"].map((x) => `<button type="button" data-v="${x}" class="${x === st.view ? "on" : ""}">${{ chart: "Chart", table: "Table only" }[x]}</button>`).join("")}</div></div>`;
    $$("#sLvl button").forEach((b) => (b.onclick = () => { st.lvl = b.dataset.v; st.geo = []; st.ctx = ""; draw(); }));
    $$("#sView button").forEach((b) => (b.onclick = () => { st.view = b.dataset.v; draw(); }));
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
    if (st.view !== "table") chart(c, d, sel, st, breaks, nat);
    tiles(c, d, rows, st);
    table(c, d, st.geo.length ? shown : sel);
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
  const lines = [`${geoLabel(p.geo)} · ${p.period}`, `${exact(p.value)} ${c.unit}`, `${BASIS[p.basis] || p.basis} · ${ed.id || ""}`,
    `${ci.table || ""}${ci.pdf_page ? " · pdf p" + ci.pdf_page : ""}${ci.printed_page ? " (printed " + ci.printed_page + ")" : ""}`];
  if (p.ci_low != null) lines.push(`95% interval ${exact(p.ci_low)} – ${exact(p.ci_high)}`);
  if (p.reliability && p.reliability !== "unknown") lines.push(`Reliability: ${p.reliability}`);
  if (p.others?.length) lines.push(`Also printed: ${p.others.map((o) => exact(o.value) + " (" + (d.editions[o.edition]?.id || "") + ")").join("; ")}`);
  if (p.main) lines.push(`Main line uses ${exact(p.main.value)} (${d.editions[p.main.edition]?.id || ""})`);
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
  const allPts = [...series, ...context, ...natS].flatMap((s) => s.pts);
  const head = $("#chartHead");
  if (!allPts.length) { el.innerHTML = `<div class="skel">No values for this selection. Try another breakdown or level.</div>`; $("#legend").innerHTML = ""; head.innerHTML = ""; $("#chartNotes").innerHTML = ""; return; }
  const vals = allPts.map((p) => p.value).filter((x) => typeof x === "number");
  const nonneg = vals.every((x) => x >= 0);
  const zero = nonneg && !["rate", "index", "ratio"].includes(c.statistic) && c.unit !== "index" || (c.unit === "percent" && c.statistic === "share");
  const monthly = isMonthly(allPts[0].period);
  const single = new Set(allPts.map((p) => p.period)).size === 1;
  head.innerHTML = `<div><b>${esc(brkLabel(st.b))}</b> <span class="muted small">· ${esc(c.unit)}${st.lvl !== "country" ? " · " + LEVELS[st.lvl] : ""}</span></div><span class="muted small">${zero ? "Axis starts at zero" : "Axis fitted to the data (not from zero)"}</span>`;
  $("#legend").innerHTML = series.map((s) => `<span><i style="background:${s.color}"></i>${esc(s.label)}</span>`).join("") + (natS.length ? `<span><i style="background:var(--text);height:2px;border-top:1px dashed var(--text)"></i>Malaysia (reference)</span>` : "") + (context.length ? `<span><i style="background:var(--line-2)"></i>${context.length} other places (context)</span>` : "");

  const marks = [];
  const W = el.clientWidth || 900;
  if (single) {
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
  if (zero) marks.push(Plot.ruleY([0], { stroke: css("--line-2") }));
  const tipPts = [...(series.length ? series : context), ...natS].flatMap((s) => s.pts);
  marks.push(Plot.tip(tipPts, Plot.pointer({ x: (p) => pdate(p.period), y: "value", title: (p) => tipText(c, d, p), fontSize: 12, fill: css("--panel"), stroke: css("--line-2") })));
  marks.push(Plot.dot(tipPts, Plot.pointer({ x: (p) => pdate(p.period), y: "value", r: 5, fill: "none", stroke: css("--text"), strokeWidth: 1.5 })));
  el.innerHTML = "";
  el.append(Plot.plot({
    width: W, height: Math.min(440, Math.max(300, W * 0.42)), marginLeft: 64, marginRight: 18, marginTop: 22,
    style: { background: "transparent", fontSize: "12px", color: css("--text-2") },
    x: { type: "utc", label: null, grid: false }, y: { grid: true, zero, label: unitShort(c.unit), tickFormat: (x) => compact(x, c.unit) }, marks,
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
    const pick = (g) => { const xs = sel.filter((r) => r.geo === g && r.period === per); xs.sort((a, b) => String(d.editions[b.edition]?.vintage).localeCompare(String(d.editions[a.edition]?.vintage))); return xs[0]; };
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
      return `<a class="tile" href="#/state/${g}" title="${esc(geoName(g))}: ${r ? exact(r.value) + " " + esc(c.unit) : "not published"}" style="grid-column:${x + 1};grid-row:${y + 1};background:${fill[k]};${k === "na" ? "border-style:dashed;" : ""}color:var(--text)"><b>${ab}</b><span>${r ? compact(r.value, c.unit) : "–"}</span></a>`;
    }).join("");
    box.innerHTML = `<h2>States in ${esc(per)}, against Malaysia</h2>
      <div class="card"><div class="row" style="justify-content:space-between;margin-bottom:10px">
        <div class="legend" style="margin:0"><span><i style="background:color-mix(in srgb, var(--s1) 50%, var(--panel));height:10px"></i>above Malaysia</span><span><i style="background:var(--line-2);height:10px"></i>about the same</span><span><i style="background:color-mix(in srgb, var(--s2) 50%, var(--panel));height:10px"></i>below Malaysia</span></div>
        ${periods.length > 1 ? `<select id="tp">${periods.map((p) => `<option ${p === per ? "selected" : ""}>${esc(p)}</option>`).join("")}</select>` : ""}</div>
        <div class="tiles" style="grid-template-columns:repeat(7,1fr);max-width:640px">${cells}</div>
        <p class="small muted" style="margin:10px 0 0">${nat ? `Malaysia: <b>${exact(nat.value)}</b> ${esc(c.unit)}. "About the same" is within ${band != null ? "1 percentage point" : "5%"} of Malaysia${stRows.some((r) => r.ci_low != null) ? ", or where the confidence intervals overlap" : ""}: a band, not a ranking. Higher is not always better: read the indicator.` : "Malaysia's own figure is not published for this period, so states are not banded."} ${counts.hi} above, ${counts.eq} about the same, ${counts.lo} below${counts.na ? `, ${counts.na} not published` : ""}. Click a state for its profile.</p></div>`;
    $("#tp") && ($("#tp").onchange = (e) => { per = e.target.value; render(); });
  };
  render();
}

function table(c, d, sel) {
  const rs = [...sel].sort((a, b) => geoLabel(a.geo).localeCompare(geoLabel(b.geo)) || pdate(b.period) - pdate(a.period));
  const lim = 400;
  $("#tCount").textContent = `${NF(0).format(rs.length)} rows${rs.length > lim ? `, first ${lim} shown (download for all)` : ""}`;
  $("#tbl").innerHTML = `<table><thead><tr><th>Place</th><th>Period</th><th class="n">Value (as printed)</th><th>Basis</th><th>Edition</th><th>Table · page</th><th>Source row (L1)</th><th>Caveats</th></tr></thead><tbody>
    ${rs.slice(0, lim).map((r) => { const ci = d.cites[r.cite] || {}; return `<tr><td>${esc(geoLabel(r.geo))}</td><td class="mono">${esc(r.period)}</td><td class="n">${exact(r.value)}${r.ci_low != null ? `<div class="small muted">${exact(r.ci_low)}–${exact(r.ci_high)}</div>` : ""}${r.reliability === "low" ? `<div>${chip("low reliability", "warn")}</div>` : ""}</td><td class="small">${esc(BASIS[r.basis] || r.basis)}</td><td class="small mono">${esc(d.editions[r.edition]?.id || "")}</td><td class="small">${esc(ci.table || "")}${ci.pdf_page ? ` · p${esc(ci.pdf_page)}` : ""}${ci.printed_page ? ` <span class="muted">(${esc(ci.printed_page)})</span>` : ""}<div class="mono muted" title="file sha256">${esc((ci.sha256 || "").slice(0, 12))}</div></td><td class="small mono">${l1link(r.l1_ref)}</td><td>${(r.caveats || "").split(";").filter(Boolean).map((k) => `<span class="chip warn" title="${esc(D.caveats[k] || "")}">${esc(k)}</span>`).join(" ")}</td></tr>`; }).join("")}
  </tbody></table>`;
}
function l1link(ref) {
  if (!ref) return "";
  const m = /^(sources\/[^#]+?)(?:#row(\d+))?(?:\s|$)/.exec(ref);
  return m ? `<a href="${REPO}/blob/main/${esc(m[1])}${m[2] ? "#L" + (+m[2] + 1) : ""}" target="_blank" rel="noopener">${esc(ref)}</a>` : esc(ref);
}

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
    <p class="lede">Each view compares two things that should line up: a plan and its outcome, a budget and its spending, need and money, what one institution reports and what another audited. Ask a question, or start from one below.</p>
    <div class="card" style="margin:18px 0;padding:14px"><input type="search" id="gq" placeholder="Ask, e.g. “was the education budget spent?”, “poverty in Kelantan”, “PFI”" style="width:100%;font-size:15px;padding:10px 12px"><div id="gans" style="margin-top:10px"></div></div>
    <div class="grid g3" id="gcards">${QUESTIONS.map(([q, name]) => { const g = D.gaps.find((x) => x.name === name); return g ? `<a class="card link" href="#/gaps/${name}"><div class="small muted">${esc(g.title)}</div><h3 style="margin:4px 0 8px;font-size:15px">${esc(q)}</h3><div class="small muted">${NF(0).format(g.n)} rows · open the analysis →</div></a>` : ""; }).join("")}</div>
    <div class="note info" style="margin-top:18px">Every view follows a method declared before its results were seen, runs for all states and Federal Territories, and keeps the sources' own figures. The plain-language reading at the top of each view is generated by fixed rules from the rows below it, not written by hand.</div>`;
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
    const big = [...under].sort((a, b) => b.unspent_rm - a.unspent_rm).slice(0, 3);
    return `In <b>${f.year}</b>, ${held.length} ministries and bodies had a ${this.flowLabel[f.flow].toLowerCase()} allocation and an audited actual. Together they spent <b>${compact(act, "RM")}</b> of <b>${compact(est, "RM")}</b> allocated (<b>${pct(act / est)}</b>). <b>${under.length}</b> spent less than their allocation by the view's threshold and <b>${over.length}</b> spent more.${big.length ? ` The largest amounts left unspent: ${big.map((r) => `${esc(r.body)} (${compact(r.unspent_rm, "RM")}, ${pct(r.execution_rate)} spent)`).join("; ")}.` : ""}`;
  },
  chart(rs) {
    const h = rs.filter((r) => r.execution_rate != null).sort((a, b) => a.execution_rate - b.execution_rate);
    if (!h.length) return null;
    return Plot.plot({ height: Math.max(240, h.length * 17 + 40), marginLeft: 260, x: { label: "Share of allocation spent (audited)", tickFormat: (x) => pct(x, 0), grid: true },
      y: { label: null, domain: h.map((r) => r.body) },
      marks: [Plot.ruleX([1], { stroke: css("--text-3"), strokeDasharray: "3,3" }), Plot.barX(h, { x: "execution_rate", y: "body", fill: (r) => (r.status === "underspent" ? css("--s2") : r.status === "overspent" ? css("--s3") : css("--s1")), title: (r) => `${r.body}\nallocation ${exact(r.estimate_revised_pkkp)}\naudited actual ${exact(r.actual_audited)}\n${pct(r.execution_rate)} spent · ${statusText(r.status)}` }), Plot.tip(h, Plot.pointerY({ x: "execution_rate", y: "body", title: (r) => `${r.body}\nallocation RM ${exact(r.estimate_revised_pkkp)}\naudited actual RM ${exact(r.actual_audited)}\n${pct(r.execution_rate)} spent · ${statusText(r.status)}` }))] });
  },
  legend: [["--s1", "within the allocation"], ["--s2", "underspent"], ["--s3", "overspent"]],
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
    return `For <b>${f.year}</b>, leaving out the contingency reserve (P.70), Parliament was tabled <b>${compact(tab, "RM")}</b> for development projects; the audited accounts show an allocation of <b>${compact(alloc, "RM")}</b> and spending of <b>${compact(act, "RM")}</b> (<b>${pct(act / alloc)}</b> of the allocation). <b>${zero.length}</b> projects had an allocation and spent nothing; <b>${under.length}</b> spent markedly less than allocated. Tabled and allocated differ because allocations are revised during the year (supplementary supply, virement).`;
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
    return `In <b>${last}</b>, federal debt stood at <b>${compact(debt?.amount_rm, "RM")}</b>${debt?.growth != null ? `, up ${pct(debt.growth)} on the year` : ""}. Beside it, outside the debt figure: ${ly.map((r) => `${esc(r.instrument_label)} <b>${compact(r.amount_rm, "RM")}</b> (${r.growth != null ? (r.growth >= 0 ? "+" : "") + pct(r.growth) : "growth n/a"}, ${statusText(r.status).toLowerCase()})`).join("; ")}. Deposit and contributor guarantees (EPF, Tabung Haji and others) are savings guaranteed by statute, not borrowing, and are never added to debt.`;
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
    return Plot.plot({ height: 40 + h.length * 17, marginLeft: 330, x: { label: "Outcome ÷ target", grid: true, type: "log", tickFormat: (x) => NF(2).format(x) }, y: { label: null, domain: h.map((r) => r.lab) },
      marks: [Plot.ruleX([1], { stroke: css("--text-3"), strokeDasharray: "3,3" }), Plot.ruleY(h, { x1: 1, x2: "ratio", y: "lab", stroke: css("--line-2") }), Plot.dot(h, { x: "ratio", y: "lab", fill: (r) => (r.ratio >= 1 ? css("--s1") : css("--s2")), r: 4 }),
        Plot.tip(h, Plot.pointerY({ x: "ratio", y: "lab", title: (r) => `${r.lab}\ntarget ${exact(r.target)}\noutcome ${exact(r.outcome)}\n${r.outcome_source}` }))] });
  },
  legend: [["--s1", "outcome at or above target"], ["--s2", "outcome below target"]],
  table: ["indicator_code", "geo_code", "breakdown_key", "target_line", "target", "outcome", "outcome_source", "difference", "ratio", "status", "note"],
};
G.gap_need_vs_money = {
  filters: (rs) => ({ year: years(rs.filter((r) => r.state_gov_expenditure_per_capita_rm != null)) }),
  rows: (rs, f) => rs.filter((r) => r.year === f.year),
  read(rs, f) {
    const h = rs.filter((r) => r.state_gov_expenditure_per_capita_rm != null && r.poverty_absolute_rate != null);
    const fed = rs.find((r) => r.federal_placed_share != null);
    return `For <b>${f.year}</b>, <b>${h.length}</b> states have both an absolute poverty rate and a state government spending figure. The chart sets each state's own government spending per person against its poverty rate: if money followed need, the points would rise to the right. This is the state governments' own money only.${fed ? ` Federal spending by state is withheld: only <b>${pct(fed.federal_placed_share)}</b> of federal spending in ${f.year} can be placed in a state from the federal accounts (guard: 60%).` : ""}`;
  },
  chart(rs) {
    const h = rs.filter((r) => r.state_gov_expenditure_per_capita_rm != null && r.poverty_absolute_rate != null);
    return Plot.plot({ height: 380, marginLeft: 70, grid: true, x: { label: "Absolute poverty rate (%)", zero: true }, y: { label: "State government spending per person (RM)", zero: true, tickFormat: (x) => NF(0).format(x) },
      marks: [Plot.dot(h, { x: "poverty_absolute_rate", y: "state_gov_expenditure_per_capita_rm", r: 5, fill: css("--s1"), fillOpacity: 0.85 }), Plot.text(h, { x: "poverty_absolute_rate", y: "state_gov_expenditure_per_capita_rm", text: "state", dy: -9, fontSize: 11, fill: css("--text-2") }),
        Plot.tip(h, Plot.pointer({ x: "poverty_absolute_rate", y: "state_gov_expenditure_per_capita_rm", title: (r) => `${r.state} · ${r.year}\npoverty ${exact(r.poverty_absolute_rate)}%\nmedian income RM ${exact(r.income_median_rm)}\nstate spending RM ${exact(r.state_gov_expenditure_rm)} (${r.state_gov_expenditure_basis})\nper person RM ${exact(r.state_gov_expenditure_per_capita_rm)}` }))] });
  },
  table: ["state", "population", "poverty_absolute_rate", "income_median_rm", "gini", "unemployment_rate", "state_gov_expenditure_rm", "state_gov_expenditure_basis", "state_gov_expenditure_per_capita_rm", "state_gov_receipts_per_capita_rm", "verification_tier", "coverage_note"],
};
G.gap_federal_vs_state = {
  filters: (rs) => ({ transfer: [...new Set(rs.map((r) => r.transfer))], year: years(rs) }),
  transferLabel: { capitation: "Capitation grant", concurrent_list: "Concurrent-list grant", named: "Grants to a named state", loans: "Federal loans to states" },
  rows: (rs, f) => rs.filter((r) => r.transfer === f.transfer && r.year === f.year),
  read(rs, f, all) {
    const t = all.filter((r) => r.transfer === f.transfer);
    const cmp = t.filter((r) => ["agree", "differ", "consistent", "agree_after_other_lenders"].includes(r.status));
    const dif = t.filter((r) => r.status === "differ");
    return `For the <b>${(this.transferLabel[f.transfer] || f.transfer).toLowerCase()}</b>, <b>${cmp.length}</b> state-years could be compared (the federal figure and the state's own printed figure both held): <b>${cmp.length - dif.length}</b> agree or are consistent and <b>${dif.length}</b> differ. The rest cannot yet be compared, for the reason shown in each row (the state did not print it, its volume is not held, or a Federal Territory has no state government). Shown: ${f.year}.`;
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
  if (/(rate|share|growth|ratio)$/.test(k) && typeof v === "number" && !/poverty|unemployment|pp$/.test(k) && Math.abs(v) < 20 && k !== "ratio_to_debt") return pct(v);
  if (/_ref$/.test(k)) return `<span class="mono small">${l1link(v)}</span>`;
  if (typeof v === "number") return NF(2).format(v);
  return esc(v);
}
const colLabel = (k) => k.replace(/_rm$/, " (RM)").replace(/_/g, " ").replace(/\bpkkp\b/g, "PKKP").replace(/\bbnm\b/g, "BNM").replace(/\bmof\b/g, "MOF").replace(/^./, (x) => x.toUpperCase());

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
  const qs = QUESTIONS.find((q) => q[1] === name);
  const cavs = [...new Set(all.flatMap((r) => String(r.caveats || "").split(";").filter(Boolean)))].sort();
  v.innerHTML = `<div class="row">${chip("Gap view", "accent")}${chip(`<span class="mono">${esc(name)}</span>`)}</div>
    <h1>${esc(qs ? qs[0] : g.question)}</h1><p class="lede">${esc(g.title)}: ${esc(g.question)}</p>
    <div class="card" style="padding:12px 14px;margin:16px 0 12px"><div class="row" id="gf" style="gap:14px"></div></div>
    <div class="answer"><div class="small muted" style="margin-bottom:6px">What the rows say</div><div class="finding" id="read"></div>
      <div class="row" style="margin-top:12px"><button class="btn" id="brief" type="button">Copy as brief</button><button class="btn" id="gcsv" type="button">Download rows (CSV)</button><a class="btn" href="${REPO}/blob/main/core/${name}.csv" target="_blank" rel="noopener">Source table on GitHub</a></div></div>
    <div class="card" style="margin-top:14px"><div class="legend" id="glegend"></div><div class="chart" id="gchart"></div></div>
    <h2>The rows</h2><div class="small muted" id="gcount" style="margin-bottom:8px"></div><div class="tablewrap" id="gtbl"></div>
    ${cavs.length ? `<h2>Caveats</h2><div class="grid g2">${cavs.map((k) => `<div class="note"><b>${esc(k)}</b> ${esc(D.caveats[k] || "")}</div>`).join("")}</div>` : ""}`;
  const label = (k, x) => (k === "flow" ? cfg.flowLabel[x] : k === "transfer" ? cfg.transferLabel[x] : k === "status" ? (x ? statusText(x) : "All") : x);
  function draw() {
    const p = new URLSearchParams(Object.entries(f).filter(([, x]) => x)); setParams("/gaps/" + name, p);
    $("#gf").innerHTML = Object.entries(opts).map(([k, list]) => list.length <= 4 ? `<div><div class="small muted">${colLabel(k)}</div><div class="seg">${list.map((x) => `<button type="button" data-k="${k}" data-v="${esc(x)}" class="${f[k] === x ? "on" : ""}">${esc(label(k, x))}</button>`).join("")}</div></div>`
      : `<div><div class="small muted">${colLabel(k)}</div><select data-k="${k}">${list.map((x) => `<option value="${esc(x)}" ${f[k] === x ? "selected" : ""}>${esc(label(k, x))}</option>`).join("")}</select></div>`).join("") || `<span class="small muted">All years and series are shown.</span>`;
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
    $("#gcount").textContent = `${NF(0).format(rs.length)} rows${rs.length > 500 ? ", first 500 shown (download for all)" : ""} · all ${NF(0).format(all.length)} rows are in the CSV`;
    $("#gtbl").innerHTML = `<table><thead><tr>${tc.map((k) => `<th class="${typeof rs[0]?.[k] === "number" ? "n" : ""}">${esc(colLabel(k))}</th>`).join("")}</tr></thead><tbody>${sorted.slice(0, 500).map((r) => `<tr>${tc.map((k) => `<td class="${typeof r[k] === "number" ? "n" : ""} ${k === "note" ? "small muted" : ""}" ${k === "note" ? 'style="min-width:280px"' : ""}>${cellFmt(k, r[k])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    $("#brief").onclick = () => {
      const txt = $("#read").innerText;
      copy(`${qs ? qs[0] : g.question}\n\n${txt}\n\nSource: Malaysia Economy Data Warehouse (IKRAM), gap view ${name}, release ${D.meta.release_id}${Object.keys(f).length ? " (" + Object.entries(f).filter(([, x]) => x).map(([k, x]) => `${k} ${x}`).join(", ") + ")" : ""}. Rows and citations: ${location.href}\n${cavs.length ? "Caveats: " + cavs.map((k) => `${k} ${D.caveats[k] || ""}`).join(" ") : ""}`, "Brief copied, with its source");
    };
    $("#gcsv").onclick = () => download(`${name}.csv`, toCSV(d.cols, d.rows));
  }
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
    ...[["About", "#/about"], ["Explore data", "#/explore"], ["Policy gaps", "#/gaps"], ["States", "#/states"], ["Sources & caveats", "#/sources"], ["Method & trust", "#/method"]].map(([t, h]) => ["Page", h, t, ""]),
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
