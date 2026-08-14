"""Shared data models for ingestion, retrieval, and API responses."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SourceType(StrEnum):
    CONFLUENCE = "confluence"
    GITHUB = "github"
    REGISTRY = "registry"


class ContentBlock(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)
    page_number: int | None = Field(default=None, ge=1)
    heading_path: tuple[str, ...] = ()
    visual_description: bool = False


class ParsedDocument(BaseModel):
    """Normalized representation returned by both supported parsers."""

    model_config = ConfigDict(frozen=True)

    document_id: str
    title: str
    source_type: SourceType
    source_location: str
    component_id: str
    blocks: tuple[ContentBlock, ...]


class Chunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: str
    document_id: str
    title: str
    text: str = Field(min_length=1)
    source_type: SourceType
    source_location: str
    component_id: str
    page_number: int | None = Field(default=None, ge=1)
    heading_path: tuple[str, ...] = ()
    visual_description: bool = False


class SearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str
    chunk: Chunk
    score: float

    @property
    def citation(self) -> str:
        if self.chunk.page_number:
            return f"{self.chunk.title} — Page {self.chunk.page_number}"
        if self.chunk.heading_path:
            return f"{self.chunk.title} — {' > '.join(self.chunk.heading_path)}"
        return self.chunk.title


class SourceCitation(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str
    title: str
    location: str


class KnowledgeAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    answer: str
    visual: str | None = None
    suggested_questions: tuple[str, ...] = ()
    response_type: str = "general"
    sources: tuple[SourceCitation, ...] = ()


class KnowledgeQueryResponse(BaseModel):
    """Public API response; source details remain internal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    answer: str = Field(min_length=1)


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    prompt: str = Field(min_length=3, max_length=4_000)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=200)


class ReindexSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    documents: int = Field(ge=0)
    chunks: int = Field(ge=0)
    vectors: int = Field(ge=0)
    skipped: int = Field(ge=0)


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    vector_store_reachable: bool
    cached_chunks: int = Field(ge=0)


class Repository(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(pattern=r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?$")
    url: str | None = None
    branch: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    purpose: str | None = None


class Component(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str
    description: str
    aliases: tuple[str, ...] = ()
    repositories: tuple[Repository, ...] = ()
    documentation_prefixes: tuple[str, ...] = ()
    owner: str | None = None
    status: str = "active"
