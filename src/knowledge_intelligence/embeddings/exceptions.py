"""Project-specific failures raised by embedding integrations."""


class EmbeddingProviderError(RuntimeError):
    """An embedding provider could not produce a valid result."""


class EmbeddingDimensionError(EmbeddingProviderError):
    """An embedding provider returned an unexpected vector size."""
