from __future__ import annotations

from typing import TYPE_CHECKING, cast

import boto3

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

from knowledge_intelligence.connectors.s3vectors_repository import S3VectorsClient


def create_s3_client(region_name: str) -> S3Client:
    """Create an S3 client using the standard AWS credential chain."""
    return boto3.client("s3", region_name=region_name)


def create_s3vectors_client(region_name: str) -> S3VectorsClient:
    """Create an S3 Vectors client using the standard AWS credential chain."""
    return cast(S3VectorsClient, boto3.client("s3vectors", region_name=region_name))
