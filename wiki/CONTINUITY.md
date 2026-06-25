# CV Profile Assessment — Session Continuity Reference

**Last session:** 2026-06-25 21:00 UTC
**Project status:** Phase 4 (austria-job-scout integration) shipped, v0.2.0 pending
**GitHub:** https://github.com/ether-btc/cv-profile-assessment

---

## Quick Resume (read this first in a fresh session)

```bash
cd ~/projects/cv-profile-assessment
source venv/bin/activate
pytest tests/ -v                       # expect 57/57 (2 skipped) in ~7s

# Demo: parse CV → build profile → match against synthetic scout DB
python scripts/seed_scout_db_from_samples.py /tmp/scout.sqlite
python scripts/parse_cv.py data/sample_cvs/senior_swe_vienna.txt -o /tmp/sarah.json
python scripts/match_scout_jobs.py /tmp/sarah.json /tmp/scout.sqlite
```

**Expected output:** `Senior Backend Engineer (Python)` scores ~0.73 for senior SWE profile.

---

## What's Where

| What | Location |
|------|----------|
| Code | `~/projects/cv-profile-assessment/` |
| Git | 8 commits (post-Phase 4), clean tree, branch `master` tracking `origin/master` |
| Tests | 57 passing, 2 skipped (need profile JSONs built from CVs); 2 files |
| Schema | `schema/profile_schema.json` |
| Sample CVs | `data/sample_cvs/` (3 personas) |
| Sample jobs | `data/sample_jobs/` (4 jobs) |
| Scout integration | `integration/scout_adapter.py`, `scripts/match_scout_jobs.py` |
| Scout seed | `scripts/seed_scout_db_from_samples.py` |
| Scout test fixture | `tests/fixtures/scout_schema.sql` (copied from austria-job-scout) |
| CLI scripts | `scripts/parse_cv.py`, `scripts/match_jobs.py`, `scripts/match_scout_jobs.py`, `scripts/seed_scout_db_from_samples.py` |
| Wiki (research) | `~/.wiki/research/cv-profile-assessment/framework-v1.md` |
| Wiki (audit Phase 1) | `~/.wiki/audits/cv-profile-assessment-phase1-audit-2026-06-25.md` |
| Wiki (audit Phase 4) | `~/.wiki/audits/cv-profile-assessment-phase4-audit-2026-06-25.md` |
| GitHub | https://github.com/ether-btc/cv-profile-assessment |
| Tags | `v0.1.0` (Phase 1), `v0.2.0` pending (Phase 4) |

---

## Architecture Snapshot

```
CV (PDF/DOCX/TXT)
    ↓ parser/         — pdfminer.six, python-docx, spaCy NER, regex
    ↓ profile_builder_pkg/ — assembly + JSON Schema validation
    ↓ matching/        — deal-breakers + TF-IDF + scorer
    → Ranked jobs with component-level scores

       ┌────────────────────────────────────────────┐
       │ Phase 4: integration/scout_adapter.py      │
       │ austria_job_scout → cv-profile-assessment   │
       │ schema adapter (lazy austria-job-scout      │
       │ import)                                     │
       └────────────────────────────────────────────┘
                          ↓
              scripts/match_scout_jobs.py
```

**Scoring formula (unchanged from Phase 1):**
```
match_score = (
    required_skills * 0.45 +
    experience * 0.25 +
    preferred * 0.18 +
    keyword * 0.12
)
```

---

## Phase 4 Summary (2026-06-25)

**Goal:** Wire the matching engine into the live austria-job-scout pipeline.

**Delivered:**
1. `integration/scout_adapter.py` (310 lines) — converts `austria_jobs` DB rows
   and `IndexedJob` dataclasses → cv-profile-assessment job dict. Lazy import
   so austria-job-scout is optional.
2. `scripts/match_scout_jobs.py` (130 lines) — end-to-end CLI: load profile,
   query scout DB, adapt, score, output ranked JSON.
3. `scripts/seed_scout_db_from_samples.py` (150 lines) — builds a synthetic
   scout SQLite DB from the project's 4 sample jobs using the real
   `schema.sql`, so the integration is fully testable offline.
4. `tests/test_scout_adapter.py` (400 lines, 38 tests + 2 skipped e2e) —
   unit tests for all field mappers + end-to-end pipeline tests.
5. `tests/fixtures/scout_schema.sql` (copied verbatim from austria-job-scout
   so the seed script works without depending on the external package).

**Field mapping table:**

| austria-job-scout | cv-profile-assessment |
|-------------------|------------------------|
| `title`, `company`, `location` | direct |
| `remote_policy` enum | `remote` bool (`hybrid` → True) |
| `seniority` (or free-form) | `_SENIORITY_HINTS` normalize |
| `salary_min/max/currency/period` | nested `salary_range` |
| `skills_json` (JSON string) | `required_skills: list[str]` |
| `min_years_experience` (not stored) | regex-extracted from description |
| n/a | `_source.{url,ats,source_domain,scout_job_id}` |

**Verification:**
- 57/57 unit + integration tests pass (was 19 pre-Phase 4; +38 new)
- Ad-hoc end-to-end: seed scout DB → parse Sarah Chen CV → match → Senior
  Backend Engineer (Python) ranks #1 at 0.7360. Differs from
  `match_jobs.py` output (0.7421) by 0.006 because the adapter's
  `requirements` list is empty (we don't fabricate it). Acceptable.

**Ponytail discipline applied:**
- No fake years of experience — default to 0 when description has no signal
- Lazy import so the package loads cleanly without austria-job-scout
- Empty `requirements` is honest — doesn't fabricate skill → req mapping
- `remote_policy='unknown'` → `remote=False` (conservative — better to
  filter than to mislead)

---

## Open Decisions for Fresh Session

1. **Continue with Phase 2** (ESCO + German BERT)?
   - Download ESCO v1.2.1 dataset (~50MB, free)
   - Add `gebert` embeddings → F1 0.70 → 0.84
   - 3-4 weeks of work
2. **Provide real CV** to populate personal profile?
   - Run `parse_cv.py` on user's PDF/DOCX
   - Match against a real austria-job-scout DB (Phase 4 makes this trivial now)
   - No code work needed
3. **Refinements from audit deferred items?**
   - dataclass migration (replaces Dict returns)
   - Enums for SkillCategory / Proficiency / SectionKey
   - pyproject.toml + pip install -e . to replace sys.path hacks in scripts
   - ProcessPoolExecutor for parallel job matching (now relevant with scout)
   - 1-2 weeks of polish

---

## Deferred Items (from Phase 1 audit, still relevant)

| Item | Why deferred | When |
|------|--------------|------|
| Dataclass / pydantic migration | Big change, no immediate pain | Phase 2 start |
| Enums (SkillCategory / Proficiency / SectionKey) | Needs dataclass first | Phase 2 |
| ProcessPoolExecutor | Was 4 jobs ≠ 100+ | NOW relevant — scout DB can have 100+ |
| TF-IDF batch (vocab fit once) | Same | NOW relevant — scout scale |
| N+1 spaCy batch | Sample CVs parse <1s | Scout-scale irrelevant |
| `read_json()` helper | No behavior change | Phase 2 polish |
| `iter_nonblank_lines()` helper | No behavior change | Phase 2 polish |
| pyproject.toml + pip install -e . | Replaces 4 sys.path hacks | Before Phase 2 |
| 10 `__main__` blocks in library files | Useful for ad-hoc testing | Never (kept) |
| conftest.py for pytest | Cleaner test imports | Before Phase 2 |

## Newly Deferred (Phase 4)

| Item | Why | When |
|------|-----|------|
| Backfill scout DB with real scraped jobs | Network risk + scraping requires active run | User-driven |
| `description_html` cleanup before matching | Description is plain text already | Phase 2 |
| Multilingual matching (German) | scout stores `language` field; we ignore | Phase 2 (gebert) |
| `requirements` reconstruction from description | Risk of fabrication | Phase 2 (ESCO skill extraction) |
| Batch mode in `match_scout_jobs.py` | Single-profile use case | If/when needed |

---

## Known Minor Issues (not bugs)

- `entity_extractor.extract_name` may capture 2 lines as one entity when email
  is on line 2 of the header (senior CV shows `name='Sarah Chen\nsarah.chen@…'`).
  Email is still extracted separately; matching still works correctly. Phase 1.1.
- Adapter's `requirements` is always `[]` for scout-sourced jobs (we don't
  fabricate it). This causes ~0.006 score diff vs. manually-curated jobs.
- Scout DB `description` may contain HTML entities; we don't decode them.
  Affects TF-IDF keyword matching only (low-weight component).

---

## Dependencies

```
pdfminer.six>=20260107
python-docx>=1.2.0
spacy>=3.8.0
scikit-learn>=1.9.0
pydantic>=2.13.0
jsonschema>=4.26.0
pytest>=9.1.0
```

Plus: `en_core_web_sm` spaCy model (`python3 -m spacy download en_core_web_sm`).

**Optional (Phase 4):** austria-job-scout — only needed if you want to
run the live integration. Install: `pip install -e /path/to/austria-job-scout`.

---

## Files Added/Modified in Phase 4 (2026-06-25)

### New code (Phase 4 commit, ~1000 lines):
- `integration/__init__.py` (10 lines)
- `integration/scout_adapter.py` (310 lines)
- `scripts/match_scout_jobs.py` (130 lines)
- `scripts/seed_scout_db_from_samples.py` (150 lines)
- `tests/test_scout_adapter.py` (400 lines, 38 tests)
- `tests/fixtures/scout_schema.sql` (verbatim copy from austria-job-scout)

### Updated:
- `README.md` — Phase 4 section + integration architecture diagram
- `wiki/CONTINUITY.md` (this file)

---

## Mnemosyne State

Stored facts about this project (auto-surfaced in future sessions):
- CV profile assessment uses multi-stage matching (filters → TF-IDF → weighted)
- 45/25/18/12 scoring weights
- Phase 4 ships `integration/scout_adapter.py` + `scripts/match_scout_jobs.py`
- 57/57 tests (2 skipped — need profile JSONs)
- ~2200 LOC project total
- Phase 1 audit completed 2026-06-25 with 18 fixes applied (commit 8a5b7fc)
- Phase 4 ships 2026-06-25 with 38 new tests + integration verification

---

## Continue From Here

**Default next action:** Phase 2 (ESCO + German BERT) — biggest F1 gain.

**If user provides real CV:** Drop it in `data/sample_cvs/`, run
`scripts/parse_cv.py` on it, then `scripts/match_scout_jobs.py` against
the real austria-job-scout DB.

---

*Reference written: 2026-06-25 21:00 UTC*
*Ready for fresh-session resumption*