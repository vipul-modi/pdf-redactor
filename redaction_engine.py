import fitz  # PyMuPDF


class RedactionEngine:
    """Applies permanent black-box redactions to PDF documents."""

    def __init__(self, doc: fitz.Document):
        self.doc = doc

    def apply_redactions(self, page_redactions: dict[int, list[tuple[float, float, float, float]]]) -> None:
        """Apply black-box redactions to specified pages.

        Args:
            page_redactions: dict mapping page index to list of rects (x0, y0, x1, y1)
                             in PDF coordinate space.
        """
        for page_idx, rects in page_redactions.items():
            if page_idx < 0 or page_idx >= len(self.doc):
                continue
            page = self.doc[page_idx]
            for rect in rects:
                pdf_rect = fitz.Rect(rect)
                page.add_redact_annot(pdf_rect, fill=(0, 0, 0))
            page.apply_redactions()

    def save(self, output_path: str) -> None:
        """Save the redacted document."""
        self.doc.save(output_path, garbage=4, deflate=True)
