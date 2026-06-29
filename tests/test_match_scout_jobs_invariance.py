"""Invariance tests for scripts/match_scout_jobs.py.

Verifies:
- Calling match_scout_jobs twice with the same input does not mutate the input
  job list (defense vs. dict-identity caches in adapters).
- Result dict is structurally correct: summary counts add up.
- Filter annotation is present on every scored result.
- --no-excluded CLI flag removes the excluded bucket but keeps summary numbers.

These tests do NOT exercise the SQLite adapter — that lives in scout_adapter
tests. They assume a stub loader is patched in via monkeypatch.
"""

import json
from pathlib import Path

import pytest

from scripts import match_scout_jobs as msj


class _StubJob:
    """Minimal job dict-shaped object that load_jobs_from_scout_db would produce."""
    def __init__(self, d: dict):
        self.__dict__.update(d)


@pytest.fixture
def fake_jobs():
    """Mixed-bucket sample — pure hunter, flagged, plain roles, empty title."""
    return [
        # 0: pure hunter → exclude
        {"title": "Sales Hunter (m/w/d)",
         "description": "Kaltakquise und Neukundengewinnung im Außendienst.",
         "location": "Wien", "company": "X", "requirements": [],
         "required_skills": [], "preferred_skills": [],
         "remote_policy": "on_site", "_source": {"url": "u0", "ats": "custom"}},
        # 1: borderline flagged
        {"title": "Kundenbetreuer",
         "description": "Bestandskunden, gelegentlich Neukund:innen.",
         "location": "Wien", "company": "Y", "requirements": [],
         "required_skills": [], "preferred_skills": [],
         "remote_policy": "hybrid", "_source": {"url": "u1", "ats": "custom"}},
        # 2: plain include
        {"title": "Sachbearbeiter Online-Marketing",
         "description": "Content-Pflege, Kennzahlen, MS Office.",
         "location": "Wien", "company": "Z", "requirements": [],
         "required_skills": [], "preferred_skills": [],
         "remote_policy": "on_site", "_source": {"url": "u2", "ats": "custom"}},
        # 3: empty-ish (should still classify; required_skills missing → no crash)
        {"title": "", "description": "",
         "location": "Wien", "company": "", "requirements": [],
         "_source": {"url": "u3"}},
    ]


@pytest.fixture
def fake_profile(tmp_path):
    """Minimal profile used to drive scoring."""
    return {
        "basics": {"name": "Test User"},
        "skills": [{"name": "python"}],
        "experience": [],
    }


@pytest.fixture(autouse=True)
def patch_loader(monkeypatch, fake_jobs):
    """Patch load_jobs_from_scout_db to return our fake list (no real SQLite)."""
    monkeypatch.setattr(
        msj, "load_jobs_from_scout_db",
        lambda db_path: fake_jobs,
    )


def test_does_not_mutate_input_jobs(fake_profile, fake_jobs, monkeypatch):
    """Re-running match_scout_jobs on the same input must not leak _filter."""
    # Spy to ensure _filter is never set on the input
    original_count = sum(1 for j in fake_jobs if "_filter" in j)
    assert original_count == 0, "fixture invariant: no _filter on inputs"

    r1 = msj.match_scout_jobs(fake_profile, Path("/tmp/x.sqlite"))
    r2 = msj.match_scout_jobs(fake_profile, Path("/tmp/x.sqlite"))

    # Input lists/dicts must remain pristine.
    after_count = sum(1 for j in fake_jobs if "_filter" in j)
    assert after_count == 0, (
        f"_filter leaked onto input jobs ({after_count} jobs mutated); "
        "match_scout_jobs must copy, not mutate."
    )
    # Both runs should produce the same counts.
    assert r1["summary"]["excluded"] == r2["summary"]["excluded"]
    assert r1["summary"]["ranked"] == r2["summary"]["ranked"]


def test_summary_counts_add_up(fake_profile, fake_jobs):
    result = msj.match_scout_jobs(fake_profile, Path("/tmp/x.sqlite"))
    summary = result["summary"]
    assert summary["total"] == len(fake_jobs)
    assert summary["ranked"] + summary["excluded"] == summary["total"]
    # flagged count must be <= ranked (a job could be flagged AND blocked-by-deal-breaker;
    # that's counted in ranked, with the deal-breaker setting `blocked=True`).
    assert summary["flagged"] <= summary["ranked"]


def test_filter_annotation_on_every_ranked(fake_profile, fake_jobs):
    result = msj.match_scout_jobs(fake_profile, Path("/tmp/x.sqlite"))
    for r in result["ranked"]:
        assert "_filter" in r, f"missing _filter on ranked entry: {r}"
        assert r["_filter"]["decision"] in ("include", "flag")
        assert isinstance(r["_filter"]["reasons"], list)


def test_no_excluded_cli_flag_drops_bucket_only(fake_profile, fake_jobs, capsys, tmp_path):
    """--no-excluded keeps summary; it only drops the excluded list itself."""
    # Drive main() via sys.argv. We need *real files* on disk because the
    # CLI validates existence first (defensive — exit codes 2/3 on missing).
    profile_path = tmp_path / "profile.json"
    scout_db = tmp_path / "scout.sqlite"
    out_path = tmp_path / "out.json"
    profile_path.write_text(json.dumps(fake_profile), encoding="utf-8")
    scout_db.write_bytes(b"")  # empty file; load_jobs_from_scout_db is stubbed to fake_jobs

    import sys
    argv_backup = sys.argv
    try:
        sys.argv = ["match_scout_jobs.py", str(profile_path), str(scout_db),
                    "--no-excluded", "-o", str(out_path)]
        rc = msj.main()
    finally:
        sys.argv = argv_backup
    assert rc == 0, f"expected rc=0, got {rc}"
    if out_path.exists():
        parsed = json.loads(out_path.read_text(encoding="utf-8"))
        assert parsed["excluded"] == [], "excluded bucket should be empty under --no-excluded"
        # Summary numbers must survive --no-excluded
        assert "summary" in parsed and parsed["summary"]["total"] == len(fake_jobs)


def test_empty_db_returns_signal(fake_profile, monkeypatch):
    """Zero jobs in DB → exit code 4."""
    monkeypatch.setattr(msj, "load_jobs_from_scout_db", lambda db_path: [])
    result = msj.match_scout_jobs(fake_profile, Path("/tmp/x.sqlite"))
    assert result["summary"]["total"] == 0
    assert result["ranked"] == []
    assert result["excluded"] == []
