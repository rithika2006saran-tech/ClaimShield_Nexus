"""Nexus Second Brain service: backend selection, hybrid retrieval, similar-case search, reviewer memory."""
from __future__ import annotations

import json
import threading

from .. import config, db
from .base import INDICES, Backend, Hit, hybrid_search
from .embedder import embed_doc, embed_query
from .local_backend import LocalBackend

_lock = threading.Lock()
_backend: Backend | None = None


def get_backend(force: str | None = None, refresh: bool = False) -> Backend:
    """Elasticsearch when reachable (SECOND_BRAIN_BACKEND auto|elasticsearch), otherwise the in-process fallback."""
    global _backend
    with _lock:
        if _backend is not None and not refresh and not force:
            return _backend
        choice = force or config.SECOND_BRAIN_BACKEND
        if choice in ("auto", "elasticsearch"):
            try:
                from .es_backend import ESBackend
                es = ESBackend()
                if es.available():
                    _backend = es
                    return _backend
            except Exception:
                pass
            if choice == "elasticsearch":
                raise RuntimeError("SECOND_BRAIN_BACKEND=elasticsearch but the cluster is unreachable")
        _backend = LocalBackend()
        return _backend


def status() -> dict:
    b = get_backend()
    try:
        h = b.health()
    except Exception as e:  # noqa: BLE001
        h = {"backend": b.name, "error": str(e)}
    h["elasticsearch_url"] = config.ELASTICSEARCH_URL
    h["using_fallback"] = b.name != "elasticsearch"
    return h


def search(query: str, index: str = "cases", filters: dict | None = None, size: int = 10, mode: str = "hybrid") -> dict:
    if index not in INDICES:
        raise ValueError(f"unknown index {index}")
    b = get_backend()
    hits = hybrid_search(b, index, query, embed_query(query) if query.strip() else None, filters, size, mode=mode)
    return {"query": query, "index": index, "filters": filters or {}, "mode": mode, "backend": b.name, "vector_mode": b.vector_mode, "hits": [h.to_dict() for h in hits]}


def similar_cases(case_id: str, size: int = 5) -> dict:
    """Historical investigations (and prior reviewed cases) similar to a current case, by behavioural pattern (kNN + BM25 over its signature, RRF)."""
    b = get_backend()
    doc = b.get("cases", case_id)
    if not doc:
        return {"case_id": case_id, "backend": b.name, "hits": [], "note": "case not indexed"}
    sig = doc.get("search_text") or doc.get("summary") or ""
    vec = embed_doc(sig, rule_ids=doc.get("rule_ids"), specialty=doc.get("specialty"), exposure=doc.get("exposure"), n_providers=doc.get("n_providers"))
    filt = {"kind": "historical_investigation"}
    q = " ".join(doc.get("patterns", []) + doc.get("rule_ids", []) + [doc.get("specialty") or ""])
    hits = hybrid_search(b, "cases", q, vec, filt, size)
    out = []
    for h in hits:
        d = h.to_dict()
        shared = sorted(set(doc.get("patterns", [])) & set(h.source.get("patterns", [])))
        shared_rules = sorted(set(doc.get("rule_ids", [])) & set(h.source.get("rule_ids", [])))
        d["shared_patterns"], d["shared_rules"] = shared, shared_rules
        d["same_specialty"] = h.source.get("specialty") == doc.get("specialty")
        out.append(d)
    return {"case_id": case_id, "backend": b.name, "vector_mode": b.vector_mode, "filters": filt, "hits": out}


def record_review(review: dict) -> dict:
    """Reviewer decision -> reviewer memory (searchable by later investigations). Postgres review_actions stays the source of truth."""
    b = get_backend()
    c = db.query_one("SELECT case_id, provider_ids, patterns, rule_hits, specialty, anchor_provider_id FROM cases WHERE case_id=:c", {"c": review["case_id"]}) or {}
    text = f"{review['decision']} {review.get('rationale', '')} patterns {' '.join(c.get('patterns') or [])} {' '.join(c.get('rule_hits') or [])}"
    doc = review_doc(review["review_id"], review["case_id"], review["decision"], review.get("rationale", ""), review.get("reviewer", ""), c, str(review.get("created_at", "")))
    b.ensure_indices()
    b.bulk_index("review_memory", [doc])
    return {"indexed": doc["_id"], "backend": b.name, "text": text[:200]}


OUTCOME_OF = {"ESCALATE": "escalated", "REQUEST_DOCUMENTATION": "documentation_requested", "MONITOR": "monitoring", "CLOSE": "closed"}


def review_doc(review_id, case_id, decision, rationale, reviewer, case_row: dict, created_at: str) -> dict:
    patterns = list(case_row.get("patterns") or [])
    rules = list(case_row.get("rule_hits") or [])
    text = f"Reviewer decision {decision} on {case_id}. {rationale} Patterns: {', '.join(patterns)}. Rules: {', '.join(rules)}."
    return {"_id": f"REV-{int(review_id):05d}", "review_id": f"REV-{int(review_id):05d}", "case_id": case_id, "decision": decision, "reviewer": reviewer,
            "provider_ids": list(case_row.get("provider_ids") or []), "patterns": patterns, "outcome": OUTCOME_OF.get(decision, decision.lower()), "source": "SIU reviewer",
            "specialty": case_row.get("specialty"), "rationale": rationale, "text": text, "patterns_text": " ".join(patterns + rules),
            "date": (created_at or "")[:10] or None, "vector": embed_doc(text, rule_ids=rules, specialty=case_row.get("specialty"), outcome_text=decision)}
