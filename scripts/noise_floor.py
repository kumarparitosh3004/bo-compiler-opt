"""Phase 2 (Member 2): measurement noise floor.

Runs each benchmark's -O3 binary `noise_floor_reps` times (default 30) and reports
the coefficient of variation. Differences smaller than ~2x this CV are reported
as "no measurable difference" in Phase 4.

usage: python scripts/noise_floor.py [--bench matmul ...] [--reps 30]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from bopass import OK  # noqa: E402
from bopass.benchmarks import load_benchmarks  # noqa: E402
from bopass.compiler_driver import compile  # noqa: E402
from bopass.config import BUILD_DIR, RESULTS_DIR, compiler_path, fixed_flags, load_experiment  # noqa: E402
from bopass.runner import run, summarize  # noqa: E402

OUT = RESULTS_DIR / "baselines" / "noise_floor.csv"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", nargs="*")
    ap.add_argument("--reps", type=int)
    a = ap.parse_args()
    cfg = load_experiment()
    cc, fixed = compiler_path(cfg), fixed_flags(cfg)
    reps = a.reps or cfg.get("noise_floor_reps", 30)
    benches = load_benchmarks()
    rows = []
    for name in a.bench or list(benches):
        b = benches[name]
        cr = compile(b, ["-O3"], BUILD_DIR / "baselines", cc=cc, fixed=fixed)
        if cr.status != OK:
            print(f"{name}: build failed")
            continue
        rr = run(cr.exe_path, b.args, warmup=1, reps=reps, timeout_s=600)
        st = summarize(rr.kernel_ns)
        rows.append({"benchmark": name, "n": len(rr.kernel_ns), "median_kernel_ns": st["median"],
                     "min_kernel_ns": st["min"], "iqr_kernel_ns": st["iqr"], "cv": st["cv"],
                     "noise_floor_pct": round(st["cv"] * 100, 3)})
        print(f"{name:10s} median={st['median'] / 1e6:8.2f} ms  CV={st['cv'] * 100:.2f}%")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    new = pd.DataFrame(rows)
    if OUT.exists():  # keep rows of benchmarks not re-measured now
        old = pd.read_csv(OUT)
        new = pd.concat([old[~old.benchmark.isin(new.benchmark)], new], ignore_index=True)
    new.to_csv(OUT, index=False)
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
