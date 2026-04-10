"""
Hybrid search Strands tools.

Each tool performs a hybrid search combining:
  1. BM25 lexical  – exact keyword matching (high precision)
  2. KNN semantic  – vector similarity (high recall)

Results are merged via Reciprocal Rank Fusion (RRF) so the combined list
outperforms either search method alone.
"""
from __future__ import annotations

import json
import logging

import boto3
from strands import tool

from config.settings import (
    AWS_REGION,
    BEDROCK_EMBED_MODEL_ID,
    OPENSEARCH_INDICES,
)
from etl.opensearch_indexer import get_opensearch_client

_log = logging.getLogger("medical-agent.search")


def _embed_query(text: str) -> list[float]:
    bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    body = json.dumps({"inputText": text[:8192]})
    response = bedrock.invoke_model(
        modelId=BEDROCK_EMBED_MODEL_ID,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(response["body"].read())["embedding"]


def _rrf_merge(lexical_hits: list, semantic_hits: list, k: int = 60) -> list[dict]:
    """
    Reciprocal Rank Fusion: merges two ranked lists into one.
    k=60 is the standard RRF constant that penalises low-ranked docs.
    """
    scores: dict[str, float] = {}
    sources: dict[str, dict] = {}

    for rank, hit in enumerate(lexical_hits):
        doc_id = hit["_id"]
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
        sources[doc_id] = hit["_source"]

    for rank, hit in enumerate(semantic_hits):
        doc_id = hit["_id"]
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
        sources[doc_id] = hit["_source"]

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [{"id": doc_id, "score": score, **sources[doc_id]} for doc_id, score in ranked]


def _hybrid_search(domain: str, query: str, top_k: int = 5) -> str:
    """Core hybrid search logic shared by all domain tools."""
    index_name = OPENSEARCH_INDICES.get(domain)
    if not index_name:
        return f"Unknown domain: {domain}"

    client = get_opensearch_client()
    query_vector = _embed_query(query)

    # ── BM25 lexical search ───────────────────────────────────────────────────
    lexical_body = {
        "size": top_k,
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["text"],
                "type": "best_fields",
            }
        },
        "_source": ["text", "filename", "domain", "chunk_index"],
    }
    lexical_resp = client.search(index=index_name, body=lexical_body)
    lexical_hits = lexical_resp["hits"]["hits"]

    # ── KNN semantic search ───────────────────────────────────────────────────
    semantic_body = {
        "size": top_k,
        "query": {
            "knn": {
                "vector": {
                    "vector": query_vector,
                    "k": top_k,
                }
            }
        },
        "_source": ["text", "filename", "domain", "chunk_index"],
    }
    semantic_resp = client.search(index=index_name, body=semantic_body)
    semantic_hits = semantic_resp["hits"]["hits"]

    # ── Merge via RRF ─────────────────────────────────────────────────────────
    merged = _rrf_merge(lexical_hits, semantic_hits)[:top_k]

    if not merged:
        return "No relevant documents found."

    parts = [
        f"[Source: {hit.get('filename', 'unknown')} | chunk {hit.get('chunk_index', '?')}]\n"
        f"{hit.get('text', '')}"
        for hit in merged
    ]
    return "\n\n---\n\n".join(parts)


# ─── Per-domain Strands tools ─────────────────────────────────────────────────

@tool
def search_disease_study(query: str, top_k: int = 5) -> str:
    """
    Hybrid search over the Disease Study document corpus.

    Args:
        query: Natural-language search query related to diseases, symptoms,
               clinical trials, or epidemiology.
        top_k: Maximum number of passages to return (default 5).

    Returns:
        Relevant text passages with source file references.
    """
    return _hybrid_search("disease_study", query, top_k)


@tool
def search_medicine_study(query: str, top_k: int = 5) -> str:
    """
    Hybrid search over the Medicine Study document corpus.

    Args:
        query: Query about drug interactions, pharmacology, dosage, or
               clinical medicine research.
        top_k: Maximum number of passages to return (default 5).

    Returns:
        Relevant text passages with source file references.
    """
    return _hybrid_search("medicine_study", query, top_k)


@tool
def search_medicine_expiry(query: str, top_k: int = 5) -> str:
    """
    Hybrid search over the Medicine Expiry Study corpus.

    Args:
        query: Query about drug shelf-life, expiry dates, stability testing,
               or storage conditions.
        top_k: Maximum number of passages to return (default 5).

    Returns:
        Relevant text passages with source file references.
    """
    return _hybrid_search("medicine_expiry", query, top_k)


@tool
def search_equipment_study(query: str, top_k: int = 5) -> str:
    """
    Hybrid search over the Equipment Study document corpus.

    Args:
        query: Query about medical devices, calibration, maintenance,
               or equipment safety standards.
        top_k: Maximum number of passages to return (default 5).

    Returns:
        Relevant text passages with source file references.
    """
    return _hybrid_search("equipment_study", query, top_k)


# Convenience list used by agents that need all four search tools
ALL_SEARCH_TOOLS = [
    search_disease_study,
    search_medicine_study,
    search_medicine_expiry,
    search_equipment_study,
]
