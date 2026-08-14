from dataclasses import dataclass

from knowledge_intelligence.domain.documents import (
    DownloadedDocument,
)
from knowledge_intelligence.domain.parsed_documents import (
    ParsedDocument,
)
from knowledge_intelligence.domain.visual_analysis import (
    VisualPageAnalysis,
)
from knowledge_intelligence.services.page_content import index_page_text
from knowledge_intelligence.services.visual_document_processing import (
    VisualDocumentProcessingService,
)


@dataclass(frozen=True)
class EnrichedPDFDocument:
    parsed_document: ParsedDocument
    visual_analyses: tuple[VisualPageAnalysis, ...]


class PDFEnrichmentService:
    """Enrich a parsed PDF with selective model-derived visual knowledge."""

    def __init__(
        self,
        visual_service: VisualDocumentProcessingService,
    ) -> None:
        self._visual_service = visual_service

    def enrich(
        self,
        *,
        downloaded: DownloadedDocument,
        parsed: ParsedDocument,
    ) -> EnrichedPDFDocument:
        result = self._visual_service.process(
            pdf_bytes=downloaded.content,
            document_key=downloaded.reference.key,
            document_title=parsed.title,
            page_text=index_page_text(parsed),
        )

        return EnrichedPDFDocument(
            parsed_document=parsed,
            visual_analyses=result.visual_analyses,
        )
