"""Persistence for complete evidence chunks in standard Amazon S3."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError

from knowledge_intelligence.connectors.s3.exceptions import S3AccessError
from knowledge_intelligence.domain.retrieval import (
    DocumentChunk,
    DocumentChunkManifest,
    StoredChunk,
)

NOT_FOUND_ERROR_CODES = frozenset({"NoSuchKey", "404", "NotFound"})


@runtime_checkable
class S3ObjectBody(Protocol):
    def read(self, amount: int | None = None) -> bytes: ...
    def close(self) -> None: ...


class ChunkS3Client(Protocol):
    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str,
    ) -> Mapping[str, object]: ...

    def get_object(self, *, Bucket: str, Key: str) -> Mapping[str, object]: ...
    def delete_object(self, *, Bucket: str, Key: str) -> Mapping[str, object]: ...


class S3ChunkRepository:
    """Store full evidence outside the vector index and maintain source manifests."""

    def __init__(self, client: ChunkS3Client, bucket: str) -> None:
        if not bucket.strip():
            raise ValueError("Chunk bucket name must not be empty.")
        self._client = client
        self._bucket = bucket

    def save(
        self,
        chunk: DocumentChunk,
        *,
        fingerprint: str,
        embedding_model: str,
        embedding_dimensions: int,
        vector_written: bool,
    ) -> None:
        payload = chunk.model_dump(mode="json") | {
            "fingerprint": fingerprint,
            "embedding_model": embedding_model,
            "embedding_dimensions": embedding_dimensions,
            "vector_written": vector_written,
        }
        self._put_json(self.key_for(chunk.document_id, chunk.chunk_id), payload)

    def load(self, document_id: str, chunk_id: str) -> StoredChunk | None:
        payload = self._load_json(self.key_for(document_id, chunk_id))
        if payload is None:
            return None
        fingerprint = payload.pop("fingerprint", None)
        if not isinstance(fingerprint, str) or not fingerprint:
            raise S3AccessError("Processed chunk is missing its fingerprint.")
        payload.pop("embedding_model", None)
        payload.pop("embedding_dimensions", None)
        vector_written = bool(payload.pop("vector_written", False))
        try:
            return StoredChunk(
                chunk=DocumentChunk.model_validate(payload),
                fingerprint=fingerprint,
                vector_written=vector_written,
            )
        except ValidationError as exc:
            raise S3AccessError("Processed chunk has an invalid schema.") from exc

    def delete(self, document_id: str, chunk_id: str) -> None:
        self._delete(self.key_for(document_id, chunk_id))

    def load_manifest(self, chunk: DocumentChunk) -> DocumentChunkManifest | None:
        payload = self._load_json(
            self.manifest_key_for(chunk.reference.bucket, chunk.reference.key)
        )
        if payload is None:
            return None
        try:
            return DocumentChunkManifest.model_validate(payload)
        except ValidationError as exc:
            raise S3AccessError("Processed chunk manifest has an invalid schema.") from exc

    def save_manifest(self, chunks: tuple[DocumentChunk, ...]) -> None:
        if not chunks:
            return
        first = chunks[0]
        if any(chunk.document_id != first.document_id for chunk in chunks):
            raise ValueError("A chunk manifest must contain one document.")
        if any(chunk.reference != first.reference for chunk in chunks):
            raise ValueError("A chunk manifest must contain one source object.")
        manifest = DocumentChunkManifest(
            source_bucket=first.reference.bucket,
            source_key=first.reference.key,
            document_id=first.document_id,
            chunk_ids=tuple(chunk.chunk_id for chunk in chunks),
        )
        self._put_json(
            self.manifest_key_for(manifest.source_bucket, manifest.source_key),
            manifest.model_dump(mode="json"),
        )

    def _load_json(self, key: str) -> dict[str, object] | None:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            body = response.get("Body")
            if not isinstance(body, S3ObjectBody):
                raise S3AccessError("S3 returned an invalid object body.")
            try:
                value: object = json.loads(body.read())
            finally:
                body.close()
        except ClientError as exc:
            error = str(exc.response.get("Error", {}).get("Code", ""))
            if error in NOT_FOUND_ERROR_CODES:
                return None
            raise S3AccessError("Unable to load processed chunk data.") from exc
        except (BotoCoreError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise S3AccessError("Unable to load processed chunk data.") from exc
        if not isinstance(value, dict):
            raise S3AccessError("Processed chunk data must be a JSON object.")
        return value

    def _put_json(self, key: str, payload: Mapping[str, object]) -> None:
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=json.dumps(payload, separators=(",", ":")).encode(),
                ContentType="application/json",
            )
        except (ClientError, BotoCoreError) as exc:
            raise S3AccessError("Unable to persist processed chunk data.") from exc

    def _delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            raise S3AccessError("Unable to delete processed chunk data.") from exc

    @staticmethod
    def key_for(document_id: str, chunk_id: str) -> str:
        return f"processed/chunks/{document_id}/{chunk_id}.json"

    @staticmethod
    def manifest_key_for(source_bucket: str, source_key: str) -> str:
        identity = f"{source_bucket}:{source_key}".encode()
        return f"processed/manifests/{hashlib.sha256(identity).hexdigest()}.json"
