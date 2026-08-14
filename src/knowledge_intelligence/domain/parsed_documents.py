from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from knowledge_intelligence.domain.documents import DocumentReference


class ContentBlockType(StrEnum):
    """Supported normalized document content types."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    PAGE_TEXT = "page_text"


class ParsedContentBlock(BaseModel):
    """One logical block extracted from a source document."""

    model_config = ConfigDict(frozen=True)

    block_type: ContentBlockType
    text: str = Field(min_length=1)

    page_number: int | None = Field(default=None, ge=1)
    heading_level: int | None = Field(default=None, ge=1, le=9)
    heading_path: tuple[str, ...] = ()

    table_rows: tuple[tuple[str, ...], ...] = ()


class ParsedDocument(BaseModel):
    """Normalized content extracted from a PDF or DOCX document."""

    model_config = ConfigDict(frozen=True)

    reference: DocumentReference
    title: str
    blocks: tuple[ParsedContentBlock, ...]

    author: str | None = None
    subject: str | None = None

    page_count: int | None = Field(default=None, ge=0)
    warnings: tuple[str, ...] = ()

    @property
    def full_text(self) -> str:
        """Return all non-empty block text in document order."""

        return "\n\n".join(block.text for block in self.blocks)
