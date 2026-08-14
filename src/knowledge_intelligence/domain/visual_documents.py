from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class VisualPageClassification(StrEnum):
    TEXT_ONLY = "text_only"
    MIXED_CONTENT = "mixed_content"
    VISUAL_CANDIDATE = "visual_candidate"


class EmbeddedImageInfo(BaseModel):
    """Basic information about an image referenced by a PDF page."""

    model_config = ConfigDict(frozen=True)

    xref: int
    width: int = Field(ge=0)
    height: int = Field(ge=0)
    area_ratio: float = Field(ge=0.0, le=1.0)


class VisualPageInspection(BaseModel):
    """Result of inspecting one PDF page for meaningful visual content."""

    model_config = ConfigDict(frozen=True)

    page_number: int = Field(ge=1)

    text_character_count: int = Field(ge=0)
    embedded_image_count: int = Field(ge=0)
    largest_image_area_ratio: float = Field(ge=0.0, le=1.0)

    classification: VisualPageClassification
    reasons: tuple[str, ...] = ()

    @property
    def requires_visual_analysis(self) -> bool:
        return self.classification == VisualPageClassification.VISUAL_CANDIDATE


class RenderedPDFPage(BaseModel):
    """Rendered PNG representation of one PDF page."""

    model_config = ConfigDict(
        frozen=True,
        arbitrary_types_allowed=True,
    )

    page_number: int = Field(ge=1)
    image_bytes: bytes
    image_format: str = "png"

    width: int = Field(gt=0)
    height: int = Field(gt=0)
    dpi: int = Field(gt=0)
