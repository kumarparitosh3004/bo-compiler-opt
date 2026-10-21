/* pages-run.js - dashboard, optimize, live run view, BO vs Random, verify. */
"use strict";

const T2_BO = "bo speed-up vs -O3 (median of seeds)";
const T2_RND = "random speed-up vs -O3 (median of seeds)";
const T2_BO_V = "bo seeds faster/same/slower";
const T2_RND_V = "random seeds faster/same/slower";

function benchOptions(selected, withAll = false) {
  const groups = { "Synthetic kernels": [], "Real-world data": [], "Uploaded programs": [] };
  for (const b of INFO.benchmarks) groups[b.custom ? "Uploaded programs" : b.real_data ? "Real-world data" : "Synthetic kernels"].push(b);
  return Object.entries(groups).filter(([, l]) => l.length).map(([g, l]) => `<optgroup label="${g}">${l.map((b) => `<option value="${esc(b.name)}" ${b.name === selected ? "selected" : ""}>${esc(b.name)}</option>`).join("")}</optgroup>`).join("") + (withAll ? `<option value="all">All programs (one job each)</option>` : "");
}

function timeAgo(iso) {
  const t = Date.parse(iso || "");
  if (Number.isNaN(t)) return "";
  const s = (Date.now() - t) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
const fasterSeeds = (v) => (typeof v === "string" ? parseInt(v.split("/")[0], 10) || 0 : 0);

/** Verified speed-up per program, bars drawn from x1.0; faded = not statistically significant. */
function drawSpeedups(el, rows) {
  const C = palette();
  const W = 820, L = 104, R = 70, rowH = 36, T = 6, B = 28, H = T + B + rows.length * rowH;
  const vals = rows.flatMap((r) => [r.bo, r.rnd]).filter((v) => v != null);
  let x0 = Math.min(0.97, ...vals), x1 = Math.max(1.03, ...vals);
  const pad = (x1 - x0) * 0.05; x0 -= pad; x1 += pad;
  const X = (v) => L + ((v - x0) / (x1 - x0)) * (W - L - R);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="verified speed-up vs -O3 by program">`;
  for (const t of niceTicks(x0, x1, 6)) s += `<line class="gridline" x1="${X(t)}" x2="${X(t)}" y1="${T}" y2="${H - B}"/><text class="tick" x="${X(t)}" y="${H - B + 17}" text-anchor="middle">×${t}</text>`;
  s += `<line x1="${X(1)}" x2="${X(1)}" y1="${T}" y2="${H - B}" stroke="${css("--ink-3")}" stroke-width="1.2"/>`;
  rows.forEach((r, i) => {
    const y = T + i * rowH;
    s += `<text class="tick" x="${L - 12}" y="${y + rowH / 2 + 4}" text-anchor="end" style="font-size:12.5px;fill:${css("--ink")}">${esc(r.name)}</text>`;
    [["bo", r.bo, r.sig, 7], ["random", r.rnd, r.sigR, rowH / 2 + 1]].forEach(([m, v, sig, dy]) => {
      if (v == null) return;
      const xa = X(Math.min(1, v)), xb = X(Math.max(1, v));
      s += `<rect x="${xa}" y="${y + dy}" width="${Math.max(2, xb - xa)}" height="11" rx="3" fill="${C[m]}" opacity="${sig ? 1 : 0.4}" data-tip="${esc(r.name)} · ${METHOD[m]}: ×${num(v, 3)}${sig ? " · significant" : " · within noise"}"/>`;
    });
    s += `<text x="${W - R + 10}" y="${y + rowH / 2 + 4}" style="font:600 12px var(--mono);fill:${r.sig ? css("--good") : css("--ink-3")}">×${num(r.bo, 3)}</text>`;
  });
  el.innerHTML = s + "</svg>";
  attachTips(el);
}

// ---------- Overview (dashboard) -----------------------------------------------------
addRoute(/^#?\/?$/, dashboard, "dashboard", "Overview");
async function dashboard() {
  const [d, jobs] = await Promise.all([api("/api/dashboard"), api("/api/jobs")]);
  const C = palette(), ps = d.programs, gm = d.geomean || {};
  const base = Object.fromEntries(INFO.benchmarks.map((b) => [b.name, b]));
  const running = jobs.filter((j) => j.status === "running").length, queued = jobs.filter((j) => j.status === "queued").length;
  const rows = ps.filter((p) => p.verified && p.verified[T2_BO] != null)
    .map((p) => ({ name: p.name, bo: p.verified[T2_BO], rnd: p.verified[T2_RND], sig: fasterSeeds(p.verified[T2_BO_V]) >= 2, sigR: fasterSeeds(p.verified[T2_RND_V]) >= 2 }))
    .sort((a, b) => b.bo - a.bo);
  const top = rows[0], latest = d.recent[0], g = gm.geomean_speedup_vs_O3_bo;
  const sigCount = rows.filter((r) => r.sig).length;
  const version = (INFO.compiler_version.match(/\d+\.\d+\.\d+/) || [""])[0];

  const activity = d.recent.length ? `<ul class="activity">${d.recent.slice(0, 7).map((r) => `<li><a href="#/run/${r.source}/${r.exp_id}"><span class="dot ${r.finished ? "" : "run"}"></span>
      <span class="what"><b>${esc(r.benchmark)}</b> <span class="muted">· ${SHORT[r.method]} search</span></span>
      <span class="mono small ${r.best_pct > 0 ? "" : "muted"}">${sgn(r.best_pct, 1)}</span><span class="when">${timeAgo(r.started)}</span></a></li>`).join("")}</ul>` : emptyState("No searches yet", "history");

  const programs = `<div class="table-wrap"><table><thead><tr><th>Program</th><th class="num">-O3 time</th><th class="num">Best found</th><th class="num">Verified</th><th class="num">Runs</th><th></th></tr></thead><tbody>
    ${ps.map((p) => {
      const b = base[p.name] || {}, v = p.verified && p.verified[T2_BO], sig = p.verified && fasterSeeds(p.verified[T2_BO_V]) >= 2;
      const best = Math.max(p.best_bo ?? -Infinity, p.best_random ?? -Infinity);
      return `<tr class="clickable" data-go="#/duel?bench=${encodeURIComponent(p.name)}"><td><b>${esc(p.name)}</b>${b.real_data ? `<span class="tag">real data</span>` : b.custom ? `<span class="tag">uploaded</span>` : ""}</td>
        <td class="num mono">${b.baseline_ms && b.baseline_ms.O3 != null ? num(b.baseline_ms.O3, 0) + " ms" : "–"}</td>
        <td class="num mono">${Number.isFinite(best) ? sgn(best, 1) : "–"}</td>
        <td class="num mono">${v != null ? `${sig ? `<span style="color:var(--good)">×${num(v, 3)}</span>` : `×${num(v, 3)}`}` : "–"}</td>
        <td class="num">${p.runs}</td>
        <td class="num"><a class="icon-link" href="#/optimize?bench=${encodeURIComponent(p.name)}" title="Optimize ${esc(p.name)}" onclick="event.stopPropagation()">${icon("play")}</a></td></tr>`;
    }).join("")}</tbody></table></div>`;

  view.innerHTML = pageHead("", "Overview", latest ? `Last search ${timeAgo(latest.started)} · ${fmtInt(d.evaluations)} evaluations across ${ps.length} programs` : "Run your first optimization to see results here.",
      `<a class="btn" href="#/results">${icon("chart")}Results</a><a class="btn primary" href="#/optimize">${icon("play")}New optimization</a>`)
    + sweepNotice()
    + `<div class="grid g4" style="margin-bottom:20px">
        ${kpi("Verified speed-up", g ? `×${num(g, 3)}` : "–", g ? `<span class="delta">+${num((g - 1) * 100, 1)}%</span> geometric mean vs -O3` : "pending final measurement", "gauge")}
        ${kpi("Best program", top ? `×${num(top.bo, 3)}` : "–", top ? `${esc(top.name)} · ${sigCount} of ${rows.length} significant` : "", "target")}
        ${kpi("Searches", fmtInt(d.runs), `${fmtInt(d.evaluations)} evaluations`, "cpu")}
        ${kpi("Search space", fmtInt(INFO.n_configs), `${INFO.dim - 1} flags + base level`, "grid")}
      </div>
      <div class="grid g-2-1">
        ${card("Speed-up vs -O3", rows.length ? `<div class="chart" id="sp"></div>` : emptyState("Verified results appear after the final measurement.", "chart"),
          { sub: "verified · median of seeds", right: `<div class="legend-inline"><span><i style="background:${C.bo}"></i>BO</span><span><i style="background:${C.random}"></i>Random</span><span><i style="background:${C.lvl};opacity:.4"></i>within noise</span></div>` })}
        <div>
          ${card("Recent activity", activity, { flush: true, right: `<a class="btn sm ghost" href="#/history">View all</a>` })}
          ${card("Environment", `<dl class="kv"><dt>Compiler</dt><dd>GCC ${esc(version)}</dd><dt>Flags searched</dt><dd>${INFO.dim - 1}</dd><dt>Programs</dt><dd>${ps.length}</dd><dt>Queue</dt><dd>${running ? `${running} running` : queued ? `${queued} queued` : "idle"}</dd></dl>`, { flush: true })}
        </div>
      </div>`
    + card("Programs", programs, { flush: true, right: `<a class="btn sm ghost" href="#/programs">Manage</a>` });
  if (rows.length) drawSpeedups($("#sp"), rows);
  $$("[data-go]").forEach((tr) => (tr.onclick = () => (location.hash = tr.dataset.go)));
}

// ---------- Optimize ---------------------------------------------------------------
addRoute(/^#\/optimize/, optimize, "optimize", "Optimize");
async function optimize() {
  const q = query(), d = INFO.defaults;
  view.innerHTML = pageHead("", "Optimize", "Search GCC flag configurations for a program and track every evaluation live.") + sweepNotice() + `
  <div class="grid g-2-1">
    ${card("Configure", `<form id="f">
      <div class="form-row"><label class="field" style="flex:1;min-width:220px">Program<select name="bench" id="bench">${benchOptions(q.bench, true)}</select><span class="hint" id="bench-hint"></span></label></div>
      <div class="field" style="margin-bottom:16px">Search method
        <div class="choice-grid">
          <label class="choice"><input type="radio" name="method" value="bo" checked><div><b>Bayesian Optimization</b><span>GP surrogate + Expected Improvement</span></div></label>
          <label class="choice"><input type="radio" name="method" value="random"><div><b>Random search</b><span>Uniform sampling baseline</span></div></label>
          <label class="choice"><input type="radio" name="method" value="both"><div><b>Both</b><span>Run both with the same seed</span></div></label>
        </div></div>
      <div class="form-row">
        <label class="field">Budget<input type="number" name="budget" min="5" max="200" value="${d.budget}"><span class="hint">evaluations</span></label>
        <label class="field">Timed rounds<input type="number" name="reps" min="1" max="15" value="${d.reps}"><span class="hint">per evaluation</span></label>
        <label class="field">Initial points<input type="number" name="n_init" min="2" max="20" value="${d.n_init}"><span class="hint">-O3 + random</span></label>
        <label class="field">Seed<input type="number" name="seed" min="0" value="${d.seed}"><span class="hint">for reproducible runs</span></label>
      </div>
      <div class="flex"><button class="btn primary" type="submit">${icon("play")}Start optimization</button><span class="muted small" id="estimate"></span></div>
      <div id="msg" style="margin-top:12px"></div></form>`)}
    <div>
      ${card("Summary", `<dl class="kv"><dt>Program</dt><dd id="s-prog"></dd><dt>Method</dt><dd id="s-method"></dd><dt>Jobs</dt><dd id="s-jobs"></dd><dt>Evaluations</dt><dd id="s-evals"></dd><dt>-O3 baseline</dt><dd id="s-base"></dd><dt>Estimated time</dt><dd id="s-time"></dd></dl>`, { flush: true })}
      ${card("Pipeline", `<ol class="steps">
        <li><b>Propose</b><span>model picks the next configuration</span></li>
        <li><b>Build &amp; check</b><span>compile, deduplicate, verify output</span></li>
        <li><b>Measure</b><span>paired timing against -O3</span></li></ol>`)}
    </div>
  </div>
  ${card("Queue", `<div id="queue"></div>`, { sub: "live", flush: true })}`;
  const form = $("#f");
  const benchMap = Object.fromEntries(INFO.benchmarks.map((b) => [b.name, b]));
  const updateEst = () => {
    const fd = Object.fromEntries(new FormData(form));
    const names = fd.bench === "all" ? Object.keys(benchMap) : [fd.bench];
    const m = fd.method === "both" ? 2 : 1;
    let sec = 0;
    for (const n of names) {
      const t = ((benchMap[n].baseline_ms || {}).O3 || 400) / 1000;
      sec += +fd.budget * (1.0 + 0.6 * (+fd.reps + 1) * 2 * t);
    }
    sec *= m;
    const est = sec < 120 ? `${Math.round(sec)} s` : `${Math.round(sec / 60)} min`;
    $("#estimate").textContent = `≈ ${est}`;
    const b = benchMap[fd.bench];
    $("#bench-hint").innerHTML = b ? `${b.real_data ? "Real-world data · " : ""}args <code>${esc(b.args.join(" ") || "none")}</code>` : "One job per program";
    $("#s-prog").textContent = fd.bench === "all" ? `All (${names.length})` : fd.bench;
    $("#s-method").textContent = { bo: "Bayesian Optimization", random: "Random search", both: "BO + Random" }[fd.method];
    $("#s-jobs").textContent = names.length * m;
    $("#s-evals").textContent = fmtInt(names.length * m * +fd.budget);
    $("#s-base").textContent = b && b.baseline_ms && b.baseline_ms.O3 ? `${num(b.baseline_ms.O3, 0)} ms` : "–";
    $("#s-time").textContent = `≈ ${est}`;
  };
  form.addEventListener("input", updateEst); updateEst();
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const jobs = await post("/api/jobs", { type: "search", ...Object.fromEntries(new FormData(form)) });
      if (jobs.length === 1) location.hash = `#/run/web/${jobs[0].exp_id}`;
      else { $("#msg").innerHTML = notice("ok", `${jobs.length} jobs queued. Follow them below.`); renderQueue($("#queue")); }
    } catch (err) { $("#msg").innerHTML = errorBox(err); }
  });
  every(2000, () => renderQueue($("#queue")));
}

async function renderQueue(el) {
  const jobs = await api("/api/jobs");
  if (!el || !el.isConnected) return;
  if (!jobs.length) { el.innerHTML = emptyState("No jobs yet", "play"); return; }
  el.innerHTML = `<div class="table-wrap"><table><thead><tr><th>Job</th><th>Program</th><th>Task</th><th>Status</th><th style="width:180px">Progress</th><th></th></tr></thead><tbody>
  ${jobs.slice(0, 40).map((j) => {
    const p = j.params, link = j.type === "search" ? `#/run/web/${j.exp_id}` : `#/compare/${j.id}`;
    const what = j.type === "search" ? `${methodChip(p.method)} <span class="small muted">seed ${p.seed} · budget ${p.budget}</span>` : `<span class="small">compare ${p.candidates.length} configs · ${p.reps} rounds</span>`;
    const best = j.summary && j.summary.best_pct_faster_than_O3 != null ? `<div class="small muted">best ${sgn(j.summary.best_pct_faster_than_O3)}</div>` : "";
    return `<tr><td class="mono small">${esc(j.id)}<div class="muted small">${esc((j.created_at || "").slice(5, 16).replace("T", " "))}</div></td><td><b>${esc(p.bench)}</b></td><td>${what}${best}</td>
      <td>${chip(j.status)}${j.error ? `<div class="small" style="color:var(--bad);max-width:260px">${esc(j.error)}</div>` : ""}</td>
      <td><div class="flex" style="flex-wrap:nowrap">${progress(j.progress.done || 0, j.progress.total || 0)}<span class="small muted mono">${j.progress.done || 0}/${j.progress.total || "?"}</span></div></td>
      <td><div class="flex" style="flex-wrap:nowrap"><a class="btn sm" href="${link}">Open</a>${["queued", "running"].includes(j.status) ? `<button class="btn sm danger" data-cancel="${j.id}">Cancel</button>` : ""}</div></td></tr>`;
  }).join("")}</tbody></table></div>`;
  $$("[data-cancel]", el).forEach((b) => b.addEventListener("click", async () => { b.disabled = true; await post(`/api/jobs/${b.dataset.cancel}/cancel`); renderQueue(el); }));
}

// ---------- Run view ---------------------------------------------------------------
addRoute(/^#\/run\/(study|web)\/([\w-]+)/, runView, "optimize", "Run", true);
async function runView(source, exp) {
  let tab = "progress", overlay = null, job = null, last = null;
  const runs = await api("/api/runs");
  view.innerHTML = `<div id="rh"></div><div class="grid g4" id="rk" style="margin-bottom:20px"></div>
    <section class="card"><div class="tabs-inline" id="rtabs">${[["progress", "Progress"], ["matrix", "Configuration matrix"], ["evals", "Evaluations"], ["model", "Model"], ["log", "Log"]].map(([k, l]) => `<button data-t="${k}" class="${k === tab ? "active" : ""}">${l}</button>`).join("")}</div><div class="card-body" id="rbody"></div></section>
    <div id="rbest"></div>`;
  $$("#rtabs button").forEach((b) => b.addEventListener("click", () => { tab = b.dataset.t; $$("#rtabs button").forEach((x) => x.classList.toggle("active", x === b)); renderBody(); }));

  function renderBody() {
    if (!last) return;
    const { r, method, budget } = last, ev = r.evals, C = palette(), col = C[method] || C.bo, body = $("#rbody");
    if (tab === "progress") {
      body.innerHTML = `<div class="flex" style="margin-bottom:8px"><span class="muted small">% faster than -O3 for every evaluation; the line is the best found so far.</span><span class="spacer"></span>
        <label class="field" style="flex-direction:row;align-items:center;gap:8px">Overlay <select id="ov"><option value="">none</option>${runs.filter((x) => x.benchmark === last.bench && x.exp_id !== exp).map((x) => `<option value="${x.source}/${x.exp_id}" ${overlay && overlay.key === `${x.source}/${x.exp_id}` ? "selected" : ""}>${SHORT[x.method]} seed ${x.seed} (${x.source})</option>`).join("")}</select></label></div>
        <div class="chart" id="chart"></div><div class="legend" id="legend"></div>
        <div class="divider"></div><h3>Exploration → exploitation</h3><p class="muted small">Expected Improvement of each configuration BO chose, on a log scale. It falls as the model becomes confident it has found the good region.</p><div class="chart" id="eichart"></div>`;
      $("#ov").onchange = async (e) => { overlay = e.target.value ? { key: e.target.value, data: await api(`/api/runs/${e.target.value}`) } : null; renderBody(); };
      const ok = ev.filter((e) => e.pct != null);
      const floor = ok.length ? Math.min(...ok.map((e) => e.pct)) : -5;
      const pts = ok.map((e) => ({ x: e.eval_id + 1, y: e.pct, color: col, hollow: e.reused, tip: `<b>#${e.eval_id + 1}</b> · ${sgn(e.pct)} vs -O3<br>${diffHtml(e.diff) || "same as -O3"}${e.reused ? "<br><i>identical binary: measurement reused</i>" : ""}` }))
        .concat(ev.filter((e) => e.pct == null).map((e) => ({ x: e.eval_id + 1, y: floor, color: C.bad, cross: true, tip: `#${e.eval_id + 1} · ${esc(e.status)}<br>${esc(e.note || "")}` })));
      const lines = [{ color: col, data: ev.filter((e) => e.best_pct != null).map((e) => [e.eval_id + 1, e.best_pct]), step: true, width: 2.6 }];
      if (overlay) { const om = overlay.data.manifest || {}; lines.push({ color: C[om.method] || C.lvl, dash: true, step: true, data: overlay.data.evals.filter((e) => e.best_pct != null).map((e) => [e.eval_id + 1, e.best_pct]) }); }
      drawChart($("#chart"), { lines, points: pts, xLabel: "evaluation", yLabel: "% faster than -O3", xMin: 0, xMax: Math.max(budget, overlay ? overlay.data.evals.length : 0) });
      $("#legend").innerHTML = `<span><i style="background:${col}"></i>evaluation (hollow = reused identical binary)</span><span><i style="background:${col};height:3px"></i>best so far</span><span><i style="background:${C.bad}"></i>failed</span>${overlay ? `<span><i style="background:${lines[1].color};height:3px"></i>overlay best so far</span>` : ""}`;
      const eis = ev.filter((e) => e.acq != null && e.acq > 0);
      if (eis.length) drawChart($("#eichart"), { height: 180, zero: false, lines: [{ color: C.bo, data: eis.map((e) => [e.eval_id + 1, Math.log10(e.acq)]) }], points: eis.map((e) => ({ x: e.eval_id + 1, y: Math.log10(e.acq), color: C.bo, r: 3.5, tip: `#${e.eval_id + 1}: EI = ${Number(e.acq).toExponential(2)}` })), xLabel: "evaluation", yLabel: "log₁₀ EI", xMin: 0, xMax: budget });
      else $("#eichart").innerHTML = emptyState(method === "bo" ? "EI values appear after the initial random points" : "Random search uses no acquisition function");
    } else if (tab === "matrix") {
      body.innerHTML = `<p class="muted small">Each column is one evaluation; each row is one bit of the configuration (filled = on). Dots mark bits that differ from <code>-O3</code>. The strip on top shows each evaluation's result. Watch BO's columns converge on one pattern while random search stays scattered.</p><div class="chart" style="overflow-x:auto" id="mx"></div>`;
      drawMatrix($("#mx"), { evals: ev, bitNames: r.bit_names || [], refKey: r.ref_key, color: col });
    } else if (tab === "evals") {
      body.innerHTML = ev.length ? `<div class="flex" style="margin-bottom:10px"><span class="muted small">${ev.length} evaluations, newest first</span><span class="spacer"></span><a class="btn sm" href="/api/runs/${source}/${exp}/csv">${icon("download")}Download CSV</a></div>
        <div class="table-wrap"><table><thead><tr><th class="num">#</th><th>Status</th><th class="num">Time</th><th class="num">vs -O3</th><th class="num">Best so far</th><th>Changes from -O3</th><th class="num">.text</th><th class="num">EI</th></tr></thead><tbody>
        ${[...ev].reverse().map((e) => `<tr><td class="num">${e.eval_id + 1}</td><td>${statusChip(e.status)} ${e.reused ? chip("reused", "plain") : ""} ${e.noisy ? chip("noisy", "warn") : ""}</td>
          <td class="num mono">${e.median_ms != null ? num(e.median_ms, 1) + " ms" : "–"}</td><td class="num mono">${sgn(e.pct)}</td><td class="num mono">${sgn(e.best_pct)}</td>
          <td class="mono small">${diffHtml(e.diff) || '<span class="muted">same as -O3</span>'}</td><td class="num mono small">${e.text_bytes ? fmtInt(e.text_bytes) : "–"}</td><td class="num small mono">${e.acq != null ? Number(e.acq).toExponential(1) : "init"}</td></tr>`).join("")}</tbody></table></div>` : emptyState("Waiting for the first evaluation…");
    } else if (tab === "model") {
      const s = r.summary;
      if (s && s.length_scales) {
        const ent = Object.entries(s.length_scales).map(([k, v]) => [k, 1 / v]); const mx = Math.max(...ent.map((e) => e[1])); ent.sort((a, b) => b[1] - a[1]);
        body.innerHTML = `<p class="muted small">Relevance = 1 / fitted ARD length scale of the Gaussian process, normalized. A long bar means run time was sensitive to that bit. This is correlational, not causal.</p>
          ${ent.map(([k, v]) => `<div class="bar-row"><span class="mono">${esc(k === "base_level" ? "base -O2/-O3" : "-f" + k)}</span><div class="track"><div class="fill" style="width:${(100 * v) / mx}%"></div></div><span class="mono">${num(v / mx, 2)}</span></div>`).join("")}`;
      } else body.innerHTML = emptyState(method === "bo" ? "The model's flag relevance appears when the run finishes." : "Random search builds no model.", "bulb");
    } else body.innerHTML = `<div class="log">${esc((r.log || []).join("\n") || "–")}</div>`;
  }

  async function tick() {
    const r = await api(`/api/runs/${source}/${exp}`);
    if (source === "web") job = (await api("/api/jobs")).find((j) => j.exp_id === exp) || job;
    if (!$("#rh")) return "gone";
    const m = r.manifest || {}, ev = r.evals || [];
    const method = m.method || (job && job.params.method) || "bo", budget = m.budget || (job && job.params.budget) || ev.length;
    const status = job ? job.status : m.finished_at ? "done" : "partial", bench = m.benchmark || (job && job.params.bench) || "";
    last = { r, method, budget, bench };
    const C = palette(), ok = ev.filter((e) => e.pct != null);
    const best = ok.length ? ok.reduce((a, b) => (b.pct > a.pct ? b : a)) : null;
    $("#rh").innerHTML = pageHead(source === "study" ? "Study sweep run" : "Website run", `${esc(bench)} · ${esc(METHOD[method] || method)} <span class="muted" style="font-weight:500">seed ${esc(m.seed ?? (job && job.params.seed))}</span> ${chip(status)}`,
      `<span class="mono small">${esc(exp)}</span>${job && job.message ? " · " + esc(job.message) : ""}`,
      `${job && ["queued", "running"].includes(job.status) ? `<button class="btn danger" id="cancel">${icon("x")}Cancel</button>` : ""}<a class="btn" href="#/duel?bench=${encodeURIComponent(bench)}">${icon("duel")}Compare methods</a><a class="btn primary" href="#/optimize?bench=${encodeURIComponent(bench)}">${icon("play")}New run</a>`)
      + `<div class="flex" style="margin:-6px 0 18px">${progress(ev.length, budget)}<span class="small muted mono">${ev.length} / ${budget}</span></div>`
      + (job && job.status === "queued" ? notice("info", "Waiting in the queue; it starts when the jobs ahead of it finish.") : "") + (job && job.error ? errorBox(job.error) : "");
    const cb = $("#cancel"); if (cb) cb.onclick = async () => { cb.disabled = true; await post(`/api/jobs/${job.id}/cancel`); };
    const uniq = ev.filter((e) => !e.reused && e.median_ms != null).length, fails = ev.filter((e) => e.pct == null).length;
    $("#rk").innerHTML = kpi("Best so far (search)", best ? sgn(best.pct) : "–", best ? `evaluation #${best.eval_id + 1}` : "", "target", best && best.pct > 0 ? C.good : C.lvl)
      + kpi("Evaluations", `${ev.length}<span class="muted" style="font-size:15px"> / ${budget}</span>`, "", "cpu", C[method])
      + kpi("Measured binaries", uniq, `${ev.length - uniq - fails} reused byte-identical`, "hash", C.brand)
      + kpi("Failures", fails, "compile / run / wrong output", "warn", fails ? C.bad : C.lvl);
    $("#rbest").innerHTML = best ? card("Best configuration so far", `<div class="grid g2"><div>
        <div class="big" style="color:${best.pct > 0 ? "var(--good)" : "var(--ink)"}">${sgn(best.pct)}</div><div class="muted small">vs -O3 · search-time measurement · evaluation #${best.eval_id + 1}</div>
        ${notice("info", "Search-time result. Confirm it with an interleaved benchmark.")}
        <button class="btn primary" id="vb">${icon("verify")}Verify against -O2 and -O3</button> <span id="vmsg"></span></div>
        <div><h3>Changes from -O3</h3><div class="flags">${diffHtml(best.diff) || "same as -O3"}</div><h3 style="margin-top:12px">Command line</h3><div class="flags">gcc ${esc(best.flags)} prog.c</div></div></div>`) : "";
    const vb = $("#vb");
    if (vb) vb.onclick = async () => {
      vb.disabled = true;
      try {
        const j = await post("/api/jobs", { type: "compare", bench, reps: INFO.defaults.compare_reps, kind: "verify", source_runs: [exp], candidates: [{ name: "O2", flags: ["-O2"] }, { name: `${SHORT[method]} best #${best.eval_id + 1}`, flags: best.flags.split(" ") }] });
        location.hash = `#/compare/${j[0].id}`;
      } catch (e) { $("#vmsg").innerHTML = errorBox(e); vb.disabled = false; }
    };
    renderBody();
    return status;
  }
  const st = await tick();
  if (["queued", "running", "partial"].includes(st)) every(1800, async () => { const s = await tick(); if (!["queued", "running", "partial"].includes(s)) clearTimers(); });
}

// ---------- BO vs Random ----------------------------------------------------------
addRoute(/^#\/duel/, duel, "duel", "BO vs Random");
async function duel() {
  const q = query(), names = INFO.benchmarks.map((b) => b.name);
  const bench = q.bench && names.includes(q.bench) ? q.bench : names[0];
  view.innerHTML = pageHead("", "Compare methods", "Best configuration found so far, by evaluation, across all seeds.",
    `<select id="db">${benchOptions(bench)}</select><label class="flex small"><input type="checkbox" id="dw"> include website runs</label>`) + `<div id="dbody"><div class="skeleton" style="height:340px"></div></div>`;
  const render = async () => {
    const b = $("#db").value, incl = $("#dw").checked;
    history.replaceState(null, "", `#/duel?bench=${encodeURIComponent(b)}`);
    const all = (await api(`/api/curves?bench=${encodeURIComponent(b)}`)).filter((r) => incl || r.source === "study");
    const C = palette();
    if (!all.length) { $("#dbody").innerHTML = card("", emptyState("No searches for this program yet. Run one from Optimize.", "duel")); return; }
    const agg = {};
    const lines = [], bands = [];
    for (const m of ["bo", "random"]) {
      const rs = all.filter((r) => r.method === m && r.best.length);
      if (!rs.length) continue;
      const L = Math.max(...rs.map((r) => r.best.length));
      const fill = (arr) => Array.from({ length: L }, (_, i) => arr[Math.min(i, arr.length - 1)] ?? arr.find((v) => v != null) ?? 0);
      const A = rs.map((r) => fill(r.best));
      const med = [], band = [];
      for (let i = 0; i < L; i++) { const col = A.map((a) => a[i]).sort((x, y) => x - y); const md = col.length % 2 ? col[(col.length - 1) / 2] : (col[col.length / 2 - 1] + col[col.length / 2]) / 2; med.push([i + 1, md]); band.push([i + 1, col[0], col[col.length - 1]]); }
      lines.push({ color: C[m], data: med, step: true, width: 2.8 }); bands.push({ color: C[m], data: band });
      agg[m] = { runs: rs.length, at: (n) => med[Math.min(n, L) - 1][1], final: med[L - 1][1] };
    }
    const row = (n) => `<tr><td>best after ${n} evaluations</td>${["bo", "random"].map((m) => `<td class="num mono">${agg[m] ? sgn(agg[m].at(n)) : "–"}</td>`).join("")}<td class="num mono">${agg.bo && agg.random ? sgn(agg.bo.at(n) - agg.random.at(n)) : "–"}</td></tr>`;
    $("#dbody").innerHTML = `<div class="grid g4" style="margin-bottom:20px">${kpi("BO runs", agg.bo ? agg.bo.runs : 0, "", "target", C.bo)}${kpi("Random runs", agg.random ? agg.random.runs : 0, "", "shuffle", C.random)}${kpi("BO final (median)", agg.bo ? sgn(agg.bo.final) : "–", "search-time vs -O3", "gauge", C.bo)}${kpi("Random final (median)", agg.random ? sgn(agg.random.final) : "–", "search-time vs -O3", "gauge", C.random)}</div>`
      + card("Convergence", `<div class="chart" id="dc"></div><div class="legend"><span><i style="background:${C.bo}"></i>Bayesian Optimization (median, band = min–max)</span><span><i style="background:${C.random}"></i>Random search</span></div>`, { sub: "% faster than -O3 during search" })
      + `<div class="grid g2">` + card("Sample efficiency", `<table><thead><tr><th>Budget</th><th class="num">BO</th><th class="num">Random</th><th class="num">BO − Random</th></tr></thead><tbody>${[5, 10, 20, 30, 50].map(row).join("")}</tbody></table>`, { flush: true, sub: "median across seeds" })
      + card("Runs", `<table><thead><tr><th>Method</th><th class="num">Seed</th><th>Source</th><th class="num">Best</th><th></th></tr></thead><tbody>${all.map((r) => `<tr><td>${methodChip(r.method)}</td><td class="num">${r.seed}</td><td class="small">${r.source}</td><td class="num mono">${sgn(r.best_pct)}</td><td><a class="btn sm" href="#/run/${r.source}/${r.exp_id}">Open</a></td></tr>`).join("")}</tbody></table>`, { flush: true }) + `</div>`;
    drawChart($("#dc"), { lines, bands, xLabel: "evaluation", yLabel: "best so far: % faster than -O3", xMin: 1, height: 340 });
  };
  $("#db").addEventListener("change", render); $("#dw").addEventListener("change", render);
  render();
}

// ---------- Verify & compare -------------------------------------------------------
addRoute(/^#\/verify/, verify, "verify", "Verify & baselines");
async function verify() {
  const q = query();
  view.innerHTML = pageHead("", "Benchmarks", "Interleaved head-to-head against -O3, with confidence intervals and significance.") + sweepNotice() + `
  <div class="grid g-2-1">${card("New comparison", `<form id="vf">
    <div class="form-row"><label class="field" style="flex:1">Program<select name="bench" id="vbench">${benchOptions(q.bench)}</select></label><label class="field">Rounds<input type="number" name="reps" min="3" max="30" value="${INFO.defaults.compare_reps}"></label></div>
    <h3>Standard levels</h3><div class="flex" style="margin-bottom:14px">${["O0", "O1", "O2", "O3"].map((l) => `<label class="choice" style="padding:8px 12px"><input type="checkbox" name="lvl" value="${l}" ${l === "O3" ? "checked disabled" : l !== "O0" ? "checked" : ""}><div><b>-${l}</b></div></label>`).join("")}</div>
    <h3>Best from searches</h3><div id="bestlist" class="stack" style="margin-bottom:14px"></div>
    <label class="field">Your own flags <span class="hint">an -O level first, then verified -f / -fno- flags</span><input name="custom" placeholder="-O3 -funroll-all-loops -fno-tree-pre"></label>
    <div class="flex" style="margin-top:14px"><button class="btn primary" type="submit">${icon("verify")}Run comparison</button><span id="vmsg"></span></div></form>`)}
    ${card("Recent comparisons", `<div id="clist"></div>`, { flush: true })}</div>`;
  const runs = await api("/api/runs");
  const fill = () => {
    const list = runs.filter((r) => r.benchmark === $("#vbench").value && r.best_flags);
    $("#bestlist").innerHTML = list.length ? list.map((r, i) => `<label class="choice"><input type="checkbox" name="run" value="${i}" ${i < 2 ? "checked" : ""}><div><b>${SHORT[r.method]} · seed ${r.seed} · ${esc(r.source)} · ${sgn(r.best_pct)}</b><span class="mono">${diffHtml(r.best_diff)}</span></div></label>`).join("") : `<span class="muted small">No finished searches for this program yet.</span>`;
    $("#bestlist").dataset.runs = JSON.stringify(list);
  };
  $("#vbench").addEventListener("change", fill); fill();
  $("#vf").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target), list = JSON.parse($("#bestlist").dataset.runs || "[]");
    const cands = fd.getAll("lvl").map((l) => ({ name: l, flags: [`-${l}`] }));
    fd.getAll("run").forEach((i) => { const r = list[+i]; cands.push({ name: `${SHORT[r.method]} s${r.seed} (${r.source})`, flags: r.best_flags.split(" ") }); });
    if (fd.get("custom").trim()) cands.push({ name: "custom", flags: fd.get("custom").trim().split(/\s+/) });
    try { const j = await post("/api/jobs", { type: "compare", bench: fd.get("bench"), candidates: cands, reps: fd.get("reps"), kind: "verify" }); location.hash = `#/compare/${j[0].id}`; }
    catch (err) { $("#vmsg").innerHTML = errorBox(err); }
  });
  const jobs = (await api("/api/jobs")).filter((j) => j.type === "compare");
  $("#clist").innerHTML = jobs.length ? `<table><tbody>${jobs.map((j) => `<tr class="clickable" onclick="location.hash='#/compare/${j.id}'"><td><b>${esc(j.params.bench)}</b><div class="muted small">${j.params.candidates.length} configs · ${esc((j.created_at || "").slice(5, 16).replace("T", " "))}</div></td><td>${chip(j.status)}</td></tr>`).join("")}</tbody></table>` : emptyState("No comparisons yet", "verify");
}

addRoute(/^#\/compare\/([\w-]+)/, compareView, "verify", "Comparison", true);
async function compareView(jobId) {
  view.innerHTML = `<div id="ch"></div><div id="cb"></div>`;
  async function tick() {
    const j = await api(`/api/jobs/${jobId}`);
    if (!$("#ch")) return "gone";
    const active = ["queued", "running"].includes(j.status);
    $("#ch").innerHTML = pageHead("Verify & baselines", `Comparison · ${esc(j.params.bench)} ${chip(j.status)}`, `${j.params.candidates.length} configurations · ${j.params.reps} interleaved rounds${j.message ? " · " + esc(j.message) : ""}`,
      `${active ? `<button class="btn danger" id="cc">${icon("x")}Cancel</button>` : ""}<a class="btn" href="#/verify?bench=${encodeURIComponent(j.params.bench)}">New comparison</a>`)
      + (active ? `<div class="flex" style="margin:-6px 0 18px">${progress(j.progress.done || 0, j.progress.total || 0)}<span class="small muted mono">${j.progress.done || 0} / ${j.progress.total || "?"} runs</span></div>` : "") + (j.error ? errorBox(j.error) : "");
    const c = $("#cc"); if (c) c.onclick = () => post(`/api/jobs/${jobId}/cancel`);
    if (j.status === "done" && j.result_file) { renderCompare(await api(`/api/compare/${jobId}`)); return "done"; }
    if (active && !$("#cb").innerHTML) $("#cb").innerHTML = `<div class="skeleton" style="height:300px"></div>`;
    return j.status;
  }
  const st = await tick();
  if (["queued", "running"].includes(st)) every(1500, async () => { const s = await tick(); if (!["queued", "running"].includes(s)) clearTimers(); });
}

function renderCompare(r) {
  const C = palette();
  const colorOf = (name) => (/^bo/i.test(name) ? C.bo : /^random/i.test(name) ? C.random : /custom/i.test(name) ? C.brand : C.lvl);
  const rows = [...r.candidates].sort((a, b) => (a.median_ms ?? 1e18) - (b.median_ms ?? 1e18));
  const valid = rows.filter((x) => x.times_ms.length);
  const verdictChip = (v) => v ? chip(v, v === "faster" ? "faster" : v === "slower" ? "slower" : "plain") : "";
  $("#cb").innerHTML = card("Speed-up vs -O3", `<div class="chart" id="forest"></div>`, { sub: `95% bootstrap CI · noise floor ${num(r.noise_floor_pct, 2)}%` })
    + card("Results", `<div class="table-wrap"><table><thead><tr><th>Configuration</th><th>Output</th><th class="num">Median</th><th class="num">vs -O3</th><th class="num">95% CI</th><th class="num">p</th><th>Verdict</th><th class="num">.text vs -O3</th><th class="num">Compile</th></tr></thead><tbody>
    ${rows.map((x) => `<tr><td><b>${esc(x.name)}</b><div class="mono small muted">${esc(x.flags)}</div></td><td>${statusChip(x.status)}</td><td class="num mono">${x.median_ms != null ? num(x.median_ms, 1) + " ms" : "–"}</td>
      <td class="num mono">${x.name === "O3" ? '<span class="muted">reference</span>' : sgn(x.pct_vs_O3)}</td><td class="num mono small">${x.ci ? `×${num(x.ci[0], 3)} – ×${num(x.ci[1], 3)}` : "–"}</td><td class="num mono small">${x.p ?? "–"}</td>
      <td>${verdictChip(x.verdict)}</td><td class="num mono small">${x.text_vs_O3_pct != null ? sgn(x.text_vs_O3_pct, 1) : "–"}</td><td class="num mono small">${x.compile_time_s != null ? num(x.compile_time_s, 2) + " s" : "–"}</td></tr>`).join("")}
    </tbody></table></div><p class="muted small" style="padding:12px 16px 0">The verdict is "faster" or "slower" only when p &lt; 0.05, the CI excludes ×1, and the difference exceeds 2× this program's noise floor. Otherwise there is no measurable difference.</p>`, { flush: true })
    + card("Every timed run", `<div class="chart" id="strip"></div>`, { sub: "one dot per round; bar = median" });
  drawForest($("#forest"), rows.filter((x) => x.speedup_vs_O3 != null).map((x) => ({ label: x.name, value: x.speedup_vs_O3, lo: x.ci && x.ci[0], hi: x.ci && x.ci[1], color: colorOf(x.name), note: x.verdict === "faster" ? "faster" : x.verdict === "slower" ? "slower" : "" })));
  const pts = [], lines = [];
  valid.forEach((x, i) => {
    const y = valid.length - i;
    x.times_ms.forEach((t) => pts.push({ x: t, y, color: colorOf(x.name), r: 4, tip: `${esc(x.name)}: ${num(t, 1)} ms` }));
    lines.push({ color: colorOf(x.name), width: 3, data: [[x.median_ms, y - 0.32], [x.median_ms, y + 0.32]] });
  });
  drawChart($("#strip"), { lines, points: pts, xLabel: "kernel time (ms)", yLabel: "", zero: false, yMin: 0.3, yMax: valid.length + 0.7,
    xMin: Math.min(...pts.map((p) => p.x)) * 0.98, xMax: Math.max(...pts.map((p) => p.x)) * 1.02, height: 60 + 44 * valid.length });
  // label rows in the strip chart
  const svg = $("#strip svg");
  if (svg) valid.forEach((x, i) => { const t = document.createElementNS("http://www.w3.org/2000/svg", "text"); const H = 60 + 44 * valid.length, T = 14, B = 46; const yy = T + (1 - ((valid.length - i) - 0.3) / (valid.length + 0.4)) * (H - T - B); t.setAttribute("x", 64); t.setAttribute("y", yy - 10); t.setAttribute("class", "tick"); t.textContent = x.name; svg.appendChild(t); });
}
