/* core.js - helpers, icons, app shell, router, toasts, charts. No dependencies. */
"use strict";

// ---------- helpers ---------------------------------------------------------------
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const view = $("#view");
const tooltip = $("#tooltip");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (v, d = 1) => (v == null || Number.isNaN(Number(v)) ? "–" : Number(v).toFixed(d));
const sgn = (v, d = 2) => (v == null || Number.isNaN(Number(v)) ? "–" : (v > 0 ? "+" : "") + Number(v).toFixed(d) + "%");
const fmtInt = (v) => (v == null ? "–" : Number(v).toLocaleString());
const METHOD = { bo: "Bayesian Optimization", random: "Random search" };
const SHORT = { bo: "BO", random: "Random" };

function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
function palette() { return { bo: css("--bo"), random: css("--rnd"), lvl: css("--lvl"), good: css("--good"), bad: css("--bad"), ink3: css("--ink-3"), brand: css("--brand"), surface3: css("--surface-3") }; }

async function api(path, opts) {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `${r.status} ${r.statusText}`);
  return j;
}
const post = (path, body) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });

let INFO = null;
async function info(force) { if (!INFO || force) INFO = await api("/api/info"); return INFO; }

let timers = [];
const clearTimers = () => { timers.forEach(clearInterval); timers = []; };
function every(ms, fn) { fn(); timers.push(setInterval(fn, ms)); }
function query() { const q = location.hash.split("?")[1] || ""; return Object.fromEntries(new URLSearchParams(q)); }

// ---------- icons (24x24 stroke) --------------------------------------------------
const ICON_PATHS = {
  dashboard: "M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z",
  play: "M7 4.5v15l12-7.5z",
  duel: "M3 17l5-6 4 3 8-9M3 21h18",
  verify: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM8.5 12l2.5 2.5 4.5-5",
  history: "M12 7v5l3 2M3.5 12a8.5 8.5 0 1 0 2.5-6M3 4v4h4",
  grid: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
  layers: "M12 3l9 5-9 5-9-5zM3 13l9 5 9-5M3 17.5l9 5 9-5",
  bulb: "M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.7.6 1.1 1.4 1.1 2.2h5c0-.8.4-1.6 1.1-2.2A6 6 0 0 0 12 3z",
  sliders: "M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0M14 4v4M8 10v4M16 16v4",
  star: "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z",
  database: "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
  chart: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  doc: "M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6",
  code: "M8 6l-6 6 6 6M16 6l6 6-6 6",
  sun: "M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10z",
  moon: "M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z",
  download: "M12 3v12M7 10l5 5 5-5M4 21h16",
  x: "M6 6l12 12M18 6L6 18",
  info: "M12 8h0M11 12h1v5h1M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
  warn: "M12 9v4M12 17h0M10.3 3.9 2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
  cpu: "M7 7h10v10H7zM9 3v4M15 3v4M9 17v4M15 17v4M3 9h4M3 15h4M17 9h4M17 15h4",
  target: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM12 11a1 1 0 1 0 0 2 1 1 0 0 0 0-2z",
  bolt: "M13 2L4 14h7l-1 8 9-12h-7z",
  hash: "M5 9h14M5 15h14M10 3 8 21M16 3l-2 18",
  scale: "M12 3v18M5 7h14M7 7l-3 7a3 3 0 0 0 6 0zM17 7l-3 7a3 3 0 0 0 6 0z",
  shuffle: "M16 3h5v5M4 20 21 3M21 16v5h-5M15 15l6 6M4 4l5 5",
  check: "M5 12l5 5L20 7",
  file: "M7 3h7l5 5v13H7zM14 3v5h5",
  users: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
  server: "M3 4h18v7H3zM3 13h18v7H3zM7 7.5h0M7 16.5h0",
  monitor: "M3 4h18v12H3zM8 20h8M12 16v4",
  gauge: "M12 14l4-4M3.5 17a9 9 0 1 1 17 0",
};
function icon(name, extra = "") {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" ${extra} aria-hidden="true"><path d="${ICON_PATHS[name] || ""}"/></svg>`;
}

// ---------- badges, blocks ---------------------------------------------------------
function chip(text, cls) { return `<span class="chip ${esc(cls ?? String(text).toLowerCase())}">${esc(text)}</span>`; }
function statusChip(s) {
  if (s === "OK") return chip("OK", "ok");
  if (/ERROR|TIMEOUT|CRASH|WRONG/.test(s || "")) return chip(s.replace("_", " ").toLowerCase(), "bad");
  return chip(s);
}
function methodChip(m) { return chip(SHORT[m] || m, m); }
function progress(done, total) { const p = total ? Math.min(100, (100 * done) / total) : 0; return `<div class="progress" title="${done}/${total}"><div style="width:${p}%"></div></div>`; }
function diffHtml(diff) {
  if (!diff) return "";
  return esc(diff).split(" ").map((t) => (t.startsWith("+") ? `<span class="diff-on">${t}</span>` : t.startsWith("-") ? `<span class="diff-off">${t}</span>` : t)).join(" ");
}
function notice(kind, html) { const ic = { warn: "warn", info: "info", ok: "check", err: "warn" }[kind] || "info"; return `<div class="notice ${kind}">${icon(ic)}<div>${html}</div></div>`; }
function errorBox(e) { return `<div class="notice err">${esc(e.message || e)}</div>`; }
// The first argument (a section label) is kept for call compatibility but no longer
// rendered: the sidebar and breadcrumb already say where you are.
function pageHead(_section, title, lead, actions = "") {
  return `<div class="page-head"><div><h1>${title}</h1>${lead ? `<p class="lead">${lead}</p>` : ""}</div>${actions ? `<div class="actions">${actions}</div>` : ""}</div>`;
}
function card(title, body, { sub = "", right = "", flush = false, id = "" } = {}) {
  return `<section class="card" ${id ? `id="${id}"` : ""}>${title ? `<div class="card-head"><h2>${title}</h2>${sub ? `<span class="sub">${sub}</span>` : ""}${right ? `<div class="right">${right}</div>` : ""}</div>` : ""}<div class="card-body ${flush ? "flush" : ""}">${body}</div></section>`;
}
/** Metric card. Values stay in neutral ink; colour is reserved for charts and status. */
function kpi(label, value, sub, ic) {
  return `<div class="stat"><div class="stat-top"><span>${esc(label)}</span>${ic ? `<span class="stat-ic">${icon(ic)}</span>` : ""}</div><div class="stat-val">${value}</div>${sub ? `<div class="stat-sub">${sub}</div>` : ""}</div>`;
}
function emptyState(text, ic = "info") { return `<div class="empty">${icon(ic)}${text}</div>`; }
function sweepNotice() {
  if (INFO && !INFO.compiler_ok) return notice("warn", `<b>GCC was not found</b> (compiler: <code>${esc(INFO.compiler)}</code>, ${esc(INFO.compiler_version)}). Results and docs work, but new optimizations need real GCC. On macOS run <code>brew install gcc</code>, then restart the app.`);
  return INFO && INFO.sweep_running ? notice("warn", "<b>The study sweep is running on this machine.</b> Jobs started here would compete with it for the CPU and disturb both sets of timings. For clean demo numbers, wait until it finishes.") : "";
}
function attachTips(root) {
  $$("[data-tip]", root).forEach((n) => {
    n.addEventListener("mousemove", (e) => { tooltip.innerHTML = n.dataset.tip; tooltip.style.display = "block"; const x = Math.min(e.clientX + 14, window.innerWidth - 400); tooltip.style.left = x + "px"; tooltip.style.top = e.clientY + 14 + "px"; });
    n.addEventListener("mouseleave", () => (tooltip.style.display = "none"));
  });
}

// ---------- toasts & job watcher ---------------------------------------------------
function toast(title, body, kind = "") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `<b>${esc(title)}</b>${body}`;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), 7000);
}
let lastJobs = null;
async function watchJobs() {
  const foot = $("#side-foot");
  try {
    const jobs = await api("/api/jobs");
    const running = jobs.filter((j) => j.status === "running").length, queued = jobs.filter((j) => j.status === "queued").length;
    foot.innerHTML = running || queued ? `<span class="dot busy"></span>${running} running · ${queued} queued` : `<span class="dot"></span>Server ready · idle`;
    if (lastJobs) {
      for (const j of jobs) {
        const before = lastJobs[j.id];
        if (before && ["queued", "running"].includes(before) && !["queued", "running"].includes(j.status)) {
          const link = j.type === "search" ? `#/run/web/${j.exp_id}` : `#/compare/${j.id}`;
          const what = j.type === "search" ? `${SHORT[j.params.method]} search on <b>${esc(j.params.bench)}</b>` : `Comparison on <b>${esc(j.params.bench)}</b>`;
          const best = j.summary && j.summary.best_pct_faster_than_O3 != null ? ` · best ${sgn(j.summary.best_pct_faster_than_O3)}` : "";
          toast(j.status === "done" ? "Job finished" : `Job ${j.status}`, `${what}${best}. <a href="${link}">Open →</a>`, j.status === "done" ? "ok" : "bad");
        }
      }
    }
    lastJobs = Object.fromEntries(jobs.map((j) => [j.id, j.status]));
  } catch { foot.innerHTML = `<span class="dot off"></span>Server offline`; }
}

// ---------- shell: nav, theme, router ----------------------------------------------
const NAV = [
  ["", [["dashboard", "Overview", "#/", "dashboard"]]],
  ["Workspace", [["optimize", "Optimize", "#/optimize", "play"], ["duel", "Compare methods", "#/duel", "duel"], ["verify", "Benchmarks", "#/verify", "verify"], ["history", "Runs", "#/history", "history"], ["programs", "Programs", "#/programs", "code"]]],
  ["Insights", [["results", "Results", "#/results", "chart"], ["space", "Search space", "#/space", "grid"], ["data", "Datasets", "#/data", "database"]]],
  ["Docs", [["learn", "How it works", "#/learn", "bulb"], ["architecture", "Architecture", "#/architecture", "layers"], ["parameters", "Parameters", "#/parameters", "sliders"], ["novelty", "Contributions", "#/novelty", "star"], ["manuscript", "Paper", "#/manuscript", "doc"]]],
];
function renderNav(active) {
  $("#nav").innerHTML = NAV.map(([g, items]) => (g ? `<div class="nav-group">${g}</div>` : "") + items.map(([k, label, href, ic]) => `<a href="${href}" class="${k === active ? "active" : ""}">${icon(ic)}${label}</a>`).join("")).join("");
}
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem("bo-theme", t); } catch {}
  $("#theme").innerHTML = icon(t === "dark" ? "sun" : "moon");
}
$("#theme").addEventListener("click", () => { setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"); route(); });

const ROUTES = [];
function addRoute(re, fn, nav, crumb, detail = false) { ROUTES.push({ re, fn, nav, crumb, detail }); }
async function route() {
  clearTimers();
  tooltip.style.display = "none";
  const h = location.hash.split("?")[0] || "#/";
  for (const r of ROUTES) {
    const m = h.match(r.re);
    if (m) {
      renderNav(r.nav);
      const group = NAV.find(([, items]) => items.some((i) => i[0] === r.nav));
      const item = group && group[1].find((i) => i[0] === r.nav);
      const label = item ? item[1] : r.crumb;
      const detail = r.detail ? ` / <b>${esc(r.crumb)}</b>` : "";
      $("#crumbs").innerHTML = (group && group[0] ? `${esc(group[0])} / ` : "") + (detail ? `${esc(label)}${detail}` : `<b>${esc(label)}</b>`);
      $("#top-new").style.display = r.nav === "optimize" && !r.detail ? "none" : "";
      view.innerHTML = `<div class="skeleton"></div><div class="skeleton" style="height:260px"></div>`;
      try { await info(true); await r.fn(...m.slice(1)); } catch (e) { view.innerHTML = errorBox(e); }
      window.scrollTo(0, 0);
      return;
    }
  }
  location.hash = "#/";
}
window.addEventListener("hashchange", route);

// ---------- charts ------------------------------------------------------------------
function niceTicks(min, max, n = 5) {
  const span = max - min || 1, step0 = span / n, mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= n) || 10 * mag;
  const out = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}

/** lines: [{color, data:[[x,y]], dash, width}], bands: [{color, data:[[x,lo,hi]]}],
 *  points: [{x,y,color,hollow,cross,r,tip}], refLines: [{y,label}] */
function drawChart(el, { lines = [], bands = [], points = [], refLines = [], xLabel = "", yLabel = "", xMin = 0, xMax, yMin, yMax, zero = true, height = 300, step = false }) {
  const W = 880, H = height, L = 60, R = 18, T = 14, B = 46;
  const ys = [...lines.flatMap((s) => s.data.map((d) => d[1])), ...bands.flatMap((b) => b.data.flatMap((d) => [d[1], d[2]])), ...points.map((p) => p.y), ...refLines.map((r) => r.y)].filter((v) => v != null && isFinite(v));
  const xs = [...lines.flatMap((s) => s.data.map((d) => d[0])), ...points.map((p) => p.x)];
  if (zero) ys.push(0);
  if (!ys.length) { el.innerHTML = emptyState("No data yet"); return; }
  let y0 = yMin ?? Math.min(...ys), y1 = yMax ?? Math.max(...ys);
  const pad = (y1 - y0) * 0.08 || 1; if (yMin == null) y0 -= pad; if (yMax == null) y1 += pad;
  const x1 = xMax ?? Math.max(1, ...xs);
  const X = (v) => L + ((v - xMin) / (x1 - xMin || 1)) * (W - L - R);
  const Y = (v) => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(yLabel)}">`;
  for (const t of niceTicks(y0, y1, 6)) s += `<line class="gridline" x1="${L}" x2="${W - R}" y1="${Y(t)}" y2="${Y(t)}"/><text class="tick" x="${L - 9}" y="${Y(t) + 4}" text-anchor="end">${t}</text>`;
  for (const t of niceTicks(xMin, x1, 10)) s += `<text class="tick" x="${X(t)}" y="${H - B + 18}" text-anchor="middle">${t}</text>`;
  if (zero && y0 < 0 && y1 > 0) s += `<line class="zero" x1="${L}" x2="${W - R}" y1="${Y(0)}" y2="${Y(0)}"/>`;
  for (const r of refLines) s += `<line x1="${L}" x2="${W - R}" y1="${Y(r.y)}" y2="${Y(r.y)}" stroke="${r.color || css("--ink-3")}" stroke-dasharray="5 4"/><text class="tick" x="${W - R}" y="${Y(r.y) - 5}" text-anchor="end">${esc(r.label || "")}</text>`;
  s += `<text class="axis-label" x="${(L + W - R) / 2}" y="${H - 6}" text-anchor="middle">${esc(xLabel)}</text>`;
  s += `<text class="axis-label" transform="translate(15 ${(T + H - B) / 2}) rotate(-90)" text-anchor="middle">${esc(yLabel)}</text>`;
  for (const b of bands) {
    if (!b.data.length) continue;
    const top = b.data.map((d, i) => `${i ? "L" : "M"}${X(d[0]).toFixed(1)} ${Y(d[2]).toFixed(1)}`).join("");
    const bot = [...b.data].reverse().map((d) => `L${X(d[0]).toFixed(1)} ${Y(d[1]).toFixed(1)}`).join("");
    s += `<path d="${top}${bot}Z" fill="${b.color}" opacity="0.14"/>`;
  }
  for (const ln of lines) {
    if (!ln.data.length) continue;
    let d = "";
    ln.data.forEach((p, i) => {
      if (i && (ln.step ?? step)) d += `H${X(p[0]).toFixed(1)}V${Y(p[1]).toFixed(1)}`;
      else d += `${i ? "L" : "M"}${X(p[0]).toFixed(1)} ${Y(p[1]).toFixed(1)}`;
    });
    s += `<path d="${d}" fill="none" stroke="${ln.color}" stroke-width="${ln.width || 2.4}" ${ln.dash ? 'stroke-dasharray="6 5"' : ""} stroke-linejoin="round" stroke-linecap="round"/>`;
  }
  points.forEach((p, i) => {
    const cx = X(p.x), cy = Y(p.y);
    const tip = p.tip ? `data-tip="${esc(p.tip)}"` : "";
    if (p.cross) s += `<g ${tip}><path d="M${cx - 5} ${cy - 5}L${cx + 5} ${cy + 5}M${cx + 5} ${cy - 5}L${cx - 5} ${cy + 5}" stroke="${p.color}" stroke-width="2.2"/><circle cx="${cx}" cy="${cy}" r="9" fill="transparent"/></g>`;
    else s += `<circle ${tip} cx="${cx}" cy="${cy}" r="${p.r || 5}" fill="${p.hollow ? css("--surface") : p.color}" stroke="${p.hollow ? p.color : css("--surface")}" stroke-width="${p.hollow ? 2 : 1.5}"/>`;
  });
  el.innerHTML = s + "</svg>";
  attachTips(el);
}

/** Forest plot of speed-ups with CI whiskers; rows: [{label, value, lo, hi, color, note}] */
function drawForest(el, rows) {
  const W = 880, rowH = 34, T = 14, B = 40, L = 230, R = 70;
  const H = T + B + rows.length * rowH;
  const vals = rows.flatMap((r) => [r.lo ?? r.value, r.hi ?? r.value, r.value]).concat([1]);
  let x0 = Math.min(...vals), x1 = Math.max(...vals);
  const pad = (x1 - x0) * 0.12 || 0.02; x0 -= pad; x1 += pad;
  const X = (v) => L + ((v - x0) / (x1 - x0)) * (W - L - R);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="speed-up forest plot">`;
  for (const t of niceTicks(x0, x1, 7)) s += `<line class="gridline" x1="${X(t)}" x2="${X(t)}" y1="${T}" y2="${H - B}"/><text class="tick" x="${X(t)}" y="${H - B + 16}" text-anchor="middle">×${t}</text>`;
  s += `<line x1="${X(1)}" x2="${X(1)}" y1="${T - 4}" y2="${H - B}" stroke="${css("--ink-2")}" stroke-width="1.4"/><text class="tick" x="${X(1)}" y="${T - 2}" text-anchor="middle">-O3</text>`;
  s += `<text class="axis-label" x="${(L + W - R) / 2}" y="${H - 6}" text-anchor="middle">speed-up vs -O3 (median ratio, 95% CI) — right of the line is faster</text>`;
  rows.forEach((r, i) => {
    const y = T + i * rowH + rowH / 2;
    s += `<text class="tick" x="${L - 12}" y="${y + 4}" text-anchor="end" style="font-size:12px;fill:${css("--ink")}">${esc(r.label)}</text>`;
    if (r.lo != null) s += `<line x1="${X(r.lo)}" x2="${X(r.hi)}" y1="${y}" y2="${y}" stroke="${r.color}" stroke-width="2.4" stroke-linecap="round"/>`;
    s += `<circle cx="${X(r.value)}" cy="${y}" r="6" fill="${r.color}" stroke="${css("--surface")}" stroke-width="1.5" data-tip="${esc(r.label)}: ×${num(r.value, 4)}${r.lo != null ? ` [${num(r.lo, 3)}, ${num(r.hi, 3)}]` : ""}"/>`;
    if (r.note) s += `<text class="tick" x="${W - R + 8}" y="${y + 4}">${esc(r.note)}</text>`;
  });
  el.innerHTML = s + "</svg>";
  attachTips(el);
}

/** Configuration matrix: evaluations (columns) x bits (rows). */
function drawMatrix(el, { evals, bitNames, refKey, color }) {
  const C = palette();
  const n = evals.length, rows = bitNames.length;
  if (!n) { el.innerHTML = emptyState("No evaluations yet"); return; }
  const L = 168, T = 70, cw = Math.max(6, Math.min(22, 700 / n)), ch = 18, W = L + n * cw + 20, H = T + rows * ch + 30;
  const pcts = evals.map((e) => e.pct).filter((v) => v != null);
  const maxAbs = Math.max(1, ...pcts.map(Math.abs));
  const best = evals.reduce((b, e) => (e.pct != null && (b == null || e.pct > b.pct) ? e : b), null);
  let s = `<svg viewBox="0 0 ${W} ${H}" style="min-width:${Math.min(W, 1200)}px" role="img" aria-label="configuration matrix">`;
  s += `<text class="tick" x="${L - 10}" y="${T - 44}" text-anchor="end">% vs -O3</text><line x1="${L}" x2="${L + n * cw}" y1="${T - 36}" y2="${T - 36}" stroke="${C.ink3}" stroke-width="0.6"/>`;
  evals.forEach((e, j) => {
    const x = L + j * cw;
    if (e.pct != null) {
      const h = (Math.abs(e.pct) / maxAbs) * 28, up = e.pct >= 0;
      s += `<rect x="${x + 1}" y="${up ? T - 36 - h : T - 36}" width="${cw - 2}" height="${Math.max(1, h)}" fill="${up ? C.good : C.bad}" opacity="0.85" data-tip="#${e.eval_id + 1}: ${sgn(e.pct)} vs -O3<br>${esc(e.diff)}"/>`;
    } else s += `<text x="${x + cw / 2}" y="${T - 30}" text-anchor="middle" fill="${C.bad}" font-size="10">×</text>`;
    if ((j + 1) % 10 === 0 || j === 0) s += `<text class="tick" x="${x + cw / 2}" y="${T + rows * ch + 16}" text-anchor="middle">${j + 1}</text>`;
  });
  bitNames.forEach((name, i) => {
    const y = T + i * ch;
    s += `<text class="tick" x="${L - 10}" y="${y + ch / 2 + 4}" text-anchor="end" style="font-family:var(--mono);font-size:10.5px">${esc(name)}</text>`;
    evals.forEach((e, j) => {
      const bit = e.key ? e.key[i] : "0", ref = refKey ? refKey[i] : null;
      const x = L + j * cw;
      const on = bit === "1";
      s += `<rect x="${x + 1}" y="${y + 1}" width="${cw - 2}" height="${ch - 2}" rx="2" fill="${on ? color : C.surface3}" opacity="${on ? 0.9 : 1}" data-tip="#${e.eval_id + 1} · ${esc(name)} = ${on ? "on" : "off"}${ref != null && ref !== bit ? " (differs from -O3)" : ""}"/>`;
      if (ref != null && ref !== bit) s += `<circle cx="${x + cw / 2}" cy="${y + ch / 2}" r="${Math.min(2.6, cw / 5)}" fill="${on ? "#fff" : C.ink3}"/>`;
    });
  });
  if (best) {
    const j = evals.indexOf(best);
    s += `<rect x="${L + j * cw}" y="${T - 2}" width="${cw}" height="${rows * ch + 4}" fill="none" stroke="${C.good}" stroke-width="2" rx="3"/><text class="tick" x="${L + j * cw + cw / 2}" y="${T + rows * ch + 28}" text-anchor="middle" style="fill:${C.good};font-weight:600">best</text>`;
  }
  s += `<text class="tick" x="${L}" y="${T + rows * ch + 28}">evaluation →</text>`;
  el.innerHTML = s + "</svg>";
  attachTips(el);
}

// ---------- boot -----------------------------------------------------------------
function boot() {
  setTheme(document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  watchJobs();
  setInterval(watchJobs, 3000);
  route();
}
