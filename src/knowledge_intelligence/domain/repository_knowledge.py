"""Domain models for source-grounded repository knowledge retrieval."""

from pydantic import BaseModel, ConfigDict, Field


class RepositoryCodeFile(BaseModel):
    """One UTF-8 code or configuration file in an approved local repository."""

    model_config = ConfigDict(frozen=True)

    relative_path: str = Field(min_length=1)
    content: str
    line_count: int = Field(ge=1)
    repository_name: str | None = None
    revision: str | None = None
    html_url: str | None = None


class RepositoryCodeEvidence(BaseModel):
    """A short, line-cited code excerpt returned to the Repository Knowledge Agent."""

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(pattern=r"^R[1-9][0-9]*$")
    repository_name: str
    relative_path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    excerpt: str = Field(min_length=1)
    score: float = Field(ge=0)
    revision: str | None = None
    html_url: str | None = None


class RepositorySearchResponse(BaseModel):
    """Structured code evidence returned by a repository search tool."""

    model_config = ConfigDict(frozen=True)

    query: str
    evidence: tuple[RepositoryCodeEvidence, ...]
