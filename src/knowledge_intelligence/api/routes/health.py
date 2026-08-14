from fastapi import APIRouter, Request

from knowledge_intelligence.api.schemas import (
    HealthResponse,
    ReadinessResponse,
)
from knowledge_intelligence.application.container import (
    ApplicationContainer,
)

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
)
def health() -> HealthResponse:
    return HealthResponse(status="healthy")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
)
def ready(request: Request) -> ReadinessResponse:
    container: ApplicationContainer | None = getattr(
        request.app.state,
        "container",
        None,
    )

    if container is None:
        return ReadinessResponse(
            status="not_ready",
            knowledge_index_ready=False,
            indexed_chunk_count=0,
            vector_retrieval_configured=False,
            vector_retrieval_reachable=False,
        )

    return ReadinessResponse(
        status="ready",
        knowledge_index_ready=True,
        indexed_chunk_count=container.indexed_chunk_count,
        vector_retrieval_configured=container.vector_retrieval_configured,
        vector_retrieval_reachable=container.vector_retrieval_reachable,
    )
