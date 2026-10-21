"""Evaluator: compile -> (binary cache) -> run -> check -> record, for one configuration."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import numpy as np

from . import OK, RUN_CRASH, RUN_TIMEOUT, WRONG_OUTPUT
from . import compiler_driver, correctness, runner
from .benchmarks import Benchmark
from .space import SearchSpace


@dataclass
class EvalRecord:
    experiment_id: str = ""
    eval_id: int = 0
    benchmark: str = ""
    method: str = ""
    seed: int = 0
    config_key: str = ""
    flags: str = ""
    status: str = ""
    compile_time_s: float | None = None
    file_size_bytes: int | None = None
    text_size_bytes: int | None = None
    binary_sha256: str | None = None
    reused_from: int | None = None
    median_kernel_ns: float | None = None
    min_kernel_ns: float | None = None
    iqr_kernel_ns: float | None = None
    cv: float | None = None
    n_reps: int | None = None
    ref_median_kernel_ns: float | None = None   # paired -O3 runs measured alongside this config
    ratio_to_ref: float | None = None           # median of per-round (config / -O3) time ratios
    noisy: int = 0
    checksum: str | None = None
    y: float | None = None
    y_used_by_model: float | None = None
    best_y_so_far: float | None = None
    acq_value: float | None = None
    elapsed_s: float | None = None
    timestamp: str = ""
    note: str = ""

    def to_row(self) -> dict:
        return {k: ("" if v is None else v) for k, v in asdict(self).items()}

    @classmethod
    def from_row(cls, row: dict) -> "EvalRecord":
        kw = {}
        for f in fields(cls):
            v = row.get(f.name, "")
            if v == "" or v is None:
                kw[f.name] = None if f.default is None else f.default
                continue
            t = str(f.type)
            if "int" in t and "float" not in t:
                kw[f.name] = int(float(v))
            elif "float" in t:
                kw[f.name] = float(v)
            else:
                kw[f.name] = v
        return cls(**kw)


FIELDNAMES = [f.name for f in fields(EvalRecord)]
_MEASUREMENT_FIELDS = ("status", "median_kernel_ns", "min_kernel_ns", "iqr_kernel_ns", "cv",
                       "n_reps", "ref_median_kernel_ns", "ratio_to_ref", "noisy", "checksum", "note")


class Evaluator:
    """Evaluates configurations of one benchmark. Function hooks allow fakes in tests."""

    def __init__(self, bench: Benchmark, space: SearchSpace, cc: str, fixed_flags: list[str],
                 build_dir: Path, failures_dir: Path, warmup: int = 1, reps: int = 5,
                 compile_timeout_s: float = 60.0, run_timeout_s: float = 30.0,
                 cv_threshold: float = 0.05, compile_fn=None, run_fn=None, check_fn=None,
                 ref_exe: Path | None = None, paired_fn=None):
        self.bench, self.space, self.cc = bench, space, cc
        self.fixed_flags = list(fixed_flags)
        self.build_dir, self.failures_dir = Path(build_dir), Path(failures_dir)
        self.warmup, self.reps = warmup, reps
        self.compile_timeout_s, self.run_timeout_s = compile_timeout_s, run_timeout_s
        self.cv_threshold = cv_threshold
        self.compile_fn = compile_fn or compiler_driver.compile
        self.run_fn = run_fn or runner.run
        self.check_fn = check_fn or correctness.check
        # paired mode: every measured config alternates with this -O3 executable
        self.ref_exe = ref_exe
        self.paired_fn = paired_fn or runner.run_paired
        self.measured: dict[str, EvalRecord] = {}   # binary sha256 -> record that measured it

    def _measure(self, exe):
        """-> (RunResult of the candidate, PairedResult or None)."""
        kw = {} if self.bench.timing == "kernel" else {"mode": self.bench.timing}
        if self.ref_exe is None:
            return self.run_fn(exe, self.bench.args, warmup=self.warmup, reps=self.reps,
                               timeout_s=self.run_timeout_s, **kw), None
        try:
            pr = self.paired_fn(exe, self.ref_exe, self.bench.args, warmup=self.warmup, reps=self.reps,
                                timeout_s=self.run_timeout_s, **kw)
        except RuntimeError as e:  # the -O3 reference itself failed: a machine problem, not this config
            status = RUN_TIMEOUT if "TIMEOUT" in str(e) else RUN_CRASH
            return runner.RunResult(status, stderr_tail=f"reference run failed: {e}"), None
        return pr.cand, pr

    @staticmethod
    def _spread(rr, pr) -> float:
        """Noise indicator: CV of the per-round ratios when paired, else of the run times."""
        if pr is not None and len(pr.ratios) > 1:
            return runner.summarize(pr.ratios)["cv"]
        return runner.summarize(rr.kernel_ns)["cv"]

    def evaluate(self, x, eval_id: int = 0) -> EvalRecord:
        x = np.asarray(x)
        assert self.space.is_valid(x), f"invalid configuration {x}"
        flags = self.space.to_flags(x)
        rec = EvalRecord(eval_id=eval_id, benchmark=self.bench.name, config_key=self.space.key(x),
                         flags=" ".join(flags), timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"))

        cr = self.compile_fn(self.bench, flags, self.build_dir, cc=self.cc, fixed=self.fixed_flags,
                             timeout_s=self.compile_timeout_s)
        rec.compile_time_s = round(cr.compile_time_s, 4)
        rec.file_size_bytes, rec.text_size_bytes = cr.file_size_bytes, cr.text_size_bytes
        rec.binary_sha256 = cr.sha256[:16] if cr.sha256 else None
        if cr.status != OK:
            rec.status = cr.status
            rec.note = (cr.stderr_tail or "").splitlines()[-1][:200] if cr.stderr_tail else ""
            return rec

        prev = self.measured.get(rec.binary_sha256)
        if prev is not None:                       # identical executable: reuse its measurement
            for f in _MEASUREMENT_FIELDS:
                setattr(rec, f, getattr(prev, f))
            rec.reused_from = prev.eval_id if prev.reused_from is None else prev.reused_from
            return rec

        rr, pr = self._measure(cr.exe_path)
        if rr.status == RUN_TIMEOUT:
            # a timeout can be transient (machine asleep or overloaded): retry once
            time.sleep(2)
            rr, pr = self._measure(cr.exe_path)
            rec.note = "timed out once, retried"
        if rr.status == OK and not self.check_fn(self.bench, rr.checksum):
            rr.status = WRONG_OUTPUT
        if rr.status == OK and self._spread(rr, pr) > self.cv_threshold:
            rr2, pr2 = self._measure(cr.exe_path)
            if rr2.status == OK and self.check_fn(self.bench, rr2.checksum):
                rr, pr = rr2, pr2
            rec.noisy = 1

        rec.status = rr.status
        rec.checksum = rr.checksum
        if rr.status == OK:
            st = runner.summarize(rr.kernel_ns)
            rec.median_kernel_ns, rec.min_kernel_ns = st["median"], st["min"]
            rec.iqr_kernel_ns, rec.cv = st["iqr"], round(st["cv"], 5)
            rec.n_reps = len(rr.kernel_ns)
            if pr is not None:
                rec.ref_median_kernel_ns = runner.summarize(pr.ref.kernel_ns)["median"]
                rec.ratio_to_ref = round(float(np.median(pr.ratios)), 6)
                rec.cv = round(runner.summarize(pr.ratios)["cv"], 5)
        else:
            rec.note = ((rec.note + "; ") if rec.note else "") + (rr.stderr_tail or "")[:200].replace("\n", " ")
            if rr.status == WRONG_OUTPUT:
                d = correctness.save_failure(self.bench, flags, cr.exe_path, WRONG_OUTPUT,
                                             self.failures_dir, rr.checksum)
                rec.note = f"archived to {d.name}"
        if rec.status != RUN_TIMEOUT:      # never cache a timeout: it may have been transient
            self.measured[rec.binary_sha256] = rec
        return rec
