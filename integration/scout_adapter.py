"""Adapter: bridge austria-job-scout data → cv-profile-assessment job schema.

Converts either:
- A row from `austria_jobs` SQLite table (sqlite3.Row or dict), OR
- An `austria_job_scout.modules.indexer.IndexedJob` dataclass

into the job dict shape that the cv-profile-assessment matching engine
expects. See `data/sample_jobs/senior_backend_vienna.json` for the target
shape.

Design notes:
- austria-job-scout is an optional dependency. The import is lazy so this
  module loads cleanly even when austria-job-scout isn't installed.
- Years-of-experience heuristic: if a job description mentions "N+ years",
  extract that as `min_years_experience`. Otherwise default to 0, which
  the scorer treats as "no constraint".
- Remote policy is mapped: on_site/None → False, hybrid/remote → True,
  unknown → False (conservative — better to filter than to mislead).
- `seniority` enum is normalized to lowercase to match cv-profile-assessment
  schema values (junior/mid/senior/lead).
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

# Map austria-job-scout remote_policy → boolean (cv-profile-assessment schema).
_REMOTE_BOOL: dict[str, bool] = {
    "remote": True,
    "hybrid": True,   # hybrid is "at least partly remote"
    "on_site": False,
    "unknown": False,
}

# Substring hints for seniority normalization (defensive — scout already
# stores one of the canonical values, but descriptions sometimes leak
# free-form text like "Senior Engineer").
_SENIORITY_HINTS: list[tuple[str, str]] = [
    ("principal", "principal"),
    ("staff", "staff"),
    ("lead", "lead"),
    ("senior", "senior"),
    ("junior", "junior"),
    ("entry", "junior"),
    ("intern", "junior"),
    ("mid", "mid"),
    ("intermediate", "mid"),
]

# Match e.g. "5+ years", "3-5 years", "at least 2 years", "minimum 2 years"
_YEARS_PATTERN = re.compile(
    r"(?:"
    r"(?:at\s+least|minimum|min\.?)\s+(?P<min>\d+)\s*(?:years?|yrs?)"
    r"|"
    r"(?P<min2>\d+)\s*(?:\+|to|-|–|—)\s*\d*\s*(?:years?|yrs?)"
    r")",
    re.IGNORECASE,
)


# -----------------------------------------------------------------------------
# Low-level field mappers (exported for direct testing)
# -----------------------------------------------------------------------------

def remote_policy_to_bool(remote_policy: str | None) -> bool:
    """Map austria-job-scout `remote_policy` → cv-profile-assessment `remote` bool."""
    if not remote_policy:
        return False
    return _REMOTE_BOOL.get(remote_policy.lower(), False)


def normalize_seniority(value: str | None) -> str:
    """Map austria-job-scout `seniority` (or free-form text) → canonical enum.

    Returns one of: junior, mid, senior, lead, staff, principal, '' (unknown).
    """
    if not value:
        return ""
    s = value.lower().strip()
    for hint, canonical in _SENIORITY_HINTS:
        if hint in s:
            return canonical
    return ""


def extract_min_years(description: str | None) -> int:
    """Extract min years of experience from a job description.

    Returns 0 if no clear signal. Conservative — only matches explicit
    patterns like "5+ years", "3-5 years", "at least 2 years".
    """
    if not description:
        return 0
    match = _YEARS_PATTERN.search(description)
    if not match:
        return 0
    raw = match.group("min") or match.group("min2")
    if raw is None:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


def parse_skills_json(skills_json: str | None) -> list[str]:
    """Parse austria-job-scout `skills_json` (JSON array string) → list[str].

    Returns [] on any parse error — matching scorer treats empty as neutral.
    """
    if not skills_json:
        return []
    try:
        data = json.loads(skills_json)
        if isinstance(data, list):
            return [str(s) for s in data if s]
    except (json.JSONDecodeError, TypeError):
        return []
    return []


# -----------------------------------------------------------------------------
# Public adapter API
# -----------------------------------------------------------------------------

def adapt_austria_jobs_row(row: sqlite3.Row | dict) -> dict:
    """Convert one `austria_jobs` DB row → cv-profile-assessment job dict.

    Args:
        row: Either a sqlite3.Row (from austria-job-scout DB) or a plain dict
             with the same column names. See schema.sql for the column list.

    Returns:
        Dict matching the cv-profile-assessment job schema. Always contains
        the required fields: title, company, location, required_skills,
        preferred_skills, description. Other fields may be empty/None.
    """
    # sqlite3.Row and dict both support __getitem__; no need to distinguish.

    salary_min = row["salary_min"] or None
    salary_max = row["salary_max"] or None
    salary_currency = row["salary_currency"] or "EUR"
    salary_period = row["salary_period"] or "yearly"

    description = row["description"] or ""
    required_skills = parse_skills_json(row["skills_json"])

    return {
        "title": row["title"] or "",
        "company": row["company"] or "",
        "location": row["location"] or "",
        "remote": remote_policy_to_bool(row["remote_policy"]),
        "description": description,
        "requirements": [],   # scout stores skills in skills_json; requirements
                              # are recoverable from description but we don't
                              # fabricate them. Empty list = no penalty.
        "required_skills": required_skills,
        "preferred_skills": [],
        "min_years_experience": extract_min_years(description),
        "salary_range": {
            "min": salary_min,
            "max": salary_max,
            "currency": salary_currency,
            "period": salary_period,
        },
        "seniority_level": normalize_seniority(row["seniority"]),
        # Provenance — useful for debugging, doesn't affect matching
        "_source": {
            "ats": row["ats"],
            "url": row["url"],
            "source_domain": row["source_domain"],
            "scout_job_id": row["id"],
        },
    }


def adapt_indexed_job(indexed: Any) -> dict:
    """Convert an `IndexedJob` dataclass → cv-profile-assessment job dict.

    IndexedJob is a richer object (has embeddings, raw_json); we only use
    the metadata fields the matching engine needs.
    """
    description = indexed.description or ""
    return {
        "title": indexed.title or "",
        "company": indexed.company or "",
        "location": indexed.location or "",
        "remote": bool(indexed.remote),
        "description": description,
        "requirements": [],
        "required_skills": list(indexed.skills or []),
        "preferred_skills": [],
        "min_years_experience": extract_min_years(description),
        "salary_range": {
            "min": indexed.salary_min,
            "max": indexed.salary_max,
            "currency": indexed.currency or "EUR",
            "period": "yearly",
        },
        "seniority_level": normalize_seniority(indexed.seniority),
        "_source": {
            "ats": None,
            "url": indexed.url,
            "source_domain": None,
            "scout_job_id": indexed.job_id,
        },
    }


def load_jobs_from_scout_db(db_path: str | Path, status: str = "active") -> list[dict]:
    """Query austria-job-scout SQLite DB and adapt all matching rows.

    Args:
        db_path: Path to austria-job-scout SQLite database file. Must have
                 the `austria_jobs` table (see schema.sql).
        status: Only return jobs with this status (default: 'active').
                Pass None to return all statuses.

    Returns:
        List of adapted job dicts ready for the matching engine.

    Raises:
        FileNotFoundError: If db_path doesn't exist.
        sqlite3.OperationalError: If the DB doesn't have the austria_jobs table.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"austria-job-scout DB not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        if status is not None:
            query = "SELECT * FROM austria_jobs WHERE status = ? ORDER BY first_seen_at DESC"
            rows = conn.execute(query, (status,)).fetchall()
        else:
            query = "SELECT * FROM austria_jobs ORDER BY first_seen_at DESC"
            rows = conn.execute(query).fetchall()
        return [adapt_austria_jobs_row(row) for row in rows]
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# CLI smoke test
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <scout_db.sqlite>", file=sys.stderr)
        sys.exit(1)

    jobs = load_jobs_from_scout_db(sys.argv[1])
    print(f"Loaded {len(jobs)} jobs from {sys.argv[1]}")
    if jobs:
        sample = jobs[0]
        print("\nSample adapted job:")
        print(json.dumps(sample, indent=2, default=str))