"""Strands tool for code evidence from one registry-authorized local repository."""

from dataclasses import dataclass, field
from typing import Protocol

from strands import tool
from strands.types.tools import AgentTool

from knowledge_intelligence.domain.repository_knowledge import (
    RepositoryCodeEvidence,
    RepositorySearchResponse,
)
from knowledge_intelligence.retrieval.repository_search import RepositoryCodeSearchService


@dataclass
class RepositoryCodeQueryContext:
    """Request-scoped repository evidence captured by the code-search tool."""

    evidence: list[RepositoryCodeEvidence] = field(default_factory=list)

    def record(self, items: tuple[RepositoryCodeEvidence, ...]) -> None:
        self.evidence.extend(items)


@dataclass(frozen=True)
class RepositorySearchAdapter:
    repository_name: str
    search_service: RepositoryCodeSearchService

    def search(self, query: str, limit: int) -> RepositorySearchResponse:
        matches = self.search_service.search(query, limit)
        evidence = tuple(
            RepositoryCodeEvidence(
                source_id=f"R{position}",
                repository_name=self.repository_name,
                relative_path=source_file.relative_path,
                start_line=line_number,
                end_line=line_number,
                excerpt=self.search_service.excerpt(source_file, line_number),
                score=score,
                revision=source_file.revision,
                html_url=source_file.html_url,
            )
            for position, (source_file, line_number, score) in enumerate(matches, start=1)
        )
        return RepositorySearchResponse(query=query, evidence=evidence)


class RepositorySearchClient(Protocol):
    """Request-independent repository evidence search."""

    def search(self, query: str, limit: int) -> RepositorySearchResponse: ...


def create_repository_search_tool(
    *,
    adapter: RepositorySearchClient,
    context: RepositoryCodeQueryContext,
) -> AgentTool:
    """Create request-scoped code search without exposing local filesystem access."""

    @tool
    def search_repository_code(query: str, limit: int = 5) -> dict[str, object]:
        """Search the selected repository and return concise file-and-line evidence."""
        initial = adapter.search(query, limit)
        evidence = tuple(
            item.model_copy(update={"source_id": f"R{len(context.evidence) + position}"})
            for position, item in enumerate(initial.evidence, start=1)
        )
        response = RepositorySearchResponse(query=initial.query, evidence=evidence)
        context.record(response.evidence)
        return response.model_dump(mode="json")

    return search_repository_code
