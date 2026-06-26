"""Deal-breaker filters — hard constraints that eliminate jobs immediately.

Uses word-boundary regex matching instead of plain substring `in` to avoid
false positives: e.g., deal-breaker "java" should NOT block a job that
mentions "javascript", and "go" should NOT block "Google".
"""

import re
from typing import Dict, Tuple


def check_deal_breakers(profile: Dict, job: Dict) -> Tuple[bool, str]:
    """Check if a job violates any of the candidate's deal-breakers.

    Args:
        profile: Personal profile with preferences.deal_breakers.
        job: Job dict with title, location, requirements, etc.

    Returns:
        Tuple of (passes, reason).
        passes=True, reason="" if job is acceptable.
        passes=False, reason="..." with explanation.
    """
    deal_breakers = profile.get("preferences", {}).get("deal_breakers", [])
    if not deal_breakers:
        return True, ""

    job_text = " ".join([
        job.get("title", ""),
        job.get("description", ""),
        job.get("location", ""),
        " ".join(job.get("requirements", [])),
    ]).lower()

    for db in deal_breakers:
        db_lower = db.lower().strip()
        if not db_lower:
            continue
        # Use word-boundary matching to avoid false positives
        # (e.g., "java" matching "javascript", "go" matching "google").
        # Use (?<![a-z0-9]) and (?![a-z0-9]) instead of \b because \b
        # doesn't work correctly for tokens ending in non-word chars
        # like "c++" (the + is non-word, so \b fails after it).
        pattern = r"(?<![a-z0-9])" + re.escape(db_lower) + r"(?![a-z0-9])"
        if re.search(pattern, job_text):
            return False, f"Deal-breaker matched: '{db}'"

    return True, ""