"""Shared scoring pipeline — single source of truth for job-candidate matching.

Both CLIs (scripts/match_jobs.py and scripts/match_scout_jobs.py) call this
to avoid duplicating the scoring logic. The result dict includes optional
provenance fields (url, ats) pulled from job._source when present.
"""

from __future__ import annotations

from typing import Dict, Optional, Set

from .deal_breakers import check_deal_breakers
from .scorer import (
    DEFAULT_WEIGHTS,
    _calculate_years_experience,
    compute_overall_score,
    score_experience,
    score_preferred,
    score_required_skills,
)
from .tfidf_matcher import compute_tfidf_similarity


def score_one_job(
    profile: dict,
    job: dict,
    candidate_years: Optional[float] = None,
    profile_skill_names: Optional[Set[str]] = None,
) -> dict:
    """Score one job against a profile. Returns result dict.

    This is the single source of truth for the scoring pipeline:
      deal-breaker filter → 4 component scores → weighted combination.

    Args:
        profile: Personal profile dict (schema-validated).
        job: Job dict (from adapter, sample JSON, or match_jobs.py).
        candidate_years: Precomputed years of experience. Lazy-computed
            if None. For batch use, pass from caller to avoid O(n) recompute.
        profile_skill_names: Precomputed lowercased skill name set.
            Lazy-computed if None.

    Returns:
        Dict with: job_title, company, location, remote, overall_score,
        blocked, component_scores, weights, and optional url/ats/block_reason.
    """
    source = job.get("_source") or {}

    # Stage 1: Hard filter — deal-breakers
    passes, db_reason = check_deal_breakers(profile, job)
    if not passes:
        return {
            "job_title": job.get("title", "Unknown"),
            "company": job.get("company", "Unknown"),
            "overall_score": 0.0,
            "blocked": True,
            "block_reason": db_reason,
            "url": source.get("url"),
        }

    # Lazy-compute profile-only values if not precomputed
    if candidate_years is None:
        candidate_years = _calculate_years_experience(profile)
    if profile_skill_names is None:
        profile_skill_names = {s["name"].lower() for s in profile.get("skills", []) if "name" in s}

    # Stage 2: Component scores
    req = score_required_skills(profile, job)
    exp = score_experience(profile, job, candidate_years=candidate_years)
    pref = score_preferred(profile, job, profile_skill_names=profile_skill_names)
    kw = compute_tfidf_similarity(profile, job)

    # Stage 3: Weighted overall
    overall = compute_overall_score(req, exp, pref, kw)

    return {
        "job_title": job.get("title", "Unknown"),
        "company": job.get("company", "Unknown"),
        "location": job.get("location", ""),
        "remote": job.get("remote", False),
        "url": source.get("url"),
        "ats": source.get("ats"),
        "overall_score": overall,
        "blocked": False,
        "component_scores": {
            "required_skills": round(req, 4),
            "experience": round(exp, 4),
            "preferred": round(pref, 4),
            "keyword_tfidf": round(kw, 4),
        },
        "weights": DEFAULT_WEIGHTS,
    }
