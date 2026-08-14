"""Explicit, idempotent writer for normalized chunks and S3 Vectors."""

import hashlib
from dataclasses import dataclass

from knowledge_intelligence.connectors.s3.chunk_repository import S3ChunkRepository
from knowledge_intelligence.connectors.s3.exceptions import (
    S3AccessError,
    VectorIndexUnavailableError,
)
from knowledge_intelligence.connectors.s3vectors_repository import S3VectorsRepository
from knowledge_intelligence.domain.retrieval import DocumentChunk
from knowledge_intelligence.domain.vector_search import VectorMetadata, VectorRecord
from knowledge_intelligence.embeddings.base import EmbeddingProvider
from knowledge_intelligence.embeddings.exceptions import EmbeddingProviderError


@dataclass(frozen=True)
class VectorIngestionSummary:
    chunks_processed: int = 0
    vectors_written: int = 0
    embedding_tokens: int = 0
    skipped_items: int = 0
    failures: int = 0


class VectorIngestionService:
    def __init__(
        self,
        embeddings: EmbeddingProvider,
        chunks: S3ChunkRepository,
        vectors: S3VectorsRepository,
        model: str,
        dimensions: int,
        batch_size: int,
        chunking_version: str = "v1",
        visual_prompt_version: str = "visual-analysis-v1",
    ) -> None:
        self._embeddings = embeddings
        self._chunks = chunks
        self._vectors = vectors
        self._model = model
        self._dimensions = dimensions
        self._batch_size = batch_size
        self._chunking_version = chunking_version
        self._visual_prompt_version = visual_prompt_version

    def ingest(
        self,
        chunks: tuple[DocumentChunk, ...],
        dry_run: bool = False,
    ) -> VectorIngestionSummary:
        if chunks:
            self._vectors.validate_index_dimensions()
        pending: list[tuple[DocumentChunk, str]] = []
        skipped = 0
        document_chunks = self._group_by_document(chunks)
        previous_manifests = {
            document_id: self._chunks.load_manifest(document_chunks[document_id][0])
            for document_id in document_chunks
        }
        for chunk in chunks:
            fingerprint = self._fingerprint(chunk)
            existing = self._chunks.load(chunk.document_id, chunk.chunk_id)
            if (
                existing is not None
                and existing.fingerprint == fingerprint
                and existing.vector_written
            ):
                skipped += 1
            else:
                pending.append((chunk, fingerprint))
        written = tokens = failures = 0
        failed_documents: set[str] = set()
        if not dry_run:
            for start in range(0, len(pending), self._batch_size):
                group = pending[start : start + self._batch_size]
                try:
                    embedded = self._embeddings.embed(
                        tuple(self._embedding_input(chunk) for chunk, _ in group)
                    )
                    if len(embedded.embeddings) != len(group):
                        raise ValueError("Embedding result length does not match input batch.")
                    records = tuple(
                        self._record(chunk, embedding.values)
                        for (chunk, _), embedding in zip(
                            group,
                            embedded.embeddings,
                            strict=True,
                        )
                    )
                    for chunk, fingerprint in group:
                        self._chunks.save(
                            chunk,
                            fingerprint=fingerprint,
                            embedding_model=self._model,
                            embedding_dimensions=self._dimensions,
                            vector_written=False,
                        )
                    self._vectors.put_vectors(records)
                    for chunk, fingerprint in group:
                        self._chunks.save(
                            chunk,
                            fingerprint=fingerprint,
                            embedding_model=self._model,
                            embedding_dimensions=self._dimensions,
                            vector_written=True,
                        )
                    written += len(group)
                    tokens += embedded.total_tokens
                except (
                    EmbeddingProviderError,
                    S3AccessError,
                    VectorIndexUnavailableError,
                    ValueError,
                ):
                    failures += len(group)
                    failed_documents.update(chunk.document_id for chunk, _ in group)
            for document_id, current_chunks in document_chunks.items():
                if document_id in failed_documents:
                    continue
                previous = previous_manifests[document_id]
                if previous is not None:
                    current_ids = {chunk.chunk_id for chunk in current_chunks}
                    obsolete_ids = tuple(
                        chunk_id for chunk_id in previous.chunk_ids if chunk_id not in current_ids
                    )
                    if obsolete_ids:
                        self._vectors.delete_vectors(obsolete_ids)
                        for chunk_id in obsolete_ids:
                            self._chunks.delete(previous.document_id, chunk_id)
                self._chunks.save_manifest(current_chunks)
        return VectorIngestionSummary(len(chunks), written, tokens, skipped, failures)

    def delete_obsolete(self, chunks: tuple[DocumentChunk, ...]) -> None:
        """Remove source objects and vectors superseded by a document update.

        The caller supplies the previous normalized chunks after document change
        detection; this deliberately avoids broad deletion by an untrusted key.
        """
        self._vectors.delete_vectors(tuple(chunk.chunk_id for chunk in chunks))
        for chunk in chunks:
            self._chunks.delete(chunk.document_id, chunk.chunk_id)

    def _fingerprint(self, chunk: DocumentChunk) -> str:
        visual_version = self._visual_prompt_version if chunk.model_derived else ""
        value = "|".join(
            (
                chunk.chunk_id,
                hashlib.sha256(chunk.text.encode()).hexdigest(),
                self._model,
                str(self._dimensions),
                self._chunking_version,
                visual_version,
            )
        )
        return hashlib.sha256(value.encode()).hexdigest()

    @staticmethod
    def _embedding_input(chunk: DocumentChunk) -> str:
        return "\n".join(
            part
            for part in (
                chunk.document_title,
                chunk.component_name or chunk.component_id or "",
                " > ".join(chunk.heading_path),
                chunk.text,
            )
            if part
        )

    def _record(self, chunk: DocumentChunk, values: tuple[float, ...]) -> VectorRecord:
        return VectorRecord(
            key=chunk.chunk_id,
            values=values,
            metadata=VectorMetadata(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_title=chunk.document_title,
                component_id=chunk.component_id,
                component_name=chunk.component_name,
                source_system=chunk.source_system,
                content_type=chunk.content_type,
                document_key=chunk.reference.key,
                page_number=chunk.page_number,
                sequence=chunk.sequence,
                embedding_model=self._model,
                embedding_dimensions=self._dimensions,
            ),
        )

    @staticmethod
    def _group_by_document(
        chunks: tuple[DocumentChunk, ...],
    ) -> dict[str, tuple[DocumentChunk, ...]]:
        grouped: dict[str, list[DocumentChunk]] = {}
        for chunk in chunks:
            grouped.setdefault(chunk.document_id, []).append(chunk)
        return {document_id: tuple(items) for document_id, items in grouped.items()}
