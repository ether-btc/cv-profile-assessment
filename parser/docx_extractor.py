"""DOCX text extraction using python-docx"""

from docx import Document


def extract_text_from_docx(file_path: str) -> str:
    """Extract plain text from a DOCX file.

    Args:
        file_path: Absolute path to DOCX file.

    Returns:
        Extracted text as a single string with paragraphs separated by newlines.

    Raises:
        FileNotFoundError: If the DOCX does not exist.
        Exception: If python-docx fails to parse.
    """
    try:
        doc = Document(file_path)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n".join(paragraphs).strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"DOCX not found: {file_path}")
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from {file_path}") from e


