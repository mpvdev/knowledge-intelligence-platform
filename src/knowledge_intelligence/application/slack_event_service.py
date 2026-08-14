import logging
import re
from dataclasses import dataclass

from knowledge_intelligence.application.answer_presentation import format_public_answer
from knowledge_intelligence.application.models import KnowledgeAnswer
from knowledge_intelligence.application.platform_knowledge_service import (
    PlatformKnowledgeService,
)
from knowledge_intelligence.connectors.slack.client import (
    SlackMessageClient,
)
from knowledge_intelligence.connectors.slack.models import (
    SlackCommandRequest,
    SlackKnowledgeRequest,
)

MENTION_PATTERN = re.compile(r"<@[A-Z0-9]+>")
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SlackEventService:
    """Process Slack questions using the Platform Knowledge capability."""

    knowledge_service: PlatformKnowledgeService
    slack_client: SlackMessageClient
    maximum_message_length: int = 3_500

    def process(self, request: SlackKnowledgeRequest) -> None:
        question = self._clean_question(request.text)

        if not question:
            self.slack_client.post_thread_reply(
                channel_id=request.channel_id,
                thread_ts=request.thread_ts,
                text=("Please include a platform knowledge question after mentioning me."),
            )
            return

        self.slack_client.post_thread_reply(
            channel_id=request.channel_id,
            thread_ts=request.thread_ts,
            text=self._answer(question),
        )

    def process_command(self, request: SlackCommandRequest) -> None:
        """Process a slash command after its immediate acknowledgement."""
        question = self._clean_question(request.text)
        response = (
            self._answer(question)
            if question
            else "Please include a platform knowledge question after the command."
        )

        self.slack_client.post_command_response(
            response_url=request.response_url.get_secret_value(),
            text=response,
        )

    def _answer(self, question: str) -> str:
        try:
            result = self.knowledge_service.answer(question)
            response = self._format_answer(result)
        except Exception:
            LOGGER.exception(
                "Slack knowledge request processing failed.",
                extra={
                    "component": "slack_event_service",
                    "operation": "answer_platform_question",
                },
            )
            response = (
                "I could not process the platform knowledge request. "
                "Please try again or contact the platform team if the issue "
                "continues."
            )

        return self._truncate(response)

    @staticmethod
    def _clean_question(text: str) -> str:
        without_mentions = MENTION_PATTERN.sub("", text)
        return " ".join(without_mentions.split()).strip()

    @staticmethod
    def _format_answer(result: KnowledgeAnswer) -> str:
        """Create a concise Slack view while retaining full internal evidence."""
        return format_public_answer(result.answer)

    def _truncate(self, text: str) -> str:
        if len(text) <= self.maximum_message_length:
            return text

        suffix = "\n\n_Response truncated._"
        available = self.maximum_message_length - len(suffix)

        return text[:available].rstrip() + suffix
