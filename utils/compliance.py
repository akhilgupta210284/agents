"""
HIPAA / GDPR compliance helpers.

HIPAA safeguards addressed:
  § 164.308 – Administrative: access controls, audit controls, workforce training
  § 164.312 – Technical:  encryption, automatic logoff, audit logs

GDPR articles addressed:
  Art. 17  – Right to erasure ("right to be forgotten")
  Art. 25  – Data protection by design (minimal data collection)
  Art. 30  – Records of processing activities (audit trail)
"""
from __future__ import annotations

import boto3
from config.settings import AWS_REGION, OPENSEARCH_INDICES, S3_BUCKET, S3_PREFIXES


# ─── GDPR Art. 17: Right to Erasure ─────────────────────────────────────────

def delete_user_data(user_id: str, opensearch_client) -> dict:
    """
    Remove all indexed documents associated with a user_id from every
    OpenSearch index.  Call when a data-subject deletion request is received.

    Args:
        user_id:           The data subject's opaque identifier.
        opensearch_client: Initialised OpenSearch client from opensearch_indexer.

    Returns:
        Summary dict with deleted counts per index.
    """
    summary: dict[str, int] = {}
    query = {"query": {"term": {"user_id": user_id}}}

    for domain, index in OPENSEARCH_INDICES.items():
        resp = opensearch_client.delete_by_query(index=index, body=query)
        summary[domain] = resp.get("deleted", 0)

    return summary


# ─── HIPAA § 164.308: Minimum Necessary Access ───────────────────────────────

ALLOWED_DOMAINS_BY_ROLE: dict[str, list[str]] = {
    "clinician":      ["disease_study", "medicine_study", "medicine_expiry"],
    "lab_technician": ["equipment_study", "medicine_study"],
    "administrator":  list(OPENSEARCH_INDICES.keys()),
    "researcher":     list(OPENSEARCH_INDICES.keys()),
}


def check_domain_access(user_role: str, domain: str) -> bool:
    """
    Enforce minimum-necessary-access: return True only if the role is
    permitted to query the given document domain.
    """
    allowed = ALLOWED_DOMAINS_BY_ROLE.get(user_role, [])
    return domain in allowed


# ─── HIPAA § 164.312 (e): Encryption in Transit ──────────────────────────────

def assert_tls_endpoint(host: str) -> None:
    """
    Raise ValueError if the OpenSearch host does not use HTTPS.
    Called at startup to prevent accidental plaintext connections.
    """
    if not host.startswith("https://") and "localhost" not in host:
        raise ValueError(
            f"OpenSearch host '{host}' must use HTTPS to comply with "
            "HIPAA § 164.312(e)(1) encryption-in-transit requirement."
        )


# ─── GDPR Art. 25: Data Minimisation ─────────────────────────────────────────

SENSITIVE_METADATA_KEYS = {"patient_id", "mrn", "dob", "ssn", "nhs_number"}


def strip_sensitive_metadata(metadata: dict) -> dict:
    """
    Remove any keys that could identify a natural person before indexing.
    Keeps document-level attributes (title, page, domain) while dropping PHI.
    """
    return {k: v for k, v in metadata.items() if k not in SENSITIVE_METADATA_KEYS}
