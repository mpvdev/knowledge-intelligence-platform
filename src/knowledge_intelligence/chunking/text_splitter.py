import re


class TextSplitter:
    """Split long text into bounded chunks while preserving overlap."""

    def __init__(
        self,
        max_characters: int = 2_000,
        overlap_characters: int = 250,
    ) -> None:
        if max_characters <= 0:
            raise ValueError("max_characters must be greater than zero.")

        if overlap_characters < 0:
            raise ValueError("overlap_characters cannot be negative.")

        if overlap_characters >= max_characters:
            raise ValueError("overlap_characters must be smaller than max_characters.")

        self._max_characters = max_characters
        self._overlap_characters = overlap_characters

    def split(self, text: str) -> tuple[str, ...]:
        normalized = text.strip()

        if not normalized:
            return ()

        if len(normalized) <= self._max_characters:
            return (normalized,)

        paragraphs = tuple(
            paragraph.strip() for paragraph in re.split(r"\n\s*\n", normalized) if paragraph.strip()
        )

        chunks: list[str] = []
        current = ""

        for paragraph in paragraphs:
            if len(paragraph) > self._max_characters:
                if current:
                    chunks.append(current)
                    current = ""

                chunks.extend(self._split_large_text(paragraph))
                continue

            candidate = f"{current}\n\n{paragraph}" if current else paragraph

            if len(candidate) <= self._max_characters:
                current = candidate
                continue

            chunks.append(current)

            overlap = current[-self._overlap_characters :].strip()
            current = f"{overlap}\n\n{paragraph}" if overlap else paragraph

        if current:
            chunks.append(current)

        return tuple(chunks)

    def _split_large_text(self, text: str) -> list[str]:
        chunks: list[str] = []
        start = 0

        while start < len(text):
            end = min(start + self._max_characters, len(text))
            chunk = text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            if end == len(text):
                break

            start = end - self._overlap_characters

        return chunks
