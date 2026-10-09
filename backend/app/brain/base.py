"""Second Brain backend contract + shared hybrid retrieval (BM25 + kNN + filters -> RRF)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

INDICES = ["cases", "evidence", "entities", "patterns", "review_memory"]
RRF_K = 60
ID_PATTERN = re.compile(r"\b(CASE-\d+|CLM-\d+|PRV-\d+|FAC-\d+|EV-\d+|INV-\d+|REV-\d+|MEM-\d+|R00\d_[A-Z_]+)\b", re.I)

# fields searched lexically (BM25) per index
TEXT_FIELDS = {
    "cases": ["title^3", "summary^2", "search_text", "analyst_notes", "patterns_text^2"],
    "evidence": ["text^2", "feature", "rule_id"],
    "entities": ["name^3", "profile^2", "patterns_text"],
    "patterns": ["description^2", "patterns_text^2"],
    "review_memory": ["rationale^2", "text", "patterns_text"],
}
ID_FIELDS = {
    "cases": ["case_id", "provider_ids", "rule_ids", "investigation_id"],
    "evidence": ["evidence_id", "case_id", "claim_ids", "provider_id", "rule_id"],
    "entities": ["entity_id"],
    "patterns": ["pattern_id", "rule_ids"],
    "review_memory": ["review_id", "case_id", "provider_ids"],
}


@dataclass
class Hit:
    id: str
    index: str
    source: dict
    score: float = 0.0
    bm25_rank: int | None = None
    knn_rank: int | None = None
    bm25_score: float | None = None
    knn_score: float | None = None
    rrf_score: float = 0.0
    explain: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.source.items() if k != "vector"}
        return {"id": self.id, "index": self.index, "doc": d, "score": round(self.rrf_score or self.score, 5), "bm25_rank": self.bm25_rank, "knn_rank": self.knn_rank,
                "bm25_score": self.bm25_score, "knn_score": self.knn_score, "retrieval": self.explain}


def extract_ids(query: str) -> list[str]:
    return [m.upper() for m in ID_PATTERN.findall(query)]


class Backend:
    name = "abstract"
    vector_mode = "n/a"

    def available(self) -> bool: ...
    def ensure_indices(self, recreate: bool = False) -> None: ...
    def bulk_index(self, index: str, docs: list[dict]) -> int: ...
    def count(self, index: str) -> int: ...
    def lexical(self, index: str, query: str, filters: dict | None, size: int) -> list[Hit]: ...
    def knn(self, index: str, vector: list[float], filters: dict | None, size: int) -> list[Hit]: ...
    def get(self, index: str, doc_id: str) -> dict | None: ...
    def filter_only(self, index: str, filters: dict | None, size: int) -> list[Hit]: ...
    def health(self) -> dict: ...


def rrf_fuse(rank_lists: list[list[Hit]], k: int = RRF_K, size: int = 10, offset: int = 0) -> list[Hit]:
    """Reciprocal Rank Fusion: score = sum 1 / (k + rank) across ranked lists."""
    fused: dict[tuple[str, str], Hit] = {}
    for lst in rank_lists:
        for r, h in enumerate(lst, 1):
            key = (h.index, h.id)
            cur = fused.get(key)
            if cur is None:
                cur = Hit(id=h.id, index=h.index, source=h.source)
                fused[key] = cur
            cur.rrf_score += 1.0 / (k + r)
            if h.bm25_rank is not None:
                cur.bm25_rank, cur.bm25_score = h.bm25_rank, h.bm25_score
            if h.knn_rank is not None:
                cur.knn_rank, cur.knn_score = h.knn_rank, h.knn_score
    out = sorted(fused.values(), key=lambda h: -h.rrf_score)[offset:offset+size]
    for h in out:
        h.explain = {"method": "RRF(k=%d)" % k, "bm25_rank": h.bm25_rank, "knn_rank": h.knn_rank}
    return out


def hybrid_search(backend: Backend, index: str, query: str, vector: list[float] | None, filters: dict | None = None, size: int = 10, offset: int = 0, window: int = 100,
                  mode: str = "hybrid") -> list[Hit]:
    """BM25 + structured filters + vector/kNN fused with RRF. `mode` in {hybrid, bm25, knn}. Falls back to BM25 if kNN is unavailable."""
    lists: list[list[Hit]] = []
    if mode in ("hybrid", "bm25") and query.strip():
        lists.append(backend.lexical(index, query, filters, window))
    if mode in ("hybrid", "knn") and vector is not None:
        try:
            lists.append(backend.knn(index, vector, filters, window))
        except Exception:        # vector retrieval must never break the investigation workflow
            if not lists and query.strip():
                lists.append(backend.lexical(index, query, filters, window))
    if not lists:
        return backend.filter_only(index, filters, window)[offset:offset+size]
    if len(lists) == 1:
        for r, h in enumerate(lists[0], 1):
            h.rrf_score = 1.0 / (RRF_K + r)
            h.explain = {"method": "single-ranker", "bm25_rank": h.bm25_rank, "knn_rank": h.knn_rank}
        return lists[0][offset:offset+size]
    return rrf_fuse(lists, size=size, offset=offset)
