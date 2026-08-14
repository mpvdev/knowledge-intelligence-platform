from pathlib import Path

from knowledge_intelligence.evaluation.models import (
    CaseEvaluationResult,
    EvaluationSummary,
)


def build_summary(
    results: tuple[CaseEvaluationResult, ...],
) -> EvaluationSummary:
    total = len(results)
    passed = sum(result.passed for result in results)
    failed = total - passed

    def metric_accuracy(metric_name: str) -> float:
        relevant = [
            metric for result in results for metric in result.metrics if metric.name == metric_name
        ]

        if not relevant:
            return 1.0

        return sum(metric.passed for metric in relevant) / len(relevant)

    average_latency = (
        sum(result.execution.total_latency_ms for result in results) / total if total else 0.0
    )

    return EvaluationSummary(
        total_cases=total,
        passed_cases=passed,
        failed_cases=failed,
        pass_rate=passed / total if total else 1.0,
        retrieval_accuracy=metric_accuracy("expected_sources"),
        citation_accuracy=metric_accuracy("citations"),
        refusal_accuracy=metric_accuracy("refusal"),
        tool_usage_accuracy=metric_accuracy("tool_usage"),
        average_latency_ms=average_latency,
    )


def render_markdown_report(
    results: tuple[CaseEvaluationResult, ...],
    summary: EvaluationSummary,
) -> str:
    lines = [
        "# Platform Knowledge Evaluation",
        "",
        "## Summary",
        "",
        f"- Total cases: {summary.total_cases}",
        f"- Passed: {summary.passed_cases}",
        f"- Failed: {summary.failed_cases}",
        f"- Pass rate: {summary.pass_rate:.1%}",
        f"- Retrieval accuracy: {summary.retrieval_accuracy:.1%}",
        f"- Citation accuracy: {summary.citation_accuracy:.1%}",
        f"- Refusal accuracy: {summary.refusal_accuracy:.1%}",
        f"- Tool usage accuracy: {summary.tool_usage_accuracy:.1%}",
        f"- Average latency: {summary.average_latency_ms:.0f} ms",
        "",
        "## Cases",
        "",
    ]

    for result in results:
        state = "PASS" if result.passed else "FAIL"

        lines.extend(
            [
                f"### {state} — {result.case.id}",
                "",
                f"**Question:** {result.case.question}",
                "",
                f"**Latency:** {result.execution.total_latency_ms:.0f} ms",
                "",
                "**Metrics:**",
            ]
        )

        for metric in result.metrics:
            marker = "✅" if metric.passed else "❌"
            lines.append(f"- {marker} `{metric.name}`: {metric.details}")

        lines.extend(
            [
                "",
                "**Answer:**",
                "",
                result.execution.answer,
                "",
            ]
        )

    return "\n".join(lines)


def write_report(
    report: str,
    destination: Path,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report, encoding="utf-8")
