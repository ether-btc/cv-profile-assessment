"""Profile builder — assembles parsed CV data into a valid PersonalProfile."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

# Add project root to path so we can import parser package
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser import (
    extract_text_from_pdf,
    extract_text_from_docx,
    segment_sections,
    extract_entities,
    extract_skills,
)


def build_profile_from_cv(cv_path: str) -> Dict:
    """Build a PersonalProfile dict from a CV file (PDF or DOCX).

    Args:
        cv_path: Absolute path to CV file (.pdf or .docx).

    Returns:
        Dict matching PersonalProfile JSON Schema.

    Raises:
        ValueError: If file format is unsupported.
        FileNotFoundError: If CV does not exist.
    """
    cv_path_obj = Path(cv_path)
    if not cv_path_obj.exists():
        raise FileNotFoundError(f"CV not found: {cv_path}")

    # Step 1: Extract text
    suffix = cv_path_obj.suffix.lower()
    if suffix == ".pdf":
        text = extract_text_from_pdf(cv_path)
    elif suffix in (".docx", ".doc"):
        text = extract_text_from_docx(cv_path)
    elif suffix == ".txt":
        text = cv_path_obj.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Use .pdf, .docx, or .txt")

    # Step 2: Segment sections
    sections = segment_sections(text)

    # Step 3: Extract entities
    entities = extract_entities(sections)

    # Step 4: Extract skills
    skills = extract_skills(text, sections)

    # Step 5: Build profile dict
    now = datetime.utcnow().isoformat() + "Z"
    profile = {
        "basics": {
            "name": entities.get("name") or "Unknown",
            "email": entities.get("email") or "",
            "phone": entities.get("phone") or "",
            "location": entities.get("location") or {},
            "summary": sections.get("summary", ""),
            "languages": [],
        },
        "skills": skills,
        "experience": _parse_experience(sections.get("experience", "")),
        "education": [],
        "projects": [],
        "certifications": [],
        "preferences": {
            "location_preference": {},
            "salary_expectations": {},
            "role_preferences": {},
            "deal_breakers": [],
        },
        "metadata": {
            "version": "1.0",
            "last_updated": now,
            "source": cv_path,
            "confidence_scores": {
                "skills_extraction": 0.7,
                "esco_mapping": 0.0,
            },
        },
    }

    return profile


def _parse_experience(text: str) -> list:
    """Parse experience section into structured entries.

    Phase 1: simple line-based parsing (placeholder).
    Phase 2: NLP-based parsing with date extraction.
    """
    if not text:
        return []

    entries = [e.strip() for e in text.split("\n\n") if e.strip()]

    result = []
    for entry in entries:
        lines = [l.strip() for l in entry.split("\n") if l.strip()]
        if not lines:
            continue

        first_line = lines[0]
        if "@" in first_line:
            position, company = first_line.split("@", 1)
            position = position.strip()
            company = company.strip()
        else:
            position = first_line
            company = ""

        result.append({
            "position": position,
            "company": company,
            "startDate": "2020-01-01",  # Placeholder; Phase 2: date extraction
            "summary": "\n".join(lines[1:]) if len(lines) > 1 else "",
            "skills_used": [],
        })

    return result


if __name__ == "__main__":
    import json
    if len(sys.argv) != 2:
        print("Usage: python profile_builder.py <cv_path>")
        sys.exit(1)

    profile = build_profile_from_cv(sys.argv[1])
    print(json.dumps(profile, indent=2))