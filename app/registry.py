"""Load the authoritative component-to-source mappings."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

import yaml

from app.models import Component, ContentBlock, ParsedDocument, SourceType

DEFAULT_GITHUB_ORGANIZATION = "sky-uk"


class ComponentRegistry:
    def __init__(self, directory: Path) -> None:
        self.components = self._load(directory)

    @staticmethod
    def _load(directory: Path) -> tuple[Component, ...]:
        if not directory.is_dir():
            raise ValueError(f"Component registry not found: {directory}")
        components: list[Component] = []
        for path in sorted(directory.glob("*.yaml")):
            raw = path.read_text(encoding="utf-8").strip()
            if raw:
                components.append(Component.model_validate(yaml.safe_load(raw)))
        if not components:
            raise ValueError(f"Component registry contains no components: {directory}")
        ids = [component.id for component in components]
        if len(ids) != len(set(ids)):
            raise ValueError("Component registry contains duplicate component IDs.")
        return tuple(components)

    def component_for_s3_key(self, key: str) -> Component | None:
        matches = [
            component
            for component in self.components
            if any(
                key.startswith(prefix) for prefix in component.documentation_prefixes
            )
        ]
        if len(matches) > 1:
            raise ValueError(f"Multiple components map the Confluence object: {key}")
        return matches[0] if matches else None

    def repositories(self) -> tuple[tuple[Component, str, str | None], ...]:
        return tuple(
            (
                component,
                self._repository_name(repository.name, repository.url),
                repository.branch,
            )
            for component in self.components
            for repository in component.repositories
        )

    def as_documents(self) -> tuple[ParsedDocument, ...]:
        documents: list[ParsedDocument] = []
        for component in self.components:
            repositories = ", ".join(
                name for _, name, _ in self._component_repositories(component)
            )
            prefixes = ", ".join(component.documentation_prefixes)
            text = "\n".join(
                value
                for value in (
                    f"Component: {component.name}",
                    f"Aliases: {', '.join(component.aliases)}"
                    if component.aliases
                    else "",
                    component.description.strip(),
                    f"Repositories: {repositories}" if repositories else "",
                    f"Confluence prefixes: {prefixes}" if prefixes else "",
                    f"Owner: {component.owner}" if component.owner else "",
                )
                if value
            )
            documents.append(
                ParsedDocument(
                    document_id=hashlib.sha256(
                        f"registry:{component.id}".encode()
                    ).hexdigest(),
                    title=f"{component.name} component registry",
                    source_type=SourceType.REGISTRY,
                    source_location=f"registry/components/{component.id}.yaml",
                    component_id=component.id,
                    blocks=(ContentBlock(text=text),),
                )
            )
        return tuple(documents)

    def _component_repositories(
        self, component: Component
    ) -> tuple[tuple[Component, str, str | None], ...]:
        return tuple(
            (
                component,
                self._repository_name(repository.name, repository.url),
                repository.branch,
            )
            for repository in component.repositories
        )

    @staticmethod
    def _repository_name(name: str, url: str | None) -> str:
        if url:
            parsed = urlparse(url)
            parts = tuple(part for part in parsed.path.split("/") if part)
            if (
                parsed.scheme != "https"
                or parsed.hostname != "github.com"
                or len(parts) != 2
            ):
                raise ValueError(
                    "Repository URL must be https://github.com/<owner>/<repository>."
                )
            return "/".join(parts)
        return name if "/" in name else f"{DEFAULT_GITHUB_ORGANIZATION}/{name}"


def load_registry(directory: Path) -> ComponentRegistry:
    return ComponentRegistry(directory)
