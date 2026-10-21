"""Append-only CSV storage of evaluation records, with resume support."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .evaluator import FIELDNAMES, EvalRecord


class ResultStore:
    def __init__(self, directory: str | Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.dir / "evals.csv"

    def append(self, rec: EvalRecord) -> None:
        new = not self.csv_path.exists() or self.csv_path.stat().st_size == 0
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if new:
                w.writeheader()
            w.writerow(rec.to_row())
            f.flush()

    def load(self) -> list[EvalRecord]:
        """All complete rows. A partially written last line (crash mid-write) is skipped."""
        if not self.csv_path.exists():
            return []
        out = []
        with open(self.csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if None in row or any(row.get(k) is None for k in FIELDNAMES):
                    continue  # truncated row
                if not row.get("config_key") or not row.get("status"):
                    continue
                try:
                    out.append(EvalRecord.from_row(row))
                except (ValueError, TypeError):
                    continue
        return out

    def write_json(self, name: str, data: dict) -> Path:
        p = self.dir / name
        p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return p

    def read_json(self, name: str) -> dict | None:
        p = self.dir / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
