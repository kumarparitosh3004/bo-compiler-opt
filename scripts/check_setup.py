"""Check that this machine can run PassTune: Python packages, a real GCC, and
every benchmark building and reproducing its reference output.

usage: python scripts/check_setup.py [--quick] [--fix-references]

  --quick            build and run only two small benchmarks
  --fix-references   if a benchmark's -O0 output differs from the stored
                     reference (possible on a different CPU or C library),
                     store this machine's -O0 output as the new reference
"""
from __future__ import annotations

import argparse
import importlib
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GREEN, RED, YELLOW, END = ("\033[32m", "\033[31m", "\033[33m", "\033[0m") if sys.stdout.isatty() else ("",) * 4
PACKAGES = ["flask", "numpy", "scipy", "sklearn", "pandas", "matplotlib", "yaml", "docx"]


def ok(msg):
    print(f"  {GREEN}OK{END}    {msg}")


def bad(msg):
    print(f"  {RED}FAIL{END}  {msg}")


def warn(msg):
    print(f"  {YELLOW}WARN{END}  {msg}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--fix-references", action="store_true")
    a = ap.parse_args()
    failed = False

    print("\nPython")
    if sys.version_info < (3, 10):
        bad(f"Python {platform.python_version()} is too old; 3.10 or newer is needed")
        return 1
    ok(f"Python {platform.python_version()} on {platform.system()} {platform.machine()}")
    for name in PACKAGES:
        try:
            m = importlib.import_module(name)
            ok(f"{name} {getattr(m, '__version__', '')}".rstrip())
        except ImportError as e:
            bad(f"{name} is missing ({e}); run the setup script again")
            failed = True
    if failed:
        return 1

    from bopass import OK
    from bopass.benchmarks import load_benchmarks
    from bopass.compiler_driver import compile, compiler_version
    from bopass.config import BUILD_DIR, compiler_path, fixed_flags, load_experiment
    from bopass.correctness import expected, matches
    from bopass.runner import run

    print("\nCompiler")
    cfg = load_experiment()
    cc, fixed = compiler_path(cfg), fixed_flags(cfg)
    ver = compiler_version(cc)
    if ver == "unknown":
        bad(f"'{cc}' was not found. Install GCC (macOS: brew install gcc) or set it in config/local.yaml")
        return 1
    if "clang" in ver.lower():
        bad(f"'{cc}' is Apple clang ({ver}), not GCC. Install GCC with: brew install gcc")
        return 1
    ok(f"{cc}: {ver}")

    print("\nBenchmarks (build -O0 and -O3, run, compare with reference output)")
    benches = load_benchmarks()
    names = ["recursive", "sort"] if a.quick else list(benches)
    for name in names:
        b = benches[name]
        outs = {}
        for lvl in ("-O0", "-O3"):
            cr = compile(b, [lvl], BUILD_DIR / "check", cc=cc, fixed=fixed)
            if cr.status != OK:
                bad(f"{name} {lvl}: build failed\n{cr.stderr_tail}")
                failed = True
                break
            rr = run(cr.exe_path, b.args, warmup=0, reps=1, timeout_s=600, mode=b.timing)
            if rr.status != OK:
                bad(f"{name} {lvl}: run failed ({rr.status})")
                failed = True
                break
            outs[lvl] = rr
        if len(outs) < 2:
            continue
        want = expected(b)
        o0, o3 = outs["-O0"], outs["-O3"]
        if not matches(b, o0.checksum, want):
            if a.fix_references:
                b.expected_path.write_text(o0.checksum + "\n", encoding="utf-8")
                want = o0.checksum
                warn(f"{name}: reference updated for this machine ({o0.checksum})")
            else:
                bad(f"{name}: -O0 output {o0.checksum} differs from reference {want}; "
                    "re-run with --fix-references to store this machine's output")
                failed = True
                continue
        if not matches(b, o3.checksum, want):
            bad(f"{name}: -O3 output {o3.checksum} differs from -O0 output {want}")
            failed = True
            continue
        ok(f"{name:10s} correct   -O3 {(o3.kernel_ns or o3.wall_ns)[0] / 1e6:8.1f} ms")

    print()
    if failed:
        print(f"{RED}Some checks failed.{END} See the messages above.")
        return 1
    print(f"{GREEN}All checks passed.{END} Start the app with the run script.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
