"""Container entrypoint: wait for Postgres, run the pipeline if the database is empty (AUTO_PIPELINE), then serve the API."""
from __future__ import annotations

import os
import sys
import time

import uvicorn

from . import db


def wait_db(timeout: int = 90):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            db.query_one("SELECT 1")
            return
        except Exception:
            time.sleep(2)
    sys.exit("PostgreSQL not reachable")


def needs_pipeline() -> bool:
    try:
        return not (db.table_exists("cases") and db.query_one("SELECT count(*) n FROM cases")["n"] > 0)
    except Exception:
        return True


def wait_es(timeout: int = 60):
    from .brain.service import get_backend
    t0 = time.time()
    while time.time() - t0 < timeout:
        if get_backend(refresh=True).name == "elasticsearch":
            return True
        time.sleep(3)
    return False


if __name__ == "__main__":
    wait_db()
    if os.getenv("AUTO_PIPELINE", "true").lower() == "true" and needs_pipeline():
        from . import pipeline
        if os.getenv("SECOND_BRAIN_BACKEND", "auto") != "local":
            wait_es()
        pipeline.run(regenerate=False, reset=True, index_brain=True)
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
