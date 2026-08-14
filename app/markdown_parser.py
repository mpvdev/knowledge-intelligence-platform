"""README Markdown-to-ParsedDocument conversion."""

import re

from app.models import ContentBlock, ParsedDocument, SourceType

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def parse_markdown(
    content: str,
    *,
    document_id: str,
    title: str,
    source_location: str,
    component_id: str,
) -> ParsedDocument:
    blocks: list[ContentBlock] = []
    headings: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        text = "\n".join(buffer).strip()
        if text:
            blocks.append(ContentBlock(text=text, heading_path=tuple(headings)))
        buffer.clear()

    for line in content.splitlines():
        match = HEADING.match(line)
        if not match:
            buffer.append(line)
            continue
        flush()
        level = len(match.group(1))
        headings[level - 1 :] = [match.group(2).strip()]
    flush()

    if not blocks:
        raise ValueError(f"README contains no content: {source_location}")
    return ParsedDocument(
        document_id=document_id,
        title=title,
        source_type=SourceType.GITHUB,
        source_location=source_location,
        component_id=component_id,
        blocks=tuple(blocks),
    )
