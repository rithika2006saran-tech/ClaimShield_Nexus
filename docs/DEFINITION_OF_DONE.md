# Definition of Done - verification record

Legend: **V** verified by execution in the build sandbox - **P** verified partially (see note) - **U** not verifiable in the sandbox (verify on your machine with the given command).

| Item | Status | Evidence / command |
|---|---|---|
| Repository structure, deps, docs (12 required .md) | V | tree + `ls *.md` |
| Docker Compose file valid | V | `docker compose config -q` (exit 0) |
| `docker compose up` (all four containers start) | **U** | image registry blocked in sandbox; run `docker compose up --build` |
| PostgreSQL starts, schema applied | V | native PostgreSQL 16; pytest + pipeline |
| Elasticsearch starts / live indices / kNN / BM25 | **U** | `python scripts/verify_elasticsearch.py` (exit 2 = unreachable). ES request bodies + mappings unit-tested offline |
| Synthetic data at target scale (82,682 claims, 1,000 providers, 12,000 members, 260 facilities, ~4.8k referrals, 300 investigations) | V | `tests/test_pipeline_data.py` |
| Ingestion + quarantine (30 invalid rows, 6 reasons) | V | pipeline log, tests |
| Features, R001-R008 each with structured evidence | V | `tests/test_rules_evidence.py` |
| Isolation Forest anomaly score (not a probability) | V | `tests/test_rules_evidence.py`, `ML.md` |
| XGBoost chronological validation, PR-AUC, P@K, R@K | V | `tests/test_models.py`, `GET /api/models` |
| SHAP top contributors | V | `tests/test_models.py` |
| NetworkX analytics + Cytoscape rendering | V | `tests/test_network_temporal.py`; headless Playwright screenshots in `docs/screenshots` |
| Temporal intelligence + rolling 7/30/90 + phases | V | tests, screenshots |
| 30/60/90 honest calibration + labelling | V | `tests/test_models.py` (label derived from criteria) |
| Case formation, SIU prioritization, capacity 5/10/20 | V | `tests/test_queue_funnel.py` |
| Elasticsearch indices (5), BM25, filters, kNN, RRF | **P** | all five indices, BM25 exact IDs, filters, kNN, RRF verified on the **in-process fallback backend** (same contract); live ES = U |
| Similar historical case for CASE-1024 (INV-0087) | V | `tests/test_hero_and_control.py`, `verify_all.py` |
| Nexus Memory / reviewer memory persists | V | `tests/test_review_memory.py` |
| CASE-1024 end-to-end + legitimate controls not flagged | V | `scripts/verify_all.py` (25/25) |
| Investigation Brief (12 sections, validated citations) | V | `tests/test_brief_copilot.py` |
| Copilot deterministic fallback, refusal without evidence, invented-ID rejection | V | `tests/test_brief_copilot.py` |
| LLM providers (Anthropic/OpenAI) with real keys | **U** | no keys in sandbox; only the abstraction + validation/fallback path is tested |
| Human review (4 decisions) | V | `tests/test_review_memory.py` |
| API tests / frontend type-check + build | V | `make test`, `make build` |
| No secrets / node_modules / venv / __pycache__ in the ZIP | V | see archive listing check in TESTING.md |
