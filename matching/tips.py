"""Generate human-readable tips from deterministic scoring results.

Adopts the reference repo (ai-resume-analyzer) pattern of structured feedback:
each dimension (ATS, Tone & Style, Content, Structure, Skills) carries a score
and a list of tips, where each tip is:
    { type: "good" | "improve", tip: <short title>, explanation: <detail> }

All tips here are derived from our existing deterministic pipeline — deal-breaker
results, skill-match gaps, experience years, and TF-IDF keyword overlap. No LLM,
no cloud dependency. This brings explainable, per-dimension feedback to our
matching engine, matching the UX the reference repo's Summary/Details components
provided in the browser.
"""
from __future__ import annotations

from typing import Any

from .feedback_schema import DIMENSION_LABELS, make_tip

# Score thresholds (0–1) that map to tip types
_HIGH = 0.70
_MID = 0.45


def generate_tips(
    *,
    profile: dict[str, Any],
    job: dict[str, Any],
    component_scores: dict[str, float],
    candidate_years: float | None = None,
    profile_skill_names: set[str] | None = None,
    blocked: bool = False,
    block_reason: str | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Generate categorized tips for each rubric dimension.

    Derives tips from the same data that powers score_one_job():
    - deal-breaker results (ATS dimension)
    - skill coverage (Skills dimension)
    - experience years vs. requirement (Content dimension)
    - preferred-skill overlap (Tone & Style dimension)
    - keyword overlap (Structure dimension)

    Args:
        profile: personal profile dict.
        job: job dict.
        component_scores: from score_one_job() — required_skills, experience,
            preferred, keyword_tfidf (all 0–1).
        candidate_years: precomputed years of experience (lazy-computed if None).
        profile_skill_names: precomputed lowercased skill names (lazy if None).
        blocked: whether a deal-breaker fired.
        block_reason: the deal-breaker reason string.

    Returns:
        Dict mapping dimension key → list of tip dicts.
    """
    if candidate_years is None:
        from .scorer import _calculate_years_experience
        candidate_years = _calculate_years_experience(profile)
    if profile_skill_names is None:
        profile_skill_names = {
            s["name"].lower() for s in profile.get("skills", []) if "name" in s
        }

    required = {s.lower() for s in job.get("required_skills", [])}
    preferred = {s.lower() for s in job.get("preferred_skills", [])}
    req_years = job.get("min_years_experience", 0)

    # --- ATS dimension ---
    ats_tips: list[dict[str, str]] = []
    if blocked:
        ats_tips.append(make_tip(
            "Deal-breaker triggered",
            block_reason or "This job is blocked by your stated deal-breakers.",
            "improve",
        ))
    if component_scores.get("keyword_tfidf", 0) < _MID:
        missing_kw = _find_low_keyword_overlap(profile, job, profile_skill_names)
        if missing_kw:
            ats_tips.append(make_tip(
                "Low keyword overlap",
                f"Your profile shares few keywords with this posting "
                f"({', '.join(missing_kw[:5])}). Add relevant terminology from the "
                f"posting to your experience bullets.",
                "improve",
            ))
    if component_scores.get("keyword_tfidf", 0) > _HIGH:
        ats_tips.append(make_tip(
            "Strong keyword alignment",
            "Your skills and the job description share strong topical overlap — "
            "ATS keyword scanners will likely parse this favorably.",
            "good",
        ))

    # --- Skills dimension (required skills coverage) ---
    skills_tips: list[dict[str, str]] = []
    req_score = component_scores.get("required_skills", 0.0)
    if required:
        matched = required & profile_skill_names
        missing = required - profile_skill_names
        if req_score >= _HIGH:
            skills_tips.append(make_tip(
                "All required skills covered",
                f"Your profile covers every required skill: "
                f"{', '.join(sorted(matched))}.",
                "good",
            ))
        elif missing:
            skills_tips.append(make_tip(
                "Missing required skills",
                f"You lack {len(missing)} required skill(s): "
                f"{', '.join(sorted(missing))}. Consider upskilling or "
                f"reframing adjacent experience.",
                "improve",
            ))
        elif req_score < _HIGH:
            skills_tips.append(make_tip(
                "Partial skill coverage",
                "Some required skills are only partially matched by your profile.",
                "improve",
            ))

    # --- Content dimension (experience match) ---
    content_tips: list[dict[str, str]] = []
    exp_score = component_scores.get("experience", 0.0)
    if req_years and req_years > 0:
        if candidate_years is None or candidate_years == 0:
            content_tips.append(make_tip(
                "Experience not quantified",
                "Years of experience could not be extracted from your profile "
                "— add date ranges to your experience entries so this can match "
                "against job requirements.",
                "improve",
            ))
        elif candidate_years >= req_years:
            excess = candidate_years - req_years
            if excess > 3:
                content_tips.append(make_tip(
                    "Over-qualified",
                    f"You have {candidate_years:g} years vs. {req_years} required. "
                    f"Over-qualification may raise flight-risk concerns; address this "
                    f"proactively in your cover letter.",
                    "improve",
                ))
            else:
                content_tips.append(make_tip(
                    "Experience exceeds requirement",
                    f"You have {candidate_years:g} years vs. {req_years} required.",
                    "good",
                ))
        else:
            content_tips.append(make_tip(
                "Below required experience",
                f"You have {candidate_years:g} years vs. {req_years} required. "
                f"Consider reframing adjacent or transferable experience.",
                "improve",
            ))

    # --- Tone & Style dimension (preferred skills) ---
    tone_tips: list[dict[str, str]] = []
    pref_score = component_scores.get("preferred", 0.0)
    if preferred:
        matched_pref = preferred & profile_skill_names
        missing_pref = preferred - profile_skill_names
        if pref_score >= _HIGH and len(matched_pref) >= len(preferred) * 0.8:
            tone_tips.append(make_tip(
                "Strong preferred-skill alignment",
                f"You cover most preferred skills: {', '.join(sorted(matched_pref))}.",
                "good",
            ))
        elif missing_pref:
            tone_tips.append(make_tip(
                "Some preferred skills missing",
                f"Nice-to-haves you lack: {', '.join(sorted(missing_pref)[:5])}. "
                f"These are not hard requirements but strengthen your application.",
                "improve",
            ))

    # --- Structure dimension (keyword / TF-IDF overlap) ---
    struct_tips: list[dict[str, str]] = []
    kw_score = component_scores.get("keyword_tfidf", 0.0)
    if kw_score < _MID:
        struct_tips.append(make_tip(
            "Low resume-job keyword alignment",
            "Your resume language differs significantly from the job posting. "
            "Incorporate the posting's terminology into your experience bullets "
            "and summary.",
            "improve",
        ))
    elif kw_score >= _HIGH:
        struct_tips.append(make_tip(
            "Strong terminology alignment",
            "Your resume language closely matches the job posting's vocabulary.",
            "good",
        ))

    return {
        "ats": ats_tips,
        "skills": skills_tips,
        "content": content_tips,
        "tone_and_style": tone_tips,
        "structure": struct_tips,
    }


def _find_low_keyword_overlap(
    profile: dict[str, Any],
    job: dict[str, Any],
    profile_skill_names: set[str],
) -> list[str]:
    """Return required/preferred skills from the job not found in the profile."""
    job_skills = set()
    for s in job.get("required_skills", []) + job.get("preferred_skills", []):
        job_skills.add(s.lower())
    return sorted(job_skills - profile_skill_names)
