"""
Integration tests — full ETL pipeline (chunk → embed → index).

* Uses a real OpenSearch Docker instance (no auth).
* AWS Bedrock embedding is mocked to avoid needing real AWS credentials.
* S3 reads are mocked via moto so no real bucket is required.

Run:
    pytest tests/integration -m integration -v
"""
import os
import uuid
from unittest.mock import MagicMock, patch

import pytest
from opensearchpy import OpenSearch, helpers

pytestmark = pytest.mark.integration

# ── Sample document corpus ───────────────────────────────────────────────────

_MEDICINE_DOC = {
    "text": (
        "Penicillin was discovered by Alexander Fleming in 1928. "
        "It is a beta-lactam antibiotic used to treat a wide range of bacterial infections. "
        "Common side effects include rash, nausea, and diarrhoea. "
    ) * 25,  # ~225 words → multiple chunks
    "domain": "medicine_study",
    "s3_key": "medical-docs/medicine-study/penicillin.txt",
    "filename": "penicillin.txt",
}

_EQUIPMENT_DOC = {
    "text": (
        "The stethoscope is an acoustic medical device for auscultation. "
        "It must be calibrated every 12 months and cleaned after each patient contact. "
        "The device amplifies sounds from the heart, lungs, and intestines. "
    ) * 20,  # ~180 words → multiple chunks
    "domain": "equipment_study",
    "s3_key": "medical-docs/equipment-study/stethoscope.txt",
    "filename": "stethoscope.txt",
}


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def os_client():
    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    port = int(os.environ.get("OPENSEARCH_PORT", "9200"))
    client = OpenSearch(
        hosts=[{"host": host, "port": port}],
        use_ssl=False,
        verify_certs=False,
        timeout=30,
    )
    client.info()
    return client


@pytest.fixture
def temp_index(os_client):
    """Unique per-test index; always cleaned up afterwards."""
    from etl.opensearch_indexer import create_index
    name = f"test-etl-{uuid.uuid4().hex[:8]}"
    create_index(os_client, name)
    yield name
    if os_client.indices.exists(index=name):
        os_client.indices.delete(index=name)


# ── Helper ───────────────────────────────────────────────────────────────────

def _fake_embed(texts):
    """Return a deterministic fake vector for each text (no Bedrock call)."""
    return [[0.01 * (i % 100)] * 1024 for i, _ in enumerate(texts)]


# ── Tests ────────────────────────────────────────────────────────────────────

class TestChunkAndIndexPipeline:
    @patch("etl.opensearch_indexer._embed", side_effect=_fake_embed)
    def test_all_chunks_are_indexed(self, _mock_embed, os_client, temp_index):
        from etl.document_processor import process_documents
        from etl.opensearch_indexer import index_chunks
        from config.settings import OPENSEARCH_INDICES

        chunks = process_documents([_MEDICINE_DOC])
        assert len(chunks) > 1, "Expected multiple chunks from the sample document"

        test_map = dict(OPENSEARCH_INDICES, medicine_study=temp_index)
        with patch("etl.opensearch_indexer.OPENSEARCH_INDICES", test_map):
            indexed = index_chunks(os_client, chunks, "medicine_study")

        assert indexed == len(chunks)

        os_client.indices.refresh(index=temp_index)
        resp = os_client.search(index=temp_index, body={"query": {"match_all": {}}})
        assert resp["hits"]["total"]["value"] == len(chunks)

    @patch("etl.opensearch_indexer._embed", side_effect=_fake_embed)
    def test_chunk_metadata_persisted_correctly(self, _mock_embed, os_client, temp_index):
        from etl.document_processor import chunk_document
        from etl.opensearch_indexer import index_chunks
        from config.settings import OPENSEARCH_INDICES

        chunks = chunk_document(_EQUIPMENT_DOC, chunk_size=40, overlap=5)
        test_map = dict(OPENSEARCH_INDICES, equipment_study=temp_index)
        with patch("etl.opensearch_indexer.OPENSEARCH_INDICES", test_map):
            index_chunks(os_client, chunks, "equipment_study")

        os_client.indices.refresh(index=temp_index)
        resp = os_client.search(
            index=temp_index,
            body={"query": {"match_all": {}}, "_source": ["filename", "domain", "chunk_index"]},
            size=1,
        )
        src = resp["hits"]["hits"][0]["_source"]
        assert src["filename"] == "stethoscope.txt"
        assert src["domain"] == "equipment_study"
        assert isinstance(src["chunk_index"], int)

    @patch("etl.opensearch_indexer._embed", side_effect=_fake_embed)
    def test_phi_fields_not_present_in_indexed_docs(self, _mock_embed, os_client, temp_index):
        from etl.document_processor import chunk_document
        from etl.opensearch_indexer import index_chunks
        from config.settings import OPENSEARCH_INDICES

        doc_with_phi = {**_MEDICINE_DOC, "patient_id": "P-999", "mrn": "MRN-123", "ssn": "000-11-2222"}
        chunks = chunk_document(doc_with_phi, chunk_size=50, overlap=5)
        test_map = dict(OPENSEARCH_INDICES, medicine_study=temp_index)
        with patch("etl.opensearch_indexer.OPENSEARCH_INDICES", test_map):
            index_chunks(os_client, chunks, "medicine_study")

        os_client.indices.refresh(index=temp_index)
        resp = os_client.search(index=temp_index, body={"query": {"match_all": {}}})
        for hit in resp["hits"]["hits"]:
            src = hit["_source"]
            assert "patient_id" not in src
            assert "mrn" not in src
            assert "ssn" not in src

    @patch("etl.opensearch_indexer._embed", side_effect=_fake_embed)
    def test_lexical_search_finds_indexed_content(self, _mock_embed, os_client, temp_index):
        from etl.document_processor import process_documents
        from etl.opensearch_indexer import index_chunks
        from config.settings import OPENSEARCH_INDICES

        chunks = process_documents([_MEDICINE_DOC])
        test_map = dict(OPENSEARCH_INDICES, medicine_study=temp_index)
        with patch("etl.opensearch_indexer.OPENSEARCH_INDICES", test_map):
            index_chunks(os_client, chunks, "medicine_study")

        os_client.indices.refresh(index=temp_index)
        resp = os_client.search(
            index=temp_index,
            body={"query": {"multi_match": {"query": "penicillin antibiotic", "fields": ["text"]}}},
        )
        assert resp["hits"]["total"]["value"] > 0
        filenames = [h["_source"]["filename"] for h in resp["hits"]["hits"]]
        assert "penicillin.txt" in filenames

    @patch("etl.opensearch_indexer._embed", side_effect=_fake_embed)
    def test_batch_size_does_not_affect_total_indexed(self, _mock_embed, os_client, temp_index):
        """Verify that varying batch_size still indexes the same total documents."""
        from etl.document_processor import process_documents
        from etl.opensearch_indexer import index_chunks, create_index
        from config.settings import OPENSEARCH_INDICES

        chunks = process_documents([_MEDICINE_DOC])

        index_b1 = f"test-batch1-{uuid.uuid4().hex[:6]}"
        index_b10 = f"test-batch10-{uuid.uuid4().hex[:6]}"
        create_index(os_client, index_b1)
        create_index(os_client, index_b10)

        try:
            map_b1 = dict(OPENSEARCH_INDICES, medicine_study=index_b1)
            map_b10 = dict(OPENSEARCH_INDICES, medicine_study=index_b10)

            with patch("etl.opensearch_indexer.OPENSEARCH_INDICES", map_b1):
                count_b1 = index_chunks(os_client, chunks, "medicine_study", batch_size=1)
            with patch("etl.opensearch_indexer.OPENSEARCH_INDICES", map_b10):
                count_b10 = index_chunks(os_client, chunks, "medicine_study", batch_size=10)

            assert count_b1 == count_b10 == len(chunks)
        finally:
            for idx in (index_b1, index_b10):
                if os_client.indices.exists(index=idx):
                    os_client.indices.delete(index=idx)


class TestS3ReaderIntegration:
    """Test S3 reader with moto — no real S3 required."""

    @pytest.fixture(autouse=True)
    def _mock_s3(self):
        """Set up a fake S3 bucket via moto."""
        import boto3
        from moto import mock_aws

        with mock_aws():
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket="test-bucket")

            # Upload a sample text file to the disease domain prefix
            s3.put_object(
                Bucket="test-bucket",
                Key="medical-docs/disease-study/fever_report.txt",
                Body=b"Fever is defined as a body temperature above 38 degrees Celsius. "
                     b"It is commonly caused by infections, inflammatory conditions, or heat stroke. " * 20,
            )
            yield

    def test_read_domain_documents_returns_correct_fields(self):
        from etl.s3_reader import read_domain_documents
        with patch("etl.s3_reader.S3_BUCKET", "test-bucket"), \
             patch("etl.s3_reader.S3_PREFIXES", {"disease_study": "medical-docs/disease-study/"}):
            docs = read_domain_documents("disease_study")

        assert len(docs) == 1
        doc = docs[0]
        assert doc["domain"] == "disease_study"
        assert doc["filename"] == "fever_report.txt"
        assert "Fever" in doc["text"]
        assert "s3_key" in doc

    def test_read_domain_documents_raises_for_unknown_domain(self):
        from etl.s3_reader import read_domain_documents
        import pytest
        with pytest.raises(ValueError, match="Unknown domain"):
            read_domain_documents("nonexistent_domain")

    def test_empty_prefix_returns_no_documents(self):
        from etl.s3_reader import read_domain_documents
        with patch("etl.s3_reader.S3_BUCKET", "test-bucket"), \
             patch("etl.s3_reader.S3_PREFIXES", {"disease_study": "medical-docs/empty-prefix/"}):
            docs = read_domain_documents("disease_study")
        assert docs == []
