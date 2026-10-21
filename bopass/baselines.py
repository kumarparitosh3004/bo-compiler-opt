"""Access to baseline measurements (results/baselines/baselines.csv)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import RESULTS_DIR

BASELINES_CSV = RESULTS_DIR / "baselines" / "baselines.csv"


def load(path: Path = BASELINES_CSV) -> pd.DataFrame:
    if not Path(path).exists():
        raise FileNotFoundError(f"{path} not found; run scripts/run_baselines.py first")
    return pd.read_csv(path)


def median_ns(bench: str, level: str, path: Path = BASELINES_CSV) -> float:
    df = load(path)
    row = df[(df.benchmark == bench) & (df.level == level.lstrip("-"))]
    if row.empty:
        raise KeyError(f"no baseline for {bench} {level}; run scripts/run_baselines.py --bench {bench}")
    return float(row.iloc[0].median_kernel_ns)
