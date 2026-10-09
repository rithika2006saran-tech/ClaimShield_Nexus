-- ClaimShield Nexus — PostgreSQL schema (transactional source of truth).
-- All data is synthetic. Ground-truth label tables are used ONLY for model
-- training/evaluation and are never read by rules, features, or the UI evidence.

DROP TABLE IF EXISTS case_claims, review_actions, evidence, cases, model_runs, quarantine,
  claim_labels, provider_labels, investigations, relationships, referrals,
  claims, procedures, members, providers, facilities CASCADE;

CREATE TABLE facilities (
  facility_id    TEXT PRIMARY KEY,
  name           TEXT NOT NULL,
  facility_type  TEXT NOT NULL,
  region         TEXT NOT NULL,
  city           TEXT NOT NULL,
  lat            DOUBLE PRECISION NOT NULL,
  lon            DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS user_roles (
  email TEXT PRIMARY KEY,
  role TEXT NOT NULL
);

CREATE TABLE providers (
  provider_id          TEXT PRIMARY KEY,           -- canonical, e.g. PRV-102
  display_label        TEXT NOT NULL,              -- display label, e.g. P102
  name                 TEXT NOT NULL,
  specialty            TEXT NOT NULL,
  region               TEXT NOT NULL,
  city                 TEXT NOT NULL,
  primary_facility_id  TEXT REFERENCES facilities(facility_id),
  primary_facility_type TEXT,
  enrolled_date        DATE
);

CREATE TABLE members (
  member_id   TEXT PRIMARY KEY,
  age         INT NOT NULL CHECK (age BETWEEN 0 AND 120),
  sex         TEXT NOT NULL CHECK (sex IN ('M','F')),
  region      TEXT NOT NULL,
  death_date  DATE
);

CREATE TABLE procedures (
  code               TEXT PRIMARY KEY,
  description        TEXT NOT NULL,
  category           TEXT NOT NULL,
  em_level           INT,                          -- 1..5 for evaluation/management codes
  base_amount        NUMERIC(12,2) NOT NULL,
  bundle_group       TEXT,
  is_bundle_parent   BOOLEAN DEFAULT FALSE,
  allowed_sex        TEXT DEFAULT 'A',
  min_age            INT DEFAULT 0,
  max_age            INT DEFAULT 120,
  facility_types     TEXT[],                       -- NULL = any
  service_minutes    INT DEFAULT 20,
  repeat_same_day_ok BOOLEAN DEFAULT FALSE
);

CREATE TABLE claims (
  claim_id               TEXT PRIMARY KEY,
  member_id              TEXT NOT NULL REFERENCES members(member_id),
  provider_id            TEXT NOT NULL REFERENCES providers(provider_id),
  referring_provider_id  TEXT REFERENCES providers(provider_id),
  facility_id            TEXT NOT NULL REFERENCES facilities(facility_id),
  service_date           DATE NOT NULL,
  submit_date            DATE NOT NULL,
  procedure_code         TEXT NOT NULL REFERENCES procedures(code),
  units                  INT NOT NULL DEFAULT 1 CHECK (units > 0),
  billed_amount          NUMERIC(12,2) NOT NULL CHECK (billed_amount >= 0),
  allowed_amount         NUMERIC(12,2) NOT NULL CHECK (allowed_amount >= 0),
  paid_amount            NUMERIC(12,2) NOT NULL CHECK (paid_amount >= 0),
  service_minutes        INT NOT NULL DEFAULT 20,
  claim_type             TEXT NOT NULL
);
CREATE INDEX claims_provider_date_idx ON claims(provider_id, service_date);
CREATE INDEX claims_member_idx ON claims(member_id);
CREATE INDEX claims_date_idx ON claims(service_date);
CREATE INDEX claims_facility_idx ON claims(facility_id);

-- Synthetic ground truth (injected scenarios). NEVER used as a model feature.
CREATE TABLE claim_labels (
  claim_id      TEXT PRIMARY KEY REFERENCES claims(claim_id),
  injected_fwa  BOOLEAN NOT NULL,
  scenario      TEXT NOT NULL
);
CREATE TABLE provider_labels (
  provider_id     TEXT PRIMARY KEY REFERENCES providers(provider_id),
  role            TEXT NOT NULL,                  -- normal|injected|historical|control|hero|ring
  scenarios       TEXT[] NOT NULL DEFAULT '{}',
  scenario_start  DATE,
  notes           TEXT
);

CREATE TABLE referrals (
  referral_id            TEXT PRIMARY KEY,
  referring_provider_id  TEXT NOT NULL REFERENCES providers(provider_id),
  target_provider_id     TEXT NOT NULL REFERENCES providers(provider_id),
  target_facility_id     TEXT REFERENCES facilities(facility_id),
  member_id              TEXT NOT NULL REFERENCES members(member_id),
  referral_date          DATE NOT NULL
);
CREATE INDEX referrals_target_idx ON referrals(target_provider_id, referral_date);
CREATE INDEX referrals_source_idx ON referrals(referring_provider_id, referral_date);

CREATE TABLE relationships (
  relationship_id    TEXT PRIMARY KEY,
  entity_a_type      TEXT NOT NULL,
  entity_a_id        TEXT NOT NULL,
  entity_b_type      TEXT NOT NULL,
  entity_b_id        TEXT NOT NULL,
  relationship_type  TEXT NOT NULL,                -- works_at | associated_with | shared_address
  start_date         DATE,
  source             TEXT
);
CREATE INDEX relationships_a_idx ON relationships(entity_a_id);
CREATE INDEX relationships_b_idx ON relationships(entity_b_id);

CREATE TABLE investigations (
  investigation_id  TEXT PRIMARY KEY,
  provider_id       TEXT NOT NULL REFERENCES providers(provider_id),
  opened_date       DATE NOT NULL,
  closed_date       DATE,
  patterns          TEXT[] NOT NULL DEFAULT '{}',
  specialty         TEXT,
  outcome           TEXT NOT NULL,
  amount_identified NUMERIC(14,2) DEFAULT 0,
  summary           TEXT NOT NULL,
  analyst_notes     TEXT
);

CREATE TABLE quarantine (
  id           SERIAL PRIMARY KEY,
  source_table TEXT NOT NULL,
  row_number   INT,
  reason       TEXT NOT NULL,
  raw          JSONB,
  loaded_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE model_runs (
  run_id        SERIAL PRIMARY KEY,
  run_type      TEXT NOT NULL,                     -- pipeline_stage | isolation_forest | xgboost | forecast | rules
  model_name    TEXT NOT NULL,
  model_version TEXT NOT NULL,
  dataset_version TEXT,
  started_at    TIMESTAMPTZ DEFAULT now(),
  finished_at   TIMESTAMPTZ,
  metrics       JSONB,
  params        JSONB,
  notes         TEXT
);

CREATE TABLE cases (
  case_id             TEXT PRIMARY KEY,
  anchor_provider_id  TEXT NOT NULL,
  provider_ids        TEXT[] NOT NULL,
  facility_ids        TEXT[] NOT NULL DEFAULT '{}',
  member_count        INT NOT NULL DEFAULT 0,
  member_ids_sample   TEXT[] NOT NULL DEFAULT '{}',
  claim_ids           TEXT[] NOT NULL DEFAULT '{}',
  claim_count         INT NOT NULL DEFAULT 0,
  rule_hits           TEXT[] NOT NULL DEFAULT '{}',
  patterns            TEXT[] NOT NULL DEFAULT '{}',
  specialty           TEXT,
  model_score         DOUBLE PRECISION,            -- XGBoost FWA risk score (not a probability claim)
  anomaly_score       DOUBLE PRECISION,            -- Isolation Forest anomaly score (percentile 0-1)
  components          JSONB NOT NULL,              -- risk decomposition
  priority_score      DOUBLE PRECISION NOT NULL,
  review_priority     TEXT NOT NULL,
  review_status       TEXT NOT NULL DEFAULT 'PENDING',
  potential_exposure  NUMERIC(14,2) NOT NULL DEFAULT 0,
  forecast_30d        DOUBLE PRECISION,
  forecast_60d        DOUBLE PRECISION,
  forecast_90d        DOUBLE PRECISION,
  forecast_label      TEXT,                        -- 'probability' | 'escalation index'
  network_signals     JSONB NOT NULL DEFAULT '[]',
  limitations         TEXT[] NOT NULL DEFAULT '{}',
  first_activity      DATE,
  as_of               DATE,
  summary             TEXT,
  created_at          TIMESTAMPTZ DEFAULT now(),
  updated_at          TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX cases_priority_idx ON cases(priority_score DESC);

CREATE TABLE evidence (
  evidence_id     TEXT PRIMARY KEY,
  case_id         TEXT,
  evidence_type   TEXT NOT NULL,                   -- RULE | PEER | MODEL | ANOMALY | SHAP | NETWORK | TEMPORAL | FORECAST
  rule_id         TEXT,
  severity        TEXT,
  source_table    TEXT NOT NULL,
  source_row_id   TEXT NOT NULL,
  claim_ids       TEXT[] NOT NULL DEFAULT '{}',
  claim_count     INT NOT NULL DEFAULT 0,
  provider_id     TEXT,
  facility_id     TEXT,
  feature         TEXT NOT NULL,
  observed_value  DOUBLE PRECISION,
  expected_value  DOUBLE PRECISION,
  unit            TEXT,
  event_ts        TIMESTAMPTZ NOT NULL,
  explanation     TEXT NOT NULL,
  rule_version    TEXT,
  model_version   TEXT,
  payload         JSONB NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX evidence_case_idx ON evidence(case_id);
CREATE INDEX evidence_provider_idx ON evidence(provider_id);
CREATE INDEX evidence_rule_idx ON evidence(rule_id);

CREATE TABLE review_actions (
  review_id     SERIAL PRIMARY KEY,
  case_id       TEXT NOT NULL REFERENCES cases(case_id),
  decision      TEXT NOT NULL CHECK (decision IN ('ESCALATE','REQUEST_DOCUMENTATION','MONITOR','CLOSE')),
  rationale     TEXT NOT NULL,
  reviewer      TEXT NOT NULL,
  prior_status  TEXT,
  new_status    TEXT,
  context       JSONB DEFAULT '{}',
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE case_claims (
  case_id               TEXT NOT NULL,
  claim_id              TEXT NOT NULL,
  provider_id           TEXT NOT NULL,
  member_id             TEXT,
  paid_amount           NUMERIC(12,2),
  service_date          DATE,
  procedure_code        TEXT,
  rules                 TEXT,
  counts_toward_exposure BOOLEAN DEFAULT TRUE,
  PRIMARY KEY (case_id, claim_id)
);
CREATE INDEX case_claims_claim_idx ON case_claims(claim_id);
