import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://claimshield:claimshield@127.0.0.1:5432/claimshield")
os.environ.setdefault("SECOND_BRAIN_BACKEND", "auto")
os.environ.setdefault("LLM_PROVIDER", "none")


@pytest.fixture(scope="session", autouse=True)
def pipeline_ready():
    """Tests run against the real pipeline output. If the DB is empty, run the full pipeline once."""
    from app import db
    if not (db.table_exists("cases") and db.query_one("SELECT count(*) n FROM cases")["n"] > 0):
        from app import pipeline
        pipeline.run(regenerate=False, reset=True, index_brain=True)
    from app.brain import service
    if service.get_backend().count("cases") == 0:
        from app.brain import indexer
        indexer.index_all()


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)
