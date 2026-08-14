from typing import Protocol

from knowledge_intelligence.domain.documents import DownloadedDocument
from knowledge_intelligence.domain.parsed_documents import ParsedDocument


class DocumentParser(Protocol):
    """Contract implemented by document-format parsers."""

    def parse(self, document: DownloadedDocument) -> ParsedDocument:
        """Parse raw downloaded bytes into normalized content."""
