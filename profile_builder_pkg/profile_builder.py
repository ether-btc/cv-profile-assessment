"""Profile builder — assembles parsed CV data into a valid PersonalProfile.

Phase 5: Adds language detection and routes entities to the right NER model
(en_core_web_sm or de_core_news_sm) based on detected language.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
from cv_profile_assessment import detect_language, log_processing_run


def build_profile_from_cv(cv_path: str, log: bool = True) -> Dict:
    """Build a PersonalProfile dict from a CV file (PDF or DOCX).

    Args:
        cv_path: Absolute path to CV file (.pdf or .docx).
        log: If True (default), append a usage-history record after building.

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

    # Step 1b: Detect language (default "en" if unknown)
    language, _confidence = detect_language(text)
    if language == "unknown":
        language = "en"

    # Step 2: Segment sections (language-agnostic — patterns cover both)
    sections = segment_sections(text)

    # Step 3: Extract entities (routes to DE or EN NER based on detected language)
    entities = extract_entities(sections, language=language)

    # Step 4: Extract skills
    skills = extract_skills(text, sections)

    # Step 5: Build profile dict
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    profile = {
        "basics": {
            "name": entities.get("name") or "Unknown",
            "email": entities.get("email") or "",
            "phone": entities.get("phone") or "",
            "location": entities.get("location") or {},
            "summary": sections.get("summary", ""),
            "languages": entities.get("languages", []),
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
            "language": language,
            "confidence_scores": {
                "skills_extraction": _skills_confidence(skills, sections),
                "esco_mapping": 0.0,
            },
        },
    }

    # Step 6: Append usage history (Phase 5)
    if log:
        warnings = []
        # Warn if section segmentation collapsed everything into 'header'
        if list(sections.keys()) == ["header"]:
            warnings.append(
                "Section segmentation collapsed: no recognized section headers detected. "
                "Text was treated as a single 'header' bucket — downstream parsing "
                "(experience entries, education, skills) is degraded."
            )
        # Warn if language couldn't be detected
        if language == "en" and not any(c in text for c in "äöüÄÖÜß"):
            pass  # Likely genuinely English
        elif language == "en" and any(c in text for c in "äöüÄÖÜß"):
            warnings.append(
                "German characters detected but language classifier returned 'en'. "
                "Section patterns used EN vocabulary, may miss German headers."
            )
        log_processing_run(
            source_path=cv_path,
            profile=profile,
            language=language,
            warnings=warnings,
        )

    return profile


def _skills_confidence(skills: List[Dict], sections: Dict[str, str]) -> float:
    """Score skill extraction confidence.

    Higher when a dedicated Skills section was found and parsed;
    lower when skills come from full-text keyword matching alone.
    """
    if not skills:
        return 0.0
    if "skills" in sections:
        # Dedicated skills section found — high confidence
        return 0.9
    if skills and not sections.get("skills"):
        # Skills extracted from full text only — medium confidence
        return 0.6
    return 0.7


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
            "summary": "\n".join(lines[1:]) if len(lines) > 1 else "",
            "skills_used": [],
        })

    return result
