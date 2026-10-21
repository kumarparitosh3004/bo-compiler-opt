"""Shared fixtures. Tests that need a real compiler are skipped when none is found."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bopass.benchmarks import Benchmark  # noqa: E402
from bopass.compiler_driver import compile  # noqa: E402
from bopass.config import compiler_path, fixed_flags, load_experiment  # noqa: E402
from bopass.runner import run  # noqa: E402
from bopass.space import Flag, SearchSpace  # noqa: E402

DATA = Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def cfg():
    return load_experiment()


@pytest.fixture(scope="session")
def cc(cfg):
    c = compiler_path(cfg)
    if not (shutil.which(c) or Path(c).exists()):
        pytest.skip(f"compiler {c!r} not available")
    return c


@pytest.fixture(scope="session")
def fixed(cfg):
    return fixed_flags(cfg)


@pytest.fixture
def small_space():
    """4 flags with a dependency, defaults resembling GCC's."""
    return SearchSpace([
        Flag("tree-pre", {"O2": 1, "O3": 1}),
        Flag("tree-partial-pre", {"O2": 0, "O3": 1}, requires=("tree-pre",)),
        Flag("unroll-all-loops", {"O2": 0, "O3": 0}),
        Flag("tree-loop-vectorize", {"O2": 1, "O3": 1}),
    ])


@pytest.fixture(scope="session")
def toy_bench(tmp_path_factory, cc, fixed):
    """Toy benchmark with a reference checksum generated from its -O0 build."""
    d = tmp_path_factory.mktemp("toy")
    b = Benchmark(name="toy", source=DATA / "toy" / "toy.c", args=("100000", "40"),
                  expected_path=d / "expected.txt")
    cr = compile(b, ["-O0"], d / "build", cc=cc, fixed=fixed)
    assert cr.status == "OK", cr.stderr_tail
    rr = run(cr.exe_path, b.args, warmup=0, reps=1)
    assert rr.status == "OK"
    b.expected_path.write_text(rr.checksum + "\n")
    return b


def bad_bench(name: str, tmp: Path) -> Benchmark:
    return Benchmark(name=name, source=DATA / "bad" / f"{name}.c", args=(), expected_path=tmp / "e.txt")


def synthetic_objective(dim: int, seed: int = 123):
    """Deterministic 'true' objective on bit vectors: weighted bits + 2 interactions."""
    rng = np.random.default_rng(seed)
    w = rng.normal(0, 1, dim)
    i1, j1, i2, j2 = rng.choice(dim, 4, replace=False)

    def f(x):
        x = np.asarray(x, dtype=float)
        return float(w @ x + 1.5 * x[i1] * x[j1] - 1.5 * x[i2] * x[j2])

    return f
