# cv-profile-assessment

Privacy-focused CV/resume parser and job-candidate matching engine for the Austrian/EU job market. 100% local execution on Raspberry Pi 5 (ARM64, 8GB RAM). Synergizes with the [austria-job-scout](https://github.com/ether-btc/austria-job-scout) project.

**Status: Phase 4 shipped 2026-06-25** — 57/57 tests pass; live integration with austria-job-scout SQLite DB.

## Quickstart

```bash
git clone https://github.com/ether-btc/cv-profile-assessment.git
cd cv-profile-assessment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m spacy download en_core_web_sm

# Parse a CV
python scripts/parse_cv.py data/sample_cvs/senior_swe_vienna.txt -o profile.json

# Match against local job JSON files
python scripts/match_jobs.py profile.json data/sample_jobs/

# Match against jobs from a live austria-job-scout SQLite DB (Phase 4)
python scripts/match_scout_jobs.py profile.json /path/to/scout.sqlite -o results.json

# Run tests
pytest tests/ -v
```

## Architecture

```
CV (PDF/DOCX/TXT)
    ↓
parser/  (pdfminer.six, python-docx, spaCy NER, regex)
    ↓
profile_builder_pkg/  (assembly + JSON Schema validation)
    ↓
matching/  (deal-breakers + TF-IDF + scorer)
    ↓
Ranked jobs with explainable component scores

       ┌──────────────────────────────────────────────┐
       │ Phase 4: integration/scout_adapter.py        │
       │ Converts austria-job-scout SQLite rows →     │
       │ cv-profile-assessment job schema             │
       └──────────────────────────────────────────────┘
                          ↓
              scripts/match_scout_jobs.py
```

## Algorithm

Phase 1 uses TF-IDF + cosine similarity with weighted component scoring:

```
match_score = (
    required_skills * 0.45 +   # hard requirements coverage
    experience * 0.25 +        # years + seniority alignment
    preferred * 0.18 +         # nice-to-have qualifications
    keyword * 0.12             # TF-IDF cosine similarity
)
```

Plus hard filters (deal-breakers) that eliminate jobs before scoring.

## Phase 4: austria-job-scout Integration

The `integration/scout_adapter.py` module bridges the two projects:

| Field | austria-job-scout source | cv-profile-assessment target |
|-------|--------------------------|------------------------------|
| `title`, `company`, `location` | direct | direct |
| `remote_policy` enum | `remote`/`hybrid`/`on_site`/`unknown` | `remote` bool (hybrid → True) |
| `seniority` | `junior`/`mid`/`senior`/`lead` | normalized via `_SENIORITY_HINTS` |
| `salary_min/max` | flat columns | nested `salary_range{min, max, currency, period}` |
| `skills_json` | JSON array string | `required_skills: list[str]` |
| `min_years_experience` | not stored | derived from description regex (`5+ years`, `at least 2 years`) |
| `_source` (provenance) | n/a | `{url, ats, source_domain, scout_job_id}` |

The adapter has a **lazy import** for the austria-job-scout package — you can use the rest of cv-profile-assessment without austria-job-scout installed.

### End-to-end CLI

```bash
python scripts/match_scout_jobs.py <profile.json> <scout.sqlite> [-o results.json]
```

Pipeline: load profile → query `austria_jobs` (status='active') → adapt rows → run matching engine → ranked JSON output.

### Offline testing

`scripts/seed_scout_db_from_samples.py` builds a synthetic austria-job-scout SQLite DB from the project's sample jobs (using the real `schema.sql`), so the integration is fully testable without network access:

```bash
python scripts/seed_scout_db_from_samples.py db/scout.sqlite
python scripts/match_scout_jobs.py data/sample_profiles/senior_swe_vienna.json db/scout.sqlite
```

**Verified output (Sarah Chen vs. 4 sample jobs):**

```
1. Senior Backend Engineer (Python)   0.7360  ← correct
2. DevOps Engineer                    0.6721
3. NLP Research Engineer              0.6681
4. Frontend Developer (React/Next.js) 0.5745
```

## Roadmap

- [x] Phase 1: Resume parser (PDF/DOCX → text)
- [x] Phase 1: Section segmentation
- [x] Phase 1: Entity extraction (spaCy NER + regex)
- [x] Phase 1: Skill extraction (categorized taxonomy)
- [x] Phase 1: Profile builder with JSON Schema validation
- [x] Phase 1: Matching engine (TF-IDF + scoring)
- [x] Phase 1: Sample data + tests (19 passing)
- [x] Phase 1: Code audit + fixes (commit 8a5b7fc)
- [x] Phase 4: austria-job-scout integration (adapter + CLI + tests; 57 passing)
- [ ] Phase 2: ESCO ontology integration (F1 0.70 → 0.84)
- [ ] Phase 2: German BERT (gebert) embeddings
- [ ] Phase 3: Knowledge Graph + GNN (F1 0.91)

## Tech Stack

- **Python:** 3.11+
- **NLP:** spaCy 3.8 (en_core_web_sm)
- **ML:** scikit-learn 1.9 (TF-IDF, cosine similarity)
- **Validation:** jsonschema 4.26
- **Testing:** pytest 9.1
- **Target Hardware:** Raspberry Pi 5 (ARM64, 8GB RAM)

## Privacy & Compliance

- 100% local execution (no data leaves the machine)
- No external API calls during parsing
- GDPR-compliant by design
- EU AI Act: Explainable scoring (component-level visibility)
- No bias on protected attributes (gender, age, ethnicity)

## Research Foundation

Full research and architecture rationale: see `wiki/CONTINUITY.md` and the local wiki at `~/.wiki/research/cv-profile-assessment/`.

External skills ontology research: https://github.com/ether-btc/job-matching-system/blob/main/RESEARCH_COMPREHENSIVE.md

## License

MIT