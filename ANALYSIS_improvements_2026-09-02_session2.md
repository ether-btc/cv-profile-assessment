# CV Analyzer Improvements — 2026-09-02 (Session 2)

## New Work (Phase 7+)

### 1. State-Machine Experience Parser (`profile_builder_pkg/_exp_new.py`)

**Problem:** The user CV (Matthias K., FlowCV template) uses a tabular layout
that pdfminer extracts column-by-column (transposed). The legacy two-pass parser
struggled with mixed transposed/direct format in the second half of the CV.

**Solution:** New state-machine parser handles three patterns in one pass:
- **Transposed** (first half): All dates+locations first, then companies+bullets
  → orphaned dates paired FIFO with orphaned companies.
- **Direct format** (some entries): Date → Location → Company, Role → Bullets
- **Company-first** (some entries): Company → Date → Location → Role → Bullets
  → pending_company gets assigned to next date.

**Results on user CV:**
| Before | After |
|--------|-------|
| 1 of 6+ entries parsed (Phase 1 placeholder) | 15 entries parsed |
| Companies mostly missing | First 6 entries: all companies correctly paired |
| Skills bleed from KENNTNISSE section | Skills bleed stopped at section marker |
| 15 experience entries (mostly empty) | 15 entries, 12 with companies |

**Files:**
- `profile_builder_pkg/_exp_new.py` (new, 343 lines)
- `profile_builder_pkg/profile_builder.py` — routes to new parser with legacy fallback
- `tests/test_cv_pipeline_improvements.py` — updated test for new FIFO behavior

### 2. Proficiency-Level Detection (`parser/skill_extractor.py`)

**Problem:** All extracted skills defaulted to "advanced" proficiency — losing
information from CVs that explicitly qualify skills ("Anwendungskenntnisse SAP",
"Grundkenntnisse Python", "Versiert in MS Office").

**Solution:** Context-aware proficiency detection with German CV vocabulary:
- **Expert:** Experte, Expertenwissen, umfassende Kenntnisse
- **Advanced:** Versiert, Fundiert, sehr gute Kenntnisse (default)
- **Intermediate:** Gute Kenntnisse, Anwendungskenntnisse, solide Kenntnisse
- **Beginner:** Grundkenntnisse, Basiskenntnisse, Vorkenntnisse

Marker must appear within 30 chars **before** the skill (German CV convention:
"Versiert in MS Office", not "MS Office, versiert").

**Conservative default:** When no marker found → "advanced" (preserves prior behavior
and avoids downgrading skills the user didn't bother to qualify).

**Results on user CV:**
| Skill | Proficiency | Marker Found |
|-------|-------------|--------------|
| MS Office | advanced | "Versiert in MS Office" |
| Organisation | advanced | (default — conservative) |
| SAP | intermediate | "Anwendungskenntnisse SAP R/3" |
| R | intermediate | (same context as SAP) |
| Others | advanced | (default) |

**Files:**
- `parser/skill_extractor.py` — added `_detect_proficiency()` + `_PROFICIENCY_MARKERS`
- `tests/test_cv_pipeline_improvements.py` — 7 new proficiency tests

## Test Results
- **Before:** 190 passed, 3 skipped
- **After:** 197 passed, 3 skipped (0 regressions)

## Remaining Limitations (Phase 3 Roadmap)
1. **Mixed transposed/direct format**: The second half of the user CV has a
   complex layout where one company (e.g. "A1 Telekom Austria") covers 3
   overlapping date entries. The current FIFO pairing incorrectly assigns
   companies 1:1. Full solution requires PyMuPDF's `get_text("dict")` to
   group text by y-coordinate, then split by x-coordinate.

2. **Skill extraction from experience bullets**: Skills mentioned only in
   experience descriptions (not in the dedicated Skills section) are missed.
   Could be added by scanning `summary` fields for skill names.

3. **No NER-based company detection**: Position/role lines like
   "Personalvermittlung", "Quality Monitoring", "HR Administration" are
   currently classified as "other" and set as position. A small NER model
   or keyword classifier could distinguish roles from companies more
   reliably than heuristics.

## Commits This Session
- (pending) State-machine parser + proficiency detection