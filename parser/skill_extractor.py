"""Skill extraction using keyword matching + ESCO normalization.

Phase 1 approach: keyword-based extraction with manual skill taxonomy.
Future: ESCO API integration for canonical skill IDs.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Set


# Default skill taxonomy (Phase 1: curated list, Phase 2: ESCO integration)
DEFAULT_SKILL_TAXONOMY = {
    "programming_languages": {
        "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
        "ruby", "php", "swift", "kotlin", "scala", "r", "matlab", "sql", "bash",
        "shell", "powershell", "perl", "haskell", "lua", "dart", "elixir",
    },
    "frameworks": {
        "django", "flask", "fastapi", "react", "vue", "angular", "svelte",
        "express", "nestjs", "spring", "rails", "laravel", "symfony",
        "tensorflow", "pytorch", "keras", "scikit-learn", "pandas", "numpy",
        "next.js", "nuxt", "gatsby", "redux", "graphql", "rest",
    },
    "tools": {
        "git", "docker", "kubernetes", "jenkins", "travis", "circleci",
        "terraform", "ansible", "puppet", "chef", "vagrant",
        "webpack", "vite", "babel", "eslint", "prettier",
        "postman", "swagger", "insomnia",
    },
    "platforms": {
        "aws", "azure", "gcp", "google cloud", "heroku", "digitalocean",
        "vercel", "netlify", "cloudflare",
        "linux", "ubuntu", "debian", "centos", "redhat", "macos", "windows",
        "android", "ios",
    },
    "databases": {
        "postgresql", "mysql", "mariadb", "mongodb", "redis", "cassandra",
        "elasticsearch", "sqlite", "oracle", "sql server", "dynamodb",
        "neo4j", "influxdb",
    },
    "methodologies": {
        "agile", "scrum", "kanban", "lean", "devops", "ci/cd", "tdd", "bdd",
        "microservices", "rest", "graphql", "event-driven", "serverless",
        "machine learning", "deep learning", "nlp", "computer vision",
        "data science", "data engineering", "etl",
    },
    "soft_skills": {
        "leadership", "communication", "teamwork", "problem-solving",
        "project management", "mentoring", "collaboration",
    },
    "domains": {
        "fintech", "healthtech", "edtech", "e-commerce", "saas", "iot",
        "blockchain", "cybersecurity", "devops", "mlops", "dataops",
    },
}


# Flatten for quick lookup
SKILL_TO_CATEGORY: Dict[str, str] = {}
for category, skills in DEFAULT_SKILL_TAXONOMY.items():
    for skill in skills:
        SKILL_TO_CATEGORY[skill.lower()] = category


def extract_skills(text: str, sections: Dict[str, str] | None = None) -> List[Dict]:
    """Extract skills from CV text.

    Strategy:
    1. Prefer the Skills section if available
    2. Fall back to full-text keyword matching
    3. Return categorized skills

    Args:
        text: Full CV text.
        sections: Optional segmented sections from segment_sections().

    Returns:
        List of skill dicts: {category, name, esco_id (None for now)}
    """
    # Prefer skills section
    skills_text = sections.get("skills", "") if sections else ""
    if not skills_text:
        skills_text = text

    # Extract skills by keyword matching
    found_skills: Set[str] = set()
    text_lower = skills_text.lower()

    for skill in SKILL_TO_CATEGORY:
        # Match whole words (avoid "go" matching "google")
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text_lower):
            found_skills.add(skill)

    # Build categorized output
    skills_list = []
    for skill in sorted(found_skills):
        entry = {
            "name": skill,
            "category": SKILL_TO_CATEGORY[skill],
            "proficiency": "advanced",  # Phase 1 default; Phase 2: extract from CV context
        }
        # Only add esco_id if it's set (Phase 2 integration)
        # skills_list.append({**entry, "esco_id": None})  # Don't add null field
        skills_list.append(entry)

    return skills_list


def load_esco_skills(esco_file: Path) -> Dict[str, str]:
    """Load ESCO skills mapping (Phase 2).

    Args:
        esco_file: Path to ESCO CSV/JSON file.

    Returns:
        Dict mapping skill name to ESCO URI.
    """
    # TODO: Phase 2 implementation
    raise NotImplementedError("ESCO integration is Phase 2")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python skill_extractor.py <text_file>")
        sys.exit(1)
    from .section_segmenter import segment_sections

    with open(sys.argv[1]) as f:
        text = f.read()
    sections = segment_sections(text)
    skills = extract_skills(text, sections)

    print(f"\nExtracted {len(skills)} skills:")
    print(json.dumps(skills, indent=2))