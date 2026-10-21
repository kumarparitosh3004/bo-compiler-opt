"""Correctness checking against reference checksums produced by the -O0 build."""
from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path

from .benchmarks import Benchmark


def expected(bench: Benchmark) -> str:
    if not bench.expected_path.exists():
        raise FileNotFoundError(
            f"no reference output for {bench.name}; run scripts/make_references.py first")
    return bench.expected_path.read_text(encoding="utf-8").strip()


def matches(bench: Benchmark, got: str | None, want: str) -> bool:
    if got is None:
        return False
    if bench.checksum == "float":
        try:
            g, w = float(got), float(want)
        except ValueError:
            return False
        return abs(g - w) <= bench.rel_tol * max(abs(w), 1e-300)
    return got.strip() == want.strip()


def check(bench: Benchmark, checksum: str | None) -> bool:
    return matches(bench, checksum, expected(bench))


def save_failure(bench: Benchmark, flags: list[str], exe: Path | None, reason: str,
                 failures_dir: Path, got: str | None = None) -> Path:
    """Archive a failing binary and its flags for later investigation."""
    stamp = time.strftime("%Y%m%dT%H%M%S")
    tag = hashlib.sha256(" ".join(flags).encode()).hexdigest()[:10]
    d = Path(failures_dir) / f"{bench.name}_{stamp}_{tag}"
    d.mkdir(parents=True, exist_ok=True)
    if exe and Path(exe).exists():
        shutil.copy2(exe, d / Path(exe).name)
    (d / "failure.json").write_text(json.dumps({
        "benchmark": bench.name, "reason": reason, "flags": flags,
        "got_checksum": got, "expected_checksum": _safe_expected(bench),
    }, indent=2), encoding="utf-8")
    return d


def _safe_expected(bench: Benchmark):
    try:
        return expected(bench)
    except FileNotFoundError:
        return None
