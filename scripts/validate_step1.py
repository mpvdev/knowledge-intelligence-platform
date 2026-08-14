from knowledge_intelligence.config import get_settings
from knowledge_intelligence.connectors.s3.client import create_s3_client
from knowledge_intelligence.connectors.s3.repository import S3DocumentRepository
from knowledge_intelligence.services.document_discovery import (
    DocumentDiscoveryService,
)


def main() -> None:
    settings = get_settings()

    repository = S3DocumentRepository(
        s3_client=create_s3_client(settings.aws_region),
        bucket=settings.s3_bucket,
        max_document_size_bytes=settings.max_document_size_bytes,
    )

    service = DocumentDiscoveryService(repository)

    documents = service.discover(settings.s3_prefix)

    print(f"Discovered {len(documents)} supported documents")

    for document in documents:
        print(
            f"- {document.filename} "
            f"[{document.format}] "
            f"{document.size_bytes} bytes "
            f"s3://{document.bucket}/{document.key}"
        )

        downloaded = repository.download_document(document.key)

        print(f"  Downloaded successfully: {len(downloaded.content)} bytes")


if __name__ == "__main__":
    main()
