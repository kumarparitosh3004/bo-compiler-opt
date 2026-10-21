#!/bin/bash
# One-time setup on macOS: GCC, Python environment, packages, self-check.
# usage:  bash setup_mac.sh
set -e
cd "$(dirname "$0")"
echo
echo "== PassTune setup (macOS) =="

# Files from a downloaded zip carry the quarantine flag; clear it for this folder.
xattr -dr com.apple.quarantine . 2>/dev/null || true

# 1. Xcode command line tools (linker and system headers that GCC needs)
if ! xcode-select -p >/dev/null 2>&1; then
  echo "Xcode command line tools are missing. A dialog will open: click Install,"
  echo "wait for it to finish, then run  bash setup_mac.sh  again."
  xcode-select --install || true
  exit 1
fi
echo "[1/5] Xcode command line tools: OK"

# 2. Homebrew
BREW=""
for b in /opt/homebrew/bin/brew /usr/local/bin/brew "$(command -v brew 2>/dev/null)"; do
  if [ -n "$b" ] && [ -x "$b" ]; then BREW="$b"; break; fi
done
find_gcc() {
  for d in /opt/homebrew/bin /usr/local/bin; do
    ls "$d"/gcc-[0-9]* 2>/dev/null | grep -E 'gcc-[0-9]+$' | sort -t- -k2 -n | tail -1
  done | tail -1
}
GCC="$(find_gcc)"
if [ -z "$GCC" ]; then
  if [ -z "$BREW" ]; then
    echo
    echo "Homebrew is needed to install GCC. Install it by pasting this in Terminal:"
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    echo "then run  bash setup_mac.sh  again."
    exit 1
  fi
  echo "[2/5] Installing GCC with Homebrew (a few minutes)..."
  "$BREW" install gcc
  GCC="$(find_gcc)"
fi
if [ -z "$GCC" ]; then echo "GCC could not be installed."; exit 1; fi
echo "[2/5] GCC: $GCC ($("$GCC" -dumpfullversion))"

# 3. Python 3.10 or newer
PY=""
for p in python3.13 python3.12 python3.11 python3.10 python3.14 python3; do
  for c in "/opt/homebrew/bin/$p" "/usr/local/bin/$p" "$(command -v $p 2>/dev/null)"; do
    if [ -n "$c" ] && [ -x "$c" ] && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      PY="$c"; break 2
    fi
  done
done
if [ -z "$PY" ]; then
  if [ -z "$BREW" ]; then echo "Python 3.10+ is needed: install it from https://www.python.org/downloads/"; exit 1; fi
  echo "[3/5] Installing Python 3.12 with Homebrew..."
  "$BREW" install python@3.12
  PY="$("$BREW" --prefix)/bin/python3.12"
fi
echo "[3/5] Python: $PY ($("$PY" --version))"

# 4. Virtual environment and packages
if [ ! -x .venv/bin/python ]; then "$PY" -m venv .venv; fi
.venv/bin/python -m pip install --upgrade pip >/dev/null
if ! .venv/bin/python -m pip install -r requirements.txt; then
  echo "Pinned versions are not available for this Python; installing the latest compatible ones."
  .venv/bin/python -m pip install flask matplotlib numpy pandas pytest python-docx pyyaml scikit-learn scipy
fi
echo "[4/5] Packages: OK"

# 5. Point the project at GCC and check every benchmark
printf "# Per-machine settings (written by setup_mac.sh).\ncompiler: %s\n" "$GCC" > config/local.yaml
echo "[5/5] Checking the compiler and benchmarks..."
.venv/bin/python scripts/check_setup.py --fix-references

echo
echo "Setup finished. Start the app with:  bash run_mac.sh"
