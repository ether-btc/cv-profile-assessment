# cv-profile-assessment — Development Log

## 2026-06-29: Real German-language CV test

### What happened
First real CV processed through the pipeline: a German-language Austrian CV
(FlowCV layout, 2 pages, PDF). PDF extraction worked flawlessly (4,254 chars),
but the downstream NLP pipeline failed comprehensively.

### Failures identified
1. **Section segmentation** — SECTION_PATTERNS is English-only. German headers
   not recognized: BERUFSERFAHRUNG, AUSBILDUNG, KENNTNISSE, SPRACHEN, ITK.
   All text dumped into "header" bucket.
2. **Skill extraction** — DEFAULT_SKILL_TAXONOMY is English-only. Only "oracle"
   and "r" detected (both false positives or misclassified). Real skills missed:
   SAP R/3, BMC Remedy, SCCM, Google Analytics, Microsoft Ads, Amdocs, Clarify.
3. **Entity extraction** — en_core_web_sm NER model cannot parse German text.
   Name captured as "Matthias K.\nÖsterreich". Email/phone/location all missed.
4. **No usage history** — No mechanism to record what was processed, when, and
   what the pipeline produced. Every run is a blank slate.

### Required for Phase 5: Internationalization (i18n)
- [ ] German section header patterns in section_segmenter.py
- [ ] de_core_news_sm SpaCy model (German NER) as fallback
- [ ] Auto language detection → route to DE or EN pipeline
- [ ] Expanded skill taxonomy with EU/Austrian enterprise tools
- [ ] PDF layout-aware extraction (FlowCV two-column layout scrambles reading order)

### Required: Usage history / processing log
- [ ] Append-only JSONL log: timestamp, source file, language detected,
      sections found, skills extracted, profile confidence, errors/warnings
- [ ] CLI flag `--history` to show past runs
- [ ] Profile diff: compare reprocessed profiles to detect regression
- [ ] This enables iterative improvement measurement across CV variants
