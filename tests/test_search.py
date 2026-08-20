"""Hybrid search: the inverted keyword index and its ranking."""

from __future__ import annotations

from typing import Any

from app.models import Chunk, SourceType
from app.search import HybridSearch

CORPUS = (
    "EKS onboarding requires a cluster request and approval",
    "Golden AMI patching lifecycle and validation runbook",
    "Concourse pipeline observability dashboards",
    "EKS cluster upgrade runbook with validation steps",
    "Onboarding prerequisites for new TME users",
)


class UnavailableEmbeddings:
    def create(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        raise RuntimeError("semantic search unavailable")


class EmptyVectors:
    def query(self, embedding: tuple[float, ...], limit: int) -> tuple[Any, ...]:
        return ()

    def load_chunks(self) -> tuple[Chunk, ...]:
        return ()


def build_search() -> HybridSearch:
    chunks = tuple(
        Chunk(
            chunk_id=f"c{index}",
            document_id="d",
            title="doc",
            text=text,
            source_type=SourceType.CONFLUENCE,
            source_location="s3://b/k",
            component_id="eks-service",
        )
        for index, text in enumerate(CORPUS)
    )
    search = HybridSearch(UnavailableEmbeddings(), EmptyVectors(), top_k=5)  # type: ignore[arg-type]
    search.replace_keyword_cache(chunks)
    return search


def test_keyword_search_survives_semantic_failure() -> None:
    # The embedding provider raises; keyword results must still come back.
    assert build_search().search("EKS cluster runbook", 5)


def test_source_ids_are_sequential_from_one() -> None:
    results = build_search().search("EKS cluster runbook", 5)
    assert [r.source_id for r in results] == [f"S{i}" for i in range(1, len(results) + 1)]


def test_results_are_ranked_by_descending_score() -> None:
    results = build_search().search("EKS onboarding", 5)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_unmatched_query_returns_nothing() -> None:
    assert build_search().search("zzzz qqqq", 5) == ()


def test_blank_query_returns_nothing() -> None:
    assert build_search().search("   ", 5) == ()


def test_empty_index_returns_nothing() -> None:
    search = build_search()
    search.replace_keyword_cache(())
    assert search.search("EKS", 5) == ()
    assert search.cached_chunk_count == 0


def test_cached_chunk_count_tracks_the_index() -> None:
    assert build_search().cached_chunk_count == len(CORPUS)


def test_limit_is_respected() -> None:
    assert len(build_search().search("EKS onboarding runbook", 2)) <= 2
