from enum import StrEnum

from knowledge_intelligence.connectors.s3.exceptions import (
    S3AccessError,
    VectorIndexUnavailableError,
)
from knowledge_intelligence.domain.retrieval import KnowledgeSearchFilter, SearchResult
from knowledge_intelligence.embeddings.exceptions import EmbeddingProviderError
from knowledge_intelligence.retrieval.search_service import KnowledgeSearchService
from knowledge_intelligence.retrieval.semantic_search import SemanticSearchService


class RetrievalMode(StrEnum):
    KEYWORD_ONLY = "keyword_only"
    SEMANTIC_ONLY = "semantic_only"
    HYBRID = "hybrid"


def reciprocal_rank_fusion(
    *rankings: tuple[SearchResult, ...], limit: int, constant: int = 60
) -> tuple[SearchResult, ...]:
    scores: dict[str, float] = {}
    results: dict[str, SearchResult] = {}
    for ranking in rankings:
        for rank, result in enumerate(ranking, start=1):
            scores[result.chunk.chunk_id] = scores.get(result.chunk.chunk_id, 0.0) + 1 / (
                constant + rank
            )
            results.setdefault(result.chunk.chunk_id, result)
    return tuple(
        SearchResult(
            chunk=results[chunk_id].chunk,
            score=scores[chunk_id],
            matched_terms=results[chunk_id].matched_terms,
        )
        for chunk_id in sorted(scores, key=lambda key: (-scores[key], key))[:limit]
    )


class HybridSearchService:
    def __init__(
        self,
        keyword: KnowledgeSearchService,
        semantic: SemanticSearchService | None,
        mode: RetrievalMode = RetrievalMode.HYBRID,
    ) -> None:
        self._keyword, self._semantic, self._mode = keyword, semantic, mode

    def search(
        self, query: str, limit: int = 5, *, filters: KnowledgeSearchFilter | None = None
    ) -> tuple[SearchResult, ...]:
        keyword = self._keyword.search(query, limit, filters=filters)
        if self._mode == RetrievalMode.KEYWORD_ONLY or self._semantic is None:
            return keyword
        try:
            semantic = self._semantic.search(query, limit, filters=filters)
        except EmbeddingProviderError, S3AccessError, VectorIndexUnavailableError, ValueError:
            return keyword
        if self._mode == RetrievalMode.SEMANTIC_ONLY:
            return semantic
        return reciprocal_rank_fusion(keyword, semantic, limit=limit)
