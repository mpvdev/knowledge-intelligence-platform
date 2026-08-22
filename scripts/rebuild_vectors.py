#!/usr/bin/env python3
"""Rebuild the vector index from the chunks already persisted in S3.

Use this after the vector bucket or index has been recreated. It re-embeds the
stored chunks instead of re-parsing the source documents, so it costs embedding
calls only — no PDF parsing and no visual analysis.

    python scripts/rebuild_vectors.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.ingestion import _embedding_text  # noqa: E402
from app.main import build_application, configure_logging  # noqa: E402

LOGGER = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    settings = get_settings()
    application = build_application(settings)
    vectors = application.ingestion.vectors

    chunks = vectors.load_chunks()
    if not chunks:
        raise SystemExit(
            "No persisted chunks were found. The chunk store is empty, so the "
            "index must be rebuilt with scripts/ingest.py instead."
        )

    print(f"Re-embedding {len(chunks)} persisted chunks...", flush=True)
    written = 0
    batch_size = settings.embedding_batch_size
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        embedded = application.ingestion.embeddings.create(
            tuple(_embedding_text(chunk) for chunk in batch)
        )
        written += vectors.put(batch, embedded)
        print(f"  {written}/{len(chunks)}", flush=True)

    vectors.finalize(tuple(chunk.chunk_id for chunk in chunks))
    application.search.replace_keyword_cache(chunks)
    LOGGER.info(
        "Vector index rebuilt from persisted chunks.",
        extra={
            "operation": "rebuild_vectors",
            "component": "ingestion",
            "chunks": len(chunks),
            "vectors": written,
        },
    )
    print(f"Rebuilt {written} vectors from {len(chunks)} persisted chunks.")


if __name__ == "__main__":
    main()
