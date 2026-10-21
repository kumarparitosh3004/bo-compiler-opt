"""Phase 4 Steps B, C and D (Member 2 / Member 1): fair final re-measurement.

The best configuration found during a search is optimistically biased (it was
picked out of 50 noisy measurements). So for each benchmark this script rebuilds
fresh: -O0, -O1, -O2, -O3 and the best BO / random configuration of every seed,
checks every binary's output (Step C), then measures them INTERLEAVED: one
discarded warm-up round, then `final_reps` rounds, each running every candidate
once in a freshly shuffled order. All reported comparisons use these numbers.

--alt runs Step D: the same binaries on the larger `args_alt` input, checked
against a reference produced by the -O0 build on that input.

usage: python scripts/final_measure.py [--bench ...] [--reps 15] [--alt] [--tag NAME]

--tag NAME reads the searches written by run_all.py --tag NAME and writes
candidates_NAME.csv / final_runs_NAME.csv, so a re-measurement on a new
machine never overwrites the committed study results.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from bopass import OK  # noqa: E402
from bopass.benchmarks import load_benchmarks  # noqa: E402
from bopass.compiler_driver import compile  # noqa: E402
from bopass.config import BUILD_DIR, RESULTS_DIR, compiler_path, fixed_flags, load_experiment, resolve  # noqa: E402
from bopass.correctness import matches  # noqa: E402
from bopass.env_info import collect  # noqa: E402
from bopass.runner import run, run_once  # noqa: E402
from bopass.space import SearchSpace  # noqa: E402

OUT = RESULTS_DIR / "final"


def candidates_for(bench: str, cfg: dict, space: SearchSpace, tag: str = "") -> list[dict]:
    cands = [{"candidate": lvl, "method": "level", "seed": None, "flags": [f"-{lvl}"]}
             for lvl in ("O0", "O1", "O2", "O3")]
    for method in cfg["methods"]:
        for seed in cfg["seeds"]:
            p = RESULTS_DIR / "search" / f"{bench}_{method}_s{seed}{tag}" / "summary.json"
            if not p.exists():
                print(f"  warning: no search result {p.parent.name}; skipped")
                continue
            s = json.loads(p.read_text(encoding="utf-8"))
            if not s.get("best_flags"):
                print(f"  warning: {p.parent.name} has no successful configuration; skipped")
                continue
            cands.append({"candidate": f"{method}_s{seed}", "method": method, "seed": seed,
                          "flags": s["best_flags"].split(), "search_y": s["best_y"],
                          "config_key": s["best_key"],
                          "diff_vs_O3": space.describe_diff(space.from_key(s["best_key"]), "O3")})
    return cands


def main() -> int:
    ap = argparse.ArgumentParser()
    cfg = load_experiment()
    ap.add_argument("--bench", nargs="*", default=cfg["benchmarks"])
    ap.add_argument("--reps", type=int, default=cfg.get("final_reps", 15))
    ap.add_argument("--alt", action="store_true", help="Step D: larger args_alt input")
    ap.add_argument("--seed", type=int, default=12345, help="seed for the round shuffling")
    ap.add_argument("--tag", default="", help="read <bench>_<method>_s<seed>_NAME searches")
    a = ap.parse_args()
    cc, fixed = compiler_path(cfg), fixed_flags(cfg)
    benches = load_benchmarks()
    space = SearchSpace.from_yaml(resolve(cfg["flags_file"]))
    rng = np.random.default_rng(a.seed)
    tag = f"_{a.tag}" if a.tag and not a.tag.startswith("_") else a.tag
    suffix = tag + ("_alt" if a.alt else "")
    OUT.mkdir(parents=True, exist_ok=True)
    cand_rows, run_rows = [], []

    for name in a.bench:
        b = benches[name]
        args = b.args_alt if a.alt else b.args
        print(f"\n== {name} (args {' '.join(args)})")
        cands = candidates_for(name, cfg, space, tag)

        # build (3 compiles, median compile time) and check correctness (Step C)
        ref = None
        for c in cands:
            times, cr = [], None
            for _ in range(3):
                cr = compile(b, c["flags"], BUILD_DIR / "final", cc=cc, fixed=fixed)
                if cr.status != OK:
                    break
                times.append(cr.compile_time_s)
            c.update(status=cr.status, exe=cr.exe_path, compile_time_s=statistics.median(times) if times else None,
                     file_size_bytes=cr.file_size_bytes, text_size_bytes=cr.text_size_bytes,
                     binary_sha256=cr.sha256[:16] if cr.sha256 else None)
            if cr.status != OK:
                c["correct"] = False
                continue
            rr = run(cr.exe_path, args, warmup=0, reps=1, timeout_s=900)
            if c["candidate"] == "O0":
                ref = rr.checksum if a.alt else b.expected_path.read_text(encoding="utf-8").strip()
            c["correct"] = rr.status == OK and ref is not None and matches(b, rr.checksum, ref)
            c["status"] = rr.status if rr.status != OK else ("OK" if c["correct"] else "WRONG_OUTPUT")
            print(f"  {c['candidate']:10s} {c['status']:12s} {' '.join(c['flags'])}")

        live = [c for c in cands if c["correct"]]
        for rnd in range(-1, a.reps):                      # round -1 = discarded warm-up
            for i in rng.permutation(len(live)):
                c = live[i]
                st, kernel, wall, checksum, _, _ = run_once(c["exe"], args, 900)
                ok = st == OK and matches(b, checksum, ref)
                if rnd >= 0:
                    run_rows.append({"benchmark": name, "candidate": c["candidate"], "method": c["method"],
                                     "seed": c["seed"], "round": rnd, "kernel_ns": kernel, "wall_ns": wall,
                                     "correct": ok})
                if not ok:
                    print(f"  WARNING: {c['candidate']} failed in round {rnd}: {st}")
        for c in cands:
            ks = [r["kernel_ns"] for r in run_rows if r["benchmark"] == name and r["candidate"] == c["candidate"]
                  and r["correct"]]
            med = float(np.median(ks)) if ks else None
            cand_rows.append({"benchmark": name, **{k: v for k, v in c.items() if k not in ("exe",)},
                              "flags": " ".join(c["flags"]), "median_kernel_ns": med, "n": len(ks)})
            if med:
                print(f"  {c['candidate']:10s} median {med / 1e6:8.2f} ms  (n={len(ks)})")

    for name, rows in ((f"candidates{suffix}.csv", cand_rows), (f"final_runs{suffix}.csv", run_rows)):
        new = pd.DataFrame(rows)
        p = OUT / name
        if p.exists():  # keep rows of benchmarks not re-measured now
            old = pd.read_csv(p)
            new = pd.concat([old[~old.benchmark.isin(a.bench)], new], ignore_index=True)
        new.to_csv(p, index=False)
    (OUT / f"final_manifest{suffix}.json").write_text(json.dumps(
        {"reps": a.reps, "shuffle_seed": a.seed, "alt_input": a.alt, "benchmarks": a.bench,
         "env": collect(cc, [resolve(cfg["flags_file"])])}, indent=2), encoding="utf-8")
    print(f"\nwrote results/final/candidates{suffix}.csv and final_runs{suffix}.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
