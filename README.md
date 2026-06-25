# CV Profile Assessment

**Status:** Phase 1 MVP — Working prototype with sample data
**Goal:** Privacy-focused, local CV analysis and job-candidate matching
**Synergy:** Designed to work with `austria-job-scout` skill

## Overview

This project provides a complete pipeline for:
1. **Parsing CVs** (PDF, DOCX, TXT) into structured profiles
2. **Extracting skills** using keyword matching + categorization
3. **Normalizing to ESCO** (Phase 2) for canonical skill IDs
4. **Matching profiles to jobs** using multi-stage scoring
5. **Explaining matches** with component-level scoring

## Architecture

```
CV (PDF/DOCX/TXT)
    ↓
[Parser] → Text + Sections
    ↓
[Entity Extractor] → Name, Email, Phone, Location
    ↓
[Skill Extractor] → Categorized skills
    ↓
[Profile Builder] → JSON Profile (validated)
    ↓
[Matching Engine]
    ↓
[Scorer] → Weighted match score
```

## Components

### Parser (`parser/`)
- `pdf_extractor.py` — PDF → text (pdfminer.six)
- `docx_extractor.py` — DOCX → text (python-docx)
- `section_segmenter.py` — Regex-based section detection
- `entity_extractor.py` — spaCy NER + regex for contact info
- `skill_extractor.py` — Keyword matching against skill taxonomy

### Profile (`profile/`)
- `profile_builder.py` — Assemble profile from parsed CV
- `validator.py` — JSON Schema validation

### Matching (`matching/`)
- `tfidf_matcher.py` — TF-IDF + cosine similarity
- `deal_breakers.py` — Hard filter logic
- `scorer.py` — Weighted scoring (45/25/18/12)

## Setup

```bash
cd ~/projects/cv-profile-assessment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m spacy download en_core_web_sm
```

## Usage

### Parse a CV

```bash
source venv/bin/activate
python scripts/parse_cv.py data/sample_cvs/senior_swe_vienna.txt
# Output: structured JSON profile
```

### Match profile to jobs

```bash
python scripts/match_jobs.py data/sample_profiles/sarah_chen.json data/sample_jobs/
# Output: ranked list of matches with component scores
```

### Run tests

```bash
pytest tests/test_smoke.py -v
```

## Algorithm Phases

| Phase | Algorithm | F1 Score | Complexity | GDPR | Status |
|-------|-----------|----------|------------|------|--------|
| **1** | TF-IDF + Cosine | ≈ 0.70 | Low | ✅ Excellent | ✅ Done |
| **2** | German BERT | ≈ 0.84 | Medium | ✅ Excellent | 🔲 Planned |
| **3** | Knowledge Graph + GNN | ≈ 0.91 | High | ⚠️ Good | 🔲 Planned |

## Scoring Formula

```
match_score = (
    required_skills * 0.45 +   # 45% weight
    experience * 0.25 +        # 25% weight
    preferred * 0.18 +         # 18% weight
    keyword * 0.12             # 12% weight
)
```

## Roadmap

- [x] Phase 1: Resume parser (PDF/DOCX → text)
- [x] Phase 1: Section segmentation
- [x] Phase 1: Entity extraction (NER + regex)
- [x] Phase 1: Skill extraction (keyword-based)
- [x] Phase 1: Profile builder + JSON Schema validation
- [x] Phase 1: Matching engine (TF-IDF + scoring)
- [x] Phase 1: Sample data + tests
- [ ] Phase 1: Real CV integration (awaiting user's CV)
- [ ] Phase 2: ESCO ontology integration
- [ ] Phase 2: German BERT embeddings (gebert)
- [ ] Phase 3: Knowledge Graph + GNN
- [ ] Phase 4: Integration with `austria-job-scout`
- [ ] Phase 4: Production deployment

## Privacy & Compliance

- ✅ 100% local execution (no data leaves the machine)
- ✅ No external API calls during parsing
- ✅ GDPR-compliant by design
- ✅ EU AI Act: Explainable scoring (component-level visibility)
- ✅ No bias on protected attributes (gender, age, ethnicity)

## Tech Stack

- **Python:** 3.11+
- **NLP:** spaCy 3.8 (en_core_web_sm)
- **ML:** scikit-learn (TF-IDF, cosine)
- **Validation:** jsonschema
- **Testing:** pytest
- **Target Hardware:** Raspberry Pi 5 (ARM64, 8GB RAM)

## References

- Research: `~/.wiki/research/cv-profile-assessment/framework-v1.md`
- Skills ontology research: https://github.com/ether-btc/job-matching-system
- ESCO ontology: https://esco.ec.europa.eu/en
- O*NET taxonomy: https://www.onetcenter.org/taxonomy.html

## License

MIT (placeholder — adjust as needed)