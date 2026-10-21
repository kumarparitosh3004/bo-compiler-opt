"""Benchmark runner: warm-up + timed repetitions, output parsing, timeouts, statistics."""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import OK, RUN_CRASH, RUN_TIMEOUT, WRONG_OUTPUT
from .proc import run_cmd

_CHECKSUM = re.compile(r"^CHECKSUM=(\S+)\s*$", re.M)
_KERNEL = re.compile(r"^KERNEL_NS=(\d+)\s*$", re.M)


@dataclass
class RunResult:
    status: str
    kernel_ns: list[int] = field(default_factory=list)
    wall_ns: list[int] = field(default_factory=list)
    checksum: str | None = None
    exit_code: int | None = None
    stderr_tail: str = ""

    def stats(self) -> dict:
        return summarize(self.kernel_ns)


def summarize(values) -> dict:
    """median, min, IQR and coefficient of variation of a list of timings."""
    a = np.asarray(values, dtype=float)
    if a.size == 0:
        return {"median": None, "min": None, "iqr": None, "cv": None}
    q1, med, q3 = np.percentile(a, [25, 50, 75])
    mean = a.mean()
    cv = float(a.std(ddof=1) / mean) if a.size > 1 and mean > 0 else 0.0
    return {"median": float(med), "min": float(a.min()), "iqr": float(q3 - q1), "cv": cv}


def parse_output(stdout: str) -> tuple[str | None, int | None]:
    c = _CHECKSUM.search(stdout or "")
    k = _KERNEL.search(stdout or "")
    return (c.group(1) if c else None, int(k.group(1)) if k else None)


def run_once(exe: Path, args, timeout_s: float, mode: str = "kernel"):
    """One execution -> (status, kernel_ns, wall_ns, checksum, exit_code, stderr).

    mode "kernel": the program prints CHECKSUM= and KERNEL_NS= (all built-in benchmarks).
    mode "wall":   any program; time = whole-process wall time, checksum = hash of stdout.
    """
    t0 = time.perf_counter_ns()
    try:
        p = run_cmd([str(exe), *map(str, args)], timeout_s)
    except OSError as e:
        return RUN_CRASH, None, None, None, None, str(e)
    wall = time.perf_counter_ns() - t0
    if p.timed_out:
        return RUN_TIMEOUT, None, wall, None, None, ""
    if p.returncode != 0:
        return RUN_CRASH, None, wall, None, p.returncode, (p.stderr or "")[-2000:]
    if mode == "wall":
        return OK, wall, wall, hashlib.sha256((p.stdout or "").encode()).hexdigest()[:16], 0, ""
    checksum, kernel = parse_output(p.stdout)
    if checksum is None or kernel is None:
        return RUN_CRASH, None, wall, None, p.returncode, "unparseable output: " + (p.stdout or "")[-500:]
    return OK, kernel, wall, checksum, 0, ""


@dataclass
class PairedResult:
    cand: RunResult
    ref: RunResult
    ratios: list[float] = field(default_factory=list)   # per round: cand time / ref time

    @property
    def status(self) -> str:
        return self.cand.status


def run_paired(exe: Path, ref_exe: Path, args=(), warmup: int = 1, reps: int = 5,
               timeout_s: float = 30.0, mode: str = "kernel") -> PairedResult:
    """Alternate the candidate with the reference executable, A-B then B-A, so
    both are measured under the same machine conditions. Slow drift in machine
    speed (power source, temperature) then cancels in the per-round ratio."""
    cand, ref = RunResult(OK), RunResult(OK)
    ratios = []
    for i in range(warmup + reps):
        order = ("c", "r") if i % 2 == 0 else ("r", "c")
        got = {}
        for who in order:
            st, kernel, wall, checksum, rc, err = run_once(exe if who == "c" else ref_exe, args, timeout_s, mode)
            if st != OK:
                failed = RunResult(st, [], [], checksum, rc, err)
                if who == "c":
                    return PairedResult(failed, ref, ratios)
                raise RuntimeError(f"reference executable failed ({st}): {err}")
            got[who] = (kernel, wall, checksum)
        if i < warmup:
            continue
        for who, res in (("c", cand), ("r", ref)):
            kernel, wall, checksum = got[who]
            if res.checksum is not None and checksum != res.checksum:
                res.status = WRONG_OUTPUT
                res.stderr_tail = f"checksum changed between runs: {res.checksum} vs {checksum}"
            res.checksum = checksum
            res.kernel_ns.append(kernel)
            res.wall_ns.append(wall)
        if cand.status != OK:
            return PairedResult(cand, ref, ratios)
        ratios.append(got["c"][0] / got["r"][0])
    return PairedResult(cand, ref, ratios)


def run(exe: Path, args=(), warmup: int = 1, reps: int = 5, timeout_s: float = 30.0,
        mode: str = "kernel") -> RunResult:
    """Run `warmup` discarded executions, then `reps` timed ones.

    All timed repetitions must print the same checksum; otherwise the program is
    non-deterministic under this configuration and is reported as WRONG_OUTPUT.
    """
    res = RunResult(OK)
    for i in range(warmup + reps):
        status, kernel, wall, checksum, rc, err = run_once(exe, args, timeout_s, mode)
        if status != OK:
            return RunResult(status, res.kernel_ns, res.wall_ns, checksum, rc, err)
        if i < warmup:
            continue
        if res.checksum is not None and checksum != res.checksum:
            return RunResult(WRONG_OUTPUT, res.kernel_ns, res.wall_ns, checksum, rc,
                             f"checksum changed between runs: {res.checksum} vs {checksum}")
        res.checksum = checksum
        res.kernel_ns.append(kernel)
        res.wall_ns.append(wall)
        res.exit_code = rc
    return res
