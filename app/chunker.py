"""Deterministic document chunking."""

import hashlib
import re

from app.models import Chunk, ParsedDocument


def chunk_document(
    document: ParsedDocument,
    *,
    max_characters: int = 2_000,
    overlap_characters: int = 250,
) -> tuple[Chunk, ...]:
    chunks: list[Chunk] = []
    for block in document.blocks:
        for text in _split(block.text, max_characters, overlap_characters):
            sequence = len(chunks)
            identity = f"{document.document_id}:{sequence}:{text}".encode()
            chunks.append(
                Chunk(
                    chunk_id=hashlib.sha256(identity).hexdigest(),
                    document_id=document.document_id,
                    title=document.title,
                    text=text,
                    source_type=document.source_type,
                    source_location=document.source_location,
                    component_id=document.component_id,
                    page_number=block.page_number,
                    heading_path=block.heading_path,
                    visual_description=block.visual_description,
                )
            )
    return tuple(chunks)


def _split(text: str, maximum: int, overlap: int) -> tuple[str, ...]:
    normalized = text.strip()
    if len(normalized) <= maximum:
        return (normalized,) if normalized else ()
    parts: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + maximum, len(normalized))
        if end < len(normalized):
            boundary = max(
                normalized.rfind("\n\n", start, end), normalized.rfind(". ", start, end)
            )
            if boundary > start + maximum // 2:
                end = boundary + 1
        part = re.sub(r"\n{3,}", "\n\n", normalized[start:end]).strip()
        if part:
            parts.append(part)
        if end == len(normalized):
            break
        start = max(end - overlap, start + 1)
    return tuple(parts)
