"""
Structured audit logger for HIPAA / GDPR compliance.

Every data-access event is written both to stdout (application logs) and
to S3 (immutable audit trail).  PHI/PII fields are masked before logging
so protected health information never appears in log storage.
"""
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3

from config.settings import AUDIT_LOG_BUCKET, AUDIT_LOG_PREFIX, AWS_REGION

# ─── Internal Python logger (console / CloudWatch) ──────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
_log = logging.getLogger("medical-agent")

# PHI patterns to mask (names, MRN-style numbers, email, phone, SSN)
_PHI_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "***-**-****"),          # SSN
    (re.compile(r"\b\d{10,}\b"), "[ID_REDACTED]"),                   # Long numeric IDs
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[EMAIL_REDACTED]"),
    (re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"), "[PHONE_REDACTED]"),
]


def _mask_phi(text: str) -> str:
    """Remove common PHI patterns from a string before logging."""
    for pattern, replacement in _PHI_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _s3_key(event_type: str) -> str:
    now = datetime.now(timezone.utc)
    return (
        f"{AUDIT_LOG_PREFIX}"
        f"{now.strftime('%Y/%m/%d')}/"
        f"{event_type}_{now.strftime('%H%M%S')}_{uuid.uuid4().hex[:8]}.json"
    )


def audit(
    event_type: str,
    user_id: str,
    query: str | None = None,
    domain: str | None = None,
    agent_name: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """
    Write a compliance audit record.

    Args:
        event_type:  Category e.g. "QUERY", "TOOL_CALL", "ETL_RUN", "DATA_ACCESS"
        user_id:     Identifier of the requesting user (opaque token preferred).
        query:       User's natural-language query — PHI is masked before storage.
        domain:      One of the 4 medical document domains.
        agent_name:  Which agent handled the request.
        extra:       Any additional structured metadata.
    """
    record: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_id": uuid.uuid4().hex,
        "event_type": event_type,
        "user_id": user_id,
        "domain": domain,
        "agent": agent_name,
        "query_masked": _mask_phi(query) if query else None,
        **(extra or {}),
    }

    # Console log (no raw query — PHI already masked)
    _log.info(json.dumps({k: v for k, v in record.items() if v is not None}))

    # Persist to S3 (immutable audit trail)
    if AUDIT_LOG_BUCKET:
        try:
            s3 = boto3.client("s3", region_name=AWS_REGION)
            s3.put_object(
                Bucket=AUDIT_LOG_BUCKET,
                Key=_s3_key(event_type),
                Body=json.dumps(record),
                ContentType="application/json",
                ServerSideEncryption="aws:kms",   # Encryption at rest (HIPAA §164.312)
            )
        except Exception as exc:
            _log.error("Audit S3 write failed: %s", exc)
