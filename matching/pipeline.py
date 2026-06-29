"""Shared scoring pipeline — single source of truth for job-candidate matching.

Both CLIs (scripts/match_jobs.py and scripts/match_scout_jobs.py) call this
to avoid duplicating the scoring logic. The result dict includes optional
provenance fields (url, ats) pulled from job._source when present.

Supports both dict-based and dataclass-based inputs (backward compatible).
"""

from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Set, Union

# Make cv_profile_assessment types importable
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if TYPE_CHECKING:
    from cv_profile_assessment.types import PersonalProfile, Job

from .deal_breakers import check_deal_breakers  # noqa: E402
from .scorer import (  # noqa: E402
    DEFAULT_WEIGHTS,
    _calculate_years_experience,
    compute_overall_score,
    score_experience,
    score_preferred,
    score_required_skills,
)
from .tfidf_matcher import compute_tfidf_similarity  # noqa: E402

# Runtime import (after sys.path modification)
from cv_profile_assessment.types import PersonalProfile, Job  # noqa: E402


def score_one_job(
    profile: Union[dict, PersonalProfile],
    job: Union[dict, Job],
    candidate_years: Optional[float] = None,
    profile_skill_names: Optional[Set[str]] = None,
) -> dict:
    """Score one job against a profile. Returns result dict.

    This is the single source of truth for the scoring pipeline:
      deal-breaker filter → 4 component scores → weighted combination.

    Args:
        profile: Personal profile dict or PersonalProfile dataclass.
        job: Job dict or Job dataclass.
        candidate_years: Precomputed years of experience. Lazy-computed
            if None. For batch use, pass from caller to avoid O(n) recompute.
        profile_skill_names: Precomputed lowercased skill name set.
            Lazy-computed if None.

    Returns:
        Dict with: job_title, company, location, remote, overall_score,
        blocked, component_scores, weights, and optional url/ats/block_reason.
    """
    # Convert dataclasses to dicts if needed
    if isinstance(profile, PersonalProfile):
        profile = profile.to_dict()
    if isinstance(job, Job):
        job = job.to_dict()
    
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


def score_jobs_parallel(
    profile: Union[dict, PersonalProfile],
    jobs: list[Union[dict, Job]],
    max_workers: Optional[int] = None,
) -> list[dict]:
    """Score multiple jobs in parallel using ProcessPoolExecutor.
    
    Best for 100+ jobs (austria-job-scout scale). For small batches (<50),
    the sequential score_many_jobs() is faster due to pool overhead.
    
    Args:
        profile: Personal profile (dict or dataclass).
        jobs: List of jobs (dicts or dataclasses).
        max_workers: Number of worker processes (default: CPU count).
        
    Returns:
        List of result dicts, sorted by overall_score descending.
    """
    from multiprocessing import cpu_count
    
    if max_workers is None:
        max_workers = cpu_count()
    
    # Precompute profile-only values once
    if isinstance(profile, PersonalProfile):
        profile_dict = profile.to_dict()
    else:
        profile_dict = profile
    
    candidate_years = _calculate_years_experience(profile_dict)
    profile_skill_names = {
        s["name"].lower() for s in profile_dict.get("skills", []) if "name" in s
    }
    
    # Parallel execution using module-level _score_job_worker
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit jobs with precomputed profile values
        futures = [
            executor.submit(
                _score_job_worker,
                profile_dict,
                job,
                candidate_years,
                profile_skill_names,
            )
            for job in jobs
        ]
        results = [f.result() for f in futures]
    
    # Sort: blocked jobs go last, then by score descending
    results.sort(key=lambda r: (r.get("blocked", False), -r["overall_score"]))
    return results


def _score_job_worker(
    profile_dict: dict,
    job: Union[dict, Job],
    candidate_years: float,
    profile_skill_names: Set[str],
) -> dict:
    """Worker function for parallel job scoring (must be module-level for pickling).
    
    This is a thin wrapper around score_one_job that accepts precomputed values.
    """
    # Convert Job dataclass to dict if needed
    if hasattr(job, 'to_dict'):
        job = job.to_dict()
    
    return score_one_job(
        profile_dict,
        job,
        candidate_years=candidate_years,
        profile_skill_names=profile_skill_names,
    )


def score_many_jobs(
    profile: Union[dict, PersonalProfile],
    jobs: list[Union[dict, Job]],
) -> list[dict]:
    """Score multiple jobs sequentially (optimized batch mode).
    
    Better than parallel for <100 jobs due to no process spawn overhead.
    Precomputes profile-only values once.
    
    Args:
        profile: Personal profile (dict or dataclass).
        jobs: List of jobs (dicts or dataclasses).
        
    Returns:
        List of result dicts, sorted by overall_score descending.
    """
    # Convert profile once
    if isinstance(profile, PersonalProfile):
        profile = profile.to_dict()
    
    # Precompute profile-only values once (not per job)
    candidate_years = _calculate_years_experience(profile)
    profile_skill_names = {
        s["name"].lower() for s in profile.get("skills", []) if "name" in s
    }
    
    # Score all jobs
    results = [
        score_one_job(
            profile, job,
            candidate_years=candidate_years,
            profile_skill_names=profile_skill_names,
        )
        for job in jobs
    ]
    
    # Sort: blocked jobs go last, then by score descending
    results.sort(key=lambda r: (r.get("blocked", False), -r["overall_score"]))
    return results
