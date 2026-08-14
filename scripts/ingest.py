#!/usr/bin/env python3
"""Explicitly rebuild the Phase 1 knowledge index."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.main import build_application, configure_logging  # noqa: E402


def main() -> None:
    configure_logging()
    application = build_application(get_settings())
    summary = application.ingestion.run()
    logging.getLogger(__name__).info(
        "Reindex completed.",
        extra={
            "operation": "reindex",
            "component": "ingestion",
            "documents": summary.documents,
            "chunks": summary.chunks,
            "vectors": summary.vectors,
            "skipped": summary.skipped,
        },
    )
    print(summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
