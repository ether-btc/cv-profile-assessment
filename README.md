# cv-profile-assessment

Privacy-focused CV/resume parser and job-candidate matching engine for the Austrian/EU job market. 100% local execution on Raspberry Pi 5 (ARM64, 8GB RAM). Synergizes with the `austria-job-scout` skill.

**Status: Phase 1 MVP shipped 2026-06-25** — 19/19 tests pass post-audit.

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

# Match against jobs
python scripts/match_jobs.py profile.json data/sample_jobs/

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

## Roadmap

- [x] Phase 1: Resume parser (PDF/DOCX → text)
- [x] Phase 1: Section segmentation
- [x] Phase 1: Entity extraction (spaCy NER + regex)
- [x] Phase 1: Skill extraction (categorized taxonomy)
- [x] Phase 1: Profile builder with JSON Schema validation
- [x] Phase 1: Matching engine (TF-IDF + scoring)
- [x] Phase 1: Sample data + tests (19 passing)
- [x] Phase 1: Code audit + fixes (commit 8a5b7fc)
- [ ] Phase 2: ESCO ontology integration (F1 0.70 → 0.84)
- [ ] Phase 2: German BERT (gebert) embeddings
- [ ] Phase 3: Knowledge Graph + GNN (F1 0.91)
- [ ] Phase 4: Integration with `austria-job-scout` skill

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

Full research and architecture rationale: see `wiki/audits/cv-profile-assessment-phase1-audit-2026-06-25.md` in the project's local wiki.

External skills ontology research: https://github.com/ether-btc/job-matching-system/blob/main/RESEARCH_COMPREHENSIVE.md

## License

MIT