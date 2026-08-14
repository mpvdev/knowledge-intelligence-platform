import re
from dataclasses import dataclass

from knowledge_intelligence.connectors.github.client import GitHubCodeClient
from knowledge_intelligence.domain.repository_knowledge import (
    RepositoryCodeEvidence,
    RepositorySearchResponse,
)
from knowledge_intelligence.retrieval.repository_search import RepositoryCodeSearchService
from knowledge_intelligence.retrieval.tokenizer import SearchTokenizer


@dataclass(frozen=True)
class GitHubRepositorySearchAdapter:
    """Produce line-cited evidence from approved remote repositories."""

    client: GitHubCodeClient
    repositories: tuple[str, ...]
    organization: str | None
    maximum_results: int

    def __post_init__(self) -> None:
        if not self.repositories and self.organization is None:
            raise ValueError("A GitHub organization or approved repository is required.")
        if self.maximum_results <= 0:
            raise ValueError("maximum_results must be positive.")
        invalid = tuple(
            repository
            for repository in self.repositories
            if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is None
        )
        if invalid:
            raise ValueError(f"Invalid GitHub repository names: {', '.join(invalid)}")
        if (
            self.organization is not None
            and re.fullmatch(
                r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?",
                self.organization,
            )
            is None
        ):
            raise ValueError("Invalid GitHub organization name.")

    def search(self, query: str, limit: int) -> RepositorySearchResponse:
        effective_limit = min(max(limit, 1), self.maximum_results)
        files = self.client.search_code(
            query=query,
            repositories=self.repositories,
            organization=self.organization,
            limit=effective_limit,
        )
        evidence: list[RepositoryCodeEvidence] = []
        for source_file in files:
            repository_name = source_file.repository_name
            if repository_name is None:
                continue
            search_service = RepositoryCodeSearchService(
                repository_name,
                (source_file,),
                SearchTokenizer(),
            )
            for matched_file, line_number, score in search_service.search(query, 1):
                evidence.append(
                    RepositoryCodeEvidence(
                        source_id=f"R{len(evidence) + 1}",
                        repository_name=repository_name,
                        relative_path=matched_file.relative_path,
                        start_line=line_number,
                        end_line=line_number,
                        excerpt=search_service.excerpt(matched_file, line_number),
                        score=score,
                        revision=matched_file.revision,
                        html_url=matched_file.html_url,
                    )
                )

        return RepositorySearchResponse(query=query.strip(), evidence=tuple(evidence))
