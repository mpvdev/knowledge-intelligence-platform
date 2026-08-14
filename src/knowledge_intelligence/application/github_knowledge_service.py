import re

from knowledge_intelligence.agents.github_knowledge import GitHubKnowledgeAgentFactory
from knowledge_intelligence.application.models import (
    KnowledgeAnswerStatus,
    RepositoryKnowledgeAnswer,
)
from knowledge_intelligence.tools.repository_search import (
    RepositoryCodeQueryContext,
    RepositorySearchClient,
    create_repository_search_tool,
)

INSUFFICIENT_GITHUB_EVIDENCE = "I don't have enough repository evidence to answer that reliably."


class GitHubKnowledgeService:
    """Answer one request using read-only, revision-cited GitHub evidence."""

    def __init__(
        self,
        *,
        agent_factory: GitHubKnowledgeAgentFactory,
        search_adapter: RepositorySearchClient,
    ) -> None:
        self._agent_factory = agent_factory
        self._search_adapter = search_adapter

    def answer(self, question: str) -> RepositoryKnowledgeAnswer:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("Question cannot be empty.")

        context = RepositoryCodeQueryContext()
        agent = self._agent_factory.create(
            create_repository_search_tool(adapter=self._search_adapter, context=context)
        )
        answer = str(agent(normalized_question)).strip()
        cited_ids = set(re.findall(r"\[(R\d+)]", answer))
        available = {item.source_id: item for item in context.evidence}
        sources = tuple(
            available[source_id]
            for source_id in sorted(cited_ids, key=lambda value: int(value[1:]))
            if source_id in available
        )
        insufficient = not sources or (INSUFFICIENT_GITHUB_EVIDENCE.casefold() in answer.casefold())
        return RepositoryKnowledgeAnswer(
            answer=answer,
            status=(
                KnowledgeAnswerStatus.INSUFFICIENT_EVIDENCE
                if insufficient
                else KnowledgeAnswerStatus.ANSWERED
            ),
            sources=sources,
        )
