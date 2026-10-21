"""Phase 2 (Member 1): create reference checksums from the -O0 build and check
that -O1, -O2 and -O3 reproduce them.

usage: python scripts/make_references.py [--bench matmul ...]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bopass import OK  # noqa: E402
from bopass.benchmarks import load_benchmarks  # noqa: E402
from bopass.compiler_driver import compile  # noqa: E402
from bopass.config import BUILD_DIR, compiler_path, fixed_flags, load_experiment  # noqa: E402
from bopass.correctness import matches  # noqa: E402
from bopass.runner import run  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", nargs="*")
    a = ap.parse_args()
    cfg = load_experiment()
    cc, fixed = compiler_path(cfg), fixed_flags(cfg)
    benches = load_benchmarks()
    failed = False
    for name in a.bench or list(benches):
        b = benches[name]
        cr = compile(b, ["-O0"], BUILD_DIR / "reference", cc=cc, fixed=fixed)
        if cr.status != OK:
            print(f"{name}: -O0 build failed\n{cr.stderr_tail}")
            failed = True
            continue
        rr = run(cr.exe_path, b.args, warmup=0, reps=1, timeout_s=600)
        if rr.status != OK:
            print(f"{name}: -O0 run failed ({rr.status})")
            failed = True
            continue
        b.expected_path.write_text(rr.checksum + "\n", encoding="utf-8")
        line = [f"{name:10s} reference={rr.checksum}"]
        for lvl in ("-O1", "-O2", "-O3"):
            c2 = compile(b, [lvl], BUILD_DIR / "reference", cc=cc, fixed=fixed)
            r2 = run(c2.exe_path, b.args, warmup=0, reps=1, timeout_s=600) if c2.status == OK else None
            good = r2 is not None and r2.status == OK and matches(b, r2.checksum, rr.checksum)
            failed |= not good
            line.append(f"{lvl}:{'ok' if good else 'MISMATCH'}")
        print("  ".join(line))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
