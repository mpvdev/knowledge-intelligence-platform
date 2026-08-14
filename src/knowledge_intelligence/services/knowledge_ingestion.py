from knowledge_intelligence.chunking.chunker import DocumentChunker
from knowledge_intelligence.connectors.s3.repository import S3DocumentRepository
from knowledge_intelligence.domain.retrieval import DocumentChunk
from knowledge_intelligence.parsers.registry import DocumentParserRegistry
from knowledge_intelligence.services.document_classification import (
    DocumentClassificationService,
)


class KnowledgeIngestionService:
    """Download, classify, parse and chunk approved documents."""

    def __init__(
        self,
        *,
        repository: S3DocumentRepository,
        parser_registry: DocumentParserRegistry,
        chunker: DocumentChunker,
        classification_service: DocumentClassificationService,
    ) -> None:
        self._repository = repository
        self._parser_registry = parser_registry
        self._chunker = chunker
        self._classification_service = classification_service

    def ingest_prefix(self, prefix: str) -> tuple[DocumentChunk, ...]:
        chunks: list[DocumentChunk] = []
        for reference in self._repository.list_documents(prefix):
            downloaded = self._repository.download_document(reference.key)
            parsed = self._parser_registry.parse(downloaded)
            classification = self._classification_service.classify(reference.key)
            chunks.extend(self._chunker.chunk(document=parsed, classification=classification))
        return tuple(chunks)
