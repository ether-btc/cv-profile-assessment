"""Weighted scoring — combines multiple signals into a final match score.

Formula:
  match_score = (
      required_skills_score * 0.45 +
      experience_score * 0.25 +
      preferred_score * 0.18 +
      keyword_score * 0.12
  )

Deal-breakers and location/salary hard filters eliminate jobs entirely.
"""

import re
from typing import Dict, Optional


# Module-level constants — avoid rebuilding per call.
PROFICIENCY_WEIGHT: Dict[str, float] = {
    "expert": 1.0,
    "advanced": 0.85,
    "intermediate": 0.6,
    "beginner": 0.3,
}

DEFAULT_WEIGHTS: Dict[str, float] = {
    "required_skills": 0.45,
    "experience": 0.25,
    "preferred": 0.18,
    "keyword": 0.12,
}


def score_required_skills(profile: Dict, job: Dict) -> float:
    """Score 0.0-1.0: how well profile skills cover required job skills.

    Considers proficiency levels (expert > advanced > intermediate > beginner).
    """
    required = {s.lower() for s in job.get("required_skills", [])}
    if not required:
        return 1.0  # No required skills = perfect match for this dimension

    profile_skills = {
        s["name"].lower(): s.get("proficiency", "intermediate")
        for s in profile.get("skills", []) if "name" in s
    }

    matched_weight = 0.0
    for req_skill in required:
        # Exact match
        if req_skill in profile_skills:
            matched_weight += PROFICIENCY_WEIGHT.get(profile_skills[req_skill], 0.5)
            continue
        # Partial match (word-boundary substring match)
        # Use (?<![a-z0-9])/(?![a-z0-9]) to avoid 'r' matching 'react', 'go' matching 'google'
        for prof_skill, prof_level in profile_skills.items():
            pattern = r"(?<![a-z0-9])" + re.escape(req_skill) + r"(?![a-z0-9])"
            if re.search(pattern, prof_skill.lower()):
                matched_weight += PROFICIENCY_WEIGHT.get(prof_level, 0.5) * 0.7
                break

    return min(matched_weight / len(required), 1.0)


def score_experience(profile: Dict, job: Dict, candidate_years: Optional[float] = None) -> float:
    """Score 0.0-1.0: experience alignment.

    Args:
        profile: Personal profile dict.
        job: Job dict with min_years_experience.
        candidate_years: Optional precomputed years (for batch efficiency).
            If None, computed from profile.

    Considers years of experience and seniority level match.
    """
    required_years = job.get("min_years_experience", 0)
    if required_years == 0:
        return 1.0

    if candidate_years is None:
        candidate_years = _calculate_years_experience(profile)

    # When dates are absent (Phase 1 placeholder), score neutrally.
    # Ponytail: don't fake data; instead, score as "unknown".
    if candidate_years == 0:
        return 0.7

    if candidate_years >= required_years:
        # Over-qualified: flight-risk penalty
        excess = candidate_years - required_years
        penalty = min(excess * 0.05, 0.2)  # up to 20% penalty
        return max(1.0 - penalty, 0.8)

    gap_ratio = candidate_years / required_years if required_years > 0 else 1.0
    return max(gap_ratio, 0.0)


def _calculate_years_experience(profile: Dict) -> float:
    """Sum up years from all experience entries (rough estimate)."""
    total_years = 0.0
    for exp in profile.get("experience", []):
        start = exp.get("startDate")
        end = exp.get("endDate") or "2099-12-31"

        if not start:
            continue

        try:
            start_year = int(start[:4])
            end_year = int(end[:4])
            duration = max(end_year - start_year, 0)
            total_years += duration
        except (ValueError, IndexError):
            continue

    return total_years


def score_preferred(profile: Dict, job: Dict, profile_skill_names: Optional[set] = None) -> float:
    """Score 0.0-1.0: preferred qualifications match.

    Args:
        profile: Personal profile dict.
        job: Job dict with preferred_skills.
        profile_skill_names: Optional precomputed lowercased skill names set
            (for batch efficiency).
    """
    preferred = {s.lower() for s in job.get("preferred_skills", [])}
    if not preferred:
        return 0.5  # Neutral when no preferred skills specified

    if profile_skill_names is None:
        profile_skill_names = {s["name"].lower() for s in profile.get("skills", [])}

    matched = len(preferred & profile_skill_names)
    return matched / len(preferred)


def compute_overall_score(
    required_skills: float,
    experience: float,
    preferred: float,
    keyword: float,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """Compute weighted overall match score.

    Args:
        required_skills: 0-1 score for required skills coverage.
        experience: 0-1 score for experience alignment.
        preferred: 0-1 score for preferred qualifications.
        keyword: 0-1 score for keyword/TF-IDF overlap.
        weights: Optional custom weights dict.

    Returns:
        Final score between 0.0 and 1.0.
    """
    w = weights or DEFAULT_WEIGHTS

    score = (
        required_skills * w["required_skills"]
        + experience * w["experience"]
        + preferred * w["preferred"]
        + keyword * w["keyword"]
    )

    return round(min(max(score, 0.0), 1.0), 4)


