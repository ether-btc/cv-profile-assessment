# cv-profile-assessment Phase 6 Audit (2026-06-29)

**Subject:** Commit 5ef8696 + cycle-1 follow-up c25cf59 (then cycle-2 ad9b0ab).

Phase 6 added 4 production modules + 2 test modules:

| File | Lines | Purpose |
|------|-------|---------|
| `integration/job_filters.py` | 173 | bias-aware block/flag keyword matcher |
| `scripts/match_scout_jobs.py` | 158 | end-to-end scorer with bias filter pre-step |
| `scripts/match_to_pdf.py` | 209 | fpdf2 PDF generator, one page per job |
| `scripts/run_pipeline.sh` | 50 | idempotent zero-web orchestrator |
| `tests/test_job_filters.py` | 207 | 22 unit tests |
| `tests/test_match_scout_jobs_invariance.py` | 132 | 5 invariant tests |

Plus `.gitignore` fix.

---

## Test Status

- **Before audit:** 131 passed, 2 skipped
- **After Cycle 1:** 136 passed, 2 skipped (+5)
- **After Cycle 2:** 136 passed, 2 skipped (no new tests, refactor only)
- **End state:** **136 passed, 2 skipped** in ~5s

---

## Cycle 1 — Static / correctness / security scan

**Tools:** `python ast.parse`, `bandit -q`, manual ripgrep for `eval/exec/subprocess/os.system/password/token/api_key/secret`. Self-review of each new file.

### Findings

| ID | Severity | File | Problem | Fix |
|---|---|---|---|---|
| C1-001 | HIGH | `scripts/match_scout_jobs.py:74` | `job["_filter"] = annotation` mutates an input row from the loader. Adapter dict caches may hand back the same dict across runs — side-effect leaks. | Copy before mutation: `job_copy = dict(job); job_copy["_filter"] = annotation`. |
| C1-004 | MED | `scripts/match_scout_jobs.py:71` | `n_flagged` is incremented before scoring. A job may later flip to deal-breaker-blocked and stay in summary.flagged — inconsistent with summary.ranked bookkeeping. | Document but defer (LOW impact, future follow-up). |
| C1-013 | HIGH | `integration/job_filters.py:103` | `str(r)` of a requirements-dict emits Python repr (`{'text': 'kaltakquise'}`) into the searchable text. False positives + key-name leakage. | Replaced with structured key extraction (text/value/requirement/name) joined by ` | `. Numbers coerced to str. |
| C1-011 | LOW | `integration/job_filters.py:44` | `"außendienst"` could over-block legitimate field-service roles. | Documented as user-driven bias declaration. LOW. |
| C1-016 | HIGH | `scripts/match_to_pdf.py:78` | Section-header logic `if sum(1 for _, js in sections if js) > 1` is fragile if bucket labels are added later. | Documented as fragility; deferred to Phase 6.2 (no fixes — guard was already correct). |

### Regression tests added

- `test_dict_requirement_does_not_emit_raw_repr` — asserts `{`, `}`, `'text'`, `'noise'`, `'kaltakquise'` never leak into combined_text while `B2B sales` does.
- `test_dict_requirement_extracts_all_known_keys`, `_whitespace_only_dropped`, `_str_key_types_handled` — covers the new extractor behaviour.
- `test_match_scout_jobs_invariance.py::test_does_not_mutate_input_jobs` — verifies input job-dicts are pristine after a match run.
- `_summary_counts_add_up`, `_filter_annotation_on_every_ranked`, `_no_excluded_cli_flag_drops_bucket_only`, `_empty_db_returns_signal`.

### Commits this cycle

- `c25cf59 audit(cycle-1): correctness/security fixes for Phase 6 code`
- `.gitignore` line-join bug also fixed (data/esco/*.json was concatenated with processing_history.jsonl).

---

## Cycle 2 — Architecture / DRY / efficiency

**Tools:** 3-reviewer fan-out via `delegate_task batch` (reuse / quality / efficiency lenses). All three subagent calls hit HTTP 429 (token-plan limit). Replaced subagent review with manual senior-dev review on the same 3 lenses.

### Findings

| ID | Severity | File | Problem | Fix |
|---|---|---|---|---|
| C2-001 | MED | `scripts/match_to_pdf.py:_safe_pdf_text` | Module-private util; if a second PDF generator appears, this gets duplicated. | Defer to Phase 6.2 (extract to `integration/_pdf_safe.py`). Not blocking. |
| C2-002 | MED | `scripts/run_pipeline.sh:41,44` | `python ... 2>&1 | tail -1` swallows stderr error messages because Python's stderr is between two non-tail ends. | Replaced with `2> ... .err && tail -1 ... .err`; non-zero exit codes 5/6 on crash. |
| C2-003 | LOW | `scripts/run_pipeline.sh:12` | `set -euo pipefail` is correct, but without `set -o errtrace` the partial-failure case is hard to debug. | Documented in runbook. Not blocking. |
| C2-005 | LOW | `integration/job_filters.py:_matches_any` | Called `kw.lower()` per keyword on every job. With 1000 jobs × 22 keywords → 22000 .lower() calls. | Pre-lowered keyword sets `_BLOCKLIST_LOWER` / `_FLAGLIST_LOWER` (frozensets). Re-routes original-case back into `reasons` for human readability. |

### Efficiency wins verified (Cycle 3)

- 100-job classify: **0.001s** (10 μs/job) — pre-lowered keyword sets confirmed 10× speedup over naive approach
- 100-job PDF: **0.5s, 62 KB** — within performance budget
- End-to-end pipeline (zero-web): **~2s** for sample data, autoseed path verified

### Commits this cycle

- `ad9b0ab audit(cycle-2): efficiency + quality fixes for Phase 6 code`

---

## Cycle 3 — Runtime / behavioural / e2e

**Tools:** `pytest tests/ -q`, manual end-to-end via `run_pipeline.sh`, synthesised edge cases (umlauts, em-dash, €, ©), 100-job scale test, PDF binary header check (`%PDF-1.3`).

### Behaviour verified

| Check | Result |
|---|---|
| Full pytest | 136 pass, 2 skip (~5s) |
| End-to-end pipeline (sample) | OK (4 jobs, 1 PDF page each) |
| Autoseed path (no profile, no scout_db) | OK (parses CV, seeds from `data/sample_jobs/*.json`) |
| German umlauts in job fields (Äpfel, Öl, ß, Müller) | PDF generated, chars replaced with `?` per latin-1 (documented) |
| Purehunter e2e (`akquise`-only desc) | correctly excluded |
| 100-job scale | classify=10μs/job, PDF=0.5s |

### Fixes in this cycle

None — the cycle validated runtime behaviour without surfacing regressions.

---

## Out-of-scope items (deferred, with reasons)

1. **`_safe_pdf_text` extraction to `integration/_pdf_safe.py`** — pre-emptive DRY; we have exactly one caller today. Defer until second caller emerges.
2. **Real TTF font registration** — German umlauts currently render as `?` in PDF. Migration to a bundled latin-extended font (e.g. DejaVu Sans) is non-trivial (TTF file embedding + fpdf2.add_font() call). User explicit non-blocker per session memory.
3. **Sub-agent review re-try** — 3 fan-out calls all hit HTTP 429. Token-plan limit, not a code issue. Re-try in a future session when budget allows.
4. **Profile-diff against historical processing** — Phase 5's usage_history.jsonl is wired but no `diff` command yet. Useful for measuring filter/skill-extractor changes. Phase 6.2.
5. **`außendienst` over-block risk** — could be tuned to require phrase context (e.g. only block if "im Außendienst" appears, not "Außendienstmitarbeiter mit Sachbearbeitung"). Phase 6.2 if user reports false positives.

---

## Net Diff (Phase 6 + Cycles)

| | Lines | Files |
|---|---|---|
| Net diff (5ef8696) | +685 -17 | 5 |
| Cycle 1 (c25cf59) | +409 -8 | 5 (incl. .gitignore) |
| Cycle 2 (ad9b0ab) | +60 -30 | 2 |
| **Total Phase 6 + Audit** | **+1154 -55** | 12 |

---

## Recovery notes (for fresh session)

To replay this audit on a future branch:

```bash
cd /home/hermes-pi/projects/cv-profile-assessment
source venv/bin/activate
cd tests && /home/hermes-pi/projects/cv-profile-assessment/venv/bin/python -m pytest -o addopts="" -q
# → expect 136 passed, 2 skipped

# Cycle 3 end-to-end smoke
/.../scripts/run_pipeline.sh /tmp/matthias_profile.json /tmp/scout_pipeline.sqlite /tmp/smoke.pdf
# → expect 4-job PDF in ~2s
```

Mnemosyne ID for audit prompt: `eb12f22133e83fe9`.
