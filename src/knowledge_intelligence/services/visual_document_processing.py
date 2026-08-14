from collections.abc import Mapping
from dataclasses import dataclass
from itertools import islice

from knowledge_intelligence.domain.visual_analysis import (
    VisualPageAnalysis,
)
from knowledge_intelligence.domain.visual_documents import (
    RenderedPDFPage,
    VisualPageInspection,
)
from knowledge_intelligence.visual.analyser import (
    VisualPageAnalyser,
)
from knowledge_intelligence.visual.detector import (
    VisualPageDetector,
)
from knowledge_intelligence.visual.renderer import (
    PDFPageRenderer,
)


@dataclass(frozen=True)
class VisualDocumentProcessingResult:
    inspections: tuple[VisualPageInspection, ...]
    rendered_pages: tuple[RenderedPDFPage, ...]
    visual_analyses: tuple[VisualPageAnalysis, ...] = ()


class VisualDocumentProcessingService:
    """Detect, render and optionally analyse meaningful PDF visuals."""

    def __init__(
        self,
        *,
        detector: VisualPageDetector,
        renderer: PDFPageRenderer,
        analyser: VisualPageAnalyser | None = None,
        maximum_pages: int,
    ) -> None:
        if maximum_pages <= 0:
            raise ValueError("maximum_pages must be greater than zero.")

        self._detector = detector
        self._renderer = renderer
        self._analyser = analyser
        self._maximum_pages = maximum_pages

    def process(
        self,
        *,
        pdf_bytes: bytes,
        document_key: str | None = None,
        document_title: str | None = None,
        page_text: Mapping[int, str] | None = None,
    ) -> VisualDocumentProcessingResult:
        inspections = self._detector.inspect_document(pdf_bytes)

        selected_pages = tuple(
            islice(
                (
                    inspection.page_number
                    for inspection in inspections
                    if inspection.requires_visual_analysis
                ),
                self._maximum_pages,
            )
        )

        rendered_pages = self._renderer.render_pages(
            pdf_bytes=pdf_bytes,
            page_numbers=selected_pages,
        )

        if self._analyser is None:
            return VisualDocumentProcessingResult(
                inspections=inspections,
                rendered_pages=rendered_pages,
            )

        if not document_key or not document_title:
            raise ValueError(
                "document_key and document_title are required when visual analysis is enabled."
            )

        resolved_page_text = page_text or {}

        visual_analyses = tuple(
            self._analyser.analyse(
                document_key=document_key,
                document_title=document_title,
                page=rendered_page,
                extracted_text=resolved_page_text.get(rendered_page.page_number),
            )
            for rendered_page in rendered_pages
        )

        return VisualDocumentProcessingResult(
            inspections=inspections,
            rendered_pages=rendered_pages,
            visual_analyses=visual_analyses,
        )
