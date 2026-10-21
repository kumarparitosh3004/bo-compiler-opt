"""End-to-end: real compiler, toy benchmark, full search loop."""
import json
import math

from bopass import COMPILE_ERROR, OK
from bopass.orchestrator import run_search
from bopass.space import Flag, SearchSpace
from bopass.storage import ResultStore


def _cfg(cfg, **over):
    c = dict(cfg)
    c.update(n_init=4, search_reps=2, warmup=0, bo={"pool_size": 200, "gp_restarts": 0},
             cv_threshold=10.0, wallclock_cap_h=1)
    c.update(over)
    return c


def _go(cfg, toy_bench, space, tmp_path, budget, method="bo", seed=0, t_ref_ns=1e7):
    return run_search("toy", method, seed, cfg, budget=budget, results_root=tmp_path / "res",
                      build_root=tmp_path / "build", t_ref_ns=t_ref_ns, run_timeout_s=20,
                      benchmarks={"toy": toy_bench}, space=space)


def test_paired_reference(cfg, toy_bench, tmp_path):
    _go(_cfg(cfg, paired_reference=True), toy_bench, _space(), tmp_path, budget=4, method="random",
        t_ref_ns=None)
    rows = ResultStore(tmp_path / "res" / "toy_random_s0").load()
    assert len(rows) == 4
    for r in rows:
        if r.status == OK:
            assert r.ratio_to_ref is not None and r.ref_median_kernel_ns is not None
            assert abs(r.y - math.log(r.ratio_to_ref)) < 1e-5
    assert abs(rows[0].ratio_to_ref - 1.0) < 0.25            # x_O3 paired with itself


def test_reference_measured_in_run(cfg, toy_bench, tmp_path):
    _go(_cfg(cfg, paired_reference=False), toy_bench, _space(), tmp_path, budget=4, method="random",
        t_ref_ns=None)
    rows = ResultStore(tmp_path / "res" / "toy_random_s0").load()
    assert rows[0].config_key == _space().key(_space().reference("O3"))
    assert rows[0].y == 0.0                                  # x_O3 is its own reference
    m = json.loads((tmp_path / "res" / "toy_random_s0" / "manifest.json").read_text())
    assert m["t_ref_O3_ns"] == rows[0].median_kernel_ns
    # resuming keeps the stored reference
    _go(_cfg(cfg, paired_reference=False), toy_bench, _space(), tmp_path, budget=6, method="random",
        t_ref_ns=None)
    assert len(ResultStore(tmp_path / "res" / "toy_random_s0").load()) == 6


def _space():
    return SearchSpace([Flag("tree-loop-vectorize", {"O2": 1, "O3": 1}),
                        Flag("unroll-all-loops", {"O2": 0, "O3": 0}),
                        Flag("tree-pre", {"O2": 1, "O3": 1}),
                        Flag("gcse", {"O2": 1, "O3": 1})])


def test_end_to_end_small(cfg, toy_bench, tmp_path):
    summary = _go(_cfg(cfg), toy_bench, _space(), tmp_path, budget=10)
    rows = ResultStore(tmp_path / "res" / "toy_bo_s0").load()
    assert len(rows) == 10
    assert len({r.config_key for r in rows}) == 10              # no duplicate configurations
    ok_ys = [r.y for r in rows if r.status == OK]
    assert ok_ys and summary["best_y"] == min(ok_ys)
    assert all(r.best_y_so_far is not None for r in rows)
    m = json.loads((tmp_path / "res" / "toy_bo_s0" / "manifest.json").read_text())
    assert m["env"]["compiler_version"] != "unknown" and "finished_at" in m
    assert summary["unique_binaries"] <= 10


def test_resume(cfg, toy_bench, tmp_path):
    c = _cfg(cfg)
    _go(c, toy_bench, _space(), tmp_path, budget=5, method="random")
    store = ResultStore(tmp_path / "res" / "toy_random_s0")
    first = [r.config_key for r in store.load()]
    _go(c, toy_bench, _space(), tmp_path, budget=10, method="random")
    rows = store.load()
    assert len(rows) == 10 and [r.config_key for r in rows[:5]] == first
    assert len({r.config_key for r in rows}) == 10
    assert sorted(r.eval_id for r in rows) == list(range(10))


def test_failure_injection_keeps_going(cfg, toy_bench, tmp_path):
    space = SearchSpace(list(_space().flags) + [Flag("this-flag-does-not-exist", {"O2": 0, "O3": 0})])
    _go(_cfg(cfg), toy_bench, space, tmp_path, budget=12, method="random")
    rows = ResultStore(tmp_path / "res" / "toy_random_s0").load()
    assert len(rows) == 12
    assert any(r.status == COMPILE_ERROR for r in rows) and any(r.status == OK for r in rows)
    for r in rows:
        if r.status == COMPILE_ERROR:
            assert r.y is None and r.y_used_by_model is not None
