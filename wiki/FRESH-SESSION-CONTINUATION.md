# CV Profile Assessment — Fresh Session Continuation Reference

**Created:** 2026-06-26  
**Last session end:** Multi-cycle audit complete, all fixes committed/pushed, wiki documented.

---

## Current State (as of 2026-06-26)

### Repository
- **Path:** `/home/hermes-pi/projects/cv-profile-assessment`
- **Remote:** `git@github.com:ether-btc/cv-profile-assessment.git`
- **Branch:** `master` (not `main`)
- **HEAD:** `8421264` — "ponytail: Cycle 2 cleanup (180 lines removed) + scorer substring fix"
- **Status:** Clean, all pushed, tests green (72/72)

### Recent Commits (audit series)
```
8421264 ponytail: Cycle 2 cleanup (180 lines removed) + scorer substring fix
29ae89d fix: deal-breaker substring matching false positives (Cycle 2)
6813680 audit: multi-model review fixes (3 reviewers)
b789f86 refactor: extract shared scoring pipeline (score_one_job)
7ef3652 audit: Phase 4 ponytail + correctness fixes
6633341 feat: Phase 4 — austria-job-scout integration
```

### Test Coverage
- **Total:** 72 tests (was 19 at Phase 1, 57 at Phase 4 ship)
- **Files:** `tests/test_smoke.py` (smoke tests), `tests/test_scout_adapter.py` (integration + regression)
- **Run:** `cd ~/projects/cv-profile-assessment && source venv/bin/activate && python -m pytest tests/ -q`

---

## Multi-Cycle Audit Summary

### Cycle 1: Self-Review + Ponytail
- **Findings:** 10 issues (6 dead code, 4 bugs)
- **Fixed:** Commit 7ef3652
- **Key fix:** N+1 performance regression in `match_all_profiles_to_jobs()`

### Cycle 2: Deep Correctness + Ponytail
- **Findings:** 3 correctness bugs (all HIGH severity)
- **Fixed:** Commits 29ae89d + 8421264
- **Key fixes:**
  1. Deal-breaker substring false positives (`'java'` blocked `'JavaScript'`)
  2. Scorer substring false positives (`'r'` matched `'react'`)
  3. 180 lines dead code removed (__main__ blocks, Phase 2 stubs)

### Cycle 3: Verification
- **Ad-hoc verification:** 4/4 checks passed
  - pytest: 72/72 pass
  - Deal-breaker: `'java'` ≠ `'javascript'` ✓
  - Scorer: `'r'` ≠ `'react'` ✓
  - No `__main__` blocks in library files ✓

---

## Key Files & Architecture

### Core Modules
| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `parser/*.py` | CV parsing (PDF/DOCX) | `extract_text_from_pdf`, `extract_entities`, `extract_skills` |
| `profile_builder_pkg/*.py` | Profile validation | `build_profile_from_cv`, `validate_profile` (jsonschema) |
| `matching/deal_breakers.py` | Hard constraints | `check_deal_breakers` (word-boundary regex) |
| `matching/scorer.py` | Weighted scoring | `score_required_skills`, `score_experience`, `compute_overall_score` |
| `matching/pipeline.py` | Batch matching | `score_one_job` (single source of truth) |
| `matching/tfidf_matcher.py` | Keyword similarity | `compute_keyword_similarity` (sklearn TfidfVectorizer) |
| `integration/scout_adapter.py` | Austria-job-scout DB | `load_jobs_from_scout_db`, `adapt_austria_jobs_row` |

### Sample Data
- `data/sample_profiles/sarah_chen.json` — Python backend engineer
- `data/sample_profiles/marcus_weber.json` — DevOps engineer
- `tests/fixtures/scout_schema.sql` — Scout DB schema (copied from upstream)

### CLI Scripts
- `scripts/parse_cv.py` — Parse CV → profile JSON
- `scripts/match_jobs.py` — Match profile against job directory
- `scripts/match_scout_jobs.py` — Match profile against Scout DB
- `scripts/seed_scout_db_from_samples.py` — Seed Scout DB with sample profiles

---

## Known Issues / Future Work

### Phase 2 (Planned)
- ESCO skills integration (`load_esco_skills()` stub was deleted — re-add when Phase 2 arrives)
- IndexedJob support (`adapt_indexed_job()` exists but untested — no production caller yet)

### Technical Debt
1. **Date extraction:** `DATE_PATTERN` constant was removed (unused). Entity extractor parses dates but doesn't use the pattern.
2. **Validation:** `validator.py` has `_minimal_validation()` fallback for missing jsonschema — but jsonschema is a hard dependency. Confirm and delete if dead.
3. **Weights param:** `compute_overall_score(weights=None)` — never called with custom weights. Could simplify signature.

### Test Gaps
- `adapt_indexed_job()` — zero test coverage (Phase 2 feature)
- `load_esco_skills()` — zero coverage (Phase 2 feature)
- CLI exit codes — not tested (0-4 ranges documented but untested)

---

## Common Commands

### Run Tests
```bash
cd ~/projects/cv-profile-assessment
source venv/bin/activate
python -m pytest tests/ -v          # Verbose
python -m pytest tests/ -q          # Quiet
python -m pytest tests/ -k deal     # Filter by keyword
```

### Match Profile Against Jobs
```bash
# Against job directory
python scripts/match_jobs.py data/sample_profiles/sarah_chen.json data/jobs/

# Against Scout DB
python scripts/match_scout_jobs.py data/sample_profiles/sarah_chen.json /path/to/scout.db
```

### Parse CV
```bash
python scripts/parse_cv.py /path/to/cv.pdf --output profile.json
```

### Git Workflow
```bash
cd ~/projects/cv-profile-assessment
git status
git add <files>
git commit -m "type: description"
git push origin master
```

---

## Patterns & Pitfalls

### Word-Boundary Matching (Critical Pattern)
When matching tokens that may contain non-word characters (like `'c++'`), use:
```python
pattern = r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])"
```
**NOT** `\b...\b` — it fails for tokens ending in non-word chars.

**Applied in:**
- `matching/deal_breakers.py:44` — deal-breaker filtering
- `matching/scorer.py:55` — partial skill matching

### N+1 Prevention
Precompute shared state outside loops:
```python
# WRONG: rebuilds set every iteration
for job in jobs:
    profile_skills = {s["name"] for s in profile["skills"]}
    ...

# CORRECT: compute once
profile_skills = {s["name"] for s in profile["skills"]}
for job in jobs:
    ...
```

### Malformed Data Safety
Always guard against missing keys in profile/job dicts:
```python
# WRONG: KeyError if skill has no "name"
{s["name"].lower() for s in profile.get("skills", [])}

# CORRECT: filter out malformed entries
{s["name"].lower() for s in profile.get("skills", []) if "name" in s}
```

---

## Wiki Documentation

- **Full audit report:** `~/.wiki/audits/cv-profile-assessment-full-audit-2026-06-26.md`
- **Session continuity:** `~/projects/cv-profile-assessment/wiki/CONTINUITY.md`

---

## Resuming Work

### To Continue the Audit
If asked to "continue the cv-profile-assessment audit":
1. Read this file for context
2. Read the full audit report (~/.wiki/audits/...)
3. Check if new code has been added since 8421264
4. If yes: run another audit cycle (3 reviewers + ponytail)
5. If no: task is complete, verify nothing regressed

### To Add New Features
1. **Phase 2 (ESCO integration):**
   - Re-add `load_esco_skills()` in `parser/skill_extractor.py`
   - Implement ESCO CSV/JSON parsing
   - Wire into `score_required_skills` for URI matching
   - Add tests

2. **IndexedJob support:**
   - Add tests for `adapt_indexed_job()`
   - Decide if production path is needed (currently only tested with mocks)

### To Run a Fresh Audit Cycle
1. Pack source: `repomix --output /tmp/cv-profile-packed.xml`
2. Dispatch 3 subagents (correctness, robustness, ponytail)
3. Run OCR: `ocr scan . --output /tmp/ocr-cv.md`
4. Triage findings, fix, test, commit, push
5. Update wiki audit doc

---

## Environment

- **Python:** 3.11 (venv at `~/projects/cv-profile-assessment/venv`)
- **Key deps:** pdfminer.six, python-docx, spacy, scikit-learn, jsonschema
- **Test framework:** pytest
- **Lint:** No linter configured (audit used OCR + manual review)

---

## Contact / Context

- **User preferences:** Autonomous execution, no sub-step confirmations. "continue" = self-review then proceed.
- **GitHub lifecycle:** assess → fix → commit → push → save-and-file (for ether-btc/* repos)
- **Memory:** Audit summary stored in Mnemosyne (memory_id: 0a0e723652b6229b)

---

**End of continuation reference.** For questions about specific code paths, grep the source or run the verification script from the audit.