import base64

import httpx
import pytest

from knowledge_intelligence.connectors.github.client import (
    GitHubClientConfig,
    GitHubCodeClient,
)
from knowledge_intelligence.connectors.github.exceptions import GitHubAuthenticationError


def test_search_reads_revision_pinned_github_blob() -> None:
    source = "def deploy():\n    return 'ready'\n"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer token"
        if request.url.path == "/search/code":
            assert "org:sky-uk" in request.url.params["q"]
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "path": "src/deploy.py",
                            "sha": "blob-sha",
                            "html_url": "https://github.example/sky/eks-service/blob/main/src/deploy.py",
                            "repository": {"full_name": "sky/eks-service"},
                        }
                    ]
                },
            )
        assert request.url.path == "/repos/sky/eks-service/git/blobs/blob-sha"
        encoded = base64.b64encode(source.encode()).decode()
        return httpx.Response(
            200,
            json={
                "content": f"{encoded[:8]}\n{encoded[8:]}",
                "encoding": "base64",
                "size": len(source.encode()),
            },
        )

    client = GitHubCodeClient(
        GitHubClientConfig(token="token"),
        client=httpx.Client(
            base_url="https://api.github.test",
            transport=httpx.MockTransport(handler),
        ),
    )

    files = client.search_code(
        query="deploy",
        repositories=(),
        organization="sky-uk",
        limit=5,
    )

    assert len(files) == 1
    assert files[0].content == source
    assert files[0].revision == "blob-sha"
    assert files[0].repository_name == "sky/eks-service"


def test_search_rejects_query_scope_injection() -> None:
    client = GitHubCodeClient(
        GitHubClientConfig(token="token"),
        client=httpx.Client(
            base_url="https://api.github.test",
            transport=httpx.MockTransport(lambda request: httpx.Response(500)),
        ),
    )

    with pytest.raises(ValueError, match="repository allowlist"):
        client.search_code(
            query="deploy repo:unapproved/private",
            repositories=("sky/eks-service",),
            organization=None,
            limit=5,
        )


def test_authentication_error_does_not_expose_response_body() -> None:
    client = GitHubCodeClient(
        GitHubClientConfig(token="secret-token"),
        client=httpx.Client(
            base_url="https://api.github.test",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(401, text="sensitive upstream response")
            ),
        ),
    )

    with pytest.raises(GitHubAuthenticationError, match="configured credentials"):
        client.search_code(
            query="deploy",
            repositories=("sky/eks-service",),
            organization=None,
            limit=5,
        )
