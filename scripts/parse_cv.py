#!/usr/bin/env python3
"""CLI: Parse a CV and output the structured profile as JSON.

Usage:
    python parse_cv.py <cv_path> [-o output.json]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from profile_builder_pkg import build_profile_from_cv, validate_profile


def main():
    parser = argparse.ArgumentParser(description="Parse CV into structured profile")
    parser.add_argument("cv_path", help="Path to CV file (.pdf, .docx, or .txt)")
    parser.add_argument("-o", "--output", help="Output JSON file (default: stdout)")
    args = parser.parse_args()

    try:
        profile = build_profile_from_cv(args.cv_path)
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
        print(f"Profile written to {args.output}")
    else:
        print(profile_json)

    sys.exit(0 if is_valid else 2)


if __name__ == "__main__":
    main()