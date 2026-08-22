"""Shared data models for ingestion, retrieval, and API responses."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

UNMAPPED_COMPONENT_ID = "unmapped"


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


class MindMapBranch(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str = Field(min_length=1)
    items: tuple[str, ...] = ()


class MindMap(BaseModel):
    model_config = ConfigDict(frozen=True)

    center: str = Field(min_length=1)
    branches: tuple[MindMapBranch, ...] = Field(min_length=2, max_length=6)


class KnowledgeAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    answer: str
    visual: str | None = None
    mindmap: MindMap | None = None
    suggested_questions: tuple[str, ...] = ()
    response_type: str = "general"


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
    unmapped: int = Field(default=0, ge=0)


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    vector_store_reachable: bool
    cached_chunks: int = Field(ge=0)


COMPONENT_ID = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class Repository(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(pattern=r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?$")
    url: str | None = None
    branch: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    purpose: str | None = None


class Contact(BaseModel):
    """Where to send someone who needs help with a component."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    slack: str | None = Field(default=None, pattern=r"^[#@][A-Za-z0-9._-]+$")
    team: str | None = None

    @property
    def route(self) -> str:
        return self.slack or self.name


class Note(BaseModel):
    """Knowledge agreed outside Confluence, captured against a component."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    note: str = Field(min_length=1)
    recorded: date
    source: str | None = None


class RelatedComponent(BaseModel):
    """A directed, registry-declared link to another component."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=COMPONENT_ID)
    relationship: str = Field(min_length=1)


class Component(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=COMPONENT_ID)
    name: str
    description: str
    aliases: tuple[str, ...] = ()
    repositories: tuple[Repository, ...] = ()
    contact: Contact | None = None
    notes: tuple[Note, ...] = ()
    part_of: str | None = Field(default=None, pattern=COMPONENT_ID)
    related: tuple[RelatedComponent, ...] = ()
    documentation_prefixes: tuple[str, ...] = ()
    owner: str | None = None
    status: str = "active"
