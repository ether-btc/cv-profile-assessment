# CV Analyzer Improvements — 2026-09-02 (Session 3)

## Codex Debate Outcome

After Codex review of the Phase 3 roadmap (3 items), the recommended build order was:

1. **Coordinate-assisted PDF parser** (PyMuPDF dict mode) — 140-240 LOC, up to 7/7 entries fixed
2. ~~spaCy NER for company/role~~ — **Skipped**: wrong tool, would only catch 3/7
3. ~~Skills from experience summaries~~ — **Optional**: 0 new top-level SAP on this CV

Quick spike recommended: try `page.get_text("text", sort=True)` first (10-30 LOC).
**If 15/15 → keep, else discard and fall back to geometry.**

## Implementation: PyMuPDF sort=True Spike — 15/15 ✓

**Discovered**: PyMuPDF's `get_text("text", sort=True)` returns row-aligned text:
- Each row line contains date, company, role at different x-positions
- Company headers appear on standalone lines above date rows
- Bullet continuations appear on lines following `•` bullets

This **single change** (using sort=True instead of pdfminer's column-by-column extraction)
preserves the 2D table structure that pdfminer destroys.

### Files Added
- `profile_builder_pkg/_exp_sorted.py` (335 lines): Row-aligned parser for sort=True text
- `tests/test_cv_pipeline_improvements.py` — 6 new tests

### Files Modified
- `profile_builder_pkg/profile_builder.py`:
  - `build_profile_from_cv`: For PDFs, also extract sort=True via PyMuPDF
  - `_parse_experience`: Routes to sorted-text parser when sorted_text is available
  - Falls back to state-machine parser, then legacy two-pass parser

### Results on User CV

| Before | After |
|--------|-------|
| 1 of 6+ entries (Phase 1 placeholder) | **15 of 15 entries** with correct dates, companies, roles, locations |
| 12 entries with companies | 15 entries with companies (all) |
| 4 dates displaced | All dates correct |
| 1 missing date range (IVM 2013-2014) | All dates present |
| 3 role strings treated as positions | All roles correctly attributed |
| 1 empty company | All companies filled |

## Test Results
- **Before:** 197 passed, 3 skipped
- **After:** 203 passed, 3 skipped (0 regressions, 6 new tests)

## Key Parser Features

### 1. Row-line parsing
```
2024 – 2025         ipcenter.at GmbH, Outplacement   → → 1 entry: company=ipcenter.at GmbH, position=Outplacement
1100 Wien                                                     → location=1100 Wien
•Liaison zu Partnern...                                       → summary
```

### 2. Company header (company-first format)
```
IVM Technical Consultants                            → pending_company
  2014 – 2015       Personalvermittlung              → 1 entry: company=IVM, position=Personalvermittlung
  2331 Vösendorf
  •Kundenbetreuung...
  2013 – 2014        IT User-Support                 → 2 entries: same company, position=IT User-Support
```

### 3. Bullet-continuation suppression
Indented bullet continuations like "Managements zur Lead-Generierung..." are NOT
detected as companies even though they contain commas. The parser uses context:
- `_previous_was_bullet`: previous non-empty line was `•` or `-`
- `_previous_had_bullet_after_date`: any `•` since the last date row
- Strong company signal (suffix/brand) can override bullet context

### 4. Direct-format row supersedes pending header
```
A1 Telekom Austria                                  → pending_company
  2011 – 2012       Small Accounts Manager            → entry: company=A1, position=Small Accounts Manager
  2009 – 2010        T-Mobile Austria, Projektmitarbeit  → entry: company=T-Mobile Austria, position=Projektmitarbeit
                                                                       (T-Mobile row supersedes A1 header)
```

### 5. Word-boundary suffix matching
Company suffix check uses `\bGmbH\b` etc., avoiding false positives like
`Management` containing `AG` substring.

## What's Next (Phase 4)

The user CV is now parsed with 100% field accuracy. Remaining work:
- Generalize to other tabular CV templates (Europass, modern resume builders)
- Add skills-from-summaries (Item 2) with intermediate proficiency default
- Consider geometry-based parser for non-sortable scans

## Commits This Session
- (pending) Row-aligned experience parser via PyMuPDF sort=True