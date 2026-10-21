"""The optimization loop: ask -> evaluate -> objective -> store -> tell, with budget and resume."""
from __future__ import annotations

import logging
import time
import warnings
from pathlib import Path

import numpy as np

from . import OK, baselines, compiler_driver
from .benchmarks import Benchmark, load_benchmarks
from .config import BUILD_DIR, RESULTS_DIR, compiler_path, fixed_flags, resolve
from .env_info import collect
from .evaluator import EvalRecord, Evaluator
from .objective import objective
from .optimizer import BayesOpt, make_optimizer
from .optimizer.bo import make_gp
from .space import SearchSpace
from .storage import ResultStore


MAX_EVAL_S = 900.0  # longest plausible single evaluation; longer gaps are sleep


def active_seconds(elapsed: list[float | None]) -> float:
    """Active search time from the per-evaluation elapsed_s column: the sum of the
    increments, each capped at MAX_EVAL_S, so time spent asleep is not counted."""
    total, prev = 0.0, 0.0
    for e in elapsed:
        if e is None or e != e:   # missing / NaN
            continue
        inc = e - prev if e >= prev else e   # a resumed run restarts its clock
        total += min(max(inc, 0.0), MAX_EVAL_S)
        prev = e
    return total


def experiment_id(bench: str, method: str, seed: int, tag: str = "") -> str:
    return f"{bench}_{method}_s{seed}" + (f"_{tag}" if tag else "")


def initial_design(space: SearchSpace, seed: int, n_init: int) -> list[np.ndarray]:
    """x_O3 plus (n_init - 1) random valid configurations. Identical for BO and random search."""
    rng = np.random.default_rng([int(seed), 0])
    return [space.reference("O3")] + space.sample(rng, max(0, n_init - 1))


def _logger(exp_dir: Path, exp_id: str) -> logging.Logger:
    log = logging.getLogger(f"bopass.{exp_id}")
    log.setLevel(logging.INFO)
    log.propagate = False
    if not log.handlers:
        fmt = logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S")
        fh = logging.FileHandler(exp_dir / "log.txt", encoding="utf-8")
        sh = logging.StreamHandler()
        fh.setFormatter(fmt)
        sh.setFormatter(fmt)
        log.addHandler(fh)
        log.addHandler(sh)
    return log


def run_search(bench_name: str, method: str, seed: int, cfg: dict, budget: int | None = None,
               results_root: Path = RESULTS_DIR / "search", build_root: Path = BUILD_DIR / "search",
               t_ref_ns: float | None = None, run_timeout_s: float | None = None, tag: str = "",
               benchmarks: dict[str, Benchmark] | None = None, space: SearchSpace | None = None,
               evaluator: Evaluator | None = None, should_stop=None) -> dict:
    benchmarks = benchmarks or load_benchmarks()
    bench = benchmarks[bench_name]
    space = space or SearchSpace.from_yaml(resolve(cfg["flags_file"]))
    budget = int(budget or cfg["budget"])
    cc = compiler_path(cfg)
    exp_id = experiment_id(bench_name, method, seed, tag)
    store = ResultStore(Path(results_root) / exp_id)
    log = _logger(store.dir, exp_id)

    # The objective's -O3 reference is measured inside this run (evaluation 0 is
    # always x_O3), not taken from the stored baselines: machine speed drifts
    # between sessions (power source, thermals), and a stale reference would bias
    # every y. A t_ref_ns passed in explicitly (tests) is used as given.
    if run_timeout_s is None:
        try:
            run_timeout_s = max(10 * baselines.median_ns(bench_name, "O0") / 1e9, cfg.get("run_timeout_min_s", 5))
        except (FileNotFoundError, KeyError):
            run_timeout_s = 60.0

    if evaluator is None:
        ref_exe = None
        if cfg.get("paired_reference", True):
            # every measured configuration alternates with this -O3 build (see runner.run_paired)
            rc = compiler_driver.compile(bench, space.to_flags(space.reference("O3")),
                                         Path(build_root) / "reference", cc=cc, fixed=fixed_flags(cfg),
                                         timeout_s=cfg.get("compile_timeout_s", 60))
            if rc.status != OK:
                raise RuntimeError(f"[{exp_id}] could not build the -O3 reference: {rc.stderr_tail}")
            ref_exe = rc.exe_path
        evaluator = Evaluator(
            bench, space, cc, fixed_flags(cfg), Path(build_root), RESULTS_DIR / "failures",
            warmup=cfg.get("warmup", 1), reps=cfg.get("search_reps", 5),
            compile_timeout_s=cfg.get("compile_timeout_s", 60), run_timeout_s=run_timeout_s,
            cv_threshold=cfg.get("cv_threshold", 0.05), ref_exe=ref_exe)
    paired = evaluator.ref_exe is not None

    init = initial_design(space, seed, int(cfg.get("n_init", 8)))
    opt = make_optimizer(method, space, seed, init, cfg)

    manifest = store.read_json("manifest.json")
    env_now = collect(cc, [resolve(cfg["flags_file"]), bench.source])
    if manifest is not None:
        # Resuming replays the recorded evaluations into the optimizer, so the old
        # and new measurements end up in one objective. That is only sound on the
        # same toolchain and machine; otherwise the run must be kept separate.
        prev = manifest.get("env") or {}
        drift = [k for k in ("compiler_version", "machine")
                 if prev.get(k) is not None and prev.get(k) != env_now.get(k)]
        if drift:
            detail = "; ".join(f"{k} {prev.get(k)!r} -> {env_now.get(k)!r}" for k in drift)
            raise SystemExit(
                f"[{exp_id}] refusing to resume: recorded on a different setup ({detail}).\n"
                f"Timings from two machines must not be mixed into one search.\n"
                f"Use --tag NAME to start a separate run, or delete {store.dir} to redo it.")
    if manifest is None:
        manifest = {
            "experiment_id": exp_id, "benchmark": bench_name, "args": list(bench.args),
            "method": method, "seed": seed, "budget": budget, "n_init": cfg.get("n_init", 8),
            "bo": cfg.get("bo", {}), "failure_penalty": cfg.get("failure_penalty", 1.0),
            "search_reps": cfg.get("search_reps", 5), "warmup": cfg.get("warmup", 1),
            "t_ref_O3_ns": t_ref_ns, "run_timeout_s": run_timeout_s,
            "fixed_flags": fixed_flags(cfg), "flags": space.flag_names,
            "objective": ("y = ln(median per-round time ratio to a paired -O3 build)" if paired
                          else "y = ln(median time / in-run -O3 median)"),
            "base_levels": list(space.base_levels), "dim": space.dim,
            "env": env_now,
            "resumed_at": [],
        }
    else:
        manifest.setdefault("resumed_at", []).append(time.strftime("%Y-%m-%dT%H:%M:%S"))
        if t_ref_ns is None:
            t_ref_ns = manifest.get("t_ref_O3_ns")
    store.write_json("manifest.json", manifest)
    x_o3_key = space.key(space.reference("O3"))

    # resume: replay earlier evaluations into the optimizer and the binary cache
    done = store.load()
    for r in done:
        opt.tell(space.from_key(r.config_key), r.y, r.status == OK)
        if r.binary_sha256 and r.reused_from is None:
            evaluator.measured.setdefault(r.binary_sha256, r)
    if done:
        log.info(f"[{exp_id}] resuming with {len(done)} completed evaluations")

    # Active time: each evaluation contributes its own duration, capped at 15 min.
    # A longer gap can only be the machine sleeping, which must not count towards
    # the cap or the reported search cost.
    active_s = active_seconds([r.elapsed_s for r in sorted(done, key=lambda r: r.eval_id)])
    cap_s = float(cfg.get("wallclock_cap_h", 2)) * 3600
    while opt.n_told < budget:
        t_it = time.time()
        if should_stop is not None and should_stop():
            log.info(f"[{exp_id}] cancelled at {opt.n_told} evaluations")
            break
        if active_s > cap_s:
            log.info(f"[{exp_id}] wall-clock cap reached, stopping at {opt.n_told} evaluations")
            break
        x = opt.ask()
        rec: EvalRecord = evaluator.evaluate(x, eval_id=opt.n_told)
        rec.experiment_id, rec.method, rec.seed = exp_id, method, seed
        if not paired and t_ref_ns is None:
            if rec.config_key != x_o3_key or rec.status != OK:
                raise RuntimeError(f"[{exp_id}] the first evaluation must be a successful x_O3 "
                                   f"to set the objective reference (got {rec.config_key} {rec.status})")
            t_ref_ns = rec.median_kernel_ns
            manifest["t_ref_O3_ns"] = t_ref_ns
            store.write_json("manifest.json", manifest)
            log.info(f"[{exp_id}] -O3 reference for this run: {t_ref_ns / 1e6:.2f} ms")
        if rec.status == OK:
            if rec.ratio_to_ref is not None:      # paired: drift-free ratio to -O3
                rec.y = round(float(np.log(rec.ratio_to_ref)), 6)
            else:
                rec.y = round(objective(rec.median_kernel_ns, t_ref_ns), 6)
        opt.tell(x, rec.y, rec.status == OK)
        rec.y_used_by_model = round(float(opt.model_data()[1][-1]), 6)
        rec.best_y_so_far = opt.best()[1]
        rec.acq_value = opt.last_acq
        active_s += min(time.time() - t_it, MAX_EVAL_S)
        rec.elapsed_s = round(active_s, 2)
        store.append(rec)
        med = f"{rec.median_kernel_ns / 1e6:.1f}ms" if rec.median_kernel_ns else "-"
        y = f"{rec.y:+.4f}" if rec.y is not None else "fail"
        best = f"{rec.best_y_so_far:+.4f}" if rec.best_y_so_far is not None else "-"
        acq = f" EI={rec.acq_value:.2e}" if rec.acq_value is not None else ""
        reuse = " (reused)" if rec.reused_from is not None else ""
        log.info(f"[{exp_id}] {opt.n_told}/{budget} key={rec.config_key} status={rec.status} "
                 f"median={med} y={y} best={best}{acq}{reuse}")

    records = store.load()
    summary = summarize_run(records, space, t_ref_ns)
    if isinstance(opt, BayesOpt) and len(opt.history) >= 2:
        summary["length_scales"] = dict(zip(["base_level"] + space.flag_names, final_length_scales(opt)))
    manifest["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    store.write_json("manifest.json", manifest)
    store.write_json("summary.json", summary)
    if summary.get("best_key"):
        log.info(f"[{exp_id}] best y={summary['best_y']:+.4f} ({summary['best_pct_faster_than_O3']:+.2f}% vs -O3 "
                 f"during search) flags: {summary['best_diff_vs_O3']}")
    return summary


def final_length_scales(opt: BayesOpt) -> list[float]:
    X, y = opt.model_data()
    gp = make_gp(opt.space.dim, opt.seed, opt.gp_restarts)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gp.fit(X, y)
    return [float(v) for v in np.atleast_1d(gp.kernel_.k1.k2.length_scale)]


def summarize_run(records: list[EvalRecord], space: SearchSpace, t_ref_ns: float) -> dict:
    ok = [r for r in records if r.status == OK and r.y is not None]
    statuses = {}
    for r in records:
        statuses[r.status] = statuses.get(r.status, 0) + 1
    out = {
        "evaluations": len(records),
        "unique_binaries": len({r.binary_sha256 for r in records if r.binary_sha256}),
        "measured_runs": sum(1 for r in records if r.reused_from is None and r.median_kernel_ns is not None),
        "status_counts": statuses,
        "total_compile_time_s": round(sum(r.compile_time_s or 0 for r in records), 2),
        "search_wall_time_s": round(active_seconds([r.elapsed_s for r in sorted(records, key=lambda r: r.eval_id)]), 1),
        "t_ref_O3_ns": t_ref_ns,
    }
    if ok:
        b = min(ok, key=lambda r: r.y)
        x = space.from_key(b.config_key)
        out.update({
            "best_eval_id": b.eval_id, "best_key": b.config_key, "best_flags": b.flags,
            "best_y": b.y, "best_pct_faster_than_O3": round((1 - np.exp(b.y)) * 100, 3),
            "best_diff_vs_O3": space.describe_diff(x, "O3"),
        })
    return out
