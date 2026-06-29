#!/usr/bin/env python3
"""CLI: Match a profile against jobs from an austria-job-scout SQLite database.

Pipeline:
  1. Load profile (JSON)
  2. Query austria-job-scout DB for active jobs
  3. Adapt rows → cv-profile-assessment job schema (via scout_adapter)
  4. Apply bias filter (integration.job_filters) — exclude / flag / include
  5. Run the shared scoring pipeline (matching.pipeline.score_one_job)
     on included + flagged jobs (flagged are annotated)
  6. Output ranked results (JSON to stdout or file)

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
from integration.job_filters import classify_job
from matching import score_one_job, _calculate_years_experience


def match_scout_jobs(profile: dict, scout_db_path: Path) -> dict:
    """End-to-end: load → adapt → filter → score → sort.

    Returns a dict with three keys:
      - "ranked": list of scored jobs in include/flag bucket, sorted desc by score
      - "excluded": list of jobs excluded by bias filter (no scoring)
      - "summary": counts of each bucket
    """
    jobs = load_jobs_from_scout_db(scout_db_path)

    # Precompute profile-only values once (not per job)
    candidate_years = _calculate_years_experience(profile)
    profile_skill_names = {s["name"].lower() for s in profile.get("skills", []) if "name" in s}

    # Bias filter split
    scored, excluded = [], []
    n_flagged = 0
    for job in jobs:
        decision, reasons = classify_job(job)
        annotation = {"decision": decision, "reasons": reasons}
        if decision == "exclude":
            # Excluded jobs: keep a slim record (no scoring) with filter annotation
            source = job.get("_source") or {}
            excluded.append({
                "job_title": job.get("title", "Unknown"),
                "company": job.get("company", "Unknown"),
                "location": job.get("location", ""),
                "url": source.get("url"),
                "ats": source.get("ats"),
                "_filter": annotation,
            })
            continue
        if decision == "flag":
            n_flagged += 1
        # Mutate job to carry filter annotation through scoring
        job["_filter"] = annotation
        result = score_one_job(
            profile, job,
            candidate_years=candidate_years,
            profile_skill_names=profile_skill_names,
        )
        result["_filter"] = annotation
        scored.append(result)

    # Sort: blocked jobs last (still listed, ranked by overall desc among blocked).
    scored.sort(key=lambda r: (r.get("blocked", False), -r["overall_score"]))

    return {
        "ranked": scored,
        "excluded": excluded,
        "summary": {
            "total": len(jobs),
            "ranked": len(scored),
            "flagged": n_flagged,
            "excluded": len(excluded),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Match a CV profile against jobs from austria-job-scout DB"
    )
    parser.add_argument("profile", help="Path to profile JSON")
    parser.add_argument("scout_db", help="Path to austria-job-scout SQLite DB")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument("--no-excluded", action="store_true",
                        help="Omit excluded jobs from output (smaller JSON)")
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
        result = match_scout_jobs(profile, scout_db_path)
    except (FileNotFoundError, OSError) as e:
        print(f"Error: cannot read scout DB: {e}", file=sys.stderr)
        return 3

    summary = result["summary"]
    if summary["total"] == 0:
        print("No jobs found in scout DB.", file=sys.stderr)
        return 4

    candidate_name = profile.get("basics", {}).get("name", "candidate")
    print(
        f"Matched profile '{candidate_name}' against "
        f"{summary['total']} jobs from {scout_db_path.name}: "
        f"{summary['ranked']} ranked ({summary['flagged']} flagged), "
        f"{summary['excluded']} excluded",
        file=sys.stderr,
    )

    if args.no_excluded:
        result = {**result, "excluded": []}

    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
