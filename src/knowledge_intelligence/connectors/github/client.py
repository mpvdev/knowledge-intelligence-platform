import base64
import binascii
import re
from dataclasses import dataclass

import httpx
from pydantic import ValidationError

from knowledge_intelligence.connectors.github.exceptions import (
    GitHubAuthenticationError,
    GitHubConnectorError,
    GitHubResourceNotFoundError,
)
from knowledge_intelligence.connectors.github.models import (
    GitHubBlobPayload,
    GitHubCodeSearchPayload,
)
from knowledge_intelligence.domain.repository_knowledge import RepositoryCodeFile


@dataclass(frozen=True)
class GitHubClientConfig:
    token: str
    api_url: str = "https://api.github.com"
    api_version: str = "2026-03-10"
    timeout_seconds: float = 10.0
    maximum_file_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        if not self.token.strip():
            raise ValueError("GitHub token cannot be empty.")
        if self.timeout_seconds <= 0 or self.maximum_file_bytes <= 0:
            raise ValueError("GitHub client limits must be positive.")


class GitHubCodeClient:
    """Read immutable code blobs through the GitHub REST API."""

    def __init__(
        self,
        config: GitHubClientConfig,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {config.token}",
            "X-GitHub-Api-Version": config.api_version,
        }
        self._client = client or httpx.Client(
            base_url=config.api_url.rstrip("/"),
            timeout=config.timeout_seconds,
        )

    def search_code(
        self,
        *,
        query: str,
        repositories: tuple[str, ...],
        organization: str | None,
        limit: int,
    ) -> tuple[RepositoryCodeFile, ...]:
        normalized_query = query.strip()
        if not normalized_query:
            return ()
        if re.search(r"(?:^|\s)(?:repo|org|user):\S+", normalized_query, re.IGNORECASE):
            raise ValueError("GitHub scope qualifiers are controlled by the repository allowlist.")
        if not repositories and organization is None:
            raise ValueError("A GitHub organization or approved repository is required.")
        if limit <= 0:
            raise ValueError("limit must be positive.")

        scopes = [f"repo:{repository}" for repository in repositories]
        if organization is not None:
            scopes.append(f"org:{organization}")
        qualifiers = " ".join(scopes)
        response = self._request(
            "/search/code",
            params={"q": f"{normalized_query} {qualifiers}", "per_page": str(limit)},
        )
        try:
            payload = GitHubCodeSearchPayload.model_validate(response.json())
            return tuple(
                code_file
                for item in payload.items[:limit]
                if (
                    code_file := self._read_search_item(
                        item.repository.full_name, item.path, item.sha, item.html_url
                    )
                )
                is not None
            )
        except (ValueError, ValidationError) as exc:
            raise GitHubConnectorError("GitHub returned an invalid code-search response.") from exc

    def _read_search_item(
        self,
        repository: str,
        path: str,
        revision: str,
        html_url: str,
    ) -> RepositoryCodeFile | None:
        response = self._request(f"/repos/{repository}/git/blobs/{revision}")
        try:
            payload = GitHubBlobPayload.model_validate(response.json())
            if payload.size > self._config.maximum_file_bytes or payload.encoding != "base64":
                return None
            encoded_content = "".join(payload.content.split())
            content = base64.b64decode(encoded_content, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError, ValidationError) as exc:
            raise GitHubConnectorError("GitHub returned invalid repository file content.") from exc

        return RepositoryCodeFile(
            repository_name=repository,
            relative_path=path,
            content=content,
            line_count=max(1, content.count("\n") + 1),
            revision=revision,
            html_url=html_url,
        )

    def _request(self, path: str, *, params: dict[str, str] | None = None) -> httpx.Response:
        try:
            response = self._client.get(path, params=params, headers=self._headers)
        except httpx.HTTPError as exc:
            raise GitHubConnectorError("GitHub could not be reached.") from exc

        if response.status_code in {401, 403}:
            raise GitHubAuthenticationError("GitHub rejected the configured credentials.")
        if response.status_code == 404:
            raise GitHubResourceNotFoundError("The requested GitHub resource was not found.")
        if response.is_error:
            raise GitHubConnectorError(f"GitHub request failed with status {response.status_code}.")
        return response
