class DocumentParsingError(Exception):
    """Base exception for document parsing failures."""


class CorruptedDocumentError(DocumentParsingError):
    """Raised when a document cannot be opened or decoded."""


class EncryptedDocumentError(DocumentParsingError):
    """Raised when an encrypted document cannot be parsed."""


class UnsupportedParserError(DocumentParsingError):
    """Raised when no parser supports the document format."""


class EmptyDocumentError(DocumentParsingError):
    """Raised when a document contains no extractable content."""
