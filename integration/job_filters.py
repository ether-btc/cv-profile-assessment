"""Job-fit filters — bias-aware filtering before matching.

User-tunable knobs to either drop jobs that don't fit (blocklist) or keep
them visible with a flag so the user can decide (flaglist). Both are
substring-matched against the combined job text (title + description),
case-insensitive.

Filter signature returns one of three decisions:
  ("include", [])         → matches the user's preferences
  ("flag",   [...])       → borderline; kept, with reasons
  ("exclude", [...])      → does not match; kept out of ranking

Designed to be pure functions (no DB, no IO) so tests can drive every
edge case in <50ms.

Bias declaration (2026-06-29, user-driven):

  Excluded: roles whose primary task is B2B cold outreach / "hunting"
  new customers. Includes commission-driven fee structures that turn the
  role into a sales-hunter slot.

  Flagged: roles where some acquisition/new-customer activity exists
  alongside non-sales tasks (e.g. "Kundenbetreuer mit Akquise-Anteil")
  — kept in ranking so user can decide.
"""

from __future__ import annotations

from typing import Iterable


# Words/phrases that, when present in title OR description, exclude the job.
# Substring match — kept conservative on purpose (no regex). Lower-cased once
# at module load (see _BLOCKLIST_LOWER below) so we don't re-lower per call.
DEFAULT_BLOCKLIST_KEYWORDS: list[str] = [
    # German / Austrian cold-outreach vocabulary
    "akquise",
    "akquisiteur",
    "neukundengewinnung",
    "neukundenakquise",
    "kaltakquise",
    "hunter",
    "hunting",
    "vertriebsaußendienst",
    "außendienst",
    "tür-zu-tür",
    # Role titles that are pure acquisition
    "sales hunter",
    "closer",
    "commission only",
    "reine provision",
    # Aggressive sales KPIs
    "100% provision",
    "ausschließlich provision",
]


# Words/phrases that, when present, mark the job as borderline. Job stays
# in the ranking but is annotated with the matched terms. Lower-cased once
# (see _FLAGLIST_LOWER).
DEFAULT_FLAG_KEYWORDS: list[str] = [
    # Acquisition as PART of role (not whole role)
    "akquiseanteil",
    "neukunden",
    "akquise-tätigkeiten",
    "vertriebsunterstützung",
    # Sales-adjacent but not pure-hunter
    "sales support",
    "inside sales",
    "kundenakquise",
    # Hybrid roles
    "neukund:innen",
]


# Module-level pre-lowered keyword sets. classify_job() lower-cases the
# haystack (job text) once per call; matching against pre-lowered keywords
# keeps the substring check O(N) without re-lowering per keyword.
_BLOCKLIST_LOWER: frozenset[str] = frozenset(k.lower() for k in DEFAULT_BLOCKLIST_KEYWORDS)
_FLAGLIST_LOWER: frozenset[str] = frozenset(k.lower() for k in DEFAULT_FLAG_KEYWORDS)


def _matches_any(text: str, keywords_lower: frozenset[str] | Iterable[str]) -> list[str]:
    """Return subset of keywords that appear in text (case-insensitive).

    `keywords_lower` SHOULD be pre-lowered for hot-path performance. If you
    pass a mixed-case iterable, we lower each on the fly (slower, but safe).
    Returns the matched keywords in their original-case (per the original
    public list), not the lowered form — that way end-users see "Akquise"
    in filter reasons, not "akquise".

    To honour that contract, we keep the mapping internally.
    """
    # Use pre-lowered search set; map back to original-case for reporting.
    if isinstance(keywords_lower, frozenset):
        # Caller passes the pre-lowered frozenset; route via the module list
        # for round-trip back to original-case. This branch is the hot path.
        search_set = keywords_lower
        if keywords_lower is _BLOCKLIST_LOWER:
            lookup = {k.lower(): k for k in DEFAULT_BLOCKLIST_KEYWORDS}
        elif keywords_lower is _FLAGLIST_LOWER:
            lookup = {k.lower(): k for k in DEFAULT_FLAG_KEYWORDS}
        else:
            lookup = {k: k for k in keywords_lower}
    else:
        # Slow path (ad-hoc strings). Lower them here.
        lowered = [k.lower() for k in keywords_lower]
        search_set = set(lowered)
        lookup = dict(zip(lowered, [k for k in keywords_lower]))
    haystack = text.lower()
    return [lookup[k] for k in search_set if k in haystack]  # noqa: E272 (preserving original case)


def combined_text(job: dict) -> str:
    """Concatenate fields a job exposes, for keyword matching.

    Includes title, description, requirements. Does NOT include
    required_skills/preferred_skills (skills_json is technical content,
    not bias-bearing vocabulary).

    Empty fields are stripped from the join so a fully-empty job dict
    yields "" (not newlines). This keeps keyword matches from triggering
    on whitespace artefacts.
    """
    parts: list[str] = []
    for k in ("title", "description", "location"):
        v = job.get(k) or ""
        if v:
            parts.append(v if isinstance(v, str) else str(v))
    # Requirements can be list[str] OR list[dict]. For dict-shaped entries
    # we extract the first non-empty text-bearing key (text/name/requirement/
    # value). Raw repr() of a dict would emit the curly-brace literal into
    # the searchable text and could trigger spurious keyword matches; we
    # therefore never call str(dict).
    #
    # Multiple text-bearing keys in one dict are still combined by " | "
    # joining — a job row commonly bundles {name, text} for the same item,
    # and dropping one would underrepresent the search surface.
    _REQ_DICT_KEYS = ("text", "requirement", "value", "name")
    reqs = job.get("requirements") or []
    for r in reqs:
        if isinstance(r, str):
            stripped = r.strip() if r else ""
            if stripped:
                parts.append(r)
        elif isinstance(r, dict):
            extracted = [
                str(r[k]).strip()
                for k in _REQ_DICT_KEYS
                if r.get(k) and isinstance(r.get(k), (str, int, float))
                and str(r[k]).strip()
            ]
            if extracted:
                parts.append(" | ".join(extracted))
        elif isinstance(r, (int, float)) and r:
            # Plain numeric entry (rare but valid in some adapter formats)
            parts.append(str(r))
    return "\n".join(parts)


def classify_job(
    job: dict,
    blocklist: list[str] | None = None,
    flaglist: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Classify a job dict against blocklist / flaglist keyword sets.

    Args:
        job: A cv-profile-assessment job dict (see scout_adapter.adapt_austria_jobs_row).
             Used fields: title, description, location, requirements.
        blocklist: Override blocklist (substring keywords). None → use defaults.
        flaglist: Override flaglist (substring keywords). None → use defaults.

    Returns:
        Tuple (decision, matched_keywords).
            decision ∈ {"include", "flag", "exclude"}.
            matched_keywords: list of matched keywords (reasons for the decision).
    """
    blocklist = blocklist if blocklist is not None else DEFAULT_BLOCKLIST_KEYWORDS
    flaglist = flaglist if flaglist is not None else DEFAULT_FLAG_KEYWORDS

    text = combined_text(job)

    excluded = _matches_any(text, blocklist)
    if excluded:
        return ("exclude", excluded)

    flagged = _matches_any(text, flaglist)
    if flagged:
        return ("flag", flagged)

    return ("include", [])


def filter_jobs(
    jobs: list[dict],
    blocklist: list[str] | None = None,
    flaglist: list[str] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Partition a list of jobs into (included, flagged, excluded).

    Each returned dict retains its original job fields, plus a
    `_filter` annotation dict with decision + matched keywords.

    Args:
        jobs: List of job dicts (cv-profile-assessment schema).
        blocklist: Override blocklist.
        flaglist: Override flaglist.

    Returns:
        (included_jobs, flagged_jobs, excluded_jobs) — three lists
        partitioning the input.
    """
    included, flagged, excluded = [], [], []

    for job in jobs:
        decision, reasons = classify_job(job, blocklist, flaglist)
        annotated = dict(job)
        annotated["_filter"] = {"decision": decision, "reasons": reasons}
        if decision == "include":
            included.append(annotated)
        elif decision == "flag":
            flagged.append(annotated)
        else:
            excluded.append(annotated)

    return included, flagged, excluded
