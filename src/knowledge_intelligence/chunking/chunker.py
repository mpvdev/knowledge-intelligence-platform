import hashlib

from knowledge_intelligence.chunking.text_splitter import TextSplitter
from knowledge_intelligence.domain.classification import DocumentClassification
from knowledge_intelligence.domain.parsed_documents import ParsedDocument
from knowledge_intelligence.domain.retrieval import DocumentChunk


class DocumentChunker:
    """Convert classified document blocks into searchable chunks."""

    def __init__(self, text_splitter: TextSplitter) -> None:
        self._text_splitter = text_splitter

    def chunk(
        self,
        *,
        document: ParsedDocument,
        classification: DocumentClassification,
    ) -> tuple[DocumentChunk, ...]:
        document_id = self._document_id(document)
        chunks: list[DocumentChunk] = []

        for block in document.blocks:
            for text in self._text_splitter.split(block.text):
                sequence = len(chunks)
                chunks.append(
                    DocumentChunk(
                        chunk_id=self._chunk_id(document_id, sequence, text),
                        document_id=document_id,
                        document_title=document.title,
                        text=text,
                        reference=document.reference,
                        platform_id=classification.platform_id,
                        component_id=classification.component_id,
                        component_name=classification.component_name,
                        document_type=classification.document_type,
                        source_system=classification.source_system,
                        related_component_ids=classification.related_component_ids,
                        tags=classification.tags,
                        page_number=block.page_number,
                        heading_path=block.heading_path,
                        sequence=sequence,
                    )
                )

        return tuple(chunks)

    @staticmethod
    def _document_id(document: ParsedDocument) -> str:
        reference = document.reference
        identity = (
            f"{reference.bucket}:{reference.key}:"
            f"{reference.etag or ''}:{reference.version_id or ''}"
        )
        return hashlib.sha256(identity.encode()).hexdigest()

    @staticmethod
    def _chunk_id(document_id: str, sequence: int, text: str) -> str:
        return hashlib.sha256(f"{document_id}:{sequence}:{text}".encode()).hexdigest()
