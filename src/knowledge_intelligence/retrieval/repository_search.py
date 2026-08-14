"""Deterministic retrieval over approved local repository source files."""

from knowledge_intelligence.domain.repository_knowledge import RepositoryCodeFile
from knowledge_intelligence.retrieval.tokenizer import SearchTokenizer


class RepositoryCodeSearchService:
    """Find concise, line-cited code evidence without executing repository code."""

    def __init__(
        self,
        repository_name: str,
        files: tuple[RepositoryCodeFile, ...],
        tokenizer: SearchTokenizer,
    ) -> None:
        self._repository_name = repository_name
        self._files = files
        self._tokenizer = tokenizer

    def search(self, query: str, limit: int) -> tuple[tuple[RepositoryCodeFile, int, float], ...]:
        if limit <= 0:
            raise ValueError("limit must be positive.")
        terms = tuple(dict.fromkeys(self._tokenizer.tokenize(query)))
        if not terms:
            return ()

        matches: list[tuple[RepositoryCodeFile, int, float]] = []
        for source_file in self._files:
            normalized_lines = tuple(line.casefold() for line in source_file.content.splitlines())
            matching_lines = tuple(
                index
                for index, line in enumerate(normalized_lines)
                if any(term in line for term in terms)
            )
            if not matching_lines:
                continue
            score = sum(sum(term in line for term in terms) for line in normalized_lines)
            matches.append((source_file, matching_lines[0] + 1, float(score)))

        return tuple(sorted(matches, key=lambda item: (-item[2], item[0].relative_path))[:limit])

    @staticmethod
    def excerpt(source_file: RepositoryCodeFile, start_line: int, context_lines: int = 4) -> str:
        lines = source_file.content.splitlines()
        first = max(start_line - 1 - context_lines, 0)
        last = min(start_line + context_lines, len(lines))
        return "\n".join(lines[first:last])
