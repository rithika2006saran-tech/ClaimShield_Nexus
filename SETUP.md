# Setup

## A. Docker Compose (recommended)
```bash
cp .env.example .env          # optional: set LLM_PROVIDER + key (leave "none" for deterministic mode)
docker compose up --build
```
First start: the backend waits for PostgreSQL (and Elasticsearch), generates synthetic data, ingests, scores, builds cases and indexes the Second Brain (~1-2 min), then serves the API. UI http://localhost:8080 - API http://localhost:8000/docs - ES http://localhost:9200. Needs roughly 3 GB RAM (ES heap capped at 768 MB). Set `AUTO_PIPELINE=false` to skip the auto-run.

## B. Native development (no Docker)
Prerequisites: Python 3.12+, Node 20+, PostgreSQL 14+, (optional) Elasticsearch 8.x.
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
createdb claimshield   # user/password claimshield/claimshield, or set DATABASE_URL
export DATABASE_URL=postgresql+psycopg://claimshield:claimshield@127.0.0.1:5432/claimshield
make pipeline          # data -> ingestion -> rules -> ML -> graph -> temporal -> cases -> Second Brain   (~70 s)
make api               # http://localhost:8000
cd frontend && npm install && npm run dev    # http://localhost:5173 (proxies /api to :8000)
```
`scripts/dev_postgres.sh` starts a throwaway local PostgreSQL if you have the binaries but no service.

## Configuration (`.env.example`)
`DATABASE_URL`, `ELASTICSEARCH_URL`, `SECOND_BRAIN_BACKEND` (`auto|elasticsearch|local`), `LLM_PROVIDER` (`none|anthropic|openai`), `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` (+ model names), `AUTO_PIPELINE`. No secrets are committed.

## Useful commands
`make test` (pytest) - `make build` (frontend type-check + build) - `make verify` (E2E demo path against a running API) - `python -m app.pipeline --reset` (regenerate data) - `python -m app.brain.indexer` (rebuild search indices).
