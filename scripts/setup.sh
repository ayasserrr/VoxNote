#!/usr/bin/env bash
# One-time setup for local development (Linux / macOS / WSL).
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { cp .env.example .env; echo "→ created .env (add a free GROQ_API_KEY or GEMINI_API_KEY)"; }

echo "→ backend virtualenv"
python3 -m venv backend/.venv
backend/.venv/bin/pip install --upgrade pip -q
backend/.venv/bin/pip install -r backend/requirements-dev.txt -q

echo "→ frontend dependencies"
(cd frontend && npm install --no-audit --no-fund)

command -v ffmpeg >/dev/null || echo "⚠ ffmpeg not found: install it to transcribe long videos without captions."
echo "✓ done. Start everything with: ./scripts/dev.sh"
