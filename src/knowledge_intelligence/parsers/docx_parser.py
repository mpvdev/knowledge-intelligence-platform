from collections.abc import Iterator
from io import BytesIO

from docx import Document as OpenDocument
from docx.document import Document as DocxDocument
from docx.opc.exceptions import PackageNotFoundError
from docx.table import Table
from docx.text.paragraph import Paragraph

from knowledge_intelligence.domain.documents import DownloadedDocument
from knowledge_intelligence.domain.parsed_documents import (
    ContentBlockType,
    ParsedContentBlock,
    ParsedDocument,
)
from knowledge_intelligence.parsers.exceptions import (
    CorruptedDocumentError,
    EmptyDocumentError,
)


class DOCXParser:
    """Extract headings, paragraphs and tables from DOCX documents."""

    def parse(self, document: DownloadedDocument) -> ParsedDocument:
        try:
            docx_document = OpenDocument(BytesIO(document.content))
        except (PackageNotFoundError, ValueError, KeyError) as exc:
            raise CorruptedDocumentError(
                f"Unable to read DOCX document {document.reference.key!r}."
            ) from exc
        except Exception as exc:
            raise CorruptedDocumentError(
                f"Unexpected error while opening DOCX {document.reference.key!r}."
            ) from exc

        blocks: list[ParsedContentBlock] = []
        heading_path: list[str] = []

        for element in self._iter_document_blocks(docx_document):
            if isinstance(element, Paragraph):
                paragraph_text = self._normalize_text(element.text)

                if not paragraph_text:
                    continue

                heading_level = self._get_heading_level(element)

                if heading_level is not None:
                    heading_path = self._update_heading_path(
                        current_path=heading_path,
                        heading=paragraph_text,
                        level=heading_level,
                    )

                    blocks.append(
                        ParsedContentBlock(
                            block_type=ContentBlockType.HEADING,
                            text=paragraph_text,
                            heading_level=heading_level,
                            heading_path=tuple(heading_path),
                        )
                    )
                else:
                    blocks.append(
                        ParsedContentBlock(
                            block_type=ContentBlockType.PARAGRAPH,
                            text=paragraph_text,
                            heading_path=tuple(heading_path),
                        )
                    )

            elif isinstance(element, Table):
                rows = self._extract_table_rows(element)

                if not rows:
                    continue

                table_text = self._table_to_text(rows)

                blocks.append(
                    ParsedContentBlock(
                        block_type=ContentBlockType.TABLE,
                        text=table_text,
                        heading_path=tuple(heading_path),
                        table_rows=rows,
                    )
                )

        if not blocks:
            raise EmptyDocumentError(
                f"DOCX document {document.reference.key!r} contains no extractable text."
            )

        properties = docx_document.core_properties

        title = self._normalize_optional(properties.title)
        author = self._normalize_optional(properties.author)
        subject = self._normalize_optional(properties.subject)

        return ParsedDocument(
            reference=document.reference,
            title=title or document.reference.filename,
            author=author,
            subject=subject,
            blocks=tuple(blocks),
        )

    @staticmethod
    def _iter_document_blocks(
        document: DocxDocument,
    ) -> Iterator[Paragraph | Table]:
        """
        Yield paragraphs and tables in their original body order.

        Images, text boxes, headers and footers are intentionally excluded
        from Step 02.
        """

        for child in document.element.body.iterchildren():
            if child.tag.endswith("}p"):
                yield Paragraph(child, document)

            elif child.tag.endswith("}tbl"):
                yield Table(child, document)

    @staticmethod
    def _get_heading_level(paragraph: Paragraph) -> int | None:
        style_name = paragraph.style.name.strip() if paragraph.style else ""

        if not style_name.lower().startswith("heading"):
            return None

        level_text = style_name[len("Heading") :].strip()

        if not level_text.isdigit():
            return 1

        return max(1, min(int(level_text), 9))

    @staticmethod
    def _update_heading_path(
        current_path: list[str],
        heading: str,
        level: int,
    ) -> list[str]:
        new_path = current_path[: level - 1]

        while len(new_path) < level - 1:
            new_path.append("")

        new_path.append(heading)

        return new_path

    @staticmethod
    def _extract_table_rows(
        table: Table,
    ) -> tuple[tuple[str, ...], ...]:
        rows: list[tuple[str, ...]] = []

        for row in table.rows:
            cells = tuple(DOCXParser._normalize_text(cell.text) for cell in row.cells)

            if any(cells):
                rows.append(cells)

        return tuple(rows)

    @staticmethod
    def _table_to_text(
        rows: tuple[tuple[str, ...], ...],
    ) -> str:
        return "\n".join(" | ".join(cell for cell in row) for row in rows)

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(text.split()).strip()

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if not value:
            return None

        normalized = value.strip()
        return normalized or None
