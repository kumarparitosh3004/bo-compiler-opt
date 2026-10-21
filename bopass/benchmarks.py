"""Benchmark manifest loading."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .config import ROOT, load_yaml, resolve

MANIFEST = ROOT / "benchmarks" / "benchmarks.yaml"


@dataclass(frozen=True)
class Benchmark:
    name: str
    source: Path
    args: tuple[str, ...]
    checksum: str = "int"            # "int" (exact) or "float" (relative tolerance)
    rel_tol: float = 1e-9
    link_flags: tuple[str, ...] = ()
    args_alt: tuple[str, ...] = ()
    run_timeout_s: float | None = None
    timing: str = "kernel"          # "kernel" (KERNEL_NS line) or "wall" (whole process)
    real_data: bool = False         # input is a real-world data file (benchmarks/data/)
    expected_path: Path = field(default=None)  # type: ignore[assignment]

    def __post_init__(self):
        if self.expected_path is None:
            object.__setattr__(self, "expected_path", self.source.parent / "expected.txt")


def _arg(a) -> str:
    """'@relative/path' names a data file inside the project; pass it as an absolute path."""
    a = str(a)
    return str(resolve(a[1:])) if a.startswith("@") else a


def from_dict(d: dict) -> Benchmark:
    return Benchmark(
        name=d["name"],
        source=resolve(d["source"]),
        args=tuple(_arg(a) for a in d.get("args", [])),
        checksum=d.get("checksum", "int"),
        rel_tol=float(d.get("rel_tol", 1e-9)),
        link_flags=tuple(d.get("link_flags", [])),
        args_alt=tuple(_arg(a) for a in d.get("args_alt", [])),
        real_data=bool(d.get("real_data", False)),
        run_timeout_s=d.get("run_timeout_s"),
        timing=d.get("timing", "kernel"),
        expected_path=resolve(d["expected"]) if "expected" in d else None,
    )


def load_benchmarks(manifest: str | Path = MANIFEST) -> dict[str, Benchmark]:
    return {d["name"]: from_dict(d) for d in load_yaml(manifest)}
