from pydantic import BaseModel, ConfigDict, Field


class GitHubRepositorySummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    full_name: str = Field(min_length=3)


class GitHubCodeSearchItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    path: str = Field(min_length=1)
    sha: str = Field(min_length=1)
    html_url: str
    repository: GitHubRepositorySummary


class GitHubCodeSearchPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    items: tuple[GitHubCodeSearchItem, ...] = ()


class GitHubBlobPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    content: str
    encoding: str
    size: int = Field(ge=0)
