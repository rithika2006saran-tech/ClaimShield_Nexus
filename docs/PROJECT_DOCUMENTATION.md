# ClaimShield Nexus: Complete Project Documentation

## 1. Introduction & Overview
**ClaimShield Nexus** is a next-generation Fraud, Waste, and Abuse (FWA) intelligence platform designed for healthcare payers and Special Investigation Units (SIUs). The platform moves beyond simple rules-based flagging by integrating complex network analysis, machine learning (XGBoost & Anomaly Detection), and a "Second Brain" semantic retrieval system. It provides investigators with an intelligent, priority-ranked queue and an evidence-grounded AI Copilot.

## 2. System Architecture
The application follows a modern decoupled architecture:

* **Frontend:** Built with React, TypeScript, and Vite. Uses Tailwind CSS for styling and `lucide-react` for iconography. It features a dark/light mode responsive dashboard.
* **Backend:** Built with FastAPI (Python). It serves REST endpoints for the UI and interfaces with the machine learning models and the Second Brain.
* **Database (Source of Truth):** PostgreSQL (managed via Supabase). Stores cases, providers, investigations, network features, and ML scores.
* **Search / Second Brain:** Elasticsearch. Acts as the knowledge retrieval system for historical patterns, reviewer memory, and case evidence.

## 3. Core FWA Rules (`rules.py`)
The platform continuously evaluates claims against 8 core heuristics to identify fraudulent behavior:

1. **R001_DUPLICATE (Duplicate billing):** The exact same procedure is billed multiple times for the same member by the same provider on the same date.
2. **R002_UPCODING (Upcoding):** A provider consistently bills for higher-complexity procedure codes significantly more often than their peers.
3. **R003_UNBUNDLING (Unbundling):** Components of a comprehensive procedure are billed separately instead of using the required bundled code.
4. **R004_IMPLAUSIBLE_SERVICE (Implausible/phantom service):** Billed services conflict with patient data (e.g., pediatric codes for adults, female-only procedures for males).
5. **R005_EXCESSIVE_UTILIZATION (Excessive utilization):** A provider’s claim volume or per-patient intensity drastically exceeds the statistical norm for their specialty.
6. **R006_IMPOSSIBLE_TIMING (Impossible timing):** Billing for more hours of service in a single day than physically exist, or impossible travel times between facilities.
7. **R007_REFERRAL_CONCENTRATION (Referral concentration):** An unusually high percentage of referrals are locked to a single partner facility, indicating potential kickback schemes.
8. **R008_NETWORK_EXPANSION (Network expansion):** A provider's network of associated partners grows at an abnormal rate, indicating emerging coordinated fraud rings.

## 4. Machine Learning Pipeline (`ml.py` & `pipeline.py`)
The ML pipeline augments the deterministic rules with predictive analytics:

* **XGBoost Risk Classifier:** Trained on historical investigation outcomes. It predicts the probability (`xgb_risk`) that a provider or case will result in a confirmed overpayment or fraud finding. The model uses a combination of rule hit rates, network degree, and historical utilization features.
* **Anomaly Detection:** Utilizes `IsolationForest` to calculate an `anomaly_score`. This identifies providers exhibiting highly unusual behavior patterns that may not yet map to a known FWA rule, ensuring novel fraud schemes are caught early.
* **Pipeline Orchestration:** The `pipeline.py` script orchestrates data extraction from PostgreSQL, runs feature engineering, scores the models, and writes the results back to the database.

## 5. The Second Brain (`indexer.py` & `embedder.py`)
The "Second Brain" powers the Nexus Copilot and the global search, giving the system contextual awareness of past investigations.

* **Local Embedding (`embedder.py`):** Instead of relying on expensive external LLMs for vector generation, the platform uses a highly optimized, local hybrid embedding strategy. It concatenates a hashed bag of word n-grams (lexical signal) with a structured FWA-signature block (flags, specialty, scale). 
* **Data Indexing (`indexer.py`):** Periodically pulls data from PostgreSQL and pushes it into Elasticsearch. It indexes:
  * **Cases & Evidence:** Active investigations and the raw claims data triggering them.
  * **Entities:** Provider profiles, risk scores, and network metrics.
  * **Patterns:** Historical support and typical outcomes for the 8 core FWA rules.
  * **Reviewer Memory:** Past human SIU decisions and the rationales behind them.

## 6. Frontend User Experience
The user interface is built to handle high-density data efficiently without overwhelming the investigator.

* **Command Center:** A high-level overview of system health, active leads, and recent investigations.
* **SIU Queue (`Queue.tsx`):** A prioritized list of cases sorted by a dynamic score that weighs model risk, rule evidence, anomaly scores, and financial exposure.
* **Investigation Workspace (`Workspace.tsx`):** The core screen for working a case. It provides tabs for Overview (SHAP values, risk decomposition, timeline) and Network (graph visualization of provider/facility connections, evidence ledger).
* **Nexus Copilot (`Copilot.tsx`):** An AI assistant embedded directly into the workspace. It answers questions specifically using retrieved evidence from the Second Brain, ensuring responses are grounded in fact.
* **Network Explorer (`NetworkExplorer.tsx`):** A dedicated view for conducting 1-hop and 2-hop analysis of referral flows to detect organized crime rings.

## 7. Local Development & Setup
* **Backend:**
  ```bash
  python -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
  ```
* **Frontend:**
  ```bash
  cd frontend
  npm install
  npm run dev
  ```
* Ensure `.env` is configured with `DATABASE_URL` (Supabase), `ELASTICSEARCH_URL`, and the required API keys.
