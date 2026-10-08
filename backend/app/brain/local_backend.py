"""In-process Second Brain used when Elasticsearch is unreachable. Same documents, same filters, same BM25 + kNN + RRF contract.
It exists so the investigation workflow never depends on Elasticsearch being up (and for offline demos / CI)."""
from __future__ import annotations

import json
import math
import re
import threading
from pathlib import Path

import numpy as np

from .. import config
from .base import ID_FIELDS, INDICES, TEXT_FIELDS, Backend, Hit, extract_ids
from .embedder import VECTOR_MODE

_TOK = re.compile(r"[a-z0-9]+")
K1, B = 1.2, 0.75


def _tokens(s: str) -> list[str]:
    return _TOK.findall(str(s).lower())


def _match(doc: dict, filters: dict | None) -> bool:
    for f, v in (filters or {}).items():
        if v is None:
            continue
        dv = doc.get(f)
        if isinstance(v, dict):
            if dv is None:
                return False
            if "gte" in v and str(dv) < str(v["gte"]):
                return False
            if "lte" in v and str(dv) > str(v["lte"]):
                return False
        else:
            vals = set(v) if isinstance(v, (list, tuple, set)) else {v}
            have = set(dv) if isinstance(dv, list) else {dv}
            if not (vals & have):
                return False
    return True


class LocalBackend(Backend):
    name = "local-fallback"
    vector_mode = VECTOR_MODE

    def __init__(self, directory: Path | None = None):
        self.dir = Path(directory or config.BRAIN_DIR)
        self.docs: dict[str, dict[str, dict]] = {ix: {} for ix in INDICES}
        self._bm: dict[str, dict] = {}
        self.lock = threading.Lock()
        self._load()

    def available(self) -> bool:
        return True

    def _load(self):
        for ix in INDICES:
            p = self.dir / f"{ix}.jsonl"
            if p.exists():
                for line in p.read_text().splitlines():
                    d = json.loads(line)
                    self.docs[ix][d["_id"]] = d
        self._bm.clear()

    def _persist(self, ix: str):
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / f"{ix}.jsonl").write_text("\n".join(json.dumps(d) for d in self.docs[ix].values()))

    def ensure_indices(self, recreate: bool = False) -> None:
        if recreate:
            self.docs = {ix: {} for ix in INDICES}
            self._bm.clear()
            for ix in INDICES:
                p = self.dir / f"{ix}.jsonl"
                if p.exists():
                    p.unlink()

    def bulk_index(self, index: str, docs: list[dict]) -> int:
        with self.lock:
            for d in docs:
                self.docs[index][d["_id"]] = d
            self._bm.pop(index, None)
            self._persist(index)
        return len(docs)

    def count(self, index: str) -> int:
        return len(self.docs[index])

    # ------------------------------------------------------------------ BM25
    def _stats(self, index: str) -> dict:
        if index in self._bm:
            return self._bm[index]
        fields = [f.split("^")[0] for f in TEXT_FIELDS[index]]
        boosts = {f.split("^")[0]: float(f.split("^")[1]) if "^" in f else 1.0 for f in TEXT_FIELDS[index]}
        toks, df, total = {}, {}, 0
        for did, d in self.docs[index].items():
            t = []
            for f in fields:
                v = d.get(f)
                if v:
                    t += _tokens(" ".join(v) if isinstance(v, list) else v)
            toks[did] = t
            total += len(t)
            for w in set(t):
                df[w] = df.get(w, 0) + 1
        n = max(len(toks), 1)
        st = {"toks": toks, "df": df, "avg": total / n, "n": n, "boosts": boosts}
        self._bm[index] = st
        return st

    def lexical(self, index: str, query: str, filters: dict | None, size: int) -> list[Hit]:
        st = self._stats(index)
        q = list(dict.fromkeys(_tokens(query)))
        ids = extract_ids(query)
        scored = []
        for did, d in self.docs[index].items():
            if not _match(d, filters):
                continue
            t = st["toks"][did]
            if not t and not ids:
                continue
            tf: dict[str, int] = {}
            for w in t:
                tf[w] = tf.get(w, 0) + 1
            s = 0.0
            for w in q:
                f = tf.get(w, 0)
                if f:
                    idf = math.log(1 + (st["n"] - st["df"].get(w, 0) + 0.5) / (st["df"].get(w, 0) + 0.5))
                    s += idf * f * (K1 + 1) / (f + K1 * (1 - B + B * len(t) / max(st["avg"], 1)))
            if ids:
                for f in ID_FIELDS[index]:
                    v = d.get(f)
                    vv = {x.upper() for x in (v if isinstance(v, list) else [v]) if x}
                    if vv & set(ids):
                        s += 12.0
            if s > 0:
                scored.append((s, did))
        scored.sort(key=lambda x: -x[0])
        return [Hit(id=did, index=index, source={k: v for k, v in self.docs[index][did].items() if k not in ("vector", "_id")}, score=s, bm25_rank=r, bm25_score=round(s, 4))
                for r, (s, did) in enumerate(scored[:size], 1)]

    def knn(self, index: str, vector: list[float], filters: dict | None, size: int) -> list[Hit]:
        cand = [(did, d) for did, d in self.docs[index].items() if d.get("vector") and _match(d, filters)]
        if not cand:
            return []
        M = np.array([d["vector"] for _, d in cand])
        q = np.array(vector)
        sims = M @ q / (np.linalg.norm(M, axis=1) * np.linalg.norm(q) + 1e-9)
        order = np.argsort(-sims)[:size]
        return [Hit(id=cand[i][0], index=index, source={k: v for k, v in cand[i][1].items() if k not in ("vector", "_id")}, score=float(sims[i]), knn_rank=r, knn_score=round(float(sims[i]), 4))
                for r, i in enumerate(order, 1)]

    def filter_only(self, index: str, filters: dict | None, size: int) -> list[Hit]:
        out = []
        for did, d in self.docs[index].items():
            if _match(d, filters):
                out.append(Hit(id=did, index=index, source={k: v for k, v in d.items() if k not in ("vector", "_id")}, score=0.0))
            if len(out) >= size:
                break
        return out

    def get(self, index: str, doc_id: str) -> dict | None:
        d = self.docs[index].get(doc_id)
        return {k: v for k, v in d.items() if k not in ("vector", "_id")} if d else None

    def health(self) -> dict:
        return {"backend": self.name, "directory": str(self.dir), "indices": {ix: self.count(ix) for ix in INDICES}, "vector_mode": self.vector_mode,
                "note": "Elasticsearch was not reachable; using the in-process fallback with identical BM25 + filters + kNN + RRF semantics."}
