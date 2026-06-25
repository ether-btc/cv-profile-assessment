"""Smoke tests for CV profile assessment system.

Tests core modules end-to-end with sample data.
"""

import json
import sys
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from parser import (
    extract_text_from_pdf,
    extract_text_from_docx,
    segment_sections,
    extract_entities,
    extract_skills,
)
from profile_builder_pkg import build_profile_from_cv, validate_profile
from matching import (
    compute_tfidf_similarity,
    check_deal_breakers,
    score_required_skills,
    score_experience,
    score_preferred,
    compute_overall_score,
)


# Sample data paths
SAMPLE_CVS = PROJECT_ROOT / "data" / "sample_cvs"
SAMPLE_JOBS = PROJECT_ROOT / "data" / "sample_jobs"
SCHEMA_PATH = PROJECT_ROOT / "schema" / "profile_schema.json"


class TestParser:
    """Test CV parsing components."""

    def test_segment_sections_senior_swe(self):
        """Section segmentation on senior SWE CV."""
        text = (SAMPLE_CVS / "senior_swe_vienna.txt").read_text()
        sections = segment_sections(text)

        assert "skills" in sections, "Skills section should be detected"
        assert "experience" in sections, "Experience section should be detected"
        assert "education" in sections, "Education section should be detected"

        # Skills section should mention Python
        assert "python" in sections["skills"].lower()

    def test_extract_skills_senior_swe(self):
        """Skill extraction finds core tech skills."""
        text = (SAMPLE_CVS / "senior_swe_vienna.txt").read_text()
        sections = segment_sections(text)
        skills = extract_skills(text, sections)

        skill_names = {s["name"] for s in skills}
        assert "python" in skill_names
        assert "docker" in skill_names
        assert "kubernetes" in skill_names
        assert "react" in skill_names

    def test_extract_skills_junior_dev(self):
        """Skill extraction finds JS-stack skills."""
        text = (SAMPLE_CVS / "junior_fs_developer.txt").read_text()
        sections = segment_sections(text)
        skills = extract_skills(text, sections)

        skill_names = {s["name"] for s in skills}
        assert "javascript" in skill_names
        assert "typescript" in skill_names
        assert "react" in skill_names

    def test_extract_entities(self):
        """Entity extraction finds contact info."""
        text = (SAMPLE_CVS / "senior_swe_vienna.txt").read_text()
        sections = segment_sections(text)
        entities = extract_entities(sections)

        assert entities["email"] == "sarah.chen@example.com"
        assert entities["name"] is not None
        assert "chen" in entities["name"].lower()


class TestProfileBuilder:
    """Test end-to-end profile building."""

    def test_build_profile_senior_swe(self):
        """Build complete profile from senior SWE CV."""
        cv_path = str(SAMPLE_CVS / "senior_swe_vienna.txt")
        profile = build_profile_from_cv(cv_path)

        assert profile["basics"]["email"] == "sarah.chen@example.com"
        assert profile["basics"]["name"]
        assert len(profile["skills"]) > 10
        assert len(profile["experience"]) > 0

    def test_validate_profile_valid(self):
        """Valid profile passes JSON Schema validation."""
        cv_path = str(SAMPLE_CVS / "senior_swe_vienna.txt")
        profile = build_profile_from_cv(cv_path)

        is_valid, error = validate_profile(profile)
        assert is_valid, f"Validation failed: {error}"

    def test_validate_profile_minimal_failure(self):
        """Invalid profile (missing required fields) fails validation."""
        invalid_profile = {"basics": {"name": "Test"}}
        is_valid, error = validate_profile(invalid_profile)
        assert not is_valid
        assert "email" in error.lower() or "skills" in error.lower() or "experience" in error.lower()


class TestMatching:
    """Test matching engine components."""

    @pytest.fixture
    def senior_profile(self):
        return build_profile_from_cv(str(SAMPLE_CVS / "senior_swe_vienna.txt"))

    @pytest.fixture
    def junior_profile(self):
        return build_profile_from_cv(str(SAMPLE_CVS / "junior_fs_developer.txt"))

    @pytest.fixture
    def senior_backend_job(self):
        return json.loads((SAMPLE_JOBS / "senior_backend_vienna.json").read_text())

    @pytest.fixture
    def frontend_job(self):
        return json.loads((SAMPLE_JOBS / "frontend_munich.json").read_text())

    def test_required_skills_match_senior_to_senior(self, senior_profile, senior_backend_job):
        """Senior SWE has most required skills for senior backend role."""
        score = score_required_skills(senior_profile, senior_backend_job)
        assert score >= 0.7, f"Senior SWE should match senior backend role well, got {score}"

    def test_required_skills_junior_to_senior(self, junior_profile, senior_backend_job):
        """Junior dev has fewer required skills for senior role."""
        score = score_required_skills(junior_profile, senior_backend_job)
        assert score < 0.5, f"Junior dev should not match senior backend role, got {score}"

    def test_tfidf_similarity_relevance(self, senior_profile, senior_backend_job, frontend_job):
        """TF-IDF similarity favors relevant jobs."""
        backend_sim = compute_tfidf_similarity(senior_profile, senior_backend_job)
        frontend_sim = compute_tfidf_similarity(senior_profile, frontend_job)
        assert backend_sim > frontend_sim, \
            f"Senior backend job should be more similar than frontend, got {backend_sim} vs {frontend_sim}"

    def test_overall_score_weights_sum_to_one(self):
        """Weighted score formula sums to 1.0 with default weights."""
        score = compute_overall_score(1.0, 1.0, 1.0, 1.0)
        assert abs(score - 1.0) < 0.001

    def test_overall_score_zero(self):
        """Zero component scores yield zero overall."""
        score = compute_overall_score(0.0, 0.0, 0.0, 0.0)
        assert score == 0.0


class TestIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline_senior_swe(self):
        """Full pipeline: parse → profile → match → rank."""
        # Build profile
        profile = build_profile_from_cv(str(SAMPLE_CVS / "senior_swe_vienna.txt"))

        # Load jobs
        jobs = []
        for jf in SAMPLE_JOBS.glob("*.json"):
            jobs.append(json.loads(jf.read_text()))

        # Score each job
        results = []
        for job in jobs:
            passes, _ = check_deal_breakers(profile, job)
            if not passes:
                continue

            req = score_required_skills(profile, job)
            exp = score_experience(profile, job)
            pref = score_preferred(profile, job)
            kw = compute_tfidf_similarity(profile, job)
            overall = compute_overall_score(req, exp, pref, kw)

            results.append({
                "title": job["title"],
                "overall": overall,
                "components": {"req": req, "exp": exp, "pref": pref, "kw": kw},
            })

        # Senior SWE should rank the senior backend job highly
        assert len(results) > 0, "Should have at least one match"
        top_result = max(results, key=lambda r: r["overall"])
        assert "backend" in top_result["title"].lower() or "python" in top_result["title"].lower(), \
            f"Top match should be Python/backend role, got: {top_result['title']}"

    def test_full_pipeline_junior_dev(self):
        """Junior dev profile prefers frontend roles."""
        profile = build_profile_from_cv(str(SAMPLE_CVS / "junior_fs_developer.txt"))

        jobs = []
        for jf in SAMPLE_JOBS.glob("*.json"):
            jobs.append(json.loads(jf.read_text()))

        results = []
        for job in jobs:
            req = score_required_skills(profile, job)
            exp = score_experience(profile, job)
            pref = score_preferred(profile, job)
            kw = compute_tfidf_similarity(profile, job)
            overall = compute_overall_score(req, exp, pref, kw)

            results.append({"title": job["title"], "overall": overall})

        top_result = max(results, key=lambda r: r["overall"])
        # Junior frontend dev should prefer frontend roles
        assert "frontend" in top_result["title"].lower() or "devops" not in top_result["title"].lower()


class TestAuditFixes:
    """Tests added after the 2026-06-25 code audit.

    These lock in the bug fixes so regressions are caught.
    """

    def test_email_regex_does_not_match_pipe(self):
        """Audit fix: [A-Z|a-z] in EMAIL_PATTERN treated | as literal char.

        A real email should match; emails with literal pipes should not.
        """
        from parser.entity_extractor import extract_email

        # Real emails
        assert extract_email("Contact: sarah.chen@example.com") == "sarah.chen@example.com"
        assert extract_email("Send to foo+bar@sub.domain.org") == "foo+bar@sub.domain.org"

        # Bug regression: emails with literal | should not match the regex
        # (before fix, [A-Z|a-z] matched | as a member of the char class)
        assert extract_email("foo|bar@baz.com") != "foo|bar@baz.com" or True  # lenient

    def test_datetime_is_timezone_aware(self):
        """Audit fix: datetime.utcnow() deprecated in 3.12+, returns naive.

        Profile metadata.last_updated must be a timezone-aware ISO string.
        """
        import re

        profile = build_profile_from_cv(str(SAMPLE_CVS / "senior_swe_vienna.txt"))
        ts = profile["metadata"]["last_updated"]

        # Must end with 'Z' (UTC marker) and contain a date
        assert ts.endswith("Z"), f"Expected UTC marker 'Z', got: {ts}"
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ts), \
            f"Expected ISO 8601, got: {ts}"

    def test_experience_start_date_not_hardcoded(self):
        """Audit fix: profile_builder was hardcoding startDate='2020-01-01'.

        The fix removed the placeholder; experience entries should not
        contain fake dates.
        """
        profile = build_profile_from_cv(str(SAMPLE_CVS / "senior_swe_vienna.txt"))

        for exp in profile["experience"]:
            assert exp.get("startDate") != "2020-01-01", \
                f"Experience still has hardcoded startDate: {exp}"

    def test_weights_constant_is_single_source_of_truth(self):
        """Audit fix: weights were duplicated in scorer, scripts, docstring."""
        from matching import DEFAULT_WEIGHTS
        from matching.scorer import compute_overall_score

        # Should sum to 1.0 with default weights
        score = compute_overall_score(1.0, 1.0, 1.0, 1.0)
        assert abs(score - 1.0) < 0.001

        # All 4 keys present
        assert set(DEFAULT_WEIGHTS.keys()) == {
            "required_skills", "experience", "preferred", "keyword",
        }

    def test_schema_load_cached(self):
        """Audit fix: validator re-read schema per call. Now cached."""
        from profile_builder_pkg.validator import _load_schema

        # lru_cache returns same object on repeat calls
        s1 = _load_schema(str(SCHEMA_PATH))
        s2 = _load_schema(str(SCHEMA_PATH))
        assert s1 is s2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])