"""Web app: run and inspect Bayesian Optimization of GCC flags from the browser.

usage:  python -m web.app            (from the project root)  ->  http://127.0.0.1:5000
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from flask import Flask, abort, jsonify, request, send_from_directory  # noqa: E402

from bopass.config import CONFIG_DIR, RESULTS_DIR, compiler_path, fixed_flags, load_experiment, load_yaml, resolve  # noqa: E402
from bopass.compiler_driver import compiler_version  # noqa: E402
from bopass.space import SearchSpace  # noqa: E402
from bopass.storage import ResultStore  # noqa: E402

from web import custom  # noqa: E402
from web.jobs import COMPARE_DIR, SEARCH_DIR, JobManager  # noqa: E402

STATIC = Path(__file__).parent / "static"
ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,120}$")
LEVELS = ("-O0", "-O1", "-O2", "-O3", "-Os")


def create_app(cfg: dict | None = None, jobs_store: Path | None = None) -> Flask:
    cfg = cfg or load_experiment()
    app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")
    app.config["JSON_SORT_KEYS"] = False
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0   # always serve the current frontend files
    cc = compiler_path(cfg)
    state = {"version": compiler_version(cc)}
    state["ok"] = state["version"] != "unknown" and "clang" not in state["version"].lower()
    no_gcc = "GCC was not found. On macOS install it with `brew install gcc` and restart the app."
    space = SearchSpace.from_yaml(resolve(cfg["flags_file"]))
    flags_doc = load_yaml(resolve(cfg["flags_file"]))
    allowed = set(LEVELS)
    for f in flags_doc["flags"]:
        allowed |= {"-f" + f["name"], "-fno-" + f["name"]}
    jobs = JobManager(cfg, jobs_store) if jobs_store else JobManager(cfg)
    app.extensions["bopass_jobs"] = jobs

    def err(msg, code=400):
        return jsonify({"error": msg}), code

    def clean(v):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return v

    # ---- pages ----------------------------------------------------------------------
    @app.get("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    @app.get("/figures/<path:name>")
    def figure(name):
        return send_from_directory(RESULTS_DIR / "figures", name)

    # ---- info -----------------------------------------------------------------------
    def baseline_ms() -> dict:
        p = RESULTS_DIR / "baselines" / "baselines.csv"
        if not p.exists():
            return {}
        df = pd.read_csv(p)
        out = {}
        for _, r in df.iterrows():
            out.setdefault(r.benchmark, {})[r.level] = clean(round(r.median_kernel_ns / 1e6, 2)) \
                if pd.notna(r.median_kernel_ns) else None
        return out

    def sweep_running() -> bool:
        p = RESULTS_DIR / "pipeline_log.txt"
        if not p.exists():
            return False
        lines = p.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        return bool(lines) and not lines[-1].startswith("exit")

    def bench_list():
        base = baseline_ms()
        cust = custom.custom_names()
        return [{"name": b.name, "args": [Path(a).name if b.real_data and Path(a).suffix == ".txt" else a for a in b.args],
                 "timing": b.timing, "custom": b.name in cust, "real_data": b.real_data,
                 "source": str(b.source.relative_to(ROOT)) if b.source.is_relative_to(ROOT) else b.name,
                 "baseline_ms": base.get(b.name, {})} for b in custom.all_benchmarks().values()]

    @app.get("/api/info")
    def info():
        return jsonify({
            "compiler": cc, "compiler_version": state["version"],
            "compiler_ok": state["ok"],
            "fixed_flags": fixed_flags(cfg), "dim": space.dim, "n_configs": 2 ** space.dim,
            "base_levels": list(space.base_levels),
            "flags": [{"name": f["name"], "what": f.get("what", ""), "default": f.get("default", {}),
                       "active": f.get("active", False), "binaries_changed": f.get("binaries_changed", []),
                       "side_effects": f.get("side_effects_when_explicit", []),
                       "requires": f.get("requires", [])} for f in flags_doc["flags"]],
            "benchmarks": bench_list(),
            "defaults": {"budget": 30, "reps": 3, "n_init": 6, "seed": 0, "compare_reps": 10},
            "study": {"budget": cfg["budget"], "seeds": cfg["seeds"], "methods": cfg["methods"]},
            "sweep_running": sweep_running(),
            "busy": jobs.busy(),
        })

    @app.get("/api/benchmarks")
    def benchmarks():
        return jsonify(bench_list())

    @app.post("/api/benchmarks")
    def add_benchmark():
        if not state["ok"]:
            return err(no_gcc, 503)
        d = request.get_json(force=True, silent=True) or {}
        args = d.get("args", [])
        if isinstance(args, str):
            args = args.split()
        try:
            entry = custom.register(d.get("name", ""), d.get("source", ""), args, cc, fixed_flags(cfg))
        except ValueError as e:
            return err(str(e))
        return jsonify(entry)

    @app.delete("/api/benchmarks/<name>")
    def delete_benchmark(name):
        try:
            custom.remove(name)
        except ValueError as e:
            return err(str(e))
        return jsonify({"ok": True})

    # ---- jobs -----------------------------------------------------------------------
    @app.get("/api/jobs")
    def list_jobs():
        out = jobs.list()
        for j in out:
            _live_progress(j)
        return jsonify(out)

    def _live_progress(j: dict):
        if j["type"] == "search" and j["exp_id"] and j["status"] == "running":
            n = len(ResultStore(SEARCH_DIR / j["exp_id"]).load())
            j["progress"] = {"done": n, "total": j["params"]["budget"]}
        return j

    @app.get("/api/jobs/<job_id>")
    def get_job(job_id):
        j = jobs.get(job_id)
        if j is None:
            abort(404)
        return jsonify(_live_progress(j))

    @app.post("/api/jobs/<job_id>/cancel")
    def cancel_job(job_id):
        if job_id not in jobs.jobs:
            abort(404)
        jobs.cancel(job_id)
        return jsonify(jobs.get(job_id))

    @app.post("/api/jobs")
    def submit_job():
        if not state["ok"]:
            return err(no_gcc, 503)
        d = request.get_json(force=True, silent=True) or {}
        benches = custom.all_benchmarks()
        kind = d.get("type", "search")
        if kind == "search":
            names = list(benches) if d.get("bench") == "all" else [d.get("bench")]
            if any(n not in benches for n in names):
                return err(f"unknown benchmark {d.get('bench')!r}")
            methods = ["bo", "random"] if d.get("method") == "both" else [d.get("method", "bo")]
            if any(m not in ("bo", "random") for m in methods):
                return err("method must be bo, random or both")
            try:
                budget = int(d.get("budget", 30))
                reps = int(d.get("reps", 3))
                n_init = int(d.get("n_init", 6))
                seed = int(d.get("seed", 0))
            except (TypeError, ValueError):
                return err("budget, reps, n_init and seed must be integers")
            if not (5 <= budget <= 200 and 1 <= reps <= 15 and 2 <= n_init <= 20 and n_init < budget and 0 <= seed <= 10**6):
                return err("allowed ranges: budget 5-200, reps 1-15, n_init 2-20 (and below budget), seed 0-1000000")
            created = [jobs.submit("search", {"bench": n, "method": m, "seed": seed, "budget": budget,
                                              "reps": reps, "n_init": n_init})
                       for n in names for m in methods]
            return jsonify([jobs.get(j.id) for j in created])
        if kind == "compare":
            name = d.get("bench")
            if name not in benches:
                return err(f"unknown benchmark {name!r}")
            cands = d.get("candidates") or []
            if not any(c.get("name") == "O3" for c in cands):
                cands = [{"name": "O3", "flags": ["-O3"]}] + cands
            if len(cands) > 12:
                return err("at most 12 candidates")
            for c in cands:
                fl = c.get("flags")
                if isinstance(fl, str):
                    fl = fl.split()
                c["flags"] = fl
                if not fl or fl[0] not in LEVELS or any(x not in allowed for x in fl):
                    return err(f"candidate {c.get('name')!r}: only -O levels and verified -f flags are allowed")
                c["name"] = str(c.get("name", ""))[:40] or " ".join(fl)
            try:
                reps = int(d.get("reps", 10))
            except (TypeError, ValueError):
                return err("reps must be an integer")
            if not 3 <= reps <= 30:
                return err("reps must be between 3 and 30")
            j = jobs.submit("compare", {"bench": name, "candidates": cands, "reps": reps,
                                        "kind": d.get("kind", "custom"), "source_runs": d.get("source_runs", [])})
            return jsonify([jobs.get(j.id)])
        return err("type must be search or compare")

    @app.get("/api/compare/<job_id>")
    def compare_result(job_id):
        if not ID_RE.match(job_id):
            abort(404)
        p = COMPARE_DIR / f"{job_id}.json"
        if not p.exists():
            abort(404)
        return jsonify(json.loads(p.read_text(encoding="utf-8")))

    # ---- runs (study sweep + web) --------------------------------------------------
    sources = {"study": RESULTS_DIR / "search", "web": SEARCH_DIR}

    def run_info(source: str, d: Path) -> dict | None:
        m = ResultStore(d).read_json("manifest.json")
        if m is None:
            return None
        s = ResultStore(d).read_json("summary.json") or {}
        n = sum(1 for _ in open(d / "evals.csv", encoding="utf-8")) - 1 if (d / "evals.csv").exists() else 0
        return {"source": source, "exp_id": d.name, "benchmark": m.get("benchmark"), "method": m.get("method"),
                "seed": m.get("seed"), "budget": m.get("budget"), "evaluations": max(n, 0),
                "finished": "finished_at" in m, "started": m.get("env", {}).get("timestamp"),
                "best_pct": s.get("best_pct_faster_than_O3"), "best_diff": s.get("best_diff_vs_O3"),
                "best_flags": s.get("best_flags"),
                "unique_binaries": s.get("unique_binaries")}

    @app.get("/api/runs")
    def runs():
        out = all_runs()
        out.sort(key=lambda r: r.get("started") or "", reverse=True)
        return jsonify(out)

    @app.get("/api/runs/<source>/<exp_id>")
    def run_detail(source, exp_id):
        if source not in sources or not ID_RE.match(exp_id):
            abort(404)
        d = sources[source] / exp_id
        if not d.exists():
            return jsonify({"exp_id": exp_id, "pending": True, "evals": []})
        store = ResultStore(d)
        manifest = store.read_json("manifest.json") or {}
        summary = store.read_json("summary.json")
        rows = []
        for r in store.load():
            try:
                diff = space.describe_diff(space.from_key(r.config_key), "O3")
            except ValueError:
                diff = ""
            rows.append({
                "eval_id": r.eval_id, "status": r.status, "flags": r.flags, "diff": diff,
                "median_ms": round(r.median_kernel_ns / 1e6, 3) if r.median_kernel_ns else None,
                "ratio": r.ratio_to_ref, "y": r.y,
                "pct": round((1 - math.exp(r.y)) * 100, 3) if r.y is not None else None,
                "best_pct": round((1 - math.exp(r.best_y_so_far)) * 100, 3) if r.best_y_so_far is not None else None,
                "reused": r.reused_from is not None, "noisy": bool(r.noisy), "acq": r.acq_value,
                "compile_s": r.compile_time_s, "text_bytes": r.text_size_bytes, "note": r.note,
            })
        log = d / "log.txt"
        tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-30:] if log.exists() else []
        keys = {r.eval_id: r.config_key for r in store.load()}
        for row in rows:
            row["key"] = keys.get(row["eval_id"], "")
        return jsonify({"source": source, "exp_id": exp_id, "manifest": manifest, "summary": summary,
                        "evals": rows, "log": tail, "bit_names": ["base -O3"] + ["-f" + n for n in space.flag_names],
                        "ref_key": space.key(space.reference("O3"))})

    @app.get("/api/runs/<source>/<exp_id>/csv")
    def run_csv(source, exp_id):
        if source not in sources or not ID_RE.match(exp_id):
            abort(404)
        d = sources[source] / exp_id
        if not (d / "evals.csv").exists():
            abort(404)
        return send_from_directory(d, "evals.csv", as_attachment=True, download_name=f"{exp_id}.csv")

    def all_runs() -> list[dict]:
        out = []
        for src, base in sources.items():
            if base.exists():
                for d in base.iterdir():
                    if d.is_dir():
                        r = run_info(src, d)
                        if r:
                            out.append(r)
        return out

    @app.get("/api/curves")
    def curves():
        bench = request.args.get("bench", "")
        out = []
        for r in all_runs():
            if r["benchmark"] != bench:
                continue
            ev = ResultStore(sources[r["source"]] / r["exp_id"]).load()
            best = [round((1 - math.exp(e.best_y_so_far)) * 100, 3) if e.best_y_so_far is not None else None
                    for e in sorted(ev, key=lambda e: e.eval_id)]
            out.append({**r, "best": best})
        return jsonify(out)

    @app.get("/api/dashboard")
    def dashboard():
        runs = all_runs()
        names = [b.name for b in custom.all_benchmarks().values()]
        t2 = {}
        p = RESULTS_DIR / "tables" / "T2_main_results.csv"
        if p.exists():
            df = pd.read_csv(p)
            for _, r in df.iterrows():
                t2[r["benchmark"]] = {k: clean(v) for k, v in r.items() if k != "benchmark"}
        per = []
        for n in names:
            rs = [r for r in runs if r["benchmark"] == n]
            best = {}
            for m in ("bo", "random"):
                vals = [r["best_pct"] for r in rs if r["method"] == m and r["best_pct"] is not None]
                best[m] = max(vals) if vals else None
            per.append({"name": n, "runs": len(rs), "best_bo": best["bo"], "best_random": best["random"],
                        "verified": t2.get(n)})
        return jsonify({
            "runs": len(runs), "evaluations": sum(r["evaluations"] for r in runs),
            "finished_runs": sum(1 for r in runs if r["finished"]),
            "programs": per,
            "recent": sorted(runs, key=lambda r: r.get("started") or "", reverse=True)[:8],
            "sweep_running": sweep_running(),
            "geomean": (json.loads((RESULTS_DIR / "tables" / "stats.json").read_text(encoding="utf-8"))
                        if (RESULTS_DIR / "tables" / "stats.json").exists() else None),
        })

    corpus_cache = {}

    @app.get("/api/corpus")
    def corpus():
        """Real-world data used by the real-data benchmarks: provenance + statistics."""
        cpath = ROOT / "benchmarks" / "data" / "corpus.txt"
        if not cpath.exists():
            return jsonify({"available": False})
        if not corpus_cache:
            raw = cpath.read_bytes()
            text = raw.decode("utf-8", errors="replace")
            words = re.findall(r"[a-z0-9_]+", text.lower())
            freq = {}
            for w in words:
                freq[w] = freq.get(w, 0) + 1
            top = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:20]
            files = []
            md = ROOT / "benchmarks" / "data" / "CORPUS.md"
            if md.exists():
                for line in md.read_text(encoding="utf-8").splitlines():
                    m = re.match(r"\| `([^`]+)` \| ([^|]+) \| ([\d,]+) \| `([0-9a-f]+)` \|", line)
                    if m:
                        files.append({"file": m.group(1), "what": m.group(2).strip(),
                                      "bytes": int(m.group(3).replace(",", "")), "sha": m.group(4)})
            import hashlib
            corpus_cache.update({
                "available": True, "bytes": len(raw), "lines": text.count("\n") + 1, "words": len(words),
                "distinct": len(freq), "sha256": hashlib.sha256(raw).hexdigest(), "top_words": top,
                "files": files, "excerpt": text[2000:2900],
                "programs": [{"name": b.name, "args": [a if not a.endswith("corpus.txt") else "corpus.txt" for a in b.args]}
                             for b in custom.all_benchmarks().values() if b.real_data],
            })
        return jsonify(corpus_cache)

    @app.get("/api/params")
    def params():
        keys = ["budget", "n_init", "seeds", "methods", "warmup", "search_reps", "final_reps", "baseline_reps",
                "noise_floor_reps", "cv_threshold", "paired_reference", "failure_penalty", "compile_timeout_s",
                "run_timeout_min_s", "wallclock_cap_h"]
        return jsonify({"experiment": {k: cfg.get(k) for k in keys}, "bo": cfg.get("bo", {}),
                        "dim": space.dim, "n_configs": 2 ** space.dim, "flags": space.flag_names,
                        "fixed_flags": fixed_flags(cfg), "compiler_version": state["version"]})

    @app.get("/api/manuscript")
    def manuscript():
        d = ROOT / "docs" / "manuscript"
        files = sorted(d.glob("*.docx")) if d.exists() else []
        if not files:
            abort(404)
        return send_from_directory(d, files[-1].name, as_attachment=True, download_name=files[-1].name)

    @app.get("/api/manuscript/info")
    def manuscript_info():
        d = ROOT / "docs" / "manuscript"
        files = sorted(d.glob("*.docx")) if d.exists() else []
        md = d / "manuscript.md"
        return jsonify({"docx": files[-1].name if files else None,
                        "markdown": md.read_text(encoding="utf-8") if md.exists() else None})

    @app.get("/api/source/<name>")
    def source_code(name):
        b = custom.all_benchmarks().get(name)
        if b is None or not b.source.exists():
            abort(404)
        return jsonify({"name": name, "path": str(b.source.relative_to(ROOT)) if b.source.is_relative_to(ROOT) else b.name,
                        "code": b.source.read_text(encoding="utf-8", errors="replace")})

    # ---- study results ------------------------------------------------------------
    @app.get("/api/results")
    def results():
        tdir = RESULTS_DIR / "tables"
        tables = {}
        if tdir.exists():
            for p in sorted(tdir.glob("T*.csv")):
                df = pd.read_csv(p)
                tables[p.stem] = json.loads(df.to_json(orient="split", index=False))
        stats = json.loads((tdir / "stats.json").read_text(encoding="utf-8")) if (tdir / "stats.json").exists() else None
        figs = sorted(p.name for p in (RESULTS_DIR / "figures").glob("F*.png")) if (RESULTS_DIR / "figures").exists() else []
        return jsonify({"tables": tables, "stats": stats, "figures": figs, "sweep_running": sweep_running()})

    return app


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    # macOS uses port 5000 for AirPlay Receiver, so the Mac default is 5050.
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5050 if sys.platform == "darwin" else 5000)))
    a = ap.parse_args()
    app = create_app()
    print(f"\n  BO compiler optimizer - open http://{a.host}:{a.port}\n")
    app.run(host=a.host, port=a.port, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
