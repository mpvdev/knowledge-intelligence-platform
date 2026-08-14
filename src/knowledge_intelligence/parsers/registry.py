from knowledge_intelligence.domain.documents import (
    DocumentFormat,
    DownloadedDocument,
)
from knowledge_intelligence.domain.parsed_documents import ParsedDocument
from knowledge_intelligence.parsers.base import DocumentParser
from knowledge_intelligence.parsers.docx_parser import DOCXParser
from knowledge_intelligence.parsers.exceptions import UnsupportedParserError
from knowledge_intelligence.parsers.pdf_parser import PDFParser


class DocumentParserRegistry:
    """Resolve the appropriate parser for a downloaded document."""

    def __init__(
        self,
        parsers: dict[DocumentFormat, DocumentParser] | None = None,
    ) -> None:
        self._parsers = parsers or {
            DocumentFormat.PDF: PDFParser(),
            DocumentFormat.DOCX: DOCXParser(),
        }

    def parse(self, document: DownloadedDocument) -> ParsedDocument:
        parser = self._parsers.get(document.reference.format)

        if parser is None:
            raise UnsupportedParserError(
                f"No parser registered for format {document.reference.format!r}."
            )

        return parser.parse(document)
