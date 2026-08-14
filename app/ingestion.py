"""Ingest the three approved Phase 1 knowledge sources."""

import hashlib
import logging
from pathlib import PurePosixPath

from app.chunker import chunk_document
from app.diagram_analysis import DiagramAnalyzer
from app.embeddings import Embeddings
from app.github_reader import GitHubReader
from app.markdown_parser import parse_markdown
from app.models import Chunk, ParsedDocument, ReindexSummary
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

    def run(self) -> ReindexSummary:
        documents = list(self.registry.as_documents())
        skipped = 0

        for key, content in self.s3.iter_pdfs(self.s3_prefix):
            component = self.registry.component_for_s3_key(key)
            if component is None:
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
            documents.append(
                parse_pdf(
                    content,
                    document_id=hashlib.sha256(
                        f"s3:{self.s3.bucket}:{key}".encode()
                    ).hexdigest(),
                    title=PurePosixPath(key).stem,
                    source_location=f"s3://{self.s3.bucket}/{key}",
                    component_id=component.id,
                    diagram_analyzer=self.diagram_analyzer,
                )
            )

        if self.github:
            documents.extend(self._github_documents())

        chunks = tuple(
            chunk for document in documents for chunk in chunk_document(document)
        )
        vectors_written = 0
        for start in range(0, len(chunks), self.batch_size):
            batch = chunks[start : start + self.batch_size]
            embedded = self.embeddings.create(
                tuple(_embedding_text(chunk) for chunk in batch)
            )
            vectors_written += self.vectors.put(batch, embedded)
        self.vectors.finalize(tuple(chunk.chunk_id for chunk in chunks))
        self.search.replace_keyword_cache(chunks)
        return ReindexSummary(
            documents=len(documents),
            chunks=len(chunks),
            vectors=vectors_written,
            skipped=skipped,
        )

    def _github_documents(self) -> tuple[ParsedDocument, ...]:
        documents: list[ParsedDocument] = []
        assert self.github is not None
        for component, repository, branch in self.registry.repositories():
            readme = self.github.read_readme(repository, branch)
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
        return tuple(documents)


def _embedding_text(chunk: Chunk) -> str:
    return "\n".join(
        (chunk.title, chunk.component_id, " > ".join(chunk.heading_path), chunk.text)
    )
