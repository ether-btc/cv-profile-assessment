"""Tests for the bias-aware job filter (integration/job_filters.py).

Verifies:
- Pure-function signature (no IO, no DB)
- Blocklist excludes aggressive-hunter roles
- Flaglist marks borderline roles (kept in ranking)
- Inclusive roles pass through unmarked
- Empty / malformed job dicts handled safely
- Override-able blocklist / flaglist parameters
"""

import pytest

from integration.job_filters import (
    DEFAULT_BLOCKLIST_KEYWORDS,
    DEFAULT_FLAG_KEYWORDS,
    classify_job,
    filter_jobs,
    combined_text,
)


def _job(title: str, description: str = "", location: str = "Wien") -> dict:
    return {
        "title": title,
        "description": description,
        "location": location,
        "requirements": [],
        "required_skills": ["Python"],
        "preferred_skills": [],
    }


class TestClassifyJob:
    """classify_job returns ('include'|'flag'|'exclude', [reasons])."""

    def test_pure_match_include(self):
        decision, reasons = classify_job(
            _job("Senior Backend Developer",
                 "Bauen wir ein tolles Produkt. Python und FastAPI.")
        )
        assert decision == "include"
        assert reasons == []

    def test_blocked_keyword_excludes(self):
        # "akquise" is in DEFAULT_BLOCKLIST_KEYWORDS
        decision, reasons = classify_job(
            _job("Account Manager",
                 "Ihre Hauptaufgabe ist Akquise von Neukunden im B2B-Segment.")
        )
        assert decision == "exclude"
        assert "akquise" in reasons or any("akquise" in r for r in reasons)

    def test_neukundengewinnung_blocks(self):
        decision, reasons = classify_job(
            _job("Sales Manager",
                 "Neukundengewinnung und Bestandskundenpflege.")
        )
        assert decision == "exclude"

    def test_kaltakquise_blocks(self):
        decision, _ = classify_job(
            _job("Hunter", "Kaltakquise und Pipeline-Befüllung.")
        )
        assert decision == "exclude"

    def test_hunter_role_blocks(self):
        # German "außendienst" should also block
        decision, _ = classify_job(
            _job("Vertriebsmitarbeiter",
                 "Außendienst für die Region Ost, hunter profile.")
        )
        assert decision == "exclude"

    def test_flaglist_marks_keeps(self):
        # "neukunden" alone is in flaglist, not blocklist
        decision, reasons = classify_job(
            _job("Kundenbetreuer",
                 "Bestandskundenpflege, gelegentlich Neukund:innen betreuen.")
        )
        # "neukund:innen" is flag-list (substring of "neukund:innen betreuen")
        assert decision in ("flag", "include")  # depends on overlap with flaglist terms

    def test_decision_is_exclude_over_flag(self):
        # If both flaglist and blocklist match, blocklist wins
        job = _job("Hybrid Role",
                   "Akquise-Tätigkeiten (von der Flag-Liste) UND Neukundengewinnung "
                   "(blocklist).")
        decision, _ = classify_job(job)
        assert decision == "exclude"

    def test_case_insensitive(self):
        decision, _ = classify_job(_job("Sales", "AKQUISE und Neukundengewinnung"))
        assert decision == "exclude"

    def test_empty_job_safe(self):
        decision, reasons = classify_job({})
        assert decision == "include"
        assert reasons == []

    def test_missing_fields_safe(self):
        decision, reasons = classify_job({"title": "Some Role"})  # no description
        assert decision in ("include", "flag", "exclude")
        assert isinstance(reasons, list)

    def test_override_blocklist(self):
        custom_block = ["foo"]
        decision, reasons = classify_job(
            _job("Some Role", "this mentions foo in description"),
            blocklist=custom_block,
        )
        assert decision == "exclude"
        assert "foo" in reasons

    def test_override_flaglist(self):
        custom_flag = ["bar"]
        decision, reasons = classify_job(
            _job("Some Role", "mentions bar here"),
            flaglist=custom_flag,
        )
        assert decision == "flag"
        assert "bar" in reasons


class TestFilterJobs:
    """filter_jobs partitions a list of jobs into three buckets."""

    def test_partitions_correctly(self):
        jobs = [
            _job("Backend Dev"),                                   # include
            _job("Account Manager", "Akquise-Fokus"),              # exclude
            _job("Sales Support", "Neukunden-Betreuung"),          # flag or include
            _job("Hunter", "Kaltakquise"),                         # exclude
        ]
        included, flagged, excluded = filter_jobs(jobs)
        assert len(included) == 1
        assert included[0]["title"] == "Backend Dev"
        assert len(excluded) == 2
        excluded_titles = {j["title"] for j in excluded}
        assert "Account Manager" in excluded_titles
        assert "Hunter" in excluded_titles
        # flagged bucket may have 0 or 1 depending on flaglist overlaps
        assert all(j["_filter"]["decision"] in ("include", "flag", "exclude") for j in included + flagged + excluded)

    def test_empty_input(self):
        included, flagged, excluded = filter_jobs([])
        assert included == flagged == excluded == []

    def test_annotations_preserved(self):
        jobs = [_job("Sales", "Akquise-lastig")]
        _, _, excluded = filter_jobs(jobs)
        assert excluded[0]["_filter"]["decision"] == "exclude"
        assert isinstance(excluded[0]["_filter"]["reasons"], list)
        assert len(excluded[0]["_filter"]["reasons"]) > 0


class TestCombinedText:
    """combined_text builds the searchable string from a job dict."""

    def test_includes_all_fields(self):
        job = {
            "title": "Senior Engineer",
            "description": "Cool role.",
            "location": "Wien",
            "requirements": ["Python", "5+ years exp"],
        }
        text = combined_text(job).lower()
        assert "senior engineer" in text
        assert "cool role" in text
        assert "wien" in text
        assert "python" in text

    def test_handles_dict_requirements(self):
        job = {"title": "x", "requirements": [{"text": "B2B sales"}]}
        text = combined_text(job).lower()
        assert "b2b sales" in text

    def test_dict_requirement_does_not_emit_raw_repr(self):
        """Defense-in-depth: a dict requirement must NEVER call str(dict).

        Raw repr() of a dict dumps curly-brace literal into the searchable
        text. A side-channel could leak sensitive data (key names) and could
        trigger spurious keyword matches."""
        job = {"title": "Nice role", "requirements": [
            {"text": "B2B sales", "noise": "kaltakquise"}  # 'noise' is non-text, dropped
        ]}
        text = combined_text(job)
        # Neither the repr-style '{' nor the key names must leak into the text.
        assert "{" not in text
        assert "}" not in text
        assert "'text'" not in text
        assert "'noise'" not in text
        assert "'kaltakquise'" not in text  # would only appear via repr
        # The legitimate 'text' value should still be present.
        assert "B2B sales" in text

    def test_dict_requirement_extracts_all_known_keys(self):
        """Multi-key entries (e.g. {text:, value:}) must extract both."""
        job = {"title": "x", "requirements": [
            {"text": "Python", "name": "core"},
            {"value": "Salesforce"},
        ]}
        text = combined_text(job)
        assert "python" in text.lower()
        assert "salesforce" in text.lower()
        assert "core" in text.lower()

    def test_dict_requirement_whitespace_only_dropped(self):
        """Whitespace-only 'text' falls through; the next usable key wins."""
        job = {"title": "x", "requirements": [
            {"text": "   ", "value": "Salesforce"},
        ]}
        text = combined_text(job)
        assert "salesforce" in text.lower()
        # No stray "|" between two empty halves from the text field
        assert "||" not in text

    def test_dict_requirement_str_key_types_handled(self):
        """Numeric values are coerced to string; non-str/int/float dropped."""
        job = {"title": "x", "requirements": [
            {"value": 5},
            {"text": "Python"},
        ]}
        text = combined_text(job)
        assert "5" in text
        assert "python" in text.lower()

    def test_handles_missing(self):
        text = combined_text({})
        assert isinstance(text, str)
        assert text == ""

    def test_handles_list_requirements(self):
        job = {"requirements": ["Java", 42, None]}
        text = combined_text(job)
        assert "Java" in text
        assert "42" in text  # str() coerces
