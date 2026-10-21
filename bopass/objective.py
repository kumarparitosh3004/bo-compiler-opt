"""Objective function.

    y(x) = ln( median kernel time(x) / median kernel time(-O3) )

Minimized. y < 0 means faster than -O3; y = -0.05 is about 4.9 % faster.
Compile time and binary size are recorded but deliberately not part of y.
"""
from __future__ import annotations

import math


def objective(median_ns: float, ref_ns: float) -> float:
    if median_ns <= 0 or ref_ns <= 0:
        raise ValueError("timings must be positive")
    return math.log(median_ns / ref_ns)


def pct_faster(y: float) -> float:
    """Percent improvement over the reference implied by y (positive = faster)."""
    return (1.0 - math.exp(y)) * 100.0


def penalty_value(ok_ys: list[float], penalty: float = 1.0) -> float:
    """Value fed to the surrogate for a failed evaluation: worst OK y + penalty."""
    return (max(ok_ys) if ok_ys else 0.0) + penalty
