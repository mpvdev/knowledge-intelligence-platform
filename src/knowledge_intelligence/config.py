from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="KNOWLEDGE_INTELLIGENCE_",
        case_sensitive=False,
        extra="ignore",
    )

    aws_region: str = "ap-south-1"
    s3_bucket: str
    s3_prefix: str = "raw/confluence/"
    max_document_size_mb: int = Field(default=50, gt=0, le=500)

    openai_api_key: SecretStr
    openai_model: str
    agent_max_search_results: int = Field(default=5, ge=1, le=10)
    component_registry_directory: Path | None = None
    repository_local_root: Path | None = None
    repository_maximum_files: int = Field(default=2_000, ge=1, le=10_000)
    repository_maximum_file_bytes: int = Field(default=1_000_000, ge=1_024, le=10_000_000)

    github_token: SecretStr = SecretStr("")
    github_api_url: str = "https://api.github.com"
    github_api_version: str = "2026-03-10"
    github_organization: str | None = None
    github_repositories: tuple[str, ...] = ()
    github_maximum_results: int = Field(default=5, ge=1, le=20)
    github_maximum_file_bytes: int = Field(default=1_000_000, ge=1_024, le=10_000_000)

    slack_enabled: bool = False
    slack_bot_token: SecretStr = SecretStr("")
    slack_signing_secret: SecretStr = SecretStr("")
    slack_max_message_length: int = Field(default=3_500, ge=500, le=4_000)

    visual_minimum_text_characters: int = Field(
        default=150,
        ge=0,
        le=10_000,
    )

    visual_minimum_image_area_ratio: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
    )

    visual_render_dpi: int = Field(
        default=144,
        ge=72,
        le=300,
    )

    visual_max_pages_per_document: int = Field(
        default=10,
        ge=1,
        le=100,
    )

    visual_analysis_model: str | None = None

    visual_analysis_prompt_version: str = "visual-analysis-v1"

    visual_analysis_max_image_bytes: int = Field(
        default=10_000_000,
        ge=100_000,
        le=20_000_000,
    )

    vector_search_enabled: bool = False

    vector_bucket_name: str | None = None
    vector_index_name: str = "platform-knowledge"

    embedding_model: str = "text-embedding-3-small"

    embedding_dimensions: int = Field(
        default=1536,
        ge=1,
        le=4096,
    )

    embedding_batch_size: int = Field(
        default=16,
        ge=1,
        le=256,
    )

    vector_top_k: int = Field(
        default=5,
        ge=1,
        le=30,
    )

    retrieval_mode: Literal["keyword_only", "semantic_only", "hybrid"] = "keyword_only"
    chunking_version: str = Field(default="v1", min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_slack_configuration(self) -> Settings:
        if self.vector_search_enabled and not self.vector_bucket_name:
            raise ValueError("VECTOR_BUCKET_NAME is required when vector search is enabled.")

        if not self.slack_enabled:
            return self

        missing = [
            name
            for name, value in (
                ("SLACK_BOT_TOKEN", self.slack_bot_token),
                ("SLACK_SIGNING_SECRET", self.slack_signing_secret),
            )
            if not value.get_secret_value().strip()
        ]
        if missing:
            variables = ", ".join(f"KNOWLEDGE_INTELLIGENCE_{name}" for name in missing)
            raise ValueError(f"Slack is enabled but required settings are empty: {variables}")

        return self

    @property
    def max_document_size_bytes(self) -> int:
        return self.max_document_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    # BaseSettings supplies required values from the environment.
    return Settings()  # type: ignore[call-arg]
