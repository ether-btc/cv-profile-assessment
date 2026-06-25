"""Tests for the austria-job-scout → cv-profile-assessment integration.

Two layers:
1. Unit tests on field mappers (remote_policy_to_bool, normalize_seniority,
   extract_min_years, parse_skills_json) — fast, no I/O.
2. Integration tests that build a synthetic scout DB, run the adapter,
   and verify the full pipeline (match_scout_jobs) ranks correctly.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from integration.scout_adapter import (  # noqa: E402
    adapt_austria_jobs_row,
    adapt_indexed_job,
    extract_min_years,
    load_jobs_from_scout_db,
    normalize_seniority,
    parse_skills_json,
    remote_policy_to_bool,
)
from scripts.match_scout_jobs import match_scout_jobs  # noqa: E402
from scripts.seed_scout_db_from_samples import build_db  # noqa: E402

SCHEMA_PATH = PROJECT_ROOT / "tests" / "fixtures" / "scout_schema.sql"
SAMPLES_DIR = PROJECT_ROOT / "data" / "sample_jobs"
PROFILES_DIR = PROJECT_ROOT / "data" / "sample_profiles"


# ---------------------------------------------------------------------------
# Field mapper unit tests
# ---------------------------------------------------------------------------

class TestRemotePolicyMapping(unittest.TestCase):
    def test_remote_true(self):
        self.assertTrue(remote_policy_to_bool("remote"))

    def test_hybrid_true(self):
        # hybrid is at-least-partly-remote
        self.assertTrue(remote_policy_to_bool("hybrid"))

    def test_onsite_false(self):
        self.assertFalse(remote_policy_to_bool("on_site"))

    def test_unknown_false(self):
        # Conservative: unknown → not remote (don't mislead)
        self.assertFalse(remote_policy_to_bool("unknown"))

    def test_none_false(self):
        self.assertFalse(remote_policy_to_bool(None))

    def test_case_insensitive(self):
        self.assertTrue(remote_policy_to_bool("REMOTE"))


class TestSeniorityNormalization(unittest.TestCase):
    def test_canonical_values_passthrough(self):
        for v in ("junior", "mid", "senior", "lead", "staff", "principal"):
            self.assertEqual(normalize_seniority(v), v)

    def test_freeform_senior(self):
        self.assertEqual(normalize_seniority("Senior Engineer"), "senior")

    def test_freeform_lead(self):
        self.assertEqual(normalize_seniority("Lead Backend Developer"), "lead")

    def test_freeform_principal(self):
        self.assertEqual(normalize_seniority("Principal SWE"), "principal")

    def test_freeform_junior(self):
        self.assertEqual(normalize_seniority("Junior Developer"), "junior")

    def test_freeform_intern(self):
        self.assertEqual(normalize_seniority("Internship"), "junior")

    def test_freeform_mid(self):
        self.assertEqual(normalize_seniority("Mid-level Engineer"), "mid")

    def test_none(self):
        self.assertEqual(normalize_seniority(None), "")

    def test_empty(self):
        self.assertEqual(normalize_seniority(""), "")


class TestExtractMinYears(unittest.TestCase):
    def test_plus_pattern(self):
        self.assertEqual(extract_min_years("5+ years of experience required"), 5)

    def test_range_pattern(self):
        self.assertEqual(extract_min_years("3-5 years experience"), 3)

    def test_at_least_pattern(self):
        self.assertEqual(
            extract_min_years("At least 2 years in Python"), 2
        )

    def test_no_match_returns_zero(self):
        self.assertEqual(extract_min_years("No experience needed"), 0)

    def test_empty(self):
        self.assertEqual(extract_min_years(""), 0)

    def test_none(self):
        self.assertEqual(extract_min_years(None), 0)


class TestParseSkillsJson(unittest.TestCase):
    def test_valid_list(self):
        self.assertEqual(
            parse_skills_json('["python", "django", "aws"]'),
            ["python", "django", "aws"],
        )

    def test_empty_string(self):
        self.assertEqual(parse_skills_json(""), [])

    def test_none(self):
        self.assertEqual(parse_skills_json(None), [])

    def test_invalid_json(self):
        self.assertEqual(parse_skills_json("not json"), [])

    def test_non_list(self):
        # Defensive: should not crash
        self.assertEqual(parse_skills_json('{"k": "v"}'), [])

    def test_filters_empty_strings(self):
        self.assertEqual(parse_skills_json('["python", "", "rust"]'), ["python", "rust"])


# ---------------------------------------------------------------------------
# Row adapter tests
# ---------------------------------------------------------------------------

class TestAdaptRow(unittest.TestCase):
    """Test adapt_austria_jobs_row with a synthetic sqlite3.Row."""

    def _make_row(self, **overrides):
        """Build a sqlite3.Row matching the austria_jobs schema (in-memory)."""
        base = {
            "id": 1,
            "url": "https://example.com/job/1",
            "url_hash": "abc",
            "source_domain": "example.com",
            "ats": "greenhouse",
            "job_id_at_source": "GH-001",
            "title": "Backend Engineer",
            "company": "TestCo GmbH",
            "location": "Vienna",
            "postal_code": "1010",
            "country": "AT",
            "remote_policy": "hybrid",
            "employment_type": "full_time",
            "seniority": "senior",
            "salary_min": 70000,
            "salary_max": 95000,
            "salary_currency": "EUR",
            "salary_period": "yearly",
            "language": "en",
            "description": "Python + Django. 5+ years experience required.",
            "description_html": None,
            "skills_json": '["python", "django", "aws"]',
            "first_seen_at": 1000,
            "last_checked_at": 1000,
            "last_changed_at": 1000,
            "status": "active",
        }
        base.update(overrides)
        # In-memory DB — no temp files to clean up
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        cols = ",".join(base.keys())
        placeholders = ",".join(["?"] * len(base))
        conn.execute(f"CREATE TABLE austria_jobs ({cols})")
        conn.execute(f"INSERT INTO austria_jobs VALUES ({placeholders})", list(base.values()))
        row = conn.execute("SELECT * FROM austria_jobs").fetchone()
        conn.close()
        return row

    def test_basic_mapping(self):
        row = self._make_row()
        job = adapt_austria_jobs_row(row)
        self.assertEqual(job["title"], "Backend Engineer")
        self.assertEqual(job["company"], "TestCo GmbH")
        self.assertEqual(job["location"], "Vienna")
        self.assertTrue(job["remote"])  # hybrid → True
        self.assertEqual(job["seniority_level"], "senior")
        self.assertEqual(job["required_skills"], ["python", "django", "aws"])
        self.assertEqual(job["preferred_skills"], [])
        self.assertEqual(job["min_years_experience"], 5)  # from description
        self.assertEqual(job["salary_range"]["min"], 70000)
        self.assertEqual(job["salary_range"]["max"], 95000)
        self.assertEqual(job["salary_range"]["currency"], "EUR")
        self.assertEqual(job["salary_range"]["period"], "yearly")
        self.assertEqual(job["_source"]["url"], "https://example.com/job/1")
        self.assertEqual(job["_source"]["ats"], "greenhouse")

    def test_remote_onsite(self):
        row = self._make_row(remote_policy="on_site")
        job = adapt_austria_jobs_row(row)
        self.assertFalse(job["remote"])

    def test_remote_unknown_default_false(self):
        row = self._make_row(remote_policy="unknown")
        job = adapt_austria_jobs_row(row)
        self.assertFalse(job["remote"])

    def test_null_salary_safe(self):
        row = self._make_row(salary_min=None, salary_max=None)
        job = adapt_austria_jobs_row(row)
        self.assertIsNone(job["salary_range"]["min"])
        self.assertIsNone(job["salary_range"]["max"])
        # Currency defaults to EUR
        self.assertEqual(job["salary_range"]["currency"], "EUR")

    def test_invalid_skills_json_safe(self):
        row = self._make_row(skills_json="not valid json")
        job = adapt_austria_jobs_row(row)
        self.assertEqual(job["required_skills"], [])

    def test_min_years_default_zero(self):
        row = self._make_row(description="A fun role at a great company.")
        job = adapt_austria_jobs_row(row)
        self.assertEqual(job["min_years_experience"], 0)


# ---------------------------------------------------------------------------
# IndexedJob adapter test
# ---------------------------------------------------------------------------

class TestAdaptIndexedJob(unittest.TestCase):
    """Test adapt_indexed_job with a minimal mock object."""

    def test_minimal_indexed_job(self):
        class MockIndexed:
            job_id = "abc123"
            url = "https://example.com/j/1"
            title = "ML Engineer"
            company = "AILab"
            location = "Zurich"
            description = "PyTorch + NLP. 3+ years."
            skills = ["python", "pytorch", "nlp"]
            seniority = "senior"
            employment_type = "full_time"
            remote = True
            salary_min = 100000
            salary_max = 140000
            currency = "CHF"
            posted_date = "2026-06-01"

        job = adapt_indexed_job(MockIndexed())
        self.assertEqual(job["title"], "ML Engineer")
        self.assertTrue(job["remote"])
        self.assertEqual(job["required_skills"], ["python", "pytorch", "nlp"])
        self.assertEqual(job["min_years_experience"], 3)
        self.assertEqual(job["salary_range"]["currency"], "CHF")
        self.assertEqual(job["salary_range"]["period"], "yearly")


# ---------------------------------------------------------------------------
# End-to-end integration test
# ---------------------------------------------------------------------------

class TestEndToEnd(unittest.TestCase):
    """Build a synthetic scout DB from samples, then run the full pipeline."""

    @classmethod
    def setUpClass(cls):
        if not SCHEMA_PATH.exists():
            raise unittest.SkipTest(f"Scout schema fixture missing: {SCHEMA_PATH}")
        # Build a synthetic scout DB in a temp dir
        cls.tmpdir = tempfile.mkdtemp(prefix="cv-scout-it-")
        cls.db_path = Path(cls.tmpdir) / "scout.sqlite"

        samples = [
            json.loads(jf.read_text(encoding="utf-8"))
            for jf in sorted(SAMPLES_DIR.glob("*.json"))
        ]
        cls.row_count = build_db(SCHEMA_PATH, cls.db_path, samples)

        # Load Sarah Chen profile
        cls.sarah_profile_path = PROFILES_DIR / "senior_swe_vienna.json"
        if not cls.sarah_profile_path.exists():
            # Fallback: parse from raw CV text
            cls.sarah_profile_path = None
            cls.sarah_profile = None
        else:
            cls.sarah_profile = json.loads(cls.sarah_profile_path.read_text())

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_seeded_db_has_jobs(self):
        self.assertGreaterEqual(self.row_count, 4)

    def test_adapter_loads_all_jobs(self):
        jobs = load_jobs_from_scout_db(self.db_path)
        self.assertEqual(len(jobs), self.row_count)
        # Every adapted job has the required fields
        for job in jobs:
            self.assertIn("title", job)
            self.assertIn("company", job)
            self.assertIn("required_skills", job)
            self.assertIn("_source", job)

    def test_status_filter(self):
        # All our samples are 'active' so this is a smoke test
        active = load_jobs_from_scout_db(self.db_path, status="active")
        self.assertEqual(len(active), self.row_count)
        # status=None returns all
        all_jobs = load_jobs_from_scout_db(self.db_path, status=None)
        self.assertEqual(len(all_jobs), self.row_count)

    def test_missing_db_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_jobs_from_scout_db(Path(self.tmpdir) / "nonexistent.sqlite")

    @unittest.skipUnless(
        (PROFILES_DIR / "senior_swe_vienna.json").exists(),
        "Senior SWE profile not built yet",
    )
    def test_senior_profile_ranks_senior_backend_top(self):
        """Sarah Chen (senior SWE) → Senior Backend Engineer (Python) at top."""
        profile = json.loads(
            (PROFILES_DIR / "senior_swe_vienna.json").read_text()
        )
        results = match_scout_jobs(profile, self.db_path)
        self.assertGreater(len(results), 0)

        # Top non-blocked match should be the senior backend role
        unblocked = [r for r in results if not r["blocked"]]
        self.assertGreater(len(unblocked), 0, "No unblocked matches — pipeline broken")

        top = unblocked[0]
        self.assertIn("backend", top["job_title"].lower())
        self.assertGreaterEqual(top["overall_score"], 0.3)

        # All results have required fields
        for r in results:
            self.assertIn("overall_score", r)
            self.assertIn("blocked", r)

    @unittest.skipUnless(
        (PROFILES_DIR / "junior_fs_developer.json").exists(),
        "Junior FS profile not built yet",
    )
    def test_junior_profile_ranks_frontend_top(self):
        """Marcus Weber (junior FS) → Frontend Developer at top."""
        profile = json.loads(
            (PROFILES_DIR / "junior_fs_developer.json").read_text()
        )
        results = match_scout_jobs(profile, self.db_path)
        unblocked = [r for r in results if not r["blocked"]]
        self.assertGreater(len(unblocked), 0)
        top = unblocked[0]
        self.assertIn("frontend", top["job_title"].lower())


if __name__ == "__main__":
    unittest.main()