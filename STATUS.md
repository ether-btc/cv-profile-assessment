# CV Profile Assessment — Phase 1 MVP COMPLETE

**Date:** 2026-06-25
**Status:** ✅ Working prototype — all 14 tests pass, end-to-end pipeline validated

---

## What Works

```
CV (PDF/DOCX/TXT) → Parser → Profile → Matching → Ranked Jobs
                  (5 modules) (JSON)   (3 modules)
```

### Test Results

```
pytest tests/test_smoke.py -v
✓ 14 passed in 3.45s
```

### End-to-End Demo

**Sarah Chen (Senior SWE, Vienna):**
```
1. Senior Backend Engineer (Python) @ InnovateTech GmbH   0.7421 ✓ TOP MATCH
2. DevOps Engineer @ CloudOps Inc                        0.5771
3. NLP Research Engineer @ AILab Research                0.5256
4. Frontend Developer @ WebStudio AG                     0.4342
```

**Marcus Weber (Junior Full-Stack, Munich):**
```
1. Frontend Developer (React/Next.js) @ WebStudio AG     0.5712 ✓ TOP MATCH
2. Senior Backend Engineer (Python) @ InnovateTech GmbH  0.3297
3. DevOps Engineer @ CloudOps Inc                        0.2663
4. NLP Research Engineer @ AILab Research                0.2005
```

---

## Project Structure

```
~/projects/cv-profile-assessment/
├── parser/
│   ├── pdf_extractor.py      # pdfminer.six
│   ├── docx_extractor.py     # python-docx
│   ├── section_segmenter.py  # regex-based
│   ├── entity_extractor.py   # spaCy NER + regex
│   └── skill_extractor.py    # keyword matching (8 categories)
├── profile_builder_pkg/      # renamed to avoid stdlib 'profile' clash
│   ├── profile_builder.py    # assembles profile
│   └── validator.py          # JSON Schema validation
├── matching/
│   ├── tfidf_matcher.py      # TF-IDF + cosine
│   ├── deal_breakers.py      # hard filters
│   └── scorer.py             # weighted 45/25/18/12
├── data/
│   ├── sample_cvs/           # 3 synthetic CVs
│   ├── sample_jobs/          # 4 sample jobs
│   └── sample_profiles/      # parsed outputs
├── scripts/
│   ├── parse_cv.py           # CLI: CV → JSON profile
│   └── match_jobs.py         # CLI: profile → ranked jobs
├── tests/test_smoke.py       # 14 tests
├── schema/profile_schema.json
├── requirements.txt
└── README.md
```

---

## Key Decisions

### 1. Package renamed `profile` → `profile_builder_pkg`
**Why:** Python's stdlib `profile` module is imported by spaCy's CLI. Having a local package named `profile` caused circular import → spaCy import failure → cascading test collection failure.
**Fix:** Renamed + restructured imports to avoid the stdlib shadow.

### 2. Skill proficiency defaults to "advanced"
**Why:** Phase 1 has no way to infer proficiency from CV text. Defaulting to advanced gives realistic scoring; Phase 2 will extract from context.
**Impact:** Required-skills score for senior SWE → senior backend = 0.85 (correct).

### 3. Sample data structure (3 personas)
- **Sarah Chen:** Senior SWE, Python, Vienna (8y exp)
- **Marcus Weber:** Junior Full-Stack, JS, Munich (3y exp)
- **Elena Rossi:** Data Scientist, Italian (5y exp, NLP/CV)

Each represents a different career stage/region to test matching robustness.

### 4. Schema includes `databases` category
**Why:** Original taxonomy had `databases` separate; JSON Schema needed updating to match.

---

## Component-Level Scoring (Explainability)

Each match returns 4 component scores:
```
required_skills (45%) — How well profile skills cover job requirements
experience      (25%) — Years + seniority alignment
preferred       (18%) — Nice-to-have qualifications match
keyword_tfidf   (12%) — TF-IDF cosine similarity
```

This means a user can see *why* a job scored 0.74 vs 0.43 — not just a black-box number.

---

## Performance

- **Parse time:** ~2-3s per CV (single core)
- **Match time:** ~50ms per job (TF-IDF + scoring)
- **Memory:** ~300MB peak (spaCy model loaded once)
- **Test suite:** 3.45s for 14 tests

---

## What's NOT in Phase 1

- ❌ Real ESCO ontology integration (Phase 2)
- ❌ German BERT embeddings (Phase 2)
- ❌ PDF OCR fallback for scanned documents
- ❌ Date extraction from experience entries
- ❌ Education section parsing
- ❌ Projects/certifications parsing
- ❌ Persistent SQLite storage
- ❌ CLI interactive profile builder

---

## Ready For

1. **Real CV integration** — User provides CV → parsed → scored against fetched jobs
2. **Phase 2 kickoff** — ESCO download (v1.2.1), skill normalization, German BERT
3. **`austria-job-scout` integration** — Wire matching engine into the scraper pipeline

---

## How to Use

```bash
# Setup
cd ~/projects/cv-profile-assessment
source venv/bin/activate
pip install -r requirements.txt

# Parse a CV
python scripts/parse_cv.py /path/to/cv.pdf -o profile.json

# Match against jobs
python scripts/match_jobs.py profile.json /path/to/jobs_dir/

# Run tests
pytest tests/ -v
```

---

## Research Foundation

Full research document: `~/.wiki/research/cv-profile-assessment/framework-v1.md` (24KB)
External research (subagent): https://github.com/ether-btc/job-matching-system/blob/main/RESEARCH_COMPREHENSIVE.md

---

*Last updated: 2026-06-25 18:15 UTC*
*Next milestone: User CV integration + Phase 2 ESCO setup*