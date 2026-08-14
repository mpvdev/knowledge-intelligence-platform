from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from knowledge_intelligence.domain.repository_knowledge import RepositoryCodeEvidence


class KnowledgeAnswerStatus(StrEnum):
    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class KnowledgeAnswerSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str
    document_title: str
    location: str
    key: str
    page_number: int | None = None
    heading_path: tuple[str, ...] = ()


class KnowledgeAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    answer: str
    status: KnowledgeAnswerStatus
    sources: tuple[KnowledgeAnswerSource, ...]


class RoutedKnowledgeAnswer(BaseModel):
    """A unified answer produced by one or more knowledge specialists."""

    model_config = ConfigDict(frozen=True)

    answer: str
    status: KnowledgeAnswerStatus
    documentation_sources: tuple[KnowledgeAnswerSource, ...]
    code_sources: tuple[RepositoryCodeEvidence, ...]


class RepositoryKnowledgeAnswer(BaseModel):
    """A grounded answer produced by a repository specialist."""

    model_config = ConfigDict(frozen=True)

    answer: str
    status: KnowledgeAnswerStatus
    sources: tuple[RepositoryCodeEvidence, ...]
