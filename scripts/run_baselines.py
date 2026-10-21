"""Phase 2 (Member 2): baseline measurements at standard optimization levels.

For each benchmark and level: compile 3 times (median compile time), record file
and .text size, run 1 warm-up + `baseline_reps` timed runs, check correctness.
Writes results/baselines/baselines.csv (rows for re-run benchmarks are replaced).

usage: python scripts/run_baselines.py [--bench matmul ...] [--levels O0 O1 O2 O3] [--reps 15]
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from bopass import OK, WRONG_OUTPUT  # noqa: E402
from bopass.baselines import BASELINES_CSV  # noqa: E402
from bopass.benchmarks import load_benchmarks  # noqa: E402
from bopass.compiler_driver import compile, compiler_version  # noqa: E402
from bopass.config import BUILD_DIR, compiler_path, fixed_flags, load_experiment  # noqa: E402
from bopass.correctness import check  # noqa: E402
from bopass.runner import run, summarize  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", nargs="*")
    ap.add_argument("--levels", nargs="*", default=["O0", "O1", "O2", "O3"])
    ap.add_argument("--reps", type=int)
    a = ap.parse_args()
    cfg = load_experiment()
    cc, fixed = compiler_path(cfg), fixed_flags(cfg)
    reps = a.reps or cfg.get("baseline_reps", 15)
    benches = load_benchmarks()
    names = a.bench or list(benches)
    version = compiler_version(cc)
    rows = []
    for name in names:
        b = benches[name]
        for lvl in a.levels:
            times, cr = [], None
            for _ in range(3):
                cr = compile(b, [f"-{lvl}"], BUILD_DIR / "baselines", cc=cc, fixed=fixed)
                if cr.status != OK:
                    break
                times.append(cr.compile_time_s)
            row = {"benchmark": name, "level": lvl, "flags": f"-{lvl}", "compiler_version": version,
                   "status": cr.status, "compile_time_s": round(statistics.median(times), 4) if times else None,
                   "file_size_bytes": cr.file_size_bytes, "text_size_bytes": cr.text_size_bytes,
                   "binary_sha256": cr.sha256[:16] if cr.sha256 else None}
            if cr.status == OK:
                rr = run(cr.exe_path, b.args, warmup=cfg.get("warmup", 1), reps=reps, timeout_s=600)
                status = rr.status
                if status == OK and not check(b, rr.checksum):
                    status = WRONG_OUTPUT
                st = summarize(rr.kernel_ns)
                row.update(status=status, median_kernel_ns=st["median"], min_kernel_ns=st["min"],
                           iqr_kernel_ns=st["iqr"], cv=st["cv"], n_reps=len(rr.kernel_ns),
                           checksum=rr.checksum)
            rows.append(row)
            med = row.get("median_kernel_ns")
            print(f"{name:10s} -{lvl}: {row['status']:12s} "
                  f"median={med / 1e6 if med else float('nan'):9.2f} ms  cv={row.get('cv') or 0:.3f}  "
                  f"compile={row['compile_time_s']}s  text={row['text_size_bytes']}")
    new = pd.DataFrame(rows)
    BASELINES_CSV.parent.mkdir(parents=True, exist_ok=True)
    if BASELINES_CSV.exists():
        old = pd.read_csv(BASELINES_CSV)
        old = old[~(old.benchmark.isin(names) & old.level.isin(a.levels))]
        new = pd.concat([old, new], ignore_index=True)
    order = {n: i for i, n in enumerate(benches)}
    new = new.sort_values(["benchmark", "level"], key=lambda s: s.map(order) if s.name == "benchmark" else s)
    new.to_csv(BASELINES_CSV, index=False)
    print(f"wrote {BASELINES_CSV.relative_to(ROOT)}")
    return 0 if all(r["status"] == OK for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
