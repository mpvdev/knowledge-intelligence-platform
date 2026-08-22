"""Notes are dated once, at authoring time."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _module() -> Any:
    spec = importlib.util.spec_from_file_location("stamp_notes", "scripts/stamp_notes.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


UNSTAMPED = """id: demo
name: Demo
description: x

notes:
  - note: A fact from a call.
    source: Platform sync
"""


def test_a_missing_date_is_added() -> None:
    updated, added = _module().stamp(UNSTAMPED, "2026-08-22")

    assert added == 1
    assert "recorded: 2026-08-22" in updated
    assert "source: Platform sync" in updated


def test_an_existing_date_is_left_alone() -> None:
    text = UNSTAMPED + "  - note: Older.\n    recorded: 2026-01-05\n"
    updated, added = _module().stamp(text, "2026-08-22")

    assert added == 1
    assert "recorded: 2026-01-05" in updated
    assert updated.count("recorded:") == 2


def test_a_file_without_notes_is_untouched() -> None:
    text = "id: demo\nname: Demo\ndescription: x\n"
    updated, added = _module().stamp(text, "2026-08-22")

    assert added == 0
    assert updated.strip() == text.strip()


def test_stamping_twice_changes_nothing() -> None:
    module = _module()
    once, _ = module.stamp(UNSTAMPED, "2026-08-22")
    twice, added = module.stamp(once, "2026-08-23")

    assert added == 0
    assert once == twice


def test_the_shipped_registry_is_fully_stamped() -> None:
    module = _module()
    for path in sorted(Path("registry/components").glob("*.yaml")):
        _, added = module.stamp(path.read_text(encoding="utf-8"), "2026-08-22")
        assert added == 0, path
