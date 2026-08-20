"""OpenAI embedding generation."""

from openai import OpenAI, OpenAIError

from app.cache import LruCache


class EmbeddingUnavailableError(RuntimeError):
    """Raised when the external embedding service cannot serve a request."""


class Embeddings:
    def __init__(
        self,
        api_key: str,
        model: str,
        dimensions: int,
        query_cache_size: int = 256,
    ) -> None:
        self.client = OpenAI(api_key=api_key, max_retries=4, timeout=20.0)
        self.model = model
        self.dimensions = dimensions
        self._query_cache: LruCache[tuple[float, ...]] = LruCache(query_cache_size)

    def create(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()
        if len(texts) == 1:
            cached = self._query_cache.get(_cache_key(texts[0]))
            if cached is not None:
                return (cached,)
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=list(texts),
                dimensions=self.dimensions,
                encoding_format="float",
            )
        except OpenAIError as exc:
            raise EmbeddingUnavailableError(
                "The embedding service is temporarily unavailable."
            ) from exc
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors = tuple(
            tuple(float(value) for value in item.embedding) for item in ordered
        )
        if len(vectors) != len(texts) or any(
            len(vector) != self.dimensions for vector in vectors
        ):
            raise RuntimeError(
                "The embedding response did not match the requested inputs."
            )
        if len(texts) == 1:
            self._query_cache.put(_cache_key(texts[0]), vectors[0])
        return vectors


def _cache_key(text: str) -> str:
    return text.strip().casefold()
