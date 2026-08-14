from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from knowledge_intelligence.application.models import (
    KnowledgeAnswerSource,
    KnowledgeAnswerStatus,
)
from knowledge_intelligence.domain.repository_knowledge import RepositoryCodeEvidence

ComponentId = Annotated[
    str,
    Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
]


class KnowledgeQueryRequest(BaseModel):
    """Prompt-only request for routed platform and repository knowledge."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    prompt: str = Field(
        min_length=3,
        max_length=4_000,
        description="Natural-language knowledge question.",
    )


class KnowledgeQueryResponse(BaseModel):
    """End-user answer returned by the public API."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    answer: str = Field(min_length=1)
    status: KnowledgeAnswerStatus
    documentation_sources: tuple[KnowledgeAnswerSource, ...]
    code_sources: tuple[RepositoryCodeEvidence, ...]


class ChangeImpactRequest(BaseModel):
    """A proposed component change to assess against approved documentation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    change_description: str = Field(min_length=10, max_length=4_000)
    component_ids: tuple[ComponentId, ...] = Field(min_length=1, max_length=20)

    @field_validator("component_ids")
    @classmethod
    def component_ids_must_be_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(values)) != len(values):
            raise ValueError("component_ids must not contain duplicates.")
        return values


class ChangeImpactResponse(BaseModel):
    """Grounded impact assessment and its resolved source locations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis: str = Field(min_length=1)
    status: KnowledgeAnswerStatus
    sources: tuple[KnowledgeAnswerSource, ...]


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str
    knowledge_index_ready: bool
    indexed_chunk_count: int = Field(ge=0)
    vector_retrieval_configured: bool = False
    vector_retrieval_reachable: bool = False


class ErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    error: str
    message: str
    correlation_id: str
