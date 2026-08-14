"""PDF-to-ParsedDocument conversion."""

from io import BytesIO

from pypdf import PdfReader

from app.diagram_analysis import DiagramAnalyzer
from app.models import ContentBlock, ParsedDocument, SourceType


def parse_pdf(
    content: bytes,
    *,
    document_id: str,
    title: str,
    source_location: str,
    component_id: str,
    diagram_analyzer: DiagramAnalyzer | None = None,
) -> ParsedDocument:
    reader = PdfReader(BytesIO(content))
    if reader.is_encrypted and reader.decrypt("") == 0:
        raise ValueError(f"Encrypted PDF is not supported: {source_location}")

    blocks = tuple(
        ContentBlock(text=text, page_number=page_number)
        for page_number, page in enumerate(reader.pages, start=1)
        if (text := _normalize(page.extract_text() or ""))
    )
    if not blocks:
        raise ValueError(f"PDF contains no extractable text: {source_location}")

    metadata = reader.metadata
    metadata_title = str(metadata.title).strip() if metadata and metadata.title else ""
    visual_blocks = (
        diagram_analyzer.analyze(content, source_location) if diagram_analyzer else ()
    )
    return ParsedDocument(
        document_id=document_id,
        title=metadata_title or title,
        source_type=SourceType.CONFLUENCE,
        source_location=source_location,
        component_id=component_id,
        blocks=blocks + visual_blocks,
    )


def _normalize(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines()).strip()
