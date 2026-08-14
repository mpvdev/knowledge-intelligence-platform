from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DocumentFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"


class DocumentSource(StrEnum):
    CONFLUENCE = "confluence"


class DocumentReference(BaseModel):
    """Metadata describing a supported document stored in S3."""

    model_config = ConfigDict(frozen=True)

    bucket: str
    key: str
    filename: str
    source: DocumentSource
    format: DocumentFormat
    size_bytes: int = Field(ge=0)
    etag: str | None = None
    last_modified: datetime | None = None
    content_type: str | None = None
    version_id: str | None = None


class DownloadedDocument(BaseModel):
    """A document downloaded from S3 together with its metadata."""

    model_config = ConfigDict(frozen=True)

    reference: DocumentReference
    content: bytes
