"""Evidence Ledger: the canonical evidence contract consumed by the UI, Brief, Copilot and audit trail."""
from __future__ import annotations

import json
from typing import Iterable

import pandas as pd

from . import config, db

SEVERITY_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
SEVERITY_WEIGHT = {"LOW": 0.15, "MEDIUM": 0.40, "HIGH": 0.70, "CRITICAL": 1.00}
MAX_CLAIM_IDS = 50


def make_ev(*, rule_id: str | None, severity: str | None, source_table: str, source_row_id: str, claim_ids: Iterable[str] | None,
            provider_id: str | None, feature: str, observed: float | None, expected: float | None, unit: str | None, ts,
            explanation: str, facility_id: str | None = None, payload: dict | None = None, evidence_type: str = "RULE",
            model_version: str | None = None, claim_count: int | None = None) -> dict:
    ids = list(dict.fromkeys(claim_ids or []))
    return {
        "evidence_type": evidence_type, "rule_id": rule_id, "severity": severity, "source_table": source_table,
        "source_row_id": str(source_row_id), "claim_ids": ids[:MAX_CLAIM_IDS], "claim_count": int(claim_count if claim_count is not None else len(ids)),
        "provider_id": provider_id, "facility_id": facility_id, "feature": feature,
        "observed_value": None if observed is None else float(observed), "expected_value": None if expected is None else float(expected),
        "unit": unit, "event_ts": pd.Timestamp(ts), "explanation": explanation,
        "rule_version": config.RULE_VERSION if evidence_type == "RULE" else None, "model_version": model_version, "payload": payload or {},
    }


def _arr(v: list[str]) -> str:
    return "{" + ",".join('"' + x.replace('"', '') + '"' for x in v) + "}"


def persist(evs: list[dict], start_id: int = 1) -> pd.DataFrame:
    """Assign stable IDs and bulk-insert into PostgreSQL. Returns the evidence frame."""
    df = pd.DataFrame(evs)
    df.insert(0, "evidence_id", [f"EV-{start_id + i:06d}" for i in range(len(df))])
    df["case_id"] = None
    out = df.copy()
    out["claim_ids"] = out.claim_ids.apply(_arr)
    out["payload"] = out.payload.apply(lambda d: json.dumps(d, default=db._json_default))
    out["event_ts"] = out.event_ts.dt.strftime("%Y-%m-%d %H:%M:%S")
    cols = ["evidence_id", "case_id", "evidence_type", "rule_id", "severity", "source_table", "source_row_id", "claim_ids", "claim_count",
            "provider_id", "facility_id", "feature", "observed_value", "expected_value", "unit", "event_ts", "explanation", "rule_version",
            "model_version", "payload"]
    db.copy_df(out, "evidence", cols)
    return df


def next_id() -> int:
    r = db.query_one("SELECT COALESCE(MAX(CAST(SUBSTRING(evidence_id FROM 4) AS INT)), 0) AS m FROM evidence")
    return int(r["m"]) + 1
