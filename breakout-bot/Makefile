# Bot Breakout Swing — raccourcis de développement

BACKEND=backend
FRONTEND=frontend
PY=$(BACKEND)/.venv/bin/python

.PHONY: install dev api front test test-all lint build

install:           ## installe backend (venv) + frontend (npm)
	cd $(BACKEND) && uv venv .venv && uv pip install --python .venv/bin/python -e . pytest ruff mypy httpx
	cd $(FRONTEND) && npm install

api:               ## lance l'API FastAPI (port 8000)
	cd $(BACKEND) && .venv/bin/uvicorn app.main:app --reload --port 8000

front:             ## lance le frontend Vite (port 5173, proxy /api → 8000)
	cd $(FRONTEND) && npm run dev

test:              ## tests rapides (anti-look-ahead, fills, reproductibilité…)
	cd $(BACKEND) && .venv/bin/python -m pytest -m "not slow" -q

test-all:          ## tous les tests, y compris performance (< 60 s pour 3×12 mois)
	cd $(BACKEND) && .venv/bin/python -m pytest -q

lint:              ## ruff + mypy + tsc
	cd $(BACKEND) && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests
	cd $(BACKEND) && .venv/bin/python -m mypy app/engine app/execution app/backtest app/config app/metrics app/optimize app/adaptive
	cd $(FRONTEND) && npx tsc --noEmit

build:             ## build de production du frontend
	cd $(FRONTEND) && npm run build
