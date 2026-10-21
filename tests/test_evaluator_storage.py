"""Evaluator status paths with fake compiler/runner, and CSV storage."""
from pathlib import Path

from bopass import COMPILE_ERROR, OK, RUN_TIMEOUT, WRONG_OUTPUT
from bopass.benchmarks import Benchmark
from bopass.compiler_driver import CompileResult
from bopass.evaluator import EvalRecord, Evaluator
from bopass.runner import RunResult
from bopass.storage import ResultStore


class FakeCompiler:
    def __init__(self, status=OK, sha_for=None):
        self.status, self.calls = status, 0
        self.sha_for = sha_for or (lambda flags: "".join(flags))

    def __call__(self, bench, flags, out_root, cc, fixed, timeout_s):
        self.calls += 1
        if self.status != OK:
            return CompileResult(self.status, compile_time_s=0.1, stderr_tail="error: boom")
        sha = (str(abs(hash(self.sha_for(flags)))) * 8)[:64]
        return CompileResult(OK, exe_path=Path("fake.exe"), compile_time_s=0.5, file_size_bytes=1000,
                             text_size_bytes=500, sha256=sha)


class FakeRunner:
    def __init__(self, results):
        self.results, self.calls = list(results), 0

    def __call__(self, exe, args, warmup, reps, timeout_s):
        self.calls += 1
        return self.results.pop(0)


def _ev(small_space, tmp_path, comp, runner, check=lambda b, c: c == "7", cv=0.05):
    bench = Benchmark("fake", tmp_path / "fake.c", ())
    return Evaluator(bench, small_space, "cc", [], tmp_path / "b", tmp_path / "f",
                     compile_fn=comp, run_fn=runner, check_fn=check, cv_threshold=cv)


def ok_run(times=(100, 101, 102)):
    return RunResult(OK, list(times), list(times), "7", 0)


def test_ok_path(small_space, tmp_path):
    ev = _ev(small_space, tmp_path, FakeCompiler(), FakeRunner([ok_run()]))
    r = ev.evaluate(small_space.reference("O3"), 0)
    assert r.status == OK and r.median_kernel_ns == 101 and r.n_reps == 3 and r.noisy == 0


def test_compile_error_path(small_space, tmp_path):
    runner = FakeRunner([])
    r = _ev(small_space, tmp_path, FakeCompiler(COMPILE_ERROR), runner).evaluate(small_space.reference("O3"))
    assert r.status == COMPILE_ERROR and runner.calls == 0 and "boom" in r.note


def test_run_timeout_path(small_space, tmp_path):
    r = _ev(small_space, tmp_path, FakeCompiler(), FakeRunner([RunResult(RUN_TIMEOUT)] * 2)).evaluate(
        small_space.reference("O3"))
    assert r.status == RUN_TIMEOUT and r.median_kernel_ns is None


def test_wrong_output_is_archived(small_space, tmp_path):
    bad = RunResult(OK, [1, 1, 1], [1, 1, 1], "999", 0)
    r = _ev(small_space, tmp_path, FakeCompiler(), FakeRunner([bad])).evaluate(small_space.reference("O3"))
    assert r.status == WRONG_OUTPUT
    assert any((tmp_path / "f").iterdir())


def test_binary_cache_hit_skips_running(small_space, tmp_path):
    comp = FakeCompiler(sha_for=lambda flags: "same")       # every config -> identical binary
    runner = FakeRunner([ok_run()])
    ev = _ev(small_space, tmp_path, comp, runner)
    a = ev.evaluate(small_space.reference("O3"), 0)
    b = ev.evaluate(small_space.reference("O2"), 1)
    assert runner.calls == 1 and b.reused_from == 0 and b.median_kernel_ns == a.median_kernel_ns


def test_noisy_measurement_is_rerun(small_space, tmp_path):
    runner = FakeRunner([ok_run((100, 200, 300)), ok_run((150, 151, 152))])
    r = _ev(small_space, tmp_path, FakeCompiler(), runner).evaluate(small_space.reference("O3"))
    assert runner.calls == 2 and r.noisy == 1 and r.median_kernel_ns == 151


def test_paired_measurement_records_ratio(small_space, tmp_path):
    from bopass.runner import PairedResult

    def fake_paired(exe, ref_exe, args, warmup, reps, timeout_s):
        # machine slows down 30% halfway: raw times drift, ratios do not
        cand = RunResult(OK, [90, 90, 117, 117], [0] * 4, "7", 0)
        ref = RunResult(OK, [100, 100, 130, 130], [0] * 4, "7", 0)
        return PairedResult(cand, ref, [0.9, 0.9, 0.9, 0.9])

    bench = Benchmark("fake", tmp_path / "fake.c", ())
    ev = Evaluator(bench, small_space, "cc", [], tmp_path / "b", tmp_path / "f", compile_fn=FakeCompiler(),
                   check_fn=lambda b, c: True, ref_exe=Path("ref.exe"), paired_fn=fake_paired)
    r = ev.evaluate(small_space.reference("O2"), 0)
    assert r.status == OK and r.ratio_to_ref == 0.9 and r.ref_median_kernel_ns == 115 and r.noisy == 0


def test_timeout_is_retried_once_and_not_cached(small_space, tmp_path):
    runner = FakeRunner([RunResult(RUN_TIMEOUT), ok_run()])
    ev = _ev(small_space, tmp_path, FakeCompiler(), runner)
    r = ev.evaluate(small_space.reference("O3"), 0)
    assert r.status == OK and runner.calls == 2 and "retried" in r.note
    runner2 = FakeRunner([RunResult(RUN_TIMEOUT), RunResult(RUN_TIMEOUT), ok_run()])
    ev2 = _ev(small_space, tmp_path, FakeCompiler(), runner2)
    assert ev2.evaluate(small_space.reference("O3"), 0).status == RUN_TIMEOUT
    assert ev2.evaluate(small_space.reference("O3"), 1).status == OK      # same binary re-measured


def test_reference_failure_is_recorded_not_raised(small_space, tmp_path):
    def broken_paired(*a, **k):
        raise RuntimeError("reference executable failed (RUN_TIMEOUT): ")

    bench = Benchmark("fake", tmp_path / "fake.c", ())
    ev = Evaluator(bench, small_space, "cc", [], tmp_path / "b", tmp_path / "f", compile_fn=FakeCompiler(),
                   check_fn=lambda b, c: True, ref_exe=Path("ref.exe"), paired_fn=broken_paired)
    r = ev.evaluate(small_space.reference("O2"), 0)
    assert r.status == RUN_TIMEOUT and "reference run failed" in r.note


def test_storage_round_trip(tmp_path):
    s = ResultStore(tmp_path)
    s.append(EvalRecord(experiment_id="e", eval_id=0, config_key="0101", status=OK, y=-0.01,
                        median_kernel_ns=12.5, noisy=0))
    s.append(EvalRecord(experiment_id="e", eval_id=1, config_key="0110", status=COMPILE_ERROR))
    rows = s.load()
    assert [r.eval_id for r in rows] == [0, 1]
    assert rows[0].y == -0.01 and rows[0].median_kernel_ns == 12.5 and rows[1].y is None


def test_storage_tolerates_truncated_last_line(tmp_path):
    s = ResultStore(tmp_path)
    s.append(EvalRecord(experiment_id="e", eval_id=0, config_key="0101", status=OK, y=0.0))
    with open(s.csv_path, "a", encoding="utf-8") as f:
        f.write("e,1,fake,bo,0,01")                          # crash mid-write
    assert len(s.load()) == 1
