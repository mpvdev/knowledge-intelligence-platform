class S3DocumentError(Exception):
    """Base exception for S3 document operations."""


class DocumentNotFoundError(S3DocumentError):
    """Raised when the requested S3 object does not exist."""


class UnsupportedDocumentError(S3DocumentError):
    """Raised when the object format is not supported."""


class DocumentTooLargeError(S3DocumentError):
    """Raised when an object exceeds the configured size limit."""


class S3AccessError(S3DocumentError):
    """Raised when AWS denies or fails an S3 request."""


class S3VectorsError(S3DocumentError):
    """Base exception raised by the Amazon S3 Vectors connector."""


class VectorIndexUnavailableError(S3VectorsError):
    """Raised when the configured S3 Vector index cannot be used."""
