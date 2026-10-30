#!/usr/bin/env bash
# Run API (http://localhost:8000) + React UI (http://localhost:5173). Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."
trap 'kill 0' INT TERM EXIT
(cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) &
(cd frontend && npm run dev) &
wait
