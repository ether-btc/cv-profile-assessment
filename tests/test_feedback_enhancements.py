"""Tests for the ai-job-search / ai-resume-analyzer inspired enhancements.

Covers: deterministic feedback (rubric + tips) wired into score_one_job,
the optional PDF→image renderer, and UUID-keyed history + wipe.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from matching import score_one_job  # noqa: E402
from matching.feedback_schema import feedback_to_text, build_feedback_dict  # noqa: E402
from matching.tips import generate_tips  # noqa: E402
from matching.gates import check_eligibility_gate, check_language_gate  # noqa: E402
from profile_builder_pkg import build_profile_from_cv  # noqa: E402
from cv_profile_assessment import read_history  # noqa: E402
from cv_profile_assessment.usage_history import (  # noqa: E402
    log_processing_run,
    wipe_history,
    DEFAULT_LOG_PATH,
)
from parser.pdf_extractor import extract_text_from_pdf  # noqa: E402
from parser.pdf_renderer import render_first_page  # noqa: E402

SAMPLE_CVS = PROJECT_ROOT / "data" / "sample_cvs"
SAMPLE_JOBS = PROJECT_ROOT / "data" / "sample_jobs"


class TestFeedbackWiredIntoPipeline:
    """The explainable feedback block must ride along with every score."""

    @pytest.fixture
    def senior_profile(self):
        return build_profile_from_cv(str(SAMPLE_CVS / "senior_swe_vienna.txt"))

    @pytest.fixture
    def backend_job(self):
        return json.loads((SAMPLE_JOBS / "senior_backend_vienna.json").read_text())

    def test_score_one_job_returns_feedback_block(self, senior_profile, backend_job):
        result = score_one_job(senior_profile, backend_job)
        assert "feedback" in result, "score_one_job must attach a feedback block"
        fb = result["feedback"]
        for dim in ("ATS", "toneAndStyle", "content", "structure", "skills"):
            assert dim in fb, f"feedback missing dimension {dim}"
            assert isinstance(fb[dim]["score"], int)
            assert isinstance(fb[dim]["tips"], list)
        # overallScore present and 0-100
        assert 0 <= fb["overallScore"] <= 100

    def test_blocked_job_feedback_flags_block(self, senior_profile, backend_job):
        # Force a deal-breaker that actually appears in the posting text.
        backend_job["description"] = "Must be based in Vienna, Austria."
        senior_profile["preferences"]["deal_breakers"] = ["vienna"]
        result = score_one_job(senior_profile, backend_job)
        assert result["blocked"] is True
        fb = result["feedback"]
        assert fb.get("blocked") is True
        # ATS tips should mention the deal-breaker
        assert any("Deal-breaker" in t["tip"] or "deal" in t["tip"].lower()
                   for t in fb["ATS"]["tips"])

    def test_feedback_to_text_renders(self, senior_profile, backend_job):
        result = score_one_job(senior_profile, backend_job)
        text = feedback_to_text(result["feedback"])
        assert "Overall Score" in text
        assert "Skills" in text
        # feedback_to_text resolves casing; the stored key is uppercase "ATS".
        assert "ATS" in result["feedback"]

    def test_ats_score_is_document_property_not_keyword_overlap(self, senior_profile):
        """Regression: ATS must be stable across jobs and equal to the profile's
        ats_parse_safety score — not the per-job keyword overlap."""
        ats_meta = senior_profile["metadata"]["ats_parse_safety"]
        jobs = [
            json.loads((SAMPLE_JOBS / "senior_backend_vienna.json").read_text()),
            json.loads((SAMPLE_JOBS / "nlp_research_zurich.json").read_text()),
        ]
        scores = {score_one_job(senior_profile, j)["feedback"]["ATS"]["score"]
                  for j in jobs}
        # Identical ATS for the same document against two different jobs.
        assert len(scores) == 1
        # And it must equal the value computed at parse time.
        assert scores.pop() == ats_meta["score"]



class TestTipsAreExplainable:
    """Tips must name concrete missing skills, not be generic placeholders."""

    def test_missing_required_skills_named(self):
        profile = {"skills": [{"name": "python"}]}
        job = {"required_skills": ["rust", "kubernetes"], "preferred_skills": []}
        tips = generate_tips(
            profile=profile, job=job,
            component_scores={"required_skills": 0.3, "experience": 0.5,
                              "preferred": 0.0, "keyword_tfidf": 0.4},
        )
        # The missing skills must appear in the skills dimension tips
        # (title or explanation).
        skills_blob = " ".join(
            f"{t['tip']} {t.get('explanation', '')}" for t in tips["skills"]
        )
        assert "rust" in skills_blob and "kubernetes" in skills_blob


class TestPdfRenderer:
    """PDF→image is optional (fitz); test when available, skip gracefully."""

    def test_render_first_page_optional(self, tmp_path):
        # Create a tiny PDF from sample text via pdfminer is not trivial; instead
        # test the missing-file path and the graceful no-fitz path without a PDF.
        missing = tmp_path / "nope.pdf"
        with pytest.raises(FileNotFoundError):
            render_first_page(missing)

    def test_render_existing_pdf_if_fitz(self, tmp_path):
        # Try to find any sample PDF in the repo to exercise the happy path.
        pdfs = list(PROJECT_ROOT.rglob("*.pdf"))
        if not pdfs:
            pytest.skip("no sample PDF in repo to render")
        out = tmp_path / "page1.png"
        res = render_first_page(pdfs[0], out)
        if res["error"] and "PyMuPDF" in res["error"]:
            pytest.skip("PyMuPDF not installed")
        assert res["error"] is None, res["error"]
        assert Path(res["image_path"]).exists()


class TestHistoryUuidAndWipe:
    """UUID-keyed records + a wipe helper, mirroring the reference wipe route."""

    def test_log_writes_profile_id(self, tmp_path, monkeypatch):
        log = tmp_path / "hist.jsonl"
        monkeypatch.setattr(
            "cv_profile_assessment.usage_history.DEFAULT_LOG_PATH", log
        )
        rec = log_processing_run(
            source_path="x.pdf",
            profile={"basics": {"name": "A", "email": "a@b.c"},
                     "skills": [], "experience": []},
            log_path=log,
        )
        assert "profile_id" in rec and len(rec["profile_id"]) >= 32
        lines = log.read_text().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["profile_id"] == rec["profile_id"]

    def test_wipe_history_removes_file(self, tmp_path, monkeypatch):
        log = tmp_path / "hist.jsonl"
        log.write_text('{"a":1}\n')
        monkeypatch.setattr(
            "cv_profile_assessment.usage_history.DEFAULT_LOG_PATH", log
        )
        freed = wipe_history(log)
        assert freed > 0
        assert not log.exists()
        assert wipe_history(log) == 0  # idempotent on missing file


class TestGatesAndVerdict:
    """Eligibility/Language gates + verdict bands (from ai-job-search pattern)."""

    @pytest.fixture
    def senior_profile(self):
        return build_profile_from_cv(str(SAMPLE_CVS / "senior_swe_vienna.txt"))

    @pytest.fixture
    def backend_job(self):
        return json.loads((SAMPLE_JOBS / "senior_backend_vienna.json").read_text())

    def test_verdict_band_attached(self, senior_profile, backend_job):
        r = score_one_job(senior_profile, backend_job)
        assert "verdict" in r
        assert r["verdict"] in {
            "Strong Fit", "Good Fit", "Moderate Fit", "Weak Fit", "Poor Fit",
        }
        assert r["feedback"]["verdict"] == r["verdict"]

    def test_language_gate_fail_when_required_lang_undeclared(self):
        profile = {"basics": {"languages": [{"language": "English", "fluency": "B2"}]}}
        job = {"title": "Dev", "description": "Fluency in Polish required."}
        verdict, note = check_language_gate(profile, job)
        assert verdict == "FAIL"
        assert "polish" in note.lower()

    def test_language_gate_pass_when_declared(self):
        profile = {"basics": {"languages": [{"language": "German", "fluency": "C1"}]}}
        job = {"title": "Dev", "description": "German required at C1 level."}
        verdict, note = check_language_gate(profile, job)
        assert verdict == "PASS"

    def test_eligibility_gate_fail_on_citizenship(self):
        profile = {"basics": {}}
        job = {"title": "Dev", "description": "Must be a US citizen or permanent resident."}
        verdict, note = check_eligibility_gate(profile, job)
        assert verdict == "FAIL"

    def test_eligibility_gate_pass_on_sponsorship(self):
        profile = {"basics": {}}
        job = {"title": "Dev", "description": "We sponsor visas; international applicants welcome."}
        verdict, _ = check_eligibility_gate(profile, job)
        assert verdict == "PASS"

    def test_gates_present_in_result(self, senior_profile, backend_job):
        r = score_one_job(senior_profile, backend_job)
        assert "gates" in r
        assert "eligibility_gate" in r["gates"] and "language_gate" in r["gates"]
        # And surfaced inside feedback
        assert "eligibility_gate" in r["feedback"]
        assert r["feedback"]["eligibility_gate"]["verdict"] == \
            r["gates"]["eligibility_gate"]["verdict"]


class TestPdfFeedbackRendering:
    """match_to_pdf should embed the feedback block when present."""

    def test_match_to_pdf_renders_feedback(self, tmp_path):
        from scripts.match_to_pdf import render_pdf
        from profile_builder_pkg import build_profile_from_cv
        from matching import score_one_job

        profile = build_profile_from_cv(str(SAMPLE_CVS / "senior_swe_vienna.txt"))
        job = json.loads((SAMPLE_JOBS / "senior_backend_vienna.json").read_text())
        scored = score_one_job(profile, job)
        # Wrap in the shape match_to_pdf expects.
        payload = {
            "summary": {"total": 1, "ranked": 1},
            "ranked": [scored],
            "excluded": [],
        }
        json_path = tmp_path / "match.json"
        json_path.write_text(json.dumps(payload), encoding="utf-8")
        out = tmp_path / "out.pdf"
        n = render_pdf(json_path, out, include_only=False, exclude_flagged=False)
        assert n >= 1
        assert out.exists()

