"""Offline checks of the Elasticsearch request bodies (no cluster needed). Live-cluster behaviour is covered by scripts/verify_elasticsearch.py."""
from app.brain.embedder import DIM
from app.brain.es_backend import build_filter, build_lexical_query
from app.brain.mappings import MAPPINGS, SETTINGS


def test_filter_translation():
    f = build_filter({"specialty": "Orthopedics", "severity": ["HIGH", "CRITICAL"], "date": {"gte": "2026-01-01", "lte": "2026-09-30"}, "x": None})
    assert {"term": {"specialty": "Orthopedics"}} in f and {"terms": {"severity": ["HIGH", "CRITICAL"]}} in f
    assert {"range": {"date": {"gte": "2026-01-01", "lte": "2026-09-30"}}} in f and len(f) == 3


def test_lexical_query_boosts_exact_ids():
    q = build_lexical_query("evidence", "CLM-068187 duplicate R001_DUPLICATE", {"case_id": "CASE-1024"})
    shoulds = q["bool"]["should"]
    assert any("multi_match" in s for s in shoulds)
    boosted = [s for s in shoulds if "terms" in s]
    assert boosted and any("CLM-068187" in list(s["terms"].values())[0] for s in boosted)
    assert q["bool"]["filter"] == [{"term": {"case_id": "CASE-1024"}}]


def test_mappings_define_hybrid_fields():
    assert SETTINGS["number_of_shards"] == 1 and SETTINGS["number_of_replicas"] == 0
    assert set(MAPPINGS) == {"cases", "evidence", "entities", "patterns", "review_memory"}
    for ix, m in MAPPINGS.items():
        v = m["properties"]["vector"]
        assert v["type"] == "dense_vector" and v["dims"] == DIM and v["similarity"] == "cosine", ix
