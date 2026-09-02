"""Experience parser for PyMuPDF sort=True text output.

The sort=True mode returns text in row-by-row order (top-to-bottom,
left-to-right within each row), preserving the 2D table structure
of tabular CVs.

Compared to the column-extracted text from pdfminer:
- Each row line contains all its cells (date, company, role) separated
  by spaces instead of being split into separate column lines.
- Company headers appear on their own line ABOVE the rows they apply to.
- Locations still appear on a separate line below the date+company+role row.

The parser:
1. Identifies "date lines" containing year patterns.
2. Detects whether the line also has a "Company, Role" pattern (row line)
   or is just a standalone date under a pending company header.
3. Company headers are standalone lines with no date — they apply to all
   subsequent date rows until another company header is encountered.
4. Location is captured from the next line if it matches postal+city.
5. Bullet/continuation lines form the summary until the next entry.

This handles:
- Direct format: date+company+role on one line, location next, bullets after.
- Company-first: standalone company, then date+role rows, then bullets.
- One-company-many-dates: same company applies to multiple date rows.
"""
import re


def _normalize_end_year(end_year: str) -> str:
    if end_year.lower() in ("present", "derzeit", "aktuell"):
        return "Present"
    return end_year


# Match the "Date — Company, Role" or "Date — Company" pattern in row lines
_DATE_RE = re.compile(
    r"^(\d{4})\s*[–—-]\s*(\d{4}|(?:\b(?:Present|derzeit|aktuell)\b))",
    re.IGNORECASE,
)
_LOCATION_RE = re.compile(r"^(\d{3,4})\s+.+")
_PAGINATION_RE = re.compile(r"^\d+\s*/\s*\d+$")
_SECTION_MARKERS = (
    "KENNTNISSE", "FÄHIGKEITEN", "SKILLS", "SOFT SKILLS",
    "AUSBILDUNG", "BERUFSSCHULUNG", "WEITERBILDUNG", "BILDUNG",
    "SPRACHEN", "PERSÖNLICHKEIT", "ZERTIFIKATE", "PROJEKTE",
    "PUBLIKATIONEN",
)
_COMPANY_SUFFIXES = (
    "GmbH", "AG", "KG", "s.r.o.", "S.A.", "s.r.l.", "LLC", "Inc",
    "Co. KG", "& Co KG", "mbH", "mbB",
)
_KNOWN_BRANDS = (
    "telekom", "t-mobile", "siemens", "ricoh", "trimetis",
    "ipcenter", "artex", "volkshochschule", "volksschule",
    "akv", "candidatis", "ivm", "amdocs", "promotion",
)


def _is_section_marker(line: str) -> bool:
    stripped = line.upper().strip()
    return any(stripped.startswith(m) for m in _SECTION_MARKERS)


def _previous_had_bullet_after_date(lines: list, i: int) -> bool:
    """Check if there's a • bullet between the current line and the most recent date row.

    A bullet that follows a date row indicates we're inside that entry's
    description, so subsequent non-bullet lines until the next date row are
    continuations of that description, NOT standalone company headers.
    """
    for j in range(i - 1, -1, -1):
        prev = lines[j].strip()
        if not prev:
            continue
        # Bullet may be at start OR after a location on the same line:
        # "1010 Wien    •Konzeption einer OM-Strategie..."
        if "•" in prev or prev.startswith("-"):
            return True
        if _DATE_RE.match(prev):
            return False
        # Stop at lines that look like real company headers (suffix or known brand)
        lower = prev.lower()
        if any(re.search(r"\b" + re.escape(s.lower()) + r"\b", lower) for s in _COMPANY_SUFFIXES):
            return False
        if any(re.search(r"\b" + re.escape(brand) + r"\b", lower) for brand in _KNOWN_BRANDS):
            return False
    return False


def _previous_was_bullet(lines: list, i: int) -> bool:
    """Check if the previous non-empty line in lines[:i] was a bullet."""
    for j in range(i - 1, -1, -1):
        prev = lines[j].strip()
        if not prev:
            continue
        return prev.startswith("•") or prev.startswith("-")
    return False


def _looks_like_company(line: str, original: str = "", previous_was_bullet: bool = False,
                        previous_had_bullet_after_date: bool = False) -> bool:
    """Detect standalone company name (no date pattern on this line).

    Args:
        line: The stripped line content.
        original: The original (unstripped) line.
        previous_was_bullet: True if the previous non-empty line started with •.
        previous_had_bullet_after_date: True if any line since the last date row
                                        was a • bullet. Indicates we're inside an
                                        entry's description, so this line is a
                                        continuation, not a company header.
    """
    if _DATE_RE.match(line):
        return False
    if _LOCATION_RE.match(line):
        return False
    if line.startswith("•") or line.startswith("-"):
        return False
    if _PAGINATION_RE.match(line):
        return False
    if _is_section_marker(line):
        return False
    if previous_was_bullet:
        # If line has strong company signal, override the bullet check.
        lower = line.lower()
        if any(re.search(r"\b" + re.escape(s.lower()) + r"\b", lower) for s in _COMPANY_SUFFIXES):
            pass  # Continue to suffix/brand checks
        elif any(re.search(r"\b" + re.escape(brand) + r"\b", lower) for brand in _KNOWN_BRANDS):
            pass  # Continue
        else:
            return False
    # Lines inside an entry's description (after a bullet following a date) are
    # usually continuations. But: if the line has a strong company signal (suffix
    # or known brand), it can still be a company header for a new entry group.
    if previous_had_bullet_after_date:
        lower = line.lower()
        has_strong_company_signal = (
            any(re.search(r"\b" + re.escape(s.lower()) + r"\b", lower) for s in _COMPANY_SUFFIXES)
            or any(re.search(r"\b" + re.escape(brand) + r"\b", lower) for brand in _KNOWN_BRANDS)
        )
        if not has_strong_company_signal:
            return False
    if original:
        leading = len(original) - len(original.lstrip(" "))
        if leading >= 5 and not line.startswith("•"):
            return False
    if line.endswith(":") or line.startswith("Veränderungsgrund") or line.startswith("Kontext"):
        return False
    # Note: don't reject lowercase-starting lines — company names can be lowercase
    # (e.g. "ipcenter.at GmbH", "t-mobile"). The bullet-context check above
    # already excludes continuations.
    lower = line.lower()
    if any(re.search(r"\b" + re.escape(s.lower()) + r"\b", lower) for s in _COMPANY_SUFFIXES):
        return True
    if any(re.search(r"\b" + re.escape(brand) + r"\b", lower) for brand in _KNOWN_BRANDS):
        return True
    if any(line.lower().startswith(prefix) for prefix in (
        "der ", "die ", "das ", "und ", "sowie ", " von ",
        "zur ", "im ", "beim ", "für ", "mit ", "nach ",
    )):
        return False
    words = line.split()
    if 2 <= len(words) <= 5 and line[0].isupper():
        role_words = (
            "Administration", "Support", "Manager", "Director",
            "Engineer", "Developer", "Consultant", "Monitoring",
            "Vermittlung", "Promotion", "Personalvermittlung",
            "Vertrieb", "Beratung", "Aufsicht", "Saalpersonal",
            "Personal", "Beratung", "Koordination",
            "Kandidaten", "Bewerber", "Kunden", "Rechnungs",
            "Organisation", "Mitarbeit", "Projekt", "Service",
        )
        if len(words) == 2 and any(w in words[1] for w in (
            "Promotion", "Vermittlung", "Administration", "Services",
            "Support", "Management",
        )):
            return False
        if not any(r in line for r in role_words):
            return True
    return False


def _parse_date_company_role(line: str) -> tuple:
    """Extract (start_year, end_year, company, role) from a row line.

    Returns (start, end, company, role) tuple. company and role may be empty
    if the line doesn't contain them.
    """
    m = _DATE_RE.match(line)
    if not m:
        return ("", "", "", "")
    start = m.group(1)
    end = _normalize_end_year(m.group(2))
    rest = line[m.end():].strip().lstrip(",").strip()
    # Try "Company, Role" pattern
    company, role = "", ""
    if "," in rest:
        # Find the FIRST top-level comma (not inside parentheses)
        depth = 0
        split_idx = -1
        for i, c in enumerate(rest):
            if c == "(":
                depth += 1
            elif c == ")":
                depth = max(0, depth - 1)
            elif c == "," and depth == 0:
                split_idx = i
                break
        if split_idx > 0:
            company = rest[:split_idx].strip()
            role = rest[split_idx + 1:].strip()
    else:
        # No comma — entire rest is the company (or just the date with nothing after)
        if rest:
            company = rest
    return (start, end, company, role)


def _parse_experience(lines: list, original_lines: list = None) -> list:  # type: ignore[assignment]
    """Parse experience lines from PyMuPDF sort=True output.

    Args:
        lines: List of stripped line content.
        original_lines: Optional list of original (unstripped) lines for
                        indentation-based classification. If not provided,
                        uses `lines` (no indent info available).

    Lines can be:
    - "2024 – 2025   ipcenter.at GmbH, Outplacement" — row line
    - "1100 Wien" — location
    - "IVM Technical Consultants" — company header (standalone)
    - "•Liaison zu Partnern..." — bullet
    - "Veränderungsgrund: ..." — bullet continuation
    - "1 / 2" — pagination (skip)
    - "KENNTNISSE" — section marker (stop)
    """
    if original_lines is None:
        original_lines = lines
    entries = []
    pending_company = None  # Company header applying to next date rows
    current_entry = None    # Entry being built

    def _new_entry():
        return {
            "position": "", "company": "", "startDate": "",
            "endDate": "", "location": "", "summary": "",
            "skills_used": [],
        }

    def _flush(entry):
        if entry and entry.get("startDate"):
            if not entry.get("position") and entry.get("company"):
                entry["position"] = entry["company"]
            entries.append(entry)

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if _is_section_marker(line):
            break
        if _PAGINATION_RE.match(line):
            i += 1
            continue

        # Track whether previous non-empty line was a bullet or continuation
        # (used to reject lines that follow bullets as standalone company headers)
        prev_is_bullet_or_cont = False
        if i > 0:
            for j in range(i - 1, -1, -1):
                prev = lines[j].strip()
                if not prev:
                    continue
                if prev.startswith("•") or prev.startswith("-"):
                    prev_is_bullet_or_cont = True
                # Don't propagate across date rows or company headers
                if _DATE_RE.match(prev) or _looks_like_company(prev):
                    prev_is_bullet_or_cont = False
                break

        # Row line: "Date — Company, Role" or "Date — Company" or "Date — Role"
        if _DATE_RE.match(line):
            start, end, company, role = _parse_date_company_role(line)

            # Flush previous entry
            _flush(current_entry)
            current_entry = _new_entry()
            current_entry["startDate"] = f"{start}-01-01"
            current_entry["endDate"] = end

            # Decide attribution: row has company/role vs pending company header
            if company and role and _looks_like_company(company):
                # Row contains full "Company, Role" — direct format row,
                # supersedes any pending company header.
                current_entry["company"] = company
                current_entry["position"] = role
                pending_company = None  # Reset — used
            elif company and _looks_like_company(company) and not pending_company:
                # Row contains company only — direct format row.
                current_entry["company"] = company
                current_entry["position"] = role or company
                pending_company = None
            elif pending_company:
                # Row under a pending company header (company-first format).
                # The "company" we parsed is actually a role here.
                current_entry["company"] = pending_company["company"]
                current_entry["position"] = company or role or pending_company["position"]
            else:
                # No company attribution possible — leave empty
                pass

            # Capture location from next line
            if i + 1 < len(lines) and _LOCATION_RE.match(lines[i + 1]):
                current_entry["location"] = lines[i + 1].strip()
                i += 2
            else:
                i += 1
            continue

        # Standalone company header (no date pattern)
        prev_had_bullet = _previous_had_bullet_after_date(lines, i)
        prev_was_bullet = _previous_was_bullet(lines, i)
        if _looks_like_company(line, original=original_lines[i], previous_was_bullet=prev_was_bullet,
                                previous_had_bullet_after_date=prev_had_bullet):
            _flush(current_entry)
            current_entry = None
            # Split "Company, Role" if present
            if "," in line:
                parts = line.split(",", 1)
                pending_company = {
                    "company": parts[0].strip(),
                    "position": parts[1].strip(),
                }
            else:
                pending_company = {
                    "company": line.strip(),
                    "position": "",
                }
            i += 1
            continue

        # Bullet line — attach to current_entry
        if line.startswith("•") or line.startswith("-"):
            if current_entry:
                if current_entry["summary"]:
                    current_entry["summary"] += "\n"
                current_entry["summary"] += line
            i += 1
            continue

        # Continuation or other — append to current_entry's summary
        if current_entry and current_entry.get("startDate"):
            if current_entry["summary"]:
                current_entry["summary"] += "\n"
            current_entry["summary"] += line
            i += 1
            continue

        i += 1

    # Flush last entry
    _flush(current_entry)

    # Sort by date descending
    entries.sort(key=lambda x: x.get("startDate", "") or "9999", reverse=True)
    return entries


__all__ = ["_parse_experience"]