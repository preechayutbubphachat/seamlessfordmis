#!/usr/bin/env bash
# ============================================================
#  SeamlessFordMIS - Desktop SQLite D3 Gate Test Runner (Linux/macOS)
#  Runs G4 (compile), G1 (SQLite smoke), G5 (regression).
#  Writes everything to: desktop-sqlite-test-results.txt
#  Usage:  bash scripts/run_desktop_sqlite_tests.sh
#  Then paste desktop-sqlite-test-results.txt back to the assistant.
# ============================================================
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT/desktop-sqlite-test-results.txt"
cd "$ROOT" || { echo "cannot cd to repo root"; exit 1; }

{
  echo "SeamlessFordMIS Desktop SQLite D3 Gate run"
  echo "Started: $(date)"
  echo "Repo: $ROOT"
  echo
} > "$LOG"

cd backend || { echo "backend folder missing"; exit 1; }

if [ ! -x ".venv/bin/python" ]; then
  echo "[setup] creating venv..."
  python3 -m venv .venv || { echo "venv creation failed" | tee -a "$LOG"; exit 1; }
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[setup] installing backend/requirements.txt (includes pytest)..."
python -m pip install --upgrade pip   >> "$LOG" 2>&1
python -m pip install -r requirements.txt >> "$LOG" 2>&1

{
  echo "============================================================"
  echo "G4 - compileall backend/app"
  echo "============================================================"
} >> "$LOG"
python -m compileall -q app >> "$LOG" 2>&1
echo "G4 exit code: $?" >> "$LOG"; echo >> "$LOG"

{
  echo "============================================================"
  echo "G1 - SQLite workflow smoke suite (desktop_local + sqlite)"
  echo "============================================================"
} >> "$LOG"
APP_EDITION=desktop_local DATABASE_ENGINE=sqlite \
  python -m pytest tests/test_desktop_sqlite_workflow.py -v -p no:randomly --tb=short >> "$LOG" 2>&1
echo "G1 exit code: $?" >> "$LOG"; echo >> "$LOG"

{
  echo "============================================================"
  echo "G5 - Regression (rest of suite; uses your .env / PostgreSQL)"
  echo "NOTE: failures here may just mean PostgreSQL is not running."
  echo "============================================================"
} >> "$LOG"
python -m pytest tests/ -v --ignore=tests/test_desktop_sqlite_workflow.py --tb=short >> "$LOG" 2>&1
echo "G5 exit code: $?" >> "$LOG"; echo >> "$LOG"
echo "Finished: $(date)" >> "$LOG"

echo
echo "============================================================"
echo "Results written to: $LOG"
echo "============================================================"
cat "$LOG"
