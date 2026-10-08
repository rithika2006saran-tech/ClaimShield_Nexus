# Architecture

Modular monolith. One FastAPI process hosts every domain module; PostgreSQL is the transactional source of truth; Elasticsearch is the investigation retrieval layer.

```
                    +-------------------- frontend (React/Vite, nginx) --------------------+
                    | Command Center | Queue | Workspace | Network | Provider | Memory     |
                    +------------------------------ /api (REST) ---------------------------+
                                                         |
 +--------------------------------- backend/app (FastAPI) ---------------------------------+
 | datagen -> ingestion -> features -> rules -> ml -> forecast -> graph -> temporal -> cases |
 | api/routes   ai/{context,brief,copilot,llm}   brain/{embedder,base,es_backend,local,...}  |
 +-----------+-----------------------------------------------+-------------------------------+
             | SQL (source of truth)                          | index/search
        PostgreSQL                                   Elasticsearch  (or in-process fallback)
```

## Modules (`backend/app/`)
| Module | Responsibility |
|---|---|
| `config.py`, `db.py`, `schema.sql` | settings, SQLAlchemy/pandas helpers, schema |
| `datagen.py` | seeded synthetic data + injected scenarios + ground-truth label tables |
| `ingestion.py` | validation, quarantine with reasons, COPY load |
| `features.py` | peer groups, provider features (82 cols), provider-month panel |
| `rules.py`, `evidence.py` | R001-R008 and the canonical evidence object |
| `ml.py` | Isolation Forest (anomaly score), XGBoost (FWA risk), SHAP |
| `forecast.py` | 30/60/90 chronological models + isotonic calibration + honest labelling |
| `graph.py` | NetworkX analytics, Louvain communities, Cytoscape ego JSON |
| `temporal.py` | rolling 7/30/90-day features, behavioural phase detection |
| `cases.py` | case formation, 9-component risk decomposition, exposure, limitations |
| `brain/` | Second Brain: embedder, ES backend, local fallback backend, hybrid retrieval + RRF, indexer |
| `ai/` | case context, deterministic Brief (12 sections), Copilot, LLM abstraction |
| `api/routes.py`, `main.py`, `entrypoint.py` | REST API, container entrypoint (auto pipeline) |
| `pipeline.py` | orchestrates all stages and logs `model_runs` |

## Data flow & rules of the road
1. **Postgres is the source of truth.** Elasticsearch indices are rebuilt from Postgres (`python -m app.brain.indexer`); losing ES loses nothing.
2. **One evidence contract.** Every finding is an `evidence` row (`EV-xxxxxx`): `source_table`, `source_row_id`, `claim_ids`, `provider_id`, `rule_id`, `feature`, `observed_value`, `expected_value`, `event_ts`, `explanation`, `rule_version`/`model_version`. The UI, the Brief and the Copilot read the *same* rows.
3. **LLM is not a detector.** The Copilot receives only the current case context (evidence, model outputs, network, timeline, retrieved similar cases, limitations). Output is validated: any claim/evidence/case/provider ID outside the context rejects the LLM text and falls back to the deterministic answer.
4. **Resilience.** `SECOND_BRAIN_BACKEND=auto` uses Elasticsearch when reachable and an in-process backend (same documents, same BM25 + kNN + RRF contract) otherwise. kNN failure degrades to BM25 + filters.
5. **Ground truth isolation.** `claim_labels` / `provider_labels` are used only for model training/evaluation, never by rules, features, the UI or evidence.

## SIU prioritization
`priority = sum(weight_i * component_i)` over nine components (model risk .20, rule evidence .20, peer deviation .10, network .10, temporal .10, evidence strength .10, exposure .10, anomaly .05, member impact .05). Bands: >=0.70 CRITICAL, >=0.55 HIGH, >=0.40 MEDIUM. The queue returns the top 5/10/20 by priority then exposure; closed cases leave the default queue.

## Deployment
`docker-compose.yml`: `postgres:16`, `elasticsearch:8.15` (single node, 768 MB heap, 1 shard / 0 replicas), `backend` (waits for Postgres/ES, runs the pipeline if the DB is empty), `frontend` (nginx serving the build and proxying `/api`).
