"""
Evaluation-specific OpenSearch client factory.

Chooses auth strategy based on OPENSEARCH_USE_SSL:
  false (CI / local Docker)  → plain HTTP, no authentication
  true  (AWS managed domain) → AWS SigV4 via boto3 credentials

Also defines the eval index name convention so every other eval module
imports from one place.
"""
from __future__ import annotations

import os

from opensearchpy import OpenSearch, RequestsHttpConnection

# ── Eval index names (separate from production indices) ─────────────────────
# Pattern: "eval-<production-index-name>"
# Populated by seed_index.py; torn down after the eval run.
EVAL_INDEX_MAP: dict[str, str] = {
    "disease_study":   "eval-medical-disease-study",
    "medicine_study":  "eval-medical-medicine-study",
    "medicine_expiry": "eval-medical-medicine-expiry",
    "equipment_study": "eval-medical-equipment-study",
}


def get_eval_client() -> OpenSearch:
    """
    Return an OpenSearch client suitable for the current environment.

    CI (OPENSEARCH_USE_SSL=false):  plain HTTP to localhost / Docker service.
    AWS (OPENSEARCH_USE_SSL=true):  AWS SigV4 signed requests.
    """
    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    port = int(os.environ.get("OPENSEARCH_PORT", "9200"))
    use_ssl = os.environ.get("OPENSEARCH_USE_SSL", "false").lower() == "true"

    if use_ssl:
        import boto3
        from opensearchpy import AWSV4SignerAuth

        region = os.environ.get("AWS_REGION", "us-east-1")
        service = os.environ.get("OPENSEARCH_SERVICE", "es")
        credentials = boto3.Session().get_credentials()
        auth = AWSV4SignerAuth(credentials, region, service)
        return OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=60,
        )

    # Plain HTTP — CI / local Docker
    return OpenSearch(
        hosts=[{"host": host, "port": port}],
        use_ssl=False,
        verify_certs=False,
        connection_class=RequestsHttpConnection,
        timeout=30,
    )
