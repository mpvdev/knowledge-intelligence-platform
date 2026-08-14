"""Hybrid keyword and S3 Vector search."""

import logging
import math
import re
from collections import Counter
from threading import RLock
from time import monotonic

from app.embeddings import EmbeddingUnavailableError, Embeddings
from app.models import Chunk, SearchResult
from app.vector_store import VectorStore

LOGGER = logging.getLogger(__name__)

STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "how",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "what",
        "when",
        "where",
        "which",
        "with",
    }
)


class HybridSearch:
    def __init__(
        self, embeddings: Embeddings, vectors: VectorStore, top_k: int
    ) -> None:
        self.embeddings = embeddings
        self.vectors = vectors
        self.top_k = top_k
        self._chunks: tuple[Chunk, ...] = ()
        self._frequencies: dict[str, Counter[str]] = {}
        self._document_frequency: Counter[str] = Counter()
        self._chunks_by_id: dict[str, Chunk] = {}
        self._lock = RLock()

    @property
    def cached_chunk_count(self) -> int:
        with self._lock:
            return len(self._chunks)

    def replace_keyword_cache(self, chunks: tuple[Chunk, ...]) -> None:
        frequencies = {
            chunk.chunk_id: Counter(_tokens(_searchable(chunk))) for chunk in chunks
        }
        with self._lock:
            self._chunks = chunks
            self._frequencies = frequencies
            self._document_frequency = Counter(
                term for chunk_terms in frequencies.values() for term in chunk_terms
            )
            self._chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}

    def search(self, query: str, limit: int) -> tuple[SearchResult, ...]:
        normalized = query.strip()
        if not normalized:
            return ()
        self._restore_keyword_cache_if_empty()
        effective_limit = min(max(limit, 1), self.top_k)
        started = monotonic()
        try:
            semantic = self._semantic(normalized, effective_limit)
        except (EmbeddingUnavailableError, RuntimeError):
            LOGGER.exception(
                "Semantic search unavailable; continuing with keyword search.",
                extra={"operation": "semantic_search", "component": "search"},
            )
            semantic = ()
        semantic_ms = (monotonic() - started) * 1_000
        keyword_started = monotonic()
        keyword = self._keyword(normalized, effective_limit)
        ranked = self._reciprocal_rank_fusion(semantic, keyword, effective_limit)
        LOGGER.info(
            "Knowledge search completed.",
            extra={
                "operation": "hybrid_search",
                "component": "search",
                "duration_ms": round((monotonic() - started) * 1_000, 2),
                "semantic_ms": round(semantic_ms, 2),
                "keyword_ms": round((monotonic() - keyword_started) * 1_000, 2),
            },
        )
        return tuple(
            SearchResult(source_id=f"S{index}", chunk=chunk, score=score)
            for index, (chunk, score) in enumerate(ranked, start=1)
        )

    def _restore_keyword_cache_if_empty(self) -> None:
        with self._lock:
            if self._chunks:
                return
        try:
            chunks = self.vectors.load_chunks()
        except RuntimeError:
            LOGGER.exception(
                "Keyword search cache could not be restored during a query.",
                extra={"operation": "restore_keyword_cache", "component": "search"},
            )
            return
        if chunks:
            self.replace_keyword_cache(chunks)

    def _semantic(self, query: str, limit: int) -> tuple[tuple[Chunk, float], ...]:
        vector = self.embeddings.create((query,))[0]
        return self.vectors.query(vector, limit)

    def _keyword(self, query: str, limit: int) -> tuple[tuple[Chunk, float], ...]:
        terms = tuple(dict.fromkeys(_tokens(query)))
        with self._lock:
            chunks = self._chunks
            frequencies = self._frequencies
            document_frequency = self._document_frequency
            by_id = self._chunks_by_id
        if not terms or not chunks:
            return ()
        scores: dict[str, float] = {}
        for chunk_id, counts in frequencies.items():
            total = counts.total()
            score = sum(
                counts[term]
                / total
                * (math.log((len(chunks) + 1) / (document_frequency[term] + 1)) + 1)
                for term in terms
                if counts[term]
            )
            if score:
                scores[chunk_id] = score
        return tuple(
            (by_id[chunk_id], scores[chunk_id])
            for chunk_id in sorted(scores, key=lambda item: (-scores[item], item))[
                :limit
            ]
        )

    @staticmethod
    def _reciprocal_rank_fusion(
        semantic: tuple[tuple[Chunk, float], ...],
        keyword: tuple[tuple[Chunk, float], ...],
        limit: int,
    ) -> tuple[tuple[Chunk, float], ...]:
        scores: dict[str, float] = {}
        chunks: dict[str, Chunk] = {}
        for ranking in (semantic, keyword):
            for rank, (chunk, _) in enumerate(ranking, start=1):
                chunks[chunk.chunk_id] = chunk
                scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1 / (
                    60 + rank
                )
        return tuple(
            (chunks[chunk_id], scores[chunk_id])
            for chunk_id in sorted(scores, key=lambda item: (-scores[item], item))[
                :limit
            ]
        )


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(
        term
        for term in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_.:/-]*", text.casefold())
        if term not in STOP_WORDS and len(term) > 1
    )


def _searchable(chunk: Chunk) -> str:
    return "\n".join(
        (chunk.title, chunk.component_id, " ".join(chunk.heading_path), chunk.text)
    )
