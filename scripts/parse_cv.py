#!/usr/bin/env python3
"""CLI: Parse a CV and output the structured profile as JSON.

Usage:
    python parse_cv.py <cv_path> [-o output.json] [--no-log]
    python parse_cv.py --history
"""

import argparse
import json
import sys
from pathlib import Path

# Make sibling packages importable when run as a script
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from profile_builder_pkg import build_profile_from_cv, validate_profile
from cv_profile_assessment import format_history_table, read_history


def main():
    parser = argparse.ArgumentParser(description="Parse CV into structured profile")
    parser.add_argument("cv_path", nargs="?", help="Path to CV file (.pdf, .docx, or .txt)")
    parser.add_argument("-o", "--output", help="Output JSON file (default: stdout)")
    parser.add_argument("--no-log", action="store_true",
                        help="Skip appending to usage history log")
    parser.add_argument("--history", action="store_true",
                        help="Show processing history table and exit")
    args = parser.parse_args()

    # History view mode (no CV needed)
    if args.history:
        print(format_history_table())
        return 0

    if not args.cv_path:
        parser.error("cv_path is required (or use --history)")

    try:
        profile = build_profile_from_cv(args.cv_path, log=not args.no_log)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate
    is_valid, error = validate_profile(profile)
    if not is_valid:
        print(f"Warning: Profile validation failed: {error}", file=sys.stderr)

    # Output
    profile_json = json.dumps(profile, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(profile_json, encoding="utf-8")
        # Compact summary line so users see what was found without opening JSON
        meta = profile.get("metadata", {})
        counts = {
            "skills": len(profile.get("skills", [])),
            "experience": len(profile.get("experience", [])),
            "language": meta.get("language", "?"),
            "sections_found": len(profile.get("basics", {}).get("languages", [])),
        }
        print(f"Profile written to {args.output}")
        print(f"Language: {counts['language']} | Skills: {counts['skills']} | "
              f"Experience: {counts['experience']} | "
              f"Languages extracted: {counts['sections_found']}")
        if meta.get("language") == "de":
            # German CVs may have low extraction — surface what we did get
            pass
    else:
        print(profile_json)

    return 0 if is_valid else 2


if __name__ == "__main__":
    sys.exit(main())
