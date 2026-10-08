.PHONY: help up down dev-db pipeline api frontend test build verify demo clean

PY ?= python3
export PYTHONPATH := backend

help:
	@echo "make up        - docker compose up --build (PostgreSQL + Elasticsearch + backend + frontend)"
	@echo "make dev-db    - start a native PostgreSQL for development (no Docker)"
	@echo "make pipeline  - generate synthetic data, ingest, score, build cases, index Second Brain"
	@echo "make api       - run the FastAPI backend on :8000"
	@echo "make frontend  - run the Vite dev server on :5173"
	@echo "make test      - run the pytest suite"
	@echo "make build     - type-check and build the frontend"
	@echo "make verify    - run the end-to-end verification script"

up:
	docker compose up --build

down:
	docker compose down

dev-db:
	bash scripts/dev_postgres.sh

pipeline:
	$(PY) -m app.pipeline --reset

api:
	cd backend && $(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

test:
	$(PY) -m pytest tests -q

build:
	cd frontend && npm install && npm run build

verify:
	$(PY) scripts/verify_all.py

demo: pipeline
	@echo "Pipeline complete. Start the API (make api) and frontend (make frontend)."

clean:
	rm -rf data/synthetic data/second_brain data/artifacts frontend/dist frontend/node_modules
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
