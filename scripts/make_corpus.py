"""Build the real-world text corpus used by the real-data benchmarks.

The corpus is real, human-written text taken from the local CPython
installation: the release changelog (English prose), the pydoc documentation
topics (English prose) and a fixed set of standard-library modules (real source
code). Nothing is downloaded. The files are concatenated in a fixed order with
line endings normalized to LF, and the result is committed as
benchmarks/data/corpus.txt, with its provenance and SHA-256 in
benchmarks/data/CORPUS.md, so every machine measures identical input.

usage: python scripts/make_corpus.py      (only needed to rebuild the corpus)
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmarks" / "data"
PY = Path(sys.base_prefix)

FILES = [
    ("NEWS.txt", "CPython release changelog (English prose)"),
    ("Lib/pydoc_data/topics.py", "CPython documentation topics (English prose)"),
    ("LICENSE.txt", "CPython license text (English legal prose)"),
    ("Lib/argparse.py", "standard library source"),
    ("Lib/typing.py", "standard library source"),
    ("Lib/inspect.py", "standard library source"),
    ("Lib/tarfile.py", "standard library source"),
    ("Lib/subprocess.py", "standard library source"),
    ("Lib/difflib.py", "standard library source"),
    ("Lib/http/client.py", "standard library source"),
    ("Lib/statistics.py", "standard library source"),
    ("Lib/_pydecimal.py", "standard library source"),
]


def main() -> int:
    parts, rows = [], []
    for rel, what in FILES:
        p = PY / rel
        if not p.exists():
            print(f"missing {p}; the corpus must be built from a CPython 3.12 installation")
            return 1
        text = p.read_bytes().replace(b"\r\n", b"\n")
        parts.append(text)
        rows.append((rel, what, len(text), hashlib.sha256(text).hexdigest()[:16]))
    corpus = b"\n\n".join(parts)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "corpus.txt").write_bytes(corpus)
    digest = hashlib.sha256(corpus).hexdigest()
    lines = [
        "# Real-world corpus",
        "",
        f"`corpus.txt`: {len(corpus):,} bytes, SHA-256 `{digest}`.",
        "",
        f"Built by `scripts/make_corpus.py` from the CPython {sys.version.split()[0]} installation on the",
        "measurement machine. It is real human-written text, about 70% English prose and 30% source code,",
        "distributed under the Python Software Foundation License (see LICENSE.txt, included in the corpus).",
        "",
        "| File | Content | Bytes | SHA-256 (first 16) |",
        "| --- | --- | --- | --- |",
    ] + [f"| `{r}` | {w} | {n:,} | `{h}` |" for r, w, n, h in rows]
    (OUT / "CORPUS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote benchmarks/data/corpus.txt ({len(corpus):,} bytes, sha256 {digest[:16]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
