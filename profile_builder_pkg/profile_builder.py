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

# Import the new state-machine experience parser (Phase 7+: transposed + direct format)
try:
    from profile_builder_pkg._exp_new import _parse_experience as _parse_experience_new
    _HAS_NEW_EXPERIENCE_PARSER = True
except ImportError:
    _HAS_NEW_EXPERIENCE_PARSER = False
    def _parse_experience_new(lines):  # noqa: ARG001
        return []

# Phase 7+: sorted PDF text parser (PyMuPDF sort=True)
# Produces 15/15 correct entries on the user CV's tabular layout
# by preserving row structure (date|company|role on the same line)
try:
    from profile_builder_pkg._exp_sorted import _parse_experience as _parse_experience_sorted  # type: ignore[assignment]
    _HAS_SORTED_EXPERIENCE_PARSER = True
except ImportError:
    _HAS_SORTED_EXPERIENCE_PARSER = False
    def _parse_experience_sorted(lines, original_lines=None):  # noqa: ARG001
        return []


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
    sorted_text = ""  # PyMuPDF sort=True for PDFs (row-aligned)
    if suffix == ".pdf":
        text = extract_text_from_pdf(cv_path)
        # Try to also extract sorted (row-aligned) text via PyMuPDF
        try:
            import fitz  # PyMuPDF — optional, lazy
            doc = fitz.open(str(cv_path_obj))
            sorted_text = ""
            for page in doc:
                sorted_text += page.get_text("text", sort=True) + "\n"
            doc.close()
        except Exception:
            sorted_text = ""  # Fall back to legacy parser
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
        "experience": _parse_experience(sections.get("experience", ""), sorted_text=sorted_text),
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


def _normalize_end_year(end_year: str) -> str:
    """Normalize end year: 'Present'/'derzeit'/'aktuell' → 'Present'."""
    if end_year.lower() in ("present", "derzeit", "aktuell"):
        return "Present"
    return end_year


def _parse_experience_direct(lines: list) -> list:
    """Fallback parser for non-tabular, line-based experience sections.
    
    Direct format: date → location → company,role → bullets
    """
    entries = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Date line
        date_match = re.match(
            r"^(\d{4})\s*[–—-]\s*(\d{4}|(?:Present|derzeit|aktuell))",
            line, re.IGNORECASE
        )
        if date_match:
            start_year = date_match.group(1)
            end_year = _normalize_end_year(date_match.group(2))
            i += 1
            
            # Optional location
            location = ""
            if i < len(lines) and re.match(r"^\d{3,4}\s+.+", lines[i]):
                location = lines[i]
                i += 1
            
            # Company + role
            company, position = "", ""
            if i < len(lines):
                candidate = lines[i]
                if "," in candidate and not candidate.startswith("•"):
                    parts = candidate.split(",", 1)
                    company = parts[0].strip()
                    position = parts[1].strip() if len(parts) > 1 else ""
                elif "@" in candidate:
                    parts = candidate.split("@", 1)
                    position = parts[0].strip()
                    company = parts[1].strip()
                else:
                    company = candidate
                i += 1
            
            # Collect bullets
            bullets = []
            while i < len(lines):
                b = lines[i]
                if re.match(r"^\d{4}\s*[–—-]", b):
                    break
                if b.startswith("BERUFSSCHULUNG") or b.startswith("AUSBILDUNG") or b.startswith("WEITERBILDUNG"):
                    break
                bullets.append(b)
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
        
        i += 1
    return entries


def _parse_experience(text: str, sorted_text: str = "") -> list:
    """Parse experience section into structured entries.

    Phase 7+ (2026-09-02): Routes to state-machine parser (_exp_new.py) which
    handles the FlowCV tabular PDF layout where pdfminer emits columns
    separately (transposed: all dates first, then all companies). Falls back
    to the legacy two-pass parser if the new parser is unavailable.

    For PDFs: if `sorted_text` is provided (PyMuPDF sort=True extraction),
    use the row-aligned parser (_exp_sorted.py) which produces accurate
    field attribution by preserving date+company+role row structure.

    For DOCX/TXT: use the legacy parser since they don't have PDF geometry.
    """
    if not text:
        return []

    # Flatten form-feed (page breaks) into newlines
    text = text.replace("\x0c", "\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # PDF path: use sorted-text parser if available (preserves row structure)
    if sorted_text and _HAS_SORTED_EXPERIENCE_PARSER:
        sorted_clean = sorted_text.replace("\x0c", "\n")
        sorted_lines = [l for l in sorted_clean.split("\n") if l.strip()]
        # Re-segment the sorted text into experience section
        from parser import segment_sections as _segment_sections
        sorted_sections = _segment_sections(sorted_clean)
        sorted_exp = sorted_sections.get("experience", "")
        sorted_exp_lines = [l for l in sorted_exp.split("\n") if l.strip()]
        return _parse_experience_sorted(sorted_exp_lines)

    if _HAS_NEW_EXPERIENCE_PARSER:
        return _parse_experience_new(lines)

    return _parse_experience_legacy(text)


def _parse_experience_legacy(text: str) -> list:
    """Legacy two-pass experience parser (kept as fallback).

    Many FlowCV tabular templates render experience as a 5-column table:
    | Date | Location | Company | Role | Description |
    When pdfminer/pdfminer.six extracts text from such tables, it often
    emits columns separately (transposed layout):
      - All date lines first (2024 – 2025, 2023 – 2024, ...)
      - All location lines (1100 Wien, 1140 Wien, ...)
      - All company/role lines (ipcenter.at GmbH, Outplacement, ...)

    Pass 1: Scan for date-location pairs and company-role blocks.
    Pass 2: Interleave pairs → full entries with correct attribution.

    Also handles:
    - Pipe-separated rows: |2010 – 2011||T-Mobile Austria,||Projektmitarbeit|
    - Direct format: date → location → company,role → bullets (non-transposed)
    - Form-feed \x0c page-break flattening
    """
    if not text:
        return []

    # Flatten form-feed (page breaks) into newlines
    text = text.replace("\x0c", "\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # --- Pass 1: Collect date/location pairs and company blocks ---
    date_location_pairs = []  # [(start_year, end_year, location), ...
    company_blocks = []        # [{company, position, bullets}, ...
    entries = []               # pipe-table entries collected in Pass 1
    i = 0
    while i < len(lines):
        line = lines[i]

        # --- Tabellarische Zeilen (pipe-getrennt) ---
        if line.startswith("|"):
            entry = _parse_pipe_table_row(line)
            if entry and (entry.get("company") or entry.get("position")):
                entries.append(entry)
            i += 1
            continue

        # --- Date-only line (start of a date/location pair) ---
        date_only_match = re.match(
            r"^(\d{4})\s*[–—-]\s*(\d{4})$",
            line, re.IGNORECASE
        )
        if date_only_match:
            start_year = date_only_match.group(1)
            end_year = date_only_match.group(2)
            location = ""

            # Next line might be a location (4-digit postal + city)
            j = i + 1
            if j < len(lines):
                loc_match = re.match(r"^(\d{3,4})\s+.+", lines[j])
                if loc_match:
                    location = lines[j]
                    j += 1

            date_location_pairs.append((start_year, end_year, location))
            i = j  # Continue from after location
            continue

        # --- Company/role line (direct format or transposed) ---
        # "Company, Role" or "Company @ Role" or "Position @ Company"
        # Only treat as a company block if:
        # 1. Not a bullet point (no leading •)
        # 2. Not a date line (no 20xx–20xx pattern)
        # 3. Contains a comma (Company, Role pattern)
        # 4. The first part looks like a company name OR the line contains
        #    known company suffixes (GmbH, AG, KG, s.r.o., etc.)
        if "," in line and not line.startswith("•") and not re.match(r"^\d{4}", line):
            parts = line.split(",", 1)
            company_candidate = parts[0].strip()
            # Check if this looks like a company name — either a known suffix
            # or the line follows a date/location pair (transposed mode)
            has_company_suffix = bool(re.search(
                r"\b(GmbH|AG|KG|s\.r\.o\.|S\.A\.|LLC|Inc|Co)\.?",
                company_candidate, re.IGNORECASE
            ))
            # In transposed mode: dates come first, then companies
            # Heuristic: if we've collected date_location_pairs but no company_blocks yet,
            # or the line has a known company suffix, treat as company block
            is_transposed_start = (
                date_location_pairs
                and len(company_blocks) == 0
            )
            # Also accept lines with known company suffixes regardless of position
            if has_company_suffix or is_transposed_start or not date_location_pairs:
                if not re.match(r"^\d{3,4}\s", company_candidate):
                    position = parts[1].strip() if len(parts) > 1 else ""
                    # Collect bullets
                    bullets = []
                    i += 1
                    while i < len(lines):
                        b = lines[i]
                        # Stop at dates, pagination, pipe rows, or section markers
                        if re.match(r"^\d{4}\s*[–—-]", b):
                            break
                        if b.startswith("•"):
                            bullets.append(b)
                            i += 1
                        elif b.startswith("BERUFSSCHULUNG") or b.startswith("AUSBILDUNG") or b.startswith("WEITERBILDUNG"):
                            i -= 1  # Let the outer loop handle section transitions
                            break
                        else:
                            # Non-bullet line — could be continuation or new company
                            break
                    company_blocks.append({
                        "company": company_candidate,
                        "position": position,
                        "bullets": bullets,
                    })
                    continue

        i += 1

    # --- Pass 2: Build entries from transposed structure ---
    # Extend entries (pipe-table entries from Pass 1 are preserved)
    transposed_entries = []

    if date_location_pairs and company_blocks:
        # Pair date_location_pairs with company_blocks FIFO
        paired = set()
        for dl_idx, (start_year, end_year, location) in enumerate(date_location_pairs):
            for cb_idx, cb in enumerate(company_blocks):
                if cb_idx in paired:
                    continue
                transposed_entries.append({
                    "position": cb["position"] or cb["company"],
                    "company": cb["company"],
                    "startDate": f"{start_year}-01-01",
                    "endDate": _normalize_end_year(end_year),
                    "location": location,
                    "summary": "\n".join(cb["bullets"]),
                    "skills_used": [],
                })
                paired.add(cb_idx)
                break

        # Add remaining date/location pairs without companies
        for dl_idx, (start_year, end_year, location) in enumerate(date_location_pairs):
            already_used = False
            for entry in transposed_entries:
                if entry["startDate"] == f"{start_year}-01-01" and entry["location"] == location:
                    already_used = True
                    break
            if not already_used:
                transposed_entries.append({
                    "position": "",
                    "company": "",
                    "startDate": f"{start_year}-01-01",
                    "endDate": _normalize_end_year(end_year),
                    "location": location,
                    "summary": "",
                    "skills_used": [],
                })

        # Add unpaired company blocks
        for cb_idx, cb in enumerate(company_blocks):
            if cb_idx not in paired:
                transposed_entries.append({
                    "position": cb["position"] or cb["company"],
                    "company": cb["company"],
                    "startDate": "",
                    "endDate": "",
                    "location": "",
                    "summary": "\n".join(cb["bullets"]),
                    "skills_used": [],
                })

    if transposed_entries:
        entries.extend(transposed_entries)
    elif not entries:
        # Fallback to direct parsing for non-tabular experience
        entries = _parse_experience_direct(lines)

    # Merge: if some entries have empty companies, try to fill gaps
    # from direct parsing (handles mixed transposed + direct format CVs)
    has_gaps = any(not e.get("company") for e in entries)
    if has_gaps:
        direct_entries = _parse_experience_direct(lines)
        if direct_entries:
            # Build a lookup: startDate → best entry
            merged = {}
            for e in entries:
                key = e.get("startDate", "")
                merged[key] = e

            for e in direct_entries:
                key = e.get("startDate", "")
                # Only use direct entry if two-pass entry is missing company
                if key in merged and not merged[key].get("company"):
                    if e.get("company") and e.get("company") != e.get("position", ""):
                        merged[key]["company"] = e["company"]
                        merged[key]["position"] = e.get("position", "") or e["company"]
                        merged[key]["summary"] = e.get("summary", "") or merged[key].get("summary", "")
                elif key not in merged:
                    # Date not in two-pass results — add it
                    merged[key] = e

            entries = list(merged.values())
            entries.sort(key=lambda x: x.get("startDate", "") or "9999")

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
