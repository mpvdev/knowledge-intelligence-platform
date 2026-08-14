from dataclasses import dataclass

import pymupdf

from knowledge_intelligence.domain.visual_documents import (
    EmbeddedImageInfo,
    VisualPageClassification,
    VisualPageInspection,
)
from knowledge_intelligence.visual.exceptions import (
    PDFPageInspectionError,
)


@dataclass(frozen=True)
class VisualPageDetectorConfig:
    minimum_text_characters: int = 150
    minimum_image_area_ratio: float = 0.15

    def __post_init__(self) -> None:
        if self.minimum_text_characters < 0:
            raise ValueError("minimum_text_characters cannot be negative.")

        if not 0.0 <= self.minimum_image_area_ratio <= 1.0:
            raise ValueError("minimum_image_area_ratio must be between 0 and 1.")


class VisualPageDetector:
    """Identify PDF pages that are likely to contain meaningful visuals."""

    def __init__(
        self,
        config: VisualPageDetectorConfig,
    ) -> None:
        self._config = config

    def inspect_document(
        self,
        pdf_bytes: bytes,
    ) -> tuple[VisualPageInspection, ...]:
        try:
            document = pymupdf.open(  # type: ignore[no-untyped-call]
                stream=pdf_bytes,
                filetype="pdf",
            )
        except Exception as exc:
            raise PDFPageInspectionError("Unable to open PDF for visual inspection.") from exc

        try:
            return tuple(
                self._inspect_page(
                    document=document,
                    page_index=page_index,
                )
                for page_index in range(document.page_count)
            )
        finally:
            document.close()  # type: ignore[no-untyped-call]

    def _inspect_page(
        self,
        *,
        document: pymupdf.Document,
        page_index: int,
    ) -> VisualPageInspection:
        try:
            page = document.load_page(page_index)  # type: ignore[no-untyped-call]

            extracted_text = page.get_text("text") or ""
            text_character_count = len(extracted_text.strip())

            image_infos = self._inspect_images(
                document=document,
                page=page,
            )

            largest_image_area_ratio = max(
                (image.area_ratio for image in image_infos),
                default=0.0,
            )

            classification, reasons = self._classify(
                text_character_count=text_character_count,
                image_count=len(image_infos),
                largest_image_area_ratio=largest_image_area_ratio,
            )

            return VisualPageInspection(
                page_number=page_index + 1,
                text_character_count=text_character_count,
                embedded_image_count=len(image_infos),
                largest_image_area_ratio=largest_image_area_ratio,
                classification=classification,
                reasons=reasons,
            )

        except Exception as exc:
            raise PDFPageInspectionError(f"Unable to inspect PDF page {page_index + 1}.") from exc

    def _inspect_images(
        self,
        *,
        document: pymupdf.Document,
        page: pymupdf.Page,
    ) -> tuple[EmbeddedImageInfo, ...]:
        page_area = max(page.rect.width * page.rect.height, 1.0)

        images: list[EmbeddedImageInfo] = []
        seen_xrefs: set[int] = set()

        for image_entry in page.get_images(full=True):  # type: ignore[no-untyped-call]
            xref = int(image_entry[0])

            if xref in seen_xrefs:
                continue

            seen_xrefs.add(xref)

            image_metadata = document.extract_image(xref)  # type: ignore[no-untyped-call]

            width = int(image_metadata.get("width", 0))
            height = int(image_metadata.get("height", 0))

            placement_area = max(
                (self._visible_area(rect=rect, page=page) for rect in page.get_image_rects(xref)),
                default=0.0,
            )
            area_ratio = min(placement_area / page_area, 1.0)

            images.append(
                EmbeddedImageInfo(
                    xref=xref,
                    width=width,
                    height=height,
                    area_ratio=area_ratio,
                )
            )

        return tuple(images)

    @staticmethod
    def _visible_area(*, rect: pymupdf.Rect, page: pymupdf.Page) -> float:
        """Return an image placement's visible area in PDF page units."""
        left = max(rect.x0, page.rect.x0)
        top = max(rect.y0, page.rect.y0)
        right = min(rect.x1, page.rect.x1)
        bottom = min(rect.y1, page.rect.y1)
        return float(max(right - left, 0.0) * max(bottom - top, 0.0))

    def _classify(
        self,
        *,
        text_character_count: int,
        image_count: int,
        largest_image_area_ratio: float,
    ) -> tuple[VisualPageClassification, tuple[str, ...]]:
        reasons: list[str] = []

        low_text = text_character_count < self._config.minimum_text_characters

        meaningful_image = (
            image_count > 0 and largest_image_area_ratio >= self._config.minimum_image_area_ratio
        )

        if low_text:
            reasons.append("Page contains less than the configured amount of text.")

        if meaningful_image:
            reasons.append("Page contains an image above the configured size threshold.")

        if low_text and image_count > 0:
            reasons.append("Page may be scanned or primarily image-based.")

        if meaningful_image or (low_text and image_count > 0):
            return (
                VisualPageClassification.VISUAL_CANDIDATE,
                tuple(reasons),
            )

        if image_count > 0:
            return (
                VisualPageClassification.MIXED_CONTENT,
                ("Page contains images, but none exceeded the visual-analysis threshold.",),
            )

        return (
            VisualPageClassification.TEXT_ONLY,
            (),
        )
