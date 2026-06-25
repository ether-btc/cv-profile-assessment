"""Entity extraction using spaCy NER + regex patterns.

Extracts:
- Name (from header section)
- Email
- Phone
- Location
- Job titles, companies, dates
"""

import re
from typing import Dict, List, Optional

import spacy

# Load spaCy model once at import
try:
    _NLP = spacy.load("en_core_web_sm")
except OSError:
    _NLP = None
    print("Warning: spaCy model 'en_core_web_sm' not loaded. NER disabled.")


# Regex patterns for contact info
EMAIL_PATTERN = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
PHONE_PATTERN = r"(\+?\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}"

# Date patterns (YYYY-MM-DD, MM/YYYY, Mon YYYY, etc.)
DATE_PATTERN = r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})"


def extract_email(text: str) -> Optional[str]:
    """Extract first email address found in text."""
    match = re.search(EMAIL_PATTERN, text)
    return match.group(0) if match else None


def extract_phone(text: str) -> Optional[str]:
    """Extract first phone number found in text."""
    match = re.search(PHONE_PATTERN, text)
    return match.group(0).strip() if match else None


def extract_name(text: str) -> Optional[str]:
    """Extract person name from text.

    Strategy:
    1. Look at first non-empty line(s) of header section
    2. Use spaCy NER to find PERSON entities
    3. Return first match
    """
    if not text or not _NLP:
        return None

    # Try first 3 lines (name is usually at top)
    lines = [l.strip() for l in text.split("\n") if l.strip()][:3]
    header_text = "\n".join(lines)

    doc = _NLP(header_text)
    for ent in doc.ents:
        if ent.label_ == "PERSON" and 2 <= len(ent.text.split()) <= 4:
            return ent.text.strip()

    # Fallback: assume first line is name if it looks like one
    if lines and 2 <= len(lines[0].split()) <= 4 and not re.search(EMAIL_PATTERN, lines[0]):
        return lines[0]

    return None


def extract_location(text: str) -> Optional[Dict[str, str]]:
    """Extract location (city, country) from text.

    Looks for GPE (Geopolitical Entity) entities in the header.
    """
    if not text or not _NLP:
        return None

    # Search in header
    lines = [l.strip() for l in text.split("\n") if l.strip()][:10]
    header_text = "\n".join(lines)

    doc = _NLP(header_text)
    locations = [ent.text for ent in doc.ents if ent.label_ == "GPE"]

    if locations:
        return {"city": locations[0], "country": locations[-1] if len(locations) > 1 else ""}

    return None


def extract_entities(sections: Dict[str, str]) -> Dict:
    """Extract structured entities from segmented sections.

    Args:
        sections: Dict from segment_sections() mapping section name to text.

    Returns:
        Dict with keys: name, email, phone, location
    """
    full_text = "\n".join(sections.values())
    header_text = sections.get("header", "")

    return {
        "name": extract_name(header_text) or extract_name(full_text),
        "email": extract_email(full_text),
        "phone": extract_phone(full_text),
        "location": extract_location(header_text) or extract_location(full_text),
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python entity_extractor.py <text_file>")
        sys.exit(1)
    from .section_segmenter import segment_sections

    with open(sys.argv[1]) as f:
        text = f.read()
    sections = segment_sections(text)
    entities = extract_entities(sections)

    import json
    print(json.dumps(entities, indent=2))