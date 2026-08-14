from pydantic import BaseModel, ConfigDict, Field


class RepositoryReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    local_path: str | None = Field(default=None, min_length=1)
    url: str | None = None
    purpose: str | None = None


class ComponentRelationship(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target_component_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    relationship_type: str = Field(min_length=1)
    evidence_type: str = Field(default="curated", min_length=1)
    description: str | None = None


class PlatformComponent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)

    aliases: tuple[str, ...] = ()
    repositories: tuple[RepositoryReference, ...] = ()
    documentation_prefixes: tuple[str, ...] = Field(default=(), min_length=1)
    relationships: tuple[ComponentRelationship, ...] = ()

    owner: str | None = None
    status: str = Field(default="active", min_length=1)
