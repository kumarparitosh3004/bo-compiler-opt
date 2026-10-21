from .base import BaseOptimizer, Observation, SpaceExhausted
from .bo import BayesOpt, expected_improvement
from .random_search import RandomSearch


def make_optimizer(method: str, space, seed: int, init, cfg: dict) -> BaseOptimizer:
    penalty = float(cfg.get("failure_penalty", 1.0))
    if method == "bo":
        bo = cfg.get("bo", {})
        return BayesOpt(space, seed, init, xi=bo.get("xi", 0.01), pool_size=bo.get("pool_size", 2000),
                        top_k_neighbours=bo.get("top_k_neighbours", 5),
                        gp_restarts=bo.get("gp_restarts", 5), failure_penalty=penalty)
    if method == "random":
        return RandomSearch(space, seed, init, failure_penalty=penalty)
    raise ValueError(f"unknown method {method!r}")


__all__ = ["BaseOptimizer", "Observation", "SpaceExhausted", "BayesOpt", "RandomSearch",
           "expected_improvement", "make_optimizer"]
