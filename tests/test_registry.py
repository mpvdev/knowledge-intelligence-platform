"""The registry is the authoritative mapping; nothing may be inferred."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.registry import ComponentRegistry

REGISTRY = Path("registry/components")


@pytest.fixture(scope="module")
def registry() -> ComponentRegistry:
    return ComponentRegistry(REGISTRY)


def test_blank_component_files_are_skipped(registry: ComponentRegistry) -> None:
    # concourse.yaml is an empty placeholder and must not become a component.
    assert all(component.id for component in registry.components)
    assert "concourse" not in {component.id for component in registry.components}


def test_repository_names_are_fully_qualified(registry: ComponentRegistry) -> None:
    for _component, name, _branch in registry.repositories():
        assert "/" in name, f"{name} is not owner/repository"


def test_documents_describe_each_component(registry: ComponentRegistry) -> None:
    documents = registry.as_documents()
    assert len(documents) == len(registry.components)
    assert all(document.blocks for document in documents)


def test_confluence_prefix_maps_to_one_component(registry: ComponentRegistry) -> None:
    component = registry.component_for_s3_key("raw/confluence/eks/page.pdf")
    assert component is not None
    assert component.id == "eks-service"


def test_unmapped_source_is_not_guessed(registry: ComponentRegistry) -> None:
    assert registry.component_for_s3_key("raw/confluence/unknown/page.pdf") is None


def test_missing_registry_directory_is_rejected() -> None:
    with pytest.raises(ValueError, match="Component registry not found"):
        ComponentRegistry(Path("registry/does-not-exist"))
