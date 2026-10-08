# Nexus Second Brain - Elasticsearch

PostgreSQL stays the source of truth; Elasticsearch is the retrieval/memory layer rebuilt from it.

## Logical indices (1 shard, 0 replicas)
| Index | Documents | Key fields |
|---|---|---|
| `cases` | current cases + historical investigations (`kind`) | `case_id`, `investigation_id`, `provider_ids`, `specialty`, `patterns`, `rule_ids`, `severity`, `outcome`, `date`, `exposure`, text fields, `vector` |
| `evidence` | case evidence objects | `evidence_id`, `case_id`, `rule_id`, `claim_ids`, `provider_id`, `evidence_type`, `severity`, `text`, `vector` |
| `entities` | providers of interest (entity memory) | `entity_id`, `entity_type`, `specialty`, `region`, `profile`, `vector` |
| `patterns` | one document per FWA pattern/rule with historical support and typical outcomes (pattern memory) | `pattern_id`, `rule_ids`, `support`, `typical_outcomes`, `vector` |
| `review_memory` | human SIU decisions (reviewer memory) | `review_id`, `case_id`, `decision`, `rationale`, `patterns`, `vector` |

Mappings: `backend/app/brain/mappings.py`. `vector` is `dense_vector` (cosine, `index: true`).

## Retrieval flow
```
query -> BM25 multi_match (+ boosted exact-ID terms on case/provider/claim/rule/evidence IDs)
      + kNN on `vector`
      + structured filters (provider, specialty, severity, date range, pattern, outcome, entity type, kind)
      -> Reciprocal Rank Fusion (score = sum 1/(60+rank)) -> top-k -> Copilot / UI
```
RRF is applied client-side (`brain/base.py::rrf_fuse`) so behaviour does not depend on the Elasticsearch licence tier that gates the server-side `rrf` retriever. Every hit reports its BM25 rank, kNN rank and RRF score.

## Embeddings
No external model download is needed (offline-safe). Vectors concatenate a hashed word/bigram block with a structured FWA-signature block (rule IDs, shared-facility / coordination / escalation flags, specialty, outcome, scale), L2-normalised. This is a lightweight *pattern* embedding, not a learned language model; it is surfaced as `vector_mode` in `/api/brain/status`.

## Fallback (implemented and tested)
`SECOND_BRAIN_BACKEND=auto|elasticsearch|local`. With `auto`, if the cluster is unreachable the in-process `LocalBackend` serves the same documents with its own BM25, filters, cosine kNN and the same RRF; if kNN raises, hybrid search degrades to BM25 + filters. The UI shows which backend is active ("local fallback" badge). `elasticsearch` mode fails loudly instead of falling back.

## Operating it
```bash
python -m app.brain.indexer            # rebuild all indices from PostgreSQL
python scripts/verify_elasticsearch.py # live-cluster verification (exit 2 if unreachable)
curl localhost:8000/api/brain/status
```
## Verification status
Elasticsearch could **not** be started in the build sandbox (container registry and artifact hosts blocked). Verified there: the fallback end-to-end, plus offline tests of the ES request bodies and mappings. **Not yet verified live:** index creation, BM25/kNN/filter queries and bulk indexing against a real cluster - run `scripts/verify_elasticsearch.py` after `docker compose up`.
