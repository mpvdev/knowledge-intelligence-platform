from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EvaluationCategory(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    AMBIGUOUS = "ambiguous"
    CONFLICTING = "conflicting"


class EvaluationCase(BaseModel):
    """One expected-behaviour case for the knowledge agent."""

    model_config = ConfigDict(frozen=True)

    id: str
    category: EvaluationCategory
    question: str

    expected_sources: tuple[str, ...] = ()
    expected_keywords: tuple[str, ...] = ()
    forbidden_keywords: tuple[str, ...] = ()

    minimum_expected_sources: int = Field(default=0, ge=0)

    expect_refusal: bool = False
    require_tool_call: bool = True
    require_citations: bool = True


class AgentExecution(BaseModel):
    """Captured output from one agent evaluation run."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    question: str
    answer: str

    retrieved_sources: tuple[str, ...] = ()
    cited_source_ids: tuple[str, ...] = ()
    tool_called: bool = False

    retrieval_latency_ms: float | None = Field(default=None, ge=0)
    agent_latency_ms: float = Field(ge=0)
    total_latency_ms: float = Field(ge=0)


class MetricResult(BaseModel):
    """Result for one evaluated condition."""

    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    details: str


class CaseEvaluationResult(BaseModel):
    """Combined evaluation result for one dataset case."""

    model_config = ConfigDict(frozen=True)

    case: EvaluationCase
    execution: AgentExecution
    metrics: tuple[MetricResult, ...]

    @property
    def passed(self) -> bool:
        return all(metric.passed for metric in self.metrics)


class EvaluationSummary(BaseModel):
    """Aggregated results for one evaluation run."""

    model_config = ConfigDict(frozen=True)

    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)

    pass_rate: float = Field(ge=0, le=1)

    retrieval_accuracy: float = Field(ge=0, le=1)
    citation_accuracy: float = Field(ge=0, le=1)
    refusal_accuracy: float = Field(ge=0, le=1)
    tool_usage_accuracy: float = Field(ge=0, le=1)

    average_latency_ms: float = Field(ge=0)
