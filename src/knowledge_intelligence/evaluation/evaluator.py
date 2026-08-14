from knowledge_intelligence.evaluation.models import (
    AgentExecution,
    CaseEvaluationResult,
    EvaluationCase,
    MetricResult,
)

REFUSAL_MARKERS = (
    "cannot answer",
    "can't answer",
    "do not have enough information",
    "don't have enough information",
    "no relevant evidence",
    "not documented",
)


class KnowledgeAgentEvaluator:
    """Score an agent execution against deterministic case expectations."""

    def evaluate(
        self,
        case: EvaluationCase,
        execution: AgentExecution,
    ) -> CaseEvaluationResult:
        answer = execution.answer.casefold()
        retrieved = set(execution.retrieved_sources)
        expected = set(case.expected_sources)

        metrics = (
            self._metric(
                "expected_sources",
                expected.issubset(retrieved) and len(retrieved) >= case.minimum_expected_sources,
                f"expected {sorted(expected)!r}; retrieved {sorted(retrieved)!r}",
            ),
            self._metric(
                "expected_keywords",
                all(keyword.casefold() in answer for keyword in case.expected_keywords),
                f"expected keywords: {list(case.expected_keywords)!r}",
            ),
            self._metric(
                "forbidden_keywords",
                not any(keyword.casefold() in answer for keyword in case.forbidden_keywords),
                f"forbidden keywords: {list(case.forbidden_keywords)!r}",
            ),
            self._metric(
                "citations",
                not case.require_citations or bool(execution.cited_source_ids),
                f"citation count: {len(execution.cited_source_ids)}",
            ),
            self._metric(
                "refusal",
                not case.expect_refusal or any(marker in answer for marker in REFUSAL_MARKERS),
                f"refusal expected: {case.expect_refusal}",
            ),
            self._metric(
                "tool_usage",
                not case.require_tool_call or execution.tool_called,
                f"tool call required: {case.require_tool_call}; called: {execution.tool_called}",
            ),
        )
        return CaseEvaluationResult(case=case, execution=execution, metrics=metrics)

    @staticmethod
    def _metric(name: str, passed: bool, details: str) -> MetricResult:
        return MetricResult(name=name, passed=passed, details=details)
