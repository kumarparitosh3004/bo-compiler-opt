#!/bin/bash
# Start PassTune on Linux and open it in the browser.
# usage:  bash run_linux.sh
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Run  bash setup_linux.sh  first."
  exit 1
fi
PORT="${PORT:-5000}"
URL="http://127.0.0.1:$PORT"
if command -v xdg-open >/dev/null 2>&1; then
  (sleep 2 && xdg-open "$URL" >/dev/null 2>&1) &
fi
echo "PassTune is starting at $URL  (press Ctrl+C here to stop it)"
exec .venv/bin/python web/app.py --port "$PORT"
