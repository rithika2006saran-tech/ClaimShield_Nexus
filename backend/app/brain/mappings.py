"""Elasticsearch index definitions for the Nexus Second Brain (single shard, no replicas: hackathon-sized)."""
from .embedder import DIM

SETTINGS = {"refresh_interval": "5s"}


def _vec():
    return {"type": "dense_vector", "dims": DIM, "index": True, "similarity": "cosine"}


def _kw(*names):
    return {n: {"type": "keyword"} for n in names}


MAPPINGS: dict[str, dict] = {
    "cases": {"properties": {
        **_kw("case_id", "investigation_id", "kind", "anchor_provider_id", "provider_ids", "specialty", "patterns", "rule_ids", "severity", "priority", "outcome", "status"),
        "title": {"type": "text"}, "summary": {"type": "text"}, "search_text": {"type": "text"}, "analyst_notes": {"type": "text"}, "patterns_text": {"type": "text"},
        "date": {"type": "date"}, "exposure": {"type": "float"}, "priority_score": {"type": "float"}, "n_providers": {"type": "integer"}, "vector": _vec()}},
    "evidence": {"properties": {
        **_kw("evidence_id", "case_id", "rule_id", "severity", "evidence_type", "provider_id", "claim_ids", "source_table", "feature"),
        "text": {"type": "text"}, "date": {"type": "date"}, "observed_value": {"type": "float"}, "expected_value": {"type": "float"}, "vector": _vec()}},
    "entities": {"properties": {
        **_kw("entity_id", "entity_type", "specialty", "region", "patterns", "case_id"),
        "name": {"type": "text"}, "profile": {"type": "text"}, "patterns_text": {"type": "text"}, "metrics": {"type": "object", "enabled": False}, "vector": _vec()}},
    "patterns": {"properties": {
        **_kw("pattern_id", "rule_ids", "patterns", "typical_outcomes"),
        "description": {"type": "text"}, "patterns_text": {"type": "text"}, "support": {"type": "integer"}, "vector": _vec()}},
    "review_memory": {"properties": {
        **_kw("review_id", "case_id", "decision", "reviewer", "provider_ids", "patterns", "outcome", "source", "specialty"),
        "rationale": {"type": "text"}, "text": {"type": "text"}, "patterns_text": {"type": "text"}, "date": {"type": "date"}, "vector": _vec()}},
}
