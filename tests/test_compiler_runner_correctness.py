"""Compiler driver, runner and correctness modules against real (tiny) programs."""
from bopass import COMPILE_ERROR, COMPILE_TIMEOUT, OK, RUN_CRASH, RUN_TIMEOUT
from bopass.benchmarks import Benchmark
from bopass.compiler_driver import compile, effective_flags
from bopass.correctness import check, matches
from bopass.runner import parse_output, run, summarize

from .conftest import bad_bench


def test_compile_ok_records_metadata(toy_bench, cc, fixed, tmp_path):
    cr = compile(toy_bench, ["-O2"], tmp_path, cc=cc, fixed=fixed)
    assert cr.status == OK
    assert cr.exe_path.exists() and cr.file_size_bytes > 0 and len(cr.sha256) == 64
    assert cr.compile_time_s > 0


def test_builds_are_deterministic(toy_bench, cc, fixed, tmp_path):
    a = compile(toy_bench, ["-O2"], tmp_path / "a", cc=cc, fixed=fixed)
    b = compile(toy_bench, ["-O2"], tmp_path / "b", cc=cc, fixed=fixed)
    assert a.sha256 == b.sha256


def test_invalid_flag_is_compile_error(toy_bench, cc, fixed, tmp_path):
    cr = compile(toy_bench, ["-O2", "-fthis-flag-does-not-exist"], tmp_path, cc=cc, fixed=fixed)
    assert cr.status == COMPILE_ERROR and cr.stderr_tail


def test_syntax_error_is_compile_error(cc, fixed, tmp_path):
    cr = compile(bad_bench("syntax_error", tmp_path), ["-O2"], tmp_path, cc=cc, fixed=fixed)
    assert cr.status == COMPILE_ERROR


def test_compile_timeout(toy_bench, cc, fixed, tmp_path):
    cr = compile(toy_bench, ["-O3"], tmp_path, cc=cc, fixed=fixed, timeout_s=0.001)
    assert cr.status == COMPILE_TIMEOUT


def test_effective_flags_parses_gcc_q(cc):
    st = effective_flags(cc, ["-O2", "-fno-tree-pre"])
    assert st.get("tree-pre") is False
    assert effective_flags(cc, ["-O2"]).get("tree-pre") is True


def test_run_ok_and_correct(toy_bench, cc, fixed, tmp_path):
    cr = compile(toy_bench, ["-O3"], tmp_path, cc=cc, fixed=fixed)
    rr = run(cr.exe_path, toy_bench.args, warmup=1, reps=3)
    assert rr.status == OK and len(rr.kernel_ns) == 3
    assert check(toy_bench, rr.checksum)


def test_crash_and_garbage_output_are_run_crash(cc, fixed, tmp_path):
    for name in ("crash", "garbage"):
        cr = compile(bad_bench(name, tmp_path), ["-O0"], tmp_path, cc=cc, fixed=fixed)
        assert run(cr.exe_path, (), warmup=0, reps=1, timeout_s=10).status == RUN_CRASH


def test_infinite_loop_is_run_timeout(cc, fixed, tmp_path):
    cr = compile(bad_bench("forever", tmp_path), ["-O0"], tmp_path, cc=cc, fixed=fixed)
    assert run(cr.exe_path, (), warmup=0, reps=1, timeout_s=1).status == RUN_TIMEOUT


def test_wrong_checksum_detected(tmp_path):
    b = Benchmark("x", tmp_path / "x.c", (), checksum="int", expected_path=tmp_path / "e.txt")
    b.expected_path.write_text("42\n")
    assert check(b, "42") and not check(b, "43") and not check(b, None)


def test_float_checksum_tolerance(tmp_path):
    b = Benchmark("x", tmp_path / "x.c", (), checksum="float", rel_tol=1e-9)
    assert matches(b, "1.0000000001", "1.0")
    assert not matches(b, "1.001", "1.0")


def test_parse_output_and_summarize():
    assert parse_output("CHECKSUM=12\nKERNEL_NS=345\n") == ("12", 345)
    assert parse_output("nothing") == (None, None)
    s = summarize([10, 20, 30, 40])
    assert s["median"] == 25 and s["min"] == 10 and s["cv"] > 0
