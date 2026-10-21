"""Statistics for the Phase 4 comparison."""
from __future__ import annotations

import numpy as np
from scipy.stats import mannwhitneyu


def geomean(xs) -> float:
    a = np.asarray([x for x in xs if x is not None and x > 0], dtype=float)
    return float(np.exp(np.log(a).mean())) if a.size else float("nan")


def speedup(ref_times, cand_times) -> float:
    """median(ref) / median(candidate): > 1 means the candidate is faster."""
    return float(np.median(ref_times) / np.median(cand_times))


def bootstrap_speedup_ci(ref_times, cand_times, n: int = 10_000, seed: int = 0,
                         alpha: float = 0.05) -> tuple[float, float]:
    """Percentile bootstrap CI of the ratio of medians, resampling both groups."""
    rng = np.random.default_rng(seed)
    r = np.asarray(ref_times, dtype=float)
    c = np.asarray(cand_times, dtype=float)
    rb = np.median(rng.choice(r, (n, r.size)), axis=1)
    cb = np.median(rng.choice(c, (n, c.size)), axis=1)
    ratios = rb / cb
    return float(np.quantile(ratios, alpha / 2)), float(np.quantile(ratios, 1 - alpha / 2))


def mann_whitney_p(a, b) -> float:
    return float(mannwhitneyu(a, b, alternative="two-sided").pvalue)


def verdict(s: float, ci: tuple[float, float], p: float, noise_floor_pct: float) -> str:
    """'faster' / 'slower' only if significant (p < 0.05), the CI excludes 1, and the
    difference exceeds 2x the benchmark's measured noise floor."""
    thresh = 2 * noise_floor_pct / 100
    if p < 0.05 and ci[0] > 1 and s - 1 > thresh:
        return "faster"
    if p < 0.05 and ci[1] < 1 and 1 - s > thresh:
        return "slower"
    return "no measurable difference"


def pct(s: float) -> float:
    """Speed-up -> percent change in run time, positive = faster: (t_ref - t) / t_ref * 100."""
    return (1 - 1 / s) * 100
