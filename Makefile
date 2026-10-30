# VoxNote developer commands (Linux / macOS / WSL / Git Bash)
PY ?= python3
VENV = backend/.venv
BIN = $(VENV)/bin

.PHONY: help setup env backend frontend dev test lint build docker docker-down demo clean

help:
	@echo "make setup     - install backend (venv) + frontend dependencies"
	@echo "make backend   - run the FastAPI API on http://localhost:8000"
	@echo "make frontend  - run the React app on http://localhost:5173"
	@echo "make dev       - run both (Ctrl+C stops both)"
	@echo "make demo      - run with the offline mock AI (no keys needed)"
	@echo "make test      - backend tests + frontend type-check"
	@echo "make docker    - full stack: Postgres, Redis, API, Celery worker, UI on :3000"

env:
	@test -f .env || (cp .env.example .env && echo "Created .env — add a free GROQ_API_KEY or GEMINI_API_KEY")

setup: env
	$(PY) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r backend/requirements-dev.txt
	cd frontend && npm install

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

dev:
	@trap 'kill 0' INT TERM; \
	(cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

demo:
	@trap 'kill 0' INT TERM; \
	(cd backend && LLM_PROVIDERS=mock .venv/bin/uvicorn app.main:app --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

test:
	cd backend && .venv/bin/python -m pytest -q
	cd frontend && npm run typecheck

lint:
	cd backend && .venv/bin/ruff check app tests

build:
	cd frontend && npm run build

docker: env
	docker compose up --build

docker-down:
	docker compose down

clean:
	rm -rf backend/data frontend/dist
