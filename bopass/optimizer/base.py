"""Ask/tell optimizer protocol shared by Bayesian Optimization and random search.

The orchestrator only ever calls ask(), tell() and best(), so the optimizer can
be developed and tested against a synthetic objective without a compiler.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..objective import penalty_value
from ..space import SearchSpace


@dataclass
class Observation:
    x: np.ndarray
    y: float | None      # objective value; None for failed evaluations
    ok: bool


class SpaceExhausted(RuntimeError):
    pass


class BaseOptimizer:
    name = "base"

    def __init__(self, space: SearchSpace, seed: int, init=None, failure_penalty: float = 1.0):
        self.space = space
        self.seed = int(seed)
        # independent stream from the one used to draw the initial design
        self.rng = np.random.default_rng([self.seed, 1])
        self.init_queue = [space.canonicalize(x) for x in (init or [])]
        self.failure_penalty = failure_penalty
        self.history: list[Observation] = []
        self.seen: set[str] = set()
        self.last_acq: float | None = None

    # ---- protocol -----------------------------------------------------------------
    def ask(self) -> np.ndarray:
        raise NotImplementedError

    def tell(self, x, y: float | None, ok: bool) -> None:
        x = self.space.canonicalize(x)
        self.history.append(Observation(x, None if not ok else float(y), bool(ok)))
        self.seen.add(self.space.key(x))

    def best(self) -> tuple[np.ndarray | None, float | None]:
        ok = [o for o in self.history if o.ok]
        if not ok:
            return None, None
        b = min(ok, key=lambda o: o.y)
        return b.x, b.y

    @property
    def n_told(self) -> int:
        return len(self.history)

    # ---- helpers ------------------------------------------------------------------
    def model_data(self) -> tuple[np.ndarray, np.ndarray]:
        """Training data for a surrogate; failures get worst OK y + penalty."""
        ok_ys = [o.y for o in self.history if o.ok]
        pen = penalty_value(ok_ys, self.failure_penalty)
        X = np.array([o.x for o in self.history], dtype=float)
        y = np.array([o.y if o.ok else pen for o in self.history], dtype=float)
        return X, y

    def _next_init(self) -> np.ndarray | None:
        while self.init_queue:
            x = self.init_queue.pop(0)
            if self.space.key(x) not in self.seen:
                return x
        return None

    def _random_unseen(self, max_tries: int = 100_000) -> np.ndarray:
        for _ in range(max_tries):
            x = self.space.sample(self.rng, 1)[0]
            if self.space.key(x) not in self.seen:
                return x
        raise SpaceExhausted("could not find an unseen configuration")
