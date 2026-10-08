"""Elasticsearch backend: BM25/full-text, vector/kNN, structured filters. RRF fusion happens in `hybrid_search`
(client-side RRF keeps the pipeline independent of the Elasticsearch licence tier that gates the server-side `rrf` retriever)."""
from __future__ import annotations

from elasticsearch import Elasticsearch, helpers

from .. import config
from .base import ID_FIELDS, INDICES, TEXT_FIELDS, Backend, Hit, extract_ids
from .embedder import VECTOR_MODE
from .mappings import MAPPINGS, SETTINGS


def build_filter(filters: dict | None) -> list[dict]:
    """filters: {field: value | [values] | {"gte":..,"lte":..}}"""
    out = []
    for f, v in (filters or {}).items():
        if v is None:
            continue
        if isinstance(v, dict):
            out.append({"range": {f: v}})
        elif isinstance(v, (list, tuple, set)):
            out.append({"terms": {f: list(v)}})
        else:
            out.append({"term": {f: v}})
    return out


def build_lexical_query(index: str, query: str, filters: dict | None) -> dict:
    should: list[dict] = [{"multi_match": {"query": query, "fields": TEXT_FIELDS[index], "type": "best_fields", "operator": "or"}}]
    ids = extract_ids(query)
    if ids:       # exact identifiers (claim/provider/case/rule IDs) must win lexically
        for f in ID_FIELDS[index]:
            should.append({"terms": {f: ids, "boost": 12}})
    return {"bool": {"should": should, "minimum_should_match": 1, "filter": build_filter(filters)}}


class ESBackend(Backend):
    name = "elasticsearch"
    vector_mode = VECTOR_MODE

    def __init__(self, url: str | None = None):
        self.url = url or config.ELASTICSEARCH_URL
        if config.ELASTIC_API_KEY:
            self.es = Elasticsearch(self.url, api_key=config.ELASTIC_API_KEY, request_timeout=15, max_retries=1, retry_on_timeout=False)
        else:
            self.es = Elasticsearch(self.url, request_timeout=15, max_retries=1, retry_on_timeout=False)

    def available(self) -> bool:
        try:
            return bool(self.es.ping())
        except Exception:
            return False

    def ensure_indices(self, recreate: bool = False) -> None:
        for ix in INDICES:
            exists = self.es.indices.exists(index=ix)
            if exists and recreate:
                self.es.indices.delete(index=ix)
                exists = False
            if not exists:
                self.es.indices.create(index=ix, settings=SETTINGS, mappings=MAPPINGS[ix])

    def bulk_index(self, index: str, docs: list[dict]) -> int:
        actions = [{"_op_type": "index", "_index": index, "_id": d["_id"], "_source": {k: v for k, v in d.items() if k != "_id"}} for d in docs]
        ok, _ = helpers.bulk(self.es, actions, refresh="wait_for", chunk_size=500)
        return int(ok)

    def count(self, index: str) -> int:
        return int(self.es.count(index=index)["count"])

    def _hits(self, res: dict, index: str, kind: str) -> list[Hit]:
        out = []
        for r, h in enumerate(res["hits"]["hits"], 1):
            x = Hit(id=h["_id"], index=index, source=h["_source"], score=float(h.get("_score") or 0))
            if kind == "bm25":
                x.bm25_rank, x.bm25_score = r, x.score
            else:
                x.knn_rank, x.knn_score = r, x.score
            out.append(x)
        return out

    def lexical(self, index: str, query: str, filters: dict | None, size: int) -> list[Hit]:
        res = self.es.search(index=index, query=build_lexical_query(index, query, filters), size=size, source_excludes=["vector"])
        return self._hits(res, index, "bm25")

    def knn(self, index: str, vector: list[float], filters: dict | None, size: int) -> list[Hit]:
        body = {"field": "vector", "query_vector": vector, "k": size, "num_candidates": max(100, size * 4)}
        flt = build_filter(filters)
        if flt:
            body["filter"] = {"bool": {"filter": flt}}
        res = self.es.search(index=index, knn=body, size=size, source_excludes=["vector"])
        return self._hits(res, index, "knn")

    def filter_only(self, index: str, filters: dict | None, size: int) -> list[Hit]:
        res = self.es.search(index=index, query={"bool": {"filter": build_filter(filters)}} if filters else {"match_all": {}}, size=size, source_excludes=["vector"])
        return self._hits(res, index, "bm25")

    def get(self, index: str, doc_id: str) -> dict | None:
        try:
            return self.es.get(index=index, id=doc_id, source_excludes=["vector"])["_source"]
        except Exception:
            return None

    def health(self) -> dict:
        info = self.es.info()
        return {"backend": self.name, "url": self.url, "version": info["version"]["number"], "cluster_status": self.es.cluster.health()["status"],
                "indices": {ix: self.count(ix) for ix in INDICES if self.es.indices.exists(index=ix)}, "vector_mode": self.vector_mode}
