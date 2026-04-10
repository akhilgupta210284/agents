"""
OpenSearch indexer with hybrid search support.

Each domain gets its own index with:
  - A `text` field  →  BM25 lexical search (built-in)
  - A `vector` field → KNN semantic search (HNSW / Faiss)

Hybrid search at query time combines both scores with a weighted sum,
giving the best of keyword precision and semantic recall.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection, helpers

from config.settings import (
    AWS_REGION,
    BEDROCK_EMBED_MODEL_ID,
    EMBED_DIMENSIONS,
    OPENSEARCH_HOST,
    OPENSEARCH_INDICES,
    OPENSEARCH_PORT,
    OPENSEARCH_SERVICE,
    OPENSEARCH_USE_SSL,
)

_log = logging.getLogger("medical-agent.indexer")


# ─── Client factory ──────────────────────────────────────────────────────────

def get_opensearch_client() -> OpenSearch:
    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, AWS_REGION, OPENSEARCH_SERVICE)
    return OpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
        http_auth=auth,
        use_ssl=OPENSEARCH_USE_SSL,
        verify_certs=OPENSEARCH_USE_SSL,
        connection_class=RequestsHttpConnection,
        timeout=60,
    )


# ─── Bedrock embeddings ───────────────────────────────────────────────────────

def _embed(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a batch of texts using Amazon Bedrock Titan.
    Returns a list of float vectors, one per input text.
    """
    bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    vectors: list[list[float]] = []
    for text in texts:
        body = json.dumps({"inputText": text[:8192]})  # Titan token limit
        response = bedrock.invoke_model(
            modelId=BEDROCK_EMBED_MODEL_ID,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        vectors.append(result["embedding"])
    return vectors


# ─── Index management ────────────────────────────────────────────────────────

_INDEX_BODY: dict[str, Any] = {
    "settings": {
        "index.knn": True,
        "number_of_shards": 1,
        "number_of_replicas": 1,
        "knn.algo_param.ef_search": 512,
    },
    "mappings": {
        "properties": {
            # Semantic search field
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
            # Lexical (BM25) search field
            "text":      {"type": "text", "analyzer": "english"},
            # Metadata fields
            "domain":    {"type": "keyword"},
            "s3_key":    {"type": "keyword", "index": False},
            "filename":  {"type": "keyword"},
            "chunk_index":  {"type": "integer"},
            "total_chunks": {"type": "integer"},
        }
    },
}


def create_index(client: OpenSearch, index_name: str, recreate: bool = False) -> None:
    """Create an OpenSearch index with hybrid-search mappings."""
    if client.indices.exists(index=index_name):
        if recreate:
            _log.warning("Deleting existing index '%s'", index_name)
            client.indices.delete(index=index_name)
        else:
            _log.info("Index '%s' already exists — skipping creation", index_name)
            return
    client.indices.create(index=index_name, body=_INDEX_BODY)
    _log.info("Created index '%s'", index_name)


def create_all_indices(client: OpenSearch, recreate: bool = False) -> None:
    for index_name in OPENSEARCH_INDICES.values():
        create_index(client, index_name, recreate=recreate)


# ─── Bulk indexing ────────────────────────────────────────────────────────────

def index_chunks(
    client: OpenSearch,
    chunks: list[dict],
    domain: str,
    batch_size: int = 50,
) -> int:
    """
    Embed and index a list of chunks into the domain's OpenSearch index.

    Args:
        client:     Initialised OpenSearch client.
        chunks:     Output of document_processor.process_documents().
        domain:     One of the four document domains.
        batch_size: How many chunks to embed and index per API call.

    Returns:
        Total number of documents indexed.
    """
    index_name = OPENSEARCH_INDICES[domain]
    total_indexed = 0

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        texts = [c["text"] for c in batch]

        _log.info(
            "Embedding batch %d–%d for '%s'",
            start, start + len(batch) - 1, domain,
        )
        vectors = _embed(texts)

        actions = [
            {
                "_index": index_name,
                "_source": {**chunk, "vector": vector},
            }
            for chunk, vector in zip(batch, vectors)
        ]
        success, errors = helpers.bulk(client, actions, raise_on_error=False)
        if errors:
            _log.warning("Bulk index errors: %s", errors[:3])
        total_indexed += success

    _log.info("Indexed %d chunks into '%s'", total_indexed, index_name)
    return total_indexed
