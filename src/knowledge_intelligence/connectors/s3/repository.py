from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from botocore.exceptions import BotoCoreError, ClientError

from knowledge_intelligence.connectors.s3.exceptions import (
    DocumentNotFoundError,
    DocumentTooLargeError,
    S3AccessError,
    UnsupportedDocumentError,
)
from knowledge_intelligence.domain.documents import (
    DocumentFormat,
    DocumentReference,
    DocumentSource,
    DownloadedDocument,
)

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_s3.type_defs import GetObjectOutputTypeDef, ObjectTypeDef

SUPPORTED_EXTENSIONS: dict[str, DocumentFormat] = {
    ".pdf": DocumentFormat.PDF,
    ".docx": DocumentFormat.DOCX,
}
NOT_FOUND_ERROR_CODES = frozenset({"NoSuchKey", "404", "NotFound"})


class S3DocumentRepository:
    """Read-only repository for discovering and downloading S3 documents."""

    def __init__(
        self,
        s3_client: S3Client,
        bucket: str,
        max_document_size_bytes: int,
    ) -> None:
        if not bucket:
            raise ValueError("bucket must not be empty")
        if max_document_size_bytes <= 0:
            raise ValueError("max_document_size_bytes must be positive")

        self._s3_client = s3_client
        self._bucket = bucket
        self._max_document_size_bytes = max_document_size_bytes

    def list_documents(self, prefix: str = "") -> list[DocumentReference]:
        """List supported documents below an S3 prefix."""
        documents: list[DocumentReference] = []

        try:
            paginator = self._s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self._bucket, Prefix=prefix)

            for page in pages:
                documents.extend(
                    reference
                    for item in page.get("Contents", [])
                    if (reference := self._to_document_reference(item)) is not None
                )
        except (ClientError, BotoCoreError) as exc:
            raise S3AccessError(f"Unable to list documents from {self._uri(prefix)}") from exc

        return sorted(documents, key=lambda document: document.key)

    def download_document(self, key: str) -> DownloadedDocument:
        """Download one supported document from S3."""
        document_format = self._get_document_format(key)
        response = self._get_object(key)
        declared_size = int(response.get("ContentLength", 0))
        body = response["Body"]

        try:
            self._ensure_size_allowed(key, declared_size)
            content = body.read(self._max_document_size_bytes + 1)
            self._ensure_size_allowed(key, len(content))
        except BotoCoreError as exc:
            raise S3AccessError(f"Unable to read document: {self._uri(key)}") from exc
        finally:
            body.close()

        return DownloadedDocument(
            reference=self._build_reference(
                key=key,
                document_format=document_format,
                size_bytes=len(content),
                metadata=response,
            ),
            content=content,
        )

    def _get_object(self, key: str) -> GetObjectOutputTypeDef:
        try:
            return self._s3_client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in NOT_FOUND_ERROR_CODES:
                raise DocumentNotFoundError(f"Document not found: {self._uri(key)}") from exc
            raise S3AccessError(f"Unable to read document: {self._uri(key)}") from exc
        except BotoCoreError as exc:
            raise S3AccessError(f"Unable to read document: {self._uri(key)}") from exc

    def _to_document_reference(self, item: ObjectTypeDef) -> DocumentReference | None:
        key = str(item["Key"])
        try:
            document_format = self._get_document_format(key)
        except UnsupportedDocumentError:
            return None

        size_bytes = int(item.get("Size", 0))
        if size_bytes > self._max_document_size_bytes:
            return None

        return self._build_reference(key, document_format, size_bytes, item)

    def _build_reference(
        self,
        key: str,
        document_format: DocumentFormat,
        size_bytes: int,
        metadata: Mapping[str, Any],
    ) -> DocumentReference:
        return DocumentReference(
            bucket=self._bucket,
            key=key,
            filename=PurePosixPath(key).name,
            source=DocumentSource.CONFLUENCE,
            format=document_format,
            size_bytes=size_bytes,
            etag=self._clean_etag(metadata.get("ETag")),
            last_modified=metadata.get("LastModified"),
            content_type=metadata.get("ContentType"),
            version_id=metadata.get("VersionId"),
        )

    def _ensure_size_allowed(self, key: str, size_bytes: int) -> None:
        if size_bytes > self._max_document_size_bytes:
            raise DocumentTooLargeError(
                f"Document {key!r} is {size_bytes} bytes; maximum permitted size is "
                f"{self._max_document_size_bytes} bytes."
            )

    def _uri(self, key: str) -> str:
        return f"s3://{self._bucket}/{key}"

    @staticmethod
    def _get_document_format(key: str) -> DocumentFormat:
        extension = PurePosixPath(key).suffix.lower()
        try:
            return SUPPORTED_EXTENSIONS[extension]
        except KeyError as exc:
            raise UnsupportedDocumentError(
                f"Unsupported document type for object {key!r}. "
                f"Supported extensions: {sorted(SUPPORTED_EXTENSIONS)}"
            ) from exc

    @staticmethod
    def _clean_etag(etag: str | None) -> str | None:
        return etag.strip('"') if etag else None
