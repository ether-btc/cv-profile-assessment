"""Structured-output prompt builder — ported from the reference repo's
constants/index.ts (AIResponseFormat + prepareInstructions).

adrianhajdin/ai-resume-analyzer asks an LLM to invent the entire Feedback
object from the raw resume: every score, every tip. That is the part worth
copying (a JSON schema embedded in the prompt, no function-calling API needed)
and the part worth improving on.

We already compute the scores deterministically and reproducibly on-device.
So this module inverts the reference's arrangement: the numbers are supplied
*to* the model as established facts, and the model is asked only for the thing
it is genuinely better at — prose. That keeps the engine's core property
intact (scores are reproducible and explainable, never hallucinated) while
still allowing an optional narrative pass.

Nothing here calls an LLM or imports a client. It builds a string. The engine
remains fully functional, and fully offline, without ever using this module.
"""
from __future__ import annotations

import json
from typing import Any

# The response contract, embedded in the prompt. Mirrors the reference repo's
# AIResponseFormat, minus every field we already know: no scores are requested,
# because supplying them is the whole point.
NARRATIVE_RESPONSE_FORMAT = """interface Narrative {
  summary: string;          // 2-3 sentences, addressed to the candidate as "you"
  strengths: string[];      // 2-4 concrete points, each grounded in the data given
  gaps: string[];           // 2-4 honest gaps; [] if there are genuinely none
  suggestions: string[];    // 2-4 specific, actionable next steps
}"""

_RUBRIC_ORDER = ("ATS", "skills", "content", "toneAndStyle", "structure")

_DIMENSION_MEANING = {
    "ATS": "how safely an applicant tracking system can parse the CV document",
    "skills": "coverage of the role's required skills",
    "content": "depth and relevance of experience",
    "toneAndStyle": "coverage of preferred/nice-to-have skills",
    "structure": "how closely the CV's vocabulary tracks the posting",
}


def prepare_narrative_prompt(
    *,
    job_title: str,
    job_description: str = "",
    feedback: dict[str, Any],
    company: str = "",
    language: str = "en",
) -> str:
    """Build a prompt asking an LLM for prose commentary on an existing score.

    The reference repo's prepareInstructions() sent the resume and asked the
    model to produce scores plus tips. We send the *scores we already computed*
    and ask only for narrative. The model cannot alter a score, so the
    deterministic engine stays authoritative.

    Args:
        job_title: Target role title.
        job_description: Posting text; may be empty.
        feedback: A Feedback dict from build_feedback_dict().
        company: Optional company name.
        language: "de" requests German prose, anything else English.

    Returns:
        A prompt string. No LLM call is made — the caller owns that decision.
    """
    lines: list[str] = []

    verdict = feedback.get("verdict", "")
    overall = feedback.get("overallScore", 0)

    lines.append(
        "You are an experienced career advisor. A deterministic, rule-based "
        "matching engine has already scored this candidate against the role "
        "below. The scores are established facts, computed on-device from the "
        "candidate's parsed CV."
    )
    lines.append("")
    lines.append("ROLE")
    lines.append(f"  Title: {job_title or 'Unknown'}")
    if company:
        lines.append(f"  Company: {company}")
    if job_description:
        desc = job_description.strip()
        if len(desc) > 1500:
            desc = desc[:1500].rstrip() + " [...]"
        lines.append(f"  Description: {desc}")
    lines.append("")

    lines.append("ENGINE RESULTS (authoritative — do not recompute or dispute)")
    lines.append(f"  Overall: {overall}/100" + (f" ({verdict})" if verdict else ""))
    for key in _RUBRIC_ORDER:
        dim = feedback.get(key)
        if not isinstance(dim, dict):
            continue
        meaning = _DIMENSION_MEANING.get(key, "")
        lines.append(f"  {key}: {dim.get('score', 0)}/100 — {meaning}")
        for tip in dim.get("tips", []):
            marker = "+" if tip.get("type") == "good" else "-"
            lines.append(f"      {marker} {tip.get('tip', '')}")
            if tip.get("explanation"):
                lines.append(f"        {tip['explanation']}")

    if feedback.get("blocked"):
        lines.append(
            f"  BLOCKED: {feedback.get('block_reason', 'a deal-breaker matched')}"
        )
    for gate in ("eligibility_gate", "language_gate"):
        g = feedback.get(gate)
        if isinstance(g, dict) and g.get("verdict") != "PASS":
            lines.append(f"  {gate}: {g.get('verdict')} — {g.get('note', '')}")
    lines.append("")

    lines.append("TASK")
    lines.append(
        "  Write the candidate-facing narrative for these results. Ground every "
        "statement in the findings above; introduce no skill, employer, or "
        "achievement that does not appear there. If the evidence is thin, say so "
        "plainly rather than padding. Do not restate the numbers — interpret them."
    )
    if language == "de":
        lines.append(
            "  Write in German. Use natural, professional phrasing and address "
            "the candidate with the formal 'Sie'."
        )
    lines.append("")
    lines.append("  Return one JSON object in exactly this shape, and nothing else:")
    lines.append(f"  {NARRATIVE_RESPONSE_FORMAT}")
    lines.append("  No markdown, no code fences, no commentary outside the JSON.")

    return "\n".join(lines)


def parse_narrative_response(raw: str) -> dict[str, Any]:
    """Parse an LLM narrative response defensively.

    The reference repo does `JSON.parse(feedback.message.content)` straight on
    the model output, which throws on the very common case of a fenced code
    block. We strip fences, isolate the outermost JSON object, coerce every
    field to its expected type, and never raise.

    Returns:
        {
          "narrative": {summary, strengths[], gaps[], suggestions[]} | None,
          "error": str | None,
        }
    """
    if not raw or not raw.strip():
        return {"narrative": None, "error": "empty response"}

    text = raw.strip()

    # Strip ```json ... ``` / ``` ... ``` fences.
    if text.startswith("```"):
        newline = text.find("\n")
        if newline != -1:
            text = text[newline + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
        text = text.strip()

    # Isolate the outermost object, tolerating prose on either side.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {"narrative": None, "error": "no JSON object found in response"}
    text = text[start:end + 1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return {"narrative": None, "error": f"invalid JSON: {e}"}

    if not isinstance(data, dict):
        return {"narrative": None, "error": "response JSON is not an object"}

    def _as_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [
                str(v).strip()
                for v in value
                if v is not None and str(v).strip()
            ]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    _summary = data.get("summary")
    narrative = {
        "summary": "" if _summary is None else str(_summary).strip(),
        "strengths": _as_list(data.get("strengths")),
        "gaps": _as_list(data.get("gaps")),
        "suggestions": _as_list(data.get("suggestions")),
    }

    if not narrative["summary"] and not narrative["strengths"]:
        return {"narrative": None, "error": "response contained no usable narrative"}

    return {"narrative": narrative, "error": None}


__all__ = [
    "NARRATIVE_RESPONSE_FORMAT",
    "prepare_narrative_prompt",
    "parse_narrative_response",
]
