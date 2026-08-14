VISUAL_ANALYSIS_SYSTEM_PROMPT = """
You analyse rendered pages from approved internal platform documentation.

Analyse only what is visibly present on the supplied page.

Mandatory rules:

1. Do not invent components, labels, arrows, relationships, accounts, roles,
   services, repositories or workflows.

2. A relationship may be returned only when supported by:
   - a visible arrow;
   - a visible connecting line;
   - an explicit textual statement;
   - clear diagram containment.

3. Preserve visible technical names exactly where possible.

4. Do not infer that a component belongs to TME merely because it appears on
   the page.

5. Do not treat implied organisational ownership as visible evidence.

6. Put uncertain interpretations in the uncertainties field.

7. If the page contains only decorative images, logos or formatting, set
   contains_meaningful_visual_content to false.

8. Keep summaries concise and technically precise.

9. Do not provide remediation advice or external knowledge.

10. Return only the requested structured output.
""".strip()


def build_visual_page_prompt(
    *,
    document_title: str,
    page_number: int,
    extracted_text: str | None,
) -> str:
    context_text = (
        extracted_text.strip()
        if extracted_text and extracted_text.strip()
        else "No reliable deterministic text was extracted from this page."
    )

    return f"""
Analyse page {page_number} of the document "{document_title}".

Deterministically extracted page text, which may be incomplete or have an
incorrect reading order:

--- BEGIN EXTRACTED TEXT ---
{context_text[:8_000]}
--- END EXTRACTED TEXT ---

Identify:

- the visual content type;
- all clearly visible component names;
- visible connections, arrows and relationship labels;
- visible text important to understanding the page;
- tables and their contents where legible;
- important observations;
- any uncertainty or ambiguity.

Do not infer relationships that are not visible.
""".strip()
