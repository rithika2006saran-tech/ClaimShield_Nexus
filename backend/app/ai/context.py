"""Case context: the ONLY material the Brief and Copilot may use. Everything is read from PostgreSQL evidence/model outputs plus
Second Brain retrieval. IDs not present in this context can never appear in a validated answer."""
from __future__ import annotations

import json

from .. import db
from ..brain import service as brain

SEV = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, None: 0}


def _j(v):
    return json.loads(v) if isinstance(v, str) else v


def load_evidence(case_id: str) -> list[dict]:
    rows = db.query_rows("SELECT * FROM evidence WHERE case_id=:c ORDER BY evidence_id", {"c": case_id})
    for r in rows:
        r["payload"] = _j(r["payload"]) or {}
        r["event_ts"] = r["event_ts"].date().isoformat()
        r.pop("created_at", None)
    return rows


def build_context(case_id: str, with_similar: bool = True) -> dict | None:
    c = db.query_one("SELECT * FROM cases WHERE case_id=:c", {"c": case_id})
    if not c:
        return None
    c = {k: (float(v) if k == "potential_exposure" else v) for k, v in c.items()}
    c["components"] = _j(c["components"])
    c["network_signals"] = _j(c["network_signals"])
    for k in ("as_of", "first_activity", "created_at", "updated_at"):
        c[k] = str(c[k]) if c.get(k) else None
    ev = load_evidence(case_id)
    provs = {p["provider_id"]: p for p in db.query_rows("SELECT provider_id, display_label, name, specialty, region FROM providers WHERE provider_id = ANY(:p)", {"p": c["provider_ids"]})}
    anchor = c["anchor_provider_id"]
    tl = db.query_one("SELECT payload FROM provider_timeline WHERE provider_id=:p", {"p": anchor})
    tl = _j(tl["payload"]) if tl else None
    scores = db.query_one("SELECT xgb_risk, anomaly_score, shap FROM provider_scores WHERE provider_id=:p", {"p": anchor}) or {}
    shap = _j(scores.get("shap")) if scores else None
    fc = db.query_one("SELECT f30, f60, f90, label FROM provider_forecast WHERE provider_id=:p ORDER BY month_idx DESC LIMIT 1", {"p": anchor})
    reviews = db.query_rows("SELECT review_id, decision, rationale, reviewer, created_at, new_status FROM review_actions WHERE case_id=:c ORDER BY review_id", {"c": case_id})
    for r in reviews:
        r["created_at"] = str(r["created_at"])
    similar = brain.similar_cases(case_id, 5)["hits"] if with_similar else []
    ids = {"evidence": {e["evidence_id"] for e in ev}, "claims": set(c["claim_ids"]) | {x for e in ev for x in e["claim_ids"]},
           "providers": set(c["provider_ids"]) | {p for h in similar for p in h["doc"].get("provider_ids", [])}, "facilities": set(c["facility_ids"]), "cases": {case_id} | {h["id"] for h in similar}}
    return {"case": c, "providers": provs, "evidence": ev, "timeline": tl, "shap": shap, "scores": {"xgb_risk": scores.get("xgb_risk"), "anomaly_score": scores.get("anomaly_score")},
            "forecast": fc, "similar": similar, "reviews": reviews, "allowed_ids": ids, "anchor": anchor}


def by_type(ctx: dict, t: str, provider: str | None = None) -> list[dict]:
    return [e for e in ctx["evidence"] if e["evidence_type"] == t and (provider is None or e["provider_id"] == provider)]


def rule_groups(ctx: dict) -> dict[str, list[dict]]:
    g: dict[str, list[dict]] = {}
    for e in by_type(ctx, "RULE"):
        g.setdefault(e["rule_id"], []).append(e)
    for v in g.values():
        v.sort(key=lambda e: (-SEV.get(e["severity"], 0), -e["claim_count"], e["evidence_id"]))
    return g
