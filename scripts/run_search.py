"""Phase 3 (Member 4): run one budgeted search.

usage: python scripts/run_search.py --bench matmul --method bo --seed 0 [--budget 50] [--tag demo]
Re-running the same command resumes an interrupted run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bopass.config import load_experiment  # noqa: E402
from bopass.orchestrator import run_search  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", required=True)
    ap.add_argument("--method", choices=["bo", "random"], default="bo")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--budget", type=int)
    ap.add_argument("--tag", default="", help="suffix for the experiment id, e.g. 'demo'")
    a = ap.parse_args()
    summary = run_search(a.bench, a.method, a.seed, load_experiment(), budget=a.budget, tag=a.tag)
    print(json.dumps({k: v for k, v in summary.items() if k != "length_scales"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
