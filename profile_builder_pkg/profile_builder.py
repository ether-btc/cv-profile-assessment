"""Profile builder — assembles parsed CV data into a valid PersonalProfile.

Phase 5: Adds language detection and routes entities to the right NER model
(en_core_web_sm or de_core_news_sm) based on detected language.
"""

import re
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
    check_ats_parse_safety,
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

    # Step 4b: ATS parse-safety of the source document.
    # Job-independent, so it is computed once here at parse time rather than
    # per job in the matcher. Only PDFs get the geometry checks.
    ats = check_ats_parse_safety(
        raw_text=text,
        sections=sections,
        pdf_path=cv_path if suffix == ".pdf" else None,
    )

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
            "ats_parse_safety": {
                "score": ats["score"],
                "checks": ats["checks"],
                "tips": ats["tips"],
            },
            "confidence_scores": {
                "skills_extraction": _skills_confidence(skills, sections),
                "esco_mapping": _esco_mapping_confidence(skills),
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


def _esco_mapping_confidence(skills: List[Dict]) -> float:
    """Score ESCO/taxonomy mapping confidence.

    Computes how much of the extracted skill set maps to our curated
    taxonomy (DEFAULT_SKILL_TAXONOMY). A higher ratio means more skills
    were matched to canonical categories, implying better structured output.

    Phase 2 should replace this with actual ESCO API lookup returning
    canonical skill IDs. For now, taxonomy coverage is a reasonable proxy.
    """
    if not skills:
        return 0.0
    from parser.skill_extractor import SKILL_TO_CATEGORY
    matched = sum(1 for s in skills if s.get("name", "").lower() in SKILL_TO_CATEGORY)
    return round(matched / len(skills), 2)


def _parse_experience(text: str) -> list:
    """Parse experience section into structured entries.

    Phase 2 (2026-09-02): Enhanced to handle:
    - German date ranges: "2024 – 2025", "2022 – 2023" (en/em-dash)
    - Pipe-separated tabular rows: |2010 – 2011||T-Mobile Austria,|...
    - Location lines following dates (e.g. "1100 Wien")
    - Company + role on same line with comma separator
    - Bullet-point summaries under each entry
    - Form-feed separated table rows (pdfminer emits \\x0c for page breaks)
    - Multi-page tabular experience sections

    Phase 1: simple line-based parsing (placeholder).
    """
    if not text:
        return []

    # Split on form-feed (page breaks) AND newlines, then flatten
    # This ensures table rows split across pages are still parsed
    text = text.replace("\x0c", "\n")
    entries = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    i = 0

    while i < len(lines):
        line = lines[i]

        # --- Tabellarische Zeilen (pipe-getrennt) ---
        # Format: |2010 – 2011||T-Mobile Austria,||Projektmitarbeit|
        if line.startswith("|"):
            entry = _parse_pipe_table_row(line)
            if entry:
                entries.append(entry)
                i += 1
                continue

        # --- Tabellarische Zeilen (form-feed getrennt, pdfminer) ---
        # Format: "2010 – 2011  T-Mobile Austria,  Projektmitarbeit"
        # These come from pipe-separated table rows where pdfminer
        # lost the pipe characters but kept the cell content as separate
        # lines (due to vertical positioning in the table).
        # We detect these by checking if a date-only line is followed by
        # a line that starts with a company name (no bullet, no @).
        date_only_match = re.match(
            r"^(\d{4})\s*[–—-]\s*(\d{4})$",
            line, re.IGNORECASE
        )
        if date_only_match:
            start_year = date_only_match.group(1)
            end_raw = date_only_match.group(2)
            entry = _parse_tabular_entry(lines, i, start_year, end_raw)
            if entry:
                # Consume the right number of lines
                i = entry.pop("_next_i", i + 1)
                entries.append(entry)
                continue

        # --- Datums-basierte Einträge (line-based) ---
        # Format: "2024 – 2025" followed optionally by "1100 Wien"
        date_match = re.match(
            r"^(\d{4})\s*[–—-]\s*(\d{4}|\b(?:Present|derzeit|aktuell)\b)",
            line, re.IGNORECASE
        )
        if date_match:
            start_year = date_match.group(1)
            end_raw = date_match.group(2)
            end_year = "Present" if end_raw.lower() in ("present", "derzeit", "aktuell") else end_raw

            i += 1
            # Next line might be a location (4-digit postal + city)
            location = ""
            if i < len(lines):
                loc_match = re.match(r"^\d{3,4}\s+.+", lines[i])
                if loc_match:
                    location = lines[i]
                    i += 1

            # Next line: company + role or just company
            company = ""
            position = ""
            if i < len(lines):
                candidate = lines[i]
                # "Company, Role" or "Company @ Role" or just "Company"
                if "," in candidate and not candidate.startswith("•"):
                    parts = candidate.split(",", 1)
                    company = parts[0].strip()
                    position = parts[1].strip()
                elif "@" in candidate:
                    parts = candidate.split("@", 1)
                    company = parts[1].strip()
                    position = parts[0].strip()
                else:
                    company = candidate
                i += 1

            # Collect bullet points until next date or end
            bullets = []
            while i < len(lines):
                next_line = lines[i]
                if next_line.startswith("|"):
                    break
                if re.match(r"^\d{4}\s*[–—-]", next_line):
                    break
                if next_line.startswith("BERUFSSCHULUNG") or next_line.startswith("AUSBILDUNG") or next_line.startswith("WEITERBILDUNG"):
                    break
                bullets.append(next_line)
                i += 1

            entries.append({
                "position": position or company,
                "company": company,
                "startDate": f"{start_year}-01-01",
                "endDate": end_year,
                "location": location,
                "summary": "\n".join(bullets),
                "skills_used": [],
            })
            continue

        # Fallback: line-based parsing (Phase 1)
        if "@" in line:
            parts = line.split("@", 1)
            position = parts[0].strip()
            company = parts[1].strip()
            bullets = []
            i += 1
            while i < len(lines):
                next_line = lines[i]
                if "@" in next_line or re.match(r"^\d{4}", next_line):
                    break
                bullets.append(next_line)
                i += 1
            entries.append({
                "position": position,
                "company": company,
                "summary": "\n".join(bullets),
                "skills_used": [],
            })
        else:
            i += 1

    return entries


def _parse_tabular_entry(lines: list, start_i: int, start_year: str, end_year: str) -> dict | None:
    """Parse a tabular experience entry from a multi-line date/company/role sequence.

    This handles the pattern in FlowCV tabular CVs where each experience
    is encoded as separate lines:
        2010 – 2011
        1020 Wien
        T-Mobile Austria, Projektmitarbeit
        •Liaison für Channel Management...

    Unlike the pipe-table parser, these lines lost their pipe delimiters
    during PDF text extraction but are still positionally separated.

    Also handles transposed layouts where pdfminer emits columns separately
    (dates first, then locations, then companies):
        2024 – 2025
        2023 – 2024
        1100 Wien
        1140 Wien
        ipcenter.at GmbH, Outplacement
    """
    i = start_i + 1

    # Skip any lines that are just dates — they belong to other entries
    # (transposed column layout: all dates come first, then locations)
    skipped_dates = []
    while i < len(lines):
        if re.match(r"^\d{4}\s*[–—-]\s*\d{4}$", lines[i], re.IGNORECASE):
            skipped_dates.append(lines[i])
            i += 1
        else:
            break

    location = ""
    company = ""
    position = ""
    bullets = []

    # Optional: location line (4-digit postal + city)
    if i < len(lines):
        loc_match = re.match(r"^\d{3,4}\s+.+", lines[i])
        if loc_match:
            location = lines[i]
            i += 1

    # Optional: company/role line
    if i < len(lines):
        candidate = lines[i]
        if "," in candidate and not candidate.startswith("•"):
            parts = candidate.split(",", 1)
            company = parts[0].strip()
            position = parts[1].strip()
        elif "@" in candidate:
            parts = candidate.split("@", 1)
            company = parts[1].strip()
            position = parts[0].strip()
        elif not re.match(r"^\d{4}\s*[–—-]", candidate):
            # Not a date — treat as company line
            company = candidate
            i += 1

    # Collect bullet points until next date or end
    while i < len(lines):
        next_line = lines[i]
        if re.match(r"^\d{4}\s*[–—-]", next_line):
            break
        if next_line.startswith("BERUFSSCHULUNG") or next_line.startswith("AUSBILDUNG") or next_line.startswith("WEITERBILDUNG"):
            break
        # Skip location-only lines that follow a company (transposed layout)
        if re.match(r"^\d{3,4}\s+.+", next_line):
            i += 1
            continue
        bullets.append(next_line)
        i += 1

    end_year_norm = "Present" if end_year.lower() in ("present", "derzeit", "aktuell") else end_year

    return {
        "position": position or company,
        "company": company,
        "startDate": f"{start_year}-01-01",
        "endDate": end_year_norm,
        "location": location,
        "summary": "\n".join(bullets),
        "skills_used": [],
        "_next_i": i,
    }


def _parse_pipe_table_row(line: str) -> dict | None:
    """Parse a pipe-separated table row into an experience entry.

    Format: |2010 – 2011||T-Mobile Austria,||Projektmitarbeit|

    Cells are separated by |. Empty cells || indicate missing data.
    """
    cells = [c.strip() for c in line.split("|") if c.strip()]
    if len(cells) < 2:
        return None

    entry = {
        "position": "",
        "company": "",
        "startDate": "",
        "endDate": "",
        "location": "",
        "summary": "",
        "skills_used": [],
    }

    # Cell 0: typically a date range
    date_cell = cells[0]
    date_match = re.match(r"^(\d{4})\s*[–—-]\s*(\d{4}|\w+)$", date_cell, re.IGNORECASE)
    if date_match:
        entry["startDate"] = f"{date_match.group(1)}-01-01"
        end_raw = date_match.group(2)
        entry["endDate"] = "Present" if end_raw.lower() in ("present", "derzeit", "aktuell", "") else end_raw
        for cell in cells[1:]:
            lower = cell.lower()
            if not entry["company"] and not re.match(r"^\d{4}\s*[–—-]", cell):
                # First non-date cell is likely company or position
                if "," in cell:
                    parts = cell.split(",", 1)
                    entry["company"] = parts[0].strip()
                    entry["position"] = parts[1].strip() if not entry["position"] else entry["position"]
                elif "@" in cell:
                    parts = cell.split("@", 1)
                    entry["position"] = parts[0].strip()
                    entry["company"] = parts[1].strip()
                else:
                    # If we already have a company, this is the position
                    if entry["company"]:
                        entry["position"] = cell
                    else:
                        entry["company"] = cell

    return entry if entry["company"] or entry["position"] else None
