import pytest

from knowledge_intelligence.connectors.github.client import GitHubClientConfig, GitHubCodeClient
from knowledge_intelligence.retrieval.github_search import GitHubRepositorySearchAdapter


def test_github_adapter_requires_owner_and_repository_names() -> None:
    with pytest.raises(ValueError, match="Invalid GitHub repository names"):
        GitHubRepositorySearchAdapter(
            client=GitHubCodeClient(GitHubClientConfig(token="token")),
            repositories=("not-a-full-name",),
            organization=None,
            maximum_results=5,
        )
