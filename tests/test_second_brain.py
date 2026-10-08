from app.brain import service
from app.brain.base import Hit, hybrid_search, rrf_fuse
from app.brain.embedder import DIM, embed_doc, embed_query
from app.brain.local_backend import LocalBackend


def test_embedding_deterministic_and_normalised():
    a, b = embed_query("duplicate billing referral concentration"), embed_query("duplicate billing referral concentration")
    assert a == b and len(a) == DIM
    assert abs(sum(x * x for x in a) - 1) < 1e-3


def test_rrf_math():
    h = lambda i, r: Hit(id=i, index="cases", source={}, bm25_rank=r, bm25_score=1.0)
    k = lambda i, r: Hit(id=i, index="cases", source={}, knn_rank=r, knn_score=1.0)
    out = rrf_fuse([[h("A", 1), h("B", 2)], [k("B", 1), k("C", 2)]], k=60)
    assert out[0].id == "B"            # present in both lists
    assert abs(out[0].rrf_score - (1 / 62 + 1 / 61)) < 1e-9
    assert out[0].bm25_rank == 2 and out[0].knn_rank == 1


def test_bm25_exact_identifier_lookup():
    r = service.search("INV-0087", "cases", None, 3, mode="bm25")
    assert r["hits"][0]["id"] == "INV-0087"
    r = service.search("CASE-1024", "cases", None, 3, mode="bm25")
    assert r["hits"][0]["id"] == "CASE-1024"
    ev = service.search("R007_REFERRAL_CONCENTRATION", "evidence", {"case_id": "CASE-1024"}, 5, mode="bm25")
    assert ev["hits"] and all(h["doc"]["rule_id"] == "R007_REFERRAL_CONCENTRATION" or h["bm25_rank"] for h in ev["hits"])


def test_claim_id_lookup_hits_evidence():
    row = service.search("CLM-068187", "evidence", None, 3, mode="bm25")["hits"]
    assert row and "CLM-068187" in row[0]["doc"]["claim_ids"]


def test_structured_filters_are_enforced():
    r = service.search("duplicate billing", "cases", {"kind": "historical_investigation", "specialty": "Orthopedics"}, 20)
    assert r["hits"] and all(h["doc"]["kind"] == "historical_investigation" and h["doc"]["specialty"] == "Orthopedics" for h in r["hits"])
    r = service.search("", "cases", {"severity": "CRITICAL"}, 20)
    assert r["hits"] and all(h["doc"]["severity"] == "CRITICAL" for h in r["hits"])
    r = service.search("provider", "entities", {"entity_type": "provider"}, 5)
    assert all(h["doc"]["entity_type"] == "provider" for h in r["hits"])


def test_hybrid_combines_bm25_and_knn():
    r = service.search("referral hub coordinated ring shared facility", "cases", {"kind": "historical_investigation"}, 10)
    assert any(h["bm25_rank"] for h in r["hits"]) and any(h["knn_rank"] for h in r["hits"])
    assert r["hits"][0]["retrieval"]["method"].startswith("RRF")


def test_similar_cases_for_hero():
    r = service.similar_cases("CASE-1024", 5)
    assert r["hits"][0]["id"] == "INV-0087"
    assert r["hits"][0]["shared_rules"]
    assert all(h["doc"]["kind"] == "historical_investigation" for h in r["hits"])


def test_knn_failure_falls_back_to_bm25():
    class Broken(LocalBackend):
        def knn(self, *a, **k):
            raise RuntimeError("vector index unavailable")
    b = Broken()
    hits = hybrid_search(b, "cases", "INV-0087", embed_query("INV-0087"), None, 3)
    assert hits and hits[0].id == "INV-0087"


def test_all_five_indices_populated():
    st = service.status()
    for ix in ("cases", "evidence", "entities", "patterns"):
        assert st["indices"][ix] > 0, ix
