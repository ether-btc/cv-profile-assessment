"""Matching Package — Job-candidate matching engine."""

from .tfidf_matcher import compute_tfidf_similarity, profile_to_text, job_to_text
from .deal_breakers import check_deal_breakers
from .scorer import (
    score_required_skills,
    score_experience,
    score_preferred,
    compute_overall_score,
    DEFAULT_WEIGHTS,
    PROFICIENCY_WEIGHT,
    _calculate_years_experience,
)
from .pipeline import score_one_job, score_many_jobs, score_jobs_parallel

__version__ = "0.2.0"
__all__ = [
    "compute_tfidf_similarity",
    "profile_to_text",
    "job_to_text",
    "check_deal_breakers",
    "score_required_skills",
    "score_experience",
    "score_preferred",
    "compute_overall_score",
    "score_one_job",
    "score_many_jobs",
    "score_jobs_parallel",
    "DEFAULT_WEIGHTS",
    "PROFICIENCY_WEIGHT",
    "_calculate_years_experience",
]