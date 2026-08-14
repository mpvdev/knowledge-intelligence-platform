"""S3 document storage connector."""

from knowledge_intelligence.connectors.s3.client import create_s3_client
from knowledge_intelligence.connectors.s3.repository import S3DocumentRepository

__all__ = ["S3DocumentRepository", "create_s3_client"]
