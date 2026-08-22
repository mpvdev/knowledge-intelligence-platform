#!/usr/bin/env python3
"""Stamp registry notes that are missing a `recorded` date.

Run before committing a new note, or wire it in as a pre-commit hook. The date is
written once, at authoring time: defaulting it at load time would refresh every
note on every deploy and hide exactly the staleness the field exists to reveal.

    python scripts/stamp_notes.py
    python scripts/stamp_notes.py --check
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
NOTE_ITEM = re.compile(r"^(\s+)- note:", re.MULTILINE)


def stamp(text: str, today: str) -> tuple[str, int]:
    """Insert `recorded` after any note item that lacks one."""
    lines = text.splitlines()
    output: list[str] = []
    added = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        output.append(line)
        match = NOTE_ITEM.match(line)
        if match is None:
            index += 1
            continue
        indent = match.group(1)
        item = [line]
        index += 1
        while index < len(lines):
            following = lines[index]
            if following.strip() and not following.startswith(indent + "  "):
                break
            item.append(following)
            output.append(following)
            index += 1
        if not any(re.match(rf"^{indent}  recorded:", entry) for entry in item):
            output.append(f"{indent}  recorded: {today}")
            added += 1
    return "\n".join(output) + "\n", added


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if a note is unstamped")
    parser.add_argument(
        "--directory", type=Path, default=REPOSITORY_ROOT / "registry/components"
    )
    arguments = parser.parse_args()

    today = date.today().isoformat()
    unstamped = 0
    for path in sorted(arguments.directory.glob("*.yaml")):
        original = path.read_text(encoding="utf-8")
        updated, added = stamp(original, today)
        if not added:
            continue
        unstamped += added
        if arguments.check:
            print(f"{path}: {added} note(s) missing a recorded date")
            continue
        path.write_text(updated, encoding="utf-8")
        print(f"{path}: stamped {added} note(s) with {today}")

    if arguments.check and unstamped:
        sys.exit(1)
    if not unstamped:
        print("Every note already carries a recorded date.")


if __name__ == "__main__":
    main()
