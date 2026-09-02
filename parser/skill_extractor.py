"""Skill extraction using keyword matching + ESCO normalization.

Phase 1 approach: keyword-based extraction with manual skill taxonomy.
Future: ESCO API integration for canonical skill IDs.

The taxonomy covers both modern dev stacks (Python, React, AWS) and
DACH/EU enterprise stacks (SAP, BMC Remedy, Amdocs, Microsoft AD).

Enhanced (2026-09-02): tabellarische Skills-Sektionen (pipe-getrennt,
mehrspaltig) werden jetzt vor dem Keyword-Matching entflacht, damit
Tools wie SAP, Microsoft CRM, Google Ads korrekt erkannt werden.
"""

import re
from pathlib import Path
from typing import Dict, List, Set


# ---------------------------------------------------------------------------
# Table-row unflattener — collapses pipe-separated and column-aligned rows
# into plain space-separated text so keyword matching can find skills.
# ---------------------------------------------------------------------------
_ROW_PIPE_RE = re.compile(r"\|")
_COL_PAD_RE = re.compile(r"\s{3,}")


def _flatten_table_rows(text: str) -> str:
    """Collapse pipe-separated table rows and column-aligned rows into linear text.

    FlowCV and similar tools emit skills sections as tables:
        |SAP|R/3|Microsoft CRM|Google Ads|
        |Python|AWS|Docker|Kubernetes|

    The pipe-separated cells never reach the keyword matcher because
    the surrounding ``|`` characters break word-boundary matching. This
    function replaces ``|`` with spaces so the taxonomy keywords
    inside cells are matchable again.

    Also handles column-aligned (fixed-width) rows: multiple spaces
    that act as column separators are collapsed to single spaces.
    """
    # Replace pipes with spaces — preserves content, removes cell delimiters
    flattened = _ROW_PIPE_RE.sub(" ", text)
    # Collapse runs of 3+ spaces (column padding) into a single space
    flattened = _COL_PAD_RE.sub(" ", flattened)
    return flattened


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
        # DACH enterprise IT tools
        "sap", "sap r/3", "sap erp", "sap hr", "sap procurement", "sap fi", "sap co",
        "bmc remedy", "sccm", "mdm", "ms ad", "active directory",
        # Enterprise software products (Austrian/DACH market)
        "microsoft office", "ms office", "office 365",
        "microsoft crm", "salesforce", "microsoft ads", "google ads",
    },
    "platforms": {
        "aws", "azure", "gcp", "google cloud", "heroku", "digitalocean",
        "vercel", "netlify", "cloudflare",
        "linux", "ubuntu", "debian", "centos", "redhat", "macos", "windows",
        "android", "ios",
        # Telecom / DACH enterprise platforms
        "amdocs", "clarify", "amdocs clearsales", "oracle crm",
    },
    "databases": {
        "postgresql", "mysql", "mariadb", "mongodb", "redis", "cassandra",
        "elasticsearch", "sqlite", "oracle", "sql server", "dynamodb",
        "neo4j", "influxdb",
        # DACH enterprise DBs
        "oracle database", "sap hana", "maxdb",
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
        "empathy", "einfühlungsvermögen", "kollaboration",
        "organisation", "kommunikationsfertigkeit", "kommunikationsfähigkeit",
    },
    "domains": {
        "fintech", "healthtech", "edtech", "e-commerce", "saas", "iot",
        "blockchain", "cybersecurity", "devops", "mlops", "dataops",
        # DACH / EU relevant domains
        "telecom", "telekommunikation", "telekom",
        "b2b sales", "inside sales", "account management", "key account",
        "online marketing", "content management", "lead generation",
        "lead qualification", "marcom", "marketing communications",
        "recruitment", "personalvermittlung", "cv screening",
        "outplacement", "vocational rehabilitation", "berufliche rehabilitation",
        # SEO / web analytics tools
        "google analytics",
    },
}


# Flatten for quick lookup — long phrases first so "sap r/3" matches before "sap"
SKILL_TO_CATEGORY: Dict[str, str] = {}
for category, skills in DEFAULT_SKILL_TAXONOMY.items():
    for skill in skills:
        SKILL_TO_CATEGORY[skill.lower()] = category

# Sort skills by length descending so multi-word phrases match first
_SKILLS_SORTED = sorted(SKILL_TO_CATEGORY.keys(), key=len, reverse=True)


def _word_boundary_match(token: str, text: str) -> bool:
    """Match token with word boundaries using lookahead/lookbehind.

    Uses (?<![a-z0-9]) and (?![a-z0-9]) instead of \\b because \\b
    matches between word-char and non-word-char, which fails for
    tokens ending in non-word chars like 'c++', '.net', 'node.js'.
    """
    pattern = r"(?<![a-z0-9])" + re.escape(token.lower()) + r"(?![a-z0-9])"
    return bool(re.search(pattern, text.lower()))


def extract_skills(text: str, sections: Dict[str, str] | None = None) -> List[Dict]:
    """Extract skills from CV text.

    Strategy:
    1. Prefer the Skills section if available
    2. Flatten pipe-separated table rows in the skills section (FlowCV format)
    3. Fall back to full-text keyword matching with word-boundary safety
    4. Return categorized skills

    Args:
        text: Full CV text.
        sections: Optional segmented sections from segment_sections().

    Returns:
        List of skill dicts: {name, category, proficiency}
    """
    # Prefer skills section (if section segmentation found one)
    skills_text = sections.get("skills", "") if sections else ""
    if not skills_text:
        # Fall back to full text — but we still flatten tables in it
        skills_text = text
    else:
        # Flatten table rows in the skills section so pipe-separated
        # cells like |SAP| |Microsoft CRM| become matchable text
        skills_text = _flatten_table_rows(skills_text)

    # Also flatten tables in the full text fallback path
    if skills_text == text:
        skills_text = _flatten_table_rows(skills_text)

    # Extract skills by keyword matching
    found_skills: Set[str] = set()
    for skill in _SKILLS_SORTED:
        if _word_boundary_match(skill, skills_text):
            found_skills.add(skill)

    # Build categorized output — proficiency defaults to "advanced" to match
    # Phase 1 behavior. Phase 2 should extract proficiency from CV context.
    skills_list = []
    for skill in sorted(found_skills):
        skills_list.append({
            "name": skill,
            "category": SKILL_TO_CATEGORY[skill],
            "proficiency": "advanced",
        })

    return skills_list


__all__ = [
    "extract_skills",
    "DEFAULT_SKILL_TAXONOMY",
    "SKILL_TO_CATEGORY",
    "flatten_table_rows",  # exported for testing
]
