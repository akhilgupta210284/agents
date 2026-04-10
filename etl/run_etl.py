"""
ETL pipeline entry point.

Usage:
    # Index all domains
    python -m etl.run_etl

    # Index a single domain
    python -m etl.run_etl --domain disease_study

    # Re-create indices from scratch (⚠ deletes existing data)
    python -m etl.run_etl --recreate
"""
from __future__ import annotations

import argparse
import logging

from config.settings import S3_PREFIXES
from etl.document_processor import process_documents
from etl.opensearch_indexer import (
    create_all_indices,
    create_index,
    get_opensearch_client,
    index_chunks,
)
from etl.s3_reader import read_all_domains, read_domain_documents
from utils.logger import audit

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
_log = logging.getLogger("medical-agent.etl")


def run_domain(client, domain: str, recreate: bool = False) -> None:
    from config.settings import OPENSEARCH_INDICES
    _log.info("── ETL start: %s ──", domain)
    audit("ETL_RUN", user_id="system", domain=domain, extra={"phase": "start"})

    # 1. Read
    documents = read_domain_documents(domain)
    if not documents:
        _log.warning("No documents found for domain '%s' — skipping", domain)
        return

    # 2. Chunk
    chunks = process_documents(documents)

    # 3. Index (creates index if not present)
    create_index(client, OPENSEARCH_INDICES[domain], recreate=recreate)
    indexed = index_chunks(client, chunks, domain)

    audit(
        "ETL_RUN",
        user_id="system",
        domain=domain,
        extra={"phase": "complete", "docs": len(documents), "chunks": indexed},
    )
    _log.info("── ETL complete: %s — %d docs, %d chunks ──", domain, len(documents), indexed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Medical docs ETL pipeline")
    parser.add_argument("--domain", choices=list(S3_PREFIXES.keys()), default=None)
    parser.add_argument("--recreate", action="store_true",
                        help="Delete and re-create OpenSearch indices")
    args = parser.parse_args()

    client = get_opensearch_client()

    if args.domain:
        run_domain(client, args.domain, recreate=args.recreate)
    else:
        if args.recreate:
            create_all_indices(client, recreate=True)
        for domain in S3_PREFIXES:
            run_domain(client, domain, recreate=False)


if __name__ == "__main__":
    main()
