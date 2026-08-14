from knowledge_intelligence.connectors.s3.repository import (
    S3DocumentRepository,
)
from knowledge_intelligence.domain.documents import DocumentReference


class DocumentDiscoveryService:
    """Application service for discovering available knowledge documents."""

    def __init__(self, repository: S3DocumentRepository) -> None:
        self._repository = repository

    def discover(self, prefix: str) -> list[DocumentReference]:
        normalized_prefix = self._normalize_prefix(prefix)
        return self._repository.list_documents(normalized_prefix)

    @staticmethod
    def _normalize_prefix(prefix: str) -> str:
        normalized = prefix.strip().lstrip("/")

        if normalized and not normalized.endswith("/"):
            normalized += "/"

        return normalized
