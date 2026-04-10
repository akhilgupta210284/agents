"""
Seed the eval OpenSearch indices with the golden corpus.

Key design decisions
--------------------
* NO Bedrock / AWS embedding calls — deterministic pseudo-random unit vectors
  are used for the KNN `vector` field.  This means semantic (KNN) retrieval
  scores will be noise, but BM25 lexical retrieval works correctly.
  The non-LLM RAGAS retrieval metrics only look at the text of returned
  chunks, not which retrieval path found them, so this is perfectly valid.

* Each corpus entry gets its own deterministic vector seeded from the
  corpus_id.  Repeated CI runs always produce the same vectors → repeatable
  evaluation results.

* Indices are created fresh on every eval run (recreate=True) so stale data
  from a previous run never contaminates the results.

Usage (standalone):
    python -m evals.seed_index
"""
from __future__ import annotations

import hashlib
import logging
import struct

from opensearchpy import OpenSearch

from evals.golden_dataset import CORPUS, CORPUS_BY_DOMAIN
from evals.os_client import EVAL_INDEX_MAP, get_eval_client
from config.settings import EMBED_DIMENSIONS

_log = logging.getLogger("medical-agent.eval.seed")

# ── Index mappings (mirrors production, but uses eval index names) ────────────
_INDEX_BODY = {
    "settings": {
        "index.knn": True,
        "number_of_shards": 1,
        "number_of_replicas": 0,          # single-node CI — no replicas needed
        "knn.algo_param.ef_search": 512,
    },
    "mappings": {
        "properties": {
            "vector": {
                "type": "knn_vector",
                "dimension": EMBED_DIMENSIONS,
                "method": {
                    "name": "hnsw",
                    "engine": "faiss",
                    "space_type": "l2",
                    "parameters": {"ef_construction": 128, "m": 16},
                },
            },
            "text":        {"type": "text", "analyzer": "english"},
            "domain":      {"type": "keyword"},
            "corpus_id":   {"type": "keyword"},
            "filename":    {"type": "keyword"},
            "chunk_index": {"type": "integer"},
            "total_chunks":{"type": "integer"},
        }
    },
}


def _deterministic_vector(corpus_id: str, dims: int = EMBED_DIMENSIONS) -> list[float]:
    """
    Produce a repeatable pseudo-random unit vector from a corpus_id string.

    Uses SHA-256 to generate deterministic bytes, converts to floats, then
    L2-normalises the result.  Guaranteed:
      - Same input  → same vector across runs
      - Different inputs → different vectors (with high probability)
      - No external dependencies (no Bedrock, no numpy)
    """
    digest = hashlib.sha256(corpus_id.encode()).digest()
    # Extend the digest by cycling until we have enough bytes for `dims` floats
    seed_bytes = bytearray()
    counter = 0
    while len(seed_bytes) < dims * 4:
        seed_bytes.extend(
            hashlib.sha256(digest + counter.to_bytes(4, "little")).digest()
        )
        counter += 1

    # Unpack as 32-bit signed ints then rescale to [-1, 1]
    raw = [
        struct.unpack_from("i", seed_bytes, i * 4)[0] / 2**31
        for i in range(dims)
    ]

    # L2 normalise
    magnitude = sum(x * x for x in raw) ** 0.5
    if magnitude == 0:
        return [1.0 / dims**0.5] * dims
    return [x / magnitude for x in raw]


def create_eval_indices(client: OpenSearch, recreate: bool = True) -> None:
    """Create (or recreate) all four eval OpenSearch indices."""
    for domain, index_name in EVAL_INDEX_MAP.items():
        if client.indices.exists(index=index_name):
            if recreate:
                _log.info("Dropping existing eval index '%s'", index_name)
                client.indices.delete(index=index_name)
            else:
                _log.info("Eval index '%s' already exists — skipping", index_name)
                continue
        client.indices.create(index=index_name, body=_INDEX_BODY)
        _log.info("Created eval index '%s'", index_name)


def seed_corpus(client: OpenSearch) -> int:
    """
    Index every golden corpus entry into its eval index.

    Returns the total number of documents indexed.
    """
    total = 0
    for entry in CORPUS:
        domain = entry["domain"]
        index_name = EVAL_INDEX_MAP[domain]
        vector = _deterministic_vector(entry["corpus_id"])

        doc = {
            "text":         entry["text"],
            "domain":       domain,
            "corpus_id":    entry["corpus_id"],
            "filename":     entry["filename"],
            "chunk_index":  0,
            "total_chunks": 1,
            "vector":       vector,
        }
        client.index(index=index_name, body=doc, refresh=False)
        total += 1
        _log.debug("Indexed %s → %s", entry["corpus_id"], index_name)

    # Flush all indices so documents are searchable immediately
    for index_name in EVAL_INDEX_MAP.values():
        client.indices.refresh(index=index_name)

    _log.info("Seeded %d golden corpus documents into eval indices", total)
    return total


def setup_eval_indices(client: OpenSearch | None = None) -> OpenSearch:
    """
    Convenience function: create indices + seed corpus in one call.

    Returns the OpenSearch client (useful when caller wants to reuse it).
    """
    if client is None:
        client = get_eval_client()
    create_eval_indices(client, recreate=True)
    seed_corpus(client)
    return client


def teardown_eval_indices(client: OpenSearch | None = None) -> None:
    """Delete all eval indices (called at the end of a CI run)."""
    if client is None:
        client = get_eval_client()
    for index_name in EVAL_INDEX_MAP.values():
        if client.indices.exists(index=index_name):
            client.indices.delete(index=index_name)
            _log.info("Deleted eval index '%s'", index_name)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = setup_eval_indices()
    print("Eval indices seeded successfully.")
