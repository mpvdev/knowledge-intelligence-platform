"""One entry point that routes questions to grounded knowledge specialists."""

import re
from dataclasses import dataclass
from pathlib import Path

from strands import tool
from strands.types.tools import AgentTool

from knowledge_intelligence.agents.github_knowledge import GitHubKnowledgeAgentFactory
from knowledge_intelligence.agents.platform_knowledge import PlatformKnowledgeAgentFactory
from knowledge_intelligence.application.models import (
    KnowledgeAnswerSource,
    KnowledgeAnswerStatus,
    RoutedKnowledgeAnswer,
)
from knowledge_intelligence.application.query_context import KnowledgeQueryContext
from knowledge_intelligence.connectors.local_repository import LocalRepositoryReader
from knowledge_intelligence.domain.repository_knowledge import RepositoryCodeEvidence
from knowledge_intelligence.registry.registry import ComponentRegistry
from knowledge_intelligence.retrieval.repository_search import RepositoryCodeSearchService
from knowledge_intelligence.retrieval.tokenizer import SearchTokenizer
from knowledge_intelligence.tools.knowledge_search import (
    KnowledgeSearchClient,
    create_knowledge_search_tool,
)
from knowledge_intelligence.tools.repository_search import (
    RepositoryCodeQueryContext,
    RepositorySearchAdapter,
    RepositorySearchClient,
    create_repository_search_tool,
)

INSUFFICIENT_PLATFORM_EVIDENCE = "I could not find sufficient information"
INSUFFICIENT_REPOSITORY_EVIDENCE = "not established by the retrieved code"


@dataclass(frozen=True)
class _RepositorySelection:
    repository_name: str
    local_path: str


class UnifiedKnowledgeService:
    """Route a question to platform and optional local-repository specialists."""

    def __init__(
        self,
        *,
        agent_factory: PlatformKnowledgeAgentFactory,
        platform_search: KnowledgeSearchClient,
        repository_root: Path | None = None,
        registry: ComponentRegistry | None = None,
        repository_reader: LocalRepositoryReader | None = None,
        github_agent_factory: GitHubKnowledgeAgentFactory | None = None,
        github_search: RepositorySearchClient | None = None,
    ) -> None:
        self._agent_factory = agent_factory
        self._platform_search = platform_search
        self._repository_root = repository_root
        self._registry = registry
        self._repository_reader = repository_reader
        self._github_agent_factory = github_agent_factory
        self._github_search = github_search

    def answer(
        self,
        question: str,
    ) -> RoutedKnowledgeAnswer:
        """Answer using the specialist or specialists applicable to this request."""
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("Question cannot be empty.")

        platform_context = KnowledgeQueryContext()
        platform_agent = self._agent_factory.create(
            create_knowledge_search_tool(
                adapter=self._platform_search,
                context=platform_context,
            )
        )
        specialist_tools: list[object] = [
            platform_agent.as_tool(
                name="platform_knowledge_specialist",
                description=(
                    "Answer platform and Confluence documentation questions with [S#] citations."
                ),
            )
        ]

        repository_context = RepositoryCodeQueryContext()
        github_tool = self._github_specialist_tool(context=repository_context)
        if github_tool is not None:
            specialist_tools.append(github_tool)
        repository_selections = self._select_repositories(normalized_question)
        if (
            repository_selections
            and self._requests_repository_analysis(normalized_question)
            and not self._requests_github_analysis(normalized_question)
        ):
            repository_answer = self._answer_repositories(
                question=normalized_question,
                selections=repository_selections,
                context=repository_context,
            )
            if self._requests_documentation_alignment(normalized_question):
                platform_answer = str(platform_agent(normalized_question)).strip()
                answer = self._combine_specialist_answers(
                    repository_answer,
                    platform_answer,
                )
            else:
                answer = repository_answer
        else:
            repository_tool = self._repository_specialist_tool(context=repository_context)
            if repository_tool is not None:
                specialist_tools.append(repository_tool)
            agent = self._agent_factory.create_orchestrator(specialist_tools)
            answer = str(agent(normalized_question)).strip()
        documentation_sources = self._documentation_sources(answer, platform_context)
        code_sources = self._code_sources(answer, repository_context)
        insufficient = (
            (not documentation_sources and not code_sources)
            or INSUFFICIENT_PLATFORM_EVIDENCE.casefold() in answer.casefold()
            or INSUFFICIENT_REPOSITORY_EVIDENCE in answer.casefold()
        )
        return RoutedKnowledgeAnswer(
            answer=answer,
            status=(
                KnowledgeAnswerStatus.INSUFFICIENT_EVIDENCE
                if insufficient
                else KnowledgeAnswerStatus.ANSWERED
            ),
            documentation_sources=documentation_sources,
            code_sources=code_sources,
        )

    def _github_specialist_tool(
        self,
        *,
        context: RepositoryCodeQueryContext,
    ) -> AgentTool | None:
        factory = self._github_agent_factory
        search = self._github_search
        if factory is None or search is None:
            return None

        agent = factory.create(create_repository_search_tool(adapter=search, context=context))
        return agent.as_tool(
            name="github_knowledge_specialist",
            description=(
                "Answer questions about approved GitHub repository code using revision-cited "
                "read-only evidence."
            ),
        )

    def _repository_specialist_tool(
        self,
        *,
        context: RepositoryCodeQueryContext,
    ) -> AgentTool | None:
        repository_root = self._repository_root
        repository_reader = self._repository_reader
        if repository_root is None or self._registry is None or repository_reader is None:
            return None

        @tool
        def repository_knowledge_specialist(question: str) -> str:
            """Answer a local-code question by selecting a registered repository from the prompt."""
            selections = self._select_repositories(question)
            if not selections:
                return self._repository_selection_guidance()
            return self._answer_repositories(
                question=question,
                selections=selections,
                context=context,
            )

        return repository_knowledge_specialist

    def _answer_repositories(
        self,
        *,
        question: str,
        selections: tuple[_RepositorySelection, ...],
        context: RepositoryCodeQueryContext,
    ) -> str:
        """Run the focused code specialist for each selected local repository."""
        repository_root = self._repository_root
        repository_reader = self._repository_reader
        if repository_root is None or repository_reader is None:
            return "Local repository knowledge is not available for this request."

        answers: list[str] = []
        for selection in selections:
            repository_path = (repository_root / selection.local_path).resolve()
            if (
                not repository_path.is_relative_to(repository_root.resolve())
                or not repository_path.is_dir()
            ):
                continue

            files = repository_reader.read(repository_path)
            repository_agent = self._agent_factory.create_repository_knowledge(
                create_repository_search_tool(
                    adapter=RepositorySearchAdapter(
                        repository_name=selection.repository_name,
                        search_service=RepositoryCodeSearchService(
                            selection.repository_name,
                            files,
                            SearchTokenizer(),
                        ),
                    ),
                    context=context,
                ),
            )
            repository_answer = str(
                repository_agent(f"For repository {selection.repository_name}: {question}")
            ).strip()
            answers.append(f"## {selection.repository_name}\n\n{repository_answer}")
        if not answers:
            return (
                "The registry matched the product area, but no corresponding local "
                "repository clone is available on this environment."
            )
        return "\n\n".join(answers)

    @staticmethod
    def _requests_repository_analysis(question: str) -> bool:
        return bool(
            re.search(
                r"\b(code|implementation|implemented|repository|repositories|source|"
                r"terraform|cloudformation|lambda|module|configuration|codebase)\b",
                question,
                flags=re.IGNORECASE,
            )
        )

    @staticmethod
    def _requests_github_analysis(question: str) -> bool:
        return bool(re.search(r"\bgithub\b", question, flags=re.IGNORECASE))

    @staticmethod
    def _requests_documentation_alignment(question: str) -> bool:
        return bool(
            re.search(
                r"\b(align|alignment|confluence|documentation|documented|compare)\b",
                question,
                flags=re.IGNORECASE,
            )
        )

    @staticmethod
    def _combine_specialist_answers(
        repository_answer: str,
        platform_answer: str,
    ) -> str:
        return "\n\n".join(
            (
                UnifiedKnowledgeService._without_sources(repository_answer),
                "## Platform documentation\n\n"
                f"{UnifiedKnowledgeService._without_sources(platform_answer)}",
            )
        )

    @staticmethod
    def _without_sources(answer: str) -> str:
        lines: list[str] = []
        for line in answer.splitlines():
            if line.strip().lstrip("#").strip().casefold() == "sources":
                break
            lines.append(line)
        return "\n".join(lines).strip()

    def _select_repositories(self, question: str) -> tuple[_RepositorySelection, ...]:
        """Resolve registered repositories from natural-language input."""
        if self._registry is None:
            return ()

        normalized_question = self._normalize_for_match(question)
        direct_matches = tuple(
            _RepositorySelection(
                repository_name=repository.name,
                local_path=repository.local_path or repository.name,
            )
            for component in self._registry.list_components()
            for repository in component.repositories
            if self._normalize_for_match(repository.name) in normalized_question
        )
        if direct_matches:
            return direct_matches

        component_matches = tuple(
            component
            for component in self._registry.list_components()
            if any(
                self._normalize_for_match(value) in normalized_question
                for value in (component.id, component.name, *component.aliases)
            )
        )
        if len(component_matches) != 1:
            return ()

        return tuple(
            _RepositorySelection(
                repository_name=repository.name,
                local_path=repository.local_path or repository.name,
            )
            for component in component_matches
            for repository in component.repositories
        )

    def _repository_selection_guidance(self) -> str:
        """Give a plain-language clarification without exposing an API contract."""
        if self._registry is None:
            return "Local repository knowledge is not available for this request."

        component_names = ", ".join(
            component.name
            for component in self._registry.list_components()
            if component.repositories
        )
        return (
            "I could not identify one local repository from the question. "
            "Please mention the repository or the product area in plain language. "
            f"Available product areas include: {component_names}."
        )

    @staticmethod
    def _normalize_for_match(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.casefold())

    @staticmethod
    def _documentation_sources(
        answer: str,
        context: KnowledgeQueryContext,
    ) -> tuple[KnowledgeAnswerSource, ...]:
        cited = set(re.findall(r"\[(S\d+)]", answer))
        available = {item.source_id: item for item in context.evidence}
        return tuple(
            KnowledgeAnswerSource(
                source_id=source_id,
                document_title=available[source_id].document_title,
                location=available[source_id].location,
                key=available[source_id].key,
                page_number=available[source_id].page_number,
                heading_path=available[source_id].heading_path,
            )
            for source_id in sorted(cited, key=lambda value: int(value[1:]))
            if source_id in available
        )

    @staticmethod
    def _code_sources(
        answer: str,
        context: RepositoryCodeQueryContext | None,
    ) -> tuple[RepositoryCodeEvidence, ...]:
        if context is None:
            return ()
        cited = set(re.findall(r"\[(R\d+)]", answer))
        available = {item.source_id: item for item in context.evidence}
        return tuple(
            available[source_id]
            for source_id in sorted(cited, key=lambda value: int(value[1:]))
            if source_id in available
        )
