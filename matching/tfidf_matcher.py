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


def compute_tfidf_similarity(profile: Dict, job: Dict) -> float:
    """Compute TF-IDF cosine similarity between profile and job.

    Args:
        profile: Personal profile dict.
        job: Job description dict.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    profile_text = profile_to_text(profile)
    job_text = job_to_text(job)

    if not profile_text or not job_text:
        return 0.0

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
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


