import math

import pytest

from bopass.objective import objective, pct_faster, penalty_value


def test_objective_is_log_ratio():
    assert objective(100, 100) == 0
    assert objective(95, 100) == pytest.approx(math.log(0.95))
    assert objective(110, 100) > 0


def test_pct_faster():
    assert pct_faster(math.log(0.95)) == pytest.approx(5.0)
    assert pct_faster(0.0) == 0.0


def test_penalty_value():
    assert penalty_value([-0.1, 0.2], 1.0) == pytest.approx(1.2)
    assert penalty_value([], 1.0) == 1.0


def test_objective_rejects_nonpositive():
    with pytest.raises(ValueError):
        objective(0, 1)


def test_active_seconds_ignores_sleep_gaps():
    from bopass.orchestrator import MAX_EVAL_S, active_seconds
    assert active_seconds([5, 10, 15]) == 15
    # a 10-hour gap (machine asleep) counts as at most one evaluation's worth
    assert active_seconds([5, 10, 10 + 36000, 10 + 36005]) == 10 + MAX_EVAL_S + 5
    # a resumed run restarts its clock; NaN / None are skipped
    assert active_seconds([5, 10, 3, 8, None, float("nan")]) == 18
