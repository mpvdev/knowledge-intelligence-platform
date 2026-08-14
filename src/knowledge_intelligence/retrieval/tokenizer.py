import re

DEFAULT_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "how",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "what",
        "when",
        "where",
        "which",
        "with",
    }
)


class SearchTokenizer:
    """Normalize text into searchable terms."""

    def __init__(
        self,
        stop_words: frozenset[str] = DEFAULT_STOP_WORDS,
    ) -> None:
        self._stop_words = stop_words

    def tokenize(self, text: str) -> tuple[str, ...]:
        terms = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_.:/-]*", text.lower())

        return tuple(term for term in terms if term not in self._stop_words and len(term) > 1)
