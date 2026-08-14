from typing import Protocol

from knowledge_intelligence.domain.visual_analysis import (
    VisualPageAnalysis,
)
from knowledge_intelligence.domain.visual_documents import (
    RenderedPDFPage,
)


class VisualPageAnalyser(Protocol):
    """Contract for model-based PDF-page analysis."""

    def analyse(
        self,
        *,
        document_key: str,
        document_title: str,
        page: RenderedPDFPage,
        extracted_text: str | None,
    ) -> VisualPageAnalysis: ...
