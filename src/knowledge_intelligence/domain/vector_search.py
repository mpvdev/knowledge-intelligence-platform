from pydantic import BaseModel, ConfigDict, Field

from knowledge_intelligence.domain.retrieval import ChunkContentType


class VectorMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: str
    document_id: str
    document_title: str

    component_id: str | None = None
    component_name: str | None = None

    source_system: str
    content_type: ChunkContentType

    document_key: str
    page_number: int | None = None

    sequence: int = Field(ge=0)
    embedding_model: str
    embedding_dimensions: int = Field(ge=1)


class VectorRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    values: tuple[float, ...]
    metadata: VectorMetadata


class SemanticSearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    vector_key: str
    distance: float = Field(ge=0)
    metadata: VectorMetadata
