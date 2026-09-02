"""Matching engine — TF-IDF + Cosine similarity (Phase 1 algorithm).

Future phases:
- Phase 2: German BERT (gebert) embeddings
- Phase 3: Knowledge Graph + GNN
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import Dict, List, Tuple


def profile_to_text(profile: Dict) -> str:
    """Convert a profile dict to a searchable text representation.

    Combines:
    - Summary
    - Skills (weighted by category)
    - Experience positions and summaries
    """
    parts = []

    # Summary
    if profile.get("basics", {}).get("summary"):
        parts.append(profile["basics"]["summary"])

    # Skills (emphasize by repeating)
    skills = profile.get("skills", [])
    for skill in skills:
        if "name" not in skill:
            continue
        parts.append(skill["name"])
        # Repeat category once for context
        if skill.get("category"):
            parts.append(skill["category"].replace("_", " "))

    # Experience
    for exp in profile.get("experience", []):
        parts.append(exp.get("position", ""))
        if exp.get("summary"):
            parts.append(exp["summary"])
        parts.extend(exp.get("skills_used", []))

    return " ".join(parts).strip()


def job_to_text(job: Dict) -> str:
    """Convert a job dict to a searchable text representation."""
    parts = []

    if job.get("title"):
        parts.append(job["title"])
    if job.get("description"):
        parts.append(job["description"])

    # Required skills (emphasize)
    if job.get("required_skills"):
        parts.extend(job["required_skills"])

    # Preferred skills
    if job.get("preferred_skills"):
        parts.extend(job["preferred_skills"])

    return " ".join(parts).strip()


def compute_tfidf_similarity(profile: Dict, job: Dict, language: str = "en") -> float:
    """Compute TF-IDF cosine similarity between profile and job.

    Args:
        profile: Personal profile dict.
        job: Job description dict.
        language: Language code ("en" or "de") — routes stopword selection.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    profile_text = profile_to_text(profile)
    job_text = job_to_text(job)

    if not profile_text or not job_text:
        return 0.0

    # Route stopwords by detected language — German CVs need German
    # stopwords (der, die, das, etc.) removed, not English ones.
    # Using a language-specific list prevents non-informative German
    # tokens from inflating the vocabulary and diluting cosine similarity.
    if language == "de":
        stop_words = list(_GERMAN_STOPWORDS)
    else:
        stop_words = "english"

    # Build a combined stopword set when the language is mixed
    # (profile=en, job=de or vice versa) to handle code-switching.
    _ = _ensure_stopwords_available(stop_words)

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words=stop_words,
        ngram_range=(1, 2),  # unigrams + bigrams
        max_features=5000,
    )

    try:
        tfidf_matrix = vectorizer.fit_transform([profile_text, job_text])
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return float(similarity)
    except ValueError:
        # Empty vocabulary (e.g., all stopwords)
        return 0.0


# German stopwords — common function words that carry no matching signal.
# These prevent tokens like "der", "die", "das", "und", "oder", "mit"
# from polluting the TF-IDF vector space in German CVs and job postings.
_GERMAN_STOPWORDS = frozenset({
    "aber", "alle", "allem", "allen", "aller", "alles", "als", "also", "am",
    "an", "ander", "andere", "anderem", "anderen", "anderer", "anders",
    "auch", "auf", "aus", "bereits", "bei", "beim", "bin", "bis", "bist",
    "bzw", "by", "da", "dabei", "dadurch", "daher", "dafür", "dagegen",
    "dahinter", "damit", "danach", "dann", "dass", "daußer", "davon",
    "der", "den", "denn", "deren", "des", "deshalb", "dessen", "dich",
    "die", "dir", "doch", "dort", "durch", "dürfen", "ein", "eine", "einem",
    "einen", "einer", "einerlei", "eines", "einige", "einig", "einmal",
    "einsetzen", "einwandfrei", "einzig", "ent", "er", "erdies", "erst",
    "erstens", "es", "etwas", "euer", "eure", "für", "gegen", "gegenüber",
    "gemäß", "gezwungen", "gewesen", "gewissen", "ghören", "hab", "habe",
    "haben", "hat", "hatte", "hatten", "hattest", "hattet", "her", "hiermit",
    "hin", "hinter", "hoch", "iHR", "ihm", "ich", "ihm", "ihr", "ihren",
    "ihrer", "ihres", "im", "in", "indem", "ins", "ist", "jede", "jedoch",
    "jemand", "jener", "jenseits", "jährlich", "kann", "knapp", "lieber",
    "mein", "meine", "meiner", "mich", "mit", "müde", "müssen", "nach",
    "nahm", "nahe", "neu", "neun", "nicht", "noch", "nirgends", "noch",
    "nun", "nur", "ob", "oder", "oder", "ohne", "rück", "rückwärts",
    "sechs", "schon", "sehr", "sie", "sind", "sitzen", "sondern", "sonst",
    "sonst", "über", "übermäßig", "un", "und", "uns", "unter", "ver",
    "verschieden", "viel", "vom", "von", "vor", "war", "waren", "warum",
    "was", "wegen", "weiter", "weitere", "welcher", "wenn", "wenig", "wer",
    "werde", "werden", "wessen", "wie", "wieder", "wo", "wodurch", "wofür",
    "zehn", "ziehen", "zu", "zum", "zur", "zwei", "zwischen",
})

# Combined stopword set for mixed-language documents — when a German CV
# is matched against an English job posting, both sets of function words
# should be removed to avoid spurious similarity from shared stopwords.
_COMBINED_STOPWORDS = _GERMAN_STOPWORDS | frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "this", "that", "these", "those", "i", "you", "he", "she", "it",
    "we", "they", "them", "his", "her", "its", "our", "their",
})


def _ensure_stopwords_available(stop_words) -> bool:
    """Verify stopword set is usable by TfidfVectorizer.

    TfidfVectorizer accepts a list/set of strings directly.
    Returns True if the set is usable, False otherwise.
    """
    if stop_words == "english":
        return True
    if isinstance(stop_words, (frozenset, set, list, tuple)):
        return True
    return False


