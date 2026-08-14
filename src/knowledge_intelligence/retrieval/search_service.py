from knowledge_intelligence.domain.retrieval import KnowledgeSearchFilter, SearchResult
from knowledge_intelligence.retrieval.keyword_index import KeywordIndex


class KnowledgeSearchService:
    """Apply query validation and score thresholds to indexed retrieval."""

    def __init__(self, index: KeywordIndex, minimum_score: float = 0.0) -> None:
        if minimum_score < 0:
            raise ValueError("minimum_score cannot be negative.")
        self._index = index
        self._minimum_score = minimum_score

    def search(
        self,
        query: str,
        limit: int = 5,
        *,
        filters: KnowledgeSearchFilter | None = None,
    ) -> tuple[SearchResult, ...]:
        normalized_query = query.strip()
        if not normalized_query:
            return ()

        results = self._index.search(
            query=normalized_query,
            limit=limit,
            filters=filters,
        )
        return tuple(result for result in results if result.score >= self._minimum_score)
