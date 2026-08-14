"""Explicit, cost-safe bootstrap of normalized chunks into S3 Vectors."""

from __future__ import annotations

import argparse
import logging

from knowledge_intelligence.application.container import (
    build_ingestion_service,
    build_vector_ingestion_service,
)
from knowledge_intelligence.config import get_settings


def positive_integer(value: str) -> int:
    integer = int(value)
    if integer <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return integer


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest normalized chunks into S3 Vectors.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit-documents", type=positive_integer, default=None)
    parser.add_argument("--limit-chunks", type=positive_integer, default=None)
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()
    if not settings.vector_bucket_name:
        parser.error("KNOWLEDGE_INTELLIGENCE_VECTOR_BUCKET_NAME is required.")
    chunks = build_ingestion_service(settings).ingest_prefix(settings.s3_prefix)
    if arguments.limit_documents is not None:
        document_ids = tuple(dict.fromkeys(chunk.document_id for chunk in chunks))
        document_ids = document_ids[: arguments.limit_documents]
        chunks = tuple(chunk for chunk in chunks if chunk.document_id in document_ids)
    if arguments.limit_chunks is not None:
        chunks = chunks[: arguments.limit_chunks]
    service = build_vector_ingestion_service(settings)
    summary = service.ingest(chunks, dry_run=arguments.dry_run)
    logging.info(
        "chunks_processed=%s vectors_written=%s embedding_tokens=%s skipped_items=%s failures=%s",
        summary.chunks_processed,
        summary.vectors_written,
        summary.embedding_tokens,
        summary.skipped_items,
        summary.failures,
    )
    if summary.failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
