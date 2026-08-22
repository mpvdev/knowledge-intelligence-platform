#!/usr/bin/env python3
"""Explicitly rebuild the Phase 1 knowledge index.

With no arguments every approved source is rebuilt. `--source` limits the run to
the named sources; the sources left out keep their existing chunks and vectors
rather than being pruned, so a partial run never costs you the rest of the index.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.main import build_application, configure_logging  # noqa: E402
from app.models import SourceType  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        action="append",
        choices=[source.value for source in SourceType],
        dest="sources",
        help=(
            "Ingest only this source; repeatable. Confluence PDF parsing and "
            "visual analysis are the expensive part, so use "
            "`--source github --source registry` to refresh the cheap sources "
            "without re-running it. Defaults to every source."
        ),
    )
    arguments = parser.parse_args()
    selected = (
        frozenset(SourceType(value) for value in arguments.sources)
        if arguments.sources
        else None
    )

    configure_logging()
    application = build_application(get_settings())
    summary = application.ingestion.run(selected)
    logging.getLogger(__name__).info(
        "Reindex completed.",
        extra={
            "operation": "reindex",
            "component": "ingestion",
            "sources": ",".join(sorted(source.value for source in selected))
            if selected
            else "all",
            "documents": summary.documents,
            "chunks": summary.chunks,
            "vectors": summary.vectors,
            "skipped": summary.skipped,
        },
    )
    print(summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
