"""Compiler driver: turns a flag list into an executable and records cost metadata."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from . import COMPILE_ERROR, COMPILE_TIMEOUT, OK
from .benchmarks import Benchmark
from .proc import run_cmd


@dataclass
class CompileResult:
    status: str
    exe_path: Path | None = None
    compile_time_s: float = 0.0
    file_size_bytes: int | None = None
    text_size_bytes: int | None = None
    sha256: str | None = None
    stderr_tail: str = ""
    cmd: tuple[str, ...] = ()


def exe_name(stem: str) -> str:
    return stem + (".exe" if os.name == "nt" else "")


def flags_hash(flags: list[str]) -> str:
    return hashlib.sha256(" ".join(flags).encode()).hexdigest()[:16]


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tail(text: str, n: int = 20) -> str:
    return "\n".join((text or "").splitlines()[-n:])


def size_tool(cc: str) -> str | None:
    """`size` from the same toolchain directory as the compiler, else from PATH."""
    cc_path = shutil.which(cc) or cc
    candidate = Path(cc_path).parent / exe_name("size")
    if candidate.exists():
        return str(candidate)
    return shutil.which("size")


def _macho_text_size(tool: str, exe: Path) -> int | None:
    """Bytes in the Mach-O __text section, read from `size -m`."""
    try:
        out = subprocess.run([tool, "-m", str(exe)], capture_output=True, text=True, timeout=30).stdout
        for line in out.splitlines():
            s = line.strip()
            if s.startswith("Section __text:"):
                return int(s.split(":", 1)[1].strip())
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None
    return None


def text_size(exe: Path, tool: str | None) -> int | None:
    """Size of the machine code in bytes.

    GNU binutils `size` prints Berkeley format, whose first column is .text.
    Apple's `size` prints Mach-O *segment* sizes instead, and __TEXT is page
    aligned, so it reads 16384 for every small binary and carries no
    information. On that format `size -m` is used to read the real __text
    section, which is what the Berkeley first column means elsewhere.
    """
    if not tool:
        return None
    try:
        out = subprocess.run([tool, str(exe)], capture_output=True, text=True, timeout=30).stdout
        lines = out.strip().splitlines()
        if not lines:
            return None
        if "__TEXT" in lines[0]:
            return _macho_text_size(tool, exe)
        return int(lines[1].split()[0]) if len(lines) >= 2 else None
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def compile(bench: Benchmark, flags: list[str], out_root: Path, cc: str = "gcc",
            fixed: list[str] | None = None, timeout_s: float = 60.0,
            stem: str | None = None) -> CompileResult:
    """Compile one benchmark with the given optimization flags.

    The executable goes to out_root/<bench>/<hash of flags>/<bench>[.exe], so
    configurations never overwrite each other.
    """
    fixed = list(fixed or [])
    out_dir = Path(out_root) / bench.name / flags_hash(flags + fixed)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / exe_name(stem or bench.name)
    out.unlink(missing_ok=True)
    cmd = [cc, *flags, *fixed, str(bench.source), "-o", str(out), *bench.link_flags]
    t0 = time.perf_counter()
    try:
        p = run_cmd(cmd, timeout_s)
    except OSError as e:  # compiler not found etc.
        return CompileResult(COMPILE_ERROR, stderr_tail=str(e), cmd=tuple(cmd))
    dt = time.perf_counter() - t0
    if p.timed_out:
        return CompileResult(COMPILE_TIMEOUT, compile_time_s=dt, cmd=tuple(cmd))
    if p.returncode != 0 or not out.exists():
        return CompileResult(COMPILE_ERROR, compile_time_s=dt, stderr_tail=tail(p.stderr), cmd=tuple(cmd))
    return CompileResult(
        OK, exe_path=out, compile_time_s=dt, file_size_bytes=out.stat().st_size,
        text_size_bytes=text_size(out, size_tool(cc)), sha256=file_sha256(out),
        stderr_tail=tail(p.stderr, 5), cmd=tuple(cmd),
    )


def compiler_version(cc: str) -> str:
    try:
        out = subprocess.run([cc, "--version"], capture_output=True, text=True, timeout=30).stdout
        return out.splitlines()[0].strip() if out else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


_Q_LINE = re.compile(r"^\s+-f([\w-]+)\s+\[(enabled|disabled)\]")


def effective_flags(cc: str, options: list[str]) -> dict[str, bool]:
    """Effective on/off state of every -f optimization flag for a command line,
    as reported by `gcc -Q --help=optimizers <options>`."""
    out = subprocess.run([cc, "-Q", "--help=optimizers", *options],
                         capture_output=True, text=True, timeout=60).stdout
    states = {}
    for line in out.splitlines():
        m = _Q_LINE.match(line)
        if m:
            states[m.group(1)] = m.group(2) == "enabled"
    return states
