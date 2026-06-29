"""Language detection for CV/resume text.

Lightweight heuristic-based detection using common-word frequency ratio.
No external dependency — avoids adding langdetect/langid for a 50-line module.
"""

from typing import Tuple

# High-frequency function words that are strongly language-discriminating
# (more reliable than content words for short text classification)
_MARKERS = {
    "de": frozenset({
        "und", "der", "die", "das", "von", "mit", "im", "den", "für", "auf",
        "ist", "ein", "eine", "sich", "auch", "werden", "wird", "berufserfahrung",
        "ausbildung", "kenntnisse", "sprachen", "fähigkeiten", "erfahrung",
        "tätigkeit", "verantwortlich", "projekt", "bereich", "unternehmen",
    }),
    "en": frozenset({
        "the", "and", "for", "with", "from", "this", "that", "have", "was",
        "are", "been", "experience", "education", "skills", "work", "project",
        "responsible", "management", "business", "university", "bachelor",
    }),
}


def detect_language(text: str) -> Tuple[str, float]:
    """Detect the primary language of CV text.

    Uses common-word frequency ratio — fast, dependency-free, and
    sufficient for the CV use case (documents are always DE or EN).

    Args:
        text: CV text to analyze.

    Returns:
        Tuple of (language_code, confidence).
        language_code: "de", "en", or "unknown".
        confidence: 0.0–1.0 based on word overlap with marker sets.
    """
    if not text or not text.strip():
        return "unknown", 0.0

    tokens = [t.lower().strip(".,;:!?\"'()[]/") for t in text.split()]
    if len(tokens) < 5:
        return "unknown", 0.0

    token_set = set(tokens)
    total_tokens = len(tokens)

    scores: dict = {}
    for lang, markers in _MARKERS.items():
        hits = len(token_set & markers)
        # Score: ratio of unique marker words found, weighted by text length
        scores[lang] = hits / len(markers)

    best_lang = max(scores, key=lambda k: scores[k])
    best_score = scores[best_lang]

    if best_score < 0.04:
        return "unknown", 0.0

    # Confidence: ratio of best vs runner-up
    sorted_scores = sorted(scores.values(), reverse=True)
    if len(sorted_scores) > 1 and sorted_scores[1] > 0:
        confidence = sorted_scores[0] / (sorted_scores[0] + sorted_scores[1])
    else:
        confidence = min(best_score * 5, 1.0)  # Scale up for short text

    return best_lang, round(confidence, 2)
