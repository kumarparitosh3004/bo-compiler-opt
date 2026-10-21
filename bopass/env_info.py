"""Reproducibility manifest: software versions, machine, compiler, input hashes."""
from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path

from .compiler_driver import compiler_version
from .config import ROOT

PACKAGES = ("numpy", "scipy", "scikit-learn", "pandas", "matplotlib", "PyYAML", "pytest")


def _sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def git_commit() -> str | None:
    try:
        p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        return p.stdout.strip() or None if p.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def collect(cc: str, extra_files: list[Path] | None = None) -> dict:
    pkgs = {}
    for name in PACKAGES:
        try:
            pkgs[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pkgs[name] = None
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "git_commit": git_commit(),
        "compiler": cc,
        "compiler_version": compiler_version(cc),
        "os": platform.platform(),
        "machine": platform.machine(),
        "cpu": platform.processor(),
        "cpu_count": os.cpu_count(),
        "python": sys.version.split()[0],
        "packages": pkgs,
        "file_hashes": {str(Path(p).relative_to(ROOT)) if Path(p).is_relative_to(ROOT) else str(p): _sha(p)
                        for p in (extra_files or [])},
    }
