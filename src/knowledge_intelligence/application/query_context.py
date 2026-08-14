from dataclasses import dataclass, field

from knowledge_intelligence.domain.retrieval import KnowledgeEvidence


@dataclass
class KnowledgeQueryContext:
    """Request-scoped evidence captured during an agent interaction."""

    evidence: list[KnowledgeEvidence] = field(default_factory=list)

    def record(
        self,
        items: tuple[KnowledgeEvidence, ...],
    ) -> None:
        self.evidence.extend(items)
