"""Slack conversation, presentation, and privacy-safe feedback."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import UUID, uuid4

import boto3
import httpx
from botocore.exceptions import BotoCoreError, ClientError
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier

from app.agent import PlatformKnowledgeAgent, public_answer
from app.diagram import render_flow
from app.models import KnowledgeAnswer

LOGGER = logging.getLogger(__name__)
MENTION = re.compile(r"<@[A-Z0-9]+>")
FEEDBACK_RATINGS = frozenset({"helpful", "partial", "not_helpful"})


@dataclass(frozen=True)
class SlackAction:
    kind: str
    channel: str | None = None
    thread_ts: str | None = None
    question: str | None = None
    answer_id: str | None = None
    response_type: str | None = None
    rating: str | None = None


class FeedbackStore:
    def __init__(self, *, region: str, bucket: str, prefix: str) -> None:
        self.client = boto3.client("s3", region_name=region)
        self.bucket = bucket
        self.prefix = prefix.strip("/")

    def record(self, action: SlackAction) -> None:
        if (
            not action.answer_id
            or not action.response_type
            or action.rating not in FEEDBACK_RATINGS
        ):
            return
        try:
            UUID(action.answer_id)
            recorded_at = datetime.now(UTC)
            key = (
                f"{self.prefix}/{recorded_at:%Y/%m/%d}/"
                f"{action.answer_id}-{uuid4()}.json"
            )
            payload = {
                "answer_id": action.answer_id,
                "response_type": action.response_type,
                "rating": action.rating,
                "recorded_at": recorded_at.isoformat(),
            }
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(payload, separators=(",", ":")).encode(),
                ContentType="application/json",
            )
        except (ValueError, BotoCoreError, ClientError):
            LOGGER.exception(
                "Slack feedback persistence failed.",
                extra={"operation": "record_feedback", "component": "slack"},
            )


class SlackIntegration:
    def __init__(
        self,
        *,
        bot_token: str,
        signing_secret: str,
        agent: PlatformKnowledgeAgent,
        maximum_message_length: int,
        feedback_store: FeedbackStore,
        streaming_enabled: bool = True,
    ) -> None:
        self.client = WebClient(token=bot_token)
        self.verifier = SignatureVerifier(signing_secret=signing_secret)
        self.agent = agent
        self.maximum_message_length = maximum_message_length
        self.streaming_enabled = streaming_enabled
        self.feedback_store = feedback_store
        self._events: dict[str, datetime] = {}
        self._lock = Lock()

    def verify(self, body: bytes, timestamp: str | None, signature: str | None) -> bool:
        return bool(
            timestamp
            and signature
            and self.verifier.is_valid(
                body=body, timestamp=timestamp, signature=signature
            )
        )

    def accept(self, event_id: str) -> bool:
        now = datetime.now(UTC)
        with self._lock:
            self._events = {
                key: recorded
                for key, recorded in self._events.items()
                if now - recorded <= timedelta(minutes=10)
            }
            if event_id in self._events:
                return False
            self._events[event_id] = now
            return True

    def process(self, channel: str, thread_ts: str, text: str) -> None:
        question = " ".join(MENTION.sub("", text).split()).strip()
        if not question:
            self._post(
                channel,
                thread_ts,
                (
                    "Hi 👋 What would you like to know about TME? "
                    "You can ask about its services, how things work, "
                    "onboarding, prerequisites, or where to find guidance."
                ),
                (),
            )
            return
        progress_ts = self._post(
            channel,
            thread_ts,
            "Got it 👋 I’m looking into that now…",
            (),
        )
        partial_update = (
            self._partial_updater(channel, progress_ts)
            if progress_ts and self.streaming_enabled
            else None
        )
        answer, blocks, visual = self._answer(
            question,
            conversation_id=f"{channel}:{thread_ts}",
            on_partial=partial_update,
        )
        if progress_ts:
            self._update(channel, progress_ts, answer, blocks)
        else:
            self._post(channel, thread_ts, answer, blocks)
        if visual:
            self._upload_diagram(channel, thread_ts, visual)

    def process_slash(
        self,
        question: str,
        response_url: str,
        conversation_id: str,
    ) -> None:
        answer, blocks, _ = self._answer(question, conversation_id=conversation_id)
        payload: dict[str, object] = {
            "response_type": "in_channel",
            "replace_original": False,
            "text": answer,
        }
        if blocks:
            payload["blocks"] = list(blocks)
        try:
            response = httpx.post(
                response_url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            LOGGER.exception(
                "Slack slash-command response delivery failed.",
                extra={"operation": "respond_to_command", "component": "slack"},
            )

    def _partial_updater(self, channel: str, timestamp: str) -> Callable[[str], None]:
        """Return a callback that grows the placeholder message as text arrives."""

        def update(text: str) -> None:
            self._update(channel, timestamp, _streaming_preview(text), ())

        return update

    def _answer(
        self,
        question: str,
        *,
        conversation_id: str,
        on_partial: Callable[[str], None] | None = None,
    ) -> tuple[str, tuple[dict[str, object], ...], str | None]:
        try:
            if on_partial is not None:
                result = self.agent.answer_stream(
                    question,
                    conversation_id=conversation_id,
                    on_partial=on_partial,
                )
            else:
                result = self.agent.answer(question, conversation_id=conversation_id)
            answer = public_answer(result.answer)
            blocks = self._blocks(result, answer)
            visual = result.visual
        except Exception:
            LOGGER.exception(
                "Slack knowledge request failed.",
                extra={"operation": "answer", "component": "slack"},
            )
            answer = "I could not process that request. Please try again."
            blocks = ()
            visual = None
        return answer, blocks, visual

    def _upload_diagram(self, channel: str, thread_ts: str, visual: str) -> None:
        try:
            self.client.files_upload_v2(
                channel=channel,
                thread_ts=thread_ts,
                file=render_flow(visual),
                filename="tme-high-level-view.png",
                title="TME high-level view",
            )
        except SlackApiError as exc:
            LOGGER.exception(
                "Slack diagram upload failed.",
                extra={
                    "operation": "upload_diagram",
                    "component": "slack",
                    "slack_error": _slack_error_code(exc),
                },
            )

    def parse_action(self, payload: dict[str, object]) -> SlackAction | None:
        actions = payload.get("actions")
        if (
            not isinstance(actions, list)
            or not actions
            or not isinstance(actions[0], dict)
        ):
            return None
        action_id = actions[0].get("action_id")
        value = actions[0].get("value")
        if not isinstance(action_id, str) or not isinstance(value, str):
            return None
        if action_id.startswith("knowledge_followup_"):
            channel = _nested_string(payload, "channel", "id") or _nested_string(
                payload, "container", "channel_id"
            )
            thread_ts = _nested_string(
                payload, "message", "thread_ts"
            ) or _nested_string(payload, "container", "message_ts")
            if channel and thread_ts and value.strip():
                return SlackAction(
                    kind="followup",
                    channel=channel,
                    thread_ts=thread_ts,
                    question=value.strip(),
                )
            return None
        if action_id.startswith("knowledge_feedback_"):
            parts = value.split(":", maxsplit=2)
            if len(parts) == 3 and parts[2] in FEEDBACK_RATINGS:
                return SlackAction(
                    kind="feedback",
                    answer_id=parts[0],
                    response_type=parts[1],
                    rating=parts[2],
                )
        return None

    def _blocks(
        self,
        result: KnowledgeAnswer,
        answer: str,
    ) -> tuple[dict[str, object], ...]:
        answer_id = str(uuid4())
        display_answer = (
            answer if len(answer) <= 2_900 else f"{answer[:2_876].rstrip()}…"
        )
        blocks: list[dict[str, object]] = []
        response_title = {
            "onboarding": "👋 Welcome to TME",
            "comparison": "Service comparison",
            "mapping": "Connected knowledge map",
        }.get(result.response_type)
        if response_title:
            blocks.append(
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": response_title},
                }
            )
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": display_answer},
            }
        )
        if result.visual:
            visual_title = (
                "Journey overview"
                if result.response_type == "onboarding"
                else "High-level view"
            )
            blocks.extend(_visual_blocks(visual_title, result.visual))
        suggestions = tuple(
            public_answer(question)
            for question in result.suggested_questions
            if public_answer(question)
        )
        if suggestions:
            suggestion_title = (
                "*Choose your next onboarding step:*"
                if result.response_type == "onboarding"
                else "*You may also want to know:*"
            )
            blocks.extend(
                (
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": suggestion_title,
                            }
                        ],
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "action_id": f"knowledge_followup_{position}",
                                "text": {
                                    "type": "plain_text",
                                    "text": _button_text(question),
                                },
                                "value": question[:2_000],
                            }
                            for position, question in enumerate(suggestions, start=1)
                        ],
                    },
                )
            )
        blocks.extend(
            (
                {"type": "divider"},
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": "Was this answer helpful?"}
                    ],
                },
                {
                    "type": "actions",
                    "elements": [
                        _feedback_button(
                            answer_id,
                            result.response_type,
                            "Helpful",
                            "helpful",
                            1,
                        ),
                        _feedback_button(
                            answer_id,
                            result.response_type,
                            "Partly",
                            "partial",
                            2,
                        ),
                        _feedback_button(
                            answer_id,
                            result.response_type,
                            "Not helpful",
                            "not_helpful",
                            3,
                        ),
                    ],
                },
            )
        )
        return tuple(blocks)

    def _post(
        self,
        channel: str,
        thread_ts: str,
        answer: str,
        blocks: tuple[dict[str, object], ...],
    ) -> str | None:
        if len(answer) > self.maximum_message_length:
            answer = (
                answer[: self.maximum_message_length - 24].rstrip()
                + "\n\n_Response truncated._"
            )
        try:
            response = self.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=answer,
                blocks=list(blocks) or None,
                unfurl_links=False,
                unfurl_media=False,
            )
            timestamp = response.get("ts")
            return timestamp if isinstance(timestamp, str) else None
        except SlackApiError:
            LOGGER.exception(
                "Slack response delivery failed.",
                extra={"operation": "post_message", "component": "slack"},
            )
            return None

    def _update(
        self,
        channel: str,
        timestamp: str,
        answer: str,
        blocks: tuple[dict[str, object], ...],
    ) -> None:
        try:
            self.client.chat_update(
                channel=channel,
                ts=timestamp,
                text=answer,
                blocks=list(blocks) or None,
                unfurl_links=False,
                unfurl_media=False,
            )
        except SlackApiError:
            LOGGER.exception(
                "Slack progress message update failed.",
                extra={"operation": "update_message", "component": "slack"},
            )


def _nested_string(payload: dict[str, object], parent: str, child: str) -> str | None:
    value = payload.get(parent)
    if not isinstance(value, dict):
        return None
    nested = value.get(child)
    return nested if isinstance(nested, str) and nested else None


def _slack_error_code(error: SlackApiError) -> str:
    response = error.response
    value = response.get("error")
    return value if isinstance(value, str) else "unknown"


def _visual_blocks(title: str, visual: str) -> tuple[dict[str, object], ...]:
    """Render model-derived relationships as colorful Slack flow cards."""
    nodes = tuple(
        node.strip()
        for node in re.split(r"\s*↓\s*", public_answer(visual))
        if node.strip()
    )[:8]
    if not nodes:
        return ()
    blocks: list[dict[str, object]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": title},
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "A quick visual guide"},
            ],
        },
    ]
    colors = ("🔵", "🟣", "🟢", "🟠", "🔷", "🟡", "🔴", "🟦")
    for index, node in enumerate(nodes, start=1):
        parts = tuple(
            part.strip() for part in re.split(r"\s*(?:→|->|➜)\s*", node) if part.strip()
        )
        diagram = f" {'  ➜  '.join(f'*{part[:160]}*' for part in parts)}"
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{colors[(index - 1) % len(colors)]}  *{index:02d}*{diagram[:700]}",
                },
            }
        )
        if index < len(nodes):
            blocks.append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": "↓"}],
                }
            )
    return tuple(blocks)


def _streaming_preview(text: str) -> str:
    """Trim in-progress text for Slack and mark it as still being written."""
    cleaned = public_answer(text)
    if len(cleaned) > 2_800:
        cleaned = f"{cleaned[:2_800].rstrip()}…"
    return f"{cleaned} ▌"


def _button_text(question: str) -> str:
    return question if len(question) <= 75 else f"{question[:72].rstrip()}..."


def _feedback_button(
    answer_id: str,
    response_type: str,
    label: str,
    rating: str,
    position: int,
) -> dict[str, object]:
    return {
        "type": "button",
        "action_id": f"knowledge_feedback_{position}",
        "text": {"type": "plain_text", "text": label},
        "value": f"{answer_id}:{response_type}:{rating}",
    }
