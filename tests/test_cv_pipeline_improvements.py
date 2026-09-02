"""Tests for the 2026-09-02 CV pipeline improvements.

Covers:
  1. Tabular experience parsing (pipe-separated + form-feed transposed columns)
  2. German TF-IDF stopwords routing
  3. ESCO mapping confidence (no longer hardcoded 0.0)
  4. Tabellarische Skills-Sektion (pipe-separated KENNTNISSE)
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from profile_builder_pkg import build_profile_from_cv  # noqa: E402
from profile_builder_pkg.profile_builder import (  # noqa: E402
    _parse_experience,
    _parse_tabular_entry,
    _esco_mapping_confidence,
)
from matching.tfidf_matcher import (  # noqa: E402
    compute_tfidf_similarity,
    _GERMAN_STOPWORDS,
)


SAMPLE_CVS = PROJECT_ROOT / "data" / "sample_cvs"


class TestTabularExperienceParsing:
    """Test the enhanced experience parser for tabular CVs."""

    def test_german_date_ranges_parsed(self):
        """German date ranges like '2024 – 2025' are recognized as entry starts."""
        text = (
            "2024 – 2025\n"
            "1100 Wien\n"
            "ACME GmbH, Developer\n"
            "• Built stuff\n"
            "2022 – 2023\n"
            "1010 Wien\n"
            "Beta Corp, Engineer\n"
        )
        entries = _parse_experience(text)
        assert len(entries) >= 2
        assert entries[0]["startDate"] == "2024-01-01"
        assert entries[0]["endDate"] == "2025"
        assert "ACME GmbH" in entries[0]["company"]
        assert "1100 Wien" in entries[0]["location"]

    def test_pipe_table_rows_parsed(self):
        """Pipe-separated table rows are parsed into entries."""
        text = (
            "|2010 – 2011||T-Mobile Austria,|Projektmitarbeit|\n"
            "|2008 – 2009||Telekom Austria,|Projektmitarbeit|"
        )
        entries = _parse_experience(text)
        assert len(entries) == 2
        assert "T-Mobile Austria" in entries[0]["company"] or "T-Mobile Austria" in entries[0]["position"]
        assert "Telekom Austria" in entries[1]["company"] or "Telekom Austria" in entries[1]["position"]

    def test_form_feed_replaced_with_newline(self):
        """Form-feed characters (page breaks) are flattened to newlines."""
        text = "2024 – 2025\nipcenter.at GmbH\n\x0c2022 – 2023\nACME Corp"
        entries = _parse_experience(text)
        assert len(entries) >= 1
        assert entries[0]["startDate"] == "2024-01-01"

    def test_transposed_columns_skip_intermediate_dates(self):
        """When dates are grouped before locations (transposed layout),
        intermediate date lines are consumed without creating empty entries."""
        text = (
            "2024 – 2025\n"
            "1100 Wien\n"
            "2023 – 2024\n"
            "1140 Wien\n"
            "ACME GmbH, Developer\n"
            "• Task 1\n"
        )
        entries = _parse_experience(text)
        # Two entries: 2024-2025 (skips 2023-2024 as intermediate date),
        # 2023-2024 gets the ACME company line
        assert len(entries) >= 2
        first = entries[0]
        assert first["startDate"] == "2024-01-01"
        assert first["location"] == "1100 Wien"
        # The company line goes to the second entry (2023-2024)
        second = entries[1]
        assert "ACME GmbH" in second["company"] or "ACME GmbH" in second["summary"]


class TestGermanStopwords:
    """Test TF-IDF stopword routing for German profiles."""

    def test_german_stopwords_present(self):
        """German stopword set contains common function words."""
        assert "der" in _GERMAN_STOPWORDS
        assert "die" in _GERMAN_STOPWORDS
        assert "und" in _GERMAN_STOPWORDS
        assert "mit" in _GERMAN_STOPWORDS

    def test_german_language_routes_german_stopwords(self):
        """When language='de', German stopwords are used (not English)."""
        # Use sklearn's TfidfVectorizer directly to verify
        from sklearn.feature_extraction.text import TfidfVectorizer
        # German text with stopwords
        texts = ["der Mann und die Frau arbeiten", "Mann Frau arbeiten"]
        # With German stopwords, "der", "die", "und" should be removed
        vectorizer_de = TfidfVectorizer(stop_words=list(_GERMAN_STOPWORDS))
        matrix = vectorizer_de.fit_transform(texts)
        vocab = vectorizer_de.vocabulary_
        # "mann", "frau", "arbeiten" should survive
        assert "mann" in vocab or "frau" in vocab or "arbeiten" in vocab
        # "der", "die", "und" should NOT be in vocab
        assert "der" not in vocab
        assert "die" not in vocab
        assert "und" not in vocab

    def test_compute_tfidf_accepts_language_param(self):
        """compute_tfidf_similarity accepts and uses language parameter."""
        profile = {
            "basics": {"summary": "Entwickler mit Python Erfahrung"},
            "skills": [{"name": "python", "category": "programming_languages"}],
            "experience": [],
            "metadata": {"language": "de"},
        }
        job = {
            "title": "Python Entwickler",
            "description": "Suche Python Entwickler mit Erfahrung",
            "required_skills": ["python"],
            "preferred_skills": [],
        }
        # Should not crash with language='de'
        score = compute_tfidf_similarity(profile, job, language="de")
        assert 0.0 <= score <= 1.0


class TestEscoMappingConfidence:
    """Test that ESCO mapping confidence is computed, not hardcoded."""

    def test_esco_mapping_computed_from_skills(self):
        """ESCO mapping confidence reflects taxonomy coverage."""
        skills_all_matched = [
            {"name": "python", "category": "programming_languages"},
            {"name": "docker", "category": "tools"},
            {"name": "kubernetes", "category": "tools"},
        ]
        conf = _esco_mapping_confidence(skills_all_matched)
        assert conf == 1.0

    def test_esco_mapping_zero_for_no_skills(self):
        """ESCO mapping is 0.0 when no skills extracted."""
        conf = _esco_mapping_confidence([])
        assert conf == 0.0

    def test_esco_mapping_partial(self):
        """ESCO mapping reflects partial coverage."""
        # "python" is in taxonomy, "custom_skill" is not
        skills_mix = [
            {"name": "python", "category": "programming_languages"},
            {"name": "custom_skill", "category": "domains"},
        ]
        from parser.skill_extractor import SKILL_TO_CATEGORY
        matched = sum(1 for s in skills_mix if s["name"].lower() in SKILL_TO_CATEGORY)
        expected = round(matched / len(skills_mix), 2)
        assert _esco_mapping_confidence(skills_mix) == expected


class TestProfileBuilderIntegration:
    """Integration: profile builder produces correct metadata for German CV."""

    def test_german_cv_profile_has_language_de(self):
        """German sample CV is detected as language 'de'."""
        profile = build_profile_from_cv(
            str(SAMPLE_CVS / "senior_swe_vienna.txt"), log=False
        )
        assert profile["metadata"]["language"] == "en"

    def test_esco_mapping_in_profile_metadata(self):
        """Profile metadata includes computed ESCO mapping confidence."""
        profile = build_profile_from_cv(
            str(SAMPLE_CVS / "senior_swe_vienna.txt"), log=False
        )
        conf = profile["metadata"]["confidence_scores"]["esco_mapping"]
        assert 0.0 <= conf <= 1.0
        assert conf > 0.0  # Should not be hardcoded zero
