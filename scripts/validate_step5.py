from pathlib import Path

from knowledge_intelligence.agents.platform_knowledge import PlatformKnowledgeAgentFactory
from knowledge_intelligence.application.container import build_search_adapter
from knowledge_intelligence.application.platform_knowledge_service import PlatformKnowledgeService
from knowledge_intelligence.config import get_settings
from knowledge_intelligence.evaluation.evaluator import KnowledgeAgentEvaluator
from knowledge_intelligence.evaluation.loader import load_evaluation_dataset
from knowledge_intelligence.evaluation.report import (
    build_summary,
    render_markdown_report,
    write_report,
)
from knowledge_intelligence.evaluation.runner import AgentInvoker, EvaluationRunner
from knowledge_intelligence.evaluation.trace import EvaluationTrace, TracedKnowledgeSearchAdapter


def build_evaluation_application() -> tuple[AgentInvoker, EvaluationTrace]:
    """Build the Platform Knowledge Agent with traced knowledge search."""
    settings = get_settings()
    trace = EvaluationTrace()
    search_adapter, _, _, _ = build_search_adapter(settings)
    traced_search = TracedKnowledgeSearchAdapter(
        adapter=search_adapter,
        trace=trace,
    )
    service = PlatformKnowledgeService(
        agent_factory=PlatformKnowledgeAgentFactory(
            api_key=settings.openai_api_key.get_secret_value(),
            model_id=settings.openai_model,
        ),
        search_adapter=traced_search,
    )

    def invoke(question: str) -> object:
        return service.answer(question).answer

    return invoke, trace


def main() -> None:
    dataset = load_evaluation_dataset(Path("evals/datasets/platform_knowledge.yaml"))

    agent, trace = build_evaluation_application()

    runner = EvaluationRunner(
        agent=agent,
        trace=trace,
        evaluator=KnowledgeAgentEvaluator(),
    )

    results = runner.run_all(dataset.cases)
    summary = build_summary(results)

    report = render_markdown_report(
        results=results,
        summary=summary,
    )

    destination = Path("evals/reports/platform_knowledge.md")
    write_report(report, destination)

    print(report)
    print()
    print(f"Report written to {destination}")


if __name__ == "__main__":
    main()
