from knowledge_intelligence.domain.parsed_documents import (
    ParsedDocument,
)


def index_page_text(document: ParsedDocument) -> dict[int, str]:
    """Index all non-empty page text in a single pass over content blocks."""
    page_blocks: dict[int, list[str]] = {}
    for block in document.blocks:
        if block.page_number is not None:
            page_blocks.setdefault(block.page_number, []).append(block.text)

    return {page_number: "\n\n".join(texts) for page_number, texts in page_blocks.items()}
