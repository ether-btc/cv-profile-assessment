"""Five-dimension feedback rubric — mirrors the structured-output pattern from
adrianhajdin/ai-resume-analyzer's constants/index.ts (AIResponseFormat +
prepareInstructions).

Adapted for our own stack: the reference repo embedded this schema in an LLM
prompt to get structured JSON back. We use it as a **data contract** for our
explanatory scoring pipeline — the dimensions (ATS, Tone & Style, Content,
Structure, Skills) come from the reference's rubric, but all scores are derived
from our existing deterministic scorer (deal-breakers, skill matching,
TF-IDF cosine), with zero LLM dependency.

This gives our users the same actionable breakdown the reference repo's UI
rendered — per-dimension score + categorized tips — without requiring a
cloud LLM call or client-side browser dependencies.
"""
from __future__ import annotations

from typing import Any

from .scorer import (
    DEFAULT_WEIGHTS,
    PROFICIENCY_WEIGHT,
)

# ---------------------------------------------------------------------------
# Dimension definitions
# ---------------------------------------------------------------------------

_DIMENSIONS = ["ats", "tone_and_style", "content", "structure", "skills"]

# Maps our internal scoring keys to the reference rubric's dimension names.
# The reference repo's Feedback interface uses these exact five categories.
DIMENSION_LABELS: dict[str, str] = {
    "ats": "ATS",
    "tone_and_style": "Tone & Style",
    "content": "Content",
    "structure": "Structure",
    "skills": "Skills",
}

# Weights for the overall score. The reference repo did not publish explicit
# weights (it delegated to an LLM), but our deterministic engine already has a
# 4-component weighted model (REQUIRED: 0.45, experience: 0.25, preferred: 0.18,
# keyword: 0.12). We map those onto the five-dimension rubric so the
# dimensions carry the same relative importance.
DIMENSION_WEIGHTS: dict[str, float] = {
    "skills": DEFAULT_WEIGHTS["required_skills"],       # 0.45
    "content": DEFAULT_WEIGHTS["experience"],           # 0.25
    "tone_and_style": DEFAULT_WEIGHTS["preferred"],    # 0.18
    "structure": 0.07,  # split the remaining 0.12 evenly
    "ats": 0.05,        # see note below
    "keyword_tfidf": DEFAULT_WEIGHTS["keyword"],       # 0.12 (kept as extra detail)
}

# Default scoring weights keyed by dimension for compute_overall_score compat.
_RUBRIC_WEIGHTS = {
    "required_skills": DEFAULT_WEIGHTS["required_skills"],
    "experience": DEFAULT_WEIGHTS["experience"],
    "preferred": DEFAULT_WEIGHTS["preferred"],
    "keyword": DEFAULT_WEIGHTS["keyword"],
}


# ---------------------------------------------------------------------------
# Tip helpers
# ---------------------------------------------------------------------------

def make_tip(
    tip: str,
    explanation: str,
    tip_type: str = "improve",
) -> dict[str, str]:
    """Build a single tip dict matching the reference repo's shape:
    { type: "good"|"improve", tip: <short title>, explanation: <detail> }.
    """
    assert tip_type in ("good", "improve"), f"tip_type must be 'good' or 'improve', got {tip_type!r}"
    return {"type": tip_type, "tip": tip, "explanation": explanation}


def _empty_dimension() -> dict[str, Any]:
    return {"score": 0, "tips": []}


# ---------------------------------------------------------------------------
# Feedback assembly
# ---------------------------------------------------------------------------

def build_feedback_dict(
    *,
    component_scores: dict[str, float],
    tips_by_dimension: dict[str, list[dict[str, str]]],
    blocked: bool = False,
    block_reason: str | None = None,
    overall_score: float | None = None,
    gates: dict[str, dict[str, str]] | None = None,
    verdict: str | None = None,
) -> dict[str, Any]:
    """Assemble a Feedback-shaped dict from our pipeline outputs.

    Mirrors the reference repo's ``Feedback`` interface (types/index.d.ts):
    overallScore, ATS{score,tips}, toneAndStyle{score,tips},
    content{score,tips}, structure{score,tips}, skills{score,tips}.

    Args:
        component_scores: raw scores from score_one_job(), e.g.
            {"required_skills": 0.9, "experience": 0.8, "preferred": 0.5,
             "keyword_tfidf": 0.3}.  Values are 0–1; we scale to 0–100.
        tips_by_dimension: mapping from dimension key to a list of
            tip dicts (each from make_tip).  Only the dimensions present
            need entries.
        blocked: if True, the job failed a deal-breaker filter.
        block_reason: human-readable reason when blocked.
        overall_score: pre-computed 0–1 score (from compute_overall_score);
            if None, we compute it from component_scores + DIMENSION_WEIGHTS.

    Returns:
        A dict matching the reference repo's Feedback interface, scaled
        to 0–100 integers for display consistency.
    """
    # Scale 0–1 component scores to 0–100
    _scale = lambda v: round(v * 100)

    # Map component scores → rubric dimensions
    # Required skills (0.45) → Skills dimension
    # Experience (0.25)   → Content dimension
    # Preferred (0.18)    → Tone & Style dimension
    # Keyword (0.12)      → split: Structure gets a share, ATS gets keyword overlap
    skills_score = _scale(component_scores.get("required_skills", 0.0))
    content_score = _scale(component_scores.get("experience", 0.0))
    tone_score = _scale(component_scores.get("preferred", 0.0))
    keyword_score = _scale(component_scores.get("keyword_tfidf", 0.0))

    # Structure: heuristic blend of keyword density + experience completeness
    # If experience scored well and keyword overlap is decent, structure is solid.
    structure_score = _scale(
        min(
            component_scores.get("experience", 0.0) * 0.5
            + component_scores.get("keyword_tfidf", 0.0) * 0.5,
            1.0,
        )
    )

    # ATS: keyword coverage is the closest proxy to ATS-friendliness.
    # Our deal_breakers already act as an ATS-style filter; if blocked,
    # ATS score reflects the blocker.
    ats_score = keyword_score
    if blocked:
        ats_score = max(0, keyword_score - 20)

    # Overall score
    if overall_score is None:
        overall: float = 0.0
        if not blocked:
            total_w = 0.0
            for dim, weight in DIMENSION_WEIGHTS.items():
                if dim == "keyword_tfidf":
                    continue
                sc = component_scores.get(
                    {
                        "skills": "required_skills",
                        "content": "experience",
                        "tone_and_style": "preferred",
                        "structure": None,  # computed above
                        "ats": None,        # computed above
                    }.get(dim, dim),
                    0.0,
                )
                if sc is None:
                    # computed dimension
                    sc = {
                        "structure": structure_score / 100.0,
                        "ats": ats_score / 100.0,
                    }.get(dim, 0.0)
                overall += sc * weight
                total_w += weight
            overall = min(overall / max(total_w, 0.001), 1.0)
    else:
        overall = float(overall_score)

    feedback = {
        "overallScore": round(overall * 100) if overall is not None else 0,
        "ATS": {
            "score": max(0, min(100, ats_score)),
            "tips": tips_by_dimension.get("ats", []),
        },
        "toneAndStyle": {
            "score": max(0, min(100, tone_score)),
            "tips": tips_by_dimension.get("tone_and_style", []),
        },
        "content": {
            "score": max(0, min(100, content_score)),
            "tips": tips_by_dimension.get("content", []),
        },
        "structure": {
            "score": max(0, min(100, structure_score)),
            "tips": tips_by_dimension.get("structure", []),
        },
        "skills": {
            "score": max(0, min(100, skills_score)),
            "tips": tips_by_dimension.get("skills", []),
        },
    }
    if verdict is not None:
        feedback["verdict"] = verdict
    if gates:
        for gate_name, gate_val in gates.items():
            feedback[gate_name] = {
                "verdict": gate_val.get("verdict", "PASS"),
                "note": gate_val.get("note", ""),
            }
    if blocked:
        feedback["blocked"] = True
        feedback["block_reason"] = block_reason or ""
    return feedback


def feedback_to_text(feedback: dict[str, Any]) -> str:
    """Render a Feedback dict as human-readable text (for CLI / report output).

    Mirrors how the reference repo's Summary/Details components would have
    displayed it in the browser — a score gauge per dimension plus tip lists.
    """
    lines = [f"Overall Score: {feedback['overallScore']}/100"]
    if feedback.get("blocked"):
        lines.append(f"  [BLOCKED] {feedback.get('block_reason', 'Deal-breaker triggered')}")
        lines.append("  No further scoring — this job is excluded by your filters.")
        return "\n".join(lines)

    for key in _DIMENSIONS:
        # The feedback dict keys are capitalized (e.g. "ATS", "Skills"),
        # while _DIMENSIONS holds lowercase ids. Resolve the actual key.
        actual_key = next((k for k in feedback if k.lower() == key), key)
        if actual_key not in feedback:
            continue
        dim = feedback[actual_key]
        label = DIMENSION_LABELS[key]
        lines.append(f"\n{label}: {dim['score']}/100")
        for tip in dim["tips"]:
            icon = "✓" if tip["type"] == "good" else "⚠"
            lines.append(f"  {icon} {tip['tip']}")
            if tip.get("explanation"):
                lines.append(f"    → {tip['explanation']}")
    return "\n".join(lines)
