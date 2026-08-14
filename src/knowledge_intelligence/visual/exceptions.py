class VisualProcessingError(Exception):
    """Base error for visual PDF processing."""


class PDFPageInspectionError(VisualProcessingError):
    """Raised when PDF visual inspection fails."""


class PDFPageRenderingError(VisualProcessingError):
    """Raised when a PDF page cannot be rendered."""


class VisualAnalysisError(VisualProcessingError):
    """Raised when model-based visual analysis fails."""


class VisualAnalysisValidationError(VisualAnalysisError):
    """Raised when visual analysis returns an invalid payload."""
