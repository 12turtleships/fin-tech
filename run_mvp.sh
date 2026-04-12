#!/usr/bin/env bash
# Run mvp.py every 6 hours (invoke this from cron).
# Usage: ./run_mvp.sh   or   bash run_mvp.sh
# Cron uses a minimal env: use a venv so dependencies (e.g. requests) are available.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
LOG_FILE="${LOG_DIR}/mvp-$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"
cd "$SCRIPT_DIR" || exit 1

# Use project venv if present (cron does not load your shell env)
if [ -f "${SCRIPT_DIR}/venv/bin/python" ]; then
  PYTHON="${SCRIPT_DIR}/venv/bin/python"
elif [ -f "${SCRIPT_DIR}/.venv/bin/python" ]; then
  PYTHON="${SCRIPT_DIR}/.venv/bin/python"
else
  PYTHON="python3"
fi

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] Starting mvp.py (python: $PYTHON)" >> "$LOG_FILE"
"$PYTHON" mvp.py >> "$LOG_FILE" 2>&1
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] Finished mvp.py (exit $?)" >> "$LOG_FILE"
