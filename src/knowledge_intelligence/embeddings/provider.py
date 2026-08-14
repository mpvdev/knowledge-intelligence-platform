from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from openai import APIError, OpenAI

from knowledge_intelligence.domain.embeddings import (
    EmbeddingBatchResult,
    TextEmbedding,
)
from knowledge_intelligence.embeddings.exceptions import (
    EmbeddingDimensionError,
    EmbeddingProviderError,
)


@dataclass(frozen=True)
class OpenAIEmbeddingConfig:
    api_key: str
    model_id: str = "text-embedding-3-small"
    dimensions: int = 1536

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("OpenAI API key cannot be empty.")

        if not self.model_id.strip():
            raise ValueError("Embedding model ID cannot be empty.")

        if self.dimensions <= 0:
            raise ValueError("Embedding dimensions must be greater than zero.")


class OpenAIEmbeddingProvider:
    """Generate embeddings using the OpenAI Embeddings API."""

    def __init__(
        self,
        config: OpenAIEmbeddingConfig,
        client: EmbeddingsClient | None = None,
    ) -> None:
        self._config = config
        self._client = client or OpenAI(api_key=config.api_key)

    def embed(
        self,
        texts: tuple[str, ...],
    ) -> EmbeddingBatchResult:
        normalized = tuple(text.strip() for text in texts)

        if not normalized:
            return EmbeddingBatchResult(
                embeddings=(),
                total_tokens=0,
            )
        if any(not text for text in normalized):
            raise EmbeddingProviderError("Embedding inputs cannot be empty.")

        try:
            response = cast(
                EmbeddingResponse,
                self._client.embeddings.create(
                    model=self._config.model_id,
                    input=list(normalized),
                    dimensions=self._config.dimensions,
                    encoding_format="float",
                ),
            )
        except APIError as exc:
            raise EmbeddingProviderError("OpenAI embedding request failed.") from exc

        ordered = sorted(
            response.data,
            key=lambda item: item.index,
        )

        if len(ordered) != len(normalized):
            raise EmbeddingProviderError("OpenAI returned an incomplete embedding batch.")
        if tuple(item.index for item in ordered) != tuple(range(len(normalized))):
            raise EmbeddingProviderError("OpenAI returned invalid embedding response indexes.")

        embeddings = tuple(
            TextEmbedding(
                values=tuple(item.embedding),
                model_id=response.model,
                dimensions=len(item.embedding),
                input_tokens=0,
            )
            for item in ordered
        )
        if any(item.dimensions != self._config.dimensions for item in embeddings):
            raise EmbeddingDimensionError(
                f"Expected {self._config.dimensions} dimensions from {self._config.model_id}."
            )

        return EmbeddingBatchResult(
            embeddings=embeddings,
            total_tokens=response.usage.total_tokens,
        )


class EmbeddingsEndpoint(Protocol):
    def create(
        self,
        *,
        model: str,
        input: list[str],
        dimensions: int,
        encoding_format: str,
    ) -> EmbeddingResponse: ...


class EmbeddingsClient(Protocol):
    embeddings: EmbeddingsEndpoint


class EmbeddingResponseItem(Protocol):
    index: int
    embedding: Sequence[float]


class EmbeddingUsage(Protocol):
    total_tokens: int


class EmbeddingResponse(Protocol):
    model: str
    data: Sequence[EmbeddingResponseItem]
    usage: EmbeddingUsage
