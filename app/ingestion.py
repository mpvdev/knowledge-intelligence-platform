"""Ingest the three approved Phase 1 knowledge sources."""

import hashlib
import logging
from collections.abc import Iterator
from pathlib import PurePosixPath

from app.chunker import chunk_document
from app.diagram_analysis import DiagramAnalyzer
from app.embeddings import Embeddings
from app.github_reader import GitHubReader
from app.markdown_parser import parse_markdown
from app.models import (
    UNMAPPED_COMPONENT_ID,
    Chunk,
    ParsedDocument,
    ReindexSummary,
    SourceType,
)
from app.pdf_parser import parse_pdf
from app.registry import ComponentRegistry
from app.s3_reader import S3Reader
from app.search import HybridSearch
from app.vector_store import VectorStore

LOGGER = logging.getLogger(__name__)


class Ingestion:
    def __init__(
        self,
        *,
        s3: S3Reader,
        github: GitHubReader | None,
        registry: ComponentRegistry,
        embeddings: Embeddings,
        vectors: VectorStore,
        search: HybridSearch,
        s3_prefix: str,
        batch_size: int,
        diagram_analyzer: DiagramAnalyzer | None,
        ingest_unmapped_documents: bool = True,
    ) -> None:
        self.s3 = s3
        self.github = github
        self.registry = registry
        self.embeddings = embeddings
        self.vectors = vectors
        self.search = search
        self.s3_prefix = s3_prefix
        self.batch_size = batch_size
        self.diagram_analyzer = diagram_analyzer
        self.ingest_unmapped_documents = ingest_unmapped_documents

    def run(self, sources: frozenset[SourceType] | None = None) -> ReindexSummary:
        """Ingest the approved sources, or only the ones named in `sources`.

        Ingesting a subset must never destroy the rest. `finalize()` prunes
        every chunk missing from the set it is given, so the chunks belonging to
        the sources that were *not* selected are carried across unchanged.
        """
        selected = sources if sources else frozenset(SourceType)
        documents: list[ParsedDocument] = []
        skipped = 0
        unmapped = 0

        if SourceType.REGISTRY in selected:
            documents.extend(self.registry.as_documents())

        for key, content in self._confluence_pdfs(selected):
            component = self.registry.component_for_s3_key(key)
            if component is None:
                if not self.ingest_unmapped_documents:
                    skipped += 1
                    LOGGER.warning(
                        "Skipping unmapped Confluence PDF.",
                        extra={
                            "operation": "ingest",
                            "component": "confluence",
                            "source_key": key,
                        },
                    )
                    continue
                unmapped += 1
                LOGGER.warning(
                    "Indexing a Confluence PDF that no component maps.",
                    extra={
                        "operation": "ingest",
                        "component": "confluence",
                        "source_key": key,
                    },
                )
            documents.append(
                parse_pdf(
                    content,
                    document_id=hashlib.sha256(
                        f"s3:{self.s3.bucket}:{key}".encode()
                    ).hexdigest(),
                    title=PurePosixPath(key).stem,
                    source_location=f"s3://{self.s3.bucket}/{key}",
                    component_id=(
                        component.id if component else UNMAPPED_COMPONENT_ID
                    ),
                    diagram_analyzer=self.diagram_analyzer,
                )
            )

        if self.github and SourceType.GITHUB in selected:
            readmes, unreadable = self._github_documents()
            documents.extend(readmes)
            skipped += unreadable

        chunks = tuple(
            chunk for document in documents for chunk in chunk_document(document)
        )
        retained = self._retained_chunks(selected)
        vectors_written = 0
        for start in range(0, len(chunks), self.batch_size):
            batch = chunks[start : start + self.batch_size]
            embedded = self.embeddings.create(
                tuple(_embedding_text(chunk) for chunk in batch)
            )
            vectors_written += self.vectors.put(batch, embedded)
        self.vectors.finalize(
            tuple(chunk.chunk_id for chunk in chunks + retained)
        )
        self.search.replace_keyword_cache(chunks + retained)
        if retained:
            LOGGER.info(
                "Partial ingestion completed; unselected sources were kept.",
                extra={
                    "operation": "ingest",
                    "component": "ingestion",
                    "retained_chunks": len(retained),
                },
            )
        return ReindexSummary(
            documents=len(documents),
            chunks=len(chunks),
            vectors=vectors_written,
            skipped=skipped,
            unmapped=unmapped,
        )

    def _confluence_pdfs(
        self, selected: frozenset[SourceType]
    ) -> Iterator[tuple[str, bytes]]:
        """Stream the PDFs, so their bytes are never all held at once."""
        if SourceType.CONFLUENCE not in selected:
            return
        yield from self.s3.iter_pdfs(self.s3_prefix)

    def _retained_chunks(self, selected: frozenset[SourceType]) -> tuple[Chunk, ...]:
        """Chunks of the sources this run did not touch, so pruning spares them."""
        if selected >= frozenset(SourceType):
            return ()
        return tuple(
            chunk
            for chunk in self.vectors.load_chunks()
            if chunk.source_type not in selected
        )

    def _github_documents(self) -> tuple[tuple[ParsedDocument, ...], int]:
        """Return the README documents, plus how many repositories were skipped.

        A repository that cannot be read must never discard an ingestion run:
        the PDF parsing and visual analysis before this point are expensive, and
        one expired token or renamed branch is not a reason to lose all of it.
        """
        documents: list[ParsedDocument] = []
        skipped = 0
        assert self.github is not None
        for component, repository, branch in self.registry.repositories():
            try:
                readme = self.github.read_readme(repository, branch)
            except RuntimeError:
                skipped += 1
                LOGGER.warning(
                    "Skipping repository whose README could not be read.",
                    extra={
                        "operation": "ingest",
                        "component": "github",
                        "source_key": repository,
                    },
                )
                continue
            if readme is None:
                continue
            content, url = readme
            documents.append(
                parse_markdown(
                    content,
                    document_id=hashlib.sha256(
                        f"github:{repository}:{branch or 'default'}:README.md".encode()
                    ).hexdigest(),
                    title=f"{repository} README",
                    source_location=url,
                    component_id=component.id,
                )
            )
        return tuple(documents), skipped


def _embedding_text(chunk: Chunk) -> str:
    """Text sent to the embedding model; the owner placeholder is not content."""
    return "\n".join(
        value
        for value in (
            chunk.title,
            "" if chunk.component_id == UNMAPPED_COMPONENT_ID else chunk.component_id,
            " > ".join(chunk.heading_path),
            chunk.text,
        )
        if value
    )
