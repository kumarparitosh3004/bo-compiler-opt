/* pages-project.js - search space, architecture, algorithm, parameters, novelty,
   real-world data, study results, manuscript, programs, history. */
"use strict";

// ---------- Search space ----------------------------------------------------------
addRoute(/^#\/space/, spacePage, "space", "Search space");
async function spacePage() {
  const flags = INFO.flags, active = flags.filter((f) => f.active);
  const C = palette();
  const progs = INFO.benchmarks.filter((b) => !b.custom && !b.real_data).map((b) => b.name);
  view.innerHTML = pageHead("", "Search space", "Build a configuration and see the exact compiler command.")
    + `<div class="grid g4" style="margin-bottom:20px">${kpi("Dimensions", INFO.dim, "1 base-level bit + flags", "grid", C.brand)}${kpi("Configurations", fmtInt(INFO.n_configs), "2^" + INFO.dim + " before constraints", "hash", C.bo)}${kpi("Flags in search", active.length, `of ${flags.length} candidates verified`, "check", C.good)}${kpi("Pass ordering", "fixed", "GCC's pass order is internal", "layers", C.lvl)}</div>`
    + card("Configuration builder", `<p class="muted small">Toggle bits to build a configuration. Highlighted bits differ from -O3; faded bits are disabled by a dependency rule.</p>
      <div class="bits" id="bits"></div>
      <div class="flex" style="margin:14px 0"><button class="btn sm" data-load="O3">Load -O3</button><button class="btn sm" data-load="O2">Load -O2</button><button class="btn sm" data-load="rnd">${icon("shuffle")}Random</button><span class="spacer"></span><span class="mono small" id="bitkey"></span></div>
      <div class="grid g2"><div><h3>Command line passed to GCC</h3><div class="flags" id="cmd"></div></div><div><h3>Changes from -O3</h3><div class="flags" id="diff"></div></div></div>
      <div class="flex" style="margin-top:14px"><select id="vprog">${benchOptions()}</select><button class="btn primary" id="vgo">${icon("verify")}Measure this configuration vs -O3</button><span id="vmsg"></span></div>`)
    + `<div class="grid g2">`
    + card("Flag reference", `<div class="table-wrap"><table><thead><tr><th>Flag</th><th class="num">-O2</th><th class="num">-O3</th><th>Status</th></tr></thead><tbody>${flags.map((f) => `<tr data-tip="${esc(f.what)}${f.side_effects.length ? "<br>spelling it out also changes: " + esc(f.side_effects.join(", ")) : ""}"><td><code>-f${esc(f.name)}</code><div class="muted small">${esc(f.what)}</div></td><td class="num">${f.default.O2 ? chip("on", "ok") : chip("off", "plain")}</td><td class="num">${f.default.O3 ? chip("on", "ok") : chip("off", "plain")}</td><td>${f.active ? chip("searched", "info") : `<span class="muted small">screened out</span>`}</td></tr>`).join("")}</tbody></table></div>`, { flush: true, sub: "defaults read from gcc -Q --help=optimizers" })
    + card("Flag impact", `<div class="chart" id="impact" style="overflow-x:auto"></div><p class="muted small" style="margin-top:8px">Filled: flipping the flag alone changes that program's binary. Flags with no effect are excluded.</p>`)
    + `</div>` + card("Dependency rules", `<div id="deps"></div>`);
  // builder
  const names = ["base"].concat(active.map((f) => f.name));
  const def = (lvl) => [lvl === "O3" ? 1 : 0].concat(active.map((f) => f.default[lvl] ? 1 : 0));
  const req = Object.fromEntries(active.map((f) => [f.name, (f.requires || []).filter((r) => names.includes(r))]));
  let x = def("O3");
  const canon = (v) => { v = [...v]; let ch = true; while (ch) { ch = false; active.forEach((f, i) => { if (v[i + 1] && req[f.name].some((r) => !v[names.indexOf(r)])) { v[i + 1] = 0; ch = true; } }); } return v; };
  const flagsOf = (v) => { const lvl = v[0] ? "O3" : "O2"; return [`-${lvl}`].concat(active.filter((f, i) => v[i + 1] !== (f.default[lvl] ? 1 : 0)).map((f, i2) => (v[names.indexOf(f.name)] ? "-f" : "-fno-") + f.name)); };
  const render = () => {
    x = canon(x); const ref = def("O3");
    $("#bits").innerHTML = names.map((n, i) => {
      const forced = i > 0 && req[n].some((r) => !x[names.indexOf(r)]);
      return `<div class="bit ${x[i] ? "on" : ""} ${forced ? "forced" : ""} ${x[i] !== ref[i] ? "diff" : ""}" data-i="${i}" data-tip="${i === 0 ? "base level: 0 = -O2, 1 = -O3" : "-f" + esc(n)}${forced ? "<br>forced off: needs " + esc(req[n].join(", ")) : ""}"><div class="b">${x[i]}</div><div class="n">${i === 0 ? "-O2/-O3" : esc(n)}</div></div>`;
    }).join("");
    $$("#bits .bit").forEach((b) => b.onclick = () => { if (b.classList.contains("forced")) return; const i = +b.dataset.i; x[i] ^= 1; render(); });
    attachTips($("#bits"));
    $("#bitkey").textContent = "key " + x.join("");
    const fl = flagsOf(x); $("#cmd").textContent = "gcc " + fl.join(" ") + " prog.c";
    const d = []; if (x[0] !== ref[0]) d.push("base -O2"); active.forEach((f, i) => { if (x[i + 1] !== ref[i + 1]) d.push((x[i + 1] ? "+" : "-") + f.name); });
    $("#diff").innerHTML = d.length ? diffHtml(d.join(" ")) : '<span class="muted">same as -O3: this vector builds a byte-identical executable to plain -O3</span>';
  };
  $$("[data-load]").forEach((b) => b.onclick = () => { x = b.dataset.load === "rnd" ? names.map(() => (Math.random() < 0.5 ? 1 : 0)) : def(b.dataset.load); render(); });
  $("#vgo").onclick = async () => {
    try { const j = await post("/api/jobs", { type: "compare", bench: $("#vprog").value, reps: INFO.defaults.compare_reps, candidates: [{ name: "O2", flags: ["-O2"] }, { name: "custom", flags: flagsOf(x) }] }); location.hash = `#/compare/${j[0].id}`; }
    catch (e) { $("#vmsg").innerHTML = errorBox(e); }
  };
  render();
  // impact grid
  const cw = 64, chh = 24, L = 210, T = 70, W = L + progs.length * cw + 10, H = T + flags.length * chh + 10;
  let s = `<svg viewBox="0 0 ${W} ${H}" style="min-width:${W * 0.8}px">`;
  progs.forEach((p, j) => s += `<text class="tick" transform="translate(${L + j * cw + cw / 2} ${T - 8}) rotate(-35)" style="font-size:11.5px">${esc(p)}</text>`);
  flags.forEach((f, i) => {
    s += `<text class="tick" x="${L - 10}" y="${T + i * chh + 16}" text-anchor="end" style="font-family:var(--mono);font-size:11px;${f.active ? "" : "opacity:.55"}">-f${esc(f.name)}</text>`;
    progs.forEach((p, j) => { const on = (f.binaries_changed || []).includes(p); s += `<rect x="${L + j * cw + 3}" y="${T + i * chh + 3}" width="${cw - 6}" height="${chh - 6}" rx="4" fill="${on ? C.bo : C.surface3}" opacity="${on ? 0.85 : 1}" data-tip="-f${esc(f.name)} on ${esc(p)}: ${on ? "binary changes" : "no change"}"/>`; });
  });
  $("#impact").innerHTML = s + "</svg>"; attachTips($("#impact"));
  // dependency rules
  const deps = flags.filter((f) => (f.requires || []).length);
  $("#deps").innerHTML = deps.length ? `<svg class="diagram" viewBox="0 0 760 ${90 * deps.length}">${deps.map((f, i) => `<g class="node"><rect x="20" y="${18 + i * 90}" width="260" height="52" rx="10"/><text x="150" y="${50 + i * 90}" text-anchor="middle">-f${esc(f.requires[0])}</text></g>
      <path class="edge" d="M280 ${44 + i * 90}H470" marker-end="url(#ah2)"/><text class="edge-label" x="375" y="${36 + i * 90}" text-anchor="middle">must be on for</text>
      <g class="node"><rect x="480" y="${18 + i * 90}" width="260" height="52" rx="10"/><text x="610" y="${50 + i * 90}" text-anchor="middle">-f${esc(f.name)}</text></g>`).join("")}
      <defs><marker id="ah2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="${css("--ink-3")}"/></marker></defs></svg>
      <p class="muted small">A vector with the dependent flag on but its prerequisite off builds the same binary as one with both off, so the search treats them as one point. This removes duplicate evaluations.</p>` : emptyState("No dependency rules");
  attachTips(view);
}

// ---------- Architecture ----------------------------------------------------------
const ARCH = [
  { id: "spa", layer: 0, x: 40, w: 300, t: "Single-page web app", f: "web/static/*.js · index.html", d: "Vanilla HTML/CSS/JS + hand-drawn SVG charts, with no build step and no CDN dependency. Hash routing, live polling, toasts, light/dark theme.", tech: "HTML5, CSS, JavaScript, SVG" },
  { id: "learn", layer: 0, x: 380, w: 300, t: "Interactive visualizations", f: "core.js · pages-*.js", d: "Convergence charts, configuration matrix, forest plots, GP demo, architecture diagram.", tech: "SVG" },
  { id: "api", layer: 1, x: 40, w: 220, t: "REST API (Flask)", f: "web/app.py", d: "JSON endpoints: info, jobs, runs, curves, compare, corpus, params, manuscript. Validates every request; compiler flags are checked against an allow-list.", tech: "Python 3.12, Flask" },
  { id: "jobs", layer: 1, x: 290, w: 200, t: "Job queue", f: "web/jobs.py", d: "One worker thread runs one job at a time so timings never interfere. Jobs persist to jobs.json and can be cancelled.", tech: "threading, queue" },
  { id: "custom", layer: 1, x: 520, w: 200, t: "Program upload", f: "web/custom.py", d: "Registers user C programs: compiles at -O0/-O3, checks the outputs agree, picks kernel or wall-clock timing.", tech: "GCC, SHA-256" },
  { id: "orch", layer: 2, x: 40, w: 200, t: "Orchestrator", f: "bopass/orchestrator.py", d: "The search loop: ask → evaluate → objective → store → tell, with budget, wall-clock cap, cancel hook, resume and manifests.", tech: "Python" },
  { id: "opt", layer: 2, x: 270, w: 200, t: "Optimizer", f: "bopass/optimizer/*.py", d: "BayesOpt: GP (Matérn 5/2 ARD + noise) + Expected Improvement over a candidate pool. RandomSearch is the control. Both use an ask/tell interface.", tech: "scikit-learn, SciPy, NumPy" },
  { id: "space", layer: 2, x: 500, w: 220, t: "Search space", f: "bopass/space.py", d: "Bit-vector encoding, dependency canonicalization, sampling, 1-bit neighbours, side-effect-aware flag emission.", tech: "NumPy" },
  { id: "eval", layer: 3, x: 40, w: 160, t: "Evaluator", f: "bopass/evaluator.py", d: "Compile → binary-hash cache → paired measurement → correctness → record. Retries transient timeouts.", tech: "Python" },
  { id: "cc", layer: 3, x: 220, w: 160, t: "Compiler driver", f: "bopass/compiler_driver.py", d: "Builds the command, compiles with a timeout, records compile time, .text size and SHA-256.", tech: "GCC 16.1, binutils" },
  { id: "run", layer: 3, x: 400, w: 160, t: "Runner", f: "bopass/runner.py · proc.py", d: "Warm-up + timed rounds, paired A-B/B-A runs against -O3, kills the whole process tree on timeout.", tech: "subprocess" },
  { id: "chk", layer: 3, x: 580, w: 140, t: "Correctness", f: "bopass/correctness.py", d: "Checksum vs the -O0 reference (exact or 1e-9 relative); archives failing binaries.", tech: "Python" },
  { id: "store", layer: 4, x: 40, w: 220, t: "Results store", f: "bopass/storage.py · results/", d: "Append-only CSV per run + JSON manifest (compiler, versions, seeds). Survives crashes and resumes.", tech: "CSV, JSON, pandas" },
  { id: "stats", layer: 4, x: 290, w: 200, t: "Statistics", f: "bopass/stats.py · compare.py", d: "Bootstrap CI of the median ratio, Mann–Whitney U, geometric mean, noise-floor verdicts, interleaved comparison.", tech: "SciPy" },
  { id: "bench", layer: 4, x: 520, w: 200, t: "Benchmarks & data", f: "benchmarks/ · config/", d: "9 C programs (6 synthetic kernels + 3 on a real-world corpus), reference outputs, verified flag catalog, frozen settings.", tech: "C11" },
];
const ARCH_EDGES = [["spa", "api", "REST / JSON"], ["learn", "api", ""], ["api", "jobs", "submit"], ["api", "custom", ""], ["jobs", "orch", "run job"], ["orch", "opt", "ask / tell"], ["opt", "space", ""], ["orch", "eval", "evaluate x"], ["eval", "cc", ""], ["eval", "run", ""], ["eval", "chk", ""], ["orch", "store", "append"], ["api", "store", ""], ["run", "stats", ""], ["cc", "bench", ""]];
const LAYERS = ["FRONT END · BROWSER", "BACKEND · FLASK SERVER", "BO ENGINE · bopass", "EXECUTION · GCC + PROGRAMS", "DATA & ANALYSIS"];

addRoute(/^#\/architecture/, architecture, "architecture", "Architecture");
async function architecture() {
  const LH = 112, top = 30;
  const pos = Object.fromEntries(ARCH.map((n) => [n.id, { x: n.x, y: top + n.layer * LH + 30, w: n.w, h: 58 }]));
  let s = `<svg class="diagram" viewBox="0 0 760 ${top + LAYERS.length * LH + 10}" role="img" aria-label="system architecture">
    <defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="${css("--ink-3")}"/></marker></defs>`;
  LAYERS.forEach((l, i) => s += `<g class="layer"><rect x="20" y="${top + i * LH + 6}" width="720" height="${LH - 12}" rx="12"/><text x="34" y="${top + i * LH + 22}">${l}</text></g>`);
  for (const [a, b, label] of ARCH_EDGES) {
    const p = pos[a], q = pos[b];
    const x1 = p.x + p.w / 2, y1 = p.y + p.h, x2 = q.x + q.w / 2, y2 = q.y;
    const same = Math.abs(p.y - q.y) < 5;
    const d = same ? `M${p.x + p.w} ${p.y + p.h / 2}H${q.x}` : `M${x1} ${y1}C${x1} ${(y1 + y2) / 2} ${x2} ${(y1 + y2) / 2} ${x2} ${y2}`;
    s += `<path class="edge" d="${d}" marker-end="url(#ah)"/>`;
    if (label && !same) s += `<text class="edge-label halo" x="${(x1 + x2) / 2 + 6}" y="${(y1 + y2) / 2 + 4}">${esc(label)}</text>`;
  }
  ARCH.forEach((n) => { const p = pos[n.id]; s += `<g class="node" data-id="${n.id}"><rect x="${p.x}" y="${p.y}" width="${p.w}" height="${p.h}" rx="10"/><text x="${p.x + p.w / 2}" y="${p.y + 25}" text-anchor="middle">${esc(n.t)}</text><text class="sub" x="${p.x + p.w / 2}" y="${p.y + 43}" text-anchor="middle">${esc(n.f.length > 30 ? n.f.slice(0, 29) + "…" : n.f)}</text></g>`; });
  s += `</svg>`;
  const endpoints = [["GET", "/api/info", "compiler, flag space, programs, defaults"], ["GET", "/api/dashboard", "aggregate KPIs and leaderboard"], ["POST", "/api/jobs", "queue a search (bo / random / both, one or all programs) or a comparison"], ["GET", "/api/jobs/{id}", "job status and live progress"], ["POST", "/api/jobs/{id}/cancel", "cancel a queued or running job"], ["GET", "/api/runs", "every search, from the study and the website"], ["GET", "/api/runs/{src}/{id}", "evaluations, manifest, summary, log"], ["GET", "/api/runs/{src}/{id}/csv", "download raw evaluations"], ["GET", "/api/curves?bench=", "best-so-far curves for BO vs Random"], ["GET", "/api/compare/{job}", "interleaved comparison result with statistics"], ["POST", "/api/benchmarks", "upload a C program"], ["GET", "/api/corpus", "real-world data provenance and statistics"], ["GET", "/api/params", "experiment parameters"], ["GET", "/api/results", "study tables and figures"], ["GET", "/api/manuscript", "download the manuscript (.docx)"]];
  view.innerHTML = pageHead("", "Architecture", "Components, data flow and API. Select a component for details.")
    + `<div class="grid g-2-1">${card("Component diagram", `<div id="arch">${s}</div>`)}<div>${card("Component", `<div id="adetail"></div>`)}${card("Tech stack", `<table><tbody>${[["Front end", "HTML5 · CSS (custom design system) · vanilla JS · SVG"], ["Backend", "Python 3.12 · Flask 3 · threaded job queue"], ["Algorithm", "Gaussian process (scikit-learn) · Expected Improvement · SciPy"], ["Data", "CSV + JSON manifests · pandas · real-world text corpus"], ["Compiler", esc(INFO.compiler_version)], ["Quality", "pytest: unit, integration and web end-to-end tests"]].map(([k, v]) => `<tr><td class="muted small" style="width:110px">${k}</td><td class="small">${v}</td></tr>`).join("")}</tbody></table>`, { flush: true })}</div></div>`
    + `<div class="grid g2">` + card("Request lifecycle", `<ol class="small ink2" style="margin:0;padding-left:18px;line-height:1.9">
        <li>The browser <code>POST</code>s <code>/api/jobs</code>. Flask validates it and the job is queued.</li><li>The worker thread picks it up and calls <code>run_search()</code>.</li>
        <li>The orchestrator builds the -O3 reference executable and the initial design (-O3 + random points).</li>
        <li>Loop: <code>optimizer.ask()</code> → evaluator compiles, deduplicates by SHA-256, checks output, runs the paired timing → <code>y = ln(ratio)</code> → appended to CSV → <code>optimizer.tell()</code>.</li>
        <li>The browser polls <code>/api/runs/web/{id}</code> and redraws the chart, matrix and table live.</li><li>At the end, the summary and GP length scales are saved and a toast announces the result.</li></ol>`)
    + card("REST API", `<div class="table-wrap" style="max-height:380px"><table><tbody>${endpoints.map(([m, p, d]) => `<tr><td>${chip(m, m === "GET" ? "info" : "warn")}</td><td class="mono small">${esc(p)}</td><td class="small ink2">${esc(d)}</td></tr>`).join("")}</tbody></table></div>`, { flush: true }) + `</div>`;
  const show = (id) => {
    const n = ARCH.find((a) => a.id === id);
    $$("#arch .node").forEach((g) => g.classList.toggle("sel", g.dataset.id === id));
    $("#adetail").innerHTML = `<div class="muted small" style="margin-bottom:4px">${esc(LAYERS[n.layer].toLowerCase().replace(/^\w/, (c) => c.toUpperCase()))}</div><h2 style="margin-bottom:8px">${esc(n.t)}</h2><p class="ink2">${esc(n.d)}</p><table class="small"><tbody><tr><td class="muted">Files</td><td class="mono">${esc(n.f)}</td></tr><tr><td class="muted">Tech</td><td>${esc(n.tech)}</td></tr></tbody></table>`;
  };
  $$("#arch .node").forEach((g) => g.addEventListener("click", () => show(g.dataset.id)));
  show("opt");
}

// ---------- How BO works (interactive 1-D demo) -------------------------------------
addRoute(/^#\/learn/, learn, "learn", "How BO works");
async function learn() {
  view.innerHTML = pageHead("", "How it works", "Bayesian Optimization spends each expensive compile-and-run where a model expects the most gain.")
    + `<div class="grid g-2-1">` + card("Interactive example", `<p class="muted small">Dashed: the hidden objective. Line and band: the model's prediction and uncertainty. Below: Expected Improvement, which picks the next measurement.</p>
      <div class="chart" id="gp1"></div><div class="chart" id="gp2"></div>
      <div class="flex" style="margin-top:10px"><button class="btn primary" id="g-next">${icon("bolt")}Next evaluation (max EI)</button><button class="btn" id="g-rand">${icon("shuffle")}Random evaluation</button><button class="btn ghost" id="g-reset">Reset</button><span class="spacer"></span>
      <label class="field" style="flex-direction:row;align-items:center;gap:8px">length scale <input type="range" id="g-ls" min="0.03" max="0.3" step="0.01" value="0.1" style="width:110px"></label>
      <label class="flex small"><input type="checkbox" id="g-true" checked> show hidden function</label></div>
      <div class="flex small muted" id="g-stat" style="margin-top:8px"></div>`)
    + `<div>` + card("The objective", `<div class="formula">y(x) = ln( median<sub>r</sub> t<sub>r</sub>(x) / t<sub>r</sub>(−O3) )</div><p class="small ink2">Minimized. Each configuration x is timed in rounds r that alternate with -O3, so changes in machine speed cancel out. y = −0.05 means about 4.9% faster than -O3.</p>`)
      + card("Expected Improvement", `<div class="formula">EI(x) = (y* − μ − ξ)·Φ(Z) + σ·φ(Z)<br><span style="font-size:14px">Z = (y* − μ − ξ) / σ</span></div><p class="small ink2">μ, σ: the GP's prediction; y*: the best so far; ξ = 0.01. EI is high where the model predicts a good value (exploitation) or is unsure (exploration).</p>`) + `</div></div>`
    + `<div class="grid g2">` + card("The search loop", `<div class="pseudo"><span class="kw">def</span> run_search(program, budget=50):
    X = [x_O3] + random_valid_configs(7)    <span class="cm"># shared with random search</span>
    <span class="kw">for</span> t <span class="kw">in</span> range(budget):
        x = X.pop(0) <span class="kw">if</span> X <span class="kw">else</span> bo.ask()     <span class="cm"># GP + EI</span>
        exe = gcc(base_level(x) + changed_flags(x))
        <span class="kw">if</span> sha256(exe) <span class="kw">in</span> cache:  y = cache[sha256(exe)]
        <span class="kw">elif</span> output(exe) != reference:  y = <span class="kw">FAIL</span>
        <span class="kw">else</span>:  y = ln(median(paired_ratios(exe, exe_O3)))
        bo.tell(x, y)                       <span class="cm"># failures: worst + 1</span>
    <span class="kw">return</span> argmin(y)</div>`)
      + card("Inside bo.ask()", `<div class="pseudo"><span class="kw">def</span> ask():
    gp = GaussianProcess(Matern(ν=2.5, one length
                         scale per bit) + WhiteNoise)
    gp.fit(X_seen, y_seen)
    pool  = 2000 random valid unseen configs
    pool += 1-bit neighbours of the best 5
    μ, σ  = gp.predict(pool)
    <span class="kw">return</span> pool[argmax(EI(μ, σ, y_best))]</div>
        <p class="small ink2" style="margin-top:10px">The space is binary, so EI is maximized over a candidate pool, not by gradients. The per-bit length scales show afterwards which flags mattered.</p>`) + `</div>`;
  // ----- tiny GP in JS -----
  const f = (x) => 0.55 * Math.sin(3 * Math.PI * x) * Math.exp(-0.6 * x) + 0.25 * Math.sin(10 * Math.PI * x + 1) + 0.1;
  const grid = Array.from({ length: 241 }, (_, i) => i / 240);
  let pts = [[0.08, f(0.08)], [0.5, f(0.5)], [0.93, f(0.93)]];
  const kern = (a, b, ls) => Math.exp(-((a - b) ** 2) / (2 * ls * ls));
  function gp(ls) {
    const n = pts.length, ys = pts.map((p) => p[1]), mu0 = ys.reduce((a, b) => a + b, 0) / n;
    const K = pts.map((p, i) => pts.map((q, j) => kern(p[0], q[0], ls) * 0.12 + (i === j ? 1e-4 : 0)));
    const Lm = Array.from({ length: n }, () => Array(n).fill(0));
    for (let i = 0; i < n; i++) for (let j = 0; j <= i; j++) { let s = K[i][j]; for (let k = 0; k < j; k++) s -= Lm[i][k] * Lm[j][k]; Lm[i][j] = i === j ? Math.sqrt(Math.max(s, 1e-12)) : s / Lm[j][j]; }
    const solveL = (b) => { const x = []; for (let i = 0; i < n; i++) { let s = b[i]; for (let k = 0; k < i; k++) s -= Lm[i][k] * x[k]; x.push(s / Lm[i][i]); } return x; };
    const solveLT = (b) => { const x = Array(n).fill(0); for (let i = n - 1; i >= 0; i--) { let s = b[i]; for (let k = i + 1; k < n; k++) s -= Lm[k][i] * x[k]; x[i] = s / Lm[i][i]; } return x; };
    const alpha = solveLT(solveL(ys.map((y) => y - mu0)));
    return grid.map((g) => { const ks = pts.map((p) => kern(g, p[0], ls) * 0.12); const m = mu0 + ks.reduce((a, k, i) => a + k * alpha[i], 0); const v = solveL(ks); const var_ = Math.max(1e-10, 0.12 - v.reduce((a, b) => a + b * b, 0)); return [g, m, Math.sqrt(var_)]; });
  }
  const Phi = (z) => 0.5 * (1 + erf(z / Math.SQRT2)), phi = (z) => Math.exp(-z * z / 2) / Math.sqrt(2 * Math.PI);
  function erf(x) { const t = 1 / (1 + 0.3275911 * Math.abs(x)); const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x); return x >= 0 ? y : -y; }
  let nextX = null;
  function draw() {
    const ls = +$("#g-ls").value, post_ = gp(ls), best = Math.max(...pts.map((p) => p[1])), C = palette();
    const ei = post_.map(([x, m, s]) => { const imp = m - best - 0.01, z = imp / s; return [x, s > 1e-9 ? Math.max(0, imp * Phi(z) + s * phi(z)) : 0]; });
    nextX = ei.reduce((a, b) => (b[1] > a[1] ? b : a))[0];
    const lines = [{ color: C.bo, data: post_.map((p) => [p[0], p[1]]), width: 2.6 }];
    if ($("#g-true").checked) lines.unshift({ color: C.ink3, dash: true, width: 1.6, data: grid.map((x) => [x, f(x)]) });
    drawChart($("#gp1"), { height: 270, zero: false, xMin: 0, xMax: 1, yMin: -0.9, yMax: 1.1, lines, bands: [{ color: C.bo, data: post_.map(([x, m, s]) => [x, m - 2 * s, m + 2 * s]) }],
      points: pts.map(([x, y], i) => ({ x, y, color: i === pts.length - 1 && pts.length > 3 ? C.random : C.lvl, r: 6, tip: `measurement ${i + 1}: f(${num(x, 3)}) = ${num(y, 3)}` })).concat([{ x: nextX, y: -0.85, color: C.good, r: 6, tip: "next point chosen by EI" }]),
      refLines: [{ y: best, label: "best so far", color: C.good }], xLabel: "configuration (1-D toy)", yLabel: "objective (higher is better)" });
    drawChart($("#gp2"), { height: 150, zero: false, xMin: 0, xMax: 1, lines: [{ color: C.good, data: ei, width: 2.2 }], bands: [{ color: C.good, data: ei.map(([x, v]) => [x, 0, v]) }], xLabel: "", yLabel: "EI" });
    const trueBest = Math.max(...grid.map(f));
    $("#g-stat").innerHTML = `<span>${pts.length} evaluations</span>·<span>best found ${num(best, 3)}</span>·<span>true optimum ${num(trueBest, 3)}</span>·<span>gap ${num(trueBest - best, 3)}</span>`;
  }
  $("#g-next").onclick = () => { pts.push([nextX, f(nextX)]); draw(); };
  $("#g-rand").onclick = () => { const x = Math.random(); pts.push([x, f(x)]); draw(); };
  $("#g-reset").onclick = () => { pts = [[0.08, f(0.08)], [0.5, f(0.5)], [0.93, f(0.93)]]; draw(); };
  $("#g-ls").oninput = draw; $("#g-true").onchange = draw;
  draw();
}

// ---------- Parameters ------------------------------------------------------------
addRoute(/^#\/parameters/, parameters, "parameters", "Parameters");
async function parameters() {
  const p = await api("/api/params"), e = p.experiment, bo = p.bo;
  const row = (k, v, d) => `<tr><td class="mono small">${esc(k)}</td><td class="mono"><b>${esc(Array.isArray(v) ? v.join(", ") : v)}</b></td><td class="small ink2">${d}</td></tr>`;
  view.innerHTML = pageHead("", "Parameters", "Experiment settings and the metrics we report. Source: <code>config/experiment.yaml</code>.")
    + `<div class="grid g2">`
    + card("Search parameters", `<table><tbody>${row("budget", e.budget, "evaluations per search, initial design included")}${row("n_init", e.n_init, "initial points: -O3 + random valid configurations")}${row("seeds", e.seeds, "independent repetitions of every search")}${row("methods", e.methods, "BO and the random-search control")}${row("dimensions", p.dim, `search-space bits; ${fmtInt(p.n_configs)} configurations`)}</tbody></table>`, { flush: true })
    + card("Bayesian Optimization parameters", `<table><tbody>${row("surrogate", "GP, Matérn ν = 2.5", "one length scale per bit (ARD) + white-noise kernel")}${row("acquisition", "Expected Improvement", "for minimization of y")}${row("xi (ξ)", bo.xi, "exploration margin in EI")}${row("pool_size", bo.pool_size, "random unseen candidates scored per step")}${row("top_k_neighbours", bo.top_k_neighbours, "1-bit neighbours of the best k added to the pool")}${row("gp_restarts", bo.gp_restarts, "optimizer restarts for kernel hyperparameters")}${row("failure_penalty", e.failure_penalty, "failed config modelled as worst OK y + penalty")}</tbody></table>`, { flush: true })
    + card("Measurement parameters", `<table><tbody>${row("paired_reference", e.paired_reference, "alternate each config with -O3 (A-B, B-A)")}${row("warmup", e.warmup, "discarded warm-up rounds")}${row("search_reps", e.search_reps, "timed rounds per evaluation during search")}${row("final_reps", e.final_reps, "interleaved rounds in the final comparison")}${row("baseline_reps", e.baseline_reps, "runs per -O level for baselines")}${row("noise_floor_reps", e.noise_floor_reps, "runs of -O3 to estimate noise")}${row("cv_threshold", e.cv_threshold, "re-measure once if CV exceeds this")}${row("timeouts", `${e.compile_timeout_s} s compile`, `run: max(10× -O0 time, ${e.run_timeout_min_s} s), retried once`)}</tbody></table>`, { flush: true })
    + card("Environment (fixed)", `<table><tbody>${row("compiler", p.compiler_version, "every build")}${row("fixed flags", p.fixed_flags.join(" ") || "none", "added to every build")}${row("excluded", "-ffast-math, -Ofast, -march=native", "change semantics or target")}${row("flags", p.flags.length, p.flags.map((f) => "-f" + f).join(", "))}</tbody></table>`, { flush: true })
    + `</div>` + card("Reported metrics", `<table><thead><tr><th>Metric</th><th>Definition</th><th>Why</th></tr></thead><tbody>${[
      ["Speed-up vs -O3", "median t(-O3) / median t(config) over 15 interleaved rounds", "primary outcome, unit-free"],
      ["% change", "(t(-O3) − t(config)) / t(-O3) × 100", "readable form of the speed-up"],
      ["95% CI", "percentile bootstrap (10,000 resamples) of the ratio of medians", "uncertainty of the speed-up"],
      ["p-value", "two-sided Mann–Whitney U test, config vs -O3", "significance without normality assumptions"],
      ["Noise floor", "coefficient of variation of 30 runs of -O3", "smallest difference worth reporting"],
      ["Verdict", "faster / slower only if p < 0.05, CI excludes 1 and |Δ| > 2× noise floor", "avoids claiming noise as gains"],
      ["Geometric-mean speed-up", "exp(mean(ln speed-up)) across programs", "correct average of ratios"],
      ["Best@N", "best search-time % vs -O3 after N evaluations", "sample efficiency, BO vs random"],
      ["Evaluations to within 1%", "first evaluation whose best is within 1% of the run's final best", "convergence speed"],
      [".text size, compile time", "relative to -O3, from the final builds", "cost of the gain"],
      ["Unique binaries, failures", "per run", "search cost and robustness"],
    ].map(([a, b, c]) => `<tr><td><b>${a}</b></td><td class="small">${b}</td><td class="small ink2">${c}</td></tr>`).join("")}</tbody></table>`, { flush: true });
}

// ---------- Novelty ---------------------------------------------------------------
addRoute(/^#\/novelty/, novelty, "novelty", "Novelty");
async function novelty() {
  const [runs, res] = await Promise.all([api("/api/runs"), api("/api/results")]);
  const evals = runs.reduce((a, r) => a + r.evaluations, 0), uniq = runs.reduce((a, r) => a + (r.unique_binaries || 0), 0);
  const saved = evals ? 100 * (1 - uniq / evals) : null;
  const sp = res.stats && res.stats.self_pair_O3_ratio;
  const active = INFO.flags.filter((f) => f.active).length;
  const items = [
    ["hash", "Verified flag encoding", "Flags are passed only when they differ from the level's default, read from <code>gcc -Q</code>, so the -O3 vector reproduces -O3 exactly.", "100%", "byte-identical to plain -O2 / -O3"],
    ["scale", "Drift-cancelling measurement", "Each configuration alternates with -O3 in A-B / B-A rounds; the objective is the median per-round time ratio.", sp ? num(sp.mean, 3) : "≈1.000", "mean ratio of -O3 paired with itself"],
    ["layers", "Binary deduplication", "Executables are fingerprinted with SHA-256, so configurations that compile to identical code are measured once.", saved != null ? `${num(saved, 0)}%` : "–", "of evaluations reused a measurement"],
    ["verify", "Bias-aware verification", "Best configurations are rebuilt and re-timed in shuffled rounds, judged by a bootstrap CI, a Mann–Whitney test and the noise floor.", "15", "interleaved rounds per claim"],
    ["grid", "Screened search space", "Candidate flags are toggle-checked and kept only if they change at least one benchmark binary.", `${INFO.flags.length} → ${active}`, "candidate → effective flags"],
    ["database", "Real-world workloads", "Compression, SHA-256 and word-frequency analysis run on 3.5 MB of real human-written text; any C program can be added.", "3", "real-data programs"],
  ];
  view.innerHTML = pageHead("", "Contributions", "What PassTune adds beyond a standard optimizer, with the evidence for each.")
    + `<div class="grid g3">${items.map(([ic, t, d, val, label]) => `<section class="card contrib"><div class="card-body">
        <div class="stat-ic" style="margin-bottom:12px">${icon(ic)}</div><h3>${t}</h3><p class="small ink2" style="margin:0">${d}</p></div>
        <div class="contrib-foot"><span class="contrib-val">${val}</span><span class="muted small">${label}</span></div></section>`).join("")}</div>`
    + card("Related work", `<table><thead><tr><th>Approach</th><th>How it searches</th><th>What PassTune adds</th></tr></thead><tbody>
      <tr><td><b>Fixed levels</b> -O1 / -O2 / -O3</td><td class="small">one recipe for every program</td><td class="small ink2">per-program search, verified against -O3</td></tr>
      <tr><td><b>Iterative compilation</b> · Cooper et al., 1999</td><td class="small">genetic algorithms, many evaluations</td><td class="small ink2">model-based search with an equal-budget random control</td></tr>
      <tr><td><b>Milepost GCC</b> · Fursin et al., 2011</td><td class="small">predicts flags from program features</td><td class="small ink2">no training corpus; learns from measurements</td></tr>
      <tr><td><b>OpenTuner</b> · Ansel et al., 2014</td><td class="small">ensemble of search techniques</td><td class="small ink2">one explainable model with per-flag relevance</td></tr>
      <tr><td><b>BOCA</b> · Chen et al., 2021</td><td class="small">BO with a tree-based surrogate</td><td class="small ink2">drift-cancelling timing, verified encoding, binary dedup</td></tr>
      </tbody></table>`, { flush: true, right: `<a class="btn sm ghost" href="#/manuscript">References</a>` });
}

// ---------- Real-world data -------------------------------------------------------
addRoute(/^#\/data/, dataPage, "data", "Real-world data");
async function dataPage() {
  const c = await api("/api/corpus"), C = palette();
  if (!c.available) { view.innerHTML = pageHead("", "Datasets", "") + card("", emptyState("Corpus not built. Run python scripts/make_corpus.py")); return; }
  const prose = c.files.filter((f) => /prose/.test(f.what)).reduce((a, f) => a + f.bytes, 0), code = c.files.filter((f) => /source/.test(f.what)).reduce((a, f) => a + f.bytes, 0);
  const maxW = c.top_words[0][1];
  const progInfo = { compress: ["LZ77 / LZSS compressor", "gzip-style hash-chain match finder, then decompression and a byte-exact round-trip check"], sha256: ["SHA-256 (FIPS 180-4)", "cryptographic hashing chained across rounds, with a known-answer self-test"], wordfreq: ["Word-frequency analysis", "tokenize, count in an open-addressing hash table, rank the vocabulary"] };
  view.innerHTML = pageHead("", "Datasets", "Real human-written text used by the compress, sha256 and wordfreq workloads.")
    + `<div class="grid g4" style="margin-bottom:20px">${kpi("Corpus size", (c.bytes / 1e6).toFixed(2) + " MB", fmtInt(c.lines) + " lines", "database", C.brand)}${kpi("Words", fmtInt(c.words), fmtInt(c.distinct) + " distinct", "doc", C.bo)}${kpi("Sources", c.files.length, "files, fixed order", "file", C.random)}${kpi("Composition", Math.round((100 * prose) / (prose + code)) + "% prose", Math.round((100 * code) / (prose + code)) + "% source code", "chart", C.good)}</div>`
    + `<div class="grid g3" style="margin-bottom:0">${(c.programs || []).map((p) => card("", `<div class="feature"><div class="ic">${icon("cpu")}</div><div><b>${esc(progInfo[p.name] ? progInfo[p.name][0] : p.name)}</b><p>${esc(progInfo[p.name] ? progInfo[p.name][1] : "")}</p><p class="mono small" style="margin-top:6px">${esc(p.name)} ${esc(p.args.join(" "))}</p><div class="flex" style="margin-top:10px"><a class="btn sm primary" href="#/optimize?bench=${p.name}">${icon("play")}Optimize</a><a class="btn sm" href="#/duel?bench=${p.name}">BO vs Random</a></div></div></div>`)).join("")}</div>`
    + `<div class="grid g2">` + card("Provenance", `<div class="table-wrap"><table><thead><tr><th>File</th><th>Content</th><th class="num">Bytes</th><th>SHA-256</th></tr></thead><tbody>${c.files.map((f) => `<tr><td class="mono small">${esc(f.file)}</td><td class="small">${esc(f.what)}</td><td class="num mono small">${fmtInt(f.bytes)}</td><td class="mono small muted">${esc(f.sha)}</td></tr>`).join("")}</tbody></table></div><p class="muted small" style="padding:10px 16px">Corpus SHA-256 <span class="mono">${esc(c.sha256.slice(0, 32))}…</span> · Python Software Foundation License</p>`, { flush: true })
    + card("Most frequent words", c.top_words.map(([w, n]) => `<div class="bar-row" style="grid-template-columns:110px 1fr 70px"><span class="mono">${esc(w)}</span><div class="track"><div class="fill" style="width:${(100 * n) / maxW}%;background:${C.random}"></div></div><span class="mono small">${fmtInt(n)}</span></div>`).join(""), { sub: "computed live from the corpus" }) + `</div>`
    + card("Excerpt", `<div class="code" style="max-height:260px">${esc(c.excerpt).split("\n").map((l) => `<div>${l || " "}</div>`).join("")}</div>`);
}

// ---------- Study results ---------------------------------------------------------
addRoute(/^#\/results/, results, "results", "Study results");
async function results() {
  const r = await api("/api/results"), T = r.tables, s = r.stats || {};
  if (!Object.keys(T).length) {
    view.innerHTML = pageHead("", "Results", "") + notice(r.sweep_running ? "warn" : "info", r.sweep_running ? "The study is still running. Results appear here when the analysis finishes." : "No results yet. Run the study from the command line (see EXPERIMENTS.md).");
    return;
  }
  const v = s.verdict_counts || {}, vc = (m) => (v[m] ? `${v[m].faster || 0} faster · ${v[m]["no measurable difference"] || 0} tie · ${v[m].slower || 0} slower` : "–");
  const tabs = [
    ["T2_main_results", "Summary", "Speed-up vs -O3 after interleaved re-measurement, median of seeds."],
    ["T2b_per_seed", "Per run", "Every run's best configuration with its confidence interval and significance."],
    ["T5_generalization", "Larger input", "The same binaries on an input about 2× larger."],
    ["T3b_sample_efficiency", "Efficiency", "Best found so far after 10, 20 and 50 evaluations (search-time)."],
    ["T3_search_cost", "Cost", "Search cost per run, mean of seeds."],
    ["T4_best_configs", "Configurations", "Flags that differ from -O3 in each run's best configuration."],
    ["T1_baselines", "Baselines", "Median run time at each optimization level."],
  ].filter(([k]) => T[k]);
  const caps = { F1: "Final comparison against -O3", F2: "Convergence during search", F3: "Flag relevance learned by the model", F4: "Binary size vs run time" };
  if (r.figures.length) tabs.push(["__figures", "Figures", "Static figures generated by scripts/make_plots.py."]);
  const g = s.geomean_speedup_vs_O3_bo, gr = s.geomean_speedup_vs_O3_random;
  view.innerHTML = pageHead("", "Results", `${fmtInt(s.total_evaluations)} evaluations · ${INFO.benchmarks.filter((b) => !b.custom).length} programs · ${INFO.study.seeds.length} seeds per method`,
      `<a class="btn" href="#/manuscript">${icon("doc")}Paper</a>`)
    + `<div class="grid g4" style="margin-bottom:20px">
        ${kpi("BO speed-up", g != null ? `×${num(g, 3)}` : "–", g != null ? `<span class="delta">+${num((g - 1) * 100, 1)}%</span> geometric mean vs -O3` : "", "target")}
        ${kpi("Random speed-up", gr != null ? `×${num(gr, 3)}` : "–", gr != null ? `<span class="delta flat">+${num((gr - 1) * 100, 1)}%</span> geometric mean vs -O3` : "", "shuffle")}
        ${kpi("BO verdicts", `${(v.bo && v.bo.faster) || 0} <span class="muted" style="font-size:15px">significant</span>`, vc("bo"), "verify")}
        ${kpi("Search time", `${s.total_search_wall_time_h ?? "–"} h`, `${fmtInt(s.total_evaluations)} evaluations`, "cpu")}
      </div>
      <section class="card"><div class="tabs-inline" id="rt">${tabs.map(([k, label], i) => `<button data-k="${k}" class="${i ? "" : "active"}">${esc(label)}</button>`).join("")}</div><div id="rtb"></div></section>`;
  const show = (k) => {
    const [, , desc] = tabs.find((t) => t[0] === k);
    if (k === "__figures") {
      $("#rtb").innerHTML = `<div style="padding:14px 20px 0" class="muted small">${esc(desc)}</div><div class="grid g2" style="padding:16px 20px 20px">${r.figures.map((f) => `<figure class="figure" style="margin:0"><img src="/figures/${encodeURIComponent(f)}?v=${Date.now()}" alt="${esc(caps[f.slice(0, 2)] || f)}"><figcaption>${esc(caps[f.slice(0, 2)] || f)}</figcaption></figure>`).join("")}</div>`;
      return;
    }
    const t = T[k];
    const isDiff = t.columns.map((c) => /vs -O3$|diff/i.test(c) && /flags|diff/i.test(c));
    $("#rtb").innerHTML = `<div style="padding:14px 20px 4px" class="muted small">${esc(desc)}</div><div class="table-wrap"><table><thead><tr>${t.columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${t.data.map((row) => `<tr>${row.map((val, ci) => {
      if (typeof val === "number") return `<td class="num mono">${esc(+val.toFixed(4))}</td>`;
      if (val === "faster" || val === "slower") return `<td>${chip(val)}</td>`;
      if (val === "no measurable difference") return `<td>${chip("tie", "plain")}</td>`;
      if (val == null) return "<td></td>";
      return isDiff[ci] ? `<td class="mono small">${diffHtml(String(val))}</td>` : `<td class="${/^[+-]?\d/.test(String(val)) ? "mono small" : ""}">${esc(val)}</td>`;
    }).join("")}</tr>`).join("")}</tbody></table></div>`;
  };
  $$("#rt button").forEach((b) => (b.onclick = () => { $$("#rt button").forEach((x) => x.classList.toggle("active", x === b)); show(b.dataset.k); }));
  if (tabs.length) show(tabs[0][0]);
}

// ---------- Manuscript ------------------------------------------------------------
function mdToHtml(md) {
  const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\*(.+?)\*/g, "<i>$1</i>").replace(/`(.+?)`/g, "<code>$1</code>");
  const out = []; let list = null, table = null;
  const flush = () => { if (list) { out.push(`<${list.t}>${list.items.map((i) => `<li>${inline(i)}</li>`).join("")}</${list.t}>`); list = null; } if (table) { out.push(`<div class="table-wrap" style="margin:10px 0"><table><thead><tr>${table[0].map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${table.slice(2).map((r) => `<tr>${r.map((c) => `<td class="small">${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`); table = null; } };
  for (const line of md.split("\n")) {
    let m;
    if (/^\|/.test(line)) { if (list) flush(); (table = table || []).push(line.split("|").slice(1, -1).map((c) => c.trim())); continue; }
    if (table) flush();
    if ((m = line.match(/^(#{1,4})\s+(.*)/))) { flush(); out.push(`<h${Math.min(m[1].length + 1, 4)} style="margin:18px 0 8px">${inline(m[2])}</h${Math.min(m[1].length + 1, 4)}>`); }
    else if ((m = line.match(/^\s*[-*]\s+(.*)/))) { if (!list || list.t !== "ul") { flush(); list = { t: "ul", items: [] }; } list.items.push(m[1]); }
    else if ((m = line.match(/^\s*\d+\.\s+(.*)/))) { if (!list || list.t !== "ol") { flush(); list = { t: "ol", items: [] }; } list.items.push(m[1]); }
    else if (!line.trim()) flush();
    else { flush(); out.push(`<p class="ink2">${inline(line)}</p>`); }
  }
  flush();
  return out.join("");
}
addRoute(/^#\/manuscript/, manuscriptPage, "manuscript", "Manuscript");
async function manuscriptPage() {
  const m = await api("/api/manuscript/info");
  // the web preview omits the author / affiliation block; the downloadable .docx keeps it
  const md = m.markdown ? m.markdown.split("\n").filter((l) => !/^(Authors|Affiliation|Contact):/.test(l)).join("\n") : null;
  view.innerHTML = pageHead("", "Paper", "Method, setup and measured results, in conference-paper format.", m.docx ? `<a class="btn primary" href="/api/manuscript">${icon("download")}Download .docx</a>` : "")
    + (md ? card("", `<article style="max-width:860px;margin:0 auto">${mdToHtml(md)}</article>`) : card("", emptyState("The paper is generated after the study finishes.", "doc")));
}

// ---------- Programs --------------------------------------------------------------
const TEMPLATE_KERNEL = `/* Timed like the built-in benchmarks: include the shared header and print
   CHECKSUM= and KERNEL_NS= (the timer covers only the kernel). */
#include <stdio.h>
#include <stdlib.h>
#include "../../common/bench_timer.h"

int main(int argc, char **argv) {
    int n = argc > 1 ? atoi(argv[1]) : 20000000;
    double *a = malloc((size_t)n * sizeof *a);
    for (int i = 0; i < n; i++) a[i] = (i % 1000) * 0.001;

    uint64_t t0 = bench_now_ns();
    double s = 0.0;
    for (int r = 0; r < 10; r++)
        for (int i = 0; i < n; i++) s += a[i] * a[i] + r;
    uint64_t t1 = bench_now_ns();

    bench_report_f64(s, t1 - t0);
    free(a);
    return 0;
}
`;
const TEMPLATE_PLAIN = `/* Any C program works: it is then timed as a whole process, and its output
   is checked against the -O0 build's output. Make it run for at least ~0.2 s. */
#include <stdio.h>

static unsigned collatz_len(unsigned long long x) {
    unsigned n = 0;
    while (x != 1) { x = (x & 1) ? 3 * x + 1 : x / 2; n++; }
    return n;
}

int main(void) {
    unsigned best = 0, arg = 0;
    for (unsigned i = 1; i < 3000000; i++) {
        unsigned l = collatz_len(i);
        if (l > best) { best = l; arg = i; }
    }
    printf("longest chain below 3,000,000 starts at %u (%u steps)\\n", arg, best);
    return 0;
}
`;
function modal(title, body) {
  const bg = document.createElement("div");
  bg.className = "modal-bg";
  bg.innerHTML = `<div class="modal"><div class="card-head"><h2>${title}</h2><div class="right"><button class="icon-btn" id="mclose">${icon("x")}</button></div></div><div class="card-body">${body}</div></div>`;
  document.body.appendChild(bg);
  const close = () => bg.remove();
  bg.addEventListener("click", (e) => { if (e.target === bg) close(); });
  $("#mclose", bg).onclick = close;
  document.addEventListener("keydown", function k(e) { if (e.key === "Escape") { close(); document.removeEventListener("keydown", k); } });
}
addRoute(/^#\/programs/, programs, "programs", "Programs");
async function programs() {
  await info(true);
  const kind = (b) => (b.custom ? chip("uploaded", "warn") : b.real_data ? chip("real data", "info") : chip("synthetic", "plain"));
  view.innerHTML = pageHead("", "Programs", "Built-in benchmarks, real-world workloads and your own C programs.")
    + card("Library", `<div class="table-wrap"><table><thead><tr><th>Program</th><th>Kind</th><th>Arguments</th><th>Timing</th><th class="num">-O3</th><th></th></tr></thead><tbody>${INFO.benchmarks.map((b) => `<tr><td><b>${esc(b.name)}</b><div class="mono small muted">${esc(b.source)}</div></td><td>${kind(b)}</td><td class="mono small">${esc(b.args.join(" ") || "–")}</td><td class="small">${b.timing === "kernel" ? "kernel timer" : "whole process"}</td><td class="num mono">${b.baseline_ms && b.baseline_ms.O3 != null ? num(b.baseline_ms.O3, 0) + " ms" : "–"}</td>
      <td><div class="flex" style="flex-wrap:nowrap"><button class="btn sm" data-src="${esc(b.name)}">${icon("code")}Source</button><a class="btn sm primary" href="#/optimize?bench=${encodeURIComponent(b.name)}">${icon("play")}Optimize</a>${b.custom ? `<button class="btn sm danger" data-del="${esc(b.name)}">Remove</button>` : ""}</div></td></tr>`).join("")}</tbody></table></div>`, { flush: true })
    + card("Add a program", `<form id="pf"><div class="form-row"><label class="field">Name<input name="name" placeholder="my_kernel" required pattern="[a-z][a-z0-9_]{0,31}"></label><label class="field" style="flex:1">Command-line arguments<input name="args" placeholder="e.g. 20000000"></label><button type="button" class="btn" id="t1">Template: kernel-timed</button><button type="button" class="btn" id="t2">Template: any program</button></div>
      <label class="field">Source code (.c)<textarea name="source" id="src" spellcheck="false" required></textarea></label>
      <div class="form-row" style="margin-top:12px"><label class="field">…or load a file<input type="file" id="file" accept=".c,.h,.txt"></label><span class="spacer"></span><button class="btn primary" type="submit" id="addbtn">${icon("check")}Compile, check and add</button></div><div id="pmsg"></div></form>`);
  $("#t1").onclick = () => { $("#src").value = TEMPLATE_KERNEL; $("[name=args]").value = "20000000"; };
  $("#t2").onclick = () => { $("#src").value = TEMPLATE_PLAIN; $("[name=args]").value = ""; };
  $("#file").onchange = async (e) => { const f = e.target.files[0]; if (f) $("#src").value = await f.text(); };
  $$("[data-src]").forEach((b) => b.onclick = async () => { const s = await api(`/api/source/${b.dataset.src}`); modal(`${icon("code")} ${esc(s.name)} <span class="muted mono small">${esc(s.path)}</span>`, `<div class="code">${esc(s.code).split("\n").map((l) => `<div>${l || " "}</div>`).join("")}</div>`); });
  $$("[data-del]").forEach((b) => b.onclick = async () => { if (confirm(`Remove ${b.dataset.del}?`)) { await api(`/api/benchmarks/${b.dataset.del}`, { method: "DELETE" }); programs(); } });
  $("#pf").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#addbtn"); btn.disabled = true; $("#pmsg").innerHTML = notice("info", "Compiling at -O0 and -O3 and running both…");
    try { const r = await post("/api/benchmarks", Object.fromEntries(new FormData(e.target))); $("#pmsg").innerHTML = notice("ok", `<b>${esc(r.name)}</b> added (${r.timing === "kernel" ? "kernel timer" : "whole-process timing"}). <a href="#/optimize?bench=${encodeURIComponent(r.name)}">Optimize it →</a>`); await info(true); }
    catch (err) { $("#pmsg").innerHTML = errorBox(err); }
    btn.disabled = false;
  });
}

// ---------- History ---------------------------------------------------------------
addRoute(/^#\/history/, historyPage, "history", "History");
async function historyPage() {
  const runs = await api("/api/runs");
  const benches = [...new Set(runs.map((r) => r.benchmark))].sort();
  view.innerHTML = pageHead("", "Runs", "Every search, from the study and from this app.")
    + card("Searches", `<div class="flex" style="padding:14px 16px;border-bottom:1px solid var(--border)"><select id="hb"><option value="">All programs</option>${benches.map((b) => `<option>${esc(b)}</option>`).join("")}</select><select id="hs"><option value="">All sources</option><option value="study">Study sweep</option><option value="web">Website</option></select><select id="hm"><option value="">Both methods</option><option value="bo">BO</option><option value="random">Random</option></select><span class="spacer"></span><span class="muted small" id="hcount"></span></div><div id="hl"></div>`, { flush: true });
  const render = () => {
    const b = $("#hb").value, s = $("#hs").value, m = $("#hm").value;
    const list = runs.filter((r) => (!b || r.benchmark === b) && (!s || r.source === s) && (!m || r.method === m));
    $("#hcount").textContent = `${list.length} searches`;
    $("#hl").innerHTML = list.length ? `<div class="table-wrap" style="max-height:640px"><table><thead><tr><th>Program</th><th>Method</th><th class="num">Seed</th><th>Source</th><th class="num">Evaluations</th><th class="num">Best (search)</th><th>Best changes from -O3</th></tr></thead><tbody>
      ${list.map((r) => `<tr class="clickable" data-go="#/run/${r.source}/${r.exp_id}"><td><b>${esc(r.benchmark)}</b></td><td>${methodChip(r.method)}</td><td class="num">${r.seed}</td><td class="small">${r.source === "study" ? "study" : "website"} ${r.finished ? "" : chip("unfinished", "warn")}</td><td class="num mono">${r.evaluations}/${r.budget}</td><td class="num mono">${sgn(r.best_pct)}</td><td class="mono small">${diffHtml(r.best_diff)}</td></tr>`).join("")}</tbody></table></div>` : emptyState("No searches match.", "history");
    $$("[data-go]").forEach((tr) => (tr.onclick = () => (location.hash = tr.dataset.go)));
  };
  ["#hb", "#hs", "#hm"].forEach((id) => $(id).addEventListener("change", render));
  render();
}

boot();
