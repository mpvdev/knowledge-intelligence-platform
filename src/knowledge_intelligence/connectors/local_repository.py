"""Read-only local repository access for explicit operator-run documentation jobs."""

from __future__ import annotations

from pathlib import Path

from knowledge_intelligence.domain.repository_knowledge import RepositoryCodeFile

SUPPORTED_SOURCE_SUFFIXES = frozenset(
    {".py", ".tf", ".md", ".toml", ".yaml", ".yml", ".json", ".ts", ".tsx", ".js"}
)
EXCLUDED_DIRECTORIES = frozenset(
    {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "node_modules"}
)


class LocalRepositoryAccessError(RuntimeError):
    """The requested local repository cannot be safely read."""


class LocalRepositoryReader:
    """Read an explicit local repository without following links outside its root."""

    def __init__(
        self,
        *,
        maximum_files: int = 2_000,
        maximum_file_bytes: int = 1_000_000,
    ) -> None:
        if maximum_files <= 0 or maximum_file_bytes <= 0:
            raise ValueError("Repository read limits must be positive.")
        self._maximum_files = maximum_files
        self._maximum_file_bytes = maximum_file_bytes

    def read(self, repository_path: Path) -> tuple[RepositoryCodeFile, ...]:
        root = repository_path.resolve()
        if not root.is_dir():
            raise LocalRepositoryAccessError("Repository path must be an existing directory.")

        source_files: list[RepositoryCodeFile] = []
        for candidate in sorted(root.rglob("*")):
            if self._is_excluded(candidate, root) or not candidate.is_file():
                continue
            resolved = candidate.resolve()
            if (
                not resolved.is_relative_to(root)
                or candidate.suffix.lower() not in SUPPORTED_SOURCE_SUFFIXES
            ):
                continue
            if candidate.stat().st_size > self._maximum_file_bytes:
                continue
            content = self._read_utf8(candidate)
            if content is None:
                continue
            source_files.append(
                RepositoryCodeFile(
                    relative_path=candidate.relative_to(root).as_posix(),
                    content=content,
                    line_count=max(1, content.count("\n") + 1),
                )
            )
            if len(source_files) >= self._maximum_files:
                break
        return tuple(source_files)

    @staticmethod
    def _is_excluded(candidate: Path, root: Path) -> bool:
        return any(part in EXCLUDED_DIRECTORIES for part in candidate.relative_to(root).parts)

    @staticmethod
    def _read_utf8(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return None
