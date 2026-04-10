"""
S3 document reader.

Reads PDF (and plain-text) files from S3 for each of the four medical
document domains.  Returns a list of raw document dicts ready for chunking.
"""
from __future__ import annotations

import io
import logging
from typing import Iterator

import boto3
import pdfplumber

from config.settings import AWS_REGION, S3_BUCKET, S3_PREFIXES

_log = logging.getLogger("medical-agent.s3_reader")


def _list_objects(s3_client, prefix: str) -> Iterator[str]:
    """Yield every object key under *prefix* (handles pagination)."""
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            yield obj["Key"]


def _read_pdf(s3_client, key: str) -> str:
    """Download a PDF from S3 and extract its text."""
    response = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
    raw_bytes = response["Body"].read()
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def _read_text(s3_client, key: str) -> str:
    response = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
    return response["Body"].read().decode("utf-8", errors="replace")


def read_domain_documents(domain: str) -> list[dict]:
    """
    Load all documents for a given domain from S3.

    Args:
        domain: One of disease_study | medicine_study |
                medicine_expiry | equipment_study

    Returns:
        List of dicts, each with keys: domain, s3_key, filename, text
    """
    if domain not in S3_PREFIXES:
        raise ValueError(
            f"Unknown domain '{domain}'. Valid: {list(S3_PREFIXES.keys())}"
        )

    prefix = S3_PREFIXES[domain]
    s3 = boto3.client("s3", region_name=AWS_REGION)
    documents: list[dict] = []

    for key in _list_objects(s3, prefix):
        filename = key.split("/")[-1]
        if not filename:
            continue

        _log.info("Reading s3://%s/%s", S3_BUCKET, key)
        try:
            if key.lower().endswith(".pdf"):
                text = _read_pdf(s3, key)
            else:
                text = _read_text(s3, key)
        except Exception as exc:
            _log.warning("Failed to read %s: %s", key, exc)
            continue

        if text.strip():
            documents.append(
                {"domain": domain, "s3_key": key, "filename": filename, "text": text}
            )

    _log.info("Loaded %d documents for domain '%s'", len(documents), domain)
    return documents


def read_all_domains() -> dict[str, list[dict]]:
    """Read documents for all four domains."""
    return {domain: read_domain_documents(domain) for domain in S3_PREFIXES}
