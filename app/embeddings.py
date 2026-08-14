"""OpenAI embedding generation."""

from collections import OrderedDict
from threading import RLock

from openai import OpenAI, OpenAIError


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
        self.query_cache_size = query_cache_size
        self._query_cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()
        self._cache_lock = RLock()

    def create(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()
        if len(texts) == 1:
            cached = self._cached_query(texts[0])
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
            self._cache_query(texts[0], vectors[0])
        return vectors

    def _cached_query(self, text: str) -> tuple[float, ...] | None:
        key = text.strip().casefold()
        with self._cache_lock:
            vector = self._query_cache.get(key)
            if vector is not None:
                self._query_cache.move_to_end(key)
            return vector

    def _cache_query(self, text: str, vector: tuple[float, ...]) -> None:
        key = text.strip().casefold()
        with self._cache_lock:
            self._query_cache[key] = vector
            self._query_cache.move_to_end(key)
            while len(self._query_cache) > self.query_cache_size:
                self._query_cache.popitem(last=False)
