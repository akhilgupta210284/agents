"""Unit tests for config/settings.py"""
from config.settings import (
    BEDROCK_EMBED_MODEL_ID,
    BEDROCK_MODEL_ID,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DATA_RETENTION_DAYS,
    EMBED_DIMENSIONS,
    OPENSEARCH_INDICES,
    OPENSEARCH_PORT,
    S3_PREFIXES,
)


class TestOpensearchIndices:
    EXPECTED_DOMAINS = {"disease_study", "medicine_study", "medicine_expiry", "equipment_study"}

    def test_all_four_domains_present(self):
        assert set(OPENSEARCH_INDICES.keys()) == self.EXPECTED_DOMAINS

    def test_index_names_are_strings(self):
        for name in OPENSEARCH_INDICES.values():
            assert isinstance(name, str) and len(name) > 0

    def test_index_names_are_unique(self):
        names = list(OPENSEARCH_INDICES.values())
        assert len(names) == len(set(names))


class TestS3Prefixes:
    EXPECTED_DOMAINS = {"disease_study", "medicine_study", "medicine_expiry", "equipment_study"}

    def test_all_four_domains_present(self):
        assert set(S3_PREFIXES.keys()) == self.EXPECTED_DOMAINS

    def test_prefixes_end_with_slash(self):
        for prefix in S3_PREFIXES.values():
            assert prefix.endswith("/"), f"Prefix '{prefix}' should end with '/'"


class TestChunkingConfig:
    def test_chunk_size_is_positive_integer(self):
        assert isinstance(CHUNK_SIZE, int)
        assert CHUNK_SIZE > 0

    def test_chunk_overlap_is_non_negative_integer(self):
        assert isinstance(CHUNK_OVERLAP, int)
        assert CHUNK_OVERLAP >= 0

    def test_overlap_smaller_than_chunk_size(self):
        assert CHUNK_OVERLAP < CHUNK_SIZE


class TestBedrockConfig:
    def test_model_id_is_non_empty_string(self):
        assert isinstance(BEDROCK_MODEL_ID, str) and len(BEDROCK_MODEL_ID) > 0

    def test_embed_model_id_is_non_empty_string(self):
        assert isinstance(BEDROCK_EMBED_MODEL_ID, str) and len(BEDROCK_EMBED_MODEL_ID) > 0

    def test_embed_dimensions_is_positive_integer(self):
        assert isinstance(EMBED_DIMENSIONS, int)
        assert EMBED_DIMENSIONS > 0


class TestComplianceConfig:
    def test_data_retention_meets_hipaa_minimum(self):
        # HIPAA requires 6 years (2190 days); standard is 7 years (2555 days)
        assert DATA_RETENTION_DAYS >= 2190

    def test_opensearch_port_is_valid(self):
        assert isinstance(OPENSEARCH_PORT, int)
        assert 1 <= OPENSEARCH_PORT <= 65535
