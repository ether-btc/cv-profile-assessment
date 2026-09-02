# Analyzer Improvements Identified — 2026-09-02 CV Run

## Run Summary

CV: `/home/hermes-pi/Sync/shared/Matthias_K_FlowCV_Resume_2026-06-29.pdf`
Method: `./venv/bin/python` — `build_profile_from_cv()` → `score_one_job()` → `feedback_to_text()` + `prepare_narrative_prompt()`

### Results
- ATS parse-safety: 80/100 (job-independent, identical across all 4 sample jobs)
- Skills extracted: 10/10 (only German soft-skills; no IT/marketing/enterprise skills captured)
- Experience entries: 1/6+ (only first entry parsed; tabellarische Erfahrung ignoriert)
- Match scores: 18/100 across all 4 jobs (Backend, NLP, DevOps, Frontend)

## Structural Issues Found

### 1. Skill Extractor: No Tabular/Sektional Context (HIGH PRIORITY)

**Problem**: `skill_extractor.py:extract_skills()` falls back to full-text keyword matching when `sections.get("skills", "")` is empty. However, the FlowCV CV has KENNTNISSE as a section, but the content is in a **table format** (pipe-separated or column-aligned). The section_segmenter recognizes "KENNTNISSE" as a heading, but the tabular content flows into the "header" bucket because:
- The heading detection in `section_segmenter.py` works line-by-line
- Table rows (with `|`, spacing, etc.) don't match any section pattern
- The pipe-separated table in your CV causes the segmenter to miss the section boundary

**Evidence**: Only 10 skills extracted (all German soft-skills like Kommunikationsfertigkeit, Organisation). SAP, Microsoft CRM, Google Ads, Oracle CRM — all present in the KENNTNISSE table — are not captured.

**Fix needed**:
- Extend `section_segmenter.py` to handle tabular sections (detect content until next heading, not just until blank line)
- Extend `skill_extractor.py` to search within the skills-section text, not just the full CV text
- Add tabular row parsing for pipe-separated and column-aligned skill lists

### 2. TF-IDF Matcher: English Stopwords for German CV (HIGH PRIORITY)

**Problem**: `tfidf_matcher.py:85` hardcodes `stop_words="english"`. Your CV is German. This means:
- German stopwords (der, die, das, und, etc.) inflate the vocabulary
- "Kenntnisse", "Berufserfahrung", "Ausbildung" are NOT English stopwords, so they survive and create noise
- The cosine similarity is degraded because the vector space is polluted with non-informative German terms

**Evidence**: keyword_tfidf scores all around 0.0014-0.0064 — essentially zero overlap.

**Fix needed**:
- Use `stop_words="german"` when profile language is "de"
- Or build a combined stopword list (`english` + `german` + domain-specific terms)
- Route via `profile["metadata"]["language"]`

### 3. Experience Parser: Phase 1 Placeholder (HIGH PRIORITY)

**Problem**: `_parse_experience()` in `profile_builder.py:164` only splits on `\n\n` and looks for `@` in the first line. This works for the synthetic sample CV (which uses `Position @ Company` format) but **fails completely** on your FlowCV CV, which has:
- Year ranges on separate lines (`2024 – 2025`)
- Company name on next line
- A tabellarische Erfahrung in the second half of the CV with `|` separated columns

**Evidence**: Only 1 experience entry parsed (`2024 – 2025 @ ` — position/name lost). 6+ entries in the table completely ignored.

**Fix needed**:
- Phase 2 parser: recognize `YYYY – YYYY` or `MM.YYYY – MM.YYYY` date patterns as experience entry markers
- Parse pipe-separated table rows (`|2010 – 2011|T-Mobile Austria,|...`) into experience entries
- Handle German date ranges with en-dash (`–`) and em-dash (`—`)

### 4. ATS Check: No Tabellen-Erkennung (MEDIUM PRIORITY)

**Problem**: `ats_check.py` checks for multi-column layouts but only inspects `page[0]` (first page) and uses `get_text("blocks")`. Your CV's experience table appears as text blocks that don't trigger the multi-column heuristic because the table is below-the-fold on page 1.

**Fix needed**:
- Scan all pages for multi-column detection, not just page[0]
- Detect table-like structures (pipe `|`, consistent column alignment) as an additional layout hazard

### 5. ESCO Mapping: Hardcoded 0.0 (LOW PRIORITY)

**Problem**: `profile_builder.py:114` hardcodes `"esco_mapping": 0.0`. The `skill_extractor.py` mentions "Future: ESCO API integration" but it was never implemented. Your skill taxonomy already covers DACH enterprise tools (SAP, BMC Remedy, Amdocs, Microsoft AD) — the confidence score should reflect this.

**Fix needed**: Compute a real confidence score based on taxonomy coverage, not hardcode 0.0.

### 6. Narrative Prompt: Tips Not Structured for LLM (LOW PRIORITY)

**Problem**: `prepare_narrative_prompt()` embeds tips as text lines (`+` for good, `-` for improve). An LLM consuming the prompt can read the tips but cannot programmatically extract which specific tips to surface. The response format (`NARRATIVE_RESPONSE_FORMAT`) doesn't include a field for "tips_used".

**Fix needed**: Either add a `tips_used` field to the Narrative interface, or pass tips as structured JSON alongside the prompt text.

## Priority Order for Next Iteration

1. **Skill-Extractor erweitern** — Kontext-Profilierung in tabellarischen KENNTNISSE-Sektionen; erkennt SAP, Microsoft CRM, Google Ads, Oracle CRM, etc. aus der Tabelle
2. **TF-IDF deutsche Stopwords** — `stop_words="german"` oder kombinierte Liste; routing über `profile["metadata"]["language"]`
3. **Erfahrung-Parser Phase 2** — Tabellen-basierte Erfahungserkennung (mehrspaltig, `|` getrennt); deutsche Datumsformate (`03.2019`, `2024 – 2025`)