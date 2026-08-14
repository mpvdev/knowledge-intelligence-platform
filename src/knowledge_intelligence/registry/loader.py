from pathlib import Path

import yaml
from pydantic import ValidationError
from yaml import YAMLError

from knowledge_intelligence.registry.models import PlatformComponent
from knowledge_intelligence.registry.registry import ComponentRegistry


class ComponentRegistryLoadError(ValueError):
    """Raised when curated component configuration cannot be loaded."""


class ComponentRegistryLoader:
    """Load and validate curated component definitions from YAML files."""

    def load(
        self,
        directory: Path,
        *,
        allow_empty_placeholders: bool = False,
    ) -> ComponentRegistry:
        """Load a complete component registry from a directory."""
        if not directory.is_dir():
            raise ComponentRegistryLoadError(f"Registry directory not found: {directory}")

        paths = tuple(sorted(directory.glob("*.yaml")))
        if not paths:
            raise ComponentRegistryLoadError(f"No component YAML files found in: {directory}")

        try:
            empty_paths = tuple(
                path for path in paths if not path.read_text(encoding="utf-8").strip()
            )
        except OSError as exc:
            raise ComponentRegistryLoadError(
                f"Unable to inspect component files in: {directory}"
            ) from exc
        if empty_paths and not allow_empty_placeholders:
            names = ", ".join(path.name for path in empty_paths)
            raise ComponentRegistryLoadError(f"Empty component files found in: {names}")
        populated_paths = tuple(path for path in paths if path not in empty_paths)
        if not populated_paths:
            raise ComponentRegistryLoadError(
                f"No populated component YAML files found in: {directory}"
            )

        return ComponentRegistry(tuple(self._load_component(path) for path in populated_paths))

    @staticmethod
    def _load_component(path: Path) -> PlatformComponent:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            if payload is None:
                raise ComponentRegistryLoadError(f"Component file is empty: {path}")
            return PlatformComponent.model_validate(payload)
        except ComponentRegistryLoadError:
            raise
        except (OSError, UnicodeError, YAMLError, ValidationError) as exc:
            raise ComponentRegistryLoadError(f"Invalid component file {path}: {exc}") from exc
