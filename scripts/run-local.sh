#!/usr/bin/env bash
# Start the local HEXROT API and UI together. Ctrl+C stops both.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv. See README.md for the installation commands." >&2
  exit 1
fi
if [[ ! -d node_modules ]]; then
  echo "Missing frontend dependencies. Run npm ci first." >&2
  exit 1
fi
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!
cleanup() {
  kill "$API_PID" 2>/dev/null || true
  wait "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM
printf '%s\n' 'HEXROT.EXE: open http://127.0.0.1:5173' 'Press Ctrl+C to stop.'
npm run dev -- --host 127.0.0.1
