from pydantic import BaseModel, ConfigDict, Field


class TextEmbedding(BaseModel):
    """Embedding generated for one text input."""

    model_config = ConfigDict(frozen=True)

    values: tuple[float, ...]
    model_id: str
    dimensions: int = Field(ge=1)
    input_tokens: int = Field(default=0, ge=0)


class EmbeddingBatchResult(BaseModel):
    """Embeddings produced from one batch of texts."""

    model_config = ConfigDict(frozen=True)

    embeddings: tuple[TextEmbedding, ...]
    total_tokens: int = Field(default=0, ge=0)
