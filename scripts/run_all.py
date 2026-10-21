"""Phase 4 Step A (Member 4): the full search sweep, benchmarks x methods x seeds.

Runs sequentially on one machine (parallel runs would disturb each other's timings).
Interrupted runs resume where they stopped; finished runs are skipped quickly.

usage: python scripts/run_all.py [--bench ...] [--methods bo random] [--seeds 0 1 2] [--budget 50]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bopass.config import load_experiment  # noqa: E402
from bopass.orchestrator import run_search  # noqa: E402


def main() -> int:
    cfg = load_experiment()
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", nargs="*", default=cfg["benchmarks"])
    ap.add_argument("--methods", nargs="*", default=cfg["methods"])
    ap.add_argument("--seeds", nargs="*", type=int, default=cfg["seeds"])
    ap.add_argument("--budget", type=int, default=cfg["budget"])
    a = ap.parse_args()
    t0 = time.time()
    runs = [(b, m, s) for s in a.seeds for b in a.bench for m in a.methods]
    for i, (b, m, s) in enumerate(runs, 1):
        print(f"\n=== run {i}/{len(runs)}: {b} {m} seed {s} (elapsed {(time.time() - t0) / 60:.1f} min) ===",
              flush=True)
        summary = run_search(b, m, s, cfg, budget=a.budget)
        print(f"=== done: best {summary.get('best_pct_faster_than_O3')}% vs -O3 during search, "
              f"{summary['unique_binaries']} unique binaries, {summary['measured_runs']} measured", flush=True)
    print(f"\nsweep finished in {(time.time() - t0) / 3600:.2f} h")
    return 0


if __name__ == "__main__":
    sys.exit(main())
