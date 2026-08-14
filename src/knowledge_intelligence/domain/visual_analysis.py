from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class VisualContentType(StrEnum):
    ARCHITECTURE_DIAGRAM = "architecture_diagram"
    FLOW_DIAGRAM = "flow_diagram"
    SEQUENCE_DIAGRAM = "sequence_diagram"
    NETWORK_DIAGRAM = "network_diagram"
    TABLE = "table"
    SCREENSHOT = "screenshot"
    CHART = "chart"
    SCANNED_TEXT = "scanned_text"
    OTHER = "other"


class RelationshipType(StrEnum):
    CONNECTS_TO = "connects_to"
    DEPENDS_ON = "depends_on"
    SENDS_TO = "sends_to"
    RECEIVES_FROM = "receives_from"
    DEPLOYS_TO = "deploys_to"
    EXECUTES = "executes"
    ASSUMES = "assumes"
    MONITORS = "monitors"
    REPORTS_TO = "reports_to"
    INTEGRATES_WITH = "integrates_with"
    CONTAINS = "contains"
    UNKNOWN = "unknown"


class VisualComponent(BaseModel):
    """One component visibly represented on a document page."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=300)
    component_type: str | None = Field(
        default=None,
        max_length=200,
    )
    description: str | None = Field(
        default=None,
        max_length=1_000,
    )


class VisualRelationship(BaseModel):
    """One visible relationship between two components."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(min_length=1, max_length=300)
    target: str = Field(min_length=1, max_length=300)
    relationship_type: RelationshipType
    label: str | None = Field(
        default=None,
        max_length=500,
    )
    evidence: str | None = Field(
        default=None,
        max_length=1_000,
    )


class VisualTable(BaseModel):
    """Tabular information identified from an image or diagram."""

    model_config = ConfigDict(frozen=True)

    title: str | None = None
    headers: tuple[str, ...] = ()
    rows: tuple[tuple[str, ...], ...] = ()


class VisualAnalysisPayload(BaseModel):
    """Structured model output for one rendered PDF page."""

    model_config = ConfigDict(frozen=True)

    content_type: VisualContentType

    summary: str = Field(
        min_length=1,
        max_length=5_000,
    )

    visible_text: tuple[str, ...] = ()
    components: tuple[VisualComponent, ...] = ()
    relationships: tuple[VisualRelationship, ...] = ()
    tables: tuple[VisualTable, ...] = ()

    important_observations: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()

    contains_meaningful_visual_content: bool = True


class VisualPageAnalysis(BaseModel):
    """Page-cited visual analysis stored by the application."""

    model_config = ConfigDict(frozen=True)

    document_key: str
    document_title: str
    page_number: int = Field(ge=1)

    analysis: VisualAnalysisPayload

    extraction_method: str = "openai_vision"
    model_id: str
    prompt_version: str

    model_derived: bool = True
