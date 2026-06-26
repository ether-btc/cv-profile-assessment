#!/usr/bin/env python3
"""CLI: Match a profile against one or more jobs and output ranked results.

Usage:
    python match_jobs.py <profile.json> <jobs_dir> [-o output.json]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from matching import (
    score_one_job,
    DEFAULT_WEIGHTS,
    _calculate_years_experience,
)


def match_profile_to_jobs(profile: dict, jobs: list) -> list:
    """Score profile against all jobs and return ranked results.

    Precomputes profile-only values once per batch (candidate_years,
    profile_skill_names) instead of recomputing per job.

    Args:
        profile: Personal profile dict.
        jobs: List of job dicts.

    Returns:
        List of match results, sorted by score descending.
    """
    # Profile-only values: compute once, reuse per job
    candidate_years = _calculate_years_experience(profile)
    profile_skill_names = {s["name"].lower() for s in profile.get("skills", []) if "name" in s}

    results = [
        score_one_job(
            profile, job,
            candidate_years=candidate_years,
            profile_skill_names=profile_skill_names,
        )
        for job in jobs
    ]

    # Sort by score descending
    results.sort(key=lambda r: r["overall_score"], reverse=True)
    return results


def main():
    parser = argparse.ArgumentParser(description="Match profile to jobs")
    parser.add_argument("profile", help="Path to profile JSON")
    parser.add_argument("jobs_dir", help="Path to directory containing job JSON files")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    args = parser.parse_args()

    profile_path = Path(args.profile)
    jobs_dir = Path(args.jobs_dir)

    if not profile_path.exists():
        print(f"Error: Profile not found: {profile_path}", file=sys.stderr)
        sys.exit(1)
    if not jobs_dir.is_dir():
        print(f"Error: Jobs directory not found: {jobs_dir}", file=sys.stderr)
        sys.exit(1)

    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    # Load all jobs
    job_files = sorted(jobs_dir.glob("*.json"))
    jobs = []
    for jf in job_files:
        try:
            job = json.loads(jf.read_text(encoding="utf-8"))
            jobs.append(job)
        except json.JSONDecodeError as e:
            print(f"Warning: Skipping invalid JSON in {jf}: {e}", file=sys.stderr)

    if not jobs:
        print(f"No jobs found in {jobs_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Matching profile '{profile['basics']['name']}' against {len(jobs)} jobs...", file=sys.stderr)

    results = match_profile_to_jobs(profile, jobs)

    output = json.dumps(results, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()