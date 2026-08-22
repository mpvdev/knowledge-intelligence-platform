"""The registry is the authoritative mapping; nothing may be inferred."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

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


def write(directory: Path, name: str, body: str) -> None:
    (directory / f"{name}.yaml").write_text(body, encoding="utf-8")


BASE = """
id: {id}
name: {name}
description: A component.
"""


def test_an_empty_registry_file_is_a_hard_error(tmp_path: Path) -> None:
    write(tmp_path, "good", BASE.format(id="good", name="Good"))
    (tmp_path / "empty.yaml").write_text("   \n", encoding="utf-8")

    with pytest.raises(ValueError, match="empty"):
        ComponentRegistry(tmp_path)


def test_a_relationship_to_an_unknown_component_is_rejected(tmp_path: Path) -> None:
    write(
        tmp_path,
        "hub",
        BASE.format(id="hub", name="Hub")
        + "related:\n  - id: missing\n    relationship: Includes\n",
    )

    with pytest.raises(ValueError, match="unknown component"):
        ComponentRegistry(tmp_path)


def test_a_component_cannot_relate_to_itself(tmp_path: Path) -> None:
    write(
        tmp_path,
        "hub",
        BASE.format(id="hub", name="Hub")
        + "related:\n  - id: hub\n    relationship: Includes\n",
    )

    with pytest.raises(ValueError, match="related to itself"):
        ComponentRegistry(tmp_path)


def test_relationships_are_indexed_as_sentences(tmp_path: Path) -> None:
    write(tmp_path, "leaf", BASE.format(id="leaf", name="Leaf Service") + "part_of: hub\n")
    write(
        tmp_path,
        "hub",
        BASE.format(id="hub", name="Hub")
        + "related:\n  - id: leaf\n    relationship: Includes\n",
    )
    registry = ComponentRegistry(tmp_path)

    document = next(d for d in registry.as_documents() if d.component_id == "hub")
    assert "Hub includes Leaf Service." in document.blocks[0].text


def test_a_contact_is_never_indexed(tmp_path: Path) -> None:
    write(
        tmp_path,
        "hub",
        BASE.format(id="hub", name="Hub")
        + 'contact:\n  name: Platform Engineering\n  slack: "#tme-support"\n',
    )
    registry = ComponentRegistry(tmp_path)

    document = registry.as_documents()[0]
    assert "tme-support" not in document.blocks[0].text
    assert "Platform Engineering" not in document.blocks[0].text


def test_a_component_can_be_found_by_id(tmp_path: Path) -> None:
    write(tmp_path, "hub", BASE.format(id="hub", name="Hub"))
    registry = ComponentRegistry(tmp_path)

    assert registry.component_by_id("hub") is not None
    assert registry.component_by_id("nope") is None


def test_a_component_that_forgets_its_parent_is_rejected(tmp_path: Path) -> None:
    write(tmp_path, "hub", BASE.format(id="hub", name="Hub"))
    write(tmp_path, "orphan", BASE.format(id="orphan", name="Orphan"))

    with pytest.raises(ValueError, match="Exactly one component must be the root"):
        ComponentRegistry(tmp_path)


def test_a_parent_that_does_not_exist_is_rejected(tmp_path: Path) -> None:
    write(tmp_path, "hub", BASE.format(id="hub", name="Hub"))
    write(tmp_path, "leaf", BASE.format(id="leaf", name="Leaf") + "part_of: missing\n")

    with pytest.raises(ValueError, match="part of an unknown component"):
        ComponentRegistry(tmp_path)


def test_a_hierarchy_cycle_is_rejected(tmp_path: Path) -> None:
    write(tmp_path, "hub", BASE.format(id="hub", name="Hub"))
    write(tmp_path, "a", BASE.format(id="a", name="A") + "part_of: b\n")
    write(tmp_path, "b", BASE.format(id="b", name="B") + "part_of: a\n")

    with pytest.raises(ValueError, match="cycle"):
        ComponentRegistry(tmp_path)


def test_membership_is_stated_from_both_sides(tmp_path: Path) -> None:
    write(tmp_path, "hub", BASE.format(id="hub", name="Hub"))
    write(tmp_path, "leaf", BASE.format(id="leaf", name="Leaf Service") + "part_of: hub\n")
    registry = ComponentRegistry(tmp_path)

    documents = {d.component_id: d.blocks[0].text for d in registry.as_documents()}
    assert "Leaf Service is part of Hub." in documents["leaf"]
    assert "Hub includes Leaf Service." in documents["hub"]


def test_a_new_component_joins_the_hierarchy_without_editing_the_hub(tmp_path: Path) -> None:
    write(tmp_path, "hub", BASE.format(id="hub", name="Hub"))
    write(tmp_path, "first", BASE.format(id="first", name="First") + "part_of: hub\n")
    write(tmp_path, "second", BASE.format(id="second", name="Second") + "part_of: hub\n")
    registry = ComponentRegistry(tmp_path)

    assert {c.id for c in registry.children_of("hub")} == {"first", "second"}
    hub = next(d for d in registry.as_documents() if d.component_id == "hub")
    assert "Hub includes First." in hub.blocks[0].text
    assert "Hub includes Second." in hub.blocks[0].text


def test_the_shipped_registry_has_a_single_root() -> None:
    registry = ComponentRegistry(Path("registry/components"))

    roots = [c.id for c in registry.components if c.part_of is None]
    assert roots == ["tme-platform"]
    assert len(registry.children_of("tme-platform")) == len(registry.components) - 1


def test_the_shipped_registry_still_loads() -> None:
    registry = ComponentRegistry(Path("registry/components"))

    assert {component.id for component in registry.components} >= {
        "eks-service",
        "osbuilds",
        "patch-mgmt",
        "tme-platform",
    }


def test_a_nested_component_can_be_four_levels_deep(tmp_path: Path) -> None:
    write(tmp_path, "tme", BASE.format(id="tme", name="TME"))
    write(tmp_path, "eks", BASE.format(id="eks", name="EKS") + "part_of: tme\n")
    write(tmp_path, "found", BASE.format(id="found", name="Foundation") + "part_of: eks\n")
    write(tmp_path, "pools", BASE.format(id="pools", name="Node Pools") + "part_of: found\n")
    registry = ComponentRegistry(tmp_path)

    documents = {d.component_id: d.blocks[0].text for d in registry.as_documents()}
    assert "Foundation is part of EKS." in documents["found"]
    assert "Foundation includes Node Pools." in documents["found"]


def test_a_nested_component_claims_documents_inside_its_parents_prefix(tmp_path: Path) -> None:
    write(tmp_path, "tme", BASE.format(id="tme", name="TME"))
    write(
        tmp_path,
        "eks",
        BASE.format(id="eks", name="EKS")
        + "part_of: tme\ndocumentation_prefixes:\n  - raw/confluence/eks\n",
    )
    write(
        tmp_path,
        "oidc",
        BASE.format(id="oidc", name="EKS OIDC")
        + "part_of: eks\ndocumentation_prefixes:\n  - raw/confluence/eks/oidc\n",
    )
    registry = ComponentRegistry(tmp_path)

    nested = registry.component_for_s3_key("raw/confluence/eks/oidc/doc.pdf")
    parent = registry.component_for_s3_key("raw/confluence/eks/other.pdf")
    assert nested is not None and nested.id == "oidc"
    assert parent is not None and parent.id == "eks"


def test_two_components_claiming_the_same_prefix_is_still_an_error(tmp_path: Path) -> None:
    write(tmp_path, "tme", BASE.format(id="tme", name="TME"))
    for name in ("one", "two"):
        write(
            tmp_path,
            name,
            BASE.format(id=name, name=name.title())
            + "part_of: tme\ndocumentation_prefixes:\n  - raw/confluence/shared\n",
        )
    registry = ComponentRegistry(tmp_path)

    with pytest.raises(ValueError, match="Multiple components map"):
        registry.component_for_s3_key("raw/confluence/shared/doc.pdf")


NOTE = """notes:
  - note: Windows images follow the RHEL build process.
    recorded: 2026-08-22
    source: Platform sync with Jane
"""


def test_a_note_is_indexed_as_knowledge(tmp_path: Path) -> None:
    write(tmp_path, "hub", BASE.format(id="hub", name="Hub") + NOTE)
    registry = ComponentRegistry(tmp_path)

    document = registry.as_documents()[0]
    assert "Windows images follow the RHEL build process." in document.blocks[0].text


def test_note_provenance_is_never_indexed(tmp_path: Path) -> None:
    write(tmp_path, "hub", BASE.format(id="hub", name="Hub") + NOTE)
    registry = ComponentRegistry(tmp_path)

    text = registry.as_documents()[0].blocks[0].text
    assert "Jane" not in text
    assert "Platform sync" not in text
    assert "2026-08-22" not in text


def test_a_note_must_be_dated(tmp_path: Path) -> None:
    write(
        tmp_path,
        "hub",
        BASE.format(id="hub", name="Hub") + "notes:\n  - note: Undated knowledge.\n",
    )

    with pytest.raises(ValidationError):
        ComponentRegistry(tmp_path)


def test_an_empty_note_is_rejected(tmp_path: Path) -> None:
    write(
        tmp_path,
        "hub",
        BASE.format(id="hub", name="Hub") + 'notes:\n  - note: ""\n    recorded: 2026-08-22\n',
    )

    with pytest.raises(ValidationError):
        ComponentRegistry(tmp_path)


def test_a_component_may_carry_several_notes(tmp_path: Path) -> None:
    body = (
        BASE.format(id="hub", name="Hub")
        + "notes:\n"
        + "  - note: First fact.\n    recorded: 2026-08-01\n"
        + "  - note: Second fact.\n    recorded: 2026-08-22\n"
    )
    write(tmp_path, "hub", body)
    registry = ComponentRegistry(tmp_path)

    text = registry.as_documents()[0].blocks[0].text
    assert "First fact." in text and "Second fact." in text
    assert len(registry.components[0].notes) == 2


def test_the_shipped_windows_note_is_recorded() -> None:
    registry = ComponentRegistry(Path("registry/components"))
    osbuilds = registry.component_by_id("osbuilds")

    assert osbuilds is not None
    assert any("Windows" in note.note for note in osbuilds.notes)
    assert all(note.recorded for note in osbuilds.notes)
