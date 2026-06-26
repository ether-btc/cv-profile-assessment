"""PDF text extraction using pdfminer.six"""

from pdfminer.high_level import extract_text as pdfminer_extract


def extract_text_from_pdf(file_path: str) -> str:
    """Extract plain text from a PDF file.

    Args:
        file_path: Absolute path to PDF file.

    Returns:
        Extracted text as a single string.

    Raises:
        FileNotFoundError: If the PDF does not exist.
        Exception: If pdfminer fails to parse.
    """
    try:
        text = pdfminer_extract(file_path)
        return text.strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"PDF not found: {file_path}")
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from {file_path}") from e


