from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ClassificationMethod(StrEnum):
    REGISTRY_PREFIX = "registry_prefix"
    EXPLICIT_MANIFEST = "explicit_manifest"
    MANUAL = "manual"
    UNCLASSIFIED = "unclassified"


class DocumentClassification(BaseModel):
    """Authoritative classification assigned during ingestion."""

    model_config = ConfigDict(frozen=True)

    platform_id: str = "tme"

    component_id: str | None = None
    component_name: str | None = None

    document_type: str | None = None
    source_system: str = "confluence"

    related_component_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    classification_method: ClassificationMethod
