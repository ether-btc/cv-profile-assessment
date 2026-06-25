#!/usr/bin/env python3
"""Seed a synthetic austria-job-scout SQLite DB from cv-profile-assessment sample jobs.

This exists so the Phase 4 integration (scripts/match_scout_jobs.py) can be
exercised end-to-end without network access and without running the actual
scout scraper. It reuses austria-job-scout's own schema.sql — the resulting
DB has the same shape as a real scout DB, so the adapter and matching engine
exercise the full path.

Usage:
    python scripts/seed_scout_db_from_samples.py [<output_db.sqlite>]

Default output: <project>/db/austria_job_scout_sample.sqlite
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# We import the schema path indirectly to avoid hard-coding austria-job-scout's
# package layout. If the package is on PYTHONPATH or installed, we use its
# schema.sql; otherwise we fall back to the project's bundled copy.

SCHEMA_CANDIDATES = [
    Path("/home/hermes-pi/projects/austria-job-scout/austria_job_scout/schema.sql"),
    PROJECT_ROOT / "tests" / "fixtures" / "scout_schema.sql",
]

SAMPLES_DIR = PROJECT_ROOT / "data" / "sample_jobs"
DEFAULT_OUTPUT = PROJECT_ROOT / "db" / "austria_job_scout_sample.sqlite"


def find_schema_path() -> Path:
    for p in SCHEMA_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(
        "Could not find austria-job-scout schema.sql. Looked at:\n  "
        + "\n  ".join(str(p) for p in SCHEMA_CANDIDATES)
    )


def adapt_sample_job_to_scout_row(sample: dict, scout_job_id: int) -> dict:
    """Convert a cv-profile-assessment sample job dict → austria_jobs row dict."""
    salary = sample.get("salary_range", {}) or {}
    # seniority_level is e.g. "senior"; scout stores "junior|mid|senior|lead"
    # — already compatible for known values; default to "unknown" otherwise.
    seniority = sample.get("seniority_level") or "unknown"
    if seniority not in {"junior", "mid", "senior", "lead"}:
        seniority = "unknown"

    # remote: scout stores on_site/hybrid/remote/unknown
    if sample.get("remote") is True:
        remote_policy = "remote"
    else:
        remote_policy = "on_site"

    # Build description with requirements for downstream matching
    description = sample.get("description", "")
    reqs = sample.get("required_skills", []) or []
    if reqs:
        description += "\n\nRequired skills: " + ", ".join(reqs)

    now = int(time.time())
    return {
        "url": f"https://scout.example/job/{scout_job_id}",
        "url_hash": f"hash{scout_job_id:04d}",
        "source_domain": "scout.example",
        "ats": "generic_html",
        "job_id_at_source": f"SAMPLE-{scout_job_id}",
        "title": sample.get("title", ""),
        "company": sample.get("company", ""),
        "location": sample.get("location", ""),
        "postal_code": None,
        "country": "AT",
        "remote_policy": remote_policy,
        "employment_type": "full_time",
        "seniority": seniority,
        "salary_min": salary.get("min"),
        "salary_max": salary.get("max"),
        "salary_currency": salary.get("currency", "EUR"),
        "salary_period": salary.get("period", "yearly"),
        "language": "en",
        "description": description,
        "description_html": None,
        "skills_json": json.dumps(sample.get("required_skills", [])),
        "first_seen_at": now,
        "last_checked_at": now,
        "last_changed_at": now,
        "status": "active",
    }


def build_db(schema_path: Path, output: Path, samples: list[dict]) -> int:
    """Create the DB from schema, insert samples, return row count."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    conn = sqlite3.connect(str(output))
    try:
        # Apply schema
        conn.executescript(schema_path.read_text(encoding="utf-8"))

        cols = [
            "url", "url_hash", "source_domain", "ats", "job_id_at_source",
            "title", "company", "location", "postal_code", "country",
            "remote_policy", "employment_type", "seniority",
            "salary_min", "salary_max", "salary_currency", "salary_period",
            "language", "description", "description_html",
            "skills_json", "first_seen_at", "last_checked_at",
            "last_changed_at", "status",
        ]
        placeholders = ",".join(["?"] * len(cols))
        col_list = ",".join(cols)

        for i, sample in enumerate(samples, start=1):
            row = adapt_sample_job_to_scout_row(sample, i)
            values = [row[c] for c in cols]
            conn.execute(
                f"INSERT INTO austria_jobs ({col_list}) VALUES ({placeholders})",
                values,
            )

        conn.commit()
        cur = conn.execute("SELECT count(*) FROM austria_jobs")
        return int(cur.fetchone()[0])
    finally:
        conn.close()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Seed synthetic austria-job-scout DB from sample jobs"
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=str(DEFAULT_OUTPUT),
        help=f"Output SQLite path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--samples-dir",
        default=str(SAMPLES_DIR),
        help="Directory of sample job JSON files",
    )
    args = parser.parse_args()

    output = Path(args.output)
    samples_dir = Path(args.samples_dir)
    schema_path = find_schema_path()

    samples = []
    for jf in sorted(samples_dir.glob("*.json")):
        samples.append(json.loads(jf.read_text(encoding="utf-8")))

    if not samples:
        print(f"No sample jobs found in {samples_dir}", file=sys.stderr)
        return 1

    row_count = build_db(schema_path, output, samples)
    print(f"Seeded {row_count} jobs into {output} (schema: {schema_path.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())