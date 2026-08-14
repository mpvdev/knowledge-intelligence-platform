from dataclasses import dataclass
from typing import Protocol

from strands import tool
from strands.types.tools import AgentTool

from knowledge_intelligence.application.query_context import (
    KnowledgeQueryContext,
)
from knowledge_intelligence.domain.retrieval import (
    KnowledgeEvidence,
    KnowledgeSearchFilter,
    KnowledgeSearchResponse,
)
from knowledge_intelligence.retrieval.hybrid import HybridSearchService
from knowledge_intelligence.retrieval.search_service import KnowledgeSearchService


@dataclass(frozen=True)
class KnowledgeSearchAdapter:
    search_service: KnowledgeSearchService | HybridSearchService
    maximum_results: int

    def search(
        self,
        query: str,
        limit: int,
        filters: KnowledgeSearchFilter | None = None,
    ) -> KnowledgeSearchResponse:
        normalized_query = query.strip()

        if not normalized_query:
            return KnowledgeSearchResponse(
                query=query,
                result_count=0,
                evidence=(),
                message="The search query was empty.",
            )

        effective_limit = min(
            max(limit, 1),
            self.maximum_results,
        )

        results = self.search_service.search(
            query=normalized_query,
            limit=effective_limit,
            filters=filters,
        )

        evidence = tuple(
            KnowledgeEvidence(
                source_id=f"S{position}",
                document_title=result.chunk.document_title,
                location=result.chunk.citation.display(),
                text=result.chunk.text,
                score=result.score,
                component_id=result.chunk.component_id,
                component_name=result.chunk.component_name,
                bucket=result.chunk.reference.bucket,
                key=result.chunk.reference.key,
                page_number=result.chunk.page_number,
                heading_path=result.chunk.heading_path,
            )
            for position, result in enumerate(results, start=1)
        )

        return KnowledgeSearchResponse(
            query=normalized_query,
            result_count=len(evidence),
            evidence=evidence,
            message=(
                None if evidence else "No relevant evidence was found in the indexed documents."
            ),
        )


class KnowledgeSearchClient(Protocol):
    """Request-independent knowledge search interface."""

    def search(
        self,
        query: str,
        limit: int,
        filters: KnowledgeSearchFilter | None = None,
    ) -> KnowledgeSearchResponse: ...


def create_knowledge_search_tool(
    *,
    adapter: KnowledgeSearchClient,
    context: KnowledgeQueryContext,
    filters: KnowledgeSearchFilter | None = None,
) -> AgentTool:
    """Create a request-scoped Strands knowledge-search tool."""

    @tool
    def search_platform_knowledge(
        query: str,
        limit: int = 5,
    ) -> dict[str, object]:
        """
        Search approved platform documentation for evidence relevant to a
        technical platform question.

        Args:
            query: Focused platform knowledge search query.
            limit: Maximum number of evidence sections to return.

        Returns:
            Retrieved source evidence and citation identifiers.
        """

        response = adapter.search(
            query=query,
            limit=limit,
            filters=filters,
        )

        evidence = tuple(
            item.model_copy(update={"source_id": f"S{len(context.evidence) + position}"})
            for position, item in enumerate(response.evidence, start=1)
        )
        response = response.model_copy(update={"evidence": evidence})
        context.record(evidence)

        return response.model_dump(mode="json")

    return search_platform_knowledge
