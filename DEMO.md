# Demo script (about 8 minutes)

Start: `docker compose up --build` (or see SETUP.md) and open http://localhost:8080.

1. **Command Center** - "82,682 claims -> 18,069 anomalies -> 7,987 suspicious claims -> 33 connected cases -> 17 high-risk -> 10 SIU priorities." Numbers are computed by the pipeline; hover a stage for its definition. Point at model evidence (XGBoost PR-AUC 0.875 vs rules-only 0.384, synthetic, chronological split).
2. **SIU Queue** - toggle Top 5 / 10 / 20. CASE-1024 ranks first. Note the ranking is a nine-component policy (exposure, member impact, evidence strength, network, temporal...), not model score alone.
3. **Investigation Workspace (CASE-1024)**
   - Left: summary ($772k potential exposure, 480 members), risk decomposition with weights, evidence ledger summary, **"What changed?"** timeline (utilization up -> referral concentration -> duplicates -> new facilities -> network expansion -> high-priority lead).
   - Center: Cytoscape graph for PRV-102; click nodes/edges; switch **1-hop / 2-hop**; shared facility FAC-012 and the PRV-410 -> PRV-102 referral flow (110 referrals).
   - Right: **Nexus Copilot** - "Why was this case prioritized?", "What changed over time?", "Are there similar historical cases?" (INV-0087). Click citation chips to jump to the evidence row. Ask something unrelated to show *"Insufficient evidence - human review required."*
   - Bottom: **Investigation Brief** (12 sections, every claim cited), **Evidence Ledger** (filter, search `CLM-068187`), **Similar historical cases** (RRF with BM25/kNN ranks), **Model attribution** (SHAP), **30/60/90** with the calibration note, **Human decision**.
4. **Human review** - choose *Request Documentation*, enter a rationale, submit. Status changes; open **Nexus Memory** and see the decision as reviewer memory.
5. **Provider Profile** - PRV-102 peer benchmarks (percentiles, robust z). Then search `PRV-777`: very high utilization vs peers but **not in any case** - the legitimate-control story.
6. **Network Explorer** - recenter on FAC-012, shortest path PRV-102 -> PRV-087.
7. **Nexus Memory** - search `CASE-1024` (BM25 exact), then "referral hub coordinated ring" in hybrid mode with the historical filter.

Reset after the demo: `python scripts/verify_all.py` leaves state clean; to wipe reviews re-run `make pipeline`.
