"""
Document chunker.

Splits raw document text into overlapping windows suitable for embedding.
Metadata (domain, source file, page range) is preserved on every chunk so
that citations can be surfaced to end-users.
"""
from __future__ import annotations

import logging

from config.settings import CHUNK_OVERLAP, CHUNK_SIZE
from utils.compliance import strip_sensitive_metadata

_log = logging.getLogger("medical-agent.processor")


def _split_words(text: str, size: int, overlap: int) -> list[str]:
    """Simple word-level sliding-window chunker."""
    words = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start + size
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start += size - overlap
    return chunks


def chunk_document(doc: dict, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """
    Split one raw document dict into a list of chunk dicts.

    Each chunk dict contains:
      - text        : chunk content
      - domain      : original domain
      - s3_key      : source S3 key
      - filename    : source filename
      - chunk_index : 0-based position within the document
      - total_chunks: total number of chunks in the document

    Args:
        doc:        Raw document dict from s3_reader (must have 'text' key).
        chunk_size: Number of words per chunk.
        overlap:    Overlapping words between consecutive chunks.

    Returns:
        List of chunk dicts.
    """
    raw_chunks = _split_words(doc["text"], chunk_size, overlap)
    total = len(raw_chunks)

    base_metadata = {
        "domain":   doc.get("domain"),
        "s3_key":   doc.get("s3_key"),
        "filename": doc.get("filename"),
    }
    # GDPR Art. 25: strip any accidental PHI keys from document metadata
    base_metadata = strip_sensitive_metadata(base_metadata)

    chunks: list[dict] = []
    for idx, chunk_text in enumerate(raw_chunks):
        if not chunk_text.strip():
            continue
        chunks.append(
            {
                "text": chunk_text,
                "chunk_index": idx,
                "total_chunks": total,
                **base_metadata,
            }
        )

    _log.debug(
        "Chunked '%s' → %d chunks (size=%d, overlap=%d)",
        doc.get("filename"), len(chunks), chunk_size, overlap,
    )
    return chunks


def process_documents(documents: list[dict]) -> list[dict]:
    """Chunk an entire list of raw documents."""
    all_chunks: list[dict] = []
    for doc in documents:
        all_chunks.extend(chunk_document(doc))
    _log.info("Total chunks produced: %d", len(all_chunks))
    return all_chunks
