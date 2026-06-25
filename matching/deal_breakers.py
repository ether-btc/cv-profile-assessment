"""Deal-breaker filters — hard constraints that eliminate jobs immediately."""

from typing import Dict, List, Tuple


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
        db_lower = db.lower()
        if db_lower in job_text:
            return False, f"Deal-breaker matched: '{db}'"

    return True, ""


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 3:
        print("Usage: python deal_breakers.py <profile.json> <job.json>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        profile = json.load(f)
    with open(sys.argv[2]) as f:
        job = json.load(f)

    passes, reason = check_deal_breakers(profile, job)
    if passes:
        print("✓ Job passes all deal-breakers")
    else:
        print(f"✗ Job blocked: {reason}")