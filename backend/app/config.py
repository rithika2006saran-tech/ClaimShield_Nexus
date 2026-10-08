"""Central configuration (environment driven)."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

env_path = Path(__file__).resolve().parents[2] / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(env_path)
except ImportError:
    if env_path.exists():
        import re
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                m = re.match(r'^([^=]+)=(.*)$', line)
                if m:
                    k, v = m.group(1).strip(), m.group(2).strip()
                    # Strip quotes if any
                    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                        v = v[1:-1]
                    os.environ.setdefault(k, v)

REPO_ROOT = Path(__file__).resolve().parents[2]

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://claimshield:claimshield@127.0.0.1:5432/claimshield",
)
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://127.0.0.1:9200")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY", "")
SECOND_BRAIN_BACKEND = os.getenv("SECOND_BRAIN_BACKEND", "auto")  # auto|elasticsearch|local
DATA_DIR = Path(os.getenv("DATA_DIR", str(REPO_ROOT / "data"))).resolve()
SYNTH_DIR = DATA_DIR / "synthetic"
BRAIN_DIR = DATA_DIR / "second_brain"
ARTIFACT_DIR = DATA_DIR / "artifacts"

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none").lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# --- Synthetic dataset definition -------------------------------------------------
SEED = 20261008
DATA_START = date(2025, 4, 1)          # month index 1
DATA_END = date(2026, 9, 30)           # month index 18
AS_OF = DATA_END
N_MONTHS = 18

HERO_PROVIDER = "PRV-102"
HERO_CASE_ID = "CASE-1024"             # pinned for a stable demo narrative (see DATA_MODEL.md)
CONTROL_PROVIDERS = ["PRV-777", "PRV-778"]   # legitimate high-utilization controls

# --- Versions (audit) -----------------------------------------------------------
RULE_VERSION = "rules-1.0.0"
FEATURE_VERSION = "features-1.0.0"
DATASET_VERSION = "synthetic-2026.10.08"
PRIORITY_POLICY_VERSION = "siu-priority-1.0.0"

PRIORITY_WEIGHTS = {
    "model_risk": 0.20,
    "rule_evidence": 0.20,
    "peer_deviation": 0.10,
    "network": 0.10,
    "temporal": 0.10,
    "anomaly": 0.05,
    "evidence_strength": 0.10,
    "exposure": 0.10,
    "member_impact": 0.05,
}
