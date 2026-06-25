"""Profile validator using JSON Schema (draft-07)."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Tuple

try:
    import jsonschema
except ImportError:
    jsonschema = None
    print("Warning: jsonschema not installed. Validation will be skipped.")


SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "profile_schema.json"


@lru_cache(maxsize=1)
def _load_schema(schema_path_str: str) -> Dict:
    """Load and cache JSON schema from disk.

    Cached because validation is called per-job in batch matching, and the
    schema doesn't change at runtime.
    """
    with open(schema_path_str) as f:
        return json.load(f)


class ProfileValidationError(Exception):
    """Raised when a profile fails JSON Schema validation."""
    pass


def validate_profile(profile: Dict, schema_path: Path | None = None) -> Tuple[bool, str]:
    """Validate a profile against the JSON Schema.

    Args:
        profile: Profile dict to validate.
        schema_path: Optional path to schema file. Defaults to bundled schema.

    Returns:
        Tuple of (is_valid, error_message).
        is_valid=True, error_message="" on success.
        is_valid=False, error_message="..." on failure.
    """
    if jsonschema is None:
        return _minimal_validation(profile)

    schema_file = schema_path or SCHEMA_PATH
    schema = _load_schema(str(schema_file))

    try:
        jsonschema.validate(instance=profile, schema=schema)
        return True, ""
    except jsonschema.ValidationError as e:
        return False, f"{e.message} at path: {list(e.path)}"
    except jsonschema.SchemaError as e:
        return False, f"Schema error: {e.message}"


def _minimal_validation(profile: Dict) -> Tuple[bool, str]:
    """Minimal validation without jsonschema dependency."""
    if not isinstance(profile, dict):
        return False, "Profile must be a dict"

    if "basics" not in profile:
        return False, "Missing required field: basics"
    if "skills" not in profile:
        return False, "Missing required field: skills"
    if "experience" not in profile:
        return False, "Missing required field: experience"

    basics = profile["basics"]
    if not basics.get("name"):
        return False, "basics.name is required"
    if not basics.get("email"):
        return False, "basics.email is required"

    return True, ""


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python validator.py <profile_json>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        profile = json.load(f)

    is_valid, error = validate_profile(profile)
    if is_valid:
        print("✓ Profile is valid")
    else:
        print(f"✗ Profile is invalid: {error}")
        sys.exit(1)