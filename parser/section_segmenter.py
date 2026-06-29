"""Section segmentation for CV/resume text.

Identifies common CV sections (Contact, Summary, Experience, Education, Skills, etc.)
using regex-based heading detection.

Supports English and German CV layouts (FlowCV, DIN-style, Europass, traditional).
"""

import re
from typing import Dict, List


# Section heading patterns: English | German | generic
SECTION_PATTERNS = {
    "contact": r"^(contact\s+info|contact|personal\s+info|personal\s+details|kontakt|kontaktdaten|persönliche\s+daten)",
    "summary": r"^(summary|profile|objective|about\s+me|professional\s+summary|profil|persönliches\s+profil|zusammenfassung|über\s+mich)",
    "experience": r"^(experience|work\s+experience|employment|professional\s+experience|career\s+history|berufserfahrung|beruflicher\s+werdegang|berufliche\s+laufbahn|tätigkeit|berufstätigkeit|erfahrung)",
    "education": r"^(education|academic|qualifications|ausbildung|schulbildung|studium|bildungsweg|akademische|abschlüsse)",
    "skills": r"^(skills|technical\s+skills|core\s+competencies|expertise|soft\s+skills|kenntnisse|fähigkeiten|kompetenzen|fertigkeiten|qualifikationen|itk|it-kenntnisse|sap-kenntnisse|sonstige\s+kenntnisse)",
    "projects": r"^(projects|key\s+projects|notable\s+projects|projekte|projektarbeit|referenzprojekte)",
    "certifications": r"^(certifications|certificates|licenses|accreditations|zertifikate|zertifizierungen|weiterbildung|abschlüsse|schulungen)",
    "languages": r"^(languages|language\s+proficiency|sprachen|sprachkenntnisse)",
    "interests": r"^(interests|hobbies|activities|interessen|hobbys)",
    "publications": r"^(publications|papers|research|publikationen|veröffentlichungen)",
    "awards": r"^(awards|honors|achievements|recognition|auszeichnungen|preise)",
    "references": r"^(references|empfehlungen|referenzen)",
}


def segment_sections(text: str) -> Dict[str, str]:
    """Segment resume text into sections.

    Uses regex to detect section headings and groups lines under each section.
    Lines before the first recognized heading are placed in a "header" section.

    Args:
        text: Full resume text.

    Returns:
        Dict mapping section name to its content text.
    """
    if not text or not text.strip():
        return {}

    lines = text.split("\n")
    sections: Dict[str, List[str]] = {"header": []}
    current_section = "header"

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Check if line is a section heading
        detected = _detect_section(line_stripped)
        if detected:
            current_section = detected
            if current_section not in sections:
                sections[current_section] = []
        else:
            sections[current_section].append(line_stripped)

    # Join lines into strings, drop empty sections
    return {
        name: "\n".join(section_lines).strip()
        for name, section_lines in sections.items()
        if section_lines
    }


def _detect_section(line: str) -> str | None:
    """Detect if a line is a section heading.

    Args:
        line: A single line from the resume.

    Returns:
        Section name if detected, None otherwise.
    """
    line_lower = line.lower().strip()

    # Skip very long lines (unlikely to be headings)
    if len(line_lower) > 60:
        return None

    # Strip trailing punctuation/colons (common in heading style)
    cleaned = re.sub(r"[:;,.\s]+$", "", line_lower)
    if not cleaned:
        return None

    # Check each pattern
    for section_name, pattern in SECTION_PATTERNS.items():
        if re.match(pattern, cleaned):
            return section_name

    return None
