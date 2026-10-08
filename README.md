# ClaimShield Nexus

**Evidence-connected healthcare FWA investigation intelligence.** ClaimShield Nexus compresses tens of thousands of claims and alerts into a small, ranked set of explainable SIU (Special Investigations Unit) investigation cases.

> AI flags. Evidence connects. Time reveals. Graph explains. **SIU decides.**

All data is **synthetic**. Every output is an *investigation lead for human review* - the system never says a provider committed fraud, and it never denies claims, suspends providers or makes legal conclusions.

## What it does

```
Synthetic claims -> Feature intelligence -> FWA detection (R001-R008 + XGBoost + Isolation Forest + SHAP)
 -> Evidence fusion -> Network intelligence -> Temporal intelligence -> 30/60/90 risk
 -> SIU prioritization -> Investigation Workspace -> Nexus Second Brain -> Investigation Copilot
 -> Human SIU review -> Reviewer memory
```

| Screen | Purpose |
|---|---|
| **Command Center** | Computed alert-compression funnel (claims -> anomalies -> suspicious claims -> connected cases -> high-risk cases -> SIU priorities), model evidence, rule findings |
| **SIU Queue** | Top-5/10/20 cases by a nine-component priority policy (not model score alone) |
| **Investigation Workspace** (hero) | Left: summary, risk decomposition, evidence, "what changed?" timeline - Center: Cytoscape network - Right: Nexus Copilot - Bottom: brief, evidence ledger, similar cases, 30/60/90, human decision |
| **Network Explorer** | 1-hop / 2-hop ego networks, shortest paths (Cytoscape.js + NetworkX) |
| **Provider Profile** | Peer benchmarking (specialty / region / facility type), scores, SHAP, timeline |
| **Nexus Memory** | Hybrid search (BM25 + kNN + filters + RRF) over cases, evidence, entities, patterns and reviewer memory |

**Hero demo:** `CASE-1024` - anchor provider `PRV-102` (display label P102) - duplicate billing, excessive utilization, impossible timing, referral concentration, shared facility, network expansion, temporal escalation, similar historical investigation `INV-0087`. Legitimate high-utilization **controls** `PRV-777` (oncology infusion cycles) and `PRV-778` (physical-therapy episodes) are correctly *not* flagged.

## Stack
React + Vite + TypeScript + Tailwind + shadcn/ui + Recharts + Cytoscape.js | FastAPI + Pydantic | PostgreSQL (source of truth) + Pandas + NumPy | XGBoost + scikit-learn Isolation Forest + SHAP | NetworkX | Elasticsearch (BM25, kNN, filters, RRF) | LLM provider abstraction with deterministic fallback | Docker Compose | pytest.

Modular monolith: one FastAPI backend (`backend/app/`), no extra services.

## Quick start
```bash
cp .env.example .env
docker compose up --build        # PostgreSQL + Elasticsearch + backend (auto-runs pipeline on first start) + frontend
# UI  http://localhost:8080      API docs http://localhost:8000/docs
```
No Docker? See [SETUP.md](SETUP.md) (native PostgreSQL + `make pipeline api frontend`). An LLM key is **optional**: without one the Brief and Copilot run fully deterministically from evidence.

## Documentation
[ARCHITECTURE](ARCHITECTURE.md) - [API](API.md) - [DATA_MODEL](DATA_MODEL.md) - [ML](ML.md) - [ELASTICSEARCH](ELASTICSEARCH.md) - [RESPONSIBLE_AI](RESPONSIBLE_AI.md) - [DEMO](DEMO.md) - [SETUP](SETUP.md) - [TESTING](TESTING.md) - [REUSE](REUSE.md) - [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Verification status (see TESTING.md for evidence)
Verified in the build sandbox (details: docs/DEFINITION_OF_DONE.md): pipeline, PostgreSQL, 67 pytest tests, frontend type-check + build, 25-step end-to-end demo path, Second Brain on the **local fallback backend**. **Not verifiable there:** `docker compose up` and a live Elasticsearch cluster (container registry and Elastic artifact hosts were blocked by the sandbox network). `docker compose config` validates, and `scripts/verify_elasticsearch.py` is provided to verify the live cluster on your machine.
