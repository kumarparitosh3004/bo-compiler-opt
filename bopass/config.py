"""Project paths and experiment configuration loading."""
from __future__ import annotations

import hashlib
import glob
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
RESULTS_DIR = Path(os.environ["BOPASS_RESULTS_DIR"]) if os.environ.get("BOPASS_RESULTS_DIR") else ROOT / "results"


def _build_dir() -> Path:
    """Where executables are written. Windows cannot launch an executable whose
    path exceeds 260 characters (even with long paths enabled), so a deep project
    location falls back to a short directory under the temp folder."""
    env = os.environ.get("BOPASS_BUILD_DIR")
    if env:
        return Path(env)
    d = ROOT / "build"
    if os.name == "nt" and len(str(d)) > 150:
        return Path(tempfile.gettempdir()) / "bopass_build" / hashlib.sha1(str(ROOT).encode()).hexdigest()[:8]
    return d


BUILD_DIR = _build_dir()


def load_yaml(path: str | Path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_experiment(path: str | Path = CONFIG_DIR / "experiment.yaml") -> dict:
    """Experiment settings, with per-machine overrides (e.g. `compiler:`) from the
    optional, git-ignored config/local.yaml."""
    cfg = load_yaml(path)
    local = CONFIG_DIR / "local.yaml"
    if local.exists():
        cfg.update(load_yaml(local) or {})
    return cfg


def find_real_gcc() -> str | None:
    """On macOS `gcc` is Apple clang, which ignores most GCC pass flags. Homebrew
    installs real GCC as gcc-<major>; return the newest one found."""
    found = set()
    for d in ["/opt/homebrew/bin", "/usr/local/bin", *os.environ.get("PATH", "").split(os.pathsep)]:
        found.update(p for p in glob.glob(os.path.join(d, "gcc-[0-9]*")) if re.search(r"gcc-\d+$", p))
    for p in sorted(found, key=lambda p: int(p.rsplit("-", 1)[1]), reverse=True):
        if shutil.which(p):
            return p
    return None


def compiler_path(cfg: dict) -> str:
    """The C compiler to use: $BOPASS_CC overrides the config file. A plain `gcc`
    on macOS is replaced by Homebrew GCC when it is installed."""
    cc = os.environ.get("BOPASS_CC") or cfg.get("compiler", "gcc")
    if cc == "gcc" and sys.platform == "darwin":
        cc = find_real_gcc() or cc
    return cc


def fixed_flags(cfg: dict) -> list[str]:
    """Flags added to every build, besides the search flags."""
    ff = cfg.get("fixed_flags", [])
    if isinstance(ff, dict):
        return list(ff.get("windows" if os.name == "nt" else "posix", []))
    return list(ff)


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p
