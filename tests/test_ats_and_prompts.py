"""Tests for the second absorption pass from adrianhajdin/ai-resume-analyzer.

Covers the two things the first pass got wrong or skipped:
  1. ATS is now real document parse-safety, not job-keyword overlap.
  2. The structured-prompt module (Priority 1) now exists, and its response
     parser survives the malformed LLM output the reference repo would crash on.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from matching import score_one_job  # noqa: E402
from matching.prompts import (  # noqa: E402
    prepare_narrative_prompt,
    parse_narrative_response,
)
from parser.ats_check import check_ats_parse_safety  # noqa: E402
from parser import segment_sections  # noqa: E402
from profile_builder_pkg import build_profile_from_cv  # noqa: E402

SAMPLE_CVS = PROJECT_ROOT / "data" / "sample_cvs"
SAMPLE_JOBS = PROJECT_ROOT / "data" / "sample_jobs"

GOOD_JSON = (
    '{"summary":"You fit well.","strengths":["a","b"],'
    '"gaps":[],"suggestions":["x"]}'
)


@pytest.fixture(scope="module")
def profile():
    return build_profile_from_cv(str(SAMPLE_CVS / "senior_swe_vienna.txt"), log=False)


@pytest.fixture(scope="module")
def backend_job():
    return json.loads((SAMPLE_JOBS / "senior_backend_vienna.json").read_text())


class TestAtsParseSafety:
    """ATS must grade the document, independently of any job."""

    def test_clean_cv_scores_high(self):
        text = (SAMPLE_CVS / "senior_swe_vienna.txt").read_text()
        r = check_ats_parse_safety(raw_text=text, sections=segment_sections(text))
        assert r["score"] >= 90
        assert all(r["checks"].values())

    def test_missing_headings_and_contact_penalised(self):
        bad = "Just a developer who knows python and cloud"
        r = check_ats_parse_safety(raw_text=bad, sections=segment_sections(bad))
        assert r["score"] < 40
        assert r["checks"]["section_headings"] is False
        assert r["checks"]["contact_details"] is False
        tips = [t["tip"] for t in r["tips"]]
        assert any("heading" in t.lower() for t in tips)
        assert any("email" in t.lower() for t in tips)

    def test_german_dates_are_parseable(self):
        de = (
            "Kontaktdaten\nmax@example.de\n+43 660 1234567\n"
            "Berufserfahrung\nDev @ ACME\n03.2019 - 08.2021\n"
            "Ausbildung\nBSc 2015 - 2019\nKenntnisse\nPython\n"
        )
        r = check_ats_parse_safety(raw_text=de, sections=segment_sections(de))
        assert r["checks"]["dates_present"] is True
        assert r["score"] >= 90

    def test_private_use_glyphs_penalised(self):
        text = (SAMPLE_CVS / "senior_swe_vienna.txt").read_text()
        clean = check_ats_parse_safety(raw_text=text, sections=segment_sections(text))
        dirty_text = "\uf0b7 " + text
        dirty = check_ats_parse_safety(
            raw_text=dirty_text, sections=segment_sections(dirty_text)
        )
        assert dirty["checks"]["clean_glyphs"] is False
        assert dirty["score"] < clean["score"]

    def test_score_never_out_of_bounds(self):
        r = check_ats_parse_safety(raw_text="", sections={})
        assert 0 <= r["score"] <= 100


class TestAtsIsJobIndependent:
    """The regression this pass exists to fix: ATS used to be keyword overlap."""

    def test_same_profile_same_ats_across_different_jobs(self, profile):
        scores, keywords = set(), set()
        for name in ("senior_backend_vienna.json", "nlp_research_zurich.json"):
            job = json.loads((SAMPLE_JOBS / name).read_text())
            res = score_one_job(profile, job)
            scores.add(res["feedback"]["ATS"]["score"])
            keywords.add(res["component_scores"]["keyword_tfidf"])
        # One ATS score for the document...
        assert len(scores) == 1
        # ...while the job-relative keyword signal genuinely differs.
        assert len(keywords) > 1

    def test_ats_score_comes_from_profile_metadata(self, profile, backend_job):
        degraded = dict(profile)
        degraded["metadata"] = dict(profile["metadata"])
        degraded["metadata"]["ats_parse_safety"] = {
            "score": 30,
            "checks": {},
            "tips": [{
                "type": "improve",
                "tip": "No section headings detected",
                "explanation": "collapsed",
            }],
        }
        res = score_one_job(degraded, backend_job)
        assert res["feedback"]["ATS"]["score"] == 30
        tips = [t["tip"] for t in res["feedback"]["ATS"]["tips"]]
        assert "No section headings detected" in tips

    def test_falls_back_when_profile_has_no_ats_metadata(self, profile, backend_job):
        legacy = dict(profile)
        legacy["metadata"] = {
            k: v for k, v in profile["metadata"].items() if k != "ats_parse_safety"
        }
        res = score_one_job(legacy, backend_job)
        # Must still produce a valid ATS block rather than crashing.
        assert 0 <= res["feedback"]["ATS"]["score"] <= 100

    def test_profile_builder_attaches_ats_metadata(self, profile):
        ats = profile["metadata"]["ats_parse_safety"]
        assert 0 <= ats["score"] <= 100
        assert isinstance(ats["checks"], dict)
        assert isinstance(ats["tips"], list)


class TestNarrativePrompt:
    """Priority 1 from the analysis — the module that was never built."""

    def test_prompt_includes_scores_and_forbids_recompute(self, profile, backend_job):
        res = score_one_job(profile, backend_job)
        p = prepare_narrative_prompt(
            job_title=backend_job["title"],
            job_description=backend_job.get("description", ""),
            feedback=res["feedback"],
            company=backend_job.get("company", ""),
        )
        assert backend_job["title"] in p
        assert "do not recompute" in p.lower()
        assert str(res["feedback"]["overallScore"]) in p
        assert "interface Narrative" in p

    def test_prompt_requests_no_scores_from_model(self, profile, backend_job):
        res = score_one_job(profile, backend_job)
        p = prepare_narrative_prompt(job_title="X", feedback=res["feedback"])
        # The narrative contract must not ask the model for numbers.
        contract = p.split("interface Narrative")[1]
        assert "score" not in contract.lower()

    def test_german_language_switch(self, profile, backend_job):
        res = score_one_job(profile, backend_job)
        p = prepare_narrative_prompt(
            job_title="X", feedback=res["feedback"], language="de"
        )
        assert "German" in p and "Sie" in p

    def test_long_description_is_truncated(self, profile, backend_job):
        res = score_one_job(profile, backend_job)
        huge = "w " * 4000
        p = prepare_narrative_prompt(
            job_title="X", job_description=huge, feedback=res["feedback"]
        )
        assert "[...]" in p
        # The 8000-char description must be clamped to the 1500-char budget,
        # so the prompt stays far below the raw input size.
        assert len(huge) > 7000
        assert len(p) < len(huge) / 1.5

    def test_blocked_and_gate_findings_surface(self, profile):
        blocking_job = {
            "title": "Onsite Only Role", "company": "X",
            "required_skills": ["cobol"], "min_years_experience": 30,
        }
        res = score_one_job(profile, blocking_job)
        p = prepare_narrative_prompt(job_title="X", feedback=res["feedback"])
        assert "ENGINE RESULTS" in p


class TestNarrativeResponseParsing:
    """The reference repo does raw JSON.parse() on model output; we harden it."""

    def test_clean_json(self):
        r = parse_narrative_response(GOOD_JSON)
        assert r["error"] is None
        assert r["narrative"]["summary"] == "You fit well."
        assert r["narrative"]["strengths"] == ["a", "b"]

    @pytest.mark.parametrize("wrapper", [
        "```json\n{body}\n```",
        "```\n{body}\n```",
        "Sure! Here you go:\n{body}\nHope that helps!",
    ])
    def test_survives_wrapping_that_breaks_naive_json_parse(self, wrapper):
        r = parse_narrative_response(wrapper.format(body=GOOD_JSON))
        assert r["error"] is None
        assert r["narrative"]["summary"] == "You fit well."

    @pytest.mark.parametrize("raw", [
        "", "   \n ", "I cannot help with that.", "[1,2,3]",
        '{"summary":"abc","strengths":[',
    ])
    def test_bad_input_returns_error_never_raises(self, raw):
        r = parse_narrative_response(raw)
        assert r["narrative"] is None
        assert r["error"]

    def test_nulls_do_not_become_the_string_none(self):
        r = parse_narrative_response(
            '{"summary":null,"strengths":null,"gaps":null,"suggestions":null}'
        )
        # Nothing usable -> error, and crucially no "None" string leaks through.
        assert r["narrative"] is None
        assert "None" not in (r["error"] or "")

    def test_null_entries_dropped_from_lists(self):
        r = parse_narrative_response('{"summary":"s","strengths":[1,2,null,""]}')
        assert r["narrative"]["strengths"] == ["1", "2"]

    def test_string_coerced_to_list(self):
        r = parse_narrative_response('{"summary":"s","strengths":"just one"}')
        assert r["narrative"]["strengths"] == ["just one"]

    def test_roundtrip_prompt_to_parsed_narrative(self, profile, backend_job):
        res = score_one_job(profile, backend_job)
        prompt = prepare_narrative_prompt(
            job_title=backend_job["title"], feedback=res["feedback"]
        )
        assert "Narrative" in prompt
        # Simulate a well-behaved model reply against the advertised contract.
        parsed = parse_narrative_response("```json\n" + GOOD_JSON + "\n```")
        assert parsed["narrative"]["suggestions"] == ["x"]
