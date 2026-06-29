"""Tests for Phase 5: German CV parsing (i18n), language detection, and usage history.

These regression tests verify that the parser handles German-language CVs:
- SECTION_PATTERNS recognize German section headers
- Language detection identifies German text
- Entity extraction routes to de_core_news_sm
- Skill taxonomy matches German CVs
- Usage history records every processing run
"""

import json
from pathlib import Path

import pytest

from cv_profile_assessment import (
    detect_language,
    log_processing_run,
    read_history,
    format_history_table,
)
from parser.section_segmenter import segment_sections, _detect_section
from parser.entity_extractor import (
    extract_languages_from_section,
    extract_phone,
    extract_entities,
)
from parser.skill_extractor import extract_skills


class TestLanguageDetection:
    """Language detection via common-word frequency ratio."""

    def test_detect_german(self):
        text = (
            "Matthias K.\nÖsterreich\n"
            "BERUFSERFAHRUNG\n"
            "2024 – 2025 | ipcenter.at GmbH, Outplacement\n"
            "Liaison zu Partnern für Ausbildung und Praktika für Immigranten"
        )
        lang, conf = detect_language(text)
        assert lang == "de", f"Expected German, got {lang}"
        assert conf > 0.5

    def test_detect_english(self):
        text = (
            "Sarah Chen\nsarah.chen@example.com | +43 660 1234567 | Vienna, Austria\n\n"
            "SUMMARY\n"
            "Senior Software Engineer with 8 years of experience in Python, "
            "distributed systems, and machine learning. "
            "Passionate about building scalable backend services."
        )
        lang, _ = detect_language(text)
        assert lang == "en"

    def test_empty_text_returns_unknown(self):
        assert detect_language("") == ("unknown", 0.0)
        assert detect_language("   \n  \t  ") == ("unknown", 0.0)

    def test_short_text_returns_unknown(self):
        # Too short to classify reliably
        assert detect_language("hello world") == ("unknown", 0.0)


class TestGermanSectionSegmentation:
    """German section headers should segment correctly."""

    @pytest.mark.parametrize("header,expected", [
        ("BERUFSERFAHRUNG", "experience"),
        ("Berufserfahrung", "experience"),
        ("AUSBILDUNG, ABGESCHLOSSENE", "education"),  # Matthias's CV style
        ("AUSBILDUNG", "education"),
        ("KENNTNISSE", "skills"),
        ("SPRACHEN", "languages"),
        ("SOFT SKILLS", "skills"),
        ("ITK", "skills"),  # Matthias's CV has this abbreviation
        ("ZERTIFIKATE", "certifications"),
        ("WEITERBILDUNG", "certifications"),
    ])
    def test_german_header_detected(self, header, expected):
        assert _detect_section(header) == expected, \
            f"German header {header!r} should map to {expected}"

    def test_full_german_cv_segments(self):
        text = (
            "Matthias K.\nÖsterreich\nFührerschein B\n"
            "BERUFSERFAHRUNG\n2024 – 2025\nipcenter.at GmbH, Outplacement\n"
            "AUSBILDUNG, ABGESCHLOSSENE\n2023 – 2025\nFH Burgenland, MSc eCommerce\n"
            "KENNTNISSE\nSAP, Office, Google Analytics\n"
            "SPRACHEN\nDeutsch, Ungarisch\n"
        )
        sections = segment_sections(text)
        assert "experience" in sections
        assert "education" in sections
        assert "skills" in sections
        assert "languages" in sections

    def test_english_headers_still_work(self):
        # Backward compat check
        assert _detect_section("EXPERIENCE") == "experience"
        assert _detect_section("EDUCATION") == "education"
        assert _detect_section("SKILLS") == "skills"


class TestLanguageExtraction:
    """Language names extracted from a 'languages' section (DE/EN)."""

    def test_german_names_normalized_to_english(self):
        # German CVs use "Deutsch", "Ungarisch", etc.
        result = extract_languages_from_section(
            "Deutsch\nUngarisch\nBusiness English\n"
        )
        lang_names = [r["language"] for r in result]
        assert "German" in lang_names
        assert "Hungarian" in lang_names
        assert "English" in lang_names

    def test_english_names_kept(self):
        result = extract_languages_from_section(
            "German\nEnglish\nHungarian\n"
        )
        lang_names = [r["language"] for r in result]
        assert "German" in lang_names
        assert "English" in lang_names
        assert "Hungarian" in lang_names

    def test_returns_schema_compatible_format(self):
        # Schema requires {language, fluency} objects
        result = extract_languages_from_section("German\nEnglish")
        assert len(result) == 2
        for entry in result:
            assert "language" in entry
            assert "fluency" in entry
            assert entry["fluency"] in {"native", "fluent", "intermediate", "basic"}

    def test_german_default_to_native(self):
        result = extract_languages_from_section("Deutsch")
        assert result[0]["fluency"] == "native"

    def test_empty_section_returns_empty_list(self):
        assert extract_languages_from_section("") == []
        assert extract_languages_from_section(None) == []

    def test_no_duplicates(self):
        result = extract_languages_from_section("German\nGerman\nDeutsch\nDeutsch")
        lang_names = [r["language"] for r in result]
        assert lang_names.count("German") == 1


class TestGermanSkillExtraction:
    """DACH/Austrian enterprise tools and German soft skills."""

    def test_dach_enterprise_tools(self):
        text = "Erfahrung mit SAP R/3, BMC Remedy, SCCM, MDM, MS Active Directory"
        skills = extract_skills(text)
        skill_names = {s["name"] for s in skills}
        assert "sap" in skill_names or "sap r/3" in skill_names
        assert "bmc remedy" in skill_names
        assert "sccm" in skill_names
        assert "mdm" in skill_names
        assert "active directory" in skill_names or "ms ad" in skill_names

    def test_german_soft_skills(self):
        text = (
            "Kommunikationsfähigkeit, Kollaboration und Einfühlungsvermögen "
            "sowie Organisationstalent"
        )
        skills = extract_skills(text)
        skill_names = {s["name"] for s in skills}
        assert "kommunikationsfertigkeit" in skill_names or "kommunikationsfähigkeit" in skill_names
        assert "kollaboration" in skill_names
        assert "einfühlungsvermögen" in skill_names

    def test_recruitment_terms(self):
        text = "Personalvermittlung, CV Screening, Outplacement"
        skills = extract_skills(text)
        skill_names = {s["name"] for s in skills}
        assert "personalvermittlung" in skill_names
        assert "cv screening" in skill_names
        assert "outplacement" in skill_names

    def test_telecom_skills(self):
        text = "Erfahrung in Telekommunikation, Amdocs ClearSales, Clarify"
        skills = extract_skills(text)
        skill_names = {s["name"] for s in skills}
        assert "amdocs" in skill_names or "amdocs clearsales" in skill_names
        assert "clarify" in skill_names
        assert "telekommunikation" in skill_names


class TestGermanPhoneExtraction:
    """Phone number extraction supports German format (+49, 0 prefix)."""

    def test_german_phone_with_country_code(self):
        assert extract_phone("Tel: +49 30 12345678", language="de") is not None

    def test_german_phone_with_zero_prefix(self):
        result = extract_phone("Tel: 030 12345678", language="de")
        assert result is not None

    def test_austrian_mobile(self):
        # Austrian mobile: +43 6XX or 06XX
        result = extract_phone("+43 660 1234567", language="de")
        assert result is not None


class TestUsageHistory:
    """Append-only JSONL log records every parse_cv run."""

    def test_log_creates_entry(self, tmp_path):
        log_path = tmp_path / "history.jsonl"
        profile = {
            "basics": {"name": "Test User", "languages": []},
            "skills": [{"name": "python", "category": "programming_languages", "proficiency": "advanced"}],
            "experience": [],
            "metadata": {
                "language": "en",
                "confidence_scores": {"skills_extraction": 0.9},
            },
        }
        record = log_processing_run(
            source_path="/tmp/cv.pdf",
            profile=profile,
            language="en",
            log_path=log_path,
        )
        assert record["language"] == "en"
        assert record["entity_counts"]["skills"] == 1
        assert "/tmp/cv.pdf" in record["source"]

    def test_log_is_jsonl(self, tmp_path):
        log_path = tmp_path / "history.jsonl"
        for i in range(3):
            profile = {"basics": {"name": f"User {i}", "languages": []},
                       "skills": [], "experience": [],
                       "metadata": {"language": "en", "confidence_scores": {}}}
            log_processing_run(f"/tmp/cv{i}.pdf", profile, "en", log_path=log_path)
        content = log_path.read_text()
        lines = [l for l in content.split("\n") if l]
        assert len(lines) == 3
        for line in lines:
            json.loads(line)  # Each line is valid JSON

    def test_read_history_returns_records(self, tmp_path):
        log_path = tmp_path / "history.jsonl"
        profile = {"basics": {"name": "X", "languages": []}, "skills": [],
                   "experience": [], "metadata": {"language": "de", "confidence_scores": {}}}
        log_processing_run("/tmp/x.pdf", profile, "de", log_path=log_path)
        records = read_history(log_path=log_path)
        assert len(records) == 1
        assert records[0]["language"] == "de"

    def test_format_history_table_empty(self):
        result = format_history_table([])
        assert "No processing history" in result or "history" in result.lower()

    def test_format_history_table_with_records(self, tmp_path):
        log_path = tmp_path / "history.jsonl"
        profile = {"basics": {"name": "Matthias K.", "languages": []},
                   "skills": [{"name": "sap", "category": "tools", "proficiency": "advanced"}],
                   "experience": [], "metadata": {"language": "de", "confidence_scores": {}}}
        log_processing_run("/tmp/matthias.pdf", profile, "de", log_path=log_path)
        records = read_history(log_path=log_path)
        table = format_history_table(records)
        assert "matthias" in table.lower() or "Matthias" in table


class TestGermanRouteToGermanNlp:
    """Entity extraction should route de-language CVs to de_core_news_sm."""

    def test_extract_entities_with_de_language(self):
        sections = {
            "header": "Matthias K.\nÖsterreich\n",
            "languages": "Deutsch\nUngarisch",
        }
        entities = extract_entities(sections, language="de")
        assert "languages" in entities
        # German spaCy should at least run without crashing
        # (name may or may not match depending on model — just verify no exception)
        assert "name" in entities

    def test_extract_entities_with_en_language(self):
        sections = {
            "header": "Sarah Chen\nsarah.chen@example.com\nVienna, Austria",
        }
        entities = extract_entities(sections, language="en")
        assert entities["name"] == "Sarah Chen" or entities["name"] is not None
        assert entities["email"] == "sarah.chen@example.com"
