"""State-machine experience parser for mixed transposed/direct CVs.

Layout:
- pdfminer reads column-by-column: ALL dates+locations first, THEN companies+bullets
- First half: transposed (dates block → companies block → FIFO pairing)
- Second half: mixed (some dates have companies inline, some have companies before them)
- Skills section (KENNTNISSE) may bleed in — stop at section marker
"""
import re


def _normalize_end_year(end_year: str) -> str:
    if end_year.lower() in ("present", "derzeit", "aktuell"):
        return "Present"
    return end_year


_KNOWN_BRANDS = [
    "telekom", "t-mobile", "siemens", "ricoh", "trimetis",
    "ipcenter", "artex", "volkshochschule", "volksschule",
    "akv", "candidatis", "ivm", "amdocs", "promotion",
]

def _looks_like_company_suffix(line: str) -> bool:
    lower = line.lower()
    if re.search(r"\b(gmbh|ag|kg|s\.r\.o\.|s\.a\.|llc|inc|co\.?)\b", lower):
        return True
    return any(brand in lower for brand in _KNOWN_BRANDS)


def _is_date_line(line: str) -> bool:
    return bool(re.match(
        r"^(\d{4})\s*[–—-]\s*(\d{4}|(?:\b(?:Present|derzeit|aktuell)\b))",
        line, re.IGNORECASE
    ))


def _is_location_line(line: str) -> bool:
    return bool(re.match(r"^(\d{3,4})\s+.+", line))


def _is_pagination(line: str) -> bool:
    return bool(re.match(r"^\d+\s*\/\s*\d+$", line))


def _is_section_marker(line: str) -> bool:
    """Detect section boundaries within extracted text."""
    stripped = line.upper().strip()
    if stripped.startswith(("BERUFSSCHULUNG", "AUSBILDUNG", "WEITERBILDUNG",
                            "KENNTNISSE", "FÄHIGKEITEN", "SKILLS",
                            "SOFT SKILLS", "IT-KENNTNISSE",
                            "TECHNISCHE KENNTNISSE",
                            "PERSÖNLICHKEIT", "SPRACHEN")):
        return True
    # Stop at skill/product-like lines that bleed from skills section
    # These appear after the last experience entry and are clearly skill names
    skill_product_patterns = [
        "mdm,", "clearsales", "clarify", "ad serving",
        "google analytics", "business english",
        "microsoft ads", "ms ad,",
    ]
    lower = line.lower().strip()
    return any(p in lower for p in skill_product_patterns)


def _is_company_name(line: str, prev_was_bullet: bool = False) -> bool:
    """Detect if a line looks like a company name."""
    if line.startswith("•"):
        return False
    if _is_date_line(line) or _is_location_line(line):
        return False
    if _is_pagination(line) or _is_section_marker(line):
        return False
    # Don't match if previous line was a bullet (continuation)
    if prev_was_bullet:
        return False
    return _looks_like_company_suffix(line)


def _parse_company_role(line: str) -> tuple:
    """Parse 'Company, Role' → (company, role). 'Company' → (company, company)."""
    if "," in line:
        parts = line.split(",", 1)
        c = parts[0].strip()
        r = parts[1].strip() if len(parts) > 1 else ""
        if not re.match(r"^\d{3,4}\s", c) and not _is_date_line(c):
            return (c, r or c)
    return (line, line)


def _parse_experience(lines: list) -> list:
    """Parse experience lines into structured entries.

    Strategy:
    1. Remove skills-section bleed
    2. Walk lines in order, classifying: date, location, company, bullet, other
    3. Use a deque for orphaned dates and a deque for orphaned companies
    4. When a company is found:
       - If there's a pending_date with no company → assign (direct format)
       - Else if there are orphaned dates → pop oldest, assign company (transposed)
       - Else → save as orphaned company
    5. When a date is found:
       - If there's a pending_company → assign (company-first)
       - Else → save date, collect following location
    """
    from collections import deque

    # Phase 1: Classify lines (stop at skills section)
    classified = []
    prev_was_bullet = False  # Track if previous line was a bullet (continuation)
    for i, line in enumerate(lines):
        if _is_section_marker(line):
            break

        if _is_pagination(line):
            classified.append(("skip", line, i))
            prev_was_bullet = False
        elif _is_date_line(line):
            classified.append(("date", line, i))
            prev_was_bullet = False
        elif _is_location_line(line):
            classified.append(("location", line, i))
            prev_was_bullet = False
        elif line.startswith("•"):
            classified.append(("bullet", line, i))
            prev_was_bullet = True
        elif _is_company_name(line, prev_was_bullet):
            classified.append(("company", line, i))
            prev_was_bullet = False
        else:
            classified.append(("other", line, i))
            prev_was_bullet = False

    # Phase 2: State machine
    entries = []
    pending_date = None      # current date entry awaiting company
    pending_company = None   # current company awaiting date (company-first)
    orphaned_dates = deque()  # dates saved from transposed blocks (FIFO)
    orphaned_companies = deque()  # companies saved for future dates

    def _new_entry():
        return {
            "position": "", "company": "", "startDate": "",
            "endDate": "", "location": "", "summary": "",
            "skills_used": [], "_line_idx": 0,
        }

    i = 0
    n = len(classified)
    while i < n:
        kind, line, orig_i = classified[i]

        if kind == "skip":
            i += 1
            continue

        if kind == "date":
            m = re.match(
                r"^(\d{4})\s*[–—-]\s*(\d{4}|(?:\b(?:Present|derzeit|aktuell)\b))",
                line, re.IGNORECASE
            )
            if m:
                new_e = _new_entry()
                new_e["startDate"] = f"{m.group(1)}-01-01"
                new_e["endDate"] = _normalize_end_year(m.group(2))
                new_e["_line_idx"] = orig_i

                # Collect following location
                if i + 1 < n and classified[i + 1][0] == "location":
                    new_e["location"] = classified[i + 1][1]
                    i += 2
                else:
                    i += 1

                # Assign pending_company if exists (company-first format)
                if pending_company:
                    new_e["company"] = pending_company["company"]
                    new_e["position"] = pending_company["position"]
                    new_e["summary"] = pending_company.get("summary", "")
                    pending_company = None
                else:
                    # Save pending_date to orphaned_dates if it has no company
                    # (transposed mode: dates come in sequence without companies)
                    if pending_date and not pending_date.get("company"):
                        orphaned_dates.append(pending_date)
                    pending_date = new_e
            continue

        if kind == "location":
            if pending_date:
                pending_date["location"] = line
            elif orphaned_dates:
                orphaned_dates[-1]["location"] = line
            elif entries and not entries[-1].get("location"):
                entries[-1]["location"] = line
            i += 1
            continue

        if kind == "company":
            company_name, role = _parse_company_role(line)

            # Collect bullets/other after company
            i += 1
            summary_lines = []
            while i < n:
                ik, il, _ = classified[i]
                if ik in ("date", "skip", "company"):
                    break
                summary_lines.append(il)
                i += 1
            summary = "\n".join(summary_lines)

            # Decide: direct (assign to pending_date) or transposed (orphan)?
            if pending_date and not pending_date.get("company") and not orphaned_dates:
                # Direct format: company follows date immediately
                pending_date["company"] = company_name
                pending_date["position"] = role or company_name
                if summary:
                    pending_date["summary"] = summary
                entries.append(pending_date)
                pending_date = None
            else:
                # Transposed or company-first: create orphaned company
                # Close pending_date if it exists (it's for a later company)
                if pending_date and not pending_date.get("company"):
                    orphaned_dates.append(pending_date)
                    pending_date = None

                oc = _new_entry()
                oc["company"] = company_name
                oc["position"] = role or company_name
                oc["_line_idx"] = orig_i
                if summary:
                    oc["summary"] = summary
                orphaned_companies.append(oc)
            continue

        if kind == "bullet":
            # Attach to: pending_date > orphaned_companies[-1] > orphaned_dates[-1] > entries[-1]
            target = None
            if pending_date:
                target = pending_date
            elif orphaned_companies:
                target = orphaned_companies[-1]
            elif orphaned_dates:
                target = orphaned_dates[-1]
            elif entries:
                target = entries[-1]

            if target:
                if target["summary"]:
                    target["summary"] += "\n"
                target["summary"] += line
                i += 1
                # Collect continuation lines
                while i < n:
                    ik, il, _ = classified[i]
                    if ik in ("date", "skip", "company", "bullet", "location"):
                        break
                    if target["summary"]:
                        target["summary"] += "\n"
                    target["summary"] += il
                    i += 1
                continue

        # "other" — could be a role or continuation
        if pending_date and not pending_date.get("company"):
            if not _is_company_name(line) and not line.startswith("•"):
                if pending_date["position"]:
                    if pending_date["summary"]:
                        pending_date["summary"] += "\n"
                    pending_date["summary"] += line
                else:
                    pending_date["position"] = line
                i += 1
                # Skip continuation lines
                while i < n:
                    ik, il, _ = classified[i]
                    if ik in ("date", "skip", "company"):
                        break
                    i += 1
                continue

        if pending_company:
            if pending_company["summary"]:
                pending_company["summary"] += "\n"
            pending_company["summary"] += line
            i += 1
            continue

        if orphaned_companies:
            if orphaned_companies[-1]["summary"]:
                orphaned_companies[-1]["summary"] += "\n"
            orphaned_companies[-1]["summary"] += line
            i += 1
            continue

        if entries:
            if entries[-1]["summary"]:
                entries[-1]["summary"] += "\n"
            entries[-1]["summary"] += line
        i += 1

    # Save remaining pending entries
    if pending_date:
        orphaned_dates.append(pending_date)
    if pending_company:
        entries.append(pending_company)
    # Save remaining orphaned dates to entries
    for od in orphaned_dates:
        entries.append(od)
    # Save remaining orphaned companies (will be paired or kept as-is)
    entries.extend(list(orphaned_companies))

    # Phase 3: Pair orphaned dates (no company) with orphaned companies (no date)
    orphans_dates = [e for e in entries if e.get("startDate") and not e.get("company")]
    orphans_companies = [e for e in entries if not e.get("startDate") and e.get("company")]
    if orphans_dates and orphans_companies:
        # FIFO pairing: first date gets first company (both in chronological order)
        for od in orphans_dates:
            if not orphans_companies:
                break
            oc = orphans_companies.pop(0)
            od["company"] = oc.get("company", "")
            if not od.get("position"):
                od["position"] = oc.get("position", "") or oc.get("company", "")
            if not od.get("summary"):
                od["summary"] = oc.get("summary", "")
        # Remove consumed orphaned companies from entries
        entries = [e for e in entries if e.get("startDate") or not e.get("company")]

    # Phase 4: Sort by date descending
    entries.sort(key=lambda x: x.get("startDate", "") or "9999", reverse=True)

    # Clean up
    entries = [e for e in entries if e.get("startDate") or e.get("company")]
    for e in entries:
        # If position is empty OR equals company name (no real role found),
        # leave position empty rather than duplicating company
        if e.get("position") == e.get("company") and e.get("company"):
            # Position-only entry (company came without role) — keep as-is
            pass
        elif not e.get("position") and e.get("company"):
            e["position"] = e["company"]
        e.pop("_line_idx", None)

    return entries
