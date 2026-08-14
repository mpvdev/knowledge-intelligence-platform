from pathlib import Path

from knowledge_intelligence.application.container import (
    build_document_repository,
    build_visual_processing_service,
)
from knowledge_intelligence.config import get_settings
from knowledge_intelligence.domain.documents import DocumentFormat


def main() -> None:
    settings = get_settings()

    repository = build_document_repository(settings)

    service = build_visual_processing_service(settings)

    documents = repository.list_documents(settings.s3_prefix)

    output_directory = Path("tmp/visual-pages")
    output_directory.mkdir(parents=True, exist_ok=True)

    for reference in documents:
        if reference.format != DocumentFormat.PDF:
            continue

        downloaded = repository.download_document(reference.key)

        result = service.process(pdf_bytes=downloaded.content)

        print()
        print("=" * 80)
        print(reference.key)

        for inspection in result.inspections:
            print(
                f"Page {inspection.page_number}: "
                f"{inspection.classification.value}; "
                f"text={inspection.text_character_count}; "
                f"images={inspection.embedded_image_count}; "
                f"largest_ratio="
                f"{inspection.largest_image_area_ratio:.3f}"
            )

            for reason in inspection.reasons:
                print(f"  - {reason}")

        document_output = output_directory / reference.filename.removesuffix(".pdf")
        document_output.mkdir(parents=True, exist_ok=True)

        for rendered_page in result.rendered_pages:
            output_path = document_output / f"page-{rendered_page.page_number:03d}.png"

            output_path.write_bytes(rendered_page.image_bytes)

            print(f"Rendered page {rendered_page.page_number} to {output_path}")


if __name__ == "__main__":
    main()
