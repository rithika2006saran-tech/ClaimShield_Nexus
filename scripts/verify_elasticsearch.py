#!/usr/bin/env python3
"""Verifies the Elasticsearch-backed Second Brain against a LIVE cluster (ELASTICSEARCH_URL, default http://127.0.0.1:9200).
Creates a throwaway index set only by running the standard indexer, then checks mappings, BM25, structured filters, kNN and RRF.
Exit 2 = cluster unreachable (nothing verified)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.brain import indexer
from app.brain.base import hybrid_search
from app.brain.embedder import embed_query
from app.brain.es_backend import ESBackend


def main() -> int:
    es = ESBackend()
    if not es.available():
        print(f"Elasticsearch NOT reachable at {es.url}. Nothing verified.")
        return 2
    import app.brain.service as svc
    svc._backend = es
    print("cluster:", es.health())
    res = indexer.index_all(recreate=True)
    print("indexed:", res)
    ok = True

    def chk(name, cond, detail=""):
        nonlocal ok
        ok &= bool(cond)
        print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

    for ix, n in res["docs"].items():
        if ix != "review_memory":
            chk(f"index {ix} populated", es.count(ix) == n and n > 0, f"({n})")
    chk("dense_vector mapping", es.es.indices.get_mapping(index="cases")["cases"]["mappings"]["properties"]["vector"]["type"] == "dense_vector")
    h = es.lexical("cases", "CASE-1024", None, 3)
    chk("BM25 exact case ID", h and h[0].id == "CASE-1024")
    h = es.lexical("evidence", "R007_REFERRAL_CONCENTRATION", {"case_id": "CASE-1024"}, 5)
    chk("BM25 rule ID + filter", h and all(x.source["case_id"] == "CASE-1024" for x in h))
    h = es.knn("cases", embed_query("referral hub coordinated ring shared facility duplicate billing"), {"kind": "historical_investigation"}, 5)
    chk("kNN + filter", h and all(x.source["kind"] == "historical_investigation" for x in h))
    h = hybrid_search(es, "cases", "referral concentration shared facility ring", embed_query("referral concentration shared facility ring"), {"kind": "historical_investigation"}, 5)
    chk("Hybrid BM25+kNN fused by RRF", h and h[0].explain["method"].startswith("RRF") and any(x.bm25_rank for x in h) and any(x.knn_rank for x in h))
    sim = svc.similar_cases("CASE-1024", 5)
    chk("Hero similar case INV-0087", sim["hits"] and sim["hits"][0]["id"] == "INV-0087", f"backend={sim['backend']}")
    print("ALL PASS" if ok else "FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
