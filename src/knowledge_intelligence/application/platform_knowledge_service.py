import re

from knowledge_intelligence.agents.platform_knowledge import (
    PlatformKnowledgeAgentFactory,
)
from knowledge_intelligence.application.models import (
    KnowledgeAnswer,
    KnowledgeAnswerSource,
    KnowledgeAnswerStatus,
)
from knowledge_intelligence.application.query_context import (
    KnowledgeQueryContext,
)
from knowledge_intelligence.domain.retrieval import KnowledgeSearchFilter
from knowledge_intelligence.tools.knowledge_search import (
    KnowledgeSearchClient,
    create_knowledge_search_tool,
)

INSUFFICIENT_EVIDENCE_PHRASE = (
    "I could not find sufficient information in the currently indexed "
    "platform documentation to answer this reliably."
)


class PlatformKnowledgeService:
    """Execute independent, source-grounded platform knowledge queries."""

    def __init__(
        self,
        *,
        agent_factory: PlatformKnowledgeAgentFactory,
        search_adapter: KnowledgeSearchClient,
    ) -> None:
        self._agent_factory = agent_factory
        self._search_adapter = search_adapter

    def answer(
        self,
        question: str,
        *,
        component_ids: tuple[str, ...] = (),
    ) -> KnowledgeAnswer:
        return self._answer(question, component_ids=component_ids)

    def analyse_change(
        self,
        change_description: str,
        *,
        component_ids: tuple[str, ...],
    ) -> KnowledgeAnswer:
        """Assess documented impact for a proposed change within named components."""
        return self._answer(
            f"Assess the documented impact of this proposed change: {change_description}",
            component_ids=component_ids,
            change_impact_analysis=True,
        )

    def _answer(
        self,
        question: str,
        *,
        component_ids: tuple[str, ...],
        change_impact_analysis: bool = False,
    ) -> KnowledgeAnswer:
        normalized_question = question.strip()

        if not normalized_question:
            raise ValueError("Question cannot be empty.")

        context = KnowledgeQueryContext()

        search_tool = create_knowledge_search_tool(
            adapter=self._search_adapter,
            context=context,
            filters=(
                KnowledgeSearchFilter(
                    component_ids=component_ids,
                    include_unclassified=False,
                )
                if component_ids
                else None
            ),
        )

        agent = self._agent_factory.create(
            search_tool,
            change_impact_analysis=change_impact_analysis,
        )
        result = agent(normalized_question)

        answer = str(result).strip()

        cited_ids = set(re.findall(r"\[(S\d+)]", answer))

        available_sources = {evidence.source_id: evidence for evidence in context.evidence}

        sources = tuple(
            KnowledgeAnswerSource(
                source_id=source_id,
                document_title=available_sources[source_id].document_title,
                location=available_sources[source_id].location,
                key=available_sources[source_id].key,
                page_number=available_sources[source_id].page_number,
                heading_path=available_sources[source_id].heading_path,
            )
            for source_id in sorted(
                cited_ids,
                key=lambda value: int(value[1:]),
            )
            if source_id in available_sources
        )

        insufficient = (
            not context.evidence or INSUFFICIENT_EVIDENCE_PHRASE.lower() in answer.lower()
        )

        return KnowledgeAnswer(
            answer=answer,
            status=(
                KnowledgeAnswerStatus.INSUFFICIENT_EVIDENCE
                if insufficient
                else KnowledgeAnswerStatus.ANSWERED
            ),
            sources=sources,
        )
