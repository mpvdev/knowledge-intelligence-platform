from knowledge_intelligence.connectors.s3.repository import (
    S3DocumentRepository,
)
from knowledge_intelligence.domain.parsed_documents import ParsedDocument
from knowledge_intelligence.parsers.registry import DocumentParserRegistry


class DocumentProcessingService:
    """Download and parse knowledge documents."""

    def __init__(
        self,
        repository: S3DocumentRepository,
        parser_registry: DocumentParserRegistry,
    ) -> None:
        self._repository = repository
        self._parser_registry = parser_registry

    def process_document(self, key: str) -> ParsedDocument:
        downloaded_document = self._repository.download_document(key)

        return self._parser_registry.parse(downloaded_document)
