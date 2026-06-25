"""Profile Package — Build and validate personal profiles.

Note: This package is named profile_builder_pkg because 'profile' shadows
Python's stdlib 'profile' module (causing spaCy import issues).
"""

from .profile_builder import build_profile_from_cv
from .validator import validate_profile, ProfileValidationError

__version__ = "0.1.0"
__all__ = ["build_profile_from_cv", "validate_profile", "ProfileValidationError"]