import numpy as np
import pytest
from scipy.stats import norm

from bopass.optimizer import BayesOpt, RandomSearch, expected_improvement

from .conftest import synthetic_objective


def test_ei_matches_hand_computation():
    mu, sigma, best, xi = 0.2, 0.5, 0.4, 0.01
    imp = best - mu - xi
    z = imp / sigma
    want = imp * norm.cdf(z) + sigma * norm.pdf(z)
    assert expected_improvement([mu], [sigma], best, xi)[0] == pytest.approx(want)


def test_ei_zero_when_sigma_zero():
    assert expected_improvement([0.0, 1.0], [0.0, 0.0], 0.5)[0] == 0.0
    assert expected_improvement([0.0], [0.0], 0.5)[0] == 0.0


def test_ei_never_negative():
    ei = expected_improvement(np.linspace(-2, 2, 50), np.full(50, 0.3), 0.0)
    assert np.all(ei >= 0)


def _run(opt, f, budget):
    for _ in range(budget):
        x = opt.ask()
        opt.tell(x, f(x), True)
    return opt


def test_init_queue_used_first(small_space):
    init = [small_space.reference("O3"), small_space.reference("O2")]
    opt = BayesOpt(small_space, 0, init, pool_size=50, gp_restarts=0)
    assert small_space.key(opt.ask()) == small_space.key(init[0])
    opt.tell(init[0], 0.0, True)
    assert small_space.key(opt.ask()) == small_space.key(init[1])


@pytest.mark.parametrize("cls", [BayesOpt, RandomSearch])
def test_ask_never_repeats_a_configuration(small_space, cls):
    f = synthetic_objective(small_space.dim)
    kw = {"pool_size": 50, "gp_restarts": 0} if cls is BayesOpt else {}
    opt = _run(cls(small_space, 0, [small_space.reference("O3")], **kw), f, 14)
    keys = [small_space.key(o.x) for o in opt.history]
    assert len(keys) == len(set(keys))


def test_same_seed_same_sequence(small_space):
    f = synthetic_objective(small_space.dim)
    seqs = []
    for _ in range(2):
        opt = _run(BayesOpt(small_space, 7, small_space.sample(np.random.default_rng(7), 3),
                            pool_size=100, gp_restarts=1), f, 10)
        seqs.append([small_space.key(o.x) for o in opt.history])
    assert seqs[0] == seqs[1]


def test_failures_get_penalty_in_model_data(small_space):
    opt = RandomSearch(small_space, 0, failure_penalty=1.0)
    xs = small_space.sample(np.random.default_rng(0), 3)
    opt.tell(xs[0], -0.2, True)
    opt.tell(xs[1], 0.1, True)
    opt.tell(xs[2], None, False)
    _, y = opt.model_data()
    assert y[-1] == pytest.approx(1.1)
    assert opt.best()[1] == pytest.approx(-0.2)


def test_best_is_none_without_ok_observations(small_space):
    opt = RandomSearch(small_space, 0)
    opt.tell(small_space.reference("O3"), None, False)
    assert opt.best() == (None, None)
