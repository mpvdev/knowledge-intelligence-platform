from urllib.parse import parse_qs

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import SecretStr

from knowledge_intelligence.application.slack_event_service import SlackEventService
from knowledge_intelligence.connectors.slack.models import (
    SlackCommandRequest,
    SlackEventEnvelope,
    SlackKnowledgeRequest,
)
from knowledge_intelligence.connectors.slack.signature import SlackRequestVerifier
from knowledge_intelligence.services.event_deduplication import EventDeduplicationService

router = APIRouter(
    prefix="/slack",
    tags=["slack"],
)


def _require_slack_components(
    request: Request,
) -> tuple[SlackRequestVerifier, EventDeduplicationService, SlackEventService]:
    verifier = getattr(request.app.state, "slack_request_verifier", None)
    deduplication = getattr(request.app.state, "event_deduplication", None)
    event_service = getattr(request.app.state, "slack_event_service", None)

    if verifier is None or deduplication is None or event_service is None:
        raise HTTPException(
            status_code=503,
            detail="Slack integration is not enabled.",
        )

    return verifier, deduplication, event_service


def _verify_request(
    request: Request,
    verifier: SlackRequestVerifier,
    raw_body: bytes,
) -> None:
    is_valid = verifier.verify(
        body=raw_body,
        timestamp=request.headers.get("X-Slack-Request-Timestamp"),
        signature=request.headers.get("X-Slack-Signature"),
    )

    if not is_valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid Slack request signature.",
        )


@router.post("/events")
async def receive_slack_event(
    request: Request,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    raw_body = await request.body()

    verifier, deduplication, event_service = _require_slack_components(request)
    _verify_request(request, verifier, raw_body)

    envelope = SlackEventEnvelope.model_validate_json(raw_body)

    if envelope.type == "url_verification":
        return JSONResponse(
            content={"challenge": envelope.challenge},
        )

    if envelope.type != "event_callback":
        return JSONResponse(content={"ok": True})

    if not envelope.event_id or not envelope.event:
        return JSONResponse(content={"ok": True})

    if not deduplication.accept(envelope.event_id):
        return JSONResponse(content={"ok": True})

    event = envelope.event
    event_type = event.get("type")
    channel_type = event.get("channel_type")

    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return JSONResponse(content={"ok": True})

    supported_event = event_type == "app_mention" or (
        event_type == "message" and channel_type == "im" and event.get("subtype") is None
    )

    if not supported_event:
        return JSONResponse(content={"ok": True})

    channel_id = event.get("channel")
    text = event.get("text")
    message_ts = event.get("ts")

    if not isinstance(channel_id, str) or not channel_id:
        return JSONResponse(content={"ok": True})
    if not isinstance(text, str) or not text:
        return JSONResponse(content={"ok": True})
    if not isinstance(message_ts, str) or not message_ts:
        return JSONResponse(content={"ok": True})

    raw_thread_ts = event.get("thread_ts")
    thread_ts = raw_thread_ts if isinstance(raw_thread_ts, str) and raw_thread_ts else message_ts

    normalized_request = SlackKnowledgeRequest(
        channel_id=channel_id,
        text=text,
        thread_ts=thread_ts,
    )

    background_tasks.add_task(
        event_service.process,
        normalized_request,
    )

    return JSONResponse(content={"ok": True})


@router.post("/commands")
async def receive_slack_command(
    request: Request,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """Acknowledge and asynchronously process a signed Slack slash command."""
    raw_body = await request.body()
    verifier, _, event_service = _require_slack_components(request)
    _verify_request(request, verifier, raw_body)

    form = parse_qs(raw_body.decode("utf-8"), keep_blank_values=True)

    def required_value(name: str) -> str:
        values = form.get(name)
        value = values[0].strip() if values else ""
        if not value:
            raise HTTPException(status_code=400, detail=f"Missing Slack command field: {name}.")
        return value

    text_values = form.get("text")
    command_text = text_values[0].strip() if text_values else ""

    command_request = SlackCommandRequest(
        text=command_text,
        response_url=SecretStr(required_value("response_url")),
    )
    background_tasks.add_task(event_service.process_command, command_request)

    return JSONResponse(
        content={
            "response_type": "ephemeral",
            "text": "Searching the approved platform documentation…",
        }
    )
