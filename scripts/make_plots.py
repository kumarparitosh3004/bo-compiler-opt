"""Phase 4 (Member 4 + Member 3): figures F1-F4 for the report and slides.

F1  final comparison: % change in run time vs -O3 per benchmark (dot = median of
    seeds, whisker = seed range), shaded band = +/- 2x noise floor
F2  convergence: best-so-far vs evaluation number, BO vs random (median of seeds,
    band = min-max)
F3  flag sensitivity: GP relevance (1 / ARD length scale) per benchmark x flag
F4  binary size vs run time of every evaluated configuration (two benchmarks)

usage: python scripts/make_plots.py [--experiment <id>]   (--experiment: convergence of one run, for the demo)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
import matplotlib.patches  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from bopass.config import RESULTS_DIR, load_experiment  # noqa: E402
from bopass.stats import pct, speedup  # noqa: E402

FIG = RESULTS_DIR / "figures"
# reference palette (validated categorical order), light mode
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
C = {"bo": "#2a78d6", "random": "#eb6834", "O2": "#52514e"}
LABEL = {"bo": "Bayesian Optimization", "random": "Random search", "O2": "-O2"}
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "legend.frameon": False,
})


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / name, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote results/figures/{name}")


def f1_final(cfg):
    runs = pd.read_csv(RESULTS_DIR / "final" / "final_runs.csv")
    runs = runs[runs.correct]
    noise = pd.read_csv(RESULTS_DIR / "baselines" / "noise_floor.csv").set_index("benchmark")
    t = {k: g.kernel_ns.values for k, g in runs.groupby(["benchmark", "candidate"])}
    benches = [b for b in cfg["benchmarks"] if (b, "O3") in t]
    fig, ax = plt.subplots(figsize=(7.5, 0.62 * len(benches) + 1.4))
    offs = {"O2": 0.22, "random": 0.0, "bo": -0.22}
    for i, b in enumerate(benches):
        y = len(benches) - 1 - i
        band = 2 * noise.loc[b, "noise_floor_pct"]
        ax.add_patch(plt.Rectangle((-band, y - 0.42), 2 * band, 0.84, color=GRID, alpha=0.6, lw=0))
        o3 = t[(b, "O3")]
        ax.plot(pct(speedup(o3, t[(b, "O2")])), y + offs["O2"], "o", ms=7, color=C["O2"],
                mec=SURFACE, mew=1.5, label=LABEL["O2"] if i == 0 else None)
        for m in cfg["methods"]:
            vals = [pct(speedup(o3, t[(b, f"{m}_s{s}")])) for s in cfg["seeds"] if (b, f"{m}_s{s}") in t]
            if not vals:
                continue
            yy = y + offs[m]
            ax.plot([min(vals), max(vals)], [yy, yy], color=C[m], lw=2, solid_capstyle="round")
            ax.plot(np.median(vals), yy, "o", ms=8, color=C[m], mec=SURFACE, mew=1.5,
                    label=LABEL[m] + " (median of seeds, line = range)" if i == 0 else None)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(range(len(benches)), list(reversed(benches)))
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Change in run time vs -O3 (%)   ← slower | faster →")
    ax.set_title("Final comparison against -O3 (15 interleaved runs per candidate)", loc="left")
    h, l = ax.get_legend_handles_labels()
    h.append(matplotlib.patches.Patch(color=GRID, alpha=0.6))
    l.append("±2× noise floor (no measurable difference)")
    ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, fontsize=8.5)
    ax.set_ylim(-0.6, len(benches) - 0.4)
    save(fig, "F1_final_comparison.png")


def _best_curve(e):
    e = e.sort_values("eval_id")
    return (1 - np.exp(e.best_y_so_far.values)) * 100


def f2_convergence(cfg, evals):
    benches = [b for b in cfg["benchmarks"] if b in set(evals.benchmark)]
    n = len(benches)
    cols = 3
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(10, 3.0 * rows), sharex=True, squeeze=False)
    for ax, b in zip(axes.flat, benches):
        for m in cfg["methods"]:
            curves = [_best_curve(g) for _, g in evals[(evals.benchmark == b) & (evals.method == m)]
                      .groupby("seed")]
            if not curves:
                continue
            L = min(len(c) for c in curves)
            A = np.vstack([c[:L] for c in curves])
            x = np.arange(1, L + 1)
            ax.fill_between(x, A.min(0), A.max(0), color=C[m], alpha=0.15, lw=0)
            ax.plot(x, np.median(A, 0), color=C[m], lw=2, label=LABEL[m])
        ax.axhline(0, color=INK2, lw=1)
        ax.set_title(b, loc="left")
        ax.set_xlim(1, None)
    for ax in axes.flat[n:]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel("Evaluations")
    for ax in axes[:, 0]:
        ax.set_ylabel("Best so far:\n% faster than -O3")
    h, l = axes.flat[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.02))
    fig.suptitle("Convergence during search (median of seeds; band = min–max; 0 = -O3, measured paired)",
                 x=0.01, ha="left", y=1.07, fontweight="bold", fontsize=11)
    fig.tight_layout()
    save(fig, "F2_convergence.png")


def f3_sensitivity(cfg):
    rows = {}
    flags = None
    for b in cfg["benchmarks"]:
        ls = []
        for s in cfg["seeds"]:
            p = RESULTS_DIR / "search" / f"{b}_bo_s{s}" / "summary.json"
            if p.exists():
                d = json.loads(p.read_text(encoding="utf-8")).get("length_scales")
                if d:
                    flags = list(d)
                    ls.append([d[k] for k in flags])
        if ls:
            rel = 1 / np.median(np.array(ls), axis=0)
            rows[b] = rel / rel.max()
    if not rows:
        return
    M = np.vstack(list(rows.values()))
    fig, ax = plt.subplots(figsize=(10, 0.45 * len(rows) + 2.2))
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("seq", ["#fcfcfb"] + SEQ)
    im = ax.imshow(M, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_yticks(range(len(rows)), list(rows))
    ax.set_xticks(range(len(flags)), [f.replace("base_level", "base -O2/-O3") for f in flags],
                  rotation=40, ha="right")
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    cb.set_label("relative relevance", color=INK2)
    cb.outline.set_visible(False)
    ax.set_title("Which bits the GP found the run time sensitive to (1 / ARD length scale, "
                 "normalized per benchmark; correlational)", loc="left")
    save(fig, "F3_flag_sensitivity.png")


def f4_size_vs_time(cfg, evals):
    ok = evals[(evals.status == "OK") & evals.text_size_bytes.notna()]
    if ok.empty:
        return
    spread = ok.groupby("benchmark").text_size_bytes.std().sort_values(ascending=False)
    pick = list(spread.index[:2])
    fig, axes = plt.subplots(1, len(pick), figsize=(10, 3.8), squeeze=False)
    for ax, b in zip(axes[0], pick):
        e = ok[ok.benchmark == b]
        for m in cfg["methods"]:
            d = e[e.method == m]
            ax.scatter(d.text_size_bytes / 1024, np.exp(d.y), s=22, color=C[m], alpha=0.75,
                       edgecolors=SURFACE, linewidths=0.8, label=LABEL[m])
        ax.axhline(1.0, color=INK2, lw=1)
        ax.text(ax.get_xlim()[1], 1.0, " -O3", va="center", ha="left", fontsize=8.5, color=INK2)
        ax.set_title(b, loc="left")
        ax.set_xlabel(".text size (KiB)")
        ax.set_ylabel("Run time relative to -O3 (lower is better)")
    h, l = axes[0][0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.06), fontsize=8.5)
    fig.suptitle("Binary size vs run time of every evaluated configuration (search measurements)",
                 x=0.01, ha="left", fontweight="bold", fontsize=11)
    fig.tight_layout()
    save(fig, "F4_size_vs_time.png")


def single_run(exp_id):
    e = pd.read_csv(RESULTS_DIR / "search" / exp_id / "evals.csv")
    fig, ax = plt.subplots(figsize=(7, 3.4))
    ok = e[e.status == "OK"]
    ax.scatter(ok.eval_id + 1, (1 - np.exp(ok.y)) * 100, s=18, color=GRID, edgecolors=INK2,
               linewidths=0.6, label="each evaluation", zorder=2)
    ax.plot(e.eval_id + 1, _best_curve(e), color=C.get(e.method.iloc[0], C["bo"]), lw=2,
            label="best so far", zorder=3)
    ax.axhline(0, color=INK2, lw=1)
    ax.set_xlabel("Evaluation")
    ax.set_ylabel("% faster than -O3")
    ax.set_title(f"{exp_id}: search progress", loc="left")
    ax.legend(loc="lower right", fontsize=8.5)
    save(fig, f"run_{exp_id}.png")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", help="plot only this run's progress (demo)")
    a = ap.parse_args()
    if a.experiment:
        single_run(a.experiment)
        return 0
    cfg = load_experiment()
    parts = []
    for b in cfg["benchmarks"]:
        for m in cfg["methods"]:
            for s in cfg["seeds"]:
                p = RESULTS_DIR / "search" / f"{b}_{m}_s{s}" / "evals.csv"
                if p.exists():
                    parts.append(pd.read_csv(p))
    evals = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if (RESULTS_DIR / "final" / "final_runs.csv").exists():
        f1_final(cfg)
    if not evals.empty:
        f2_convergence(cfg, evals)
        f3_sensitivity(cfg)
        f4_size_vs_time(cfg, evals)
    return 0


if __name__ == "__main__":
    sys.exit(main())
