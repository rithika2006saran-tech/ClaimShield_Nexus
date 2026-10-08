# Data model

All data is synthetic (`DATASET_VERSION synthetic-2026.10.08`, seed `20261008`, 2025-04-01 to 2026-09-30, "as of" 2026-09-30). Defaults: 1,000 providers, 12,000 members, 260 facilities, 41 procedures, ~82.7k valid claims, ~4.8k referrals, 300 historical investigations.

## Core tables (PostgreSQL, `backend/app/schema.sql`)
`facilities`, `providers` (canonical `PRV-102`, display `P102`), `members`, `procedures`, `claims`, `referrals`, `relationships` (works_at, associated_with), `investigations` (historical), `quarantine` (invalid rows with reasons, raw JSON), `model_runs` (every executed pipeline/model stage with metrics), `cases`, `case_claims`, `evidence`, `review_actions`.

## Synthetic ground truth (never a feature)
`claim_labels(claim_id, injected_fwa, scenario)` and `provider_labels(provider_id, role, scenarios, ...)` record injected scenarios for training/evaluation only.

## Derived tables (written by the pipeline)
`claim_flags`, `provider_features` (82 columns incl. `peer_median__/peer_z__/peer_pct__/peer_ratio__*`), `provider_month_panel`, `provider_scores` (anomaly score, XGBoost risk, SHAP JSON), `provider_forecast` (raw/calibrated/final 30/60/90), `provider_network`, `network_edges`, `provider_timeline` (JSON).

## Evidence object (`evidence`)
`evidence_id (EV-######)`, `case_id`, `evidence_type` (RULE|PEER|MODEL|ANOMALY|SHAP|NETWORK|TEMPORAL|FORECAST), `rule_id`, `severity`, `source_table`, `source_row_id`, `claim_ids[]`, `provider_id`, `facility_id`, `feature`, `observed_value`, `expected_value`, `unit`, `event_ts`, `explanation`, `rule_version`, `model_version`, `payload`.

## Case (`cases`)
Anchor + provider/facility/claim sets, rule hits, patterns, `model_score` (XGBoost FWA risk, *not* a probability of fraud), `anomaly_score` (Isolation Forest percentile), `components` (9-part risk decomposition), `priority_score`, `review_priority`, `review_status` (PENDING -> ESCALATED / DOCUMENTATION_REQUESTED / MONITORING / CLOSED), `potential_exposure` (de-duplicated paid amount on implicated claims), `forecast_30d/60d/90d` + `forecast_label`, `network_signals`, `limitations`.

## Injected scenarios
Duplicate billing, upcoding, unbundling, implausible/phantom service, excessive utilization, impossible timing (volume/geography), referral concentration, coordinated provider network (hero P102 + ring PRV-601..605), behavioural escalation (hero from month 9 onward), historical similar ring (PRV-085..089, `INV-0087`), and two legitimate high-utilization controls. 30 deliberately invalid claim rows exercise quarantine (6 reasons x 5).

## Search documents (Elasticsearch / fallback)
Indices `cases` (current cases + historical investigations), `evidence`, `entities`, `patterns`, `review_memory`; see [ELASTICSEARCH.md](ELASTICSEARCH.md).
