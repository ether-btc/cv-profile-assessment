#!/usr/bin/env python3
"""CLI: Match a profile against jobs from an austria-job-scout SQLite database.

Pipeline:
  1. Load profile (JSON)
  2. Query austria-job-scout DB for active jobs
  3. Adapt rows → cv-profile-assessment job schema (via scout_adapter)
  4. Run the shared scoring pipeline (matching.pipeline.score_one_job)
  5. Output ranked results (JSON to stdout or file)

Usage:
    python match_scout_jobs.py <profile.json> <scout_db.sqlite> [-o output.json]

Exit codes:
  0  success (results written or printed)
  1  invalid arguments
  2  profile not found
  3  scout DB not found / not readable
  4  no jobs found in scout DB
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make sibling packages importable when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from integration.scout_adapter import load_jobs_from_scout_db
from matching import score_one_job, _calculate_years_experience


def match_scout_jobs(profile: dict, scout_db_path: Path) -> list[dict]:
    """End-to-end: load → adapt → score → sort."""
    jobs = load_jobs_from_scout_db(scout_db_path)

    # Precompute profile-only values once (not per job)
    candidate_years = _calculate_years_experience(profile)
    profile_skill_names = {s["name"].lower() for s in profile.get("skills", [])}

    results = [
        score_one_job(
            profile, job,
            candidate_years=candidate_years,
            profile_skill_names=profile_skill_names,
        )
        for job in jobs
    ]
    # Sort: blocked go last (still listed so user sees what was filtered)
    results.sort(key=lambda r: (r.get("blocked", False), -r["overall_score"]))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Match a CV profile against jobs from austria-job-scout DB"
    )
    parser.add_argument("profile", help="Path to profile JSON")
    parser.add_argument("scout_db", help="Path to austria-job-scout SQLite DB")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    args = parser.parse_args()

    profile_path = Path(args.profile)
    scout_db_path = Path(args.scout_db)

    if not profile_path.exists():
        print(f"Error: profile not found: {profile_path}", file=sys.stderr)
        return 2
    if not scout_db_path.exists():
        print(f"Error: scout DB not found: {scout_db_path}", file=sys.stderr)
        return 3

    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: invalid profile JSON: {e}", file=sys.stderr)
        return 2

    try:
        results = match_scout_jobs(profile, scout_db_path)
    except (FileNotFoundError, OSError) as e:
        print(f"Error: cannot read scout DB: {e}", file=sys.stderr)
        return 3

    if not results:
        print("No jobs found in scout DB.", file=sys.stderr)
        return 4

    candidate_name = profile.get("basics", {}).get("name", "candidate")
    print(
        f"Matched profile '{candidate_name}' against {len(results)} jobs from "
        f"{scout_db_path.name}",
        file=sys.stderr,
    )

    output = json.dumps(results, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())