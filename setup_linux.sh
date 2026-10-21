#!/bin/bash
# One-time setup on Linux: GCC, binutils, Python environment, packages, self-check.
# usage:  bash setup_linux.sh
set -e
cd "$(dirname "$0")"
echo
echo "== PassTune setup (Linux) =="

# 1. GCC. Unlike macOS, `gcc` on Linux is real GCC, so no Homebrew detour.
if ! command -v gcc >/dev/null 2>&1; then
  echo "GCC is missing. Install it with your package manager, then run this again:"
  echo "  Debian/Ubuntu : sudo apt install build-essential binutils"
  echo "  Fedora/RHEL   : sudo dnf install gcc binutils"
  echo "  Arch          : sudo pacman -S base-devel binutils"
  exit 1
fi
GCC="$(command -v gcc)"
echo "[1/4] GCC: $GCC ($("$GCC" -dumpfullversion))"

# `size` reports the code size of each build. Without it the size columns are
# empty, which is not fatal, so warn rather than stop.
if ! command -v size >/dev/null 2>&1; then
  echo "       warning: binutils 'size' not found; binary size will not be recorded."
  echo "       Debian/Ubuntu: sudo apt install binutils"
fi

# 2. Python 3.10 or newer
PY=""
for p in python3.13 python3.12 python3.11 python3.10 python3; do
  c="$(command -v $p 2>/dev/null || true)"
  if [ -n "$c" ] && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.10 or newer is needed. Install it, then run this again:"
  echo "  Debian/Ubuntu : sudo apt install python3 python3-venv python3-pip"
  echo "  Fedora/RHEL   : sudo dnf install python3 python3-pip"
  exit 1
fi
echo "[2/4] Python: $PY ($("$PY" --version))"

# 3. Virtual environment and packages
if [ ! -x .venv/bin/python ]; then
  if ! "$PY" -m venv .venv 2>/dev/null; then
    echo "Creating the environment failed. On Debian/Ubuntu install the venv package:"
    echo "  sudo apt install python3-venv"
    exit 1
  fi
fi
.venv/bin/python -m pip install --upgrade pip >/dev/null
if ! .venv/bin/python -m pip install -r requirements.txt; then
  echo "Pinned versions are not available for this Python; installing the latest compatible ones."
  .venv/bin/python -m pip install flask matplotlib numpy pandas pytest python-docx pyyaml scikit-learn scipy
fi
echo "[3/4] Packages: OK"

# 4. Point the project at this GCC and check every benchmark
printf "# Per-machine settings (written by setup_linux.sh).\ncompiler: %s\n" "$GCC" > config/local.yaml
echo "[4/4] Checking the compiler and benchmarks..."
.venv/bin/python scripts/check_setup.py --fix-references

echo
echo "Setup finished. Start the app with:  bash run_linux.sh"
