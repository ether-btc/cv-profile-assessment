"""CV/Resume Parser Package

Extracts structured data from PDF, DOCX, and TXT resumes.
"""

from .pdf_extractor import extract_text_from_pdf
from .docx_extractor import extract_text_from_docx
from .section_segmenter import segment_sections
from .entity_extractor import extract_entities
from .skill_extractor import extract_skills

__version__ = "0.1.0"
__all__ = [
    "extract_text_from_pdf",
    "extract_text_from_docx",
    "segment_sections",
    "extract_entities",
    "extract_skills",
]