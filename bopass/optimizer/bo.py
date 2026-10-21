"""Bayesian Optimization over binary flag vectors.

Surrogate:   Gaussian process, ConstantKernel * Matern(nu=2.5, ARD) + WhiteKernel
Acquisition: Expected Improvement (minimization), maximized over a candidate
             pool of random valid unseen configurations plus every 1-bit
             neighbour of the best configurations found so far.
"""
from __future__ import annotations

import warnings

import numpy as np
from scipy.stats import norm
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel

from .base import BaseOptimizer


def expected_improvement(mu, sigma, y_best: float, xi: float = 0.01) -> np.ndarray:
    """EI for minimization. Defined as 0 where sigma == 0."""
    mu = np.asarray(mu, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    imp = y_best - mu - xi
    ei = np.zeros_like(mu)
    pos = sigma > 1e-12
    z = imp[pos] / sigma[pos]
    ei[pos] = imp[pos] * norm.cdf(z) + sigma[pos] * norm.pdf(z)
    return np.maximum(ei, 0.0)


def make_gp(dim: int, seed: int, restarts: int = 5) -> GaussianProcessRegressor:
    kernel = (ConstantKernel(1.0, (1e-3, 1e3))
              * Matern(length_scale=np.ones(dim), length_scale_bounds=(1e-2, 1e3), nu=2.5)
              + WhiteKernel(noise_level=1e-2, noise_level_bounds=(1e-6, 1e0)))
    return GaussianProcessRegressor(kernel=kernel, normalize_y=True,
                                    n_restarts_optimizer=restarts, random_state=seed)


class BayesOpt(BaseOptimizer):
    name = "bo"

    def __init__(self, space, seed, init=None, xi: float = 0.01, pool_size: int = 2000,
                 top_k_neighbours: int = 5, gp_restarts: int = 5, failure_penalty: float = 1.0):
        super().__init__(space, seed, init, failure_penalty)
        self.xi = xi
        self.pool_size = pool_size
        self.top_k = top_k_neighbours
        self.gp_restarts = gp_restarts
        self.gp: GaussianProcessRegressor | None = None

    def ask(self) -> np.ndarray:
        x = self._next_init()
        if x is not None:
            self.last_acq = None
            return x
        X, y = self.model_data()
        if len(y) < 2:
            self.last_acq = None
            return self._random_unseen()

        gp = make_gp(self.space.dim, self.seed + len(y), self.gp_restarts)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            gp.fit(X, y)
        self.gp = gp

        pool = self._candidate_pool()
        if not pool:
            self.last_acq = None
            return self._random_unseen()
        P = np.array(pool, dtype=float)
        mu, sd = gp.predict(P, return_std=True)
        ei = expected_improvement(mu, sd, float(y.min()), self.xi)
        top = np.flatnonzero(ei >= ei.max() - 1e-15)
        idx = int(self.rng.choice(top))  # seeded tie-break
        self.last_acq = float(ei[idx])
        return pool[idx]

    def _candidate_pool(self) -> list[np.ndarray]:
        cands = self.space.sample(self.rng, self.pool_size)
        best_ok = sorted((o for o in self.history if o.ok), key=lambda o: o.y)[: self.top_k]
        for o in best_ok:
            cands.extend(self.space.neighbours(o.x))
        out, keys = [], set(self.seen)
        for c in cands:
            k = self.space.key(c)
            if k not in keys:
                keys.add(k)
                out.append(c)
        return out

    def length_scales(self) -> np.ndarray | None:
        """Fitted ARD length scales (short = the objective is sensitive to that bit)."""
        if self.gp is None:
            return None
        return np.atleast_1d(self.gp.kernel_.k1.k2.length_scale)
