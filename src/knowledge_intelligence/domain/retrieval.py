from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from knowledge_intelligence.domain.documents import DocumentReference


class CitationType(StrEnum):
    PAGE = "page"
    HEADING = "heading"


class ChunkContentType(StrEnum):
    DOCUMENT_TEXT = "document_text"
    VISUAL_DESCRIPTION = "visual_description"


class SourceCitation(BaseModel):
    """Location of retrieved content in its original source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_title: str
    bucket: str
    key: str
    citation_type: CitationType

    page_number: int | None = Field(default=None, ge=1)
    heading_path: tuple[str, ...] = ()

    def display(self) -> str:
        if self.page_number is not None:
            return f"{self.document_title} — Page {self.page_number}"

        if self.heading_path:
            return (
                f"{self.document_title} — {' > '.join(part for part in self.heading_path if part)}"
            )

        return self.document_title


class DocumentChunk(BaseModel):
    """Searchable unit derived from an approved source document."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    document_id: str
    document_title: str
    text: str = Field(min_length=1)

    reference: DocumentReference

    platform_id: str = "tme"
    component_id: str | None = None
    component_name: str | None = None

    document_type: str | None = None
    source_system: str = "confluence"
    content_type: ChunkContentType = ChunkContentType.DOCUMENT_TEXT
    model_derived: bool = False

    related_component_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    page_number: int | None = Field(default=None, ge=1)
    heading_path: tuple[str, ...] = ()

    sequence: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_content_origin(self) -> DocumentChunk:
        if self.content_type == ChunkContentType.VISUAL_DESCRIPTION and not self.model_derived:
            raise ValueError("Visual-description chunks must be marked as model-derived.")
        return self

    @property
    def citation(self) -> SourceCitation:
        citation_type = CitationType.PAGE if self.page_number is not None else CitationType.HEADING
        return SourceCitation(
            document_title=self.document_title,
            bucket=self.reference.bucket,
            key=self.reference.key,
            citation_type=citation_type,
            page_number=self.page_number,
            heading_path=self.heading_path,
        )


class SearchResult(BaseModel):
    """One ranked retrieval result."""

    model_config = ConfigDict(frozen=True)

    chunk: DocumentChunk
    score: float = Field(ge=0)
    matched_terms: tuple[str, ...] = ()


class StoredChunk(BaseModel):
    """A complete chunk and its ingestion state, stored in standard S3."""

    model_config = ConfigDict(frozen=True)

    chunk: DocumentChunk
    fingerprint: str = Field(min_length=1)
    vector_written: bool


class DocumentChunkManifest(BaseModel):
    """Current indexed chunks for one source object."""

    model_config = ConfigDict(frozen=True)

    source_bucket: str
    source_key: str
    document_id: str
    chunk_ids: tuple[str, ...]


class KnowledgeEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str
    document_title: str
    location: str
    text: str
    score: float = Field(ge=0)

    component_id: str | None = None
    component_name: str | None = None

    bucket: str
    key: str
    page_number: int | None = None
    heading_path: tuple[str, ...] = ()


class KnowledgeSearchResponse(BaseModel):
    """Structured result returned by the knowledge search tool."""

    model_config = ConfigDict(frozen=True)
    query: str
    result_count: int = Field(ge=0)
    evidence: tuple[KnowledgeEvidence, ...]
    message: str | None = None


class KnowledgeSearchFilter(BaseModel):
    """Optional metadata restrictions applied during retrieval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    component_ids: tuple[str, ...] = ()
    document_types: tuple[str, ...] = ()
    source_systems: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    include_unclassified: bool = False
