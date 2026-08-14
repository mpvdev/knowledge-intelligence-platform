from dataclasses import dataclass, field
from time import perf_counter

from knowledge_intelligence.domain.retrieval import KnowledgeSearchFilter, KnowledgeSearchResponse
from knowledge_intelligence.tools.knowledge_search import KnowledgeSearchClient


@dataclass
class EvaluationTrace:
    """Mutable execution trace used only for evaluation."""

    tool_called: bool = False
    retrieved_sources: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    retrieval_latency_ms: float | None = None

    def reset(self) -> None:
        self.tool_called = False
        self.retrieved_sources.clear()
        self.source_ids.clear()
        self.retrieval_latency_ms = None


class TracedKnowledgeSearchAdapter:
    """Capture retrieval activity while delegating normal search behaviour."""

    def __init__(
        self,
        adapter: KnowledgeSearchClient,
        trace: EvaluationTrace,
    ) -> None:
        self._adapter = adapter
        self._trace = trace

    def search(
        self,
        query: str,
        limit: int = 5,
        filters: KnowledgeSearchFilter | None = None,
    ) -> KnowledgeSearchResponse:
        self._trace.tool_called = True

        started = perf_counter()

        response = self._adapter.search(
            query=query,
            limit=limit,
            filters=filters,
        )

        self._trace.retrieval_latency_ms = (perf_counter() - started) * 1_000

        self._trace.retrieved_sources.extend(evidence.key for evidence in response.evidence)

        self._trace.source_ids.extend(evidence.source_id for evidence in response.evidence)

        return response
