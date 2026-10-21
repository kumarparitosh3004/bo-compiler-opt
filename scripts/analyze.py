"""Phase 4 (Member 3 + Member 2): statistics and tables T1-T5 from raw data.

Inputs : results/baselines/*.csv, results/search/*/{evals.csv,summary.json},
         results/final/{candidates,final_runs}[_alt].csv
Outputs: results/tables/T*.csv, results/tables/summary.md, results/tables/stats.json

usage: python scripts/analyze.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from bopass.config import RESULTS_DIR, load_experiment  # noqa: E402
from bopass.orchestrator import active_seconds  # noqa: E402
from bopass.stats import bootstrap_speedup_ci, geomean, mann_whitney_p, pct, speedup, verdict  # noqa: E402

TABLES = RESULTS_DIR / "tables"


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if (isinstance(v, float) and math.isnan(v)) else str(v)
                                     for v in r.values) + " |")
    return "\n".join(out)


def fmt_pct(x):
    return f"{x:+.1f}%" if x is not None and not (isinstance(x, float) and math.isnan(x)) else ""


def load_search(cfg):
    evals, sums = [], []
    for b in cfg["benchmarks"]:
        for m in cfg["methods"]:
            for s in cfg["seeds"]:
                d = RESULTS_DIR / "search" / f"{b}_{m}_s{s}"
                if (d / "evals.csv").exists():
                    e = pd.read_csv(d / "evals.csv")
                    evals.append(e)
                if (d / "summary.json").exists():
                    sm = json.loads((d / "summary.json").read_text(encoding="utf-8"))
                    sm.update(benchmark=b, method=m, seed=s)
                    sums.append(sm)
    return (pd.concat(evals, ignore_index=True) if evals else pd.DataFrame()), pd.DataFrame(sums)


def main() -> int:
    cfg = load_experiment()
    TABLES.mkdir(parents=True, exist_ok=True)
    sections, stats = [], {}
    order = cfg["benchmarks"]

    # ---- T1 baselines (Phase 2 measurements) ---------------------------------------------
    base = pd.read_csv(RESULTS_DIR / "baselines" / "baselines.csv")
    noise = pd.read_csv(RESULTS_DIR / "baselines" / "noise_floor.csv").set_index("benchmark")
    t1 = base.pivot(index="benchmark", columns="level", values="median_kernel_ns").reindex(order) / 1e6
    t1.columns = [f"-{c} (ms)" for c in t1.columns]
    t1["-O3 .text (B)"] = base[base.level == "O3"].set_index("benchmark").text_size_bytes.reindex(order)
    t1["-O3 compile (s)"] = base[base.level == "O3"].set_index("benchmark").compile_time_s.reindex(order)
    t1["noise floor CV"] = [f"{noise.loc[b, 'noise_floor_pct']:.2f}%" for b in t1.index]
    t1 = t1.round(2).reset_index()
    t1.to_csv(TABLES / "T1_baselines.csv", index=False)
    sections.append(("T1 - Baselines (median kernel time, Phase 2 harness)", t1))

    # ---- T2 main results (Step B interleaved re-measurement) ----------------------------
    runs = pd.read_csv(RESULTS_DIR / "final" / "final_runs.csv")
    cands = pd.read_csv(RESULTS_DIR / "final" / "candidates.csv")
    runs = runs[runs.correct]
    times = {k: g.kernel_ns.values for k, g in runs.groupby(["benchmark", "candidate"])}
    detail, main_rows = [], []
    for b in order:
        if (b, "O3") not in times:
            continue
        o3, o2 = times[(b, "O3")], times[(b, "O2")]
        nf = float(noise.loc[b, "noise_floor_pct"])
        row = {"benchmark": b, "-O2 (ms)": np.median(o2) / 1e6, "-O3 (ms)": np.median(o3) / 1e6}
        for m in cfg["methods"]:
            sps, verdicts = [], []
            for s in cfg["seeds"]:
                k = (b, f"{m}_s{s}")
                if k not in times:
                    continue
                t = times[k]
                sp = speedup(o3, t)
                ci = bootstrap_speedup_ci(o3, t, seed=s)
                p = mann_whitney_p(o3, t)
                v = verdict(sp, ci, p, nf)
                c = cands[(cands.benchmark == b) & (cands.candidate == f"{m}_s{s}")].iloc[0]
                c3 = cands[(cands.benchmark == b) & (cands.candidate == "O3")].iloc[0]
                detail.append({
                    "benchmark": b, "method": m, "seed": s, "flags vs -O3": c.diff_vs_O3,
                    "median (ms)": round(np.median(t) / 1e6, 2), "speed-up vs -O3": round(sp, 4),
                    "change": fmt_pct(pct(sp)), "95% CI": f"[{ci[0]:.3f}, {ci[1]:.3f}]",
                    "p (MWU)": f"{p:.3g}", "verdict": v,
                    "speed-up vs -O2": round(speedup(o2, t), 4),
                    ".text vs -O3": fmt_pct((c.text_size_bytes / c3.text_size_bytes - 1) * 100),
                    "compile time vs -O3": fmt_pct((c.compile_time_s / c3.compile_time_s - 1) * 100),
                })
                sps.append(sp)
                verdicts.append(v)
            if sps:
                row[f"{m} speed-up vs -O3 (median of seeds)"] = round(float(np.median(sps)), 4)
                row[f"{m} range"] = f"{min(sps):.3f}-{max(sps):.3f}"
                row[f"{m} seeds faster/same/slower"] = (f"{verdicts.count('faster')}/"
                                                        f"{verdicts.count('no measurable difference')}/"
                                                        f"{verdicts.count('slower')}")
        main_rows.append(row)
    t2 = pd.DataFrame(main_rows).round(2)
    gm = {"benchmark": "geometric mean"}
    for m in cfg["methods"]:
        col = f"{m} speed-up vs -O3 (median of seeds)"
        if col in t2:
            gm[col] = round(geomean(t2[col]), 4)
            stats[f"geomean_speedup_vs_O3_{m}"] = gm[col]
    t2 = pd.concat([t2, pd.DataFrame([gm])], ignore_index=True)
    t2.to_csv(TABLES / "T2_main_results.csv", index=False)
    t2b = pd.DataFrame(detail)
    t2b.to_csv(TABLES / "T2b_per_seed.csv", index=False)
    sections.append(("T2 - Main results (Step B: 15 interleaved runs, speed-up = t(-O3) / t(method))", t2))
    sections.append(("T2b - Per seed: significance, size and compile-time cost", t2b))
    stats["verdict_counts"] = t2b.groupby(["method", "verdict"]).size().unstack(fill_value=0).to_dict("index")

    # ---- T3 search cost and sample efficiency ---------------------------------------------
    evals, sums = load_search(cfg)
    if not sums.empty:
        sums["failures"] = sums.status_counts.apply(lambda d: sum(v for k, v in d.items() if k != "OK"))
        # active search time (sleep gaps removed), recomputed from the raw evaluations
        act = {(b_, m_, s_): active_seconds(list(g.sort_values("eval_id").elapsed_s))
               for (b_, m_, s_), g in evals.groupby(["benchmark", "method", "seed"])}
        sums["search_wall_time_s"] = [act.get((r.benchmark, r.method, r.seed), r.search_wall_time_s)
                                      for r in sums.itertuples()]
        # compile time per evaluation can never legitimately exceed the 60 s compile
        # timeout; larger values are the machine sleeping mid-compile
        cap = float(cfg.get("compile_timeout_s", 60))
        ctime = {(b_, m_, s_): float(g.compile_time_s.fillna(0).clip(upper=cap).sum())
                 for (b_, m_, s_), g in evals.groupby(["benchmark", "method", "seed"])}
        sums["total_compile_time_s"] = [ctime.get((r.benchmark, r.method, r.seed), r.total_compile_time_s)
                                        for r in sums.itertuples()]
        t3 = (sums.groupby(["benchmark", "method"])
              .agg(evaluations=("evaluations", "mean"), unique_binaries=("unique_binaries", "mean"),
                   measured_runs=("measured_runs", "mean"), failures=("failures", "sum"),
                   compile_time_s=("total_compile_time_s", "mean"), wall_time_min=("search_wall_time_s", "mean"))
              .reindex(order, level=0).round(1).reset_index())
        t3["wall_time_min"] = (t3.wall_time_min / 60).round(1)
        t3.to_csv(TABLES / "T3_search_cost.csv", index=False)
        sections.append(("T3 - Search cost per run (mean over seeds; failures summed)", t3))
        stats["total_search_wall_time_h"] = round(sums.search_wall_time_s.sum() / 3600, 2)
        stats["total_evaluations"] = int(sums.evaluations.sum())

        eff = []
        for (b, m, s), g in evals.groupby(["benchmark", "method", "seed"]):
            g = g.sort_values("eval_id")
            best = g.best_y_so_far.values
            final = best[-1]
            within = np.flatnonzero(best <= final + math.log(1.01))
            eff.append({"benchmark": b, "method": m, "seed": s,
                        **{f"best@{n}": (1 - math.exp(best[min(n, len(best)) - 1])) * 100 for n in (10, 20, 50)},
                        "evals to within 1% of final best": int(within[0]) + 1})
        eff = pd.DataFrame(eff)
        t3b = eff.groupby(["benchmark", "method"]).median(numeric_only=True).drop(columns="seed")
        t3b = t3b.reindex(order, level=0).round(2).reset_index()
        for n in (10, 20, 50):
            t3b[f"best@{n}"] = t3b[f"best@{n}"].map(fmt_pct)
        t3b.to_csv(TABLES / "T3b_sample_efficiency.csv", index=False)
        sections.append(("T3b - Sample efficiency: best found so far, % faster than the run's own -O3 "
                         "measurement (search-time numbers, median of seeds)", t3b))
        # measurement check: evaluation 0 of every run is -O3 paired with itself
        if "ratio_to_ref" in evals:
            self_pairs = evals[(evals.eval_id == 0) & evals.ratio_to_ref.notna()].ratio_to_ref
            stats["self_pair_O3_ratio"] = {
                "n": int(self_pairs.size), "mean": round(float(self_pairs.mean()), 4),
                "sd": round(float(self_pairs.std()), 4), "min": round(float(self_pairs.min()), 4),
                "max": round(float(self_pairs.max()), 4)}
        for m in cfg["methods"]:
            stats[f"median_best@20_pct_{m}"] = round(float(eff[eff.method == m]["best@20"].median()), 3)
            stats[f"median_best@50_pct_{m}"] = round(float(eff[eff.method == m]["best@50"].median()), 3)

    # ---- T4 best configurations -------------------------------------------------------------
    t4 = cands[cands.method != "level"][["benchmark", "candidate", "diff_vs_O3", "search_y", "flags"]].copy()
    t4["search-time change vs -O3"] = t4.search_y.map(lambda y: fmt_pct((1 - math.exp(y)) * 100))
    t4 = t4.drop(columns="search_y")
    t4.to_csv(TABLES / "T4_best_configs.csv", index=False)
    sections.append(("T4 - Best configuration of each run (flags that differ from -O3)",
                     t4.drop(columns="flags")))

    # ---- T5 generalization (Step D) --------------------------------------------------------
    alt = RESULTS_DIR / "final" / "final_runs_alt.csv"
    if alt.exists():
        ra = pd.read_csv(alt)
        ra = ra[ra.correct]
        ta = {k: g.kernel_ns.values for k, g in ra.groupby(["benchmark", "candidate"])}
        rows = []
        for b in order:
            if (b, "O3") not in ta:
                continue
            row = {"benchmark": b}
            for m in cfg["methods"]:
                sps = [speedup(ta[(b, "O3")], ta[(b, f"{m}_s{s}")]) for s in cfg["seeds"] if (b, f"{m}_s{s}") in ta]
                if sps:
                    row[f"{m} speed-up vs -O3 on larger input"] = round(float(np.median(sps)), 4)
            rows.append(row)
        t5 = pd.DataFrame(rows)
        t5.to_csv(TABLES / "T5_generalization.csv", index=False)
        sections.append(("T5 - Generalization: same binaries on a ~2x larger input (median of seeds)", t5))

    md = ["# Results tables\n", "Generated by `scripts/analyze.py` from raw CSVs. Do not edit by hand.\n"]
    for title, df in sections:
        md += [f"## {title}\n", md_table(df), ""]
    md.append("## Key statistics\n\n```json\n" + json.dumps(stats, indent=2, default=str) + "\n```\n")
    (TABLES / "summary.md").write_text("\n".join(md), encoding="utf-8")
    (TABLES / "stats.json").write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
