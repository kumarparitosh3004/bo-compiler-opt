"""Random search: the control method. Same initial design and budget as BO."""
from __future__ import annotations

import numpy as np

from .base import BaseOptimizer


class RandomSearch(BaseOptimizer):
    name = "random"

    def ask(self) -> np.ndarray:
        self.last_acq = None
        x = self._next_init()
        return x if x is not None else self._random_unseen()
