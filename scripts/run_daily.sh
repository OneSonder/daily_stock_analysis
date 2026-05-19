#!/usr/bin/env bash
# Run daily_stock_analysis main.py from repo root using .venv when present.
# Usage: scripts/run_daily.sh [main.py args...]
#   RUN_SCHEDULE=1 scripts/run_daily.sh   → main.py --schedule (when no args)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  echo "No .venv/bin/python or python3 found" >&2
  exit 1
fi

if [[ $# -eq 0 && "${RUN_SCHEDULE:-}" == "1" ]]; then
  exec "$PYTHON" "$ROOT/main.py" --schedule
fi

exec "$PYTHON" "$ROOT/main.py" "$@"
