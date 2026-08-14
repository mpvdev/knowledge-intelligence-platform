from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

from knowledge_intelligence.evaluation.evaluator import KnowledgeAgentEvaluator
from knowledge_intelligence.evaluation.models import (
    AgentExecution,
    CaseEvaluationResult,
    EvaluationCase,
)
from knowledge_intelligence.evaluation.trace import EvaluationTrace


class AgentInvoker(Protocol):
    def __call__(self, question: str) -> object: ...


@dataclass
class EvaluationRunner:
    """Run evaluation cases against the Platform Knowledge Agent."""

    agent: AgentInvoker
    trace: EvaluationTrace
    evaluator: KnowledgeAgentEvaluator

    def run_case(
        self,
        case: EvaluationCase,
    ) -> CaseEvaluationResult:
        self.trace.reset()

        started = perf_counter()
        result = self.agent(case.question)
        total_latency_ms = (perf_counter() - started) * 1_000

        answer = str(result)

        retrieval_latency_ms = self.trace.retrieval_latency_ms

        execution = AgentExecution(
            case_id=case.id,
            question=case.question,
            answer=answer,
            retrieved_sources=tuple(self.trace.retrieved_sources),
            cited_source_ids=tuple(self.trace.source_ids),
            tool_called=self.trace.tool_called,
            retrieval_latency_ms=retrieval_latency_ms,
            agent_latency_ms=max(
                total_latency_ms - (retrieval_latency_ms or 0),
                0,
            ),
            total_latency_ms=total_latency_ms,
        )

        return self.evaluator.evaluate(
            case=case,
            execution=execution,
        )

    def run_all(
        self,
        cases: tuple[EvaluationCase, ...],
    ) -> tuple[CaseEvaluationResult, ...]:
        return tuple(self.run_case(case) for case in cases)
