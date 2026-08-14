from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from knowledge_intelligence.api.exception_handlers import register_exception_handlers
from knowledge_intelligence.api.middleware import CorrelationIdMiddleware
from knowledge_intelligence.api.routes import health, knowledge, slack
from knowledge_intelligence.application.container import build_application
from knowledge_intelligence.application.slack_event_service import (
    SlackEventService,
)
from knowledge_intelligence.config import get_settings
from knowledge_intelligence.connectors.slack.client import (
    SlackMessageClient,
)
from knowledge_intelligence.connectors.slack.signature import (
    SlackRequestVerifier,
)
from knowledge_intelligence.services.event_deduplication import (
    EventDeduplicationService,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    container = build_application(settings)

    app.state.container = container

    if settings.slack_enabled:
        app.state.slack_request_verifier = SlackRequestVerifier(
            settings.slack_signing_secret.get_secret_value()
        )
        app.state.event_deduplication = EventDeduplicationService()
        app.state.slack_event_service = SlackEventService(
            knowledge_service=container.platform_knowledge_service,
            slack_client=SlackMessageClient(settings.slack_bot_token.get_secret_value()),
            maximum_message_length=settings.slack_max_message_length,
        )
    else:
        app.state.slack_request_verifier = None
        app.state.event_deduplication = None
        app.state.slack_event_service = None

    yield

    app.state.container = None
    app.state.slack_request_verifier = None
    app.state.event_deduplication = None
    app.state.slack_event_service = None


def create_app() -> FastAPI:
    app = FastAPI(
        title="Knowledge Intelligence API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(CorrelationIdMiddleware)
    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(knowledge.router)
    app.include_router(slack.router)

    return app


app = create_app()
