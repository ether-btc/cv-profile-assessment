"""Eligibility & Language gates — pre-score hard filters.

Ported from MadsLorentzen/ai-job-search's 04-job-evaluation.md (the
ai-job-search project). In that framework, two gates run *before* any
numeric scoring and can hard-stop a job:

  * Eligibility Gate — citizenship / work-rights / security-clearance.
  * Language Gate     — required posting language vs. candidate's declared
                        languages.

We adopt the same *concept* but keep it deterministic and optional:
each gate returns a verdict of "PASS" | "FAIL" | "FLAG" plus a human
note. "FAIL" is treated like a deal-breaker (excludes the job); "FLAG"
is surfaced but does not exclude; "PASS" is silent. Gates only fire when
the relevant fields are actually present, so the Pi-local, no-LLM,
fully-reproducible property of the engine is preserved.

Thresholds/keywords are intentionally conservative and easy to extend.
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

# Verdict type alias for clarity at call sites.
Verdict = str  # one of "PASS" | "FAIL" | "FLAG"
GateResult = Tuple[Verdict, str]  # (verdict, note)

# --- Eligibility gate patterns (lowercase-contains, word-boundary-ish) ---
# Phrasings that *require* a specific work status → hard stop if the
# candidate's profile does not evidence it.
_ELIGIBILITY_REQUIRED = [
    r"citizen(ship)?\b",
    r"permanent resident",
    r"\bpr\b",
    r"full working rights",
    r"security clearance",
    r"must be authorized to work in",
    r"legally entitled to work in",
]

# Phrasings that *accept* non-citizens → explicit PASS.
_ELIGIBILITY_ACCEPTED = [
    r"international applicants? (are )?welcome",
    r"visa holders? considered",
    r"we sponsor",
    r"sponsorship available",
    r"\brelocation (support|assistance|package)\b",
]

# --- Language gate ---
# Simple level ordering for "is the posting's bar higher than declared?".
_LEVEL_RANK = {
    "native": 5, "c2": 5, "fluent": 4, "c1": 4, "business": 4,
    "b2": 3, "intermediate": 3, "conversational": 2, "b1": 2,
    "basic": 1, "a2": 1, "beginner": 1, "a1": 1,
}


def _norm(text: str) -> str:
    return (text or "").lower()


def check_eligibility_gate(profile: Dict, job: Dict) -> GateResult:
    """Eligibility / work-rights gate.

    Returns ("FAIL", note) when the posting appears to *require* a status
    the candidate has not declared; ("PASS", note) when it explicitly
    welcomes internationals/sponsors; ("PASS", "") when silent or no
    requirement is detectable (silence is *not* treated as permission here
    — we simply don't block on undetected signals, but note it).
    """
    text = _norm(" ".join([
        job.get("title", ""),
        job.get("description", ""),
    ]))

    if not text:
        return "PASS", ""

    for pat in _ELIGIBILITY_ACCEPTED:
        if re.search(pat, text):
            return "PASS", "Posting explicitly welcomes international applicants / sponsorship."

    for pat in _ELIGIBILITY_REQUIRED:
        if re.search(pat, text):
            # Required-status signal present. Does the profile evidence it?
            work_auth = profile.get("basics", {}).get("work_authorization", [])
            if isinstance(work_auth, list) and any(work_auth):
                return "PASS", "Candidate declares work authorization; eligibility satisfied."
            return (
                "FAIL",
                "Posting implies a citizenship / work-right / clearance requirement "
                "the profile does not evidence. Verify before applying.",
            )

    return "PASS", ""


def _parse_level(text: str) -> Optional[int]:
    """Extract the highest CEFR-ish level mentioned in a string."""
    text = _norm(text)
    best = None
    for token, rank in _LEVEL_RANK.items():
        if re.search(rf"\b{re.escape(token)}\b", text):
            best = max(best or 0, rank)
    return best


def check_language_gate(profile: Dict, job: Dict) -> GateResult:
    """Language requirement gate.

    Compares the languages a posting *requires* against the candidate's
    declared ``basics.languages`` table.

    Returns:
        ("FAIL", note) — required language not declared at all.
        ("FLAG", note) — declared, but the posting's bar reads higher than
                        the candidate's declared level (human decides).
        ("PASS", note) — at/under declared level, or no requirement found.
    """
    text = _norm(" ".join([
        job.get("title", ""),
        job.get("description", ""),
    ]))

    # Candidate's declared languages → {name: level_rank_or_None}
    declared: Dict[str, Optional[int]] = {}
    for lang in profile.get("basics", {}).get("languages", []) or []:
        if isinstance(lang, dict):
            name = _norm(lang.get("language", ""))
            lvl = _parse_level(lang.get("fluency", ""))
        else:
            continue
        if name:
            declared[name] = lvl

    if not declared:
        # No language data on the candidate → can't evaluate; don't block.
        return "PASS", ""

    # Find required-language signals: "required", "fluent X", "X required",
    # "must communicate in X", "native X", etc. We look for known language
    # names the posting demands.
    known_langs = [
        "german", "deutsch", "englisch", "english", "french", "französisch",
        "spanish", "spanisch", "italian", "italienisch", "polish", "polnisch",
        "russian", "russisch", "dutch", "niederländisch", "czech", "tschechisch",
    ]
    # Map German aliases to canonical english key for declared-table match.
    _alias = {
        "deutsch": "german", "englisch": "english", "französisch": "french",
        "spanisch": "spanish", "italienisch": "italian", "polnisch": "polish",
        "russisch": "russian", "niederländisch": "dutch", "tschechisch": "czech",
    }

    required_signals = []
    for kl in known_langs:
        canon = _alias.get(kl, kl)
        # Required phrasing near the language name.
        if re.search(rf"(required|must|fluent|native|communicate in|level of)\b[^\.]*\b{re.escape(kl)}\b", text) or \
           re.search(rf"\b{re.escape(kl)}\b[^\.]*\b(required|must|fluent|native|necessary)\b", text):
            required_signals.append(canon)

    if not required_signals:
        return "PASS", ""

    for req in required_signals:
        if req not in declared:
            return (
                "FAIL",
                f"Posting requires '{req}' which is not declared in the candidate's "
                f"languages table.",
            )
        # Declared — check the bar.
        posting_bar = _parse_level(text)  # best level mentioned anywhere
        declared_lvl = declared[req]
        if posting_bar is not None and declared_lvl is not None and posting_bar > declared_lvl:
            return (
                "FLAG",
                f"Posting bar for '{req}' reads higher than the declared level "
                f"({declared_lvl} vs ~{posting_bar}). Verify before applying.",
            )

    return "PASS", "All required languages are declared at or above the posting's bar."


# Convenience: run both gates, return a combined dict.
def run_gates(profile: Dict, job: Dict) -> Dict[str, Dict[str, str]]:
    """Run eligibility + language gates; return {gate_name: {verdict, note}}."""
    elig_v, elig_n = check_eligibility_gate(profile, job)
    lang_v, lang_n = check_language_gate(profile, job)
    return {
        "eligibility_gate": {"verdict": elig_v, "note": elig_n},
        "language_gate": {"verdict": lang_v, "note": lang_n},
    }


__all__ = [
    "check_eligibility_gate",
    "check_language_gate",
    "run_gates",
    "GateResult",
    "Verdict",
]
