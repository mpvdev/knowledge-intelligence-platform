"""Typed, narrow adapter for the Amazon S3 Vectors SDK client."""

from __future__ import annotations

import struct
from collections.abc import Mapping, Sequence
from typing import Protocol

from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError

from knowledge_intelligence.connectors.s3.exceptions import VectorIndexUnavailableError
from knowledge_intelligence.domain.vector_search import (
    SemanticSearchResult,
    VectorMetadata,
    VectorRecord,
)

S3VectorsResponse = Mapping[str, object]


class S3VectorsClient(Protocol):
    def put_vectors(
        self,
        *,
        vectorBucketName: str,
        indexName: str,
        vectors: list[Mapping[str, object]],
    ) -> S3VectorsResponse: ...

    def query_vectors(
        self,
        *,
        vectorBucketName: str,
        indexName: str,
        topK: int,
        queryVector: Mapping[str, Sequence[float]],
        returnMetadata: bool,
        returnDistance: bool,
        filter: object | None = None,
    ) -> S3VectorsResponse: ...

    def get_vectors(
        self,
        *,
        vectorBucketName: str,
        indexName: str,
        keys: list[str],
        returnData: bool,
        returnMetadata: bool,
    ) -> S3VectorsResponse: ...

    def delete_vectors(
        self,
        *,
        vectorBucketName: str,
        indexName: str,
        keys: list[str],
    ) -> S3VectorsResponse: ...

    def list_vectors(
        self,
        *,
        vectorBucketName: str,
        indexName: str,
        returnData: bool,
        returnMetadata: bool,
        prefix: str | None = None,
    ) -> S3VectorsResponse: ...

    def get_index(
        self,
        *,
        vectorBucketName: str,
        indexName: str,
    ) -> S3VectorsResponse: ...


class S3VectorsRepository:
    """Store compact metadata with vectors; full evidence remains in standard S3."""

    def __init__(
        self,
        client: S3VectorsClient,
        bucket_name: str,
        index_name: str,
        dimensions: int,
    ) -> None:
        if not bucket_name.strip() or not index_name.strip():
            raise ValueError("Vector bucket and index names must not be empty.")
        if dimensions <= 0:
            raise ValueError("Vector dimensions must be positive.")
        self._client = client
        self._bucket_name = bucket_name
        self._index_name = index_name
        self._dimensions = dimensions

    def put_vectors(self, vectors: tuple[VectorRecord, ...]) -> None:
        self._call_put(
            [
                {
                    "key": vector.key,
                    "data": {"float32": list(self._float32(vector.values))},
                    "metadata": vector.metadata.model_dump(exclude_none=True),
                }
                for vector in vectors
            ]
        )

    def query_vectors(
        self,
        values: tuple[float, ...],
        top_k: int,
        component_ids: tuple[str, ...] = (),
    ) -> tuple[SemanticSearchResult, ...]:
        if top_k <= 0:
            raise ValueError("top_k must be positive.")
        response = self._call_query(
            top_k=top_k,
            values=self._float32(values),
            metadata_filter=self._component_filter(component_ids),
        )
        results: list[SemanticSearchResult] = []
        for item in self._response_records(response):
            metadata = self._mapping_value(item, "metadata")
            results.append(
                SemanticSearchResult(
                    vector_key=self._string_value(item, "key"),
                    distance=self._distance(item),
                    metadata=self._metadata(metadata),
                )
            )
        return tuple(results)

    def get_vectors(self, keys: tuple[str, ...]) -> tuple[VectorRecord, ...]:
        if not keys:
            return ()
        response = self._call_get(keys)
        records: list[VectorRecord] = []
        for item in self._response_records(response):
            data = self._mapping_value(item, "data")
            values = self._float_values(data, "float32")
            records.append(
                VectorRecord(
                    key=self._string_value(item, "key"),
                    values=values,
                    metadata=self._metadata(self._mapping_value(item, "metadata")),
                )
            )
        return tuple(records)

    def delete_vectors(self, keys: tuple[str, ...]) -> None:
        if keys:
            self._call_delete(list(keys))

    def list_vectors(self, prefix: str | None = None) -> tuple[str, ...]:
        response = self._call_list(prefix)
        return tuple(self._string_value(item, "key") for item in self._response_records(response))

    def validate_index_dimensions(self) -> None:
        """Verify runtime embedding dimensions against the configured S3 Vector index."""
        response = self._call_get_index()
        index = self._mapping_value(response, "index")
        value = index.get("dimension")
        if not isinstance(value, int) or value != self._dimensions:
            raise VectorIndexUnavailableError(
                "Configured embedding dimensions do not match the S3 Vector index."
            )
        if index.get("dataType") != "float32":
            raise VectorIndexUnavailableError(
                "Configured S3 Vector index does not use float32 vectors."
            )

    def is_reachable(self) -> bool:
        try:
            self.validate_index_dimensions()
        except VectorIndexUnavailableError:
            return False
        return True

    def _call_put(self, vectors: list[Mapping[str, object]]) -> None:
        try:
            self._client.put_vectors(
                vectorBucketName=self._bucket_name,
                indexName=self._index_name,
                vectors=vectors,
            )
        except (ClientError, BotoCoreError) as exc:
            raise VectorIndexUnavailableError("Unable to write S3 Vectors.") from exc

    def _call_query(
        self,
        *,
        top_k: int,
        values: tuple[float, ...],
        metadata_filter: object | None,
    ) -> S3VectorsResponse:
        try:
            return self._client.query_vectors(
                vectorBucketName=self._bucket_name,
                indexName=self._index_name,
                topK=top_k,
                queryVector={"float32": values},
                filter=metadata_filter,
                returnMetadata=True,
                returnDistance=True,
            )
        except (ClientError, BotoCoreError) as exc:
            raise VectorIndexUnavailableError("Unable to query S3 Vectors.") from exc

    def _call_get(self, keys: tuple[str, ...]) -> S3VectorsResponse:
        try:
            return self._client.get_vectors(
                vectorBucketName=self._bucket_name,
                indexName=self._index_name,
                keys=list(keys),
                returnData=True,
                returnMetadata=True,
            )
        except (ClientError, BotoCoreError) as exc:
            raise VectorIndexUnavailableError("Unable to read S3 Vectors.") from exc

    def _call_delete(self, keys: list[str]) -> None:
        try:
            self._client.delete_vectors(
                vectorBucketName=self._bucket_name,
                indexName=self._index_name,
                keys=keys,
            )
        except (ClientError, BotoCoreError) as exc:
            raise VectorIndexUnavailableError("Unable to delete S3 Vectors.") from exc

    def _call_list(self, prefix: str | None) -> S3VectorsResponse:
        try:
            return self._client.list_vectors(
                vectorBucketName=self._bucket_name,
                indexName=self._index_name,
                prefix=prefix,
                returnData=False,
                returnMetadata=False,
            )
        except (ClientError, BotoCoreError) as exc:
            raise VectorIndexUnavailableError("Unable to list S3 Vectors.") from exc

    def _call_get_index(self) -> S3VectorsResponse:
        try:
            return self._client.get_index(
                vectorBucketName=self._bucket_name,
                indexName=self._index_name,
            )
        except (ClientError, BotoCoreError) as exc:
            raise VectorIndexUnavailableError("Unable to reach the S3 Vector index.") from exc

    def _float32(self, values: tuple[float, ...]) -> tuple[float, ...]:
        if len(values) != self._dimensions:
            raise ValueError(f"Vector must contain {self._dimensions} dimensions.")
        return tuple(struct.unpack("f", struct.pack("f", value))[0] for value in values)

    @staticmethod
    def _component_filter(component_ids: tuple[str, ...]) -> object | None:
        if not component_ids:
            return None
        return {"component_id": {"$in": list(component_ids)}}

    @staticmethod
    def _response_records(response: S3VectorsResponse) -> tuple[Mapping[str, object], ...]:
        values = response.get("vectors", ())
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            raise VectorIndexUnavailableError("S3 Vectors returned an invalid vector response.")
        if not all(isinstance(value, Mapping) for value in values):
            raise VectorIndexUnavailableError("S3 Vectors returned malformed vector records.")
        return tuple(value for value in values if isinstance(value, Mapping))

    @staticmethod
    def _mapping_value(record: Mapping[str, object], name: str) -> Mapping[str, object]:
        value = record.get(name)
        if not isinstance(value, Mapping):
            raise VectorIndexUnavailableError(f"S3 Vectors record is missing {name}.")
        return value

    @staticmethod
    def _float_values(record: Mapping[str, object], name: str) -> tuple[float, ...]:
        value = record.get(name)
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise VectorIndexUnavailableError(f"S3 Vectors record is missing {name}.")
        if not all(isinstance(item, (int, float)) for item in value):
            raise VectorIndexUnavailableError(f"S3 Vectors record has invalid {name}.")
        return tuple(float(item) for item in value)

    @staticmethod
    def _string_value(record: Mapping[str, object], name: str) -> str:
        value = record.get(name)
        if not isinstance(value, str) or not value:
            raise VectorIndexUnavailableError(f"S3 Vectors record is missing {name}.")
        return value

    @staticmethod
    def _metadata(value: Mapping[str, object]) -> VectorMetadata:
        try:
            return VectorMetadata.model_validate(value)
        except ValidationError as exc:
            raise VectorIndexUnavailableError("S3 Vectors returned invalid metadata.") from exc

    @staticmethod
    def _distance(record: Mapping[str, object]) -> float:
        value = record.get("distance")
        if not isinstance(value, (int, float)):
            raise VectorIndexUnavailableError("S3 Vectors record is missing distance.")
        return float(value)
