from strands import Agent
from strands.models.openai_responses import OpenAIResponsesModel

from knowledge_intelligence.agents.instructions import GITHUB_KNOWLEDGE_AGENT_INSTRUCTIONS


class GitHubKnowledgeAgentFactory:
    """Create independent, read-only GitHub Knowledge Agent interactions."""

    def __init__(self, *, api_key: str, model_id: str) -> None:
        if not api_key.strip() or not model_id.strip():
            raise ValueError("OpenAI API key and model ID are required.")
        self._model = OpenAIResponsesModel(
            model_id=model_id,
            client_args={"api_key": api_key},
        )

    def create(self, search_tool: object) -> Agent:
        return Agent(
            model=self._model,
            system_prompt=GITHUB_KNOWLEDGE_AGENT_INSTRUCTIONS,
            tools=[search_tool],
        )
