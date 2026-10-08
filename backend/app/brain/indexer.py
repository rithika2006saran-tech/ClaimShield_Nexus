"""Builds the Nexus Second Brain indices from PostgreSQL (the source of truth). Idempotent; safe to re-run."""
from __future__ import annotations

import json

from .. import config, db
from ..features import FEATURE_LABELS
from . import service
from .embedder import embed_doc

PATTERN_DESC = {
    "R001_DUPLICATE": "Duplicate billing: the same member, provider, procedure and date billed more than once.",
    "R002_UPCODING": "Upcoding: share of high-complexity evaluation visits significantly above comparable peers.",
    "R003_UNBUNDLING": "Unbundling: components of a bundled service billed separately from the parent code.",
    "R004_IMPLAUSIBLE_SERVICE": "Implausible or phantom service: service inconsistent with member age, sex, facility type or vital status.",
    "R005_EXCESSIVE_UTILIZATION": "Excessive utilization: claim volume or per-member intensity far above comparable peers.",
    "R006_IMPOSSIBLE_TIMING": "Impossible timing: more service time billed in a day than physically available, or services at distant sites on the same day.",
    "R007_REFERRAL_CONCENTRATION": "Referral concentration: inbound or outbound referrals concentrated on a single partner.",
    "R008_NETWORK_EXPANSION": "Network expansion: rapid growth of connected providers or facilities relative to prior behaviour.",
}


def _arr(v):
    return list(v) if v is not None else []


def case_docs() -> list[dict]:
    docs = []
    for c in db.query_rows("SELECT * FROM cases"):
        ev = db.query_rows("SELECT rule_id, count(*) n FROM evidence WHERE case_id=:c AND rule_id IS NOT NULL GROUP BY rule_id", {"c": c["case_id"]})
        rules = sorted({e["rule_id"] for e in ev} | set(_arr(c["rule_hits"])))
        text = f"{c['summary'] or ''} Patterns: {', '.join(_arr(c['patterns']))}. Rules: {', '.join(rules)}. Providers: {', '.join(_arr(c['provider_ids']))}. Facilities: {', '.join(_arr(c['facility_ids']))}."
        docs.append({"_id": c["case_id"], "case_id": c["case_id"], "kind": "current_case", "investigation_id": None, "anchor_provider_id": c["anchor_provider_id"],
                     "provider_ids": _arr(c["provider_ids"]), "specialty": c["specialty"], "patterns": _arr(c["patterns"]), "rule_ids": rules, "severity": c["review_priority"],
                     "priority": c["review_priority"], "outcome": c["review_status"], "status": c["review_status"], "title": f"{c['case_id']} - {c['anchor_provider_id']} ({c['specialty']})",
                     "summary": c["summary"] or "", "search_text": text, "analyst_notes": "", "patterns_text": " ".join(_arr(c["patterns"]) + rules),
                     "date": str(c["as_of"]) if c["as_of"] else None, "exposure": float(c["potential_exposure"] or 0), "priority_score": float(c["priority_score"]),
                     "n_providers": len(_arr(c["provider_ids"])),
                     "vector": embed_doc(text, rule_ids=rules, specialty=c["specialty"], exposure=float(c["potential_exposure"] or 0), n_providers=len(_arr(c["provider_ids"])))})
    for i in db.query_rows("SELECT * FROM investigations"):
        pats = _arr(i["patterns"])
        text = f"{i['summary']} {i['analyst_notes'] or ''} Outcome: {i['outcome']}. Patterns: {', '.join(pats)}."
        rules = [p for p in pats if p.startswith("R00")]
        docs.append({"_id": i["investigation_id"], "case_id": i["investigation_id"], "kind": "historical_investigation", "investigation_id": i["investigation_id"],
                     "anchor_provider_id": i["provider_id"], "provider_ids": [i["provider_id"]], "specialty": i["specialty"], "patterns": pats, "rule_ids": rules,
                     "severity": None, "priority": None, "outcome": i["outcome"], "status": "CLOSED", "title": f"{i['investigation_id']} - {i['provider_id']} ({i['specialty']})",
                     "summary": i["summary"], "search_text": text, "analyst_notes": i["analyst_notes"] or "", "patterns_text": " ".join(pats),
                     "date": str(i["closed_date"] or i["opened_date"]), "exposure": float(i["amount_identified"] or 0), "priority_score": None, "n_providers": 1,
                     "vector": embed_doc(text, rule_ids=rules, specialty=i["specialty"], exposure=float(i["amount_identified"] or 0), n_providers=1, outcome_text=i["outcome"])})
    return docs


def evidence_docs() -> list[dict]:
    docs = []
    rows = db.query_rows("SELECT e.*, p.specialty FROM evidence e LEFT JOIN providers p ON p.provider_id=e.provider_id WHERE e.case_id IS NOT NULL")
    for e in rows:
        text = f"{e['evidence_type']} {e['rule_id'] or ''} {e['feature']} {e['explanation']}"
        docs.append({"_id": e["evidence_id"], "evidence_id": e["evidence_id"], "case_id": e["case_id"], "rule_id": e["rule_id"], "severity": e["severity"],
                     "evidence_type": e["evidence_type"], "provider_id": e["provider_id"], "claim_ids": _arr(e["claim_ids"])[:50], "source_table": e["source_table"],
                     "feature": e["feature"], "text": text, "date": e["event_ts"].date().isoformat(), "observed_value": e["observed_value"], "expected_value": e["expected_value"],
                     "vector": embed_doc(text, rule_ids=[e["rule_id"]] if e["rule_id"] else None, specialty=e["specialty"])})
    return docs


def entity_docs() -> list[dict]:
    docs = []
    rows = db.query_rows("""SELECT f.provider_id, f.name, f.specialty, f.region, f.peer_group, f.claims_per_month_90d, f.dup_rate_90d, f.high_cx_ratio_180d, f.ref_in_top_share_180d,
                            f.degree, s.xgb_risk, s.anomaly_score, n.community_id, n.betweenness FROM provider_features f
                            JOIN provider_scores s USING(provider_id) LEFT JOIN provider_network n USING(provider_id)
                            WHERE s.xgb_risk >= 0.2 OR s.anomaly_score >= 0.9 OR f.provider_id IN (SELECT unnest(provider_ids) FROM cases)""")
    case_of = {}
    for c in db.query_rows("SELECT case_id, provider_ids, patterns FROM cases"):
        for p in c["provider_ids"]:
            case_of[p] = c
    for r in rows:
        c = case_of.get(r["provider_id"])
        pats = _arr(c["patterns"]) if c else []
        profile = (f"Provider {r['provider_id']} {r['name']} ({r['specialty']}, {r['region']}). FWA risk score {r['xgb_risk']:.2f}; anomaly score {r['anomaly_score']:.2f}; "
                   f"{r['claims_per_month_90d']:.0f} claims/month; duplicate rate {r['dup_rate_90d']:.3f}; network degree {int(r['degree'] or 0)}.")
        docs.append({"_id": r["provider_id"], "entity_id": r["provider_id"], "entity_type": "provider", "specialty": r["specialty"], "region": r["region"], "patterns": pats,
                     "case_id": c["case_id"] if c else None, "name": f"{r['provider_id']} {r['name']}", "profile": profile, "patterns_text": " ".join(pats),
                     "metrics": {"xgb_risk": float(r["xgb_risk"]), "anomaly_score": float(r["anomaly_score"]), "degree": int(r["degree"] or 0)},
                     "vector": embed_doc(profile + " " + " ".join(pats), specialty=r["specialty"])})
    return docs


def pattern_docs() -> list[dict]:
    """Pattern memory: one doc per rule/FWA pattern, with historical support and typical outcomes mined from past investigations."""
    docs = []
    for rid, desc in PATTERN_DESC.items():
        inv = db.query_rows("SELECT outcome, count(*) n FROM investigations WHERE :r = ANY(patterns) GROUP BY outcome", {"r": rid})
        support = sum(x["n"] for x in inv)
        outs = sorted(inv, key=lambda x: -x["n"])
        docs.append({"_id": rid, "pattern_id": rid, "rule_ids": [rid], "patterns": [rid], "typical_outcomes": [o["outcome"] for o in outs[:3]], "description": desc,
                     "patterns_text": f"{rid} {rid.split('_', 1)[1].replace('_', ' ').lower()}", "support": int(support),
                     "vector": embed_doc(desc, rule_ids=[rid])})
    return docs


def review_docs() -> list[dict]:
    docs = []
    for r in db.query_rows("SELECT * FROM review_actions ORDER BY review_id"):
        c = db.query_one("SELECT provider_ids, patterns, rule_hits, specialty FROM cases WHERE case_id=:c", {"c": r["case_id"]}) or {}
        docs.append(service.review_doc(r["review_id"], r["case_id"], r["decision"], r["rationale"], r["reviewer"], c, str(r["created_at"])))
    return docs


def index_all(recreate: bool = True) -> dict:
    b = service.get_backend(refresh=True)
    b.ensure_indices(recreate=recreate)
    counts = {}
    for name, fn in (("cases", case_docs), ("evidence", evidence_docs), ("entities", entity_docs), ("patterns", pattern_docs), ("review_memory", review_docs)):
        docs = fn()
        counts[name] = b.bulk_index(name, docs) if docs else 0
    res = {"backend": b.name, "docs": counts, "vector_mode": b.vector_mode, "total": sum(counts.values())}
    db.log_model_run("second_brain_index", b.name, "brain-1.0.0", metrics=res, notes="Index rebuilt from PostgreSQL")
    return res


if __name__ == "__main__":
    print(json.dumps(index_all(), indent=2))
