"""CV Profile Assessment — Privacy-focused CV parser and job matching engine.

This package provides:
- CV/resume parsing (PDF, DOCX, TXT) with spaCy NER
- Profile building with JSON Schema validation
- Job-candidate matching with TF-IDF + weighted scoring
- Integration with austria-job-scout for live job databases

All processing is 100% local — no data leaves your machine.
"""

__version__ = "0.2.0"
__author__ = "ether-btc"

from .types import (
    # Enums
    SkillCategory,
    Proficiency,
    SectionKey,
    # Dataclasses
    Skill,
    Experience,
    Education,
    Project,
    Certification,
    LocationPreference,
    SalaryExpectations,
    RolePreferences,
    Preferences,
    Metadata,
    PersonalProfile,
    Job,
    MatchResult,
)

__all__ = [
    # Version
    "__version__",
    # Enums
    "SkillCategory",
    "Proficiency", 
    "SectionKey",
    # Dataclasses
    "Skill",
    "Experience",
    "Education",
    "Project",
    "Certification",
    "LocationPreference",
    "SalaryExpectations",
    "RolePreferences",
    "Preferences",
    "Metadata",
    "PersonalProfile",
    "Job",
    "MatchResult",
]