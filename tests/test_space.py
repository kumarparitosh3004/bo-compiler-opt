import numpy as np
import pytest

from bopass.config import CONFIG_DIR
from bopass.space import SearchSpace


def test_dim_and_flag_count(small_space):
    assert small_space.dim == 5
    assert len(small_space.to_flags(np.ones(5, dtype=np.int8))) >= 1


def test_key_round_trip(small_space):
    rng = np.random.default_rng(0)
    for x in small_space.sample(rng, 50):
        assert np.array_equal(small_space.from_key(small_space.key(x)), x)


def test_canonicalize_applies_requires_and_is_idempotent(small_space):
    x = np.array([1, 0, 1, 1, 0], dtype=np.int8)        # partial-pre on, tree-pre off
    c = small_space.canonicalize(x)
    assert c[2] == 0
    assert np.array_equal(small_space.canonicalize(c), c)
    assert not small_space.is_valid(x)
    assert small_space.is_valid(c)


def test_sampled_configs_are_valid(small_space):
    rng = np.random.default_rng(1)
    assert all(small_space.is_valid(x) for x in small_space.sample(rng, 200))


def test_is_valid_rejects_bad_shapes_and_values(small_space):
    assert not small_space.is_valid(np.zeros(4))
    assert not small_space.is_valid(np.array([0, 2, 0, 0, 0]))


def test_reference_vectors_map_to_plain_levels(small_space):
    assert small_space.to_flags(small_space.reference("O3")) == ["-O3"]
    assert small_space.to_flags(small_space.reference("O2")) == ["-O2"]


def test_to_flags_emits_only_differences_from_level_default(small_space):
    x = small_space.reference("O3").copy()
    x[3] = 1                                              # unroll-all-loops on (default off)
    x[1] = 0                                              # tree-pre off -> partial-pre forced off
    x = small_space.canonicalize(x)
    flags = small_space.to_flags(x)
    assert flags[0] == "-O3"
    assert "-funroll-all-loops" in flags
    assert "-fno-tree-pre" in flags and "-fno-tree-partial-pre" in flags
    assert "-ftree-loop-vectorize" not in flags          # at default -> not spelled out


def test_neighbours_are_distinct_valid_and_one_flip_away(small_space):
    x = small_space.reference("O3")
    ns = small_space.neighbours(x)
    keys = {small_space.key(n) for n in ns}
    assert len(keys) == len(ns)
    assert small_space.key(x) not in keys
    for n in ns:
        assert small_space.is_valid(n)
        assert 1 <= int(np.sum(n != x)) <= 2               # 2 when a requirement cascades


def test_describe_diff(small_space):
    x = small_space.reference("O3").copy()
    x[3] = 1
    assert small_space.describe_diff(x) == "+unroll-all-loops"
    assert "same as" in small_space.describe_diff(small_space.reference("O3"))


def test_unknown_requirement_rejected():
    from bopass.space import Flag
    with pytest.raises(ValueError):
        SearchSpace([Flag("a", {}, requires=("missing",))])


def test_generated_flags_file_loads():
    p = CONFIG_DIR / "flags_gcc.yaml"
    if not p.exists():
        pytest.skip("run scripts/verify_flags.py first")
    s = SearchSpace.from_yaml(p)
    assert s.dim >= 2
    assert s.to_flags(s.reference("O3")) == ["-O3"]
