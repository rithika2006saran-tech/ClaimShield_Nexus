# Responsible AI

**Decision support for human investigators. Never an autonomous fraud decision.**

## Language
The product says *high-priority investigation lead*, *suspicious pattern*, *elevated FWA risk*, *anomalous behaviour*. It never says a provider "committed fraud". Tests assert banned phrasing is absent from the Brief and Copilot.

## Signal semantics
| Signal | What it is | What it is not |
|---|---|---|
| Rule hit (R001-R008) | deterministic, versioned, evidence-backed | a finding of misconduct |
| Isolation Forest **anomaly score** | percentile of unusual behaviour | a fraud probability |
| XGBoost **FWA risk score** | supervised score on synthetic scenarios | a probability of fraud |
| SHAP | attribution of the model's score | proof or causation |
| Peer deviation | distance from specialty/region/facility-type peers | evidence by itself (legitimate high utilization exists - see controls) |
| Network relationship | investigation lead | proof of coordination |
| 30/60/90 | "probability" only because calibration criteria passed on a later test period (synthetic); otherwise "escalation index" | a guarantee |

## Guardrails
- The system **cannot** deny claims, suspend providers, or draw legal conclusions; no such endpoint exists (tested via the OpenAPI schema).
- Human decisions are mandatory and limited to **Escalate / Request Documentation / Monitor / Close**, with a required rationale, stored in PostgreSQL and written to reviewer memory.
- The LLM is not the detector. It sees only the current case context and its output is rejected if it contains any claim/evidence/case/provider ID not in that context. With no API key the Brief/Copilot are fully deterministic. When evidence is insufficient the Copilot answers: **"Insufficient evidence - human review required."**
- Every case lists limitations (no clinical documentation, no ownership data, case mix not modelled, synthetic data).
- Controls: legitimate high-utilization providers (PRV-777 oncology infusion cycles, PRV-778 PT episodes) are in the data and are not flagged.
- Metrics are never fabricated; displayed numbers come from executed runs.

## Known limitations
Synthetic data; labels derived from injected scenarios (optimistic metrics, see ML.md); peer groups ignore patient acuity; local hashed embeddings are not a learned semantic model; reviewer memory influences retrieval/context only and never automatically changes scores.
