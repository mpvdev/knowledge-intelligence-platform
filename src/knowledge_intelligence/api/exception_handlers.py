import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from knowledge_intelligence.api.schemas import ErrorResponse
from knowledge_intelligence.connectors.github.exceptions import GitHubConnectorError
from knowledge_intelligence.connectors.local_repository import LocalRepositoryAccessError
from knowledge_intelligence.connectors.s3.exceptions import (
    S3DocumentError,
)
from knowledge_intelligence.parsers.exceptions import (
    DocumentParsingError,
)

logger = logging.getLogger(__name__)


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "unknown")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(GitHubConnectorError)
    async def handle_github_error(
        request: Request,
        exc: GitHubConnectorError,
    ) -> JSONResponse:
        payload = ErrorResponse(
            error="repository_source_error",
            message="The approved GitHub source could not be accessed.",
            correlation_id=_correlation_id(request),
        )
        return JSONResponse(status_code=503, content=payload.model_dump(mode="json"))

    @app.exception_handler(LocalRepositoryAccessError)
    async def handle_repository_access_error(
        request: Request,
        exc: LocalRepositoryAccessError,
    ) -> JSONResponse:
        payload = ErrorResponse(
            error="repository_source_error",
            message="The selected local repository could not be accessed.",
            correlation_id=_correlation_id(request),
        )
        return JSONResponse(status_code=503, content=payload.model_dump(mode="json"))

    @app.exception_handler(S3DocumentError)
    async def handle_s3_error(
        request: Request,
        exc: S3DocumentError,
    ) -> JSONResponse:
        payload = ErrorResponse(
            error="knowledge_source_error",
            message="The knowledge source could not be accessed.",
            correlation_id=_correlation_id(request),
        )

        return JSONResponse(
            status_code=503,
            content=payload.model_dump(mode="json"),
        )

    @app.exception_handler(DocumentParsingError)
    async def handle_parsing_error(
        request: Request,
        exc: DocumentParsingError,
    ) -> JSONResponse:
        payload = ErrorResponse(
            error="knowledge_processing_error",
            message="A knowledge document could not be processed.",
            correlation_id=_correlation_id(request),
        )

        return JSONResponse(
            status_code=503,
            content=payload.model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception(
            "Unhandled API request.",
            extra={
                "correlation_id": _correlation_id(request),
                "operation": "api_request",
            },
        )
        payload = ErrorResponse(
            error="internal_error",
            message="An unexpected error occurred.",
            correlation_id=_correlation_id(request),
        )

        return JSONResponse(
            status_code=500,
            content=payload.model_dump(mode="json"),
        )
