import re

CITATION_PATTERN = re.compile(r"\s*(?:\[S\d+])+")
SOURCE_ATTRIBUTION_PATTERN = re.compile(
    r"\b(?:the\s+)?(?:available\s+|approved\s+|indexed\s+|platform\s+)?"
    r"documentation\s+(?:states|says|indicates|notes|confirms|specifies)\s+"
    r"(?:that\s+)?",
    re.IGNORECASE,
)
DOCUMENTED_AS_PATTERN = re.compile(
    r"\b(is|are|was|were)\s+documented\s+as\b",
    re.IGNORECASE,
)
DOCUMENTED_QUALIFIER_PATTERN = re.compile(r"\bdocumented\s+(?=[A-Za-z])", re.IGNORECASE)
INTERNAL_SECTION_NAMES = frozenset(
    {
        "missing documentation",
        "missing or conflicting documentation",
        "reasonable interpretation",
        "sources",
    }
)
PRESENTATION_ONLY_HEADINGS = frozenset(
    {
        "answer",
        "facts stated by the documentation",
        "facts stated in the documentation",
    }
)
INTERNAL_INSUFFICIENT_EVIDENCE_MESSAGE = (
    "I could not find sufficient information in the currently indexed "
    "platform documentation to answer this reliably."
)
PUBLIC_INSUFFICIENT_EVIDENCE_MESSAGE = "I don't have enough information to answer that reliably."


def format_public_answer(answer: str) -> str:
    """Remove internal grounding metadata from an end-user answer."""
    answer = answer.replace(
        INTERNAL_INSUFFICIENT_EVIDENCE_MESSAGE,
        PUBLIC_INSUFFICIENT_EVIDENCE_MESSAGE,
    )

    if PUBLIC_INSUFFICIENT_EVIDENCE_MESSAGE.casefold() in answer.casefold():
        return PUBLIC_INSUFFICIENT_EVIDENCE_MESSAGE

    visible_lines: list[str] = []
    skip_section = False

    for line in answer.splitlines():
        heading = _normalized_heading(line)
        if heading in INTERNAL_SECTION_NAMES or _starts_internal_section(line):
            skip_section = True
            continue

        if _is_markdown_heading(line):
            skip_section = False
            if heading in PRESENTATION_ONLY_HEADINGS:
                continue

        if skip_section:
            continue

        public_line = CITATION_PATTERN.sub("", line)
        public_line = SOURCE_ATTRIBUTION_PATTERN.sub("", public_line)
        public_line = DOCUMENTED_AS_PATTERN.sub(r"\1", public_line)
        public_line = DOCUMENTED_QUALIFIER_PATTERN.sub("", public_line)
        visible_lines.append(public_line.rstrip())

    return "\n".join(visible_lines).strip()


def format_change_impact_analysis(answer: str) -> str:
    """Keep impact and gap sections while returning source locations separately."""
    answer = answer.replace(
        INTERNAL_INSUFFICIENT_EVIDENCE_MESSAGE,
        PUBLIC_INSUFFICIENT_EVIDENCE_MESSAGE,
    )
    if PUBLIC_INSUFFICIENT_EVIDENCE_MESSAGE.casefold() in answer.casefold():
        return PUBLIC_INSUFFICIENT_EVIDENCE_MESSAGE

    visible_lines: list[str] = []
    skip_sources = False
    for line in answer.splitlines():
        heading = _normalized_heading(line)
        if heading == "sources":
            skip_sources = True
            continue
        if _is_markdown_heading(line):
            skip_sources = False
        if not skip_sources:
            visible_lines.append(line.rstrip())
    return "\n".join(visible_lines).strip()


def _normalized_heading(line: str) -> str:
    return line.strip().lstrip("#").strip().strip("*_").removesuffix(":").strip().casefold()


def _is_markdown_heading(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("#") or (
        len(stripped) >= 4
        and (
            (stripped.startswith("**") and stripped.endswith("**"))
            or (stripped.startswith("__") and stripped.endswith("__"))
        )
    )


def _starts_internal_section(line: str) -> bool:
    normalized = line.strip().lstrip("#*_ ").casefold()
    return any(normalized.startswith(f"{section}:") for section in INTERNAL_SECTION_NAMES)
