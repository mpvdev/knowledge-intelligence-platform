from typing import Annotated

from fastapi import Depends, Request

from knowledge_intelligence.application.container import (
    ApplicationContainer,
)
from knowledge_intelligence.application.platform_knowledge_service import (
    PlatformKnowledgeService,
)
from knowledge_intelligence.application.unified_knowledge_service import (
    UnifiedKnowledgeService,
)


def get_container(request: Request) -> ApplicationContainer:
    container = getattr(request.app.state, "container", None)

    if not isinstance(container, ApplicationContainer):
        raise RuntimeError("Application container is not initialized.")

    return container


def get_platform_knowledge_service(
    container: Annotated[
        ApplicationContainer,
        Depends(get_container),
    ],
) -> PlatformKnowledgeService:
    return container.platform_knowledge_service


PlatformKnowledgeServiceDependency = Annotated[
    PlatformKnowledgeService,
    Depends(get_platform_knowledge_service),
]


def get_unified_knowledge_service(
    container: Annotated[ApplicationContainer, Depends(get_container)],
) -> UnifiedKnowledgeService:
    return container.unified_knowledge_service


UnifiedKnowledgeServiceDependency = Annotated[
    UnifiedKnowledgeService,
    Depends(get_unified_knowledge_service),
]
