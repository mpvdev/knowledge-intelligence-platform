from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.webhook import WebhookClient


class SlackClientError(Exception):
    """Raised when posting a Slack response fails."""


class SlackMessageClient:
    """Send messages through the Slack Web API."""

    def __init__(self, bot_token: str) -> None:
        if not bot_token.strip():
            raise ValueError("Slack bot token cannot be empty.")

        self._client = WebClient(token=bot_token)

    def post_thread_reply(
        self,
        *,
        channel_id: str,
        thread_ts: str,
        text: str,
    ) -> None:
        try:
            self._client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=text,
                unfurl_links=False,
                unfurl_media=False,
            )
        except SlackApiError as exc:
            raise SlackClientError(
                f"Unable to post Slack response to channel {channel_id!r}."
            ) from exc

    @staticmethod
    def post_command_response(*, response_url: str, text: str) -> None:
        """Send a delayed response through a slash command's private webhook."""
        response = WebhookClient(response_url).send(
            text=text,
            response_type="ephemeral",
        )
        if response.status_code >= 400 or response.body != "ok":
            raise SlackClientError("Unable to deliver the Slack command response.")
