from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError

from knowledge_intelligence.domain.documents import DownloadedDocument
from knowledge_intelligence.domain.parsed_documents import (
    ContentBlockType,
    ParsedContentBlock,
    ParsedDocument,
)
from knowledge_intelligence.parsers.exceptions import (
    CorruptedDocumentError,
    EmptyDocumentError,
    EncryptedDocumentError,
)


class PDFParser:
    """Extract page-level text and metadata from digital PDF files."""

    def parse(self, document: DownloadedDocument) -> ParsedDocument:
        try:
            reader = PdfReader(BytesIO(document.content))
        except PdfReadError as exc:
            raise CorruptedDocumentError(
                f"Unable to read PDF document {document.reference.key!r}."
            ) from exc
        except Exception as exc:
            raise CorruptedDocumentError(
                f"Unexpected error while opening PDF {document.reference.key!r}."
            ) from exc

        if reader.is_encrypted:
            try:
                decrypt_result = reader.decrypt("")
            except FileNotDecryptedError as exc:
                raise EncryptedDocumentError(
                    f"PDF document {document.reference.key!r} is encrypted."
                ) from exc

            if decrypt_result == 0:
                raise EncryptedDocumentError(
                    f"PDF document {document.reference.key!r} is encrypted."
                )

        blocks: list[ParsedContentBlock] = []
        warnings: list[str] = []

        for page_number, page in enumerate(reader.pages, start=1):
            try:
                extracted_text = page.extract_text() or ""
            except Exception as exc:
                warnings.append(
                    f"Text extraction failed for page {page_number}: {type(exc).__name__}"
                )
                continue

            normalized_text = self._normalize_text(extracted_text)

            if not normalized_text:
                warnings.append(f"Page {page_number} contained no extractable text.")
                continue

            blocks.append(
                ParsedContentBlock(
                    block_type=ContentBlockType.PAGE_TEXT,
                    text=normalized_text,
                    page_number=page_number,
                )
            )

        if not blocks:
            raise EmptyDocumentError(
                f"PDF document {document.reference.key!r} "
                "contains no extractable text. It may be image-based."
            )

        metadata = reader.metadata

        title = self._metadata_value(metadata, "/Title")
        author = self._metadata_value(metadata, "/Author")
        subject = self._metadata_value(metadata, "/Subject")

        return ParsedDocument(
            reference=document.reference,
            title=title or document.reference.filename,
            author=author,
            subject=subject,
            page_count=len(reader.pages),
            blocks=tuple(blocks),
            warnings=tuple(warnings),
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        lines = [line.strip() for line in text.splitlines()]

        normalized_lines: list[str] = []
        previous_blank = False

        for line in lines:
            if not line:
                if normalized_lines and not previous_blank:
                    normalized_lines.append("")
                previous_blank = True
                continue

            normalized_lines.append(line)
            previous_blank = False

        return "\n".join(normalized_lines).strip()

    @staticmethod
    def _metadata_value(
        metadata: object,
        key: str,
    ) -> str | None:
        if not metadata:
            return None

        try:
            value = metadata.get(key)  # type: ignore[attr-defined]
        except AttributeError, TypeError:
            return None

        if value is None:
            return None

        normalized = str(value).strip()
        return normalized or None
