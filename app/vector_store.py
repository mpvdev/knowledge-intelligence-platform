"""Minimal Amazon S3 Vectors and processed-chunk persistence."""

from __future__ import annotations

import struct
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from threading import RLock

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel, ConfigDict

from app.models import Chunk


class VectorStore:
    def __init__(
        self,
        *,
        region: str,
        source_bucket: str,
        vector_bucket: str,
        index_name: str,
        dimensions: int,
        chunk_cache_size: int = 512,
    ) -> None:
        self.s3 = boto3.client("s3", region_name=region)
        self.vectors = boto3.client("s3vectors", region_name=region)
        self.source_bucket = source_bucket
        self.vector_bucket = vector_bucket
        self.index_name = index_name
        self.dimensions = dimensions
        self.chunk_cache_size = chunk_cache_size
        self._chunk_cache: OrderedDict[str, Chunk] = OrderedDict()
        self._cache_lock = RLock()
        self._chunk_loader = ThreadPoolExecutor(
            max_workers=8,
            thread_name_prefix="knowledge-chunk",
        )

    def reachable(self) -> bool:
        try:
            response = self.vectors.get_index(
                vectorBucketName=self.vector_bucket,
                indexName=self.index_name,
            )
            index = response.get("index", {})
            return bool(index.get("dimension") == self.dimensions)
        except (BotoCoreError, ClientError):
            return False

    def load_chunks(self) -> tuple[Chunk, ...]:
        """Load the persisted chunk manifest for keyword search and resilience."""
        chunks = tuple(self._chunk_loader.map(self._load_chunk, self._load_manifest()))
        return tuple(chunk for chunk in chunks if chunk is not None)

    def put(
        self, chunks: tuple[Chunk, ...], embeddings: tuple[tuple[float, ...], ...]
    ) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError("Every chunk must have one embedding.")
        written = 0
        for start in range(0, len(chunks), 100):
            chunk_batch = chunks[start : start + 100]
            embedding_batch = embeddings[start : start + 100]
            for chunk in chunk_batch:
                self._save_chunk(chunk)
            try:
                self.vectors.put_vectors(
                    vectorBucketName=self.vector_bucket,
                    indexName=self.index_name,
                    vectors=[
                        {
                            "key": chunk.chunk_id,
                            "data": {"float32": list(self._float32(vector))},
                            "metadata": {
                                "component_id": chunk.component_id,
                                "source_type": chunk.source_type.value,
                            },
                        }
                        for chunk, vector in zip(
                            chunk_batch, embedding_batch, strict=True
                        )
                    ],
                )
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError("Unable to write the S3 Vector index.") from exc
            written += len(chunk_batch)
        return written

    def query(
        self, embedding: tuple[float, ...], limit: int
    ) -> tuple[tuple[Chunk, float], ...]:
        try:
            response = self.vectors.query_vectors(
                vectorBucketName=self.vector_bucket,
                indexName=self.index_name,
                topK=limit,
                queryVector={"float32": list(self._float32(embedding))},
                returnMetadata=False,
                returnDistance=True,
            )
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError("Unable to query the S3 Vector index.") from exc
        records = response.get("vectors", ())
        if not isinstance(records, Sequence):
            return ()
        candidates: list[tuple[str, float]] = []
        for record in records:
            if not isinstance(record, Mapping):
                continue
            key = record.get("key")
            distance = record.get("distance")
            if isinstance(key, str) and isinstance(distance, (int, float)):
                candidates.append((key, float(distance)))
        chunks = tuple(
            self._chunk_loader.map(
                self._load_chunk,
                (key for key, _ in candidates),
            )
        )
        return tuple(
            (chunk, 1.0 / (1.0 + distance))
            for chunk, (_, distance) in zip(chunks, candidates, strict=True)
            if chunk is not None
        )

    def finalize(self, active_chunk_ids: tuple[str, ...]) -> None:
        """Remove superseded vectors after a complete successful ingestion."""
        obsolete = tuple(
            sorted(set(self._load_manifest()).difference(active_chunk_ids))
        )
        for start in range(0, len(obsolete), 500):
            batch = obsolete[start : start + 500]
            try:
                self.vectors.delete_vectors(
                    vectorBucketName=self.vector_bucket,
                    indexName=self.index_name,
                    keys=list(batch),
                )
                for chunk_id in batch:
                    self.s3.delete_object(
                        Bucket=self.source_bucket,
                        Key=self._chunk_key(chunk_id),
                    )
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(
                    "Unable to remove superseded knowledge chunks."
                ) from exc
        try:
            self.s3.put_object(
                Bucket=self.source_bucket,
                Key="processed/index-manifest.json",
                Body=ChunkManifest(chunk_ids=active_chunk_ids)
                .model_dump_json()
                .encode(),
                ContentType="application/json",
            )
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(
                "Unable to persist the knowledge index manifest."
            ) from exc

    def _save_chunk(self, chunk: Chunk) -> None:
        try:
            self.s3.put_object(
                Bucket=self.source_bucket,
                Key=self._chunk_key(chunk.chunk_id),
                Body=chunk.model_dump_json().encode(),
                ContentType="application/json",
            )
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(
                "Unable to persist a processed knowledge chunk."
            ) from exc
        self._cache_chunk(chunk.chunk_id, chunk)

    def _load_chunk(self, chunk_id: str) -> Chunk | None:
        cached = self._cached_chunk(chunk_id)
        if cached is not None:
            return cached
        try:
            response = self.s3.get_object(
                Bucket=self.source_bucket,
                Key=self._chunk_key(chunk_id),
            )
            body = response["Body"]
            try:
                chunk = Chunk.model_validate_json(body.read())
            finally:
                body.close()
            self._cache_chunk(chunk_id, chunk)
            return chunk
        except self.s3.exceptions.NoSuchKey:
            return None
        except (BotoCoreError, ClientError, ValueError) as exc:
            raise RuntimeError("Unable to load a processed knowledge chunk.") from exc

    def _cached_chunk(self, chunk_id: str) -> Chunk | None:
        with self._cache_lock:
            chunk = self._chunk_cache.get(chunk_id)
            if chunk is not None:
                self._chunk_cache.move_to_end(chunk_id)
            return chunk

    def _cache_chunk(self, chunk_id: str, chunk: Chunk) -> None:
        with self._cache_lock:
            self._chunk_cache[chunk_id] = chunk
            self._chunk_cache.move_to_end(chunk_id)
            while len(self._chunk_cache) > self.chunk_cache_size:
                self._chunk_cache.popitem(last=False)

    def _load_manifest(self) -> tuple[str, ...]:
        try:
            response = self.s3.get_object(
                Bucket=self.source_bucket,
                Key="processed/index-manifest.json",
            )
            body = response["Body"]
            try:
                return ChunkManifest.model_validate_json(body.read()).chunk_ids
            finally:
                body.close()
        except self.s3.exceptions.NoSuchKey:
            return ()
        except ClientError as exc:
            if str(exc.response.get("Error", {}).get("Code")) in {"NoSuchKey", "404"}:
                return ()
            raise RuntimeError("Unable to load the knowledge index manifest.") from exc
        except (BotoCoreError, ValueError) as exc:
            raise RuntimeError("Unable to load the knowledge index manifest.") from exc

    def _float32(self, values: tuple[float, ...]) -> tuple[float, ...]:
        if len(values) != self.dimensions:
            raise ValueError(f"Expected an embedding with {self.dimensions} values.")
        return tuple(struct.unpack("f", struct.pack("f", value))[0] for value in values)

    @staticmethod
    def _chunk_key(chunk_id: str) -> str:
        return f"processed/chunks/{chunk_id}.json"


class ChunkManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_ids: tuple[str, ...]
