"""Read approved Confluence PDF exports from Amazon S3."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import PurePosixPath

import boto3
from botocore.exceptions import BotoCoreError, ClientError


class S3Reader:
    def __init__(self, region: str, bucket: str, maximum_bytes: int) -> None:
        self.client = boto3.client("s3", region_name=region)
        self.bucket = bucket
        self.maximum_bytes = maximum_bytes

    def list_pdfs(self, prefix: str) -> tuple[str, ...]:
        keys: list[str] = []
        try:
            pages = self.client.get_paginator("list_objects_v2").paginate(
                Bucket=self.bucket,
                Prefix=prefix,
            )
            for page in pages:
                for item in page.get("Contents", ()):
                    key = str(item["Key"])
                    if (
                        PurePosixPath(key).suffix.casefold() == ".pdf"
                        and int(item.get("Size", 0)) <= self.maximum_bytes
                    ):
                        keys.append(key)
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError("Unable to list approved Confluence PDFs.") from exc
        return tuple(sorted(keys))

    def read(self, key: str) -> bytes:
        if PurePosixPath(key).suffix.casefold() != ".pdf":
            raise ValueError("Only PDF Confluence exports are supported.")
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            if int(response.get("ContentLength", 0)) > self.maximum_bytes:
                raise ValueError(f"PDF exceeds the configured size limit: {key}")
            body = response["Body"]
            try:
                content = body.read(self.maximum_bytes + 1)
            finally:
                body.close()
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Unable to read Confluence PDF: {key}") from exc
        if len(content) > self.maximum_bytes:
            raise ValueError(f"PDF exceeds the configured size limit: {key}")
        return content

    def iter_pdfs(self, prefix: str) -> Iterator[tuple[str, bytes]]:
        for key in self.list_pdfs(prefix):
            yield key, self.read(key)
