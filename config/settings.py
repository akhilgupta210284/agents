"""
Central configuration loaded from environment / .env file.
All sensitive values (endpoints, bucket names) live in .env — never hard-coded.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── AWS ────────────────────────────────────────────────────────────────────
AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
AWS_PROFILE: str | None = os.getenv("AWS_PROFILE")

# ─── Bedrock ────────────────────────────────────────────────────────────────
BEDROCK_MODEL_ID: str = os.getenv(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
)
BEDROCK_EMBED_MODEL_ID: str = os.getenv(
    "BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0"
)
EMBED_DIMENSIONS: int = int(os.getenv("EMBED_DIMENSIONS", "1024"))

# ─── S3 ─────────────────────────────────────────────────────────────────────
S3_BUCKET: str = os.getenv("S3_BUCKET", "")
S3_PREFIXES: dict[str, str] = {
    "disease_study":  os.getenv("S3_PREFIX_DISEASE",   "medical-docs/disease-study/"),
    "medicine_study": os.getenv("S3_PREFIX_MEDICINE",  "medical-docs/medicine-study/"),
    "medicine_expiry":os.getenv("S3_PREFIX_EXPIRY",    "medical-docs/medicine-expiry/"),
    "equipment_study":os.getenv("S3_PREFIX_EQUIPMENT", "medical-docs/equipment-study/"),
}

# ─── OpenSearch ─────────────────────────────────────────────────────────────
OPENSEARCH_HOST: str    = os.getenv("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT: int    = int(os.getenv("OPENSEARCH_PORT", "9200"))
OPENSEARCH_USE_SSL: bool = os.getenv("OPENSEARCH_USE_SSL", "true").lower() == "true"
OPENSEARCH_SERVICE: str  = os.getenv("OPENSEARCH_SERVICE", "es")  # "aoss" for serverless

OPENSEARCH_INDICES: dict[str, str] = {
    "disease_study":  "medical-disease-study",
    "medicine_study": "medical-medicine-study",
    "medicine_expiry":"medical-medicine-expiry",
    "equipment_study":"medical-equipment-study",
}

# ─── Chunking ────────────────────────────────────────────────────────────────
CHUNK_SIZE: int    = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))

# ─── HIPAA / GDPR Compliance ─────────────────────────────────────────────────
AUDIT_LOG_BUCKET: str     = os.getenv("AUDIT_LOG_BUCKET", S3_BUCKET)
AUDIT_LOG_PREFIX: str     = os.getenv("AUDIT_LOG_PREFIX", "audit-logs/")
DATA_RETENTION_DAYS: int  = int(os.getenv("DATA_RETENTION_DAYS", "2555"))  # 7 yrs
