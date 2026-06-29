# cv-profile-assessment — Fresh Session Continuation Reference

**Created:** 2026-06-29
**Last session end:** Phase 5 shipped. German CV parsing fully functional.

---

## Current State

### Repository
- **Path:** `/home/hermes-pi/projects/cv-profile-assessment`
- **Remote:** `git@github.com:ether-btc/cv-profile-assessment.git`
- **Branch:** `master`
- **HEAD:** `f657b8d` — "feat(phase5): German CV support + language detection + usage history"
- **Status:** Clean, all pushed, tests green (108 pass + 2 skipped)

### Phase 5 Deliverables (committed f657b8d)

1. **Language detection** (`cv_profile_assessment/language_detection.py`)
   - Common-word frequency heuristic, dependency-free (no langdetect)
   - Returns (lang_code, confidence); "de"/"en"/"unknown"

2. **Usage history** (`cv_profile_assessment/usage_history.py`)
   - Append-only JSONL log at `data/processing_history.jsonl`
   - Records per run: timestamp, source, language, entity counts, confidence, warnings
   - CLI flag `--history` shows formatted table
   - `--no-log` to skip recording

3. **German section segmentation** (`parser/section_segmenter.py`)
   - Extended SECTION_PATTERNS with DE headers:
     BERUFSERFAHRUNG, AUSBILDUNG, KENNTNISSE, SPRACHEN, ITK, WEITERBILDUNG, SOFT SKILLS,
     FÄHIGKEITEN, KOMPETENZEN, ERFAHRUNG, TÄTIGKEIT, ZERTIFIKATE, etc.
   - Soft-skill pattern fixed: `^(skills|...|soft skills|...)`

4. **Bilingual NER** (`parser/entity_extractor.py`)
   - Loads both `en_core_web_sm` and `de_core_news_sm`
   - Routes by detected language
   - Austrian postal-code recognition (4 digits + city → Wien/Graz/...)
   - DE/AT phone formats (+43, +49, 0-prefix)
   - Languages field returns schema-compatible `[{language, fluency}]` with German names normalized to English

5. **DACH skill taxonomy** (`parser/skill_extractor.py`)
   - Added: SAP, SAP R/3, SAP ERP/HR/Procurement, BMC Remedy, SCCM, MDM, MS AD, Active Directory
   - Added enterprise products: MS Office, Microsoft CRM, Microsoft Ads, Google Analytics, Google Ads, Salesforce
   - Added telecom platforms: Amdocs, Clarify, Oracle CRM
   - German soft skills: Einfühlungsvermögen, Kollaboration, Organisation, Kommunikationsfähigkeit, Kommunikationsfertigkeit
   - DACH domains: Telekommunikation, B2B Sales, Account Management, Personalvermittlung, Outplacement, Online Marketing, MarCom
   - Word-boundary matcher uses `(?<![a-z0-9])`/`(?![a-z0-9])` (NOT `\b`) — avoids false positives on multi-word tokens

6. **Pipeline integration** (`profile_builder_pkg/profile_builder.py`)
   - Calls `detect_language()` before entities
   - Routes NER model by language
   - Adds `metadata.language` to profile
   - Computes confidence based on whether dedicated Skills section was found (0.9 if yes, 0.6 if no)
   - Appends usage history record with warnings

7. **CLI upgrades** (`scripts/parse_cv.py`)
   - `--history` shows table, `--no-log` skips recording
   - Post-write summary: "Language: de | Skills: 10 | Experience: 1 | Languages extracted: 2"

8. **Tests** (`tests/test_german_i18n.py`)
   - 36 new tests: language detection, German section patterns, language extraction, German skills, German phone, usage history, NER routing

---

## Test Status

```
108 passed, 0 failed, 2 skipped
```

Test count progression: 19 → 57 → 65 → 72 → **108**

---

## Real CV Reprocessing Result

Source: `Matthias_K_FlowCV_Resume_2026-06-29.pdf` (FlowCV two-column layout, 126 KB)

**Phase 4 output**: name "Matthias K.\nÖsterreich", location {}, languages [], skills: 2 (oracle, r)
**Phase 5 output**:
- Language: de
- Name: "Matthias K."
- Location: {city: "Wien", country: "Austria"}
- Languages: [{language: "German", fluency: "native"}, {language: "Hungarian", fluency: "fluent"}]
- Skills: 10 (SAP, MS Office, Microsoft CRM, Oracle, Oracle CRM, plus 4 German soft skills)
- Experience: 1 entry (entire career lumped — see Phase 5.1 below)

---

## Known Limitations / Phase 5.1 Candidates

### Priority 1: FlowCV 2-column PDF layout
**Problem**: FlowCV renders left+right column concurrently; pdfminer.six reads top-to-bottom across both columns, scrambling the year+company block. This is why all 13 positions land in one entry.

**Options to evaluate (spike needed)**:
- **pdfplumber**: layout-aware via word positions, has a CropFilter for columns. Mid-complexity.
- **PyMuPDF (fitz)**: best layout preservation, supports redaction, headers, etc. Native ARM64 build availability needs checking.
- **pdfminer.six with custom LAParams**: can detect column gutters from word positions. High effort.

**Recommendation**: pdfplumber — adds ~3MB dependency, has column detection primitives, well-maintained.

### Priority 2: Profile diff feature (usage history subset)
Show side-by-side comparison of profile after re-processing the same source — useful for measuring skill-taxonomy improvements over time. Marked in plan but not yet built.

### Priority 3: Sophisticated experience parsing
Build real experience-entry extraction (not `\n\n` grouping). Each block has clear structure:
- Date range (en dash separator)
- Postal code + city
- Company name + role category
- Bullet list of duties

Needs regex / spaCy-rule-based / few-shot-LLM decision.

---

## Resume / Profile Artifacts

Working CV-derived profile (verbatim from session):

### Concise (German) profile
A condensed factual listing of capabilities and accomplishments, useful as CV-basis input. Stored in Mnemosyne under ID listed below.

### Labor profile (Arbeitskraftprofil)
A wider net: statt nur Stationen auflisten, leitet aus jeder Tätigkeit die Tätigkeitsbeschreibung ab und benennt Branchen und Rollen, in denen die Erfahrung verwertbar ist. Includes "Verwertbar für" callouts per skill area (B2B-Vertrieb, Online-Marketing, Recruiting, IT-Support, Schulung/Beratung). Stored in Mnemosyne under ID listed below.

---

## Quickstart for Fresh Session

```bash
cd ~/projects/cv-profile-assessment
source venv/bin/activate
python -m pytest tests/ -q            # expect 108 passed, 2 skipped
python scripts/parse_cv.py --history  # see last runs
python scripts/parse_cv.py "/home/hermes-pi/Sync/shared/Matthias_K_FlowCV_Resume_2026-06-29.pdf" -o /tmp/profile.json
```

### Resume work: Phase 5.1 FlowCV layout

Pre-work:
1. Spike pdfplumber on the Matthias CV — does it preserve column structure?
2. If yes, integrate `pdf_extractor.py` to use pdfplumber for layout-aware extraction
3. Re-run, verify experience splits into 13 entries (or close)

### Resume work: Profile diff feature

1. Add `diff_profile(jsonl_path, source_key)` to `usage_history.py`
2. Wire to `parse_cv.py --diff <source>`
3. Add tests

---

## Mnemosyne Persistence

The German labor profile and concise profile are stored in Mnemosyne with these exact IDs:
- (See mnemosyne_remember calls — IDs returned after each call)

To recall in a fresh session, use `mnemosyne_recall(query="Matthias K. profile")` or query by Mnemosyne ID directly.

---

## Wiki Locations

- `wiki/DEVELOPMENT_LOG.md` — 2026-06-29 first real CV test + i18n gap inventory
- `wiki/FRESH-SESSION-CONTINUATION.md` — this file
- Phase 4 references: `wiki/audits/cv-profile-assessment-full-audit-2026-06-26.md`

---

## Pitfalls & Conventions

- **Don't change proficiency default**: kept "advanced" to preserve Phase 1 scoring behavior. The "intermediate" change broke a regression test (scorer at 0.6 vs 0.7 threshold).
- **Don't rename `profile_builder_pkg/`**: it was renamed from `profile/` because the stdlib `profile` module shadowed it (caused spaCy `cProfile` import failure — documented as a Phase 2 audit lesson).
- **Word-boundary regex**: use `(?<![a-z0-9])`/`(?![a-z0-9])`, NOT `\b`. `\b` fails for tokens ending in non-word chars (`c++`, `.NET`, `node.js`).
- **DE spaCy loading**: `de_core_news_sm` is downloaded via `python -m spacy download de_core_news_sm` (already installed on this Pi as of 2026-06-29).
- **JSON Schema languages field**: requires `[{language, fluency}]` objects, not flat strings.
- **Test runner**: must `source venv/bin/activate` before pytest. pytest auto-discovers tests/, but the venv has spacy + en/de models pre-installed.

---

## Resume Commands Cheat Sheet

```bash
# Process any CV
python scripts/parse_cv.py <path/to/cv.pdf> -o /tmp/out.json

# See history
python scripts/parse_cv.py --history

# Skip logging (for repeated dry-runs)
python scripts/parse_cv.py <path> --no-log

# Run all tests
python -m pytest tests/ -q

# Run only German tests
python -m pytest tests/test_german_i18n.py -v

# Run only smoke tests
python -m pytest tests/test_smoke.py -v
```
