"""Search-space representation.

A configuration is a 0/1 vector x of length d = 1 + number of flags:
  x[0]      base level: 0 -> -O2, 1 -> -O3
  x[1 + i]  flag i:     1 -> on, 0 -> off; emitted as -f<name> / -fno-<name> only
            when it differs from the base level's default (see to_flags)

Dependency rules (`requires`) are applied by canonicalize(): a flag whose
prerequisite is off is forced to 0, because both versions build the same
binary. Pass ordering is not part of the search (GCC's pass order is fixed).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .config import load_yaml

LEVEL_KEYS = ("O2", "O3")


@dataclass(frozen=True)
class Flag:
    name: str
    default: dict = field(default_factory=dict)   # {"O2": 0/1, "O3": 0/1}
    requires: tuple[str, ...] = ()
    what: str = ""


class SearchSpace:
    def __init__(self, flags: list[Flag], base_levels=("-O2", "-O3")):
        if len(base_levels) != 2:
            raise ValueError("exactly two base levels are supported (one bit)")
        self.flags = list(flags)
        self.base_levels = tuple(base_levels)
        self.dim = 1 + len(self.flags)
        self._index = {f.name: 1 + i for i, f in enumerate(self.flags)}
        for f in self.flags:
            for r in f.requires:
                if r not in self._index:
                    raise ValueError(f"{f.name} requires unknown flag {r}")

    # ---- construction -------------------------------------------------------------
    @classmethod
    def from_yaml(cls, path: str | Path, active_only: bool = True) -> "SearchSpace":
        data = load_yaml(path)
        flags = []
        for d in data["flags"]:
            if active_only and not d.get("active", True):
                continue
            flags.append(Flag(name=d["name"], default=dict(d.get("default", {})),
                              requires=tuple(d.get("requires", [])), what=d.get("what", "")))
        active = {f.name for f in flags}
        # a requirement on a dropped flag cannot be honoured; drop the requirement
        flags = [Flag(f.name, f.default, tuple(r for r in f.requires if r in active), f.what) for f in flags]
        return cls(flags, tuple(data.get("base_levels", ("-O2", "-O3"))))

    # ---- core operations ----------------------------------------------------------
    def canonicalize(self, x) -> np.ndarray:
        x = np.asarray(x, dtype=np.int8).copy()
        changed = True
        while changed:  # repeat so chains of requirements settle
            changed = False
            for f in self.flags:
                i = self._index[f.name]
                if x[i] and any(x[self._index[r]] == 0 for r in f.requires):
                    x[i] = 0
                    changed = True
        return x

    def is_valid(self, x) -> bool:
        x = np.asarray(x)
        if x.shape != (self.dim,):
            return False
        if not np.all((x == 0) | (x == 1)):
            return False
        return bool(np.array_equal(x, self.canonicalize(x)))

    def sample(self, rng: np.random.Generator, n: int) -> list[np.ndarray]:
        raw = rng.integers(0, 2, size=(n, self.dim), dtype=np.int8)
        return [self.canonicalize(r) for r in raw]

    def to_flags(self, x) -> list[str]:
        """Command-line flags for x. A flag is emitted only when its bit differs from
        the base level's default: in GCC, spelling out some flags explicitly has side
        effects even at their default value (e.g. an explicit -funroll-loops also
        enables -fweb and -frename-registers), so x_O3 must map to exactly "-O3"."""
        x = np.asarray(x)
        level = self.base_levels[int(x[0])]
        lkey = level.lstrip("-")
        out = [level]
        for f in self.flags:
            bit = int(x[self._index[f.name]])
            if f.default and lkey in f.default and bit == int(f.default[lkey]):
                continue
            out.append(("-f" if bit else "-fno-") + f.name)
        return out

    def key(self, x) -> str:
        return "".join(str(int(v)) for v in np.asarray(x))

    def from_key(self, key: str) -> np.ndarray:
        if len(key) != self.dim:
            raise ValueError(f"key length {len(key)} != dim {self.dim}")
        return np.array([int(c) for c in key], dtype=np.int8)

    def neighbours(self, x) -> list[np.ndarray]:
        """All canonical configurations that differ from x by flipping one bit."""
        x = np.asarray(x, dtype=np.int8)
        seen = {self.key(x)}
        out = []
        for i in range(self.dim):
            y = x.copy()
            y[i] ^= 1
            y = self.canonicalize(y)
            k = self.key(y)
            if k not in seen:
                seen.add(k)
                out.append(y)
        return out

    def reference(self, level: str) -> np.ndarray:
        """Vector that reproduces plain -O2 or -O3 (flag bits = that level's defaults)."""
        level = level.lstrip("-")
        if level not in LEVEL_KEYS:
            raise ValueError(level)
        x = np.zeros(self.dim, dtype=np.int8)
        x[0] = LEVEL_KEYS.index(level)
        for f in self.flags:
            x[self._index[f.name]] = int(f.default.get(level, 0))
        return self.canonicalize(x)

    def describe_diff(self, x, level: str = "O3") -> str:
        """Human-readable difference from a reference level, e.g. '+unroll-loops -tree-pre'."""
        ref = self.reference(level)
        x = np.asarray(x)
        parts = []
        if x[0] != ref[0]:
            parts.append(f"base {self.base_levels[int(x[0])]}")
        for f in self.flags:
            i = self._index[f.name]
            if x[i] != ref[i]:
                parts.append(("+" if x[i] else "-") + f.name)
        return " ".join(parts) if parts else f"(same as {level})"

    @property
    def flag_names(self) -> list[str]:
        return [f.name for f in self.flags]
