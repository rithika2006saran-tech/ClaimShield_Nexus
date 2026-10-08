# API reference

Base: `http://localhost:8000` (interactive docs at `/docs`, OpenAPI at `/openapi.json`). Through the frontend container: `http://localhost:8080/api/...`.
There are **no endpoints that deny claims, suspend providers or decide fraud**; the only state-changing endpoints record a human decision or rebuild the search index.

| Method & path | Description |
|---|---|
| `GET /api/health` | API, database, Second Brain backend, LLM provider |
| `GET /api/command-center` | Computed funnel, counts, bands, rule findings, model headline metrics, top cases |
| `GET /api/models` | Latest `model_runs`: rules, isolation_forest, xgboost, forecast (with calibration), brain index |
| `GET /api/queue?capacity=5\|10\|20&include_reviewed=&specialty=&min_band=` | SIU queue + exposure coverage + weights |
| `GET /api/cases`, `GET /api/cases/{id}` | Case list / full detail (providers, risk decomposition, evidence summary, timeline, forecast, SHAP, similar cases, reviews, reviewer memory) |
| `GET /api/cases/{id}/evidence?type=&rule_id=&provider_id=&q=&limit=&offset=` | Evidence ledger (canonical objects) |
| `GET /api/cases/{id}/claims?rule=&limit=&offset=` | Implicated claims with linked evidence IDs |
| `GET /api/cases/{id}/network?hops=1\|2&center=` | Cytoscape-ready nodes/edges (edges/nodes carry evidence IDs where applicable) |
| `GET /api/cases/{id}/timeline?provider_id=` | Weekly rolling 7/30/90-day series + behavioural events + phase |
| `GET /api/cases/{id}/brief?format=json\|markdown` | 12-section Investigation Brief; citations validated before return |
| `GET /api/cases/{id}/similar` | Similar historical investigations (hybrid retrieval) |
| `POST /api/cases/{id}/copilot` `{question, use_llm}` | Evidence-grounded answer + citations, or "Insufficient evidence - human review required." |
| `POST /api/cases/{id}/review` `{decision, rationale, reviewer}` | Human decision: `ESCALATE`, `REQUEST_DOCUMENTATION`, `MONITOR`, `CLOSE`. Writes `review_actions`, updates case status, writes reviewer memory |
| `GET /api/cases/{id}/reviews` | Decision history |
| `GET /api/providers?q=&specialty=&sort=` , `GET /api/providers/{id}` | Provider search / profile with peer benchmarks, scores, SHAP, forecast, timeline, cases |
| `GET /api/network/ego?center=&hops=` , `GET /api/network/path?a=&b=` | Network Explorer |
| `GET /api/brain/status` , `POST /api/brain/search` `{query,index,mode,filters,size}` | Second Brain search; `mode` = `hybrid`\|`bm25`\|`knn`; `index` = cases\|evidence\|entities\|patterns\|review_memory |
| `GET /api/brain/memory` , `POST /api/brain/reindex` | Nexus Memory overview / rebuild indices from PostgreSQL |

Filters accept scalars, lists and ranges: `{"kind":"historical_investigation","specialty":"Orthopedics","date":{"gte":"2026-01-01"}}`.

## Example
```bash
curl -s localhost:8000/api/cases/CASE-1024/copilot -H 'content-type: application/json' -d '{"question":"What changed over time?"}'
```
