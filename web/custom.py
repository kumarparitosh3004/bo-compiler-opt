"""User-supplied C programs ("bring your own program").

A program that prints CHECKSUM= and KERNEL_NS= lines (by including
benchmarks/common/bench_timer.h) is timed like the built-in benchmarks. Any
other program is timed as a whole process ("wall" mode) and its correctness is
checked against a hash of its standard output.
"""
from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

import yaml

from bopass import OK
from bopass.benchmarks import Benchmark, from_dict, load_benchmarks
from bopass.compiler_driver import compile
from bopass.config import BUILD_DIR, ROOT
from bopass.proc import run_cmd
from bopass.runner import parse_output

CUSTOM_DIR = ROOT / "benchmarks" / "custom"
REGISTRY = CUSTOM_DIR / "custom.yaml"
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
MAX_SOURCE_BYTES = 200_000


def _load_registry() -> list[dict]:
    if not REGISTRY.exists():
        return []
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or []


def _save_registry(entries: list[dict]) -> None:
    CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(yaml.safe_dump(entries, sort_keys=False), encoding="utf-8")


def custom_names() -> set[str]:
    return {e["name"] for e in _load_registry()}


def all_benchmarks() -> dict[str, Benchmark]:
    benches = load_benchmarks()
    for e in _load_registry():
        if e["name"] not in benches:
            benches[e["name"]] = from_dict(e)
    return benches


def _run(exe: Path, args: list[str], timeout_s: float = 120.0):
    p = run_cmd([str(exe), *args], timeout_s)
    if p.timed_out:
        raise ValueError(f"the program did not finish within {timeout_s:.0f} s")
    if p.returncode != 0:
        raise ValueError(f"the program exited with code {p.returncode}: {(p.stderr or '')[-400:]}")
    return p.stdout or ""


def register(name: str, source: str, args: list[str], cc: str, fixed: list[str]) -> dict:
    name = (name or "").strip().lower()
    if not NAME_RE.match(name):
        raise ValueError("name must start with a letter and use only a-z, 0-9 and _ (max 32 characters)")
    if name in load_benchmarks():
        raise ValueError(f"'{name}' is a built-in benchmark name")
    if len(source.encode()) > MAX_SOURCE_BYTES:
        raise ValueError("source file is too large (max 200 KB)")
    if "main" not in source:
        raise ValueError("the program needs a main() function")
    args = [str(a) for a in args if str(a).strip()]

    d = CUSTOM_DIR / name
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    src = d / f"{name}.c"
    src.write_text(source, encoding="utf-8")
    probe = Benchmark(name, src, tuple(args), link_flags=("-lm",), expected_path=d / "expected.txt")
    try:
        outs = {}
        for lvl in ("-O0", "-O3"):
            cr = compile(probe, [lvl], BUILD_DIR / "custom", cc=cc, fixed=fixed, timeout_s=120)
            if cr.status != OK:
                raise ValueError(f"compilation failed at {lvl}:\n{cr.stderr_tail}")
            outs[lvl] = _run(cr.exe_path, args)
        checksum, kernel = parse_output(outs["-O0"])
        if checksum is not None and kernel is not None:
            timing = "kernel"
            ctype = "float" if re.search(r"[.eE]", checksum) else "int"
            expected = checksum
            ok = parse_output(outs["-O3"])[0] is not None and (
                ctype == "int" and parse_output(outs["-O3"])[0] == checksum
                or ctype == "float" and abs(float(parse_output(outs["-O3"])[0]) - float(checksum))
                <= 1e-9 * max(abs(float(checksum)), 1e-300))
        else:
            timing, ctype = "wall", "int"
            expected = hashlib.sha256(outs["-O0"].encode()).hexdigest()[:16]
            ok = hashlib.sha256(outs["-O3"].encode()).hexdigest()[:16] == expected
        if not ok:
            raise ValueError("the -O3 build prints different output than the -O0 build "
                             "(non-deterministic output or undefined behaviour), so correctness cannot be checked")
    except Exception:
        shutil.rmtree(d, ignore_errors=True)
        raise
    (d / "expected.txt").write_text(expected + "\n", encoding="utf-8")
    rel = src.relative_to(ROOT).as_posix() if src.is_relative_to(ROOT) else str(src)
    entry = {"name": name, "source": rel, "args": args,
             "checksum": ctype, "rel_tol": 1e-9, "link_flags": ["-lm"], "timing": timing}
    entries = [e for e in _load_registry() if e["name"] != name] + [entry]
    _save_registry(entries)
    return {**entry, "custom": True}


def remove(name: str) -> None:
    if name not in custom_names():
        raise ValueError(f"'{name}' is not a custom program")
    _save_registry([e for e in _load_registry() if e["name"] != name])
    shutil.rmtree(CUSTOM_DIR / name, ignore_errors=True)
