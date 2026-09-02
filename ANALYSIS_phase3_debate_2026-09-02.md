# Phase 3 Roadmap Debate — Verdict

**Date:** 2026-09-02
**Participants:** Hermes (parent) ↔ codex (subagent)
**Subject:** CV parser Phase 3 — 3 open roadmap items
**Status:** ✅ Codex verdict received at /tmp/codex_debate_verdict.md (221 lines, 38,859 tokens)

---

## Ground Truth Established Before Debate

I extracted the user CV (`Matthias_K_FlowCV_Resume_2026-06-29.pdf`) with PyMuPDF
and ran it through the current parser to ground the debate in real numbers:

| Metric | Value |
|---|---|
| Total entries emitted | 15 |
| Entries correct as-is | 6 (entries 1-6: ipcenter, VHS, Trimetis, Ricoh, AKV, Candidatis) |
| Entries with defects | **9 (60%)** |
| Defective entries: misdated | 4 (entries 7, 8, 10, 11) |
| Defective entries: mis-classified role-as-position | 3 (entries 9, 11, 13) |
| Defective entries: empty company | 1 (entry 13) |
| Defective entries: multiple dates collapsed | 1 (entry 7 — IVM has 2 dates, only 1 captured) |

**The "12/15 entries correct" claim was misleading — the entry count is right but
field accuracy is the real problem.**

---

## Per-Item ROI Analysis

| Item | Fixes (entries) | LOC estimate | Regression risk | Verdict |
|---|---|---|---|---|
| **1. PyMuPDF y-coordinate** | ~7 of 9 (78%) | 140-240 prod + 120-220 test | Medium | **Build now, but as PDF-only path with state-machine fallback** |
| **2. Skills from experience summaries** | 0 entries; maybe 1 `skills_used` field | 25-60 prod + 40-80 test | Low | **Optional 2nd; does NOT improve this CV** |
| **3. spaCy NER company/role** | ~3 of 9 (all also fixed by Item 1) | 60-120 prod + 80-150 test | Medium | **Skip — replace with deterministic evidence scoring** |

### Why Item 2 has zero value on the user CV
The prompt assumed it would catch "Rechnungsprüfung SAP" inline. Reality: SAP is
already in the KENNTNISSE (Skills) section, so `extract_skills()` already finds it.
Item 2 is purely additive — useful for CVs without a Skills section, irrelevant
to this user's output. The Codex verdict concurs.

### Why Item 3 is redundant with Item 1
All 3 entries Item 3 would fix (9, 11, 13 — the role-mis-classifications) are
entries that Item 1 also fixes via row geometry. NER adds no signal that
coordinate-aware row reconstruction doesn't already provide.

---

## Codex's Concrete Recommendations

1. **Reformulate Item 1 as a PDF-only coordinate-assisted path**, not a wholesale
   state-machine replacement:
   - Extract normalized spans with page, x/y, font, text
   - Cluster spans into visual rows (median-font-height tolerance, not magic number)
   - Infer column bands from repeated x positions (date anchors + postal anchors)
   - Build entry regions between date rows
   - **Carry last employer across page breaks** when next page starts with date/role
   - Produce a confidence score; fall back to `_exp_new.py` on low confidence

2. **First commit a golden 15-tuple fixture test**, not parser changes. The
   current tests check entry count but not field accuracy. Without an oracle,
   regression risk on Item 1 is blind.

3. **Try a 10-30 LOC PyMuPDF `get_text("text", sort=True)` spike first** as a
   baseline. Keep only if it produces all 15/15 correct tuples; discard otherwise.

4. **Item 2 (skills from summaries)** — change design: populate
   `experience[*].skills_used` per entry, then merge with provenance. Use
   `intermediate` (not `advanced`) as default for narrative mentions. Skip
   ambiguous short tokens (`R`, `Go`).

5. **Item 3 (NER)** — drop from roadmap. If ambiguity remains post-Item-1, use
   a 40-90 LOC deterministic evidence score: company suffix, URL/domain shape,
   role lexicon (`Administration`, `Aufsicht`, `Consultant`), repeated employer
   carry-forward. Gate re-introduction of NER on a multi-template evaluation
   showing ≥5pp field-accuracy lift.

6. **Skip "fix FIFO heuristics"** — encodes accidental extraction order, will
   regress other templates.

---

## Concrete Numbered Verdict — Final Ranking

**Build in this order:**

1. **Golden 15-tuple fixture + exact evaluator** (60-120 test LOC). No parser changes
   before the oracle exists. Current tests prove the parser doesn't crash, not that
   fields are right.

2. **PyMuPDF sorted-text spike** (`page.get_text("text", sort=True)`). 10-30 LOC +
   20-40 test LOC. Ship only if 15/15 on golden. Cheap to try, cheap to discard.

3. **Coordinate-assisted PDF path with `_exp_new.py` fallback** (140-240 prod +
   120-220 test LOC). The actual Item 1, done as a narrow reconciler not a
   rewrite. Confidence-gated. Handles page-break employer carry-forward.
   Acceptance: 15/15 golden tuples, 197 existing tests still pass, regression
   test for low-confidence fallback path.

4. **Item 2 (summary skill evidence)** — optional. Only if a multi-CV corpus
   shows skills missed outside the Skills section. Use `intermediate` default.
   Populate `experience[*].skills_used`, merge with provenance.

**Do not build:**

5. **Item 3 (spaCy NER company/role)** — replaced by deterministic evidence
   scoring if needed. NER's prose-trained models can't tell you which row owns
   a role, only what kind of noun it is.

---

## Caveats and Pushback on Codex

Codex's analysis is largely correct but with three nuances worth flagging:

- **"T-Mobile is subsidiary of A1, don't rewrite"** — Codex correctly flags this,
  but in practice the A1 cluster problem means the 2010-2011 row has NO company
  label at all (it's a continuation). The carry-forward rule must be:
  "label-less rows inherit last explicit employer ONLY when within the same
  multi-row block." That's a stricter rule than Codex stated.

- **Loc estimate of 140-240 LOC** is for a NARROW reconciler. A general layout
  engine is more. Don't let scope creep turn this into a 500-LOC rewrite.

- **"Add a synthetic PDF fixture"** — Codex suggests generating a fixture.
  Practical concern: PDF generation can shift coordinate noise. Better to use
  the real (anonymized) user CV as the golden fixture, OR generate with reportlab
  and accept ±5px tolerance in tests.

---

## Files Created

- `/tmp/codex_debate_prompt.md` — debate prompt sent to Codex
- `/tmp/codex_debate_verdict.md` — Codex's full 221-line verdict (38,859 tokens)
- `/home/hermes-pi/projects/cv-profile-assessment/ANALYSIS_phase3_debate_2026-09-02.md`
  — this synthesis document
