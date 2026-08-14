import json

from knowledge_intelligence.application.container import (
    build_document_repository,
    build_pdf_enrichment_service,
)
from knowledge_intelligence.config import get_settings
from knowledge_intelligence.domain.documents import (
    DocumentFormat,
)
from knowledge_intelligence.parsers.registry import (
    DocumentParserRegistry,
)


def main() -> None:
    settings = get_settings()

    repository = build_document_repository(settings)

    parser_registry = DocumentParserRegistry()

    service = build_pdf_enrichment_service(settings)

    references = repository.list_documents(settings.s3_prefix)

    for reference in references:
        if reference.format != DocumentFormat.PDF:
            continue

        downloaded = repository.download_document(reference.key)
        parsed = parser_registry.parse(downloaded)

        result = service.enrich(
            downloaded=downloaded,
            parsed=parsed,
        )

        print()
        print("=" * 80)
        print(reference.key)

        for analysis in result.visual_analyses:
            print()
            print(f"Page {analysis.page_number}")
            print(
                json.dumps(
                    analysis.model_dump(mode="json"),
                    indent=2,
                )
            )


if __name__ == "__main__":
    main()
