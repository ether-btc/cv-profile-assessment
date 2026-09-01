"""PDF → image rendering for visual verification.

The reference project (adrianhajdin/ai-resume-analyzer) renders the first
PDF page to a PNG so the user can see a thumbnail alongside the text-based
analysis. Our parser only does *text* extraction (pdfminer.six), which
silently degrades on image-based / multi-column / scanned CVs.

This module adds an optional visual pass using PyMuPDF (fitz), which is
already a transitive dependency and needs no external `poppler` binary —
ideal for the Raspberry Pi 5 target. It is **optional**: import is lazy and
the function degrades to a clear error if fitz is missing, so the core
parser never hard-depends on it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional


def render_first_page(
    pdf_path: str | Path,
    output_path: str | Path | None = None,
    *,
    scale: float = 2.0,
    fmt: str = "png",
) -> Dict:
    """Render the first page of a PDF to an image.

    Args:
        pdf_path: Path to the source PDF.
        output_path: Destination image path. If None, a sibling
            ``<stem>-page1.png`` next to the PDF is written.
        scale: Render zoom factor (2.0 ≈ 144 DPI). Reference repo used 4.0;
            2.0 is a good Pi-friendly default; bump for print-quality.
        fmt: Image format passed to PyMuPDF (``png`` or ``jpeg``).

    Returns:
        Result dict:
            {
              "image_path": str | None,   # absolute path if rendered
              "page_count": int,          # total pages in the PDF
              "error": str | None,        # set on failure
            }

    Raises:
        FileNotFoundError: if pdf_path does not exist (caller-facing).
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if output_path is None:
        output_path = pdf_path.with_name(f"{pdf_path.stem}-page1.{fmt}")
    output_path = Path(output_path)

    try:
        import fitz  # PyMuPDF — lazy import; optional dependency.
    except ImportError:
        return {
            "image_path": None,
            "page_count": 0,
            "error": "PyMuPDF (fitz) not installed; cannot render PDF to image. "
                     "Install with: pip install pymupdf",
        }

    try:
        doc = fitz.open(pdf_path)
        page_count = doc.page_count
        if page_count == 0:
            doc.close()
            return {"image_path": None, "page_count": 0, "error": "PDF has no pages"}

        page = doc[0]
        matrix = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(output_path), output=fmt.upper())
        doc.close()

        return {
            "image_path": str(output_path.resolve()),
            "page_count": page_count,
            "error": None,
        }
    except Exception as e:  # noqa: BLE001 — surface as result, never crash parser
        return {
            "image_path": None,
            "page_count": 0,
            "error": f"Failed to render PDF to image: {e}",
        }


__all__ = ["render_first_page"]
