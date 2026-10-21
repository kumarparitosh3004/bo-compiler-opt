"""Evidence that the BO engine works before the compiler is attached:
on a synthetic 16-bit objective with noise, BO's mean best-at-budget over
10 seeds beats random search with the same initial design and budget."""
import numpy as np

from bopass.optimizer import BayesOpt, RandomSearch
from bopass.space import Flag, SearchSpace

from .conftest import synthetic_objective


def _best_after(cls, space, f, seed, budget, noise, **kw):
    init_rng = np.random.default_rng([seed, 0])
    init = space.sample(init_rng, 8)
    opt = cls(space, seed, init, **kw)
    rng = np.random.default_rng([seed, 99])
    for _ in range(budget):
        x = opt.ask()
        opt.tell(x, f(x) + rng.normal(0, noise), True)
    return min(f(o.x) for o in opt.history)  # true (noise-free) value of the best found


def test_bo_beats_random_on_synthetic_objective():
    space = SearchSpace([Flag(f"f{i}", {"O2": 0, "O3": 0}) for i in range(15)])  # d = 16
    f = synthetic_objective(space.dim, seed=2024)
    bo, rs = [], []
    for seed in range(10):
        bo.append(_best_after(BayesOpt, space, f, seed, 40, 0.1, pool_size=1000, gp_restarts=1))
        rs.append(_best_after(RandomSearch, space, f, seed, 40, 0.1))
    assert np.mean(bo) < np.mean(rs), (np.mean(bo), np.mean(rs))
