from typing import Any

from pydantic import BaseModel, ConfigDict, SecretStr


class SlackEventEnvelope(BaseModel):
    """Subset of the Slack Events API envelope used by the application."""

    model_config = ConfigDict(extra="allow")

    type: str
    event_id: str | None = None
    challenge: str | None = None
    event: dict[str, Any] | None = None


class SlackKnowledgeRequest(BaseModel):
    """Normalized Slack question passed into the application layer."""

    channel_id: str
    text: str
    thread_ts: str


class SlackCommandRequest(BaseModel):
    """Normalized slash command passed into the application layer."""

    text: str
    response_url: SecretStr
