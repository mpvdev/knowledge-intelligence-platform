"""Semantic retrieval that resolves vector hits to grounded S3 chunks."""

from knowledge_intelligence.connectors.s3.chunk_repository import S3ChunkRepository
from knowledge_intelligence.connectors.s3vectors_repository import S3VectorsRepository
from knowledge_intelligence.domain.retrieval import (
    DocumentChunk,
    KnowledgeSearchFilter,
    SearchResult,
)
from knowledge_intelligence.embeddings.base import EmbeddingProvider


class SemanticSearchService:
    def __init__(
        self,
        embeddings: EmbeddingProvider,
        vectors: S3VectorsRepository,
        chunks: S3ChunkRepository,
        top_k: int,
    ) -> None:
        self._embeddings = embeddings
        self._vectors = vectors
        self._chunks = chunks
        self._top_k = top_k

    def search(
        self,
        query: str,
        limit: int,
        *,
        filters: KnowledgeSearchFilter | None = None,
    ) -> tuple[SearchResult, ...]:
        batch = self._embeddings.embed((query,))
        if len(batch.embeddings) != 1:
            return ()
        component_ids = (
            filters.component_ids
            if filters is not None and not filters.include_unclassified
            else ()
        )
        hits = self._vectors.query_vectors(
            batch.embeddings[0].values,
            max(limit, self._top_k),
            component_ids,
        )
        resolved: list[SearchResult] = []
        for hit in hits:
            loaded = self._chunks.load(hit.metadata.document_id, hit.metadata.chunk_id)
            if loaded is None:
                continue
            chunk = loaded.chunk
            if (
                chunk.chunk_id != hit.metadata.chunk_id
                or chunk.document_id != hit.metadata.document_id
                or not self._matches_filter(chunk, filters)
            ):
                continue
            # S3 Vectors distance is lower-is-better; SearchResult expects non-negative score.
            resolved.append(SearchResult(chunk=chunk, score=1.0 / (1.0 + hit.distance)))
        return tuple(resolved[:limit])

    @staticmethod
    def _matches_filter(
        chunk: DocumentChunk,
        filters: KnowledgeSearchFilter | None,
    ) -> bool:
        if filters is None:
            return True
        if filters.component_ids:
            if chunk.component_id is None and not filters.include_unclassified:
                return False
            if chunk.component_id is not None and chunk.component_id not in filters.component_ids:
                return False
        elif chunk.component_id is None and not filters.include_unclassified:
            return False
        if filters.document_types and chunk.document_type not in filters.document_types:
            return False
        if filters.source_systems and chunk.source_system not in filters.source_systems:
            return False
        return not filters.tags or bool(set(chunk.tags).intersection(filters.tags))
