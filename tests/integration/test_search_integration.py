"""
Integration tests — OpenSearch index management and lexical search.

Requirements
------------
* OpenSearch running and reachable (default: localhost:9200, no auth).
  In CI this is provided as a Docker service (see .github/workflows/ci.yml).
  Locally: `docker compose up -d opensearch`

* Environment variables:
    OPENSEARCH_HOST  (default: localhost)
    OPENSEARCH_PORT  (default: 9200)
    OPENSEARCH_USE_SSL (default: false)

Run only integration tests:
    pytest tests/integration -m integration -v
"""
import os

import pytest
from opensearchpy import OpenSearch, helpers

pytestmark = pytest.mark.integration


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def os_client():
    """Plain (no-auth) OpenSearch client for the Docker test instance."""
    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    port = int(os.environ.get("OPENSEARCH_PORT", "9200"))
    client = OpenSearch(
        hosts=[{"host": host, "port": port}],
        use_ssl=False,
        verify_certs=False,
        timeout=30,
    )
    info = client.info()
    assert "cluster_name" in info, "OpenSearch cluster not reachable"
    return client


@pytest.fixture(scope="module")
def search_index(os_client):
    """Create a test index once per module; delete it after all tests run."""
    from etl.opensearch_indexer import create_index

    index_name = "test-search-integration"
    if os_client.indices.exists(index=index_name):
        os_client.indices.delete(index=index_name)
    create_index(os_client, index_name)
    yield index_name
    if os_client.indices.exists(index=index_name):
        os_client.indices.delete(index=index_name)


@pytest.fixture(scope="module")
def seeded_index(os_client, search_index):
    """Index sample documents and refresh before returning the index name."""
    docs = [
        {
            "_index": search_index,
            "_source": {
                "text": "Aspirin is a common analgesic used to treat fever and mild pain.",
                "filename": "aspirin_study.pdf",
                "domain": "medicine_study",
                "chunk_index": 0,
                "total_chunks": 1,
                "vector": [0.1] * 1024,
            },
        },
        {
            "_index": search_index,
            "_source": {
                "text": "Diabetes mellitus type 2 is a chronic metabolic disease characterised by hyperglycaemia.",
                "filename": "diabetes_overview.pdf",
                "domain": "disease_study",
                "chunk_index": 0,
                "total_chunks": 1,
                "vector": [0.2] * 1024,
            },
        },
        {
            "_index": search_index,
            "_source": {
                "text": "The stethoscope must be calibrated every 12 months according to ISO standards.",
                "filename": "stethoscope_maintenance.pdf",
                "domain": "equipment_study",
                "chunk_index": 0,
                "total_chunks": 1,
                "vector": [0.3] * 1024,
            },
        },
    ]
    helpers.bulk(os_client, docs)
    os_client.indices.refresh(index=search_index)
    return search_index


# ─── Index management ─────────────────────────────────────────────────────────

class TestIndexCreation:
    def test_index_exists_after_creation(self, os_client, search_index):
        assert os_client.indices.exists(index=search_index)

    def test_vector_field_is_knn_vector(self, os_client, search_index):
        mapping = os_client.indices.get_mapping(index=search_index)
        props = mapping[search_index]["mappings"]["properties"]
        assert props["vector"]["type"] == "knn_vector"
        assert props["vector"]["dimension"] == 1024

    def test_text_field_is_text_type(self, os_client, search_index):
        mapping = os_client.indices.get_mapping(index=search_index)
        props = mapping[search_index]["mappings"]["properties"]
        assert props["text"]["type"] == "text"

    def test_metadata_keyword_fields_present(self, os_client, search_index):
        mapping = os_client.indices.get_mapping(index=search_index)
        props = mapping[search_index]["mappings"]["properties"]
        for field in ("domain", "filename"):
            assert props[field]["type"] == "keyword"

    def test_create_index_idempotent_when_already_exists(self, os_client, search_index):
        from etl.opensearch_indexer import create_index
        # Calling create_index on an existing index without recreate must not raise
        create_index(os_client, search_index, recreate=False)
        assert os_client.indices.exists(index=search_index)

    def test_create_index_with_recreate_replaces_index(self, os_client):
        from etl.opensearch_indexer import create_index
        temp_index = "test-recreate-temp"
        try:
            create_index(os_client, temp_index)
            assert os_client.indices.exists(index=temp_index)
            create_index(os_client, temp_index, recreate=True)
            assert os_client.indices.exists(index=temp_index)
        finally:
            if os_client.indices.exists(index=temp_index):
                os_client.indices.delete(index=temp_index)


# ─── Lexical (BM25) search ────────────────────────────────────────────────────

class TestLexicalSearch:
    def test_finds_aspirin_document(self, os_client, seeded_index):
        body = {
            "query": {"multi_match": {"query": "aspirin fever", "fields": ["text"]}}
        }
        resp = os_client.search(index=seeded_index, body=body)
        filenames = [h["_source"]["filename"] for h in resp["hits"]["hits"]]
        assert "aspirin_study.pdf" in filenames

    def test_finds_diabetes_document(self, os_client, seeded_index):
        body = {
            "query": {"multi_match": {"query": "diabetes hyperglycaemia", "fields": ["text"]}}
        }
        resp = os_client.search(index=seeded_index, body=body)
        filenames = [h["_source"]["filename"] for h in resp["hits"]["hits"]]
        assert "diabetes_overview.pdf" in filenames

    def test_returns_no_results_for_unrelated_term(self, os_client, seeded_index):
        body = {
            "query": {"multi_match": {"query": "xyzzy_nonexistent_xyz", "fields": ["text"]}}
        }
        resp = os_client.search(index=seeded_index, body=body)
        assert resp["hits"]["total"]["value"] == 0

    def test_size_parameter_limits_returned_hits(self, os_client, seeded_index):
        body = {
            "size": 1,
            "query": {"match_all": {}},
        }
        resp = os_client.search(index=seeded_index, body=body)
        assert len(resp["hits"]["hits"]) == 1

    def test_source_fields_present_in_hit(self, os_client, seeded_index):
        body = {"query": {"multi_match": {"query": "calibration stethoscope", "fields": ["text"]}}}
        resp = os_client.search(index=seeded_index, body=body)
        assert len(resp["hits"]["hits"]) > 0
        src = resp["hits"]["hits"][0]["_source"]
        for field in ("text", "filename", "domain", "chunk_index"):
            assert field in src


# ─── create_all_indices ───────────────────────────────────────────────────────

class TestCreateAllIndices:
    def test_all_four_domain_indices_created(self, os_client):
        from etl.opensearch_indexer import create_all_indices
        from unittest.mock import patch

        # Redirect to test-prefixed names so we don't clobber real indices
        from config.settings import OPENSEARCH_INDICES
        test_map = {k: f"test-all-{v}" for k, v in OPENSEARCH_INDICES.items()}

        with patch("etl.opensearch_indexer.OPENSEARCH_INDICES", test_map):
            create_all_indices(os_client)

        try:
            for name in test_map.values():
                assert os_client.indices.exists(index=name)
        finally:
            for name in test_map.values():
                if os_client.indices.exists(index=name):
                    os_client.indices.delete(index=name)
