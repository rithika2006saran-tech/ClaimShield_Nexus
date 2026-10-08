# services

The architecture is a **modular monolith**: service modules live in `backend/app/` (ingestion, features, rules, ml, forecast, graph, temporal, cases, brain, ai, api). This directory intentionally contains no independently deployed services.
