import math
from collections import Counter, defaultdict

from knowledge_intelligence.domain.retrieval import (
    DocumentChunk,
    KnowledgeSearchFilter,
    SearchResult,
)
from knowledge_intelligence.retrieval.tokenizer import SearchTokenizer


class KeywordIndex:
    """Small in-memory TF-IDF retrieval index with metadata filtering."""

    def __init__(self, tokenizer: SearchTokenizer) -> None:
        self._tokenizer = tokenizer
        self._chunks: dict[str, DocumentChunk] = {}
        self._term_frequencies: dict[str, Counter[str]] = {}
        self._document_frequencies: Counter[str] = Counter()

    def build(self, chunks: tuple[DocumentChunk, ...]) -> None:
        """Replace the current index with the supplied chunks."""
        if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
            raise ValueError("Chunk IDs must be unique within an index.")

        self._chunks.clear()
        self._term_frequencies.clear()
        self._document_frequencies.clear()

        for chunk in chunks:
            frequencies = Counter(self._tokenizer.tokenize(self._searchable_text(chunk)))
            self._chunks[chunk.chunk_id] = chunk
            self._term_frequencies[chunk.chunk_id] = frequencies
            self._document_frequencies.update(frequencies.keys())

    def search(
        self,
        *,
        query: str,
        limit: int = 5,
        filters: KnowledgeSearchFilter | None = None,
    ) -> tuple[SearchResult, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero.")

        query_terms = tuple(dict.fromkeys(self._tokenizer.tokenize(query)))
        if not query_terms or not self._chunks:
            return ()

        active_filters = filters or KnowledgeSearchFilter(include_unclassified=True)
        scores: defaultdict[str, float] = defaultdict(float)
        matched_terms: defaultdict[str, set[str]] = defaultdict(set)
        chunk_count = len(self._chunks)

        for chunk_id, chunk in self._chunks.items():
            if not self._matches_filter(chunk, active_filters):
                continue

            frequencies = self._term_frequencies[chunk_id]
            total_terms = frequencies.total()
            if total_terms == 0:
                continue

            for term in query_terms:
                frequency = frequencies.get(term, 0)
                if frequency == 0:
                    continue

                inverse_document_frequency = (
                    math.log((chunk_count + 1) / (self._document_frequencies[term] + 1)) + 1
                )
                scores[chunk_id] += frequency / total_terms * inverse_document_frequency
                matched_terms[chunk_id].add(term)

        ranked_chunk_ids = sorted(
            scores,
            key=lambda chunk_id: (-scores[chunk_id], self._chunks[chunk_id].sequence),
        )[:limit]
        return tuple(
            SearchResult(
                chunk=self._chunks[chunk_id],
                score=scores[chunk_id],
                matched_terms=tuple(sorted(matched_terms[chunk_id])),
            )
            for chunk_id in ranked_chunk_ids
        )

    @staticmethod
    def _matches_filter(chunk: DocumentChunk, filters: KnowledgeSearchFilter) -> bool:
        if filters.component_ids:
            if chunk.component_id is None:
                if not filters.include_unclassified:
                    return False
            elif chunk.component_id not in filters.component_ids:
                return False
        elif not filters.include_unclassified and chunk.component_id is None:
            return False

        if filters.document_types and chunk.document_type not in filters.document_types:
            return False
        if filters.source_systems and chunk.source_system not in filters.source_systems:
            return False
        return not filters.tags or bool(set(chunk.tags).intersection(filters.tags))

    @staticmethod
    def _searchable_text(chunk: DocumentChunk) -> str:
        heading = " ".join(chunk.heading_path)
        metadata = " ".join(
            value
            for value in (chunk.component_id, chunk.component_name, *chunk.tags)
            if value is not None
        )
        return f"{chunk.document_title}\n{heading}\n{metadata}\n{chunk.text}"
