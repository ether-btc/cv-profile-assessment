"""Section segmentation for CV/resume text.

Identifies common CV sections (Contact, Summary, Experience, Education, Skills, etc.)
using regex-based heading detection.
"""

import re
from typing import Dict, List


# Common section headings (case-insensitive)
SECTION_PATTERNS = {
    "contact": r"^(contact\s+info|contact|personal\s+info|personal\s+details)",
    "summary": r"^(summary|profile|objective|about\s+me|professional\s+summary)",
    "experience": r"^(experience|work\s+experience|employment|professional\s+experience|career\s+history)",
    "education": r"^(education|academic|qualifications)",
    "skills": r"^(skills|technical\s+skills|core\s+competencies|expertise)",
    "projects": r"^(projects|key\s+projects|notable\s+projects)",
    "certifications": r"^(certifications|certificates|licenses|accreditations)",
    "languages": r"^(languages|language\s+proficiency)",
    "interests": r"^(interests|hobbies|activities)",
    "publications": r"^(publications|papers|research)",
    "awards": r"^(awards|honors|achievements|recognition)",
    "references": r"^(references)",
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
        name: "\n".join(lines).strip()
        for name, lines in sections.items()
        if lines
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

    # Check each pattern
    for section_name, pattern in SECTION_PATTERNS.items():
        if re.match(pattern, line_lower):
            return section_name

    # Also detect ALL CAPS short lines (common CV heading style)
    if line.isupper() and 2 <= len(line.split()) <= 4:
        for section_name, pattern in SECTION_PATTERNS.items():
            if re.match(pattern, line_lower):
                return section_name

    return None


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python section_segmenter.py <text_file>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        text = f.read()
    sections = segment_sections(text)
    for name, content in sections.items():
        print(f"\n{'=' * 60}")
        print(f"SECTION: {name.upper()} ({len(content)} chars)")
        print('=' * 60)
        print(content[:300] + ("..." if len(content) > 300 else ""))