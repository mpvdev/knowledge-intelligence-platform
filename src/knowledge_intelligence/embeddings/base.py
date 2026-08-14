from typing import Protocol

from knowledge_intelligence.domain.embeddings import (
    EmbeddingBatchResult,
)


class EmbeddingProvider(Protocol):
    """Generate semantic embeddings from text."""

    def embed(
        self,
        texts: tuple[str, ...],
    ) -> EmbeddingBatchResult: ...
