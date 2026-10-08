# Testing

```bash
make test      # pytest: 67 tests (uses the pipeline output in PostgreSQL; runs the pipeline if the DB is empty)
make build     # tsc type-check + vite build
make verify    # 25-step end-to-end demo path against a running API
python scripts/verify_elasticsearch.py   # live Elasticsearch verification (needs a cluster)
```

## Coverage
| File | Covers |
|---|---|
| `test_pipeline_data.py` | scale targets, quarantine reasons, PRV-102/P102 convention, ground-truth isolation |
| `test_rules_evidence.py` | each of R001-R008 fires with the full evidence contract; claim IDs exist; anomaly/SHAP wording |
| `test_models.py` | chronological split, XGBoost beats rules-only, calibration label matches evidence, monotone 30/60/90, SHAP present |
| `test_hero_and_control.py` | CASE-1024 contents, similar case INV-0087, controls not flagged, peer benchmarks |
| `test_queue_funnel.py` | capacity 5/10/20, ordering, priority != model score, funnel computed and monotone |
| `test_network_temporal.py` | 1/2-hop graph, edges reference nodes, shortest path, phases and rolling windows, control escalation |
| `test_second_brain.py` | embedder, RRF math, BM25 exact IDs, filters, hybrid ranks, similar cases, kNN failure fallback |
| `test_es_query_builders.py` | Elasticsearch request bodies and mappings (offline) |
| `test_brief_copilot.py` | 12-section brief with validated citations, 8 copilot questions grounded, refusal without evidence, LLM output with invented IDs rejected, no-key deterministic mode |
| `test_review_memory.py` | four decisions persist, become searchable reviewer memory, survive re-index, closed cases leave queue, invalid decisions rejected, no deny/suspend endpoints |

## Results recorded at build time (sandbox)
- pytest: 67 passed.
- Frontend: `tsc -b` clean; `vite build` succeeded.
- `scripts/verify_all.py`: 25/25 passed against the live API (Second Brain on the local fallback backend).
- Screens rendered and screenshotted headless with Playwright against the real API without console errors.

## Not verified in the build sandbox
- `docker compose up` (image pulls blocked) - `docker compose config` validates.
- Live Elasticsearch (`scripts/verify_elasticsearch.py` exits 2 when unreachable).
- LLM providers (no API keys; only the validation/fallback path is tested, via stubs).
