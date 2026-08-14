class GitHubConnectorError(RuntimeError):
    """Base error for read-only GitHub access."""


class GitHubAuthenticationError(GitHubConnectorError):
    """GitHub rejected the configured credentials."""


class GitHubResourceNotFoundError(GitHubConnectorError):
    """A requested GitHub resource is unavailable."""
