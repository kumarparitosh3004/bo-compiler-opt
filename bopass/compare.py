"""Fair comparison of a few configurations of one benchmark (used by the web app).

Same method as scripts/final_measure.py: fresh builds, an output check, then
one discarded warm-up round and `reps` rounds in which every candidate runs once
in a freshly shuffled order. Statistics are against the "O3" candidate.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import OK
from .benchmarks import Benchmark
from .compiler_driver import compile
from .config import RESULTS_DIR
from .correctness import matches
from .runner import run_once
from .stats import bootstrap_speedup_ci, mann_whitney_p, pct, speedup, verdict


class Cancelled(Exception):
    pass


def noise_floor_pct(bench: str) -> float | None:
    p = RESULTS_DIR / "baselines" / "noise_floor.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    row = df[df.benchmark == bench]
    return float(row.iloc[0].noise_floor_pct) if not row.empty else None


def compare(bench: Benchmark, candidates: list[dict], cc: str, fixed: list[str], build_dir: Path,
            reps: int = 15, seed: int = 0, timeout_s: float = 300.0, should_stop=None, progress=None) -> dict:
    """candidates: [{"name": "O3", "flags": ["-O3"]}, ...]; must include one named "O3"."""
    def check_stop():
        if should_stop is not None and should_stop():
            raise Cancelled()

    expected = bench.expected_path.read_text(encoding="utf-8").strip() if bench.expected_path.exists() else None
    built = []
    for c in candidates:
        check_stop()
        cr = compile(bench, list(c["flags"]), build_dir, cc=cc, fixed=fixed)
        item = {"name": c["name"], "flags": " ".join(c["flags"]), "status": cr.status,
                "compile_time_s": round(cr.compile_time_s, 3), "file_size_bytes": cr.file_size_bytes,
                "text_size_bytes": cr.text_size_bytes, "exe": cr.exe_path, "times_ns": [], "correct": False}
        if cr.status == OK:
            st, _, _, checksum, _, err = run_once(cr.exe_path, bench.args, timeout_s, bench.timing)
            item["correct"] = st == OK and (expected is None or matches(bench, checksum, expected))
            item["status"] = st if st != OK else ("OK" if item["correct"] else "WRONG_OUTPUT")
        built.append(item)
        if progress:
            progress(f"built {c['name']}: {item['status']}")

    live = [b for b in built if b["correct"]]
    rng = np.random.default_rng(seed)
    total = (reps + 1) * len(live)
    done = 0
    for rnd in range(-1, reps):                      # round -1 = discarded warm-up
        for i in rng.permutation(len(live)):
            check_stop()
            b = live[i]
            st, kernel, _, checksum, _, _ = run_once(b["exe"], bench.args, timeout_s, bench.timing)
            ok = st == OK and (expected is None or matches(bench, checksum, expected))
            if rnd >= 0 and ok:
                b["times_ns"].append(kernel)
            done += 1
            if progress and done % max(1, len(live)) == 0:
                progress(f"round {rnd + 2}/{reps + 1}", done, total)

    nf = noise_floor_pct(bench.name)
    ref = next((b for b in built if b["name"] == "O3" and b["times_ns"]), None)
    if nf is None and ref is not None:
        a = np.asarray(ref["times_ns"], dtype=float)
        nf = float(a.std(ddof=1) / a.mean() * 100) if a.size > 1 else 1.0
    out = []
    for b in built:
        t = b["times_ns"]
        row = {k: v for k, v in b.items() if k not in ("exe", "times_ns")}
        row["times_ms"] = [round(x / 1e6, 3) for x in t]
        row["median_ms"] = round(float(np.median(t)) / 1e6, 3) if t else None
        row["min_ms"] = round(float(np.min(t)) / 1e6, 3) if t else None
        if ref is not None and t and b is not ref:
            s = speedup(ref["times_ns"], t)
            ci = bootstrap_speedup_ci(ref["times_ns"], t, seed=seed)
            p = mann_whitney_p(ref["times_ns"], t)
            row.update(speedup_vs_O3=round(s, 4), pct_vs_O3=round(pct(s), 2),
                       ci=[round(ci[0], 4), round(ci[1], 4)], p=float(f"{p:.3g}"),
                       verdict=verdict(s, ci, p, nf))
            if ref.get("text_size_bytes") and b.get("text_size_bytes"):
                row["text_vs_O3_pct"] = round((b["text_size_bytes"] / ref["text_size_bytes"] - 1) * 100, 2)
        out.append(row)
    return {"benchmark": bench.name, "args": list(bench.args), "reps": reps, "noise_floor_pct": nf,
            "candidates": out, "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
