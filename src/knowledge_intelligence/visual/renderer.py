from dataclasses import dataclass

import pymupdf

from knowledge_intelligence.domain.visual_documents import (
    RenderedPDFPage,
)
from knowledge_intelligence.visual.exceptions import (
    PDFPageRenderingError,
)


@dataclass(frozen=True)
class PDFPageRendererConfig:
    dpi: int = 144

    def __post_init__(self) -> None:
        if not 72 <= self.dpi <= 300:
            raise ValueError("dpi must be between 72 and 300.")


class PDFPageRenderer:
    """Render selected PDF pages to PNG for later vision analysis."""

    def __init__(
        self,
        config: PDFPageRendererConfig,
    ) -> None:
        self._config = config

    def render_page(
        self,
        *,
        pdf_bytes: bytes,
        page_number: int,
    ) -> RenderedPDFPage:
        return self.render_pages(pdf_bytes=pdf_bytes, page_numbers=(page_number,))[0]

    def render_pages(
        self,
        *,
        pdf_bytes: bytes,
        page_numbers: tuple[int, ...],
    ) -> tuple[RenderedPDFPage, ...]:
        """Render selected pages while opening the PDF only once."""
        if any(page_number < 1 for page_number in page_numbers):
            raise ValueError("page numbers must be greater than or equal to 1.")

        if not page_numbers:
            return ()

        try:
            document = pymupdf.open(  # type: ignore[no-untyped-call]
                stream=pdf_bytes,
                filetype="pdf",
            )
        except Exception as exc:
            raise PDFPageRenderingError("Unable to open PDF for page rendering.") from exc

        try:
            missing_page = next(
                (page_number for page_number in page_numbers if page_number > document.page_count),
                None,
            )
            if missing_page is not None:
                page_label = "page" if document.page_count == 1 else "pages"
                raise ValueError(
                    f"Page {missing_page} does not exist. "
                    f"PDF contains {document.page_count} {page_label}."
                )

            return tuple(
                self._render_open_document_page(document=document, page_number=page_number)
                for page_number in page_numbers
            )

        except ValueError:
            raise
        except Exception as exc:
            raise PDFPageRenderingError("Unable to render the selected PDF pages.") from exc
        finally:
            document.close()  # type: ignore[no-untyped-call]

    def _render_open_document_page(
        self,
        *,
        document: pymupdf.Document,
        page_number: int,
    ) -> RenderedPDFPage:
        page = document.load_page(page_number - 1)  # type: ignore[no-untyped-call]
        pixmap = page.get_pixmap(dpi=self._config.dpi, alpha=False)
        return RenderedPDFPage(
            page_number=page_number,
            image_bytes=pixmap.tobytes("png"),
            width=pixmap.width,
            height=pixmap.height,
            dpi=self._config.dpi,
        )
