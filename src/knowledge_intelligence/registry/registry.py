from collections.abc import Mapping
from types import MappingProxyType

from knowledge_intelligence.registry.models import PlatformComponent


class ComponentRegistry:
    """Immutable lookup index for curated platform components."""

    def __init__(self, components: tuple[PlatformComponent, ...]) -> None:
        component_index = self._index_components(components)
        self._components: Mapping[str, PlatformComponent] = MappingProxyType(component_index)
        self._aliases: Mapping[str, str] = MappingProxyType(self._index_aliases(components))
        self._document_prefixes = self._index_document_prefixes(components)

    def get(self, component_id: str) -> PlatformComponent:
        """Return a component by its canonical identifier."""
        return self._components[component_id]

    def list_components(self) -> tuple[PlatformComponent, ...]:
        """Return components in their configured order."""
        return tuple(self._components.values())

    def resolve_alias(self, value: str) -> PlatformComponent | None:
        """Resolve a component ID, name or alias without case sensitivity."""
        component_id = self._aliases.get(self._normalize(value))
        return self._components.get(component_id) if component_id is not None else None

    def resolve_document_key(self, key: str) -> PlatformComponent | None:
        """Resolve an S3 key using the most specific configured prefix."""
        for prefix, component_id in self._document_prefixes:
            if key.startswith(prefix):
                return self._components[component_id]
        return None

    @staticmethod
    def _index_components(
        components: tuple[PlatformComponent, ...],
    ) -> dict[str, PlatformComponent]:
        index: dict[str, PlatformComponent] = {}
        for component in components:
            if component.id in index:
                raise ValueError(f"Duplicate component ID: {component.id!r}.")
            index[component.id] = component
        return index

    @classmethod
    def _index_aliases(cls, components: tuple[PlatformComponent, ...]) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for component in components:
            for value in (component.id, component.name, *component.aliases):
                normalized = cls._normalize(value)
                existing_component = aliases.get(normalized)
                if existing_component is not None and existing_component != component.id:
                    raise ValueError(
                        f"Component alias {value!r} is shared by "
                        f"{existing_component!r} and {component.id!r}."
                    )
                aliases[normalized] = component.id
        return aliases

    @staticmethod
    def _index_document_prefixes(
        components: tuple[PlatformComponent, ...],
    ) -> tuple[tuple[str, str], ...]:
        prefixes: dict[str, str] = {}
        for component in components:
            for prefix in component.documentation_prefixes:
                existing_component = prefixes.get(prefix)
                if existing_component is not None and existing_component != component.id:
                    raise ValueError(
                        f"Documentation prefix {prefix!r} is shared by "
                        f"{existing_component!r} and {component.id!r}."
                    )
                prefixes[prefix] = component.id

        return tuple(sorted(prefixes.items(), key=lambda item: len(item[0]), reverse=True))

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().casefold()
