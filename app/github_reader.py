"""Read only repository README files through the GitHub Contents API."""

import base64
import binascii
import re

import httpx

REPOSITORY_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class GitHubReader:
    def __init__(self, token: str, api_url: str) -> None:
        if not token.strip():
            raise ValueError("GitHub token cannot be empty.")
        self.client = httpx.Client(
            base_url=api_url.rstrip("/"),
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=20,
        )

    def read_readme(
        self, repository: str, branch: str | None = None
    ) -> tuple[str, str] | None:
        """Return README Markdown and its browser URL; never inspect other paths."""
        if not REPOSITORY_NAME.fullmatch(repository):
            raise ValueError(f"Invalid repository name: {repository}")
        try:
            response = self.client.get(
                f"/repos/{repository}/contents/README.md",
                params={"ref": branch} if branch else None,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            payload = response.json()
            if (
                payload.get("type") != "file"
                or payload.get("name", "").casefold() != "readme.md"
            ):
                return None
            encoded = payload.get("content")
            url = payload.get("html_url")
            if not isinstance(encoded, str) or not isinstance(url, str):
                raise RuntimeError("GitHub returned an invalid README response.")
            content = base64.b64decode(encoded, validate=False).decode("utf-8")
            return content, url
        except (httpx.HTTPError, UnicodeDecodeError, binascii.Error, ValueError) as exc:
            raise RuntimeError(f"Unable to read README.md from {repository}.") from exc

    def close(self) -> None:
        self.client.close()
