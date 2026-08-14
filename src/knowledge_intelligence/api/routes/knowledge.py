from fastapi import APIRouter, status

from knowledge_intelligence.api.dependencies import (
    PlatformKnowledgeServiceDependency,
    UnifiedKnowledgeServiceDependency,
)
from knowledge_intelligence.api.schemas import (
    ChangeImpactRequest,
    ChangeImpactResponse,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
)
from knowledge_intelligence.application.answer_presentation import (
    format_change_impact_analysis,
)

router = APIRouter(
    prefix="/v1/knowledge",
    tags=["platform-knowledge"],
)


@router.post(
    "/query",
    response_model=KnowledgeQueryResponse,
    status_code=status.HTTP_200_OK,
)
def query_knowledge(
    payload: KnowledgeQueryRequest,
    service: UnifiedKnowledgeServiceDependency,
) -> KnowledgeQueryResponse:
    result = service.answer(
        payload.prompt,
    )

    return KnowledgeQueryResponse(
        answer=format_change_impact_analysis(result.answer),
        status=result.status,
        documentation_sources=result.documentation_sources,
        code_sources=result.code_sources,
    )


@router.post(
    "/impact-analysis",
    response_model=ChangeImpactResponse,
    status_code=status.HTTP_200_OK,
)
def analyse_change_impact(
    payload: ChangeImpactRequest,
    service: PlatformKnowledgeServiceDependency,
) -> ChangeImpactResponse:
    result = service.analyse_change(
        payload.change_description,
        component_ids=payload.component_ids,
    )
    return ChangeImpactResponse(
        analysis=format_change_impact_analysis(result.answer),
        status=result.status,
        sources=result.sources,
    )
