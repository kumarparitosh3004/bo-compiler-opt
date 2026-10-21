"""Phase 2 (Member 1): verify the candidate flags against the installed compiler.

1. Read each flag's real -O2/-O3 default from `gcc -Q --help=optimizers`.
2. Toggle check: -f<name> must show [enabled] and -fno-<name> [disabled] at both levels.
3. Encoding check: the x_O3 / x_O2 vectors must build byte-identical executables
   to plain -O3 / -O2 for every benchmark.
4. Sensitivity screen: flip each flag alone from x_O3 and x_O2 and count how many
   benchmark binaries change. Flags that never change a binary are dead
   dimensions and are deactivated.

Writes config/flags_gcc.yaml, docs/flag_catalog.md and results/verification/verify_report.json.
usage: python scripts/verify_flags.py [--bench matmul ...] [--workers 8]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from bopass import OK  # noqa: E402
from bopass.benchmarks import load_benchmarks  # noqa: E402
from bopass.compiler_driver import compile, compiler_version, effective_flags  # noqa: E402
from bopass.config import BUILD_DIR, CONFIG_DIR, RESULTS_DIR, compiler_path, fixed_flags, load_experiment, load_yaml  # noqa: E402
from bopass.space import Flag, SearchSpace  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", nargs="*", help="benchmarks to use (default: all)")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    cfg = load_experiment()
    cc, fixed = compiler_path(cfg), fixed_flags(cfg)
    cand = load_yaml(CONFIG_DIR / "flag_candidates.yaml")
    benches = load_benchmarks()
    names = a.bench or list(benches)
    print(f"compiler: {cc} -> {compiler_version(cc)}")

    # 1-2. defaults and toggle check -----------------------------------------------------
    q = {lvl: effective_flags(cc, [f"-{lvl}"]) for lvl in ("O2", "O3")}
    flags, report = [], {"compiler": compiler_version(cc), "flags": {}}
    for c in cand["candidates"]:
        n = c["name"]
        known = n in q["O2"]
        ok = known
        side = set()
        default = {lvl: int(q[lvl].get(n, False)) for lvl in ("O2", "O3")}
        if known:
            for lvl in ("O2", "O3"):
                st_on = effective_flags(cc, [f"-{lvl}", f"-f{n}"])
                st_off = effective_flags(cc, [f"-{lvl}", f"-fno-{n}"])
                ok = ok and st_on.get(n) is True and st_off.get(n) is False
                # side effects: spelling the flag out at its default value changes other flags
                same = st_on if default[lvl] else st_off
                side |= {k for k in q[lvl] if k != n and q[lvl][k] != same.get(k)}
        report["flags"][n] = {"known": known, "toggle_verified": ok, "default": default,
                              "side_effects_when_explicit": sorted(side)}
        print(f"  {n:28s} O2={default['O2']} O3={default['O3']} toggle={'ok' if ok else 'FAILED'}"
              + (f"  side effects if spelled out: {', '.join(sorted(side))}" if side else ""))
        if ok:
            flags.append(Flag(n, default, tuple(c.get("requires", [])), c.get("what", "")))
    names_ok = {f.name for f in flags}
    flags = [Flag(f.name, f.default, tuple(r for r in f.requires if r in names_ok), f.what) for f in flags]
    space = SearchSpace(flags, tuple(cand.get("base_levels", ("-O2", "-O3"))))

    # 3. encoding check -------------------------------------------------------------------
    out_root = BUILD_DIR / "verify"

    ex = ThreadPoolExecutor(a.workers)
    futures = {}  # one build per distinct (benchmark, flags): identical jobs would share an output path

    def build(bname, fl):
        k = (bname, tuple(fl))
        if k not in futures:
            futures[k] = ex.submit(compile, benches[bname], list(fl), out_root, cc=cc, fixed=fixed)
        return futures[k]

    jobs = {}
    for b in names:
        for lvl in ("O2", "O3"):
            jobs[(b, lvl, "plain")] = build(b, [f"-{lvl}"])
            jobs[(b, lvl, "vector")] = build(b, space.to_flags(space.reference(lvl)))
    res = {k: v.result() for k, v in jobs.items()}
    equiv_ok = True
    report["equivalence"] = {}
    for b in names:
        for lvl in ("O2", "O3"):
            p, v = res[(b, lvl, "plain")], res[(b, lvl, "vector")]
            same = p.status == OK and v.status == OK and p.sha256 == v.sha256
            equiv_ok &= same
            report["equivalence"][f"{b}/{lvl}"] = same
            print(f"  equivalence {b:10s} x_{lvl} == -{lvl}: {'yes' if same else 'NO'}")

    # 4. sensitivity screen ---------------------------------------------------------------
    ref_sha = {(b, lvl): res[(b, lvl, "plain")].sha256 for b in names for lvl in ("O2", "O3")}
    changed = {f.name: set() for f in flags}
    jobs = {}
    for i, f in enumerate(flags):
        for lvl in ("O2", "O3"):
            x = space.reference(lvl).copy()
            x[1 + i] ^= 1
            x = space.canonicalize(x)
            if space.key(x) == space.key(space.reference(lvl)):
                continue
            for b in names:
                jobs[(f.name, lvl, b)] = build(b, space.to_flags(x))
    for (fname, lvl, b), fut in jobs.items():
        r = fut.result()
        if r.status == OK and r.sha256 != ref_sha[(b, lvl)]:
            changed[fname].add(b)
    ex.shutdown()
    max_active = int(cand.get("max_active_flags", 16))
    ranked = sorted(flags, key=lambda f: -len(changed[f.name]))
    active = {f.name for f in ranked if changed[f.name]}
    if len(active) > max_active:
        active = {f.name for f in ranked[:max_active] if changed[f.name]}

    # write outputs -----------------------------------------------------------------------
    out = {
        "generated_by": "scripts/verify_flags.py",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "compiler": cc,
        "compiler_version": compiler_version(cc),
        "base_levels": list(space.base_levels),
        "flags": [],
        "forbidden": cand.get("forbidden", []),
    }
    for c in cand["candidates"]:
        n = c["name"]
        info = report["flags"][n]
        out["flags"].append({
            "name": n, "what": c.get("what", ""), "default": info["default"],
            "requires": list(c.get("requires", [])), "toggle_verified": info["toggle_verified"],
            "side_effects_when_explicit": info["side_effects_when_explicit"],
            "binaries_changed": sorted(changed.get(n, [])), "active": n in active,
        })
        info["binaries_changed"] = sorted(changed.get(n, []))
        info["active"] = n in active
    (CONFIG_DIR / "flags_gcc.yaml").write_text(
        "# GENERATED by scripts/verify_flags.py - edit config/flag_candidates.yaml instead.\n"
        + yaml.safe_dump(out, sort_keys=False, width=120), encoding="utf-8")

    lines = [f"# Flag catalog\n\nGenerated by `scripts/verify_flags.py` on {out['generated_at']} for "
             f"`{out['compiler_version']}`. Defaults come from `gcc -Q --help=optimizers`, not from the manual.\n",
             f"Active flags (in the search space): **{len(active)}**, plus 1 base-level bit "
             f"-> d = {len(active) + 1}, {2 ** (len(active) + 1):,} configurations before constraints.\n",
             "A flag is passed to the compiler only when its bit differs from the base level's default. "
             "The *side effects* column shows why: spelling those flags out, even at their default value, "
             "changes other optimization flags.\n",
             "| Flag | What it does | -O2 | -O3 | Toggle verified | Side effects if spelled out | "
             "Binaries changed (of %d) | Active |" % len(names),
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for f in out["flags"]:
        side = ", ".join(f"`{s}`" for s in f["side_effects_when_explicit"]) or "-"
        lines.append(f"| `-f{f['name']}` | {f['what']} | {f['default']['O2']} | {f['default']['O3']} | "
                     f"{'yes' if f['toggle_verified'] else 'no'} | {side} | {len(f['binaries_changed'])} "
                     f"({', '.join(f['binaries_changed']) or '-'}) | {'yes' if f['active'] else 'no'} |")
    lines.append("\nEncoding check (x_O2 / x_O3 build byte-identical to plain -O2 / -O3): "
                 + ("**passed** for all benchmarks." if equiv_ok else "**FAILED** - see verify_report.json."))
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "flag_catalog.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    rdir = RESULTS_DIR / "verification"
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "verify_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\nactive flags ({len(active)}): {', '.join(f.name for f in ranked if f.name in active)}")
    print(f"encoding check: {'passed' if equiv_ok else 'FAILED'}")
    return 0 if equiv_ok else 1


if __name__ == "__main__":
    sys.exit(main())
