"""
Shared pytest configuration.

Environment variables are set here (before any application modules are
imported) so that config/settings.py reads safe test defaults instead of
requiring a real .env file or AWS environment.
"""
import os

# ── Set safe test defaults BEFORE any app module is imported ─────────────────
# load_dotenv() in settings.py will NOT override values already in os.environ,
# so these defaults win even if the developer has a .env file locally.
_TEST_DEFAULTS = {
    "AWS_REGION": "us-east-1",
    "BEDROCK_MODEL_ID": "test-model-id",
    "BEDROCK_EMBED_MODEL_ID": "test-embed-model",
    "EMBED_DIMENSIONS": "1024",
    "S3_BUCKET": "test-bucket",
    "S3_PREFIX_DISEASE": "medical-docs/disease-study/",
    "S3_PREFIX_MEDICINE": "medical-docs/medicine-study/",
    "S3_PREFIX_EXPIRY": "medical-docs/medicine-expiry/",
    "S3_PREFIX_EQUIPMENT": "medical-docs/equipment-study/",
    "OPENSEARCH_HOST": "localhost",
    "OPENSEARCH_PORT": "9200",
    "OPENSEARCH_USE_SSL": "false",
    "OPENSEARCH_SERVICE": "es",
    "CHUNK_SIZE": "512",
    "CHUNK_OVERLAP": "50",
    "AUDIT_LOG_BUCKET": "",        # disables real S3 writes in unit tests
    "AUDIT_LOG_PREFIX": "audit-logs/",
    "DATA_RETENTION_DAYS": "2555",
}

for _key, _val in _TEST_DEFAULTS.items():
    os.environ.setdefault(_key, _val)
