from strands import Agent
from strands.models.openai_responses import OpenAIResponsesModel

from knowledge_intelligence.agents.instructions import (
    CHANGE_IMPACT_ANALYSIS_INSTRUCTIONS,
    KNOWLEDGE_ORCHESTRATOR_INSTRUCTIONS,
    PLATFORM_KNOWLEDGE_AGENT_INSTRUCTIONS,
    REPOSITORY_KNOWLEDGE_AGENT_INSTRUCTIONS,
)


class PlatformKnowledgeAgentFactory:
    """Create independent Platform Knowledge Agent interactions."""

    def __init__(
        self,
        *,
        api_key: str,
        model_id: str,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OpenAI API key cannot be empty.")

        if not model_id.strip():
            raise ValueError("OpenAI model ID cannot be empty.")

        self._model = OpenAIResponsesModel(
            model_id=model_id,
            client_args={
                "api_key": api_key,
            },
        )

    def create(
        self,
        search_tool: object,
        *,
        change_impact_analysis: bool = False,
    ) -> Agent:
        instructions = PLATFORM_KNOWLEDGE_AGENT_INSTRUCTIONS
        if change_impact_analysis:
            instructions = f"{instructions}\n\n{CHANGE_IMPACT_ANALYSIS_INSTRUCTIONS}"
        return Agent(
            model=self._model,
            system_prompt=instructions,
            tools=[search_tool],
        )

    def create_repository_knowledge(
        self,
        repository_search_tool: object,
    ) -> Agent:
        """Create a specialist agent for local repository code evidence."""
        return Agent(
            model=self._model,
            system_prompt=REPOSITORY_KNOWLEDGE_AGENT_INSTRUCTIONS,
            tools=[repository_search_tool],
        )

    def create_orchestrator(self, specialist_tools: list[object]) -> Agent:
        """Create the single entry-point agent for specialist delegation."""
        return Agent(
            model=self._model,
            system_prompt=KNOWLEDGE_ORCHESTRATOR_INSTRUCTIONS,
            tools=specialist_tools,
        )
