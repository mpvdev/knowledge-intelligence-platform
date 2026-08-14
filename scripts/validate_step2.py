from knowledge_intelligence.config import get_settings
from knowledge_intelligence.connectors.s3.client import create_s3_client
from knowledge_intelligence.connectors.s3.repository import (
    S3DocumentRepository,
)
from knowledge_intelligence.parsers.registry import (
    DocumentParserRegistry,
)
from knowledge_intelligence.services.document_discovery import (
    DocumentDiscoveryService,
)
from knowledge_intelligence.services.document_processing import (
    DocumentProcessingService,
)


def main() -> None:
    settings = get_settings()

    repository = S3DocumentRepository(
        s3_client=create_s3_client(settings.aws_region),
        bucket=settings.s3_bucket,
        max_document_size_bytes=settings.max_document_size_bytes,
    )

    discovery_service = DocumentDiscoveryService(repository)

    processing_service = DocumentProcessingService(
        repository=repository,
        parser_registry=DocumentParserRegistry(),
    )

    documents = discovery_service.discover(settings.s3_prefix)

    print(f"Discovered {len(documents)} supported documents")

    for document in documents:
        print()
        print("=" * 80)
        print(f"Processing: s3://{document.bucket}/{document.key}")

        parsed = processing_service.process_document(document.key)

        print(f"Title: {parsed.title}")
        print(f"Format: {parsed.reference.format}")
        print(f"Blocks: {len(parsed.blocks)}")
        print(f"Pages: {parsed.page_count}")
        print(f"Warnings: {len(parsed.warnings)}")

        if parsed.warnings:
            for warning in parsed.warnings:
                print(f"  WARNING: {warning}")

        print("-" * 80)
        print(parsed.full_text[:2_000])
        print("-" * 80)


if __name__ == "__main__":
    main()
