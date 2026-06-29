"""Pytest configuration and fixtures for CV Profile Assessment tests.

This file makes helper functions and fixtures available to all tests
without requiring repetitive imports.
"""

import sys
from pathlib import Path
from typing import Dict

import pytest

# Make project root importable for all tests
TEST_DIR = Path(__file__).parent
PROJECT_ROOT = TEST_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_profile() -> Dict:
    """Sample profile dict for testing (Sarah Chen, Senior SWE)."""
    return {
        "basics": {
            "name": "Sarah Chen",
            "email": "sarah.chen@example.com",
            "phone": "+43 660 1234567",
            "location": {"city": "Vienna", "country": "Austria"},
            "summary": "Senior Software Engineer with 8+ years of experience",
            "languages": [{"language": "English", "fluency": "native"},
                         {"language": "German", "fluency": "intermediate"}],
        },
        "skills": [
            {"category": "programming_languages", "name": "Python", "proficiency": "expert"},
            {"category": "programming_languages", "name": "Go", "proficiency": "advanced"},
            {"category": "frameworks", "name": "FastAPI", "proficiency": "advanced"},
            {"category": "frameworks", "name": "Django", "proficiency": "advanced"},
            {"category": "tools", "name": "Docker", "proficiency": "advanced"},
            {"category": "tools", "name": "Kubernetes", "proficiency": "intermediate"},
            {"category": "platforms", "name": "AWS", "proficiency": "advanced"},
            {"category": "platforms", "name": "GCP", "proficiency": "intermediate"},
            {"category": "databases", "name": "PostgreSQL", "proficiency": "advanced"},
            {"category": "databases", "name": "Redis", "proficiency": "advanced"},
            {"category": "soft_skills", "name": "Leadership", "proficiency": "advanced"},
        ],
        "experience": [
            {
                "position": "Senior Backend Engineer",
                "company": "TechCorp GmbH",
                "location": "Vienna, Austria",
                "startDate": "2020-01-01",
                "current": True,
                "summary": "Leading backend development for microservices platform",
                "achievements": [
                    "Reduced API latency by 60%",
                    "Led migration to Kubernetes",
                ],
                "skills_used": ["Python", "FastAPI", "Docker", "Kubernetes", "PostgreSQL"],
            },
        ],
        "education": [],
        "projects": [],
        "certifications": [],
        "preferences": {
            "location_preference": {
                "preferred_cities": ["Vienna", "Salzburg"],
                "remote_only": False,
                "hybrid_ok": True,
                "relocation_willing": False,
            },
            "salary_expectations": {
                "minimum": 70000,
                "target": 85000,
                "currency": "EUR",
                "period": "yearly",
            },
            "role_preferences": {},
            "deal_breakers": [],
        },
        "metadata": {
            "version": "1.0",
            "last_updated": "2026-06-25T00:00:00Z",
            "source": "test",
            "confidence_scores": {
                "skills_extraction": 0.9,
                "esco_mapping": 0.0,
            },
        },
    }


@pytest.fixture
def sample_job_backend() -> Dict:
    """Sample backend engineer job."""
    return {
        "title": "Senior Backend Engineer (Python)",
        "company": "InnovateTech GmbH",
        "location": "Vienna, Austria",
        "remote": False,
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "preferred_skills": ["Kubernetes", "AWS", "Redis"],
        "min_years_experience": 5,
        "seniority": "senior",
        "salary_range": {
            "min": 75000,
            "max": 95000,
            "currency": "EUR",
            "period": "yearly",
        },
        "description": """
        We are looking for a Senior Backend Engineer with strong Python skills.
        You will work with FastAPI, PostgreSQL, and containerized deployments.
        Experience with Kubernetes and cloud platforms (AWS/GCP) is a plus.
        """,
        "_source": {
            "url": "https://example.com/jobs/123",
            "ats": "greenhouse",
            "source_domain": "example.com",
        },
    }


@pytest.fixture
def sample_job_devops() -> Dict:
    """Sample DevOps engineer job."""
    return {
        "title": "DevOps Engineer",
        "company": "CloudOps Inc",
        "location": "Vienna, Austria",
        "remote": True,
        "required_skills": ["Kubernetes", "Docker", "AWS", "Terraform"],
        "preferred_skills": ["Python", "Go", "CI/CD"],
        "min_years_experience": 4,
        "seniority": "mid",
        "salary_range": {
            "min": 65000,
            "max": 85000,
            "currency": "EUR",
            "period": "yearly",
        },
        "description": """
        DevOps Engineer needed for cloud infrastructure management.
        Kubernetes, Docker, and AWS experience required.
        Python or Go scripting skills are a plus.
        """,
    }


@pytest.fixture
def sample_job_frontend() -> Dict:
    """Sample frontend developer job (mismatch for backend profile)."""
    return {
        "title": "Frontend Developer (React/Next.js)",
        "company": "WebStudio AG",
        "location": "Vienna, Austria",
        "remote": False,
        "required_skills": ["React", "Next.js", "TypeScript", "CSS"],
        "preferred_skills": ["GraphQL", "Tailwind"],
        "min_years_experience": 3,
        "seniority": "mid",
        "description": """
        Frontend Developer with React and Next.js expertise.
        Strong TypeScript and modern CSS skills required.
        """,
    }


@pytest.fixture
def temp_json_file(tmp_path):
    """Fixture to create temporary JSON files for tests."""
    def _creator(data: Dict, name: str = "data.json") -> Path:
        file_path = tmp_path / name
        import json
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return file_path
    return _creator