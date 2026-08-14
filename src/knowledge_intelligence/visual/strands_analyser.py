from dataclasses import dataclass
from typing import cast

from pydantic import ValidationError
from strands import Agent
from strands.models.openai_responses import OpenAIResponsesModel
from strands.types.content import ContentBlock
from strands.types.media import ImageFormat

from knowledge_intelligence.domain.visual_analysis import (
    VisualAnalysisPayload,
    VisualPageAnalysis,
)
from knowledge_intelligence.domain.visual_documents import (
    RenderedPDFPage,
)
from knowledge_intelligence.visual.exceptions import (
    VisualAnalysisError,
    VisualAnalysisValidationError,
)
from knowledge_intelligence.visual.prompts import (
    VISUAL_ANALYSIS_SYSTEM_PROMPT,
    build_visual_page_prompt,
)


@dataclass(frozen=True)
class StrandsVisualAnalyserConfig:
    api_key: str
    model_id: str
    prompt_version: str
    maximum_image_bytes: int = 10_000_000

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("OpenAI API key cannot be empty.")

        if not self.model_id.strip():
            raise ValueError("Visual-analysis model ID cannot be empty.")

        if not self.prompt_version.strip():
            raise ValueError("Prompt version cannot be empty.")

        if self.maximum_image_bytes <= 0:
            raise ValueError("maximum_image_bytes must be greater than zero.")


class StrandsVisualPageAnalyser:
    """Analyse rendered PDF pages using Strands and OpenAI Responses."""

    def __init__(
        self,
        config: StrandsVisualAnalyserConfig,
    ) -> None:
        self._config = config

        model = OpenAIResponsesModel(
            model_id=config.model_id,
            client_args={
                "api_key": config.api_key,
            },
        )

        self._agent = Agent(
            model=model,
            system_prompt=VISUAL_ANALYSIS_SYSTEM_PROMPT,
            tools=[],
        )

    def analyse(
        self,
        *,
        document_key: str,
        document_title: str,
        page: RenderedPDFPage,
        extracted_text: str | None,
    ) -> VisualPageAnalysis:
        self._validate_page(page)

        prompt_text = build_visual_page_prompt(
            document_title=document_title,
            page_number=page.page_number,
            extracted_text=extracted_text,
        )

        image_format = cast(
            ImageFormat,
            "jpeg" if page.image_format.lower() == "jpg" else page.image_format.lower(),
        )
        multimodal_prompt: list[ContentBlock] = [
            {
                "text": prompt_text,
            },
            {
                "image": {
                    "format": image_format,
                    "source": {
                        "bytes": page.image_bytes,
                    },
                }
            },
        ]

        try:
            result = self._agent.structured_output(
                VisualAnalysisPayload,
                multimodal_prompt,
            )
        except ValidationError as exc:
            raise VisualAnalysisValidationError(
                f"Visual analysis returned invalid structured output for "
                f"{document_key!r}, page {page.page_number}."
            ) from exc
        except Exception as exc:
            raise VisualAnalysisError(
                f"Visual analysis failed for {document_key!r}, page {page.page_number}."
            ) from exc

        payload = self._extract_payload(result)

        return VisualPageAnalysis(
            document_key=document_key,
            document_title=document_title,
            page_number=page.page_number,
            analysis=payload,
            model_id=self._config.model_id,
            prompt_version=self._config.prompt_version,
        )

    def _validate_page(
        self,
        page: RenderedPDFPage,
    ) -> None:
        if page.image_format.lower() not in {"png", "jpeg", "jpg", "webp"}:
            raise ValueError(f"Unsupported rendered image format: {page.image_format!r}.")

        if len(page.image_bytes) > self._config.maximum_image_bytes:
            raise VisualAnalysisError(
                f"Rendered page {page.page_number} is "
                f"{len(page.image_bytes)} bytes, exceeding the configured "
                f"{self._config.maximum_image_bytes}-byte limit."
            )

    @staticmethod
    def _extract_payload(
        result: object,
    ) -> VisualAnalysisPayload:
        if isinstance(result, VisualAnalysisPayload):
            return result

        structured_output = getattr(
            result,
            "structured_output",
            None,
        )

        if isinstance(structured_output, VisualAnalysisPayload):
            return structured_output

        if isinstance(structured_output, dict):
            return VisualAnalysisPayload.model_validate(structured_output)

        if isinstance(result, dict):
            return VisualAnalysisPayload.model_validate(result)

        raise VisualAnalysisValidationError(
            "Strands did not return the expected structured visual output."
        )
