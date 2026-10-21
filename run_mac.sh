#!/bin/bash
# Start PassTune on macOS and open it in the browser.
# usage:  bash run_mac.sh
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Run  bash setup_mac.sh  first."
  exit 1
fi
PORT="${PORT:-5050}"
URL="http://127.0.0.1:$PORT"
(sleep 2 && open "$URL") &
echo "PassTune is starting at $URL  (press Ctrl+C here to stop it)"
exec .venv/bin/python web/app.py --port "$PORT"
